"""The cohort snapshot — the frozen population a placement stays reproducible against.

WHY A SNAPSHOT AND NOT A LIVE QUERY. A percentile computed at read time is computed against whoever
happens to be in the cohort right now. That is fine for "how do I read today's number" and useless
for anything else: a placement recorded last quarter, re-derived today, compares an old posture
against a new population and silently attributes the difference to the supplier. So the population is
frozen at build time, hashed, and every placement points at the snapshot it was computed from.

THE FEATURE THIS BUYS, which nobody asked for and everybody wants: *"why did my quartile change?"*
becomes mechanically answerable. Diff two snapshots and the movement decomposes into "your posture
moved" and "the cohort moved" — see `placement.build_delta`. No other output in the system can
separate those, and every risk manager asks.

APPEND-ONLY. A rebuild mints a NEW snapshot; nothing is ever mutated. Cohorts are rebuildable from
raw data by definition, which is exactly why an upheld dispute cannot be a database edit — it changes
an input, and the rebuild follows.

⚠️ MEMBER REFS. A snapshot carries them so a dispute reviewer can answer "who was I compared
against?". They are never published: `CohortSnapshot.public()` is the only outbound path, and it
cannot carry them. Decision 4.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from ..canonical import canonical_json, sha256
from ..models import utcnow
from .config import BenchmarkingConfig, get_benchmarking_config
from .discrimination import discrimination_report
from .models import (
    CohortAssignment,
    CohortSnapshot,
    DiscriminationVerdict,
    Distribution,
    DomainStats,
    PeerRecord,
)


def _percentile_value(sorted_values: list[int], pct: float) -> int | None:
    """Nearest-rank percentile. NO INTERPOLATION, deliberately.

    These are small samples. An interpolated median between two real suppliers is a company that does
    not exist, and quoting it as the cohort's centre asserts a member of the population that was never
    assessed. The same definition is used in `discrimination.py` and `placement.py` so a median can
    never differ between the snapshot and the card computed from it.
    """
    if not sorted_values:
        return None
    k = max(0, min(len(sorted_values) - 1, int(round((pct / 100) * (len(sorted_values) - 1)))))
    return sorted_values[k]


def distribution_of(values: list[int]) -> Distribution:
    ordered = sorted(v for v in values if v is not None)
    if not ordered:
        return Distribution(n=0)
    return Distribution(
        n=len(ordered),
        median=_percentile_value(ordered, 50),
        p25=_percentile_value(ordered, 25),
        p75=_percentile_value(ordered, 75),
        minimum=ordered[0],
        maximum=ordered[-1],
    )


def _median_float(values: list[float]) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    k = max(0, min(len(ordered) - 1, int(round(0.5 * (len(ordered) - 1)))))
    return round(ordered[k], 3)


def _member_hash(refs: list[str]) -> str:
    """Identifies the exact population without disclosing it.

    Published in the tenant-safe projection on purpose: it lets an auditor confirm two placements were
    computed against the identical population while learning nothing about who that population was,
    which is the whole of what transparency requires here.
    """
    return sha256(canonical_json({"members": sorted(refs)}))


def build_snapshot(
    assignment: CohortAssignment,
    peers: list[PeerRecord],
    cfg: BenchmarkingConfig | None = None,
    *,
    is_synthetic: bool = False,
    now: datetime | None = None,
    snapshot_id: str | None = None,
) -> CohortSnapshot:
    """Freeze this cohort: distribution, per-domain distributions, composition, discrimination.

    `is_synthetic` is a HARD GATE that travels on the snapshot rather than being decided at render
    time. Decision 3: when true, no percentile and no quartile is published at ANY n. Thirty invented
    numbers still produce a screenshottable fake percentile, and the label under it does not travel
    with the screenshot.
    """
    cfg = cfg or get_benchmarking_config()
    now = now or utcnow()

    overall = distribution_of([p.posture for p in peers])
    verdicts = discrimination_report(peers, cfg)
    by_key = {v.key: v.verdict for v in verdicts}

    # Per-domain distributions, each over ONLY the peers that actually covered that domain. A peer
    # never assessed for a domain is not a peer that scored zero, so it leaves the denominator rather
    # than dragging the median down with a collection failure.
    domain_names = sorted({d for p in peers for d in p.domains})
    domain_values = {
        name: sorted(p.domains[name] for p in peers if p.domains.get(name) is not None)
        for name in domain_names
    }
    domains = [
        DomainStats(
            domain=name,
            distribution=distribution_of(domain_values[name]),
            discrimination=by_key.get(name, "untested"),  # type: ignore[arg-type]
        )
        for name in domain_names
    ]

    # COMPOSITION, not a count. "n=23, of which 3 attested" is a different claim from "n=23", and
    # cohort quality is not inferable from cohort size — twelve assessed suppliers can be a firmer
    # basis than forty OSINT-only signals.
    sources: dict[str, int] = {}
    for peer in peers:
        sources[peer.source_class] = sources.get(peer.source_class, 0) + 1

    stale_window = cfg.stale_peer_days()
    stale = sum(
        1 for p in peers
        if p.computed_at and (now - p.computed_at).days > stale_window
    )

    refs = [p.supplier_ref for p in peers]
    return CohortSnapshot(
        snapshot_id=snapshot_id or str(uuid.uuid4()),
        cohort_key=assignment.cohort_key,
        rung=assignment.rung,
        rung_label=assignment.rung_label,
        dimensions=assignment.dimensions,
        distribution=overall,
        domains=domains,
        data_sources=sources,
        # DISCLOSED, never filtered on. Filtering thin peers out of the cohort would bias it toward
        # the observable — i.e. toward large companies — which is the observability bias this platform
        # exists to remove. So the number is published and the members stay.
        peer_confidence_median=_median_float([p.confidence for p in peers if p.confidence is not None]),
        stale_peers=stale,
        is_synthetic=is_synthetic,
        non_discriminating=[v for v in verdicts if v.verdict == "non_discriminating"],
        member_refs=refs,
        # Sorted and ref-stripped. A rank cannot be rebuilt from five order statistics, so these are
        # what makes a stored placement genuinely reproducible rather than approximately so — and
        # sorting detaches each value from the peer it came from.
        member_postures=sorted(p.posture for p in peers),
        domain_values=domain_values,
        member_hash=_member_hash(refs),
        last_refreshed=now,
    )


def all_verdicts(peers: list[PeerRecord], cfg: BenchmarkingConfig | None = None
                 ) -> list[DiscriminationVerdict]:
    """Every verdict, for the model-team endpoint.

    `build_snapshot` stores only the FLAGGED verdicts, because that is what a card needs. The model
    team needs the whole table — "we tested it and it was fine" has to be distinguishable from "we
    never tested it", and only the full list carries that difference.
    """
    return discrimination_report(peers, cfg or get_benchmarking_config())
