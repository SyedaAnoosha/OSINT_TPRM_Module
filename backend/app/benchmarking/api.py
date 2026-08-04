"""REST surface for the peer-benchmarking layer. Flat JSON, plus one CSV export.

MOUNTED UNDER `/api/v2/` because the v1 `/api/vendors/{ref}/benchmark` endpoint keeps serving the
superseded shape through the deprecation release. Two versions side by side beats one endpoint whose
response shape changes under a client.

DECISION 4 IS ENFORCED STRUCTURALLY, NOT BY REVIEW. Every route here returns
`CohortSnapshot.public()` or an object built from it. `PublicCohortSnapshot` has no field for member
refs, so a route cannot leak them by omission — the type system refuses before a reviewer has to
notice. The one route that reads the internal form (`/cohort-disputes/{id}/cohort`) is documented as
internal and returns the member count rather than the members.

NO BI INTEGRATION, BY DECISION. Flat REST and CSV. A supplier-benchmarking dataset piped into a BI
tool grows dashboards that outlive the caveats attached to the numbers, and the caveats are the
product.
"""

from __future__ import annotations

import csv
import io
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..scoring_config import get_scoring_config
from ..storage import Store, get_store
from .config import get_benchmarking_config
from .models import (
    BenchmarkPlacement,
    CohortDispute,
    DataAccessScope,
    DeliveryModel,
    DisputeState,
    DisputeTarget,
    SupplierFirmographics,
)
from .service import (
    advance_cohort_dispute,
    benchmark_supplier,
    expectation_gap_for,
    firmographics_of,
    preview_size_band,
    raise_cohort_dispute,
    record_attributes,
)
from .snapshot import all_verdicts

router = APIRouter(prefix="/api/v2", tags=["benchmarking"])


def _store_dep() -> Any:
    store = get_store()
    try:
        yield store
    finally:
        store.close()


StoreDep = Annotated[Store, Depends(_store_dep)]


def _placement_for(store: Store, ref: str, *, persist: bool = False) -> BenchmarkPlacement:
    """Assemble a placement from stored state, or explain precisely what is missing.

    The three failure modes are distinguished rather than collapsed into one 404, because they need
    three different actions from the caller: record the attributes, score the supplier, or wait for
    the peer pool to fill.
    """
    firmographics = firmographics_of(store, ref)
    if firmographics is None:
        raise HTTPException(
            409,
            f"no cohort attributes recorded for {ref!r}. POST /api/v2/suppliers/{ref}/attributes "
            f"with at least a sector — a peer group needs an industry, and defaulting one would "
            f"file every unclassified supplier under the same sector.",
        )
    score = store.latest_score(ref)
    if score is None:
        raise HTTPException(409, f"no score for {ref!r} — assess the supplier first. This layer "
                                 f"contextualises scores; it does not compute them.")

    domains = {c.category: c.posture for c in score.categories if c.posture is not None}
    return benchmark_supplier(
        store, firmographics, score.posture,
        domains=domains, supplier_confidence=score.overall_confidence, persist=persist,
    )


# --------------------------------------------------------------------------- attributes


class AttributesRequest(BaseModel):
    """The cohort inputs. `data_access_scope` is accepted here and used ONLY for interpretation."""

    sector: str | None = Field(default=None, description="Normalised working sector")
    delivery_model: DeliveryModel | None = None
    employees: int | None = Field(default=None, ge=0)
    revenue: float | None = Field(default=None, ge=0)
    revenue_currency: str | None = None
    data_access_scope: DataAccessScope | None = Field(
        default=None,
        description="Buyer-side. Selects the contracting recommendation; NEVER affects which peers "
                    "this supplier is compared against.",
    )


@router.post("/suppliers/{ref}/attributes", status_code=201)
async def set_attributes(ref: str, req: AttributesRequest, store: StoreDep) -> dict[str, Any]:
    """Record the raw inputs the cohort is derived from. Appends; never edits.

    Returns the derived `size_band` together with its basis, so the caller sees immediately what the
    two size inputs produced and whether they disagreed.
    """
    firmographics = SupplierFirmographics(supplier_ref=ref, **req.model_dump())
    attrs = record_attributes(store, firmographics, source="client_supplied")
    return {
        "supplier_ref": ref,
        "attributes": attrs.model_dump(),
        "note": "Cohort inputs recorded. Posture is unchanged — this layer contextualises scores "
                "and has no write path to one.",
    }


@router.post("/suppliers/{ref}/size-band/preview")
async def preview_band(ref: str, req: AttributesRequest) -> dict[str, Any]:
    """Show the size-band derivation WITHOUT storing anything.

    Exists for the dispute path: a supplier asking "why am I `large`?" gets both inputs, both
    intermediate bands, the rule version and which input decided it — without a write.
    """
    return preview_size_band(SupplierFirmographics(supplier_ref=ref, **req.model_dump()))


# --------------------------------------------------------------------------- benchmark


@router.get("/suppliers/{ref}/cohort")
async def get_cohort(ref: str, store: StoreDep) -> dict[str, Any]:
    """The cohort assignment and the full rationale for it.

    Served separately from the placement because a supplier disputing their peer group needs the
    assignment without the comparison — and because every rung the ladder tried, with its `n`, is the
    answer to the only question anyone asks about a cohort.
    """
    placement = _placement_for(store, ref)
    a = placement.assignment
    return {
        "supplier_ref": ref,
        "cohort_key": a.cohort_key,
        "rung": list(a.rung),
        "rung_label": a.rung_label,
        "dimensions": a.dimensions,
        "n": a.n,
        "placeable": a.placeable,
        "widened": a.widened,
        "sector_group": a.sector_group,
        "size_band": a.size_band.model_dump(),
        "size_band_basis": a.size_band.basis(),
        "rationale": [r.model_dump() for r in a.rationale],
        "rationale_text": a.rationale_text(),
        "disputable": [
            "sector", "size_band", "delivery_model", "headcount", "revenue",
        ],
        "not_disputable": "The cohort, the snapshot and the resulting placement are deterministic "
                          "lookups over the inputs above and carry no independent judgement. "
                          "Dispute an input.",
    }


@router.get("/suppliers/{ref}/benchmark", response_model=BenchmarkPlacement)
async def get_benchmark(
    ref: str,
    store: StoreDep,
    persist: Annotated[bool, Query(description="Store this placement as a trend point")] = False,
) -> BenchmarkPlacement:
    """Where this supplier sits among its peers — both audience renderings, one dataset.

    `n` travels with every figure. A percentile appears only at n>=30, a quartile only at n>=8, and
    below that the response says "insufficient peer data" and gives the actual `n`. Those refusals
    are the feature: a median over four suppliers is noise wearing the costume of precision.
    """
    return _placement_for(store, ref, persist=persist)


@router.get("/suppliers/{ref}/expectation-gap")
async def get_expectation_gap(ref: str, store: StoreDep) -> dict[str, Any]:
    """E10a — `Posture − E[Posture | cohort]`, and the observations that account for it.

    THE SENTENCE THIS ROUTE EXISTS TO SERVE, which is the answer to the whole research question:

        "Posture 68. Cohort median (n=14): 87. This vendor sits 19 points below its peer group.
         The gap is driven by dmarc (absent) — 12 of 14 peers are not in this band."

    A buyer handed `-19` has a fact. A buyer handed `-19, driven by DMARC, which 12 of 14 peers
    publish` has a remediation, and one they can take to the vendor with a count of the vendor's own
    peer group attached rather than an opinion of ours.

    THE DRIVERS ARE RANKED, NOT A DECOMPOSITION, and the response says so in its caveats. Since
    E7a, what a finding costs depends on what else was charged alongside it, so per-signal
    attributions do not sum to the gap and no arrangement of them can be made to.
    """
    firmographics = firmographics_of(store, ref)
    if firmographics is None:
        raise HTTPException(
            409,
            f"no cohort attributes recorded for {ref!r}. POST /api/v2/suppliers/{ref}/attributes "
            f"with at least a sector — an expectation needs a peer group.",
        )
    score = store.latest_score(ref)
    if score is None:
        raise HTTPException(409, f"no score for {ref!r} — assess the supplier first.")

    # The divisor crosses the boundary as a NUMBER, not as an import. This package reads scores and
    # has no path into how they are computed; importing the scoring config here would be the first
    # step toward a benchmark that "adjusts" one.
    divisor = get_scoring_config().penalty_divisor()
    report = expectation_gap_for(
        store, firmographics, score.posture,
        findings=store.findings_for_vendor(ref), penalty_divisor=divisor,
    )
    return {
        "supplier_ref": ref,
        "published": report.published,
        "posture": report.posture,
        "expected_posture": report.expected_posture,
        "expectation_gap": report.gap,
        "estimator": report.estimator,
        "direction": report.direction,
        "n": report.n,
        "headline": report.headline(),
        "drivers": [
            {"signal": d.signal, "band": d.subject_band,
             "peers_observed": d.peers_observed, "peers_sharing_band": d.peers_sharing_band,
             "peer_failure_rate": round(d.peer_failure_rate, 3),
             "charged_posture_points": d.charged_posture_points,
             "attribution": d.attribution, "cited": d.cited()}
            for d in report.drivers
        ],
        "suppressed_signals": report.suppressed_signals,
        "reason": report.reason,
        "caveats": report.caveats,
    }


@router.get("/suppliers/{ref}/benchmark/history", response_model=list[BenchmarkPlacement])
async def get_benchmark_history(ref: str, store: StoreDep) -> list[BenchmarkPlacement]:
    """The placement trend — each point frozen against the cohort in force at the time.

    Which is what makes it a trend rather than an artefact: recomputing history against today's
    population would attribute the cohort's movement to the supplier.
    """
    return store.placement_history(ref)


@router.get("/suppliers/{ref}/benchmark.csv")
async def export_benchmark_csv(ref: str, store: StoreDep) -> StreamingResponse:
    """Flat CSV of the per-domain placements. Aggregates only — no member refs, by construction.

    Every row carries its own `n` and its own resolution. That is not padding: a spreadsheet that
    shows a percentile in one row and a quartile in the next, with no `n` column, reads as
    inconsistent data rather than as two populations of different sizes.
    """
    placement = _placement_for(store, ref)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow([
        "supplier_ref", "domain", "subject_score", "peer_n", "sufficient", "quartile",
        "quartile_label", "quartile_direction", "percentile", "percentile_resolution",
        "rank_of_n", "tied_with", "peer_median", "direction", "delta_from_median",
        "discriminating", "suppressed", "cohort_key", "cohort_rung", "is_synthetic",
        "snapshot_id", "member_hash", "reason",
    ])

    def row(label: str, p: Any, disc: str, suppressed: bool) -> list[Any]:
        s = placement.snapshot
        return [
            placement.supplier_ref, label, p.subject, p.n, p.sufficient, p.quartile,
            p.quartile_label, p.quartile_direction, p.percentile, p.percentile_resolution,
            p.rank_of_n, p.tied_with, p.median, p.direction, p.delta_from_median,
            disc, suppressed, s.cohort_key, s.rung_label, s.is_synthetic,
            s.snapshot_id, s.member_hash, p.reason or "",
        ]

    writer.writerow(row("__overall__", placement.overall, "n/a", False))
    for dp in placement.domains:
        writer.writerow(row(dp.domain, dp.placement, dp.discrimination, dp.suppressed))

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{ref}-benchmark.csv"'},
    )


# --------------------------------------------------------------------------- cohort views


@router.get("/cohorts/{cohort_key}/snapshot")
async def get_snapshot(cohort_key: str, store: StoreDep) -> dict[str, Any]:
    """The latest snapshot for a cohort — aggregates only.

    Includes `member_hash`, deliberately: it lets an auditor confirm two placements were computed
    against the identical population without ever learning who that population was, which is the
    whole of what transparency requires here.
    """
    snap = store.latest_cohort_snapshot(cohort_key)
    if snap is None:
        raise HTTPException(404, f"no snapshot for cohort {cohort_key!r}")
    return snap.public().model_dump(mode="json")


@router.get("/cohorts/{cohort_key}/discrimination")
async def get_discrimination(cohort_key: str, store: StoreDep) -> dict[str, Any]:
    """The full discrimination table for a cohort — every verdict, not just the flagged ones.

    The card stores only the failures because that is what a reader needs. This endpoint returns
    everything, because for the model team "we tested it and it was fine" has to be distinguishable
    from "we never tested it", and only the complete table carries that difference.
    """
    snap = store.latest_cohort_snapshot(cohort_key)
    if snap is None:
        raise HTTPException(404, f"no snapshot for cohort {cohort_key!r}")

    cfg = get_benchmarking_config()
    peers = store.bm_cohort_peers(snap.dimensions)
    from .service import _row_to_peer

    verdicts = all_verdicts([_row_to_peer(r) for r in peers], cfg)
    return {
        "cohort_key": cohort_key,
        "snapshot_id": snap.snapshot_id,
        "n": snap.distribution.n,
        "min_observations": cfg.discrimination_min_observations(),
        "thresholds": {
            "max_modal_share": cfg.max_modal_share(),
            "min_coefficient_of_variation": cfg.min_coefficient_of_variation(),
        },
        "verdicts": [v.model_dump() for v in verdicts],
        "note": "A signal that does not vary across the cohort cannot rank anything. Flagged signals "
                "are excluded from peer-gap reporting and disclosed separately — never silently "
                "included, never silently dropped.",
    }


# --------------------------------------------------------------------------- disputes


class DisputeRequest(BaseModel):
    """A dispute against a cohort INPUT.

    `target` is typed to the four disputable inputs. There is deliberately no member of that type
    naming a cohort, a snapshot or a quartile: the placement is a deterministic lookup over these
    inputs and carries no independent judgement, so a request to dispute one cannot be represented.
    """

    target: DisputeTarget
    evidence: str = Field(min_length=1, description="What the supplier submitted. Retained verbatim.")
    asserted_value: str | None = Field(default=None, description="What it should be")
    observed_value: str | None = Field(default=None, description="What we assigned")
    actor: str | None = None


@router.post("/suppliers/{ref}/cohort-disputes", status_code=201, response_model=CohortDispute)
async def raise_dispute(ref: str, req: DisputeRequest, store: StoreDep) -> CohortDispute:
    """Open a dispute. The placement is notated `disputed` from this moment until it resolves.

    That notation is not politeness — it is the US Chamber / FCRA principle the platform already
    accepts for scores: a disputed rating must be marked as disputed while under review. Silence
    during review is the exposure.
    """
    latest = store.latest_placement(ref)
    return raise_cohort_dispute(
        store, ref, req.target, req.evidence,
        asserted_value=req.asserted_value, observed_value=req.observed_value, actor=req.actor,
        cohort_key_at=latest.assignment.cohort_key if latest else None,
        snapshot_id_at=latest.snapshot.snapshot_id if latest else None,
    )


class AdvanceRequest(BaseModel):
    state: DisputeState
    actor: str | None = None
    note: str | None = Field(default=None, description="Reviewer reasoning. Required on resolution.")


@router.post("/cohort-disputes/{dispute_id}/advance", status_code=201, response_model=CohortDispute)
async def advance_dispute(
    dispute_id: str, req: AdvanceRequest, store: StoreDep
) -> CohortDispute:
    """Append a state transition.

    An UPHELD dispute does not rewrite anything: the reviewer then POSTs corrected attributes, a
    rebuild mints a new snapshot, and a new placement follows. Historical placements keep pointing at
    the population they were computed against — which is exactly why the snapshot is stored.
    """
    if req.state in ("upheld", "partially_upheld", "rejected") and not (req.note or "").strip():
        raise HTTPException(
            422, "a resolution needs a `note`: an outcome with no recorded reasoning is not "
                 "auditable, and this table is the audit trail",
        )
    try:
        return advance_cohort_dispute(
            store, dispute_id, req.state, actor=req.actor, note=req.note
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/suppliers/{ref}/cohort-disputes", response_model=list[CohortDispute])
async def list_disputes(ref: str, store: StoreDep) -> list[CohortDispute]:
    """Current state of each dispute for this supplier — one row per dispute, its latest event."""
    return store.cohort_disputes_for_supplier(ref)


@router.get("/cohort-disputes/{dispute_id}/events", response_model=list[CohortDispute])
async def dispute_events(dispute_id: str, store: StoreDep) -> list[CohortDispute]:
    """The full event history: who asserted what, who decided, when. Append-only, so complete."""
    events = store.cohort_dispute_events(dispute_id)
    if not events:
        raise HTTPException(404, f"no such cohort dispute: {dispute_id}")
    return events
