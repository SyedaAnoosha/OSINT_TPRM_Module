"""Placement — where a supplier sits, at the resolution the sample can actually express.

THE FOUR HARD RULES, ENFORCED IN ONE FUNCTION (`place`) SO THEY CANNOT DIVERGE:

    is_synthetic          -> nothing. No percentile, no quartile, at ANY n.
    n < min_quartile_n    -> "Insufficient peer data", with the actual n.
    n < min_percentile_n  -> quartile + rank-of-n. NO percentile.
    otherwise             -> percentile, with its resolution published beside it.

Every caller routes through `place`. A second implementation of these thresholds — in an export, in a
summary card, in a CSV writer — is a second answer to the only question this module exists to answer,
and the two would drift within a release.

THREE ESTIMATOR DECISIONS THAT ARE EASY TO GET WRONG, AND WHY THEY GO THIS WAY:

  * TIES USE MIDRANK. Postures are integers 0-100; at n=40 collisions are certain. The obvious
    `at-or-below / n` pushes a supplier tied with ten others at the median ABOVE the 50th percentile,
    which is a real error rather than a rounding artefact. Midrank credits half the tie:
    `(below + 0.5 x equal) / n`.

  * `rank_of_n` IS REQUIRED, NOT OPTIONAL. "17th of 34" needs no estimator choice, cannot overstate
    its own precision, and survives one peer joining. At n=8-29 it is strictly more informative than
    a quartile letter, and it is the sentence a procurement reader repeats without mangling.

  * OUTLIERS USE THE IQR FENCE, NOT STANDARD DEVIATIONS. SD assumes a roughly normal spread and is
    badly destabilised by one extreme member — and at the sample sizes this feature actually runs at,
    one member IS a large share of the population.

AND ONE LABELLING DECISION. `quartile: 1` ships with `quartile_label` and `quartile_direction`
always, because "Q1" means the BEST quarter in finance and the WORST quarter almost everywhere else.
A bare quartile number is a coin flip on whether the reader inverts the finding.
"""

from __future__ import annotations

import math
from datetime import datetime

from ..models import utcnow
from .config import BenchmarkingConfig, get_benchmarking_config
from .models import (
    OPEN_DISPUTE_STATES,
    BenchmarkPlacement,
    CohortAssignment,
    CohortDispute,
    CohortSnapshot,
    Direction,
    DomainPlacement,
    Placement,
    PlacementBucket,
    PlacementDelta,
    ReliabilityFactors,
    SupplierFirmographics,
)
from .narrative import render_procurement, render_security
from .snapshot import _percentile_value

_QUARTILE_LABELS = {
    1: "bottom quartile",
    2: "lower-middle quartile",
    3: "upper-middle quartile",
    4: "top quartile",
}

_QUARTILE_BUCKETS: dict[int, PlacementBucket] = {
    1: "bottom_quartile",
    2: "lower_mid",
    3: "upper_mid",
    4: "top_quartile",
}

_DOMAIN_LABELS = {
    "email_auth": "Email authentication",
    "attack_surface": "Attack surface",
    "breach_history": "Breach history",
    "vulnerability": "Vulnerability exposure",
    "transparency": "Transparency and disclosure",
    "identity_email": "Identity and email",
    "regulatory": "Regulatory standing",
}


def domain_label(domain: str) -> str:
    """A humanised name, or the key tidied up. Never a key rendered raw into prose."""
    return _DOMAIN_LABELS.get(domain, domain.replace("_", " ").capitalize())


# --------------------------------------------------------------------------- the estimators


def midrank_percentile(values: list[int], subject: int) -> float:
    """`(below + 0.5 x equal) / n`, as a percentage.

    The half-credit for ties is the whole point. With `at-or-below`, a supplier tied with ten others
    at the cohort median reports above the 50th percentile — it inherits credit for beating suppliers
    it merely matched. Midrank is the standard correction and it is exact at the median by
    construction.
    """
    n = len(values)
    if n == 0:
        return 0.0
    below = sum(1 for v in values if v < subject)
    equal = sum(1 for v in values if v == subject)
    return 100.0 * (below + 0.5 * equal) / n


def rank_of(values: list[int], subject: int) -> tuple[int, int]:
    """`(rank, tied_with)` where rank 1 is the HIGHEST posture in the cohort.

    Competition ranking: everyone strictly better than the subject ranks ahead of it, and ties share
    the rank. So three suppliers tied at the top are all rank 1 and the next is rank 4 — which is the
    convention every reader already knows from league tables.
    """
    better = sum(1 for v in values if v > subject)
    tied = sum(1 for v in values if v == subject)
    return better + 1, tied


def quartile_of(percentile: float) -> int:
    """1 = lowest posture. Derived from the midrank percentile so the two can never disagree."""
    if percentile <= 25:
        return 1
    if percentile <= 50:
        return 2
    if percentile <= 75:
        return 3
    return 4


def is_outlier_low(values: list[int], subject: int) -> bool:
    """Below the cohort's lower fence, `p25 - 1.5 x IQR`.

    Needs at least four peers to have quartiles worth computing at all; below that the fence is a
    restatement of the minimum. Being far behind one's own industry is a finding even where the
    absolute score reads as moderate, which is why this is computed separately from the quartile.
    """
    if len(values) < 4:
        return False
    ordered = sorted(values)
    p25 = _percentile_value(ordered, 25) or 0
    p75 = _percentile_value(ordered, 75) or 0
    return subject < (p25 - 1.5 * (p75 - p25))


def place(
    subject: int | None,
    values: list[int],
    cfg: BenchmarkingConfig | None = None,
    *,
    is_synthetic: bool = False,
    min_n: int | None = None,
) -> Placement:
    """The one implementation of the thresholds. Every placement in the system comes from here.

    `min_n` overrides `min_quartile_n` for per-domain placements, which carry their own floor —
    a domain's population is not the cohort's population.
    """
    cfg = cfg or get_benchmarking_config()
    n = len(values)
    quartile_floor = min_n if min_n is not None else cfg.min_quartile_n()
    percentile_floor = cfg.min_percentile_n()

    # HARD GATE, first, before anything is computed. Decision 3: a synthetic cohort yields no ordinal
    # placement at any n. Thirty invented numbers still make a screenshottable fake percentile, and
    # the "not real peers" label does not travel with the screenshot.
    if is_synthetic:
        return Placement(
            subject=subject, n=n, sufficient=False, bucket="insufficient_peers",
            reason="Reference points only, not assessed suppliers — no percentile or quartile is "
                   "published from synthetic peers at any sample size.",
        )

    if subject is None:
        return Placement(
            subject=None, n=n, sufficient=False, bucket="insufficient_peers",
            reason="No published score to place (blocked, gated, or insufficient evidence).",
        )

    if n < quartile_floor:
        return Placement(
            subject=subject, n=n, sufficient=False, bucket="insufficient_peers",
            reason=f"Insufficient peer data: {n} comparable supplier(s) assessed, minimum "
                   f"{quartile_floor}.",
        )

    ordered = sorted(values)
    pct = midrank_percentile(ordered, subject)
    quartile = quartile_of(pct)
    rank, tied = rank_of(ordered, subject)
    median = _percentile_value(ordered, 50)
    delta = (subject - median) if median is not None else None
    direction: Direction | None = None
    if delta is not None:
        direction = "at" if delta == 0 else ("above" if delta > 0 else "below")

    # The percentile is published ONLY above its own floor, and always with the step the sample can
    # express. `ceil`, not `round`: at n=8 the achievable steps are 12.5 apart and `round` would
    # report 12, claiming a finer resolution than the data supports. Rounding the step UP can never
    # overstate precision.
    percentile: int | None = None
    resolution: int | None = None
    if n >= percentile_floor:
        resolution = max(1, math.ceil(100 / n))
        percentile = max(0, min(100, int(round(pct / resolution) * resolution)))

    return Placement(
        subject=subject, n=n, sufficient=True,
        quartile=quartile,
        quartile_label=_QUARTILE_LABELS[quartile],
        percentile=percentile,
        percentile_resolution=resolution,
        rank_of_n=rank,
        tied_with=max(0, tied),
        median=median,
        direction=direction,
        delta_from_median=delta,
        outlier_low=is_outlier_low(ordered, subject),
        bucket=_QUARTILE_BUCKETS[quartile],
        reason=None if n >= percentile_floor else (
            f"Quartile only: {n} peers is below the {percentile_floor} needed for a percentile."
        ),
    )


# --------------------------------------------------------------------------- reliability


def reliability_of(
    snapshot: CohortSnapshot,
    assignment: CohortAssignment,
    cfg: BenchmarkingConfig | None = None,
    now: datetime | None = None,
) -> ReliabilityFactors:
    """How much weight the COMPARISON deserves — four factors, each published individually.

    Deliberately NOT combined with the supplier's own confidence. That is a different quantity about
    a different thing, and multiplying them would produce one number that answers neither "how well
    do we see this supplier" nor "how good is this peer group".
    """
    cfg = cfg or get_benchmarking_config()
    now = now or utcnow()
    n = snapshot.distribution.n
    notes: list[str] = []

    saturation = cfg.sample_saturation_n()
    sample = min(1.0, n / saturation) if saturation else 0.0
    if n < cfg.min_percentile_n():
        notes.append(f"n={n}: quartile resolution only (a percentile needs {cfg.min_percentile_n()}).")

    exactness = cfg.rung_exactness(tuple(snapshot.rung))
    if assignment.widened:
        notes.append(
            f"Cohort widened to {snapshot.rung_label} — the exact peer group was too thin, so read "
            f"the comparison as indicative rather than precise."
        )

    peer_evidence = snapshot.peer_confidence_median
    if peer_evidence is None:
        peer_evidence = 0.8
    elif peer_evidence < 0.7:
        notes.append(
            f"Peers are themselves thinly evidenced (median coverage {round(peer_evidence * 100)}%), "
            f"so the median reflects what is publicly visible about them rather than their full "
            f"posture."
        )

    age_days = max(0, (now - snapshot.last_refreshed).days)
    freshness = max(0.5, 1.0 - (age_days / 730))
    if snapshot.stale_peers:
        notes.append(
            f"{snapshot.stale_peers} peer score(s) are older than {cfg.stale_peer_days()} days. "
            f"Disclosed and retained — dropping them would bias the cohort toward whoever we happen "
            f"to have rescored recently."
        )

    value = round(max(0.0, min(1.0, sample * exactness * peer_evidence * freshness)), 3)
    band = "High" if value >= 0.75 else "Medium" if value >= 0.5 else "Low"
    if band == "Low":
        notes.insert(0, (
            f"Low comparison reliability ({value}): the peer group itself is weakly supported. Read "
            f"the absolute score first."
        ))
    if band != "High" and not notes:
        # A band with no explanation is the opaque number this whole object exists to replace. When
        # no single factor tripped its own threshold, name the weakest one so the reader still knows
        # which lever moves it.
        weakest = min(
            (("sample size", sample), ("cohort exactness", exactness),
             ("peer evidence", peer_evidence), ("peer freshness", freshness)),
            key=lambda pair: pair[1],
        )
        notes.append(
            f"Comparison reliability {value} ({band}); no single factor is alarming, and "
            f"{weakest[0]} ({round(weakest[1], 2)}) is the one holding it down."
        )
    return ReliabilityFactors(
        sample_adequacy=round(sample, 3), rung_exactness=round(exactness, 3),
        peer_evidence=round(peer_evidence, 3), freshness=round(freshness, 3),
        value=value, band=band, notes=notes,
    )


# --------------------------------------------------------------------------- delta


def build_delta(
    current: Placement,
    previous: BenchmarkPlacement | None,
    snapshot: CohortSnapshot,
) -> PlacementDelta | None:
    """Attribute the movement: did the supplier move, or did the cohort move under them?

    This is the output that justifies storing snapshots at all. A supplier that gained three points
    while its cohort gained seven has lost ground without doing anything wrong, and every other view
    in the system reports that as a decline on their part.
    """
    if previous is None:
        return None

    posture_change = None
    if current.subject is not None and previous.overall.subject is not None:
        posture_change = current.subject - previous.overall.subject

    median_change = None
    if snapshot.distribution.median is not None and previous.snapshot.distribution.median is not None:
        median_change = snapshot.distribution.median - previous.snapshot.distribution.median

    quartile_change = None
    if current.quartile is not None and previous.overall.quartile is not None:
        quartile_change = current.quartile - previous.overall.quartile

    return PlacementDelta(
        previous_snapshot_id=previous.snapshot.snapshot_id,
        posture_change=posture_change,
        cohort_median_change=median_change,
        quartile_change=quartile_change,
        net_effect=_attribute(posture_change, median_change, quartile_change),
    )


def _attribute(posture: int | None, median: int | None, quartile: int | None) -> str | None:
    """The sentence. Written here rather than in the template table because it is a derivation, not
    a phrasing choice — the attribution logic has to live with the arithmetic it describes."""
    if posture is None or median is None:
        return None
    moved = f"{'no quartile change' if not quartile else f'{quartile:+d} quartile'}"
    if quartile and quartile < 0 and posture >= 0:
        return (
            f"{moved}: the supplier's score moved {posture:+d} while the cohort median moved "
            f"{median:+d} — the peer group improved faster, so the placement fell without the "
            f"supplier declining."
        )
    if quartile and quartile > 0 and posture <= 0:
        return (
            f"{moved}: the supplier's score moved {posture:+d} while the cohort median moved "
            f"{median:+d} — the placement rose because the peer group fell back, not because the "
            f"supplier improved."
        )
    return (
        f"{moved}: supplier {posture:+d}, cohort median {median:+d}."
    )


# --------------------------------------------------------------------------- the orchestrator


def build_placement(
    firmographics: SupplierFirmographics,
    posture: int | None,
    assignment: CohortAssignment,
    snapshot: CohortSnapshot,
    *,
    domains: dict[str, int] | None = None,
    supplier_confidence: float | None = None,
    previous: BenchmarkPlacement | None = None,
    disputes: list[CohortDispute] | None = None,
    cfg: BenchmarkingConfig | None = None,
    now: datetime | None = None,
) -> BenchmarkPlacement:
    """The published artefact. Reads inputs; writes nothing back.

    `posture` and `domains` are passed straight through onto the output and are never recomputed,
    rescaled or adjusted. That is asserted by test: the module contextualises scores and does not
    modify them.
    """
    cfg = cfg or get_benchmarking_config()
    now = now or utcnow()
    domains = domains or {}

    overall = place(
        posture,
        snapshot.member_postures,
        cfg,
        is_synthetic=snapshot.is_synthetic,
    )

    domain_placements = _place_domains(domains, snapshot, cfg)

    reliability = reliability_of(snapshot, assignment, cfg, now)

    flagged = (
        supplier_confidence is not None
        and supplier_confidence < cfg.flag_supplier_confidence_below()
    )

    open_disputes = [
        d.dispute_id for d in (disputes or []) if d.state in OPEN_DISPUTE_STATES
    ]

    caveats = _caveats(assignment, snapshot, overall, flagged, supplier_confidence, cfg)

    action = None
    if firmographics.data_access_scope:
        action = cfg.action_for(overall.bucket, firmographics.data_access_scope)

    placement = BenchmarkPlacement(
        supplier_ref=firmographics.supplier_ref,
        supplier_name=firmographics.supplier_name,
        assessed_at=now,
        assignment=assignment,
        snapshot=snapshot.public(),
        overall=overall,
        domains=domain_placements,
        supplier_confidence=supplier_confidence,
        confidence_flagged=flagged,
        reliability=reliability,
        data_access_scope=firmographics.data_access_scope,
        delta=build_delta(overall, previous, snapshot),
        disputed=bool(open_disputes) and cfg.notate_open_disputes(),
        open_dispute_ids=sorted(set(open_disputes)),
        action=action,
        action_disclaimer=cfg.action_disclaimer(),
        caveats=caveats,
        config_version=cfg.version(),
        narrative_version=cfg.narrative_version(),
    )

    placement.security_narrative = render_security(placement, cfg)
    placement.procurement_narrative = render_procurement(placement, cfg)
    return placement


def _place_domains(
    subject_domains: dict[str, int],
    snapshot: CohortSnapshot,
    cfg: BenchmarkingConfig,
) -> list[DomainPlacement]:
    """One placement per domain, each against ITS OWN population and floor.

    A cohort of 40 may hold only 12 suppliers with an `email_auth` score. So a card legitimately
    shows an overall percentile beside a domain quartile beside a domain refusal — which reads as an
    inconsistency unless every row carries its own n. It does.
    """
    stats = {s.domain: s for s in snapshot.domains}
    out: list[DomainPlacement] = []

    for domain in sorted(set(subject_domains) | set(stats)):
        subject = subject_domains.get(domain)
        stat = stats.get(domain)
        values = snapshot.domain_values.get(domain, [])
        p = place(
            subject, values, cfg,
            is_synthetic=snapshot.is_synthetic,
            min_n=cfg.min_domain_n(),
        )
        verdict = stat.discrimination if stat else "untested"
        out.append(DomainPlacement(
            domain=domain,
            label=domain_label(domain),
            placement=p,
            discrimination=verdict,
            # A non-discriminating domain is DISCLOSED in its own section and kept OUT of the peer-gap
            # list: telling a supplier they are behind their peers on a control every peer also fails
            # would be false, and telling them they lead on one every peer also passes is noise.
            suppressed=verdict == "non_discriminating",
        ))

    # Worst first, then by size of the gap: what a reader needs is the domains they are behind on.
    def sort_key(dp: DomainPlacement) -> tuple[int, int, str]:
        placed = 0 if dp.placement.sufficient and not dp.suppressed else 1
        gap = dp.placement.delta_from_median if dp.placement.delta_from_median is not None else 0
        return placed, gap, dp.domain

    return sorted(out, key=sort_key)


def _caveats(
    assignment: CohortAssignment,
    snapshot: CohortSnapshot,
    overall: Placement,
    flagged: bool,
    supplier_confidence: float | None,
    cfg: BenchmarkingConfig,
) -> list[str]:
    """Everything a reader needs in order to read the placement correctly. UI requirements.

    Ordered by how badly a reader is misled without them, which is why the synthetic caveat is
    inserted last and therefore lands first: every other caveat qualifies a real comparison, and that
    one says there is no real comparison to qualify.
    """
    out: list[str] = []

    if snapshot.non_discriminating:
        keys = ", ".join(v.key for v in snapshot.non_discriminating[:5])
        more = "" if len(snapshot.non_discriminating) <= 5 else f" (+{len(snapshot.non_discriminating) - 5} more)"
        out.append(
            f"{len(snapshot.non_discriminating)} signal(s) do not vary across this cohort and are "
            f"therefore excluded from peer-gap reporting: {keys}{more}. They are constants here, not "
            f"comparisons."
        )

    if snapshot.stale_peers:
        out.append(f"{snapshot.stale_peers} peer score(s) exceed the {cfg.stale_peer_days()}-day "
                   f"freshness window. Disclosed and retained, not dropped.")

    if overall.outlier_low:
        out.insert(0, (
            "This supplier sits below the normal range for its peer group. Being far behind one's "
            "own industry is a finding in itself, even where the absolute score looks moderate."
        ))

    if flagged:
        out.insert(0, (
            f"Benchmark placement may be unreliable: this supplier's confidence is "
            f"{supplier_confidence} — below the {cfg.flag_supplier_confidence_below()} floor — so "
            f"there is limited observable data behind the score being placed. The placement is "
            f"published and labelled, not suppressed."
        ))

    if assignment.widened:
        out.insert(0, (
            f"Compared against a wider population than the exact peer group: {snapshot.rung_label}. "
            f"{assignment.rationale_text()}"
        ))

    out.append(cfg.self_selection_caveat())

    if snapshot.is_synthetic:
        out.insert(0, cfg.synthetic_caveat() or (
            "NOT REAL PEERS. These are fixed reference points, not assessed suppliers."
        ))

    return [c for c in out if c]
