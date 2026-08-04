"""The seam between the store and the statistics — and the one entry point the API calls.

WHY THIS MODULE EXISTS SEPARATELY. `cohorts.py`, `snapshot.py` and `placement.py` are deliberately
free of persistence concerns: they take a `PeerLookup` callable and plain records, which is what makes
every ladder rung and every threshold testable without a database. That purity has to be paid for
somewhere, and this is where — one module that knows about both a `Store` and a `PeerRecord`, and
nothing else in the package does.

WHAT `benchmark_supplier` GUARANTEES, in order:

  1. The subject is EXCLUDED from its own cohort. Not a nicety: at the threshold boundary an "n=30"
     that counts the subject is 29 peers, so the percentile rule would be wrong by one on precisely
     the case it exists to govern.
  2. The snapshot is built from the SAME peer list the assignment resolved. Re-querying between
     assignment and snapshot would let the population shift mid-request, and the placement would then
     cite an `n` it was not computed against.
  3. Nothing is written back to any score. The supplier's posture, confidence and domain scores are
     read, carried onto the output, and returned unchanged.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from ..models import utcnow
from .cohorts import PeerLookup, assign_cohort, derive_size_band
from .config import BenchmarkingConfig, get_benchmarking_config
from .models import (
    BenchmarkPlacement,
    CohortDispute,
    DisputeState,
    DisputeTarget,
    PeerRecord,
    SupplierAttributes,
    SupplierFirmographics,
)
from .expectation_gap import ExpectationGapReport, expectation_gap
from .placement import build_placement
from .snapshot import build_snapshot


def store_peer_lookup(
    store: Any,
    *,
    exclude_ref: str,
    cfg: BenchmarkingConfig | None = None,
) -> PeerLookup:
    """Adapt a `Store` into the `PeerLookup` the ladder calls.

    `exclude_ref` is REQUIRED rather than optional — see the module docstring. Making it keyword-only
    and mandatory means no caller can forget it, which is the only defence against a bug that produces
    a plausible-looking flattering number rather than an error.

    `sector_group` is resolved from config here rather than in SQL, so the rollup can be re-cut in
    YAML without a migration.
    """
    cfg = cfg or get_benchmarking_config()

    def lookup(dims: dict[str, str]) -> list[PeerRecord]:
        query: dict[str, Any] = {}
        for key, value in dims.items():
            if key == "sector_group":
                members = cfg.sector_groups().get(value, ())
                if not members:
                    return []
                query["sector_group"] = list(members)
            else:
                query[key] = value

        rows = store.bm_cohort_peers(query, exclude_ref=exclude_ref)
        return [_row_to_peer(row) for row in rows]

    return lookup


def _row_to_peer(row: dict[str, Any]) -> PeerRecord:
    """One store row -> one comparable supplier.

    A malformed stored score costs that peer its per-domain detail and nothing more: it still counts
    toward the overall distribution. Dropping the whole peer would silently shrink `n`, and `n` is the
    number every threshold in this system turns on.
    """
    domains: dict[str, int] = {}
    raw = row.get("score_json")
    if raw:
        try:
            from ..models import Score

            domains = {
                c.category: c.posture
                for c in Score.model_validate_json(raw).categories
                if c.posture is not None
            }
        except (ValueError, TypeError):
            domains = {}

    return PeerRecord(
        supplier_ref=row["vendor_ref"],
        posture=int(row["posture"]),
        confidence=float(row.get("overall_confidence") or 0.0),
        domains=domains,
        computed_at=_parse_dt(row.get("computed_at")),
        # Every peer in this deployment is externally observed. The field exists because the
        # composition is what a reader needs beside `n`, and it becomes informative the moment a
        # questionnaire or an attestation path lands — at which point this is the one line to change.
        source_class=row.get("source_class") or "osint_only",
    )


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def benchmark_supplier(
    store: Any,
    firmographics: SupplierFirmographics,
    posture: int | None,
    *,
    domains: dict[str, int] | None = None,
    supplier_confidence: float | None = None,
    persist: bool = True,
    cfg: BenchmarkingConfig | None = None,
    now: datetime | None = None,
) -> BenchmarkPlacement:
    """Assign, snapshot, place — the whole flow, once, against one frozen population.

    `persist=False` is for previews and for the dispute-review path: a reviewer asking "what cohort
    would this supplier be in if their sector were corrected?" must be able to see the answer without
    writing a placement that then looks like a published one.
    """
    cfg = cfg or get_benchmarking_config()
    now = now or utcnow()

    lookup = store_peer_lookup(store, exclude_ref=firmographics.supplier_ref, cfg=cfg)
    assignment = assign_cohort(firmographics, lookup, cfg)

    # Resolve the peer list ONCE, from the rung the assignment actually landed on. Re-querying here
    # would let the population change between the two calls, and the placement would then publish an
    # `n` it was not computed against.
    peers = lookup(assignment.dimensions) if assignment.dimensions else []
    snapshot = build_snapshot(assignment, peers, cfg, now=now)

    previous = store.latest_placement(firmographics.supplier_ref) if persist else None
    disputes = store.cohort_disputes_for_supplier(firmographics.supplier_ref)

    placement = build_placement(
        firmographics, posture, assignment, snapshot,
        domains=domains, supplier_confidence=supplier_confidence,
        previous=previous, disputes=disputes, cfg=cfg, now=now,
    )

    if persist:
        # Snapshot first: a placement row referencing a snapshot id that was never stored would break
        # the reproducibility guarantee the whole design rests on.
        store.put_cohort_snapshot(snapshot)
        store.put_placement(placement)

    return placement


def expectation_gap_for(
    store: Any,
    firmographics: SupplierFirmographics,
    posture: int | None,
    *,
    findings: list[Any] | None = None,
    penalty_divisor: float = 1.0,
    cfg: BenchmarkingConfig | None = None,
) -> ExpectationGapReport:
    """E10a. `Posture − E[Posture | cohort]`, with the observations that account for it.

    THE DIVISOR IS PASSED IN, NOT READ. This package must not import `scoring_config` — the
    one-sentence contract at the top of `__init__.py` is that benchmarking reads scores and has no
    path into how they are computed, and an import is the first step toward a benchmark that
    "adjusts" one. So the caller converts category penalties into posture points and hands over
    the result; this module knows the arithmetic of comparison and nothing about scoring.

    The peer list is resolved through the SAME ladder the placement uses, so a gap and a placement
    published in the same breath cannot cite different populations.
    """
    cfg = cfg or get_benchmarking_config()
    lookup = store_peer_lookup(store, exclude_ref=firmographics.supplier_ref, cfg=cfg)
    assignment = assign_cohort(firmographics, lookup, cfg)
    peers = lookup(assignment.dimensions) if assignment.dimensions else []
    # Peer BANDS, loaded once for the rung that won. Without them there is no prevalence rate, and
    # without a prevalence rate a "driver" is just this vendor's biggest penalty relabelled as a
    # comparison — which is the thing this phase exists to stop being.
    bands = store.bm_peer_signals([p.supplier_ref for p in peers])
    peers = [p.model_copy(update={"signals": bands.get(p.supplier_ref, {})}) for p in peers]
    # Built rather than inferred, so the synthetic HARD GATE is read from the same object the
    # placement reads it from. Deciding "are these real peers?" twice is how the two answers
    # eventually differ, and the one that matters is whichever the screenshot came from.
    snapshot = build_snapshot(assignment, peers, cfg)

    subject_signals: dict[str, str] = {}
    charged: dict[str, float] = {}
    for f in findings or []:
        band = getattr(f, "band_key", None)
        if not band:
            continue
        subject_signals[f.signal] = band
        # `effective_penalty` is the POST-modifier, post-discount figure — the one that actually
        # reconciles to the published category penalty. Using the base `penalty` here would
        # attribute points to a signal that were never charged, and the gap would not survive
        # anyone checking it against the receipt.
        cost = float(getattr(f, "effective_penalty", 0.0) or 0.0)
        if cost > 0 and penalty_divisor > 0:
            charged[f.signal] = charged.get(f.signal, 0.0) + cost / penalty_divisor

    return expectation_gap(
        firmographics.supplier_ref, posture, peers,
        subject_signals=subject_signals, charged_points=charged,
        is_synthetic=snapshot.is_synthetic, cfg=cfg,
    )


# --------------------------------------------------------------------------- disputes


def raise_cohort_dispute(
    store: Any,
    supplier_ref: str,
    target: DisputeTarget,
    evidence: str,
    *,
    asserted_value: str | None = None,
    observed_value: str | None = None,
    actor: str | None = None,
    cohort_key_at: str | None = None,
    snapshot_id_at: str | None = None,
) -> CohortDispute:
    """Open a dispute against a cohort INPUT.

    The target is validated by the `DisputeTarget` literal, which is the enforcement point for "the
    cell is not disputable": there is no member of that type naming a cohort, a snapshot or a
    quartile, so a request to dispute one cannot be represented let alone stored.
    """
    dispute = CohortDispute(
        id=str(uuid.uuid4()),
        dispute_id=str(uuid.uuid4()),
        supplier_ref=supplier_ref,
        state="submitted",
        target=target,
        asserted_value=asserted_value,
        observed_value=observed_value,
        cohort_key_at=cohort_key_at,
        snapshot_id_at=snapshot_id_at,
        evidence=evidence,
        actor=actor,
    )
    store.put_cohort_dispute(dispute)
    return dispute


def advance_cohort_dispute(
    store: Any,
    dispute_id: str,
    state: DisputeState,
    *,
    actor: str | None = None,
    note: str | None = None,
) -> CohortDispute:
    """Append a state transition. Never an edit.

    An UPHELD dispute deliberately does NOT rewrite anything here. The resolution is a change to the
    supplier's attribute; a rebuild then mints a new snapshot and a new placement follows. Historical
    placements keep pointing at the population they were computed against — which is the entire reason
    the snapshot is stored, and the reason the config forbids manual overrides in the DB.
    """
    events = store.cohort_dispute_events(dispute_id)
    if not events:
        raise ValueError(f"no such cohort dispute: {dispute_id}")
    current = events[-1]

    event = CohortDispute(
        id=str(uuid.uuid4()),
        dispute_id=dispute_id,
        supplier_ref=current.supplier_ref,
        state=state,
        target=current.target,
        asserted_value=current.asserted_value,
        observed_value=current.observed_value,
        cohort_key_at=current.cohort_key_at,
        snapshot_id_at=current.snapshot_id_at,
        evidence=current.evidence,
        actor=actor,
        note=note,
    )
    store.put_cohort_dispute(event)
    return event


def record_attributes(
    store: Any,
    firmographics: SupplierFirmographics,
    *,
    source: str = "derived",
    cfg: BenchmarkingConfig | None = None,
) -> SupplierAttributes:
    """Derive the size band and append the supplier's cohort inputs.

    Called whenever a supplier's firmographics change — after a score run, after a client supplies a
    headcount, after a dispute is upheld. The derived band is stored ALONGSIDE its basis so the stored
    row is self-explaining: a reviewer never has to re-run the code to find out why a supplier is
    `large`.
    """
    cfg = cfg or get_benchmarking_config()
    derivation = derive_size_band(firmographics, cfg)
    attrs = SupplierAttributes(
        supplier_ref=firmographics.supplier_ref,
        sector=firmographics.sector,
        size_band=derivation.band,
        delivery_model=firmographics.delivery_model,
        data_access_scope=firmographics.data_access_scope,
        employees=firmographics.employees,
        revenue=firmographics.revenue,
        revenue_currency=firmographics.revenue_currency,
        size_band_basis=derivation.basis(),
        source=source,  # type: ignore[arg-type]
    )
    store.put_supplier_attributes(attrs)
    return attrs


def firmographics_of(store: Any, supplier_ref: str,
                     name: str | None = None) -> SupplierFirmographics | None:
    """Rebuild the firmographics from the latest stored attribute row.

    Returns None rather than an empty object when nothing is stored: a supplier with no recorded
    attributes has no cohort, and manufacturing a default sector here is how the superseded module
    ended up filing every unclassified vendor under `technology`.
    """
    row = store.latest_supplier_attributes(supplier_ref)
    if not row:
        return None
    return SupplierFirmographics(
        supplier_ref=supplier_ref,
        supplier_name=name,
        sector=row.get("sector"),
        delivery_model=row.get("delivery_model"),
        employees=row.get("employees"),
        revenue=row.get("revenue"),
        revenue_currency=row.get("revenue_currency"),
        data_access_scope=row.get("data_access_scope"),
    )


def preview_size_band(firmographics: SupplierFirmographics,
                      cfg: BenchmarkingConfig | None = None) -> dict[str, Any]:
    """The size-band derivation, exposed on its own for the dispute path.

    A supplier contesting their band needs to see the working — both inputs, both intermediate bands,
    the rule version, and which input decided it. Returning that without computing a placement means
    the question "why am I `large`?" is answerable without publishing anything.
    """
    derivation = derive_size_band(firmographics, cfg)
    return {"derivation": derivation.model_dump(), "basis": derivation.basis()}
