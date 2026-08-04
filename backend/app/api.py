"""FastAPI surface — Phase 3.

One POST kicks off an async scoring run and returns a job id; progress streams over SSE as
each collector lands; the score, its evidence receipts, and its history are then queryable.

Two invariants the API enforces at the edge (methodology Findings A/B):
  * **A bare score is unrepresentable.** Every score response is the `Score` model, which always
    carries `overall_confidence` and `confidence_band` alongside `blocked`/`refused`/`ghost` —
    you cannot get a lone number out of this API.
  * **Every finding is backed by a retrievable receipt.** `/evidence/{id}` returns the stored,
    hash-stamped raw record the score was formed on — reconstructible months later — and
    `/findings` returns the interpreted evidence, each row carrying the plain-English reason for
    its deduction and the effective penalty actually charged.
"""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from .adjudication_queue import as_dict as adjudication_queue_as_dict
from .adjudication_queue import build as build_adjudication_queue
from .assessment_depth import as_dict as assessment_plan_as_dict
from .assessment_depth import plan_for as assessment_plan_for
from .assessment_depth import table as assessment_depth_table
from .assurity import assurity_report
from .audience_views import procurement_dossier, security_dossier
from .benchmark import build_benchmark, get_benchmark_config, peer_lookup
from .benchmarking.api import router as benchmarking_router
from .benchmarking.models import DataAccessScope
from .benchmarking.service import expectation_gap_for
from .benchmarking.service import firmographics_of as benchmarking_firmographics_of
from .compliance_gap import compliance_gaps
from .concentration import as_dict as concentration_as_dict
from .concentration import concentration as fourth_party_concentration
from .contract_flowdowns import as_dict as flowdowns_as_dict
from .contract_flowdowns import flow_downs
from .coverage_statement import as_dict as coverage_as_dict
from .coverage_statement import coverage_statement
from .estate_readiness import as_dict as estate_readiness_as_dict
from .estate_readiness import measure as measure_estate_readiness
from .evidence_pack import as_dict as evidence_pack_as_dict
from .evidence_pack import build_pack as build_evidence_pack
from .evidence_pack import procurement_view, security_view
from .disclosures import disclosure_block
from .continuity import continuity_report
from .status_page import as_dict as status_page_as_dict
from .status_page import status_page_report
from .exit_readiness import as_dict as exit_readiness_as_dict
from .exit_readiness import exit_readiness
from .fourth_party import SOURCES as fourth_party_sources
from .fourth_party import extract as fourth_party_extract
from .fourth_party import extract_from_raw
from .gap_analysis import GapAnalysisExhausted, GapAnalysisUnavailable
from .gap_analysis import assemble_context as build_gap_analysis_context
from .gap_analysis import gate as gap_analysis_gate
from .gap_analysis import generate as generate_gap_analysis
from .inherent_register import Entry as RegisterEntry
from .inherent_register import apply_entry as apply_register_entry
from .inherent_register import coverage as register_coverage
from .inherent_register import entries as register_entries
from .inherent_register import entry_for as register_entry_for
from .inherent_register import relationships as register_relationships
from .jobs import Job, jobs
from .logging_config import get_logger
from .models import (
    Benchmark,
    Criticality,
    Decision,
    DecisionKind,
    Dispute,
    DisputeKind,
    Evidence,
    GapAnalysisEventKind,
    GapAnalysisRecommendationEvent,
    GapAnalysisRecord,
    PersistedFinding,
    Score,
    SizeBand,
    Substitutability,
    Vendor,
    VendorProfile,
    utcnow,
)
from .pipeline import domain_candidates, resolve_vendor, run_pipeline
from .program_kpis import as_dict as kpis_as_dict
from .program_kpis import compute as compute_kpis
from .program_maturity import as_dict as maturity_as_dict
from .residual_risk import inherent_tier
from .residual_risk import matrix as residual_matrix
from .residual_risk import residual_risk
from .scheduler import monitoring_health, recent_runs
from .profile import apply_size_override, operating_years, refresh_cohort
from .scoring.recommend import recommend, soonest_recheck
from .scoring_config import get_scoring_config
from .storage import Store, close_pool, get_store
from .summariser import SummariserError, SummariserUnavailable, summarise

log = get_logger("api")

def _warm_pool() -> None:
    """Open a connection and run the one-time schema DDL, so the first *user* request does not.

    Roughly seven seconds of TLS handshake and append-only-trigger DDL has to happen once per
    process. It used to happen on every request; now it happens once, and this moves that once
    off the critical path of whoever loads the first page.
    """
    try:
        get_store().close()
    except Exception as exc:  # noqa: BLE001 — a cold pool is a slow start, never a failed boot
        log.warning("pool warm-up skipped: %s", exc)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Warm the pool in the background on the way in; hand the connections back on the way out."""
    warmer = threading.Thread(target=_warm_pool, name="pool-warm", daemon=True)
    warmer.start()
    yield
    close_pool()


app = FastAPI(
    title="OSINT TPRM — vendor risk scoring",
    version="5.2.0",   # tracks the scoring model in scoring.yaml — the deliverable this serves
    summary="Defensible, evidence-linked third-party risk scores from lawfully-public OSINT.",
    lifespan=lifespan,
)


def store_dep() -> Any:
    """Per-request Postgres store. Its pooled connection goes back to the pool after the request."""
    store = get_store()
    try:
        yield store
    finally:
        store.close()




StoreDep = Annotated[Store, Depends(store_dep)]

# Peer benchmarking v2, under /api/v2 (docs/benchmarking-design.md). Mounted alongside the v1
# `/api/vendors/{ref}/benchmark` rather than replacing it, so a client is never handed a different
# response shape under the same URL. The v1 endpoint is deprecated and goes one release from now.
app.include_router(benchmarking_router)


# --------------------------------------------------------------------- requests

class ScoreRequest(BaseModel):
    name: str | None = None
    domain: str | None = None
    ref: str | None = Field(default=None, description="canonical slug; derived if omitted")
    criticality: Criticality | None = Field(
        default=None,
        description=(
            "How much THIS buyer depends on the vendor: low | medium | high. Client-supplied and "
            "never inferred — criticality is not observable from outside, and guessing it would "
            "be the least defensible number on the card. It shapes the recommendation a reader "
            "acts on; it never touches the posture."
        ),
    )
    size_band: SizeBand | None = Field(
        default=None,
        description=(
            "Optional client-supplied size: micro | small | medium | large | mega. Public sources "
            "publish an industry for most vendors but a headcount or revenue for far fewer, and a "
            "sector without a size cannot form a peer cohort. Supplying it here is how a vendor "
            "gets a comparison it would otherwise never get. Recorded as client-supplied, and it "
            "does not change the posture — only which population it is read against."
        ),
    )
    sector: str | None = Field(
        default=None,
        description=(
            "Optional client-supplied sector, for vendors whose industry cannot be classified from "
            "public data. Same discipline as `size_band`: recorded as client-supplied, never scored."
        ),
    )
    substitutability: Substitutability | None = Field(
        default=None,
        description=(
            "P8. How easily this vendor could be REPLACED if the relationship ended: sole_source | "
            "low | medium | high. Client-supplied and never inferred — switching cost, contractual "
            "lock-in and data portability are not observable from outside. Paired with a poor "
            "observed posture, `sole_source` is the single most useful procurement alert this "
            "system can raise; it never touches the posture itself."
        ),
    )
    entity_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description=(
            "OVERRIDE the derived entity-resolution confidence. Leave unset in normal use: it is "
            "computed from the registries after collection (GLEIF match quality, Wikidata domain "
            "verification), and < 0.5 blocks the record for human adjudication. Supply a value "
            "only to force the gate in testing, or to record an adjudicator's decision."
        ),
    )

    @model_validator(mode="after")
    def _need_name_or_domain(self) -> ScoreRequest:
        if not self.name and not self.domain:
            raise ValueError("provide a name or a domain")
        return self


class CompareRequest(BaseModel):
    refs: list[str] = Field(..., min_length=2,
                            description="Vendor refs to compare. Must share a peer cohort.")


class AdjudicationRequest(BaseModel):
    decision: str = Field(description="'cleared' or 'upheld'")
    note: str = Field(description="the human adjudicator's reasoning — retained as the record")
    adjudicator: str | None = None


class DisputeRequest(BaseModel):
    signal: str = Field(description="scoring.yaml signal the finding is under, e.g. 'kev_listed_cve'")
    band_key: str = Field(description="the specific observed band being disputed, e.g. 'listed'")
    kind: DisputeKind = Field(
        description="'nullify' (the finding does not apply — attribution error / compensating "
                    "control) or 'mitigate' (real but evidenced-remediated → ×0.6)")
    evidence: str = Field(min_length=1, description="what you are submitting — a SOC 2 reference, a "
                                                   "patch log, an attribution correction. Retained.")
    submitted_by: str | None = None


class DisputeDecision(BaseModel):
    decision: str = Field(description="'accept' or 'reject'")
    note: str = Field(min_length=1, description="the adjudicator's reasoning — retained as record")
    adjudicator: str | None = None


class DecisionRequest(BaseModel):
    decision: DecisionKind = Field(description="'approve', 'conditional', or 'reject'")
    conditions: str | None = Field(
        default=None, description="the terms — required when decision = 'conditional'")
    decided_by: str | None = Field(default=None, description="who recorded it — role or name")


# --------------------------------------------------------------------- scoring

@app.post("/api/vendors/score", status_code=202)
async def score_vendor(req: ScoreRequest) -> dict[str, Any]:
    """Kick off a scoring run. Returns a job id immediately; stream progress at
    `/api/jobs/{job_id}/stream`, or poll `/api/jobs/{job_id}`.

    A name WITHOUT a domain does not auto-score: most signals are domain-specific, and
    guessing a domain would risk assessing the wrong company. Instead we return
    `needs_domain` with a list of candidate domains for the caller to confirm — analysis
    runs only once a domain is supplied. (A domain, with or without a name, scores directly.)
    """
    if req.domain is None and req.name:
        return {"needs_domain": True, "name": req.name,
                "candidates": domain_candidates(req.name),
                "message": "Provide or confirm a domain — we don't guess it. "
                           "Most signals are domain-specific."}
    vendor = resolve_vendor(name=req.name, domain=req.domain, ref=req.ref,
                            entity_confidence=req.entity_confidence)
    job = jobs.submit(vendor, criticality=req.criticality,
                      size_band=req.size_band, sector=req.sector,
                      substitutability=req.substitutability)
    return {"job_id": job.id, "vendor_ref": vendor.ref, "domain": vendor.domain,
            "status": job.status, "stream": f"/api/jobs/{job.id}/stream"}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = _require_job(job_id)
    return job.public()


@app.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str) -> StreamingResponse:
    job = _require_job(job_id)

    async def events() -> AsyncGenerator[str, None]:
        async for item in jobs.stream(job):
            yield f"event: {item['event']}\ndata: {json.dumps(item['data'])}\n\n"

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --------------------------------------------------------------------- reads

@app.get("/api/vendors/{ref}", response_model=Score)
async def get_vendor_score(ref: str, store: StoreDep) -> Score:
    """The published score, with its recommendation attached at serve time.

    The recommendation is derived, not stored: a rule table over `grade × confidence × criticality`
    plus the soonest re-check any individual finding asks for. Deriving it here rather than
    freezing it means improving the wording improves old records — the same discipline `reason`
    and `action` follow — while the numbers it is derived FROM stay immutable.
    """
    score = store.latest_score(ref)
    if score is None:
        raise HTTPException(404, f"no score for {ref!r} — POST /api/vendors/score first")

    profile = _profile_of(store, ref)
    cfg = get_scoring_config()
    soonest = None
    for row in store.findings_for_vendor(ref):
        if row.effective_penalty > 0:
            act = cfg.action_for(row.signal, row.band_key) or {}
            soonest = soonest_recheck(soonest, act.get("recheck_after"))

    score.recommendation = recommend(
        score,
        criticality=profile.criticality if profile else None,
        soonest=soonest,
    )
    return score


@app.get("/api/vendors/{ref}/history", response_model=list[Score])
async def get_vendor_history(ref: str, store: StoreDep) -> list[Score]:
    return store.score_history(ref)


def _profile_of(store: Store, ref: str) -> VendorProfile | None:
    """Latest stored profile, with its cohort re-derived if it predates the current cohort model.

    Every read path goes through here rather than calling the store directly, so a profile written
    under an older schema cannot reach a benchmark, a peer list or a comparison in a shape those
    were never built to handle. See `profile.refresh_cohort`.
    """
    return refresh_cohort(store.latest_profile(ref))


@app.get("/api/vendors/{ref}/profile", response_model=VendorProfile)
async def get_vendor_profile(ref: str, store: StoreDep) -> VendorProfile:
    """WHO the vendor is — industry, size, country, ownership, and the peer cohort that follows.

    Served separately from the score on purpose. The profile is context a score is READ against,
    never an input to it, and keeping the two apart in the API is the cheapest way to keep that
    true: nothing in this response can reach the scoring engine, because the engine has already
    finished by the time it is built (see `pipeline.py`).
    """
    profile = _profile_of(store, ref)
    if profile is None:
        raise HTTPException(404, f"no profile for {ref!r} — score the vendor first")
    return profile


class SizeRequest(BaseModel):
    size_band: SizeBand = Field(description="the client-supplied headcount band — micro…mega")


@app.post("/api/vendors/{ref}/size", status_code=201)
async def set_vendor_size(ref: str, req: SizeRequest, store: StoreDep) -> dict[str, Any]:
    """Add a CLIENT-supplied size to a vendor public sources gave none for, so a peer group can
    form — WITHOUT re-scoring. Size never touches the posture, so there is nothing to recompute:
    this re-derives the cohort and appends a new profile row (the store is append-only). The score
    the card already shows is byte-identical afterwards; only the comparison appears or sharpens.
    """
    profile = _profile_of(store, ref)
    if profile is None:
        raise HTTPException(409, f"no profile for {ref!r} — score the vendor first")
    updated = apply_size_override(profile, req.size_band)
    if updated.cohort is None:
        # Size alone cannot rescue a vendor whose SECTOR is unknown — there is still no industry
        # to be a peer within. Say so, rather than storing a profile that still cannot benchmark.
        raise HTTPException(
            422, f"{ref!r} still has no cohort — its sector could not be established from public "
                 "sources, and a peer group needs an industry as well as a size")
    store.put_profile(updated)
    return {"vendor_ref": ref, "cohort": updated.cohort.model_dump(mode="json"),
            "size_client_supplied": True,
            "note": "peer group updated; the posture is unchanged — size never reaches the score"}


class InherentDeclaration(BaseModel):
    """The two E10b inputs plus P8's third, declared for an EXISTING vendor.

    Every field is optional individually — `inherent_tier` takes the worse of the two and says when
    only one arrived — but at least one of `criticality` / `data_access_scope` must be present, or
    there is no declaration to make.
    """

    criticality: Criticality | None = Field(
        default=None, description="How badly this vendor's failure hurts THIS buyer")
    data_access_scope: DataAccessScope | None = Field(
        default=None, description="What this vendor holds for this buyer — low…critical")
    substitutability: Substitutability | None = Field(
        default=None, description="P8 — how replaceable the relationship is")
    basis: str = Field(
        min_length=40,
        description="Why this exposure, in words a relationship owner can argue with. Required, "
                    "and the minimum length is the point: a declaration nobody can contest is a "
                    "number, and this system publishes no numbers nobody can contest.")
    declared_by: str = Field(min_length=2, description="Who is accountable for this declaration")
    confirmed: bool = Field(
        default=False,
        description="TRUE ONLY WHEN THE ACCOUNTABLE RELATIONSHIP OWNER IS THE ONE DECLARING IT. "
                    "Left false, this is a provisional declaration: it routes P5's depth and "
                    "publishes an E10b residual tier, but every page that shows it says so.")


@app.post("/api/vendors/{ref}/inherent", status_code=201)
async def declare_inherent(ref: str, req: InherentDeclaration, store: StoreDep) -> dict[str, Any]:
    """Declare this relationship's inherent exposure — WITHOUT re-scoring.

    THIS ROUTE IS WHY THE DECLARATION RATE WAS ZERO. Until it existed the only path that accepted a
    criticality was `POST /api/vendors/score`, which re-runs the whole pipeline against a dozen of
    someone else's free services. Declaring an exposure therefore cost a full scan, and P9's
    dashboard read `inherent_tier_declaration_rate: 0.0%` across 146 vendors — a missing route
    wearing the costume of a missing habit.

    NOTHING HERE TOUCHES THE POSTURE, and that is the E10b invariant rather than an optimisation.
    Inherent exposure and observed posture run on different clocks: posture moves when the vendor's
    controls move, exposure moves when the contract does. The score row is not read, not rewritten
    and not invalidated. The residual tier changes because it is recomputed on read from two inputs,
    one of which just changed — which is exactly what "a rendering, not a score" means.

    Append-only, like everything else: this SUPERSEDES the profile rather than editing it, so the
    profile the last score was read against stays exactly as it was.
    """
    if req.criticality is None and req.data_access_scope is None:
        raise HTTPException(
            422, "declare at least one of `criticality` or `data_access_scope` — a declaration "
                 "with neither is the undeclared state with a timestamp on it")

    entry = RegisterEntry(
        ref=ref, classification="relationship", criticality=req.criticality,
        data_access_scope=req.data_access_scope, substitutability=req.substitutability,
        basis=req.basis, declared_by=req.declared_by,
        declared_on=utcnow().date().isoformat(), confirmed=req.confirmed,
    )
    applied = apply_register_entry(store, entry)
    registered = register_entry_for(ref)
    return {
        "vendor_ref": ref,
        "inherent_tier": applied.tier,
        "provisional": not req.confirmed,
        "criticality": req.criticality,
        "data_access_scope": req.data_access_scope,
        "substitutability": req.substitutability,
        "declared_by": req.declared_by,
        "note": ("Declared. The posture is unchanged — inherent exposure never reaches the score. "
                 "Residual risk is recomputed on read, so "
                 f"GET /api/vendors/{ref}/residual-risk reflects this immediately."),
        "register": (
            None if registered is None else {
                "classification": registered.classification,
                "warning": (
                    None if registered.classification == "relationship" else
                    f"THIS REF IS ON THE INVENTORY OF RECORD AS `{registered.classification}`: "
                    f"{registered.note} Declaring an exposure against it does not make it a "
                    f"relationship — fix the inventory instead."),
            }),
    }


@app.get("/api/program/inventory")
async def get_inventory(store: StoreDep) -> dict[str, Any]:
    """The inventory of record — which rows in the book are relationships, and which are not.

    P9 scores Inventory & Tiering at Level 2 because the programme had no inventory of record. This
    is it, and it is the reason `inherent_tier_declaration_rate` moved: 146 scored rows were never
    146 relationships, and a denominator that could not tell a seeded benchmarking vendor from a
    real supplier could not produce an actionable number in either direction.

    `unregistered` is the bucket to watch. A vendor in the book that nobody has classified at all is
    neither declared nor excused, and it is reported on its own rather than folded into either.
    """
    cov = register_coverage(store)
    return {
        **cov,
        "relationships_detail": [
            {"ref": e.ref, "criticality": e.criticality,
             "data_access_scope": e.data_access_scope, "substitutability": e.substitutability,
             "confirmed": e.confirmed, "provisional": e.provisional,
             "basis": e.basis, "declared_by": e.declared_by, "declared_on": e.declared_on,
             "note": e.note}
            for e in register_relationships()
        ],
        "inventory_defects": [
            {"ref": e.ref, "note": e.note} for e in register_entries()
            if e.classification == "not_a_relationship"
        ],
        "note": ("Corpus vendors are derived from `seed_cohorts.SEED_SETS` rather than listed, so "
                 "the two can never disagree. They carry no declaration by design: there is no "
                 "commercial relationship, so there is no exposure, and inventing one to move a "
                 "metric is the failure this register exists to prevent."),
    }


@app.get("/api/vendors/{ref}/benchmark", response_model=Benchmark, deprecated=True)
async def get_vendor_benchmark(ref: str, store: StoreDep) -> Benchmark:
    """**DEPRECATED — superseded by `GET /api/v2/suppliers/{ref}/benchmark`.**

    This vendor's posture against its peer cohort — or a stated refusal to publish one.

    Refuses, in words, when: the vendor has no cohort (sector or size unknown), it has no
    published posture (blocked or refused), or the cohort holds fewer than `min_cohort_n` peers.
    That last one is the feature, not a limitation: a median over three vendors is noise wearing
    the costume of precision, and manufacturing precision from thin evidence is exactly what
    Finding A punishes.

    WHY IT IS STILL MOUNTED. Removing it would change a response shape under existing clients,
    which is the exact thing the side-by-side `/api/v2` mount was built to avoid. It goes one
    release from now, together with `benchmark.py`.

    WHAT WAS FIXED RATHER THAN LEFT TO THE CUTOVER, because this is still the DEFAULT route and
    `run_pipeline` writes its output onto every scored vendor — so "it goes away next release"
    would have meant shipping both defects for another release:

      * `min_cohort_n: 1` is gone, and the floor of 8 is enforced IN CODE, not only in YAML.
      * A synthetic baseline now publishes NO ORDINAL PLACEMENT — no percentile, no quartile, no
        variance-from-median — at any n. The reference line and its caveat stay; the rank against
        six invented postures does not. A caveat is not enough, because the caption does not
        travel with the screenshot.

    v2 additionally offers what this endpoint cannot: midrank tie handling, `rank_of_n`, a
    reproducible cohort snapshot, a dispute path, and per-cohort discrimination.
    """
    profile = _profile_of(store, ref)
    score = store.latest_score(ref)
    cohort = profile.cohort if profile else None
    categories = {c.category: c.posture for c in score.categories
                  if c.posture is not None} if score else {}
    signals, drivers = _subject_signals(store, ref)
    return build_benchmark(
        score.posture if score else None, cohort,
        lookup=peer_lookup(store, exclude_ref=ref), categories=categories,
        signals=signals, gap_drivers=drivers,
        subject_confidence=score.overall_confidence if score else None,
        vendor_age_years=operating_years(profile),
    )


def _subject_signals(store: Store, ref: str) -> tuple[dict[str, str], dict[str, list[str]]]:
    """This vendor's observed band per signal, plus what drives each category's deficit.

    Two things fall out of one pass over the findings:
      * `signals` — every signal and the band observed, feeding prevalence ("79% of peers publish
        a DMARC record; you do not");
      * `gap_drivers` — per category, the findings that cost the most, largest first. A gap with
        no named cause is a number; a gap with three named causes is a to-do list.
    """
    cfg = get_scoring_config()
    signals: dict[str, str] = {}
    charged: dict[str, list[tuple[float, str]]] = {}
    for row in store.findings_for_vendor(ref):
        signals[row.signal] = row.band_key
        if row.effective_penalty > 0:
            label = cfg.reason_for(row.signal, row.band_key) or row.signal.replace("_", " ")
            charged.setdefault(row.category, []).append((row.effective_penalty, label))

    drivers = {
        category: [label for _p, label in sorted(items, reverse=True)[:3]]
        for category, items in charged.items()
    }
    return signals, drivers


@app.get("/api/vendors/{ref}/peers")
async def get_vendor_peers(ref: str, store: StoreDep) -> dict[str, Any]:
    """The vendors this one may legitimately be compared with — its cohort, and nobody else.

    **Comparison is cohort-bounded by construction.** There is no endpoint that will line a
    mega-cap US technology vendor up against a small Australian food manufacturer, because that
    comparison is not harsh, it is meaningless: different observable surface area, different
    regulatory pressure, different expected posture. Peers come from the cohort or not at all.
    """
    profile = _profile_of(store, ref)
    if profile is None:
        raise HTTPException(404, f"no profile for {ref!r} — score the vendor first")
    if profile.cohort is None:
        return {
            "vendor_ref": ref, "cohort": None, "n": 0, "peers": [],
            "message": "no peer cohort — this vendor's sector or size could not be established "
                       "from public sources, so it has an absolute grade and no comparison",
        }
    members = store.cohort_members(profile.cohort.key)
    return {
        "vendor_ref": ref,
        "cohort": profile.cohort.model_dump(mode="json"),
        "n": len(members),
        "min_cohort_n": get_benchmark_config().min_cohort_n(),
        "peers": [{"vendor_ref": r, "posture": p} for r, p in members],
    }


@app.post("/api/compare")
async def compare_vendors(req: CompareRequest, store: StoreDep) -> dict[str, Any]:
    """Compare vendors — and REFUSE, with reasons, when they are not comparable.

    A 409 here is the product working. Two vendors in different cohorts have no common yardstick,
    and returning a ranked list anyway would be the single most misleading thing this system could
    do: it would look authoritative and mean nothing. The refusal names both cohorts so the caller
    can see exactly why.
    """
    if len(req.refs) < 2:
        raise HTTPException(422, "provide at least two vendor refs")

    entries: list[dict[str, Any]] = []
    for ref in req.refs:
        profile = _profile_of(store, ref)
        score = store.latest_score(ref)
        if profile is None or score is None:
            raise HTTPException(404, f"no scored profile for {ref!r} — score the vendor first")
        entries.append({
            "vendor_ref": ref,
            "posture": score.posture,
            "grade": score.grade,
            "confidence": score.overall_confidence,
            "confidence_band": score.confidence_band,
            "blocked": score.blocked,
            "refused": score.refused,
            "cohort": profile.cohort.key if profile.cohort else None,
            "sector": profile.cohort.sector if profile.cohort else None,
            "revenue_band": profile.cohort.revenue_band if profile.cohort else None,
            "employee_band": profile.cohort.employee_band if profile.cohort else None,
            "region": profile.cohort.region if profile.cohort else None,
        })

    cohorts = {e["cohort"] for e in entries}
    if None in cohorts:
        unclassified = [e["vendor_ref"] for e in entries if e["cohort"] is None]
        raise HTTPException(409, {
            "error": "not_comparable",
            "reason": "unclassified vendor(s): sector or size could not be established from "
                      "public sources, so there is no basis on which to compare them",
            "vendors": unclassified,
        })
    if len(cohorts) > 1:
        raise HTTPException(409, {
            "error": "not_comparable",
            "reason": "these vendors are in different peer cohorts. Industry, size and regulatory "
                      "region all change what a given posture means, so a cross-cohort ranking "
                      "would look authoritative and mean nothing.",
            "cohorts": {e["vendor_ref"]: e["cohort"] for e in entries},
        })

    postures = [e["posture"] for e in entries if e["posture"] is not None]
    return {
        "comparable": True,
        "cohort": next(iter(cohorts)),
        "vendors": sorted(entries, key=lambda e: (e["posture"] is None, -(e["posture"] or 0))),
        "cohort_median": _median(postures),
    }


def _median(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


@app.get("/api/vendors/{ref}/export")
async def export_evidence_pack(
    ref: str,
    store: StoreDep,
    view: Annotated[str | None, Query(
        pattern="^(procurement|security)$",
        description="P6 — render the same record for one audience. Omit for the full document.",
    )] = None,
) -> dict[str, Any]:
    """The whole record as one self-contained document — what goes in the procurement file.

    P6 — `?view=procurement` and `?view=security` are TWO ARRANGEMENTS OF THIS SAME OBJECT, not two
    documents. Nothing is recomputed for either: every figure is copied from the module that owns
    it, which is what stops the two from disagreeing. See `app/audience_views.py`.

      * `procurement` reads top-down and may stop early, so the order is the design: decision,
        residual risk, continuity, concentration, contract flow-downs, cadence, coverage, then the
        evidence request pack.
      * `security` reads to find the next task: findings by effective penalty, grouped by the
        domain that owns them, each with its receipt, peer prevalence, ask and dispute state.

    THE COVERAGE STATEMENT AND THE CONFIDENCE FIGURE TRAVEL ON BOTH. A limitation visible to only
    one reader is a limitation the other acts without, and the reader who signs is the one who can
    least afford to miss it. `views_agree()` asserts this, and the suite runs it.

    The unfiltered document is unchanged — every existing caller gets byte-for-byte what it got
    before.

    THE TEST THIS MUST PASS: **the pack reconstructs the published score from its own contents.**
    If a reader cannot add the findings up and arrive at the number on the front, it is a summary,
    not an evidence pack — and under Finding A a score that cannot be reconstructed from what was
    retained is the thing this system exists not to produce. The `reconstruction` block below does
    that arithmetic explicitly and states whether it balances, so the claim is checkable by the
    person holding the file rather than taken on trust.

    Includes the disclosures and attribution verbatim. Those are obligations, not garnish: the NVD
    notice is required wording, and HIBP's licence requires attribution wherever its data appears.
    """
    score = store.latest_score(ref)
    if score is None:
        raise HTTPException(404, f"no score for {ref!r} — POST /api/vendors/score first")

    profile = _profile_of(store, ref)
    cfg = get_scoring_config()
    findings = store.findings_for_vendor(ref)

    soonest = None
    for row in findings:
        if row.effective_penalty > 0:
            act = cfg.action_for(row.signal, row.band_key) or {}
            soonest = soonest_recheck(soonest, act.get("recheck_after"))
    score.recommendation = recommend(
        score, criticality=profile.criticality if profile else None, soonest=soonest)

    disputes = store.accepted_dispute_targets(ref)
    rows: list[dict[str, Any]] = []
    for row in findings:
        act = cfg.action_for(row.signal, row.band_key) or {}
        rows.append({
            **row.model_dump(mode="json"),
            "reason": cfg.reason_for(row.signal, row.band_key),
            "action": act.get("action"),
            "ask_of_vendor": act.get("ask_of_vendor"),
            "recheck_after": act.get("recheck_after"),
            "accepts_as_refute": act.get("accepts_as_refute"),
            # P6 — an item already adjudicated must not be chased twice. Same source P3's security
            # rendering reads, so the two cannot disagree about what is settled.
            "dispute_status": disputes.get((row.signal, row.band_key)),
        })

    # Receipt INDEX, not payloads: the pack stays readable, and every row names the hash a reader
    # can pull in full from /evidence/{id} and re-verify against the store.
    receipts = [{
        "evidence_id": e.id, "source": e.source, "status": e.status,
        "fetched_at": e.fetched_at.isoformat(), "source_version": e.source_version,
        "reliability": e.reliability, "content_hash": e.content_hash,
    } for e in store.for_vendor(ref)]

    subject_signals, subject_drivers = _subject_signals(store, ref)
    benchmark = build_benchmark(
        score.posture, profile.cohort if profile else None,
        lookup=peer_lookup(store, exclude_ref=ref),
        categories={c.category: c.posture for c in score.categories if c.posture is not None},
        signals=subject_signals, gap_drivers=subject_drivers,
        subject_confidence=score.overall_confidence,
        vendor_age_years=operating_years(profile),
    )

    if view:
        # P6. EVERY PIECE IS BUILT BY THE MODULE THAT OWNS IT and handed over already finished —
        # `audience_views` arranges, and holds no arithmetic of its own.
        coverage = _coverage_for(store, ref, score)
        pack = build_evidence_pack(ref, findings, cfg, disputes=disputes)
        plan = _assessment_plan_of(store, ref, soonest)
        if view == "security":
            return security_dossier(
                vendor_ref=ref, score=score, findings=rows, receipts=receipts,
                category_postures=[c.model_dump(mode="json") for c in score.categories],
                peer_signals=[s.model_dump(mode="json") for s in benchmark.signals],
                evidence_pack=evidence_pack_as_dict(pack), coverage=coverage,
                assessment_plan=plan, soonest_recheck=soonest,
            )
        firmographics = benchmarking_firmographics_of(store, ref)
        provisional = profile.inherent_provisional if profile else False
        inherent = inherent_tier(profile.criticality if profile else None,
                                 firmographics.data_access_scope if firmographics else None,
                                 provisional=provisional)
        substitutability = profile.substitutability if profile else None
        residual = residual_risk(
            score.posture, profile.criticality if profile else None,
            firmographics.data_access_scope if firmographics else None,
            blocked=score.blocked, refused=score.refused,
            substitutability=substitutability, provisional=provisional,
        )
        continuity = continuity_report(ref, findings)
        spof = _spof_providers(store, ref)
        return procurement_dossier(
            status_page=status_page_as_dict(status_page_report(ref, store.for_vendor(ref))),
            vendor_ref=ref, score=score,
            recommendation=score.recommendation.model_dump(mode="json"),
            residual={
                "published": residual.published, "residual": residual.residual,
                "residual_label": residual.residual_label, "headline": residual.headline(),
                "inherent_tier": residual.inherent.tier,
                "inherent_basis": residual.inherent.basis,
                "substitutability": residual.substitutability,
                "escalated_for_sole_source": residual.escalated,
                "escalated_from": residual.escalated_from,
                "reason": residual.reason, "caveats": residual.caveats,
            },
            continuity=continuity, concentration=spof,
            flowdowns=flowdowns_as_dict(ref, flow_downs(
                ref, findings, continuity_flags=continuity.flags, spof_providers=spof,
                ghost=bool(score.ghost),
                thin_coverage=score.confidence_band == "Low",
                substitutability=substitutability)),
            assessment_plan=plan,
            coverage=coverage,
            evidence_pack=procurement_view(pack, inherent.tier, inherent.basis),
        )

    return {
        "generated_at": utcnow().isoformat(),
        "vendor_ref": ref,
        "model_version": cfg.version,
        "api_version": app.version,
        "profile": profile.model_dump(mode="json") if profile else None,
        "score": score.model_dump(mode="json"),
        "benchmark": benchmark.model_dump(mode="json"),
        "findings": rows,
        "dependencies": [
            {"provider": d.provider, "category": d.category, "detected_via": d.detected_via}
            for d in fourth_party_extract(store.for_vendor(ref))
        ],
        "evidence_receipts": receipts,
        "reconstruction": _reconstruction(score, findings, cfg),
        # P2. The pack is what goes in the procurement file, so it is the one place a coverage
        # limit MUST travel with the number -- a reader holding the file months later has no
        # other way to know what the assessment could not see.
        "coverage_statement": _coverage_for(store, ref, score),
        # P7. Point-in-time availability, routed to Continuity and never to Posture. In the full
        # document because the procurement file is exactly where "can they keep serving us" gets
        # asked, and a route nobody assembles is a route nobody reads.
        "status_page": status_page_as_dict(status_page_report(ref, store.for_vendor(ref))),
        "disclosures": disclosure_block(),
    }


def _reconstruction(score: Score, findings: list[PersistedFinding],
                    cfg: Any) -> dict[str, Any]:
    """Show the arithmetic, and say whether it balances.

    `effective_penalty` is what was ACTUALLY charged after the NIST modifiers and after each
    (category, signal) group collapsed to its worst member — so these are the numbers that sum to
    the published category penalties. `penalty` is the pre-adjustment base and deliberately will
    not: a four-year-old breach stores −40 against a category that only lost −16.

    `balanced: false` is not cosmetic. It means the receipts do not add up to the published score,
    which is a defect worth surfacing in the pack rather than hiding.
    """
    by_category: dict[str, list[PersistedFinding]] = {}
    for row in findings:
        by_category.setdefault(row.category, []).append(row)

    categories = []
    total_capped = 0.0
    balanced = True
    for cat in score.categories:
        charged = [r for r in by_category.get(cat.category, []) if r.effective_penalty > 0]
        summed = round(sum(r.effective_penalty for r in charged), 2)
        published = round(cat.penalty, 2)
        ok = abs(summed - published) < 0.05
        balanced = balanced and ok
        total_capped += min(published, float(cfg.max_score))
        categories.append({
            "category": cat.category,
            "published_penalty": published,
            "sum_of_receipts": summed,
            "balances": ok,
            "published_posture": cat.posture,
            "coverage": cat.coverage,
            "deductions": [{
                "signal": r.signal, "band": r.band_key, "severity": r.severity,
                "base_penalty": r.penalty, "charged": round(r.effective_penalty, 2),
                "occurrences": r.occurrences, "evidence_id": r.evidence_id,
                "promoted_from": r.base_severity if r.promoted_by else None,
                "promoted_by": r.promoted_by,
            } for r in charged],
        })

    divisor = cfg.penalty_divisor()
    computed = max(0.0, float(cfg.max_score) - total_capped / divisor)
    return {
        "formula": "overall_posture = 100 - (sum of category penalties, each capped at 100) / divisor",
        "penalty_divisor": divisor,
        "total_capped_penalty": round(total_capped, 2),
        "computed_posture": round(computed, 2),
        "published_posture": score.posture,
        "critical_ceiling_applied": score.critical_ceiling_applied,
        "ceiling_cause": score.ceiling_cause,
        # E7d. The receipt is where a WITHHELD number matters most: `computed_posture` and
        # `published_posture` differ, and without this the reader has no way to see which of the
        # two ceilings moved it — or that a ceiling moved it at all rather than an arithmetic bug.
        "confidence_ceiling_applied": score.confidence_ceiling_applied,
        "confidence_ceiling": score.confidence_ceiling,
        "confidence": score.overall_confidence,
        "confidence_is_coverage": score.overall_confidence,  # backward-compatible alias
        "categories": categories,
        "balances": balanced,
        "note": (
            "`charged` is the effective penalty after age, frequency and mitigation modifiers and "
            "after each (category, signal) group collapsed to its worst member. Those sum to the "
            "published category penalty; the pre-adjustment `base_penalty` does not, by design."
        ),
    }


@app.get("/api/vendors/{ref}/dependencies")
async def get_vendor_dependencies(ref: str, store: StoreDep) -> dict[str, Any]:
    """WHO the vendor depends on — its fourth parties, read from evidence already collected.

    DISCLOSED, NEVER SCORED. This re-reads the DNS/CT/trust/header evidence the pipeline already
    stored; it adds no source, emits no finding, and cannot reach the scoring engine. A fourth
    party's problems are concentration context, not a penalty on this vendor — charging every AWS
    customer for an AWS CVE would punish thousands of vendors for a dependency they share with
    their competitors. The finding that matters — *"six of your vendors share one identity
    provider"* — is a portfolio statement, and that half needs the platform.
    """
    evidence = store.for_vendor(ref)
    if not evidence:
        raise HTTPException(404, f"no evidence for {ref!r} — POST /api/vendors/score first")
    deps = fourth_party_extract(evidence)
    by_category: dict[str, int] = {}
    for d in deps:
        by_category[d.category] = by_category.get(d.category, 0) + 1
    return {
        "vendor_ref": ref,
        "dependencies": [
            {"provider": d.provider, "category": d.category,
             "detected_via": d.detected_via, "evidence": d.evidence}
            for d in deps
        ],
        "count": len(deps),
        "by_category": by_category,
        "note": "Fourth parties are disclosed as concentration context, never scored. "
                "Portfolio-wide concentration (shared dependencies across many vendors) needs the "
                "portfolio view.",
    }


@app.get("/api/vendors/{ref}/continuity")
async def get_vendor_continuity(ref: str, store: StoreDep) -> dict[str, Any]:
    """Going-concern status — registry-cited facts, deliberately NOT a score.

    These signals used to sit inside Posture, where a vendor entering administration lost 20 points
    of TECHNICAL SECURITY posture and a company under ten years old was penalised for its founding
    date. Both are real things a buyer must see; neither is a security control.

    DISCLOSED, NEVER SCORED, and not reduced to a number. Four registry bands cannot support
    hundred-point precision, and a derived distress index is credit-rating territory — a different
    kind of claim, with different legal exposure, from an observed one. Every flag carries the
    register that said so and the date we retrieved it, which is what makes it publishable and
    disputable.
    """
    findings = store.findings_for_vendor(ref)
    if not findings:
        raise HTTPException(404, f"no findings for {ref!r} — POST /api/vendors/score first")
    report = continuity_report(ref, findings)
    return {
        "vendor_ref": report.vendor_ref,
        "standing": report.standing,
        "flags": [
            {"signal": f.signal, "band": f.band, "standing": f.standing,
             "statement": f.statement, "cited": f.cited(), "source": f.source,
             "observed": f.observed, "evidence_id": f.evidence_id,
             "retrieved_at": f.retrieved_at}
            for f in report.flags
        ],
        "age_context": report.age_context,
        "caveats": report.caveats,
    }


@app.get("/api/vendors/{ref}/status-page")
async def get_vendor_status_page(ref: str, store: StoreDep) -> dict[str, Any]:
    """P7 — outage history from the vendor's own status page, routed to Continuity, never Posture.

    FREQUENT OUTAGES ARE A DELIVERY PROBLEM, NOT A SECURITY PROBLEM. Nothing here can move a posture
    point: `status_page_collector.py` emits no `Finding` at all, `ok` or `empty` — the same
    discipline `FirmographicsCollector` holds for the same reason — so there is nothing for the
    scoring engine to see even by accident.

    ONLY THE STATUSPAGE.IO V2 SHAPE IS RECOGNISED, at `status.<domain>/api/v2/*.json` — the one
    status-page format stable enough to parse with confidence, and the common pattern for a vendor
    that CNAMEs a status subdomain to Statuspage. A vendor on a different platform, or one this
    check does not reach, reports as NOT FOUND — a coverage gap, not a claim that outages are rare.
    """
    evidence = store.for_vendor(ref)
    if not evidence:
        raise HTTPException(404, f"no evidence for {ref!r} — POST /api/vendors/score first")
    return status_page_as_dict(status_page_report(ref, evidence))


def _expectation_gap_or_none(store: Store, ref: str, score: Score) -> Any:
    """E10a for a vendor, or None if the cohort inputs are not recorded.

    Never raises. This assembles a supporting figure onto a card that is already useful without it
    — a missing peer group must cost a reader their peer context and nothing else, which is the
    same degrade-alone discipline `_maturity_gap` applies in the v1 benchmark.
    """
    try:
        firmographics = benchmarking_firmographics_of(store, ref)
        if firmographics is None:
            return None
        return expectation_gap_for(
            store, firmographics, score.posture,
            findings=store.findings_for_vendor(ref),
            penalty_divisor=get_scoring_config().penalty_divisor(),
        )
    except Exception:  # noqa: BLE001 — context beside the score, never worth the whole card
        log.warning("expectation gap unavailable for %r", ref, exc_info=True)
        return None


@app.get("/api/vendors/{ref}/assessment")
async def get_vendor_assessment(ref: str, store: StoreDep) -> dict[str, Any]:
    """THE ONE BLOCK A PROCUREMENT READER ACTUALLY NEEDS, assembled from parts that already exist.

        Technical Posture:  71 (Confidence 0.81)
        Peer Context:       Median 83 for financial services, medium, ANZ (n=18)
        Expectation Gap:    -12 points (17th of 34 · bottom quartile)
        Interpretation:     Materially below peers on email authentication and certificate hygiene
        Residual Risk:      High (high inherent x moderate posture)
        Recommended action: Conditional approval — targeted remediation, evidence pack, 6-month review

    WHY THIS ROUTE EXISTS AT ALL, given every number on it is already served somewhere. The three
    layers were reachable only as three separate calls, so ASSEMBLING THEM WAS THE CLIENT'S JOB —
    and a client that assembles them slightly differently from the next client is how a posture
    ends up presented as a residual risk, or a peer gap read as a grade. The composition is part of
    the product, so it is served rather than described.

    NOTHING IS RECOMPUTED HERE. Each layer is produced by the module that owns it and copied out:
    posture from the stored score, peer context from `benchmarking/`, residual from the lookup.
    This route holds no arithmetic of its own, which is what stops it becoming a fourth source of
    truth about a vendor.

    EACH LAYER DEGRADES ALONE. No cohort attributes means no peer context and everything else
    still renders; no declared exposure means no residual tier and the posture still stands. A
    reader gets what is known, labelled, rather than a 409 for what is not.
    """
    score = store.latest_score(ref)
    if score is None:
        raise HTTPException(404, f"no score for {ref!r} — POST /api/vendors/score first")

    profile = _profile_of(store, ref)
    firmographics = benchmarking_firmographics_of(store, ref)
    cfg = get_scoring_config()

    gap = _expectation_gap_or_none(store, ref, score)
    residual = residual_risk(
        score.posture,
        profile.criticality if profile else None,
        firmographics.data_access_scope if firmographics else None,
        blocked=score.blocked, refused=score.refused,
        # P8 — a declared `sole_source` escalates the published tier one band. Disclosed on the
        # response via `escalated_from`, never absorbed into the cell.
        substitutability=profile.substitutability if profile else None,
        provisional=profile.inherent_provisional if profile else False,
    )

    soonest = None
    for row in store.findings_for_vendor(ref):
        if row.effective_penalty > 0:
            soonest = soonest_recheck(
                soonest, (cfg.action_for(row.signal, row.band_key) or {}).get("recheck_after"))
    recommendation = recommend(
        score, criticality=profile.criticality if profile else None, soonest=soonest,
        # E10a reaches the CADENCE only. A peer comparison that could move a decision would be
        # the firmographic multiplier E1 deleted, arriving through the benchmark instead.
        expectation_gap=gap.gap if (gap and gap.published) else None,
    )

    return {
        "vendor_ref": ref,
        # LAYER 2 — control posture. Ours to measure. Never published without its confidence.
        "posture": {
            "posture": score.posture,
            "grade": score.grade,
            "confidence": score.overall_confidence,
            "confidence_band": score.confidence_band,
            "blocked": score.blocked,
            "blocked_reason": score.blocked_reason,
            "refused": score.refused,
            "ghost": score.ghost,
            "critical_ceiling_applied": score.critical_ceiling_applied,
            "confidence_ceiling_applied": score.confidence_ceiling_applied,
        },
        # LAYER 3 — peer context. Interprets layer 2; never feeds back into it.
        "peer_context": None if gap is None else {
            "published": gap.published,
            "expected_posture": gap.expected_posture,
            "expectation_gap": gap.gap,
            "estimator": gap.estimator,
            "n": gap.n,
            "headline": gap.headline(),
            "drivers": [d.cited() for d in gap.drivers],
            "suppressed_signals": gap.suppressed_signals,
            "reason": gap.reason,
        },
        # LAYER 1 — inherent exposure, client-declared, plus the residual lookup over both.
        "residual_risk": {
            "published": residual.published,
            "residual": residual.residual,
            "residual_label": residual.residual_label,
            "headline": residual.headline(),
            "inherent_tier": residual.inherent.tier,
            "inherent_basis": residual.inherent.basis,
            "reason": residual.reason,
        },
        "recommendation": recommendation.model_dump(),
        "caveats": [
            "THREE SEPARATE MEASUREMENTS, never collapsed. Posture is what we observed of the "
            "vendor's controls. Peer context interprets that against similar suppliers and has no "
            "path back into it. Inherent exposure is declared by the buyer and is not about the "
            "vendor at all.",
            "The peer comparison cannot change the grade. It reaches the monitoring cadence and "
            "nothing else — the same evidence scores identically in every cohort.",
            *residual.caveats,
            *(gap.caveats if gap else []),
        ],
    }


def _coverage_for(store: Store, ref: str, score: Score) -> dict[str, Any]:
    """P2. Built from what this run actually did, never hand-written."""
    cfg = get_scoring_config()
    covered = {f.signal for f in store.findings_for_vendor(ref)}
    return coverage_as_dict(coverage_statement(
        ref, store.for_vendor(ref),
        signals_covered=len(covered & cfg._all_signal_names()),
        signals_planned=cfg.planned_signal_count(),
        held=cfg.data.get("held_roadmap") or {},
    ))


@app.get("/api/vendors/{ref}/coverage")
async def get_vendor_coverage(ref: str, store: StoreDep) -> dict[str, Any]:
    """P2 — what this assessment could NOT see, derived from the run rather than written.

    COUNTER-INTUITIVELY THIS INCREASES CREDIBILITY WITH MATURE BUYERS. A report that claims less is
    a report a security team can check, and the first thing an experienced reader does with an
    outside-in assessment is look for the boundary. Finding it stated is the difference between a
    product and a marketing artefact. It is also the cheapest legal protection in the plan: under
    Finding A, what makes a published number defensible is that its limits travelled with it.

    NEVER HAND-WRITTEN PER VENDOR. A written statement is wrong the moment a collector fails on one
    run and nobody edits the prose — and wrong in the FLATTERING direction, still claiming coverage
    the run did not achieve. Deriving it means a source that failed at 03:00 shows up as a gap in
    that morning's report without anyone noticing it needed to.

    THE DISTINCTION THAT DOES THE WORK: `not_collected_this_run` may close on a re-run;
    `never_observable_from_outside` never closes. A reader who cannot tell them apart will either
    dismiss a real gap as a transient or wait indefinitely for a limit that will not lift.
    """
    score = store.latest_score(ref)
    if score is None:
        raise HTTPException(404, f"no score for {ref!r} — POST /api/vendors/score first")
    return _coverage_for(store, ref, score)


@app.get("/api/vendors/{ref}/evidence-request-pack")
async def get_evidence_request_pack(
    ref: str,
    store: StoreDep,
    view: Annotated[str | None, Query(
        pattern="^(procurement|security)$",
        description="Audience rendering. Omit for the raw pack both are built from.",
    )] = None,
) -> dict[str, Any]:
    """P3 — the bridge from outside-in to inside-out, and what makes this a TPRM module.

    A rating tells a buyer a number. This tells them what to ask, why, and what answer closes it.

        SIG Lite: ~300 fixed questions, generic basis, resolved by email thread.
        This pack: only what was observed failing, cited to a finding and an evidence id, with
                   the evidence standard stated up front and closure through the dispute path.

    ~80% OF THIS WAS ALREADY BUILT. `scoring.yaml` carries 58 `ask_of_vendor`, 58
    `accepts_as_refute` and 58 `recheck_after` entries — written when each band was written and
    read by nothing. The dispute half has adjudicated and re-scored since Phase 4. Two finished
    halves and no join, which is the same shape P1 was in.

    THE VALUE IS IN WHAT IS NOT ASKED. A pack scoped to a vendor's actual findings is answerable in
    an afternoon; a 300-question standard gets answered by an intern copying last year's.

    IT CHANGES NO SCORE. Answers travel back through the dispute path, which adjudicates, records
    the reason and re-scores — so a change to a published number always has a decision behind it.

    TWO RENDERINGS, ONE DATASET. `?view=procurement` tags each item blocking / condition /
    informational from severity × the Inherent Tier (E10b), because severity alone cannot say what
    a finding does to a DECISION — the same missing DMARC record is a footnote on a stationery
    supplier and a deal-stopper on the vendor holding production data. `?view=security` is the
    inbound worklist: by effective penalty, grouped by category so one person can take one domain,
    carrying dispute state so an item under adjudication is not chased twice. The default is the
    raw pack both are built from.
    """
    findings = store.findings_for_vendor(ref)
    if not findings:
        raise HTTPException(404, f"no findings for {ref!r} — POST /api/vendors/score first")
    pack = build_evidence_pack(ref, findings, get_scoring_config(),
                               disputes=store.accepted_dispute_targets(ref))

    if view == "security":
        return security_view(pack)
    if view == "procurement":
        profile = store.latest_profile(ref)
        firmographics = benchmarking_firmographics_of(store, ref)
        inherent = inherent_tier(profile.criticality if profile else None,
                                 firmographics.data_access_scope if firmographics else None,
                                 provisional=profile.inherent_provisional if profile else False)
        return procurement_view(pack, inherent.tier, inherent.basis)

    return {
        **evidence_pack_as_dict(pack),
        "views": {
            "procurement": f"/api/vendors/{ref}/evidence-request-pack?view=procurement",
            "security": f"/api/vendors/{ref}/evidence-request-pack?view=security",
        },
        "how_to_respond": (
            f"POST /api/vendors/{ref}/disputes with the signal, band and your evidence. An "
            f"accepted refute either nullifies the finding (it does not apply here) or marks it "
            f"mitigated (real, and evidenced as remediated), and the vendor is re-scored with the "
            f"reason recorded on the receipt."
        ),
    }


def _book_dependencies(store: Store) -> tuple[dict[str, list[Any]], dict[str, str | None]]:
    """Every vendor's fourth parties and criticality, in two queries rather than 2n.

    Fourth-party concentration is inherently a book-wide question — "how much of the estate rides
    on one provider" cannot be answered from one vendor's row — so both callers below need the
    whole book even when serving a single-vendor route. Built per-vendor, that was 146 evidence
    reads plus 146 profile reads against Neon, and it is most of why the portfolio view took the
    better part of a minute.
    """
    scores = store.latest_scores_all()
    raws = store.raw_by_source_all(fourth_party_sources)
    profiles = store.latest_profiles_all()
    deps = {s.vendor_ref: extract_from_raw(raws.get(s.vendor_ref) or {}) for s in scores}
    crit = {s.vendor_ref: (p.criticality if (p := profiles.get(s.vendor_ref)) else None)
            for s in scores}
    return deps, crit


def _spof_providers(store: Store, ref: str) -> list[str]:
    """Book-wide single points of failure that THIS vendor sits behind (P1).

    A PORTFOLIO FACT, WHICH IS WHY IT CANNOT COME FROM THE VENDOR'S OWN DEPENDENCY LIST. "Half the
    critical vendors in this book depend on the same provider" is not visible from inside one
    relationship, and that is exactly the risk it names.

    Degrades to an empty list rather than a 500: concentration is context beside a vendor's own
    record, and a portfolio query that fails must not take the record down with it. The same
    discipline `/api/portfolio` applies to its own block.
    """
    try:
        deps, crit = _book_dependencies(store)
        book = fourth_party_concentration(deps, crit)
        return [p.provider for p in book.single_points_of_failure if ref in p.dependent_vendors]
    except Exception:  # noqa: BLE001 — context, never worth the whole response
        log.warning("portfolio concentration unavailable for %r", ref, exc_info=True)
        return []


def _assessment_plan_of(store: Store, ref: str, soonest: str | None = None) -> dict[str, Any]:
    """P5's plan for this relationship, from the two client-declared inputs E10b already takes."""
    profile = _profile_of(store, ref)
    firmographics = benchmarking_firmographics_of(store, ref)
    inherent = inherent_tier(profile.criticality if profile else None,
                             firmographics.data_access_scope if firmographics else None,
                             provisional=profile.inherent_provisional if profile else False)
    return assessment_plan_as_dict(assessment_plan_for(inherent.tier), soonest)


@app.get("/api/vendors/{ref}/assessment-plan")
async def get_assessment_plan(ref: str, store: StoreDep) -> dict[str, Any]:
    """P5 — how much assessment this relationship warrants, and how often to repeat it.

    Effort matched to exposure. Today every vendor gets nineteen collectors and one staleness clock;
    a T4 supplier and the vendor holding production data cost the same to assess and are re-checked
    on the same day.

    TWO CLOCKS, PUBLISHED SEPARATELY AND NEVER AVERAGED. The review cadence tracks how much the
    RELATIONSHIP is worth reassessing (quarterly … passive) and moves when the contract moves. A
    finding's re-check date tracks one thing we FOUND (7d … 90d) and moves when the vendor's
    controls move. `next_action` returns the sooner and names which clock set it.

    A SCREENING-DEPTH PLAN PUBLISHES NO POSTURE, and says so before the run rather than leaving a
    reader to meet a refusal and read it as a finding about the vendor. Confidence is not rebased
    onto the chosen depth — it has to mean one thing across the whole book.

    UNDECLARED IS NOT T4. No declared inherent tier routes to FULL depth, because the relationships
    nobody has classified are disproportionately the ones nobody has looked at.
    """
    cfg = get_scoring_config()
    soonest = None
    for row in store.findings_for_vendor(ref):
        if row.effective_penalty > 0:
            soonest = soonest_recheck(
                soonest, (cfg.action_for(row.signal, row.band_key) or {}).get("recheck_after"))
    return {**_assessment_plan_of(store, ref, soonest), "published_table": assessment_depth_table()}


@app.get("/api/vendors/{ref}/contract-flowdowns")
async def get_contract_flowdowns(ref: str, store: StoreDep) -> dict[str, Any]:
    """P4 — findings become drafting points procurement can act on.

    P3 tells a vendor what to answer. This tells PROCUREMENT what to put in the contract if the
    answer does not close the gap. Six fixed observation families — no published incident-response
    route, unverifiable audit claims, a portfolio-level fourth-party single point of failure, a
    going-concern flag, thin evidence coverage, a KEV product-line match — each mapped to ONE
    suggested protection, argued over once in `contract_flowdowns.py` and held constant.

    SUGGESTED DRAFTING POINTS, NOT LEGAL ADVICE. This names a category of protection a lawyer would
    recognise; it does not draft clause language and never claims a vendor has agreed to anything.

    Fourth-party concentration is a PORTFOLIO fact (P1) — a single vendor's own dependency list
    cannot show it, so this degrades to no concentration row (never a 500) if the book-wide view is
    unavailable, the same discipline `/api/portfolio` applies to its own concentration block.
    """
    findings = store.findings_for_vendor(ref)
    if not findings:
        raise HTTPException(404, f"no findings for {ref!r} — POST /api/vendors/score first")
    score = store.latest_score(ref)
    continuity = continuity_report(ref, findings)
    spof_providers = _spof_providers(store, ref)

    flowdowns = flow_downs(
        ref, findings,
        continuity_flags=continuity.flags,
        spof_providers=spof_providers,
        ghost=bool(score.ghost) if score else False,
        thin_coverage=bool(score and score.confidence_band == "Low"),
        substitutability=getattr(_profile_of(store, ref), "substitutability", None),
    )
    return flowdowns_as_dict(ref, flowdowns)


@app.get("/api/vendors/{ref}/exit-readiness")
async def get_exit_readiness(ref: str, store: StoreDep) -> dict[str, Any]:
    """P8 — exit readiness and substitutability: what happens if this vendor has to go.

    `sole_source × poor Posture` is the single most useful procurement alert this system can
    raise — a critical dependency, no fallback, and weak observable controls, all at once.

    `substitutability` is CLIENT-DECLARED, never inferred — same path as `criticality`, set at
    `POST /api/vendors/score`. Switching cost, contractual lock-in and data portability are not
    observable from outside; this reports them as NOT DERIVABLE and points at the Evidence Request
    Pack rather than guessing.

    What public evidence CAN add: this vendor's own fourth-party dependencies (what technically
    travels with an exit, P1), the size of its peer cohort (evidence substitutes exist in the
    market, never evidence one is a functional replacement), and a going-concern flag (Continuity)
    if one is recorded — which turns "replaceable in principle" into "replace on a deadline".
    """
    profile = _profile_of(store, ref)
    score = store.latest_score(ref)
    if profile is None and score is None:
        raise HTTPException(404, f"no record for {ref!r} — POST /api/vendors/score first")

    posture = score.posture if (score and not score.blocked and not score.refused) else None

    providers: list[str] = []
    try:
        deps = fourth_party_extract(store.for_vendor(ref))
        providers = sorted({d.provider for d in deps})
    except Exception:  # noqa: BLE001 — context beside the alert, never worth the whole response
        log.warning("fourth-party dependencies unavailable for %r", ref, exc_info=True)

    cohort_peer_count: int | None = None
    if profile and profile.cohort:
        members = store.cohort_members(profile.cohort.key)
        cohort_peer_count = len([m for m in members if m[0] != ref])

    standing = None
    findings = store.findings_for_vendor(ref)
    if findings:
        standing = continuity_report(ref, findings).standing

    report = exit_readiness(
        ref,
        substitutability=profile.substitutability if profile else None,
        posture=posture,
        dependency_providers=providers,
        cohort_peer_count=cohort_peer_count,
        going_concern_standing=standing,
    )
    return exit_readiness_as_dict(report)


@app.get("/api/vendors/{ref}/residual-risk")
async def get_residual_risk(ref: str, store: StoreDep) -> dict[str, Any]:
    """E10b — the Residual Risk view procurement actually decides from.

    THREE THINGS, KEPT APART, AND THE SEPARATION IS THE POINT:

        Posture   — how strong the vendor looks. Ours to measure; moves when their TLS moves.
        Inherent  — how much THIS buyer stands to lose. Theirs to declare; moves when the
                    RELATIONSHIP moves, and not otherwise.
        Residual  — the published combination. A sixteen-cell lookup, not a third measurement.

    A RENDERING, NOT A SCORE. Nothing here is persisted and nothing feeds back into Posture. The
    moment a `residual` column exists it can drift from the two inputs it was derived from, and a
    reader has no way to tell which of the three is stale. Recomputed on every read.

    Both inherent inputs are CLIENT-SUPPLIED and neither is inferred: `criticality` from the vendor
    profile, `data_access_scope` from the v2 supplier attributes — where EB deliberately kept it
    out of cohort keying because it is a property of the relationship, and routed it to
    interpretation instead. This is the interpretation it routes to.
    """
    score = store.latest_score(ref)
    if score is None:
        raise HTTPException(404, f"no score for {ref!r} — POST /api/vendors/score first")

    profile = store.latest_profile(ref)
    firmographics = benchmarking_firmographics_of(store, ref)
    out = residual_risk(
        score.posture,
        profile.criticality if profile else None,
        firmographics.data_access_scope if firmographics else None,
        blocked=score.blocked, refused=score.refused,
        # P8 — a declared `sole_source` escalates the published tier one band. Disclosed on the
        # response via `escalated_from`, never absorbed into the cell.
        substitutability=profile.substitutability if profile else None,
        provisional=profile.inherent_provisional if profile else False,
    )
    return {
        "vendor_ref": ref,
        "published": out.published,
        "residual": out.residual,
        "residual_label": out.residual_label,
        "headline": out.headline(),
        "posture": out.posture,
        "posture_band": out.posture_band,
        "inherent": {
            "tier": out.inherent.tier,
            "label": out.inherent.label,
            "published": out.inherent.published,
            "criticality": out.inherent.criticality,
            "data_access_scope": out.inherent.data_access_scope,
            "basis": out.inherent.basis,
            # Declared on the inherent register but not yet confirmed by the relationship owner.
            # On the response rather than only in the prose, so a UI can badge it without parsing
            # a sentence.
            "provisional": out.inherent.provisional,
        },
        "matrix": residual_matrix(),
        # P8. `escalated_from` is the cell the matrix produced; `residual` is what is published
        # after the sole-source step. Both, always, so the lookup stays reconstructible.
        "substitutability": out.substitutability,
        "escalated_for_sole_source": out.escalated,
        "escalated_from": out.escalated_from,
        "reason": out.reason,
        "caveats": out.caveats,
        "advisory": "Residual risk is advisory. The client decides; this states what the evidence "
                    "and the declared exposure together support.",
    }


@app.get("/api/vendors/{ref}/assurity")
async def get_vendor_assurity(ref: str, store: StoreDep, sector: str | None = None
                              ) -> dict[str, Any]:
    """Assurity (E9a) + the Compliance Gap (E9c) — the assurance axis, never the security one.

    THE QUESTION THIS ANSWERS. *"How much independent assurance does this vendor actually have?"*
    A buyer needs it separately from posture, because "their TLS is current" and "an auditor has
    examined their controls" are different claims and a vendor can be strong on one and silent on
    the other. `synthetic_smallco` in the corpus is exactly that vendor: posture 97, assurity 13.

    ABSENCE NEVER SUBTRACTS. Until E2 the model charged 8 points for `cert_posture.none_claimed`,
    which fired on five of five real vendors — a tax on audit budget rather than a measure of risk,
    falling hardest on the small suppliers this product exists to assess fairly. E2 stopped the
    charging; this is the positive half, on its own axis so that credit for a trust page can never
    buy back points lost to an expired certificate.

    `sector` IS CLIENT-SUPPLIED AND SELECTS OBLIGATIONS ONLY. It picks which compliance frameworks
    apply. It cannot change what any observation is worth — that is the E1 correction, and it is
    enforced at the engine boundary by `test_sector_never_changes_a_severity`.
    """
    findings = store.findings_for_vendor(ref)
    if not findings:
        raise HTTPException(404, f"no findings for {ref!r} — POST /api/vendors/score first")

    gaps = compliance_gaps(ref, findings, sector=sector)
    # DISTINCT OBSERVATIONS, not gap count. A vendor asserting ISO 27001, SOC 2 and PCI DSS while
    # negotiating TLS 1.0 breaches three frameworks with one weakness; charging three times would
    # mean this axis punished a vendor for publishing more certifications, which is the opposite of
    # what it measures. All three gaps are still reported.
    report = assurity_report(ref, findings, compliance_gap_count=gaps.distinct_observations)
    return {
        "vendor_ref": ref,
        "assurity": report.score,
        "published": report.published,
        "observed_signals": report.observed_signals,
        "inputs": [
            {"signal": i.signal, "band": i.band_key, "credit": i.credit,
             "cited": i.cited(), "evidence_id": i.evidence_id}
            for i in report.inputs
        ],
        "compliance_gaps": [
            {"framework": g.framework, "framework_name": g.framework_name, "basis": g.basis,
             "applies_because": g.applies_because, "applies_detail": g.applies_detail,
             "signal": g.signal, "band": g.band_key, "observed": g.observed,
             "expectation": g.expectation, "cited": g.cited(), "evidence_id": g.evidence_id}
            for g in gaps.gaps
        ],
        "frameworks_considered": gaps.frameworks_considered,
        "caveats": report.caveats + gaps.caveats,
    }


@app.get("/api/vendors/{ref}/evidence")
async def list_evidence(ref: str, store: StoreDep) -> list[dict[str, Any]]:
    """Evidence receipts for a vendor — metadata only (raw omitted; fetch one for the body)."""
    rows = store.for_vendor(ref)
    if not rows:
        raise HTTPException(404, f"no evidence for {ref!r}")
    return [
        {"id": e.id, "source": e.source, "status": e.status,
         "fetched_at": e.fetched_at.isoformat(), "source_version": e.source_version,
         "reliability": e.reliability, "content_hash": e.content_hash}
        for e in rows
    ]


@app.get("/api/vendors/{ref}/evidence/{evidence_id}", response_model=Evidence)
async def get_evidence(ref: str, evidence_id: str, store: StoreDep) -> Evidence:
    """The receipt — the stored, hash-stamped raw record a finding was formed on (Finding A)."""
    ev = store.get(evidence_id)
    if ev is None or ev.vendor_ref != ref:
        raise HTTPException(404, f"no evidence {evidence_id!r} for {ref!r}")
    return ev


@app.get("/api/vendors/{ref}/findings", response_model=list[PersistedFinding])
async def list_findings(ref: str, store: StoreDep) -> list[PersistedFinding]:
    """The signal-level interpreted evidence behind a score — each observation, the severity and
    penalty the model assigned it, and the `evidence_id` of the raw receipt it came from. This is
    the per-signal audit trail (methodology Finding A): why every deduction happened, frozen at
    score time and hash-stamped, not re-derived. 404 when the vendor has not been scored yet."""
    rows = store.findings_for_vendor(ref)
    if not rows:
        raise HTTPException(404, f"no findings for {ref!r} — POST /api/vendors/score first")
    # Attach the plain-English reason for each deduction (scoring.yaml `reasons`), so the client
    # is told WHAT was wrong, not just how many points it cost.
    cfg = get_scoring_config()
    exempt = cfg.frequency_exempt_signals()
    for row in rows:
        row.reason = cfg.reason_for(row.signal, row.band_key)
        # ...and what to DO about it. Also served rather than stored, for the same reason the
        # reason is: the frozen fact is the band, the advice is presentation.
        act = cfg.action_for(row.signal, row.band_key) or {}
        row.action = act.get("action")
        row.ask_of_vendor = act.get("ask_of_vendor")
        row.recheck_after = act.get("recheck_after")
        row.accepts_as_refute = act.get("accepts_as_refute")
        row.frequency_amplified = row.occurrences > 1 and row.signal not in exempt
        # `row.dispute` is read straight from the stored finding — 'nullified'/'mitigated' when an
        # accepted refute changed it, so a discounted deduction shows why on the card.
    return rows


# --------------------------------------------------------------------- ai summary

@app.post("/api/vendors/{ref}/summary")
async def summarise_vendor(ref: str, store: StoreDep) -> dict[str, Any]:
    """AI digest of a vendor's finished record (opt-in read layer).

    Reads the already-published Score and its hash-stamped evidence receipts and returns a
    plain-English summary. It does NOT re-score and does NOT write to the evidence store — the
    summary is derived, marked AI-generated, and cites the receipts it was built from
    (methodology "the AI moment"). Returns 503 when no LLM is configured; 404 when the vendor
    has no score yet.
    """
    score = store.latest_score(ref)
    if score is None:
        raise HTTPException(404, f"no score for {ref!r} — POST /api/vendors/score first")
    evidence = store.for_vendor(ref)
    try:
        result = await summarise(score, evidence)
    except SummariserUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except SummariserError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"vendor_ref": ref, **result}


# --------------------------------------------------------------------- gap analysis (E14)


def _gap_analysis_inputs(store: Store, ref: str) -> tuple[Score, VendorProfile | None, Any, str | None]:
    """The four things every gap-analysis route needs before it can even check the gate:
    the score, the profile, firmographics, and the inherent tier those two resolve to."""
    score = store.latest_score(ref)
    if score is None:
        raise HTTPException(404, f"no score for {ref!r} — POST /api/vendors/score first")
    profile = _profile_of(store, ref)
    firmographics = benchmarking_firmographics_of(store, ref)
    inherent = inherent_tier(
        profile.criticality if profile else None,
        firmographics.data_access_scope if firmographics else None,
        provisional=profile.inherent_provisional if profile else False,
    )
    return score, profile, firmographics, inherent.tier


@app.get("/api/vendors/{ref}/gap-analysis/gate")
async def get_gap_analysis_gate(ref: str, store: StoreDep) -> dict[str, Any]:
    """Whether the "Generate Gap Analysis" button may be pressed, and why not when it may not.

    NEVER SILENTLY ABSENT, NEVER ENABLED-BUT-USELESS (E14 placement/gating) — the page calls this
    to render the button disabled with a stated reason, rather than letting a 404/409 from the
    generate call itself be the first the analyst hears of it.
    """
    score = store.latest_score(ref)
    profile = _profile_of(store, ref)
    firmographics = benchmarking_firmographics_of(store, ref)
    inherent = inherent_tier(
        profile.criticality if profile else None,
        firmographics.data_access_scope if firmographics else None,
        provisional=profile.inherent_provisional if profile else False,
    )
    result = gap_analysis_gate(score=score, inherent_tier=inherent.tier)
    return {
        "vendor_ref": ref, "allowed": result.allowed, "reasons": result.reasons,
        "inherent_tier": inherent.tier, "inherent_tier_provisional": inherent.provisional,
    }


@app.post("/api/vendors/{ref}/gap-analysis", status_code=201)
async def create_gap_analysis(ref: str, store: StoreDep) -> dict[str, Any]:
    """Generate a gap analysis — a third audience view whose renderer is a language model, over a
    finished record it never adjusts. See `app/gap_analysis.py` for the full design.

    NOTHING HERE REACHES A VENDOR SCORE: every input is COPIED from the module that already owns
    it (the same discipline `audience_views.py` follows for P6), and the model is never asked for
    a number. Returns 409 with the stated reason when a gate condition is not met, 503 when no
    provider is configured or every configured provider failed on transport grounds.
    """
    score, profile, firmographics, inherent = _gap_analysis_inputs(store, ref)
    gate_result = gap_analysis_gate(score=score, inherent_tier=inherent)
    if not gate_result.allowed:
        raise HTTPException(409, "; ".join(gate_result.reasons))

    cfg = get_scoring_config()
    findings = store.findings_for_vendor(ref)
    disputes = store.accepted_dispute_targets(ref)
    rows: list[dict[str, Any]] = []
    for row in findings:
        act = cfg.action_for(row.signal, row.band_key) or {}
        rows.append({
            **row.model_dump(mode="json"),
            "action": act.get("action"),
            "ask_of_vendor": act.get("ask_of_vendor"),
            "recheck_after": act.get("recheck_after"),
            "accepts_as_refute": act.get("accepts_as_refute"),
            "dispute_status": disputes.get((row.signal, row.band_key)),
        })

    coverage = _coverage_for(store, ref, score)
    sector = profile.sector.value if profile and profile.sector else None
    gaps_report = compliance_gaps(ref, findings, sector=sector, cfg=cfg)
    assurity = assurity_report(ref, findings, compliance_gap_count=gaps_report.distinct_observations, cfg=cfg)
    continuity = continuity_report(ref, findings)
    expectation_gap = _expectation_gap_or_none(store, ref, score)
    substitutability = profile.substitutability if profile else None
    residual = residual_risk(
        score.posture, profile.criticality if profile else None,
        firmographics.data_access_scope if firmographics else None,
        blocked=score.blocked, refused=score.refused,
        substitutability=substitutability,
        provisional=profile.inherent_provisional if profile else False,
    )
    spof = _spof_providers(store, ref)
    soonest = None
    for row in findings:
        if row.effective_penalty > 0:
            soonest = soonest_recheck(soonest, (cfg.action_for(row.signal, row.band_key) or {}).get("recheck_after"))
    plan = _assessment_plan_of(store, ref, soonest)

    context = build_gap_analysis_context(
        vendor_ref=ref, profile=profile, score=score, findings=rows,
        penalty_divisor=cfg.penalty_divisor(), coverage_statement=coverage,
        assurity=assurity, continuity=continuity, compliance_gap=gaps_report,
        expectation_gap=expectation_gap, residual=residual, concentration=spof,
        assessment_plan=plan,
    )

    try:
        result = await generate_gap_analysis(context)
    except GapAnalysisUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except GapAnalysisExhausted as exc:
        raise HTTPException(503, str(exc)) from exc

    record = GapAnalysisRecord(
        id=uuid.uuid4().hex, vendor_ref=ref,
        provider=result["provenance"]["provider"], model=result["provenance"]["model"],
        prompt_version=result["provenance"]["prompt_version"],
        context_hash=result["provenance"]["context_hash"],
        executive_summary=result["executive_summary"], gaps=result["gaps"],
        recommendations=result["recommendations"], limitations=result["limitations"],
        dropped_evidence_ids=result["dropped_evidence_ids"],
    )
    store.put_gap_analysis(record)

    return {
        "id": record.id, "vendor_ref": ref, "executive_summary": record.executive_summary,
        "gaps": record.gaps, "recommendations": record.recommendations,
        "limitations": record.limitations, "provenance": result["provenance"],
        "dropped_evidence_ids": record.dropped_evidence_ids,
        "parse_warning": result.get("parse_warning"),
        "inherent_tier": inherent, "inherent_tier_provisional": (
            profile.inherent_provisional if profile else False
        ),
        "ai_generated": True,
    }


@app.get("/api/vendors/{ref}/gap-analysis/history")
async def get_gap_analysis_history(ref: str, store: StoreDep) -> dict[str, Any]:
    """Every gap analysis generated for this vendor, newest first, each with its recommendations'
    current accept/edit/reject state — the full trail, not just the latest generation."""
    records = store.gap_analysis_history(ref)
    out = []
    for r in records:
        events = store.gap_analysis_events(r.id)
        latest_by_index: dict[int, GapAnalysisRecommendationEvent] = {}
        for e in events:   # oldest-first, so the last write wins
            latest_by_index[e.rec_index] = e
        out.append({
            "id": r.id, "provider": r.provider, "model": r.model,
            "prompt_version": r.prompt_version, "context_hash": r.context_hash,
            "executive_summary": r.executive_summary, "gaps": r.gaps,
            "recommendations": [
                {
                    **rec,
                    "status": (latest_by_index[i].event if i in latest_by_index else "pending"),
                    "edited_text": (
                        latest_by_index[i].edited_text if i in latest_by_index
                        and latest_by_index[i].event == "edited" else None
                    ),
                }
                for i, rec in enumerate(r.recommendations)
            ],
            "limitations": r.limitations, "dropped_evidence_ids": r.dropped_evidence_ids,
            "created_at": r.created_at.isoformat(),
        })
    return {"vendor_ref": ref, "analyses": out}


class GapAnalysisRecommendationAction(BaseModel):
    """An analyst's disposition of ONE recommendation on ONE generated analysis."""

    action: GapAnalysisEventKind
    edited_text: str | None = Field(
        default=None, description="the analyst's rewrite — required when action = 'edited'"
    )
    actor: str | None = Field(default=None, description="who recorded it — role or name, client-supplied")
    note: str | None = None

    @model_validator(mode="after")
    def _edit_requires_text(self) -> "GapAnalysisRecommendationAction":
        if self.action == "edited" and not (self.edited_text and self.edited_text.strip()):
            raise ValueError("action='edited' requires edited_text")
        return self


@app.post("/api/vendors/{ref}/gap-analysis/{analysis_id}/recommendations/{rec_index}", status_code=201)
async def record_gap_analysis_recommendation_event(
    ref: str, analysis_id: str, rec_index: int, req: GapAnalysisRecommendationAction, store: StoreDep,
) -> dict[str, Any]:
    """Accept, edit or reject ONE recommendation. Append-only: a rejection is recorded, never
    deleted, and an edit keeps the model's original alongside the analyst's rewrite — "the analyst
    agreed" and "the analyst rewrote it" are different facts about whether this feature works, and
    only one of them is a good result (see `acceptance rate` in `app/program_kpis.py`).
    """
    record = store.get_gap_analysis(analysis_id)
    if record is None or record.vendor_ref != ref:
        raise HTTPException(404, f"no gap analysis {analysis_id!r} for {ref!r}")
    if rec_index < 0 or rec_index >= len(record.recommendations):
        raise HTTPException(422, f"analysis {analysis_id!r} has no recommendation at index {rec_index}")

    event = GapAnalysisRecommendationEvent(
        id=uuid.uuid4().hex, analysis_id=analysis_id, vendor_ref=ref, rec_index=rec_index,
        event=req.action, edited_text=req.edited_text if req.action == "edited" else None,
        actor=req.actor, note=req.note,
    )
    store.put_gap_analysis_event(event)
    return {
        "analysis_id": analysis_id, "rec_index": rec_index, "status": event.event,
        "edited_text": event.edited_text, "recorded_at": event.created_at.isoformat(),
        "recommendation": record.recommendations[rec_index],
        "note": "recorded as a new event; the original recommendation and every prior event remain readable",
    }


# --------------------------------------------------------------------- adjudication

@app.get("/api/adjudications/queue")
async def adjudication_queue(store: StoreDep) -> dict[str, Any]:
    """Every blocked record, with the facts needed to decide it on the page.

    `blocked_pending_adjudication` counts this queue; until this route there was nothing that
    showed it. That gap is the mechanism behind the failure the sanctions review named: a queue
    nobody can work quickly gets cleared without being read, and a rubber-stamped s 16(7) record
    is worse than none because it is a statutory defence resting on a decision nobody made.

    Each row carries what matched, at what strength, whether the listed party is an entity or a
    natural person, which list it came from, and whether the query is an ordinary English word or a
    coined name — the fact that settles most sanctions rows in one glance.

    IT CLEARS NOTHING. Ordering is by inherent exposure rather than by how weak the evidence looks,
    because a queue sorted weakest-first reads as a recommendation to clear from the top.
    """
    return adjudication_queue_as_dict(build_adjudication_queue(store))


@app.post("/api/adjudications/{ref}")
async def adjudicate(ref: str, req: AdjudicationRequest,
                     store: StoreDep) -> dict[str, Any]:
    """Record a human decision on a BLOCKED gate (sanctions / ambiguous entity).

    PoC scope: the decision is validated and echoed as the adjudication record. The gate
    itself stays human by design — s 16(7) makes the adjudication the evidence (§5.5.1) — so
    a full flow re-runs scoring with the cleared gate and writes a NEW immutable Score; that
    re-score wiring is the platform build. Here we surface the current state and the decision.
    """
    if req.decision not in {"cleared", "upheld"}:
        raise HTTPException(422, "decision must be 'cleared' or 'upheld'")
    score = store.latest_score(ref)
    if score is None or not score.blocked:
        raise HTTPException(409, f"{ref!r} has no BLOCKED score to adjudicate")
    return {
        "vendor_ref": ref, "decision": req.decision, "note": req.note,
        "adjudicator": req.adjudicator,
        "blocked_reason": score.blocked_reason,
        "recorded": True,
        "next": "re-score with the gate cleared (platform build) writes a new immutable Score",
    }


@app.get("/api/disclosures")
async def get_disclosures() -> dict[str, Any]:
    """Limits, coverage gaps and attribution — served so the card and the evidence pack cannot
    drift apart. Two of these are obligations rather than editorial choices: the NVD notice is
    required wording, and HIBP's licence requires attribution wherever its data appears."""
    return disclosure_block()


# --------------------------------------------------------------------- disputes (Phase 4)

@app.post("/api/vendors/{ref}/disputes", status_code=201)
async def submit_dispute(ref: str, req: DisputeRequest, store: StoreDep) -> dict[str, Any]:
    """A vendor (or an analyst on their behalf) contests a specific finding with evidence.

    Outside-in scoring cannot see compensating controls, so it over-penalises — and both benchmarked
    platforms accept evidenced refutes for exactly this reason. Submitting creates a PENDING dispute;
    it changes no score. A human adjudicates it, and only an ACCEPTED refute re-scores.

    Validated against the CURRENT findings: you cannot dispute a finding that is not on the card. A
    dispute keyed to an observation that isn't there would be noise that never applies.
    """
    charged = [f for f in store.findings_for_vendor(ref)
               if f.signal == req.signal and f.band_key == req.band_key and f.effective_penalty > 0]
    if not charged:
        raise HTTPException(
            409, f"no penalising finding {req.signal}/{req.band_key} on {ref!r} to dispute — "
                 "the card must show it before it can be contested")

    dispute_id = uuid.uuid4().hex
    event = Dispute(
        id=uuid.uuid4().hex, dispute_id=dispute_id, vendor_ref=ref, event="submitted",
        signal=req.signal, band_key=req.band_key, kind=req.kind, evidence=req.evidence,
        actor=req.submitted_by, note=None, content_hash="",
    )
    store.put_dispute(event)
    return {"dispute_id": dispute_id, "status": "submitted", "kind": req.kind,
            "signal": req.signal, "band_key": req.band_key,
            "next": "a human adjudicates; only an accepted refute re-scores"}


@app.post("/api/disputes/{dispute_id}/adjudicate")
async def adjudicate_dispute(dispute_id: str, req: DisputeDecision,
                             store: StoreDep) -> dict[str, Any]:
    """Human decision on a dispute. Accept -> re-score with the refute applied; reject -> recorded.

    On accept the vendor is re-scored through the ordinary pipeline, which now sees the accepted
    refute and applies it (nullify -> penalty 0, mitigate -> ×0.6). A NEW immutable Score is
    written; the original stays readable. Nothing is edited — the acceptance is a new event, the
    re-score a new row, and the whole chain is auditable (Finding A)."""
    if req.decision not in ("accept", "reject"):
        raise HTTPException(422, "decision must be 'accept' or 'reject'")
    current = store.latest_dispute_event(dispute_id)
    if current is None:
        raise HTTPException(404, f"no dispute {dispute_id!r}")
    if current.event in ("accepted", "rejected"):
        raise HTTPException(409, f"dispute {dispute_id!r} is already {current.event}")

    event_name = "accepted" if req.decision == "accept" else "rejected"
    store.put_dispute(Dispute(
        id=uuid.uuid4().hex, dispute_id=dispute_id, vendor_ref=current.vendor_ref,
        event=event_name, signal=current.signal, band_key=current.band_key, kind=current.kind,
        evidence=current.evidence, actor=req.adjudicator, note=req.note, content_hash="",
    ))

    rescored = None
    if event_name == "accepted":
        vendor = _vendor_from_store(store, current.vendor_ref)
        if vendor is None:
            raise HTTPException(409, "cannot re-score: no stored evidence to reconstruct the vendor")
        result = await run_pipeline(vendor, store=store)
        rescored = {"posture": result.score.posture, "grade": result.score.grade,
                    "critical_ceiling_applied": result.score.critical_ceiling_applied}

    return {"dispute_id": dispute_id, "status": event_name,
            "signal": current.signal, "band_key": current.band_key, "kind": current.kind,
            "rescored": rescored,
            "note": "the original score and every dispute event remain readable; nothing was edited"}


@app.get("/api/vendors/{ref}/disputes")
async def list_disputes(ref: str, store: StoreDep) -> dict[str, Any]:
    """Every dispute for a vendor, with its current state and full event history."""
    events = store.disputes_for_vendor(ref)
    by_id: dict[str, list[Dispute]] = {}
    for e in events:
        by_id.setdefault(e.dispute_id, []).append(e)
    disputes = []
    for did, evs in by_id.items():
        latest = evs[-1]
        disputes.append({
            "dispute_id": did, "status": latest.event, "kind": latest.kind,
            "signal": latest.signal, "band_key": latest.band_key, "evidence": latest.evidence,
            "history": [{"event": e.event, "actor": e.actor, "note": e.note,
                         "at": e.created_at.isoformat()} for e in evs],
        })
    return {"vendor_ref": ref, "disputes": disputes,
            "accepted": [f"{s}/{b}" for (s, b) in store.accepted_dispute_targets(ref)]}


# --------------------------------------------------------------------- decisions (Phase 6)

@app.post("/api/vendors/{ref}/decisions", status_code=201)
async def record_decision(ref: str, req: DecisionRequest, store: StoreDep) -> dict[str, Any]:
    """Record a buyer's decision on a vendor — approve / conditional / reject.

    The decision is stored ALONGSIDE the score, never inside it: it emits no finding and moves no
    penalty, so recording 'approved' changes the posture by exactly nothing. It is stamped with the
    posture and grade AS AT this moment, so the decision stays reconstructible against the number it
    was actually made on, even after a later re-score. A change of mind is a NEW decision, not an
    edit — the whole decision history for a vendor is auditable.
    """
    if req.decision == "conditional" and not (req.conditions and req.conditions.strip()):
        raise HTTPException(422, "a conditional decision must state its conditions")

    score = store.latest_score(ref)
    if score is None:
        raise HTTPException(409, f"no score for {ref!r} — a decision must be made against a score")

    decision = Decision(
        id=uuid.uuid4().hex, vendor_ref=ref, decision=req.decision,
        conditions=req.conditions, actor=req.decided_by,
        posture_at=score.posture, grade_at=score.grade,
    )
    store.put_decision(decision)
    return {"id": decision.id, "vendor_ref": ref, "decision": decision.decision,
            "conditions": decision.conditions, "posture_at": decision.posture_at,
            "grade_at": decision.grade_at, "recorded_at": decision.created_at.isoformat(),
            "note": "recorded alongside the score; it changed no number"}


@app.get("/api/vendors/{ref}/decisions")
async def list_decisions(ref: str, store: StoreDep) -> dict[str, Any]:
    """Every decision recorded for a vendor, newest first — the current call plus its full history."""
    decisions = [
        {"id": d.id, "decision": d.decision, "conditions": d.conditions, "actor": d.actor,
         "posture_at": d.posture_at, "grade_at": d.grade_at, "at": d.created_at.isoformat()}
        for d in store.decisions_for_vendor(ref)
    ]
    return {"vendor_ref": ref, "current": decisions[0] if decisions else None,
            "history": decisions}


def _vendor_from_store(store: Store, ref: str) -> Vendor | None:
    """Reconstruct the Vendor (ref + domain) from stored evidence, for a re-score.

    The domain isn't persisted on its own, but every domain-scoped collector records it in `raw`.
    Reading it back lets an accepted dispute trigger a fresh, deterministic re-score without the
    caller having to re-supply what the system already knows."""
    domain = None
    for e in store.for_vendor(ref):
        if e.raw and isinstance(e.raw.get("domain"), str):
            domain = e.raw["domain"]
            break
    if domain is None:
        return None
    return Vendor(ref=ref, domain=domain, resolved=True, resolution_confidence=1.0)


# --------------------------------------------------------------------- portfolio (Phase 6)
# Per-vendor score history is already served by GET /api/vendors/{ref}/history (returns the full
# append-only list[Score]); the trend UI derives its posture sparkline from that. This block adds
# the percentile trend and the book-wide aggregate view.

@app.get("/api/vendors/{ref}/benchmark-history")
async def get_benchmark_history(ref: str, store: StoreDep) -> dict[str, Any]:
    """Where this vendor stood among its peers over time — the percentile trend, oldest first.

    Each point was frozen at a score run against the cohort that existed THEN, so "bottom quartile
    three quarters running" is legible in a way a single read-time percentile never is. Points where
    the cohort was too thin are returned with available=false, not dropped — an honest gap in the
    line is better than a fabricated continuation of it.
    """
    points = [
        {"at": s.created_at.isoformat(), "available": s.available, "percentile": s.percentile,
         "percentile_resolution": s.percentile_resolution, "quartile": s.quartile,
         "peer_n": s.peer_n, "posture": s.posture, "cohort_key": s.cohort_key, "level": s.level}
        for s in store.benchmark_history(ref)
    ]
    return {"vendor_ref": ref, "points": points,
            "with_percentile": sum(1 for p in points if p["available"])}


@app.get("/api/portfolio")
async def get_portfolio(store: StoreDep) -> dict[str, Any]:
    """The whole book at a glance — every vendor's latest score, plus concentration metrics.

    A single-vendor scorecard answers "is this one safe?"; a risk manager or CISO also needs "where
    is my exposure across the book?" — how many critical-dependency vendors sit low, how the grades
    distribute, what is blocked awaiting adjudication. Every row is the SAME immutable score object
    the scorecard renders; this view only aggregates and never recomputes a number.

    Criticality is the buyer's own client-supplied dependency rating (never inferred), so the
    concentration that matters most — a low posture on a vendor you depend on heavily — can only be
    computed where the buyer has supplied it. Vendors without a criticality are counted, not hidden.
    """
    scores = store.latest_scores_all()
    # One query for every profile in the book. This was `_profile_of` per vendor — 146 sequential
    # round trips to Neon before a single row could be rendered.
    profiles = store.latest_profiles_all()
    rows: list[dict[str, Any]] = []
    by_grade: dict[str, int] = {}
    by_criticality: dict[str, int] = {}
    concentration: list[dict[str, Any]] = []
    blocked = refused = ghosts = below_60 = 0

    for s in scores:
        profile = profiles.get(s.vendor_ref)
        criticality = profile.criticality if profile else None
        sector = profile.sector.value if profile and profile.sector else None
        row = {
            "vendor_ref": s.vendor_ref,
            "posture": s.posture,
            "grade": s.grade,
            "confidence": s.overall_confidence,
            "confidence_band": s.confidence_band,
            "ghost": s.ghost,
            "blocked": s.blocked,
            "refused": s.refused,
            "criticality": criticality,
            "sector": sector,
        }
        rows.append(row)

        if s.blocked:
            blocked += 1
        if s.refused:
            refused += 1
        if s.ghost:
            ghosts += 1
        if s.grade:
            by_grade[s.grade] = by_grade.get(s.grade, 0) + 1
        if criticality:
            by_criticality[criticality] = by_criticality.get(criticality, 0) + 1
        # The board-level number: a vendor the buyer depends on heavily AND that scores low. Not
        # "low score" alone — a low score on a vendor you barely use is not where exposure lives.
        if s.posture is not None and s.posture < 60:
            below_60 += 1
            if criticality == "high":
                concentration.append({"vendor_ref": s.vendor_ref, "posture": s.posture,
                                       "grade": s.grade, "sector": sector})

    rows.sort(key=lambda r: (r["posture"] is None, r["posture"] if r["posture"] is not None else 0))
    concentration.sort(key=lambda c: c["posture"])
    # P1 — FOURTH-PARTY CONCENTRATION. `fourth_party.extract` has enumerated providers per vendor
    # since Phase 2 and its own docstring says the finding that matters is a PORTFOLIO statement.
    # This route meanwhile shipped a field called `concentration` that was only high-criticality
    # vendors below 60 and never called the extractor once: two correct halves, one misleading
    # label, no join. The old field is kept under its accurate name below.
    #
    # Degrades alone — a book-wide view must not 500 because one vendor's evidence is malformed.
    fourth_party: dict[str, Any] = {}
    try:
        raws = store.raw_by_source_all(fourth_party_sources)
        deps = {s.vendor_ref: extract_from_raw(raws.get(s.vendor_ref) or {}) for s in scores}
        crit = {r["vendor_ref"]: r["criticality"] for r in rows}
        fourth_party = concentration_as_dict(fourth_party_concentration(deps, crit))
    except Exception:  # noqa: BLE001 — context beside the book, never worth the whole view
        log.warning("fourth-party concentration unavailable", exc_info=True)

    return {
        "total": len(rows),
        "summary": {
            "by_grade": by_grade,
            "by_criticality": by_criticality,
            "blocked": blocked,
            "refused": refused,
            "ghosts": ghosts,
            "below_60": below_60,
            "high_criticality_below_60": len(concentration),
            "single_points_of_failure": len(fourth_party.get("single_points_of_failure") or []),
        },
        # RENAMED, deliberately. This was published as `concentration` and is not concentration —
        # it is weak scores on depended-on vendors, which is a different and also useful finding.
        # Leaving the old name on it is what let the real thing go unbuilt for two phases.
        "weak_critical_vendors": concentration,
        "concentration": concentration,   # DEPRECATED alias, removed one release from now
        "fourth_party_concentration": fourth_party,
        "vendors": rows,
        "caveats": [
            "Every row is the vendor's latest immutable score; this view aggregates, it never "
            "recomputes.",
            "`weak_critical_vendors` is high-dependency vendors scoring below 60. Criticality is "
            "the buyer's client-supplied rating — vendors without one cannot enter that count.",
            "`fourth_party_concentration` is the different question: how much of the book rides on "
            "ONE provider. No per-vendor score can express it — all nine vendors on one identity "
            "provider may score an A — and it is disclosed, never scored.",
            "A Ghost is unassessed, not safe: read its confidence, not its grade.",
        ],
    }


# --------------------------------------------------------------------- P9 · the programme itself


@app.get("/api/program/maturity")
async def get_program_maturity() -> dict[str, Any]:
    """P9 — how good is OUR TPRM PROGRAMME, which is a different question from every other route.

    Every other endpoint answers something about a VENDOR. This one answers something about us:
    eight dimensions, each scored 1-5 against what this codebase actually does, with a written
    rationale and the specific thing in the tree that justifies the level.

    A SELF-ASSESSMENT, NOT A COMPUTED SCORE. There is deliberately no formula — a maturity level
    derived by arithmetic would carry a precision the underlying judgements do not have.

    THE OVERALL LEVEL IS THE MINIMUM, NEVER THE AVERAGE. A programme is not "Managed overall"
    because three dimensions are and five are not; an average lets strength where we are naturally
    strong conceal the dimension that will fail an audit. The current answer is Level 2, and the
    value of this route is entirely in the dimensions holding it there.

    Takes no vendor and reads no store: it is a statement about the programme, and a maturity level
    that varied by which vendor you asked about would be measuring the wrong thing.
    """
    return maturity_as_dict()


@app.get("/api/program/kpis")
async def get_program_kpis(store: StoreDep) -> dict[str, Any]:
    """P9 — fifteen metrics, twelve computed from the store and three that have no OSINT source.

    A `manually-supplied` metric with nothing supplied renders as `null` with its owner named. It is
    NEVER backfilled, estimated or defaulted to make the dashboard look complete: an empty cell asks
    a question, and a plausible number answers it wrongly.

    Three metrics were chosen because the programme is currently bad at them — tier declaration
    rate, blocked-adjudication queue depth, and overdue re-checks. A dashboard whose every metric is
    green is measuring the wrong things.

    Fourth-party concentration is passed in from P1's portfolio query rather than recomputed, so
    this module cannot become a second source of truth about the same number.
    """
    spof = None
    try:
        deps, crit = _book_dependencies(store)
        spof = len(fourth_party_concentration(deps, crit).single_points_of_failure)
    except Exception:  # noqa: BLE001 - one metric never takes the dashboard down
        log.warning("portfolio concentration unavailable for the KPI dashboard", exc_info=True)

    return kpis_as_dict(compute_kpis(store, spof_count=spof))


@app.get("/api/program/monitoring")
async def get_monitoring(store: StoreDep, runs: int = 10) -> dict[str, Any]:
    """Is continuous monitoring actually happening — and what drifted when it last ran?

    A DIFFERENT QUESTION FROM `monitoring_currency`, which is the point. Currency reports the share
    of the book inside its P5 interval, and that figure can read 100% on a schedule that died in
    March: nothing is re-scored into staleness because nothing is re-scored at all. This route
    reads the append-only run ledger, where **silence is the alarm condition**.

    `recent_runs` carries the retained drift reports P9's Continuous Monitoring dimension asks for.
    A log line that rotates is not a retained report.
    """
    return {
        "health": monitoring_health(store),
        "recent_runs": recent_runs(store, limit=runs),
        "schedule": {
            "installed_outside_this_repository": True,
            "artefacts": "ops/schedule/ — cron, systemd timer, Windows Scheduled Task",
            "entrypoint": "python -m app.scheduler --run",
            "health_check": "python -m app.scheduler --health  (exits 1 when the schedule is dead)",
            "note": ("The schedule is deliberately not in the application. Which host runs the "
                     "sweep, at what hour, under whose credentials, and who is paged when it stops "
                     "are operational decisions, and burying them in Python hides them from the "
                     "people who own them."),
        },
    }


@app.get("/api/program/estate-readiness")
async def get_estate_readiness(store: StoreDep) -> dict[str, Any]:
    """E12 — is the estate fan-out worth switching on, and at what cap? Measured on every read.

    `estate.probe_cap` has shipped at 1 since E12 was built, on the grounds that raising it is a
    capacity decision. The measurement says otherwise: the fan-out's input is certificate
    transparency, and CT availability is the binding constraint, not probe budget. This route is
    the standing instrument, so the answer is re-derived rather than remembered.

    Two conditions gate READY, and the second is non-compensatory: enough of the book must be able
    to produce the signal, AND no vendor publishing a posture today may stop publishing one. A
    vendor going dark is the loss of the number, not a worse number.
    """
    return estate_readiness_as_dict(measure_estate_readiness(store))


@app.get("/api/program")
async def get_program(store: StoreDep) -> dict[str, Any]:
    """Both halves of P9 on one page — the maturity self-assessment and the KPI dashboard.

    Served together because that is how a sponsor reads them: the maturity level says where the
    programme is weak, and the metrics say by how much. Neither is recomputed here.
    """
    return {
        "maturity": maturity_as_dict(),
        "inventory": await get_inventory(store),
        "monitoring": await get_monitoring(store),
        "adjudication_queue": await adjudication_queue(store),
        "estate_readiness": await get_estate_readiness(store),
        "kpis": await get_program_kpis(store),
        "note": ("P9 answers a different question from every other route in this API: not 'how is "
                 "this vendor doing' but 'how good is our programme'. Nothing on this page reaches "
                 "any vendor score."),
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    from .summariser import available as summary_available

    return {"status": "ok", "version": app.version, "summary_enabled": summary_available()}


def _require_job(job_id: str) -> Job:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(404, f"no job {job_id!r}")
    return job
