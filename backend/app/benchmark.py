"""Benchmarking — a vendor's posture read against its peers. Interpretation, never arithmetic.

THE ONE-SENTENCE CONTRACT. Nothing in this module can change a published posture. It reads scores
that already exist, computes a distribution over a cohort, and returns a `Benchmark` the scorecard
renders beside the number. If every line here were deleted, every score would be identical.

WHY THAT MATTERS MORE THAN IT SOUNDS. The obvious way to make scores industry-aware is to weight
categories differently per industry. `methodology.md` §5.6 deleted category weights precisely
because no authority publishes them and defending any particular set was a standing liability;
re-introducing them per industry would multiply that liability by twelve. So industry-awareness
lives HERE, where it changes the reading and not the reading's basis — the frozen regression
corpus still passes untouched, and no client's historical score silently moves.

FOUR FACTORS, AND THE PROBLEM THEY CREATE. A cohort is industry × revenue × headcount × region.
That is the right comparison and it is arithmetically brutal: 12 sectors × 5 revenue bands × 5
employee bands × 5 regions is **1,500 possible cohorts**, so requiring 8 peers in each would need
~12,000 scored vendors before the feature reliably said anything. Measured on a real deployment,
114 vendors produced exactly two populated cohorts, the largest holding four.

THE WIDENING LADDER IS THE ANSWER, AND DISCLOSURE IS WHAT MAKES IT HONEST. When the exact cohort
is too thin we step to a broader definition — drop region, then revenue, then headcount — and we
say so, in words, on the card: *"compared against Technology · 1k-10k staff (all regions), n=11;
region-specific peers unavailable (4 of 8)"*. A silently-widened cohort would be the worst of both
worlds: it would look like a precise comparison and be a loose one. **The ladder never widens past
sector.** Comparing a bank to every vendor ever scored is the meaningless comparison this whole
feature exists to refuse, so there is no rung below "same industry".

THE THRESHOLD IS STILL THE FEATURE. Below `min_cohort_n` at every rung, we publish no percentile.
It is tempting to show a median over three vendors; a median over three vendors is noise dressed
as precision, and manufacturing precision from thin evidence is the failure mode Finding A
punishes.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .models import (
    Benchmark,
    CategoryBenchmark,
    CohortStats,
    PeerCohort,
    SignalPrevalence,
    SizeBand,
    utcnow,
)

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "benchmarks.yaml"

# The four dimensions, in the order a cohort key is written.
DIMENSIONS = ("sector", "revenue_band", "employee_band", "region")

#: The peer floor, FLOORED IN CODE. A YAML edit may raise it; it may not lower it past here.
#: Mirrors `benchmarking/config.py::_ABSOLUTE_MIN_QUARTILE_N` deliberately — the two modules must
#: not disagree about the smallest population worth placing a supplier in, and this one is still
#: the default route until the cutover. See `BenchmarkConfig.min_cohort_n`.
_ABSOLUTE_MIN_COHORT_N = 8

_LEVEL_LABELS = {
    ("sector", "revenue_band", "employee_band", "region"): "industry + revenue + headcount + region",
    ("sector", "revenue_band", "employee_band"): "industry + revenue + headcount (all regions)",
    ("sector", "employee_band", "region"): "industry + headcount + region",
    ("sector", "revenue_band", "region"): "industry + revenue + region",
    ("sector", "employee_band"): "industry + headcount (all regions)",
    ("sector", "revenue_band"): "industry + revenue (all regions)",
    ("sector", "region"): "industry + region (all sizes)",
    ("sector",): "industry only (all sizes, all regions)",
}


class BenchmarkConfigError(ValueError):
    """Raised at load time. Fail loudly at startup, never quietly at serve time."""


@dataclass
class Peer:
    """One comparable vendor. Carries confidence and age because both bear on whether the
    comparison means anything, and both are reported rather than quietly assumed away."""

    vendor_ref: str
    posture: int
    confidence: float = 1.0
    computed_at: datetime | None = None
    categories: dict[str, int] = field(default_factory=dict)
    # signal -> observed band, for prevalence. Absent when the peer was never checked for it,
    # which is different from failing it and must not be counted as failing.
    signals: dict[str, str] = field(default_factory=dict)


# A lookup takes a partial set of cohort dimensions and returns the vendors matching ALL of them.
# Passing a callable rather than a store keeps this module free of persistence concerns and makes
# every widening path testable without a database.
PeerLookup = Callable[[dict[str, str]], list[Peer]]


class BenchmarkConfig:
    def __init__(self, data: dict[str, Any], path: Path) -> None:
        self._d = data
        self.path = path
        self._targets: Any = None
        self._validate()

    # --- accessors ---

    def min_cohort_n(self) -> int:
        """The peer floor, with a HARD LOWER BOUND IN CODE. A YAML edit may raise it, never lower it.

        E11's finding, closed here rather than at the cutover. The shipped file carried
        `min_cohort_n: 1` — a demo setting that survived into production, which is
        indistinguishable from a decision nobody made — and it let this module publish a "median"
        and a "percentile" over a SINGLE company. A percentile against one peer is not a weak
        comparison, it is a coin flip presented as a statistic.

        EB floors its two thresholds in code for exactly this reason and says so in its module
        docstring: a YAML floor alone would let the same thing recur. The deprecated path gets the
        same treatment, because it is still the DEFAULT route and `run_pipeline` still writes its
        output onto every scored vendor — so "it goes away next release" is a reason to fix it
        now, not a reason to leave it.

        8 is where a quartile stops being arithmetic theatre: below it a single peer is more than
        an eighth of the population, so a placement can flip on one supplier joining.
        """
        return max(_ABSOLUTE_MIN_COHORT_N, int(self._d.get("cohort", {}).get("min_cohort_n", 8)))

    def widening(self) -> list[tuple[str, ...]]:
        """The ladder, most-specific first. Configurable because which dimension to relax first is
        a risk-appetite judgement, and the AFA is explicit that those belong to the user."""
        raw = self._d.get("cohort", {}).get("widening")
        if not raw:
            return [
                ("sector", "revenue_band", "employee_band", "region"),
                ("sector", "revenue_band", "employee_band"),
                ("sector", "employee_band", "region"),
                ("sector", "employee_band"),
                ("sector", "region"),
                ("sector",),
            ]
        return [tuple(level) for level in raw]

    def max_peer_age_days(self) -> int | None:
        value = self._d.get("cohort", {}).get("max_peer_age_days")
        return int(value) if value else None

    def min_peer_confidence(self) -> float:
        return float(self._d.get("cohort", {}).get("min_peer_confidence", 0.0))

    def min_signal_peers(self) -> int:
        """Peers that must have been CHECKED for a control before its prevalence is published.
        A pass rate over three vendors is a rumour with a percent sign on it."""
        return int(self._d.get("cohort", {}).get("min_signal_peers", 5))

    def severity_of(self, signal: str, band: str) -> str | None:
        """The severity `scoring.yaml` assigns this observed band, or None if it lists neither.

        One definition of what an observation MEANS, held in scoring.yaml — prevalence never
        re-derives it. Note that `_is_pass` then draws a different line across those severities
        than the engine does: since E2 an `informational` band costs nothing yet still means the
        control is absent, and prevalence cares about absence.
        """
        from .scoring_config import get_scoring_config

        cfg = get_scoring_config()
        for category in cfg.category_names():
            severity = cfg.signal_severity(category, signal, band)
            if severity is not None:
                return severity
        return None

    def employee_bands(self) -> dict[str, int]:
        return dict(self._d.get("size_bands", {}).get("employees", {}))

    def revenue_bands(self) -> dict[str, int]:
        return dict(self._d.get("size_bands", {}).get("revenue_aud", {}))

    def fx_to_aud(self) -> dict[str, float]:
        return {k.upper(): float(v) for k, v in (self._d.get("fx_to_aud") or {}).items()}

    def self_selection_caveat(self) -> str:
        return str(self._d.get("disclosure", {}).get("self_selection_caveat", "")).strip()

    def targets(self) -> Any:
        """The target maturity model — a PUBLISHED baseline, independent of the peer pool.

        Built once and cached on the config object: the profiles are validated at construction, so
        re-parsing per request would repeat that work on every scorecard render.
        """
        from .targets import TargetConfig

        if self._targets is None:
            self._targets = TargetConfig(self._d)
        return self._targets

    def expected_posture(self, sector: str) -> tuple[int, str] | None:
        """A cited sector expectation, or None. A number without a basis never reaches here —
        `_validate` rejects the file at load rather than letting an uncited threshold ship."""
        entry = (self._d.get("expected_posture") or {}).get(sector)
        if not entry:
            return None
        return int(entry["value"]), str(entry["basis"])

    # --- validation ---

    def _validate(self) -> None:
        expected = self._d.get("expected_posture") or {}
        if not isinstance(expected, dict):
            raise BenchmarkConfigError("expected_posture must be a mapping of sector -> {value, basis}")
        for sector, entry in expected.items():
            if not isinstance(entry, dict) or "value" not in entry:
                raise BenchmarkConfigError(f"expected_posture.{sector} needs a `value`")
            if not str(entry.get("basis") or "").strip():
                # The same rule scoring.yaml applies to `reasons`: a number a client cannot trace
                # to a source is an opinion, and opinions do not get to look like measurements.
                raise BenchmarkConfigError(
                    f"expected_posture.{sector} has no `basis` — an expected posture without a "
                    f"named source is an assertion, and this file does not ship assertions"
                )
        # `min_cohort_n` is no longer validated here and cannot be: `min_cohort_n()` floors it at
        # `_ABSOLUTE_MIN_COHORT_N`, so a `< 1` check is unreachable. A silently-raised value beats
        # a startup failure for this one setting — a deployment that typed `1` gets 8 and a working
        # system, rather than an outage over a number the code was always going to override.
        # Asserted by `test_the_peer_floor_cannot_be_lowered_by_a_config_edit`.

        # Build the target model at LOAD time purely for its validation side-effect. A control with
        # no `basis` must stop the process at startup, not surface as a broken card at serve time —
        # the same reason `expected_posture` is checked here rather than lazily.
        self.targets()

        for level in self.widening():
            unknown = set(level) - set(DIMENSIONS)
            if unknown:
                raise BenchmarkConfigError(f"cohort.widening uses unknown dimension(s): {unknown}")
            if "sector" not in level:
                # The floor of the ladder, and it is not negotiable. A rung without `sector` would
                # compare a bank against every vendor ever scored — the exact comparison this
                # feature exists to refuse.
                raise BenchmarkConfigError(
                    f"cohort.widening level {level} omits `sector`: a peer group that crosses "
                    f"industries is not a peer group"
                )


def load_benchmark_config(path: Path | None = None) -> BenchmarkConfig:
    from .config import get_settings

    p = path or get_settings().benchmarks_yaml_path or _DEFAULT_PATH
    if not p.exists():
        raise BenchmarkConfigError(f"benchmarks.yaml not found at {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return BenchmarkConfig(data, p)


@lru_cache
def get_benchmark_config() -> BenchmarkConfig:
    return load_benchmark_config()


# --------------------------------------------------------------------- size banding


def employee_band_for(employees: int | float | None,
                      cfg: BenchmarkConfig | None = None) -> SizeBand | None:
    """Headcount -> band. None when unknown; an unsized vendor is never guessed into a band."""
    cfg = cfg or get_benchmark_config()
    return _band_from(employees, cfg.employee_bands())


def revenue_band_for(revenue: int | float | None, currency: str | None = None,
                     cfg: BenchmarkConfig | None = None) -> SizeBand | None:
    """Revenue -> band, converted to AUD for BANDING ONLY.

    The reported revenue always keeps its own currency on the profile: band edges are
    order-of-magnitude boundaries so a stale rate cannot move a vendor except at the margin, but a
    converted figure shown to a user would be a number we invented. An unconvertible currency
    yields no band rather than being silently treated as AUD.
    """
    cfg = cfg or get_benchmark_config()
    return _band_from(_to_aud(revenue, currency, cfg), cfg.revenue_bands())


_ORDER: list[SizeBand] = ["micro", "small", "medium", "large", "mega"]


def _band_from(value: float | None, bounds: dict[str, int]) -> SizeBand | None:
    if value is None or value < 0:
        return None
    for band in _ORDER[:-1]:
        limit = bounds.get(band)
        if limit is not None and value < limit:
            return band
    return _ORDER[-1]


def _to_aud(amount: float | int | None, currency: str | None,
            cfg: BenchmarkConfig) -> float | None:
    if amount is None:
        return None
    if not currency:
        return float(amount)
    rate = cfg.fx_to_aud().get(str(currency).upper())
    return float(amount) * rate if rate else None


def cohort_key(sector: str, revenue_band: str | None, employee_band: str | None,
               region: str) -> str:
    """Canonical four-factor key. Unknown size dimensions are written explicitly as `?` so a key
    never silently means two different things."""
    return f"{sector}|rev={revenue_band or '?'}|emp={employee_band or '?'}|{region}"


# --------------------------------------------------------------------- the benchmark


def cohort_stats(cohort: PeerCohort, peers: list[Peer], excluded_stale: int = 0) -> CohortStats:
    """Distribution over the cohort. `n` travels with it, always — a percentile whose population
    is hidden is a bought black-box score with extra steps."""
    postures = sorted(p.posture for p in peers if p.posture is not None)
    if not postures:
        return CohortStats(cohort=cohort, n=0, excluded_stale=excluded_stale)

    confidences = sorted(p.confidence for p in peers if p.confidence is not None)
    ages = [(utcnow() - p.computed_at).days for p in peers if p.computed_at]
    return CohortStats(
        cohort=cohort, n=len(postures),
        median=_percentile_value(postures, 50),
        p25=_percentile_value(postures, 25),
        p75=_percentile_value(postures, 75),
        minimum=postures[0], maximum=postures[-1],
        median_confidence=round(_percentile_value(confidences, 50), 3) if confidences else None,
        oldest_peer_days=max(ages) if ages else None,
        excluded_stale=excluded_stale,
    )


def resolve_peers(
    cohort: PeerCohort, lookup: PeerLookup, cfg: BenchmarkConfig | None = None,
) -> tuple[list[Peer], tuple[str, ...] | None, int, int]:
    """Walk the widening ladder until a rung holds enough peers.

    Returns `(peers, level_used, best_n_seen, stale_dropped)`. `level_used` is None when no rung
    reached the minimum — in which case `peers` is the deepest population we found, so the caller
    can still report honestly how close it came rather than just saying no.
    """
    cfg = cfg or get_benchmark_config()
    minimum = cfg.min_cohort_n()
    dims_available = {
        "sector": cohort.sector,
        "revenue_band": cohort.revenue_band,
        "employee_band": cohort.employee_band,
        "region": cohort.region,
    }

    deepest: list[Peer] = []
    deepest_stale = 0
    for level in cfg.widening():
        # A rung that needs a dimension this vendor does not have cannot be evaluated — skip it
        # rather than matching on a null, which would silently pool every unsized vendor together.
        if any(dims_available.get(d) is None for d in level):
            continue
        candidates = lookup({d: dims_available[d] for d in level})
        fresh, stale = _filter_peers(candidates, cfg)
        if len(fresh) > len(deepest):
            deepest, deepest_stale = fresh, stale
        if len(fresh) >= minimum:
            return fresh, level, len(fresh), stale
    return deepest, None, len(deepest), deepest_stale


def _filter_peers(peers: list[Peer], cfg: BenchmarkConfig) -> tuple[list[Peer], int]:
    """Drop peers that are too stale or too thinly evidenced to belong in a median.

    Both filters are disclosed rather than silent: a comparison against year-old scores, or
    against a population of Ghosts, is a different claim from a comparison against current,
    well-evidenced ones, and the reader is the one who gets to decide whether that matters.
    """
    max_age = cfg.max_peer_age_days()
    min_conf = cfg.min_peer_confidence()
    now = utcnow()

    kept: list[Peer] = []
    stale = 0
    for p in peers:
        if min_conf and p.confidence is not None and p.confidence < min_conf:
            continue
        if max_age and p.computed_at and (now - p.computed_at).days > max_age:
            stale += 1
            continue
        kept.append(p)
    return kept, stale


def _synthetic_baseline_peers(sector: str, categories: dict[str, int] | None = None) -> list[Peer]:
    base_postures = [65, 72, 78, 83, 89, 94]
    cats = categories or {
        "cyber_hygiene_technical": 78, "breach_compromise_history": 85,
        "vendor_transparency_gov": 80, "digital_footprint_assets": 75,
        "business_financial_stability": 82, "compliance_regulatory": 85,
        "adverse_media_reputation": 90,
    }
    peers = []
    for i, p in enumerate(base_postures):
        p_cats = {k: max(30, min(100, v + (i - 2) * 5)) for k, v in cats.items()}
        p_signals = {
            "dnssec_valid": "ok" if i >= 2 else "missing",
            "dmarc_policy": "reject" if i >= 1 else "none",
            "tls_certificate": "valid",
            "spf_policy": "strict" if i >= 2 else "softfail",
        }
        peers.append(Peer(
            vendor_ref=f"ref-peer-{i+1}",
            posture=p,
            confidence=0.85,
            categories=p_cats,
            signals=p_signals,
        ))
    return peers


def build_benchmark(
    posture: int | None,
    cohort: PeerCohort | None,
    lookup: PeerLookup,
    categories: dict[str, int] | None = None,
    cfg: BenchmarkConfig | None = None,
    signals: dict[str, str] | None = None,
    gap_drivers: dict[str, list[str]] | None = None,
    subject_confidence: float | None = None,
    vendor_age_years: float | None = None,
) -> Benchmark:
    """The published comparison — or a baseline industry cohort comparison.

    `lookup` must EXCLUDE the subject vendor: a cohort of one is not a peer group, and letting a
    vendor into its own comparison guarantees a flattering percentile at small n.
    """
    cfg = cfg or get_benchmark_config()

    if cohort is None:
        # Build a fallback cohort so every vendor gets a peer comparison.
        # `region` must be a member of the Region literal — "us" is not one, and using it here
        # raised a ValidationError that took out the whole no-cohort path rather than degrading it.
        cohort = PeerCohort(
            sector="technology", employee_band="medium", region="other",
            key=cohort_key("technology", None, "medium", "other"),
        )

    # Computed BEFORE the posture gate and attached to every return path, including the ones that
    # publish no percentile. That is the entire reason this measure exists: a target model needs no
    # peers, so it still has something true to say exactly when the cohort does not — a thin peer
    # group, a niche sector, or the first vendor a deployment ever scores.
    maturity_gap = _maturity_gap(cfg, signals or {}, cohort.sector, vendor_age_years)

    if posture is None:
        return Benchmark(
            available=False, posture=None,
            reason="no published posture to compare (blocked or insufficient evidence)",
            caveats=_standing_caveats(cfg),
            maturity_gap=maturity_gap,
        )

    peers, level, best_n, stale = resolve_peers(cohort, lookup, cfg)
    is_synthetic = False
    if not peers or level is None:
        peers = _synthetic_baseline_peers(cohort.sector, categories)
        level = ("sector",)
        stale = 0
        is_synthetic = True

    stats = cohort_stats(cohort, peers, excluded_stale=stale)
    minimum = cfg.min_cohort_n()

    postures = [p.posture for p in peers]
    percentile, resolution = _percentile_rank(postures, posture)
    exact = tuple(cfg.widening()[0])
    widened = tuple(level) != exact
    outlier = _is_outlier(postures, posture)
    confidence, confidence_band = _benchmark_confidence(stats, widened, cfg, subject_confidence)

    provisional = is_synthetic or stats.n < minimum + 3
    caveats = _caveats(cfg, stats, level, widened, minimum)
    if not is_synthetic and provisional:
        caveats.insert(0, (
            f"Provisional: this cohort ({stats.n} peers) only just cleared the minimum of "
            f"{minimum}. One peer joining or leaving could move the percentile — treat it as an "
            f"early read, not a settled position."
        ))
    if outlier:
        caveats.insert(0, (
            "This vendor sits below the normal range for its peer group. Being far behind one's "
            "own industry is a finding in itself, even where the absolute score looks moderate."
        ))
    if confidence_band == "Low":
        caveats.insert(0, (
            f"Low benchmark confidence ({confidence}): the comparison itself is weakly supported. "
            f"Read the absolute grade first."
        ))

    # LAST, so it lands FIRST. Every other caveat qualifies a real comparison; this one says there
    # is no real comparison to qualify. It has to outrank them, and inserting it earlier let the
    # outlier and low-confidence caveats push it down the list — where a reader meets "low
    # confidence" and concludes the peers are real but thin, which is the opposite of the truth.
    if is_synthetic:
        caveats.insert(0, (
            f"NOT REAL PEERS. No vendor in this deployment shares this cohort, so the comparison "
            f"uses a fixed industry reference baseline. The '{stats.n}' below counts reference "
            f"points, not companies — no other company was assessed for this comparison. Read the "
            f"absolute posture first, and treat the percentile as illustrative only."
        ))

    # E11 / EB DECISION 3, APPLIED TO THE DEPRECATED PATH TOO. A synthetic baseline yields NO
    # ORDINAL PLACEMENT — no percentile, no quartile, no variance-from-median — at any n.
    #
    # The caveat above is strong, leads the list, and is still not enough. Six invented postures
    # produce a real-looking "78th percentile" that a reader screenshots into a slide, and the
    # caption does not travel with the screenshot. That is the Sprint-0 defect exactly, and this
    # module is not a museum piece: it still serves `/api/vendors/{ref}/benchmark` and
    # `run_pipeline` still writes its output onto every scored vendor, so leaving it here until the
    # cutover means shipping it for another release.
    #
    # The reference baseline itself STAYS. EB's cold-start decision is that a labelled external
    # reference line is legitimate context — it is a population statistic, never a peer median. So
    # the categories, the signal prevalence and the caveat survive; only the ordinal placement,
    # which requires real peers to mean anything, is withheld.
    if is_synthetic:
        percentile = None
        resolution = None

    return Benchmark(
        available=True, posture=posture, stats=stats,
        percentile=percentile, percentile_resolution=resolution,
        quartile=None if is_synthetic else _quartile(postures, posture),
        variance_from_median=(
            None if is_synthetic
            else ((posture - stats.median) if stats.median is not None else None)
        ),
        categories=_category_benchmarks(categories or {}, peers, gap_drivers),
        signals=_signal_prevalence(signals or {}, peers, cfg),
        outlier=outlier,
        confidence=confidence, confidence_band=confidence_band,
        level=_LEVEL_LABELS.get(tuple(level), " + ".join(level)),
        widened=widened,
        synthetic=is_synthetic,
        provisional=provisional,
        caveats=caveats,
        maturity_gap=maturity_gap,
        **_expected(cfg, cohort.sector),
    )


def _maturity_gap(cfg: BenchmarkConfig, signals: dict[str, str], sector: str,
                  vendor_age_years: float | None):
    """Measure against the published baseline, never letting it sink the peer comparison.

    Isolated because the two readings are independent: a malformed target profile must not cost a
    reader their percentile, and a thin cohort must not cost them their baseline. Each degrades
    alone.
    """
    from .targets import build_maturity_gap

    try:
        return build_maturity_gap(signals, sector, cfg.targets(), vendor_age_years)
    except Exception:  # noqa: BLE001 — context beside the score, never worth the whole card
        return None


# --------------------------------------------------------------------- reporting helpers


def _category_benchmarks(subject: dict[str, int], peers: list[Peer],
                         drivers: dict[str, list[str]] | None = None) -> list[CategoryBenchmark]:
    """Per-category comparison against the same peers.

    Only peers that actually COVERED a category count toward its median. A vendor whose trust page
    was unreachable has no compliance posture, and treating that absence as a low score would drag
    the category median down with a collection failure — the same "missing data is not a bad
    result" rule the scoring engine applies one level up.

    A per-category PERCENTILE matters as much as the overall one: a vendor can sit top-quartile
    overall and bottom-quartile on the single category a given buyer cares about, and an overall
    figure hides exactly that.
    """
    drivers = drivers or {}
    out: list[CategoryBenchmark] = []
    for category, value in sorted(subject.items()):
        values = sorted(p.categories[category] for p in peers
                        if category in p.categories and p.categories[category] is not None)
        median = _percentile_value(values, 50) if values else None
        variance = (value - median) if (median is not None and value is not None) else None
        out.append(CategoryBenchmark(
            category=category, posture=value, median=median,
            variance_from_median=variance,
            percentile=_percentile_rank(values, value)[0] if values else None,
            n=len(values),
            # Only for a NEGATIVE gap. Naming "what put you here" on a category you lead would be
            # noise; naming it on one you lag is a to-do list.
            gap_drivers=drivers.get(category, []) if (variance or 0) < 0 else [],
        ))
    return out


def _signal_prevalence(subject_signals: dict[str, str], peers: list[Peer],
                       cfg: BenchmarkConfig) -> list[SignalPrevalence]:
    """How common each control is among peers — reported for the signals this vendor FAILS.

    This is the sharpest line the benchmark can produce. "-20, no DMARC record" says a vendor fell
    short of our model, which is arguable. "79% of your peers publish one" says it fell short of
    its own industry, which is not — and it is the single figure a vendor can take to their own
    board and get budget with.

    Two disciplines carried over from the scoring engine:
      * a peer that was never CHECKED for a signal is not a peer that FAILED it, so it is excluded
        from the denominator rather than counted against the industry;
      * below the minimum sample we publish nothing, because a pass rate over three vendors is a
        rumour with a percent sign on it.
    """
    minimum = cfg.min_signal_peers()
    out: list[SignalPrevalence] = []

    for signal, band in sorted(subject_signals.items()):
        subject_passes = _is_pass(signal, band, cfg)
        # Only report on what this vendor is actually behind on, or clearly ahead on. A control
        # everyone including this vendor has is not worth a line on the card.
        checked = [p.signals[signal] for p in peers if signal in p.signals]
        if len(checked) < minimum:
            continue
        passing = sum(1 for b in checked if _is_pass(signal, b, cfg))
        rate = passing / len(checked)

        if subject_passes and rate >= 0.5:
            continue  # they pass and so does most of the industry — unremarkable
        standing = "ahead" if (subject_passes and rate < 0.5) else \
                   "behind" if (not subject_passes and rate >= 0.5) else "typical"
        out.append(SignalPrevalence(
            signal=signal, band=band, passing=subject_passes,
            peers_checked=len(checked), peers_passing=passing,
            peer_pass_rate=round(rate, 3), standing=standing,
        ))
    # Worst standing first: what a reader needs is the controls the industry has and they do not.
    order = {"behind": 0, "typical": 1, "ahead": 2}
    return sorted(out, key=lambda s: (order[s.standing], s.peer_pass_rate))


def _is_pass(signal: str, band: str, cfg: BenchmarkConfig) -> bool:
    """Does this vendor HAVE the control?

    NOT the same question as "does this band cost points", and E2 is what pulled the two apart.
    They used to coincide: every absence penalised, so "not penalised" meant "present". E2
    reclassified eight absence bands to `informational` — penalising a control at 7% adoption
    penalises the norm — but the vendor still does not have the control.

    Prevalence is the one place that distinction IS the point. Counting `informational` as a pass
    made every peer "have" DNSSEC, so nobody was ever ahead or behind on it, and the sharpest line
    the benchmark produces vanished for precisely the low-base-rate controls where "you are ahead
    of 85% of your peers" is most worth saying. A caught regression, not a stale test.

    `None` — a band the scoring model does not list at all — still reads as a pass: never tell a
    vendor they lack a control we do not model.
    """
    severity = cfg.severity_of(signal, band)
    return severity in (None, "pass")


def _is_outlier(postures: list[int], posture: int) -> bool:
    """Below the cohort's lower fence (p25 − 1.5×IQR).

    DELIBERATELY NOT STANDARD DEVIATIONS, which is the usual choice. SD assumes a roughly normal
    spread and is badly destabilised by one extreme member — and at the sample sizes this feature
    actually runs at (n=8-20), one member IS a large share of the population. The IQR fence is the
    standard robust alternative and does not fall over on a small, skewed cohort.
    """
    if len(postures) < 4:
        return False
    ordered = sorted(postures)
    p25 = _percentile_value(ordered, 25)
    p75 = _percentile_value(ordered, 75)
    iqr = p75 - p25
    return posture < (p25 - 1.5 * iqr)


def _benchmark_confidence(stats: CohortStats, widened: bool, cfg: BenchmarkConfig,
                          subject_confidence: float | None) -> tuple[float, str]:
    """How much weight this COMPARISON bears — a second axis on the benchmark itself.

    The score already refuses to publish a bare number without its coverage. A benchmark deserves
    the same treatment for the same reason: it can be computed from a thin, widened, stale cohort
    of thinly-evidenced peers and still print a confident-looking percentile. Four inputs, each of
    which independently makes a comparison worth less:

      * SAMPLE   — how far past the minimum the cohort actually got;
      * EXACTNESS— whether the ladder had to widen to find peers at all;
      * PEER EVIDENCE — a cohort of Ghosts produces a Ghost median;
      * FRESHNESS— year-old peer scores describe a different industry than today's.
    """
    minimum = max(1, cfg.min_cohort_n())
    sample = min(1.0, stats.n / (minimum * 2))          # 2x the gate = full marks
    exactness = 0.7 if widened else 1.0
    peer_evidence = stats.median_confidence if stats.median_confidence is not None else 0.8
    freshness = 1.0
    if stats.oldest_peer_days:
        freshness = max(0.5, 1.0 - (stats.oldest_peer_days / 730))   # 2 years -> floor

    value = sample * exactness * peer_evidence * freshness
    # A thinly-evidenced SUBJECT cannot be meaningfully placed either: comparing a Ghost's posture
    # against a distribution compares one number we do not stand behind with several we do.
    if subject_confidence is not None:
        value *= max(0.5, min(1.0, subject_confidence + 0.2))

    value = round(max(0.0, min(1.0, value)), 3)
    band = "High" if value >= 0.75 else "Medium" if value >= 0.5 else "Low"
    return value, band


def _caveats(cfg: BenchmarkConfig, stats: CohortStats, level: tuple[str, ...],
             widened: bool, minimum: int) -> list[str]:
    """Everything a reader needs in order to read the comparison correctly. UI requirements."""
    out: list[str] = []
    if widened:
        missing = [d for d in DIMENSIONS if d not in level]
        pretty = {"region": "region", "revenue_band": "revenue", "employee_band": "headcount"}
        dropped = ", ".join(pretty.get(d, d) for d in missing)
        out.append(
            f"Exact peer group was too thin, so this compares against a wider population — "
            f"{dropped} not matched. Read the variance as indicative, not precise."
        )
    if stats.n < minimum * 2:
        out.append(
            f"Small sample (n={stats.n}): one unusual peer moves the median noticeably. "
            f"The quartile is more robust than the percentile here."
        )
    if stats.median_confidence is not None and stats.median_confidence < 0.7:
        out.append(
            f"Peers are themselves thinly evidenced (median coverage "
            f"{round(stats.median_confidence * 100)}%), so the median reflects what is publicly "
            f"visible about them rather than their full posture."
        )
    if stats.excluded_stale:
        out.append(f"{stats.excluded_stale} peer score(s) excluded as stale.")
    out.extend(_standing_caveats(cfg))
    return out


def _standing_caveats(cfg: BenchmarkConfig) -> list[str]:
    """The limitation that never goes away and so must never be omitted."""
    caveat = cfg.self_selection_caveat()
    return [caveat] if caveat else []


def _expected(cfg: BenchmarkConfig, sector: str) -> dict[str, Any]:
    cited = cfg.expected_posture(sector)
    if cited is None:
        return {"expected_posture": None, "expected_basis": None}
    return {"expected_posture": cited[0], "expected_basis": cited[1]}


def _percentile_value(sorted_values: list[float], pct: float) -> Any:
    """Nearest-rank percentile. No interpolation: these are small samples, and an interpolated
    median between two real vendors is a company that does not exist."""
    if not sorted_values:
        return None
    k = max(0, min(len(sorted_values) - 1, int(round((pct / 100) * (len(sorted_values) - 1)))))
    return sorted_values[k]


def _percentile_rank(peers: list[int], posture: int) -> tuple[int, int]:
    """Percentile, rounded to the finest step the sample can actually express.

    With 8 peers the resolution is 12.5 points, so quoting an 83rd percentile would imply a
    precision the data cannot support. We round to the achievable step and publish the step
    alongside it, so a reader can see how coarse the measure really is.
    """
    if not peers:
        return 0, 100
    # CEIL, not round: with 8 peers the achievable steps are 12.5 apart, and `round` would report
    # 12 — claiming a finer resolution than the sample can express, which is the exact overstatement
    # this function exists to prevent. Rounding up never overstates precision.
    resolution = max(1, math.ceil(100 / len(peers)))
    at_or_below = sum(1 for p in peers if p <= posture)
    raw = 100 * at_or_below / len(peers)
    # Clamp: snapping to a coarse step can overshoot (6 peers -> step 17 -> 6x17 = 102).
    snapped = int(round(raw / resolution) * resolution)
    return max(0, min(100, snapped)), resolution


def peer_lookup(store: Any, *, exclude_ref: str | None = None) -> PeerLookup:
    """Adapt a store into the `PeerLookup` the widening ladder calls.

    Kept here rather than in the API so every caller — endpoint, CLI, test — walks the ladder the
    same way, and so `benchmark.py` itself stays free of persistence concerns.
    """
    from .models import Score

    def lookup(dims: dict[str, str]) -> list[Peer]:
        # Per-signal bands for the same population, in one query rather than one per peer.
        bands: dict[str, dict[str, str]] = {}
        try:
            for ref, signal, band in store.cohort_signal_bands(dims, exclude_ref=exclude_ref):
                bands.setdefault(ref, {})[signal] = band
        except (AttributeError, NotImplementedError):
            # A store without prevalence support still benchmarks; it just cannot say how common
            # a control is. Degrading is right — losing the whole comparison would not be.
            bands = {}

        peers: list[Peer] = []
        for row in store.cohort_peers(dims, exclude_ref=exclude_ref):
            categories: dict[str, int] = {}
            raw = row.get("score_json")
            if raw:
                try:
                    categories = {c.category: c.posture
                                  for c in Score.model_validate_json(raw).categories
                                  if c.posture is not None}
                except (ValueError, TypeError):
                    # A malformed stored score must not sink a whole benchmark — the peer simply
                    # contributes to the overall median without per-category detail.
                    categories = {}
            peers.append(Peer(
                vendor_ref=row["vendor_ref"],
                posture=int(row["posture"]),
                confidence=float(row.get("overall_confidence") or 0.0),
                computed_at=_parse_dt(row.get("computed_at")),
                categories=categories,
                signals=bands.get(row["vendor_ref"], {}),
            ))
        return peers

    return lookup


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _quartile(peers: list[int], posture: int) -> int:
    """1 = bottom quarter … 4 = top quarter. Robust where a percentile is not: a claim of 'top
    quartile' survives one peer joining or leaving, which an 83rd percentile does not."""
    if not peers:
        return 1
    at_or_below = sum(1 for p in peers if p <= posture)
    share = at_or_below / len(peers)
    if share <= 0.25:
        return 1
    if share <= 0.50:
        return 2
    if share <= 0.75:
        return 3
    return 4
