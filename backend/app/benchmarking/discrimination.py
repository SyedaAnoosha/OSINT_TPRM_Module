"""The discrimination test — does this signal vary enough across the cohort to rank anything?

WHY THIS EXISTS. A signal that every peer fails, or that every peer passes, cannot order suppliers.
It shifts the intercept and nothing else. Run by hand across the five-supplier corpus, this analysis
found SIX signals penalising 100% of the population and TWELVE that were constant-pass — nineteen of
twenty-seven contributing nothing to ordering, which is a finding about the model that no amount of
per-supplier reporting would have surfaced. This module runs that analysis per cohort, on every
build, so it stops being an occasional investigation and becomes a property of the artefact.

TWO STATISTICS, BECAUSE THERE ARE TWO KINDS OF DATA:

  * Continuous domain scores get IQR + coefficient of variation. Raw variance is scale-dependent —
    a variance of 9 means something different on a 0-100 score than on a 0-5 one — so the test is
    normalised. Zero IQR is checked separately because it is the unambiguous case: half the cohort
    sitting on one value is flat regardless of what the tails do.

  * Categorical signal bands get MODAL SHARE. Variance is undefined for strings; computing it anyway
    is how a discrimination test ends up taking the standard deviation of a set of words. Modal share
    also catches BOTH failure directions in one number — all-fail and all-pass are equally useless
    for ranking, and a flat tax is not a comparison.

WHAT HAPPENS TO A FLAGGED SIGNAL. It is suppressed from the "you are behind your peers" list, because
a line saying so would be false — the supplier is exactly where its peers are. It is DISCLOSED in its
own section, because "every supplier in your cohort fails this" is worth knowing. It is never
silently included and never silently dropped.

PER COHORT, NEVER GLOBAL. DMARC may be non-discriminating among enterprise financials and highly
discriminating among small manufacturers. A global verdict would average those into a number that is
true of neither.
"""

from __future__ import annotations

from collections import Counter

from .config import BenchmarkingConfig, get_benchmarking_config
from .models import DiscriminationVerdict, PeerRecord


def _percentile_value(sorted_values: list[int], pct: float) -> int | None:
    """Nearest-rank, no interpolation. Kept identical to the placement module's definition so a
    median quoted in a snapshot and a median quoted in a placement can never disagree."""
    if not sorted_values:
        return None
    k = max(0, min(len(sorted_values) - 1, int(round((pct / 100) * (len(sorted_values) - 1)))))
    return sorted_values[k]


def domain_discrimination(
    domain: str, values: list[int], cfg: BenchmarkingConfig | None = None
) -> DiscriminationVerdict:
    """Continuous scores: flat if the IQR is zero or the spread is negligible relative to the mean."""
    cfg = cfg or get_benchmarking_config()
    n = len(values)
    if n < cfg.discrimination_min_observations():
        return DiscriminationVerdict(
            key=domain, kind="domain", verdict="untested", statistic="coefficient_of_variation",
            observations=n,
            detail=f"only {n} peers scored for this domain (need "
                   f"{cfg.discrimination_min_observations()}) — not enough to test",
        )

    ordered = sorted(values)
    p25 = _percentile_value(ordered, 25) or 0
    p75 = _percentile_value(ordered, 75) or 0
    iqr = p75 - p25

    if cfg.zero_iqr_is_flat() and iqr == 0:
        return DiscriminationVerdict(
            key=domain, kind="domain", verdict="non_discriminating", statistic="iqr",
            value=0.0, observations=n,
            detail=f"the middle half of the cohort all score {p25} — this domain does not separate "
                   f"suppliers here",
        )

    mean = sum(ordered) / n
    # Guard the degenerate case: an all-zero domain has no mean to normalise against, and it is
    # obviously flat, so say so rather than dividing by zero.
    if mean == 0:
        return DiscriminationVerdict(
            key=domain, kind="domain", verdict="non_discriminating", statistic="mean",
            value=0.0, observations=n,
            detail=f"every one of {n} peers scores 0 for this domain",
        )

    variance = sum((v - mean) ** 2 for v in ordered) / n
    cv = (variance ** 0.5) / mean
    flat = cv < cfg.min_coefficient_of_variation()
    return DiscriminationVerdict(
        key=domain, kind="domain",
        verdict="non_discriminating" if flat else "discriminating",
        statistic="coefficient_of_variation", value=round(cv, 4), observations=n,
        detail=(
            f"spread is {round(cv * 100, 1)}% of the mean across {n} peers"
            + (f" — below the {cfg.min_coefficient_of_variation() * 100:g}% floor, so this domain "
               f"cannot rank them" if flat else f" (IQR {iqr})")
        ),
    )


def signal_discrimination(
    signal: str, bands: list[str], cfg: BenchmarkingConfig | None = None
) -> DiscriminationVerdict:
    """Categorical bands: flat when nearly everyone sits in the same band, either direction."""
    cfg = cfg or get_benchmarking_config()
    n = len(bands)
    if n < cfg.discrimination_min_observations():
        return DiscriminationVerdict(
            key=signal, kind="signal", verdict="untested", statistic="modal_share",
            observations=n,
            detail=f"only {n} peers were checked for this signal (need "
                   f"{cfg.discrimination_min_observations()}) — not enough to test",
        )

    counts = Counter(bands)
    modal_band, modal_count = counts.most_common(1)[0]
    share = modal_count / n
    flat = share >= cfg.max_modal_share()
    return DiscriminationVerdict(
        key=signal, kind="signal",
        verdict="non_discriminating" if flat else "discriminating",
        statistic="modal_share", value=round(share, 4), observations=n,
        detail=(
            f"{modal_count} of {n} peers observed in band `{modal_band}`"
            + (" — this signal is a constant across the cohort, not a comparison" if flat
               else f" ({len(counts)} distinct bands seen)")
        ),
    )


def discrimination_report(
    peers: list[PeerRecord], cfg: BenchmarkingConfig | None = None
) -> list[DiscriminationVerdict]:
    """Every domain and every signal observed across the cohort, tested and verdicted.

    Returns ALL verdicts, including `discriminating` and `untested`, rather than only the flagged
    ones. The caller filters; a function that returned only failures would make "we tested and it was
    fine" indistinguishable from "we never tested it".

    Domains and signals are keyed by whatever the peers actually carry, rather than against a fixed
    list, so a newly added domain is tested from its first build without a config edit.
    """
    cfg = cfg or get_benchmarking_config()

    domain_values: dict[str, list[int]] = {}
    signal_bands: dict[str, list[str]] = {}
    for peer in peers:
        for domain, value in peer.domains.items():
            if value is not None:
                domain_values.setdefault(domain, []).append(value)
        for signal, band in peer.signals.items():
            if band:
                signal_bands.setdefault(signal, []).append(band)

    out = [domain_discrimination(d, v, cfg) for d, v in sorted(domain_values.items())]
    out += [signal_discrimination(s, b, cfg) for s, b in sorted(signal_bands.items())]
    # Flagged first: the report exists to surface what cannot rank, and a reader should meet those
    # before the long tail of signals that are working fine.
    order = {"non_discriminating": 0, "untested": 1, "discriminating": 2}
    return sorted(out, key=lambda v: (order[v.verdict], v.kind, v.key))
