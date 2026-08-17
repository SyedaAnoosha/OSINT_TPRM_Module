"""The scoring pipeline — one async function the API and the harness both call.

Runs the non-negotiable order (methodology §5.1, scoring.yaml PIPELINE ORDER):
    entity-resolution -> collect (parallel, failure-isolated) -> EVIDENCE STORE (first)
    -> normalize -> score -> persist Score

Two things this module is careful about:
  * **Evidence is written BEFORE scoring**, per collector, as each result lands — the store
    is the legal artefact (Finding A) and must exist independent of whether scoring succeeds.
  * **Collectors run concurrently but results are consumed one at a time** (`as_completed`),
    so the synchronous evidence store is never written from two places at once, and progress
    can be streamed to the caller (SSE) as each source finishes — "speed to answer" (Phase 3).

The engine owns the gates (sanctions / ambiguous entity) and the knockout floor, so the
pipeline stays dumb: resolve, collect, store, score, persist.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from typing import Any

import httpx

from .assessment_depth import Depth, sources_for_depth
from .benchmark import build_benchmark, peer_lookup
from .collectors import all_collectors
from .collectors.base import CollectorContext
from .collectors.estate import build_estate
from .collectors.estate_collector import EstateCollector
from .config import get_settings
from .entity_resolution import assess as assess_resolution
from .logging_config import get_logger
from .models import BenchmarkSnapshot, CollectorResult, Criticality, SizeBand, Substitutability, Vendor
from .profile import build_profile
from .ratelimit import RateLimiter
from .scoring import ScoringEngine
from .scoring.engine import ScoreResult
from .scoring.log_odds import PeerContext, peer_context
from .scoring_config import get_scoring_config
from .storage import Store, get_store

log = get_logger("pipeline")

# progress(event_name, payload) — may be sync or async; awaited if it returns an awaitable.
Progress = Callable[[str, dict[str, Any]], Any]


# TLDs offered as candidates for a bare-name query, most-likely first. We do NOT pick one —
# the user confirms. A real resolver (e.g. Wikidata P856) is the roadmap upgrade.
_CANDIDATE_TLDS = ("com", "io", "co", "ai", "net", "org")


def domain_candidates(name: str) -> list[str]:
    """Plausible domains for a bare company name — a LIST to show the user, never an
    auto-pick. We deliberately do not guess a single domain: most collectors are
    domain-driven, and silently assessing the wrong `<slug>.com` would attribute one
    company's posture to another. The user chooses (or types the real domain); only then do
    we analyse (methodology: no inference under uncertainty)."""
    slug = re.sub(r"[^a-z0-9]", "", name.lower())
    if not slug:
        return []
    return [f"{slug}.{tld}" for tld in _CANDIDATE_TLDS]


def resolve_vendor(
    *, name: str | None = None, domain: str | None = None, ref: str | None = None,
    entity_confidence: float | None = None,
) -> Vendor:
    """First-pass entity resolution: derive the ref slug.

    Resolution CONFIDENCE is deliberately left `None` here. It cannot be known before the
    registries have answered, and defaulting it to 1.0 is what left the ambiguity gate inert —
    an assumption of certainty dressed as a measurement. `run_pipeline` fills it after collection
    via `entity_resolution.assess`. Pass `entity_confidence` only to OVERRIDE that (tests, or a
    human adjudicator's decision).

    It does NOT infer a domain from a name. A name-only vendor keeps `domain=None`; the API
    stops before scoring and asks the caller to supply/confirm a domain (see
    `domain_candidates`). Guessing a domain and scoring it silently is the one shortcut this
    system refuses — it would risk assessing the wrong company."""
    if not name and not domain:
        raise ValueError("need a name or a domain to resolve a vendor")
    slug = ref or (domain.split(".")[0] if domain else (name or "unknown")).lower()
    return Vendor(ref=slug, name=name, domain=domain,
                  resolved=True, resolution_confidence=entity_confidence, operating_years=None)


def _resolve_estate(vendor: Vendor, results: list[CollectorResult]) -> Any:
    """E12. Turn the CT result into a sampled, tenant-filtered host set — or None.

    NONE IS A REAL ANSWER and every caller must treat it as apex-only. It means one of: the probe
    cap is 1 (the shipped default), CT returned nothing, or the CT collector failed. None is
    deliberately not an empty sample, because *"we did not fan out"* and *"we fanned out and found
    nothing"* are different facts and only the second says anything about the vendor.

    LIVENESS IS NOT RESOLVED HERE. The design record puts it before sampling, and it belongs
    before sampling — but resolving several hundred names is itself a fan-out with its own budget,
    and doing it inside this synchronous step would make one config change quietly triple the
    runtime. `is_live=None` means nothing is excluded for it, which is the safe direction: an
    UNCHECKED name is not a DEAD name. The consequence is that the denominator currently includes
    names that may not resolve, and the probe loop drops each one when the connection fails — so
    the published `reached` count is honest even though the sample was drawn from a wider pool.
    """
    cfg = get_scoring_config()
    if cfg.estate_probe_cap() <= 1 or not vendor.domain:
        return None
    ct = next((r for r in results if r.source == "ct" and r.status == "ok"), None)
    if ct is None or not ct.raw:
        return None
    names = list(ct.raw.get("subdomains_sample") or [])
    if not names:
        return None
    spec = cfg.estate_spec()
    return build_estate(
        vendor.ref, vendor.domain, names,
        cap=cfg.estate_probe_cap(),
        wildcard_seen=bool(ct.raw.get("wildcard_seen")),
        sibling_threshold=int(spec.get("tenant_sibling_threshold", 25)),
        is_live=None,
    )


async def _emit(progress: Progress | None, event: str, payload: dict[str, Any]) -> None:
    if progress is None:
        return
    result = progress(event, payload)
    if isinstance(result, Awaitable):
        await result


def _carry_forward_declaration(store: Store, ref: str, profile: Any,
                               supplied: tuple[Any, Any]) -> None:
    """Replay a prior CLIENT DECLARATION onto a freshly built profile.

    THE BUG THIS FIXES, found by the UI on 2026-08-01. A profile is rebuilt from scratch on every
    run, and `criticality` / `substitutability` arrive as call arguments — so a re-score that does
    not re-supply them (the scheduled monitor, a dispute re-score, a blocked-record retry) wrote a
    new profile row with `criticality=None` and SILENTLY DISCARDED the declaration. Two vendors on
    the live book had already lost theirs.

    It failed in the worst possible direction. `data_access_scope` lives on a different table and
    survived, so `inherent_tier` kept publishing — just one input lighter. The tier degraded from
    `max(criticality, scope)` to `scope` alone, quietly, with nothing on the page to say a declared
    input had gone. A vendor declared high/medium re-published as medium after a routine re-scan.

    WHY THIS IS A CARRY-FORWARD AND NOT A MERGE. E10b's rule is that posture and inherent exposure
    run on DIFFERENT CLOCKS: posture moves when the vendor's controls move, exposure moves when the
    relationship changes. A re-scan is a posture event and must not touch the exposure at all. The
    same discipline as `VendorProfile.search_name` above — the store already knows the answer, so a
    run that was not told it should replay it rather than blank it.

    AN EXPLICITLY SUPPLIED VALUE ALWAYS WINS. `supplied` carries what the caller passed; where it
    is not None the caller is stating the exposure now, and the prior value is superseded rather
    than restored. Only a genuinely absent argument is filled in.
    """
    crit_supplied, subst_supplied = supplied
    if crit_supplied is not None and subst_supplied is not None:
        return
    prior = store.latest_profile(ref)
    if prior is None:
        return

    if crit_supplied is None and prior.criticality is not None:
        profile.criticality = prior.criticality
        profile.inherent_provisional = getattr(prior, "inherent_provisional", False)
        log.info("%s: replayed declared criticality %r onto the re-scored profile",
                 ref, prior.criticality)
    if subst_supplied is None and prior.substitutability is not None:
        profile.substitutability = prior.substitutability


def _record_cohort_attributes(store: Store, ref: str, profile: Any) -> None:
    """Append this vendor's v2 cohort inputs from the profile the run just built.

    WHY THIS EXISTS. `supplier_attributes` is the SOURCE OF TRUTH the v2 cohort tables are a
    materialisation of — `bm_cohort_peers` reads it and nothing else. Until now the only two writers
    were the `/api/v2/suppliers/{ref}/attributes` route and the inherent register, so **being scored
    did not put a supplier into a peer group at all**. The book held 144 profiles, 128 of them with
    a sector resolved from Wikidata or GLEIF, against 23 attribute rows of which 4 carried a sector:
    a technology cohort of 4 in a book with 37 profiled technology vendors. Every benchmark on the
    platform was refusing for want of peers that had already been assessed.

    THE DECLARATION IS CARRIED FORWARD, NOT OVERWRITTEN. `data_access_scope` and `delivery_model`
    are buyer-side facts that no collector can observe, and this table is append-only, so writing a
    fresh row without them would make the newest row — the one every read takes — the one that lost
    the declaration. That is exactly the defect `_carry_forward_declaration` above exists to fix,
    one table across; re-scoring a vendor must not quietly drop what somebody declared about it.

    SOURCE IS `derived`, not `client_supplied`. These values came from public evidence, and the
    provenance is what tells a reviewer whether a disagreement is ours to fix or the client's.
    """
    try:
        from .benchmarking.models import SupplierFirmographics
        from .benchmarking.service import firmographics_of, record_attributes

        def _v(field: Any) -> Any:
            return field.value if field is not None else None

        prior = firmographics_of(store, ref)
        firmographics = SupplierFirmographics(
            supplier_ref=ref,
            sector=_v(profile.sector),
            employees=_v(profile.employees),
            revenue=_v(profile.revenue),
            revenue_currency=_v(profile.revenue_currency),
            delivery_model=prior.delivery_model if prior else None,
            data_access_scope=prior.data_access_scope if prior else None,
        )
        record_attributes(store, firmographics, source="derived")
    except Exception as exc:  # noqa: BLE001 — cohort attributes are context, never worth a score
        log.warning("%s: cohort attributes not recorded: %r", ref, exc)


def _peer_context(store: Store, vendor: Vendor, profile: Any) -> PeerContext:
    """E13 — assemble `L_peer` from this vendor's cohort, or say why there is none.

    THE ONE ARGUMENT E13'S SWITCH-ON WAS ALWAYS DESCRIBED AS. It reaches the side-by-side preview
    and nothing else; `shrink()` still refuses below eight peers, and the engine still never
    consumes the result.

    THE EXACT COHORT, NOT THE WIDENING LADDER (`build_benchmark`). Ranking a supplier against a
    widened group is worth doing with the widening disclosed; pulling their published number toward
    one is a different act, and a caption saying "sector-wide" does not travel with a score.

    PEERS COME FROM THE STORE, so they are vendors this deployment actually assessed —
    `_synthetic_baseline_peers` is a read-time fallback inside `benchmark.py` and has no write path
    into `vendor_profiles`. That is why `is_synthetic=False` here is a statement about provenance
    rather than a setting, and it is what makes the switch-on data-driven: the preview begins
    publishing for a cohort the run after it reaches eight members, with no code change and no flag.

    Failure is a refusal, never an exception. A cohort lookup is context; losing a score to it would
    invert the priority the whole pipeline is built around.
    """
    cohort = getattr(profile, "cohort", None) if profile is not None else None
    if cohort is None or not getattr(cohort, "key", None):
        return PeerContext(penalty_fraction=None, n_peers=0, is_synthetic=True,
                           basis="this vendor has no cohort — no sector was resolved or supplied")
    try:
        members = [(ref, posture) for ref, posture in store.cohort_members(cohort.key)
                   if ref != vendor.ref]
    except Exception as exc:  # noqa: BLE001 — see the docstring; context never costs a score
        log.warning("%s: peer context lookup failed: %r", vendor.ref, exc)
        return PeerContext(penalty_fraction=None, n_peers=0, is_synthetic=True,
                           basis=f"cohort lookup failed: {type(exc).__name__}")
    return peer_context([float(p) for _, p in members],
                        is_synthetic=False, cohort_label=cohort.key)


async def run_pipeline(
    vendor: Vendor, *, store: Store | None = None, http: httpx.AsyncClient | None = None,
    progress: Progress | None = None, include_enrichment: bool = False,
    criticality: Criticality | None = None, size_band: SizeBand | None = None,
    sector: str | None = None, depth: Depth | None = None,
    substitutability: Substitutability | None = None,
) -> ScoreResult:
    """Collect -> store -> score -> persist. Returns the full auditable ScoreResult.

    By default only ON-DEMAND collectors run — the ones that feed a scored category. Enrichment-only
    sources (GDELT: held/ai_adjudicated, and rate-limited to 429s) are skipped so a score is fast
    and doesn't hammer a throttled API; they belong in Phase 5 scheduled enrichment. Pass
    `include_enrichment=True` to run everything (e.g. a scheduled candidate-gathering job).

    P5 — `depth` narrows collection to what an inherent tier warrants (`screening` / `core` /
    `full`). DEFAULT `None` MEANS FULL, so every existing caller is byte-for-byte unchanged and no
    score silently gets cheaper. A shallower run is a deliberate, per-relationship decision made by
    whoever schedules it, never a default.

    THE SCORING PATH IS IDENTICAL AT EVERY DEPTH. Fewer collectors return, so fewer signals are
    observed, so confidence falls — and it is ALLOWED to fall. The denominator stays the full model
    (`assessment_depth` explains why at length): a screening run therefore refuses as a Ghost, which
    is the correct result and not a defect. There is no second, weaker scoring route here.
    """
    settings = get_settings()
    collectors = [c for c in all_collectors() if include_enrichment or c.on_demand]
    allowed = sources_for_depth(depth) if depth else None
    if allowed is not None:
        skipped = [c.source for c in collectors if c.source not in allowed]
        collectors = [c for c in collectors if c.source in allowed]
        log.info("%s: %s depth — %d collector(s) run, %d skipped: %s",
                 vendor.ref, depth, len(collectors), len(skipped), sorted(skipped))

    async with AsyncExitStack() as stack:
        if store is None:
            store = get_store()
            stack.callback(store.close)
        if http is None:
            http = await stack.enter_async_context(
                httpx.AsyncClient(
                    headers={"User-Agent": settings.user_agent},
                    timeout=settings.http_timeout_s, follow_redirects=True,
                )
            )
        ctx = CollectorContext(settings=settings, limiter=RateLimiter(), http=http)

        # DURABLE ENTITY RESOLUTION. A domain-only run — the continuous monitor, a dispute re-score —
        # searches the name-only registers (GLEIF, ABN) by the domain slug, which re-matches a
        # foreign subsidiary: "archerirm.com" → "archerirm" → the Indian arm, not the US parent. If a
        # PRIOR run resolved with a real name and stored it (`VendorProfile.search_name`), replay it
        # here, BEFORE collection, so the registers are queried with "Archer Technologies" again. The
        # domain and the whole evidence chain are untouched; only the register query changes.
        if not vendor.name:
            prior = store.latest_profile(vendor.ref)
            if prior and prior.search_name:
                vendor.name = prior.search_name
                log.info("%s: replaying stored search name %r for a domain-only run",
                         vendor.ref, prior.search_name)

        # AGE-BASED RELIABILITY MODIFIERS: Run RDAP first to extract domain age, then pass it to
        # the context so HIBP and regulatory collectors can adjust clean receipt reliability based on
        # company age. A clean result from a young company is weaker evidence than the same result
        # from a mature company (fewer years to accumulate breaches or attract enforcement).
        rdap_collector = next((c for c in collectors if c.source == "rdap"), None)
        rdap_result = None
        results: list[CollectorResult] = []
        evidence_ids: dict[str, str] = {}
        if rdap_collector and vendor.domain:
            rdap_result = await rdap_collector.collect(vendor, ctx)
            evidence = store.put(rdap_result)
            evidence_ids[rdap_result.source] = evidence.id
            results.append(rdap_result)
            await _emit(progress, "collector_done", {
                "source": rdap_result.source, "status": rdap_result.status,
                "findings": len(rdap_result.findings), "evidence_id": evidence.id,
            })
            # Extract domain age from RDAP result
            if rdap_result.status == "ok" and rdap_result.raw:
                created_str = rdap_result.raw.get("created")
                if created_str:
                    try:
                        from datetime import UTC, datetime
                        created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        if created.tzinfo is None:
                            created = created.replace(tzinfo=UTC)
                        age_days = (datetime.now(UTC) - created).days
                        ctx.domain_age_days = age_days
                        log.info("%s: domain age extracted from RDAP: %d days", vendor.ref, age_days)
                    except Exception as exc:
                        log.warning("%s: failed to parse RDAP creation date: %r", vendor.ref, exc)

        # Filter out RDAP from the remaining collectors since we already ran it
        remaining_collectors = [c for c in collectors if c.source != "rdap"]

        await _emit(progress, "collecting", {"total": len(remaining_collectors) + (1 if rdap_result else 0),
                                             "sources": [c.source for c in collectors]})
        tasks = [asyncio.create_task(c.collect(vendor, ctx)) for c in remaining_collectors]
        for fut in asyncio.as_completed(tasks):
            result = await fut
            evidence = store.put(result)          # EVIDENCE STORE FIRST — before any scoring
            evidence_ids[result.source] = evidence.id
            results.append(result)
            await _emit(progress, "collector_done", {
                "source": result.source, "status": result.status,
                "findings": len(result.findings), "evidence_id": evidence.id,
            })

        # E12 — THE SECOND WAVE. The estate is derived from certificate transparency, and every
        # collector above runs CONCURRENTLY, so at the moment the TLS collector starts the CT
        # result does not exist. Resolving it here, once, between the waves, is what stops two
        # collectors sampling independently and publishing two rates against two different
        # denominators for one estate — a reader comparing "8 of 340" with "2 of 290" has no way
        # to know the populations differ.
        #
        # AT `probe_cap: 1` NOTHING HAPPENS HERE. No estate, no second wave, no extra traffic —
        # exactly the pre-E12 behaviour. Raising the cap is a resourcing decision, and it is a
        # config value rather than a code change so that whoever raises it sees the budget.
        estate = _resolve_estate(vendor, results)
        if estate is not None and estate.denominator > 1:
            ctx.estate = estate
            await _emit(progress, "estate", {
                "probed": estate.denominator, "eligible": estate.eligible,
                "discovered": estate.discovered, "rule": estate.rule(),
            })
            estate_result = await EstateCollector().collect(vendor, ctx)
            evidence = store.put(estate_result)
            evidence_ids[estate_result.source] = evidence.id
            results.append(estate_result)
            await _emit(progress, "collector_done", {
                "source": estate_result.source, "status": estate_result.status,
                "findings": len(estate_result.findings), "evidence_id": evidence.id,
            })

        # ENTITY RESOLUTION, second pass. Confidence can only be derived once the registries have
        # answered, so it is computed here — after collection, before the gate reads it. A caller
        # may override it (testing, or a human adjudicator's judgement); otherwise it is evidence.
        if vendor.resolution_confidence is None:
            resolution = assess_resolution(vendor, results)
            vendor.resolution_confidence = resolution.confidence
            vendor.resolution_basis = resolution.summary()
            await _emit(progress, "resolved", {
                "confidence": resolution.confidence, "basis": resolution.summary(),
            })

        # PROFILE — built before scoring, but NO LONGER because the sector reaches the arithmetic.
        # Since E1 nothing on the profile does: sector selects the peer cohort and (later) the
        # Compliance Gap frameworks, and every other field was already excluded under §7.3.
        # A profiling failure must not lose a score, so it stays isolated.
        profile = None
        try:
            profile = build_profile(vendor, results, criticality=criticality,
                                    size_band=size_band, sector=sector,
                                    substitutability=substitutability)
            _carry_forward_declaration(store, vendor.ref, profile,
                                       supplied=(criticality, substitutability))
        except Exception as exc:  # noqa: BLE001 — context is not worth losing a score over
            log.warning("%s: profile build failed: %r", vendor.ref, exc)

        vendor_sector = profile.sector.value if (profile and profile.sector) else None

        # Extract operating years from profile for age-based posture penalties
        if profile and hasattr(profile, 'operating_years') and profile.operating_years is not None:
            vendor.operating_years = profile.operating_years

        # ACCEPTED refutes are honoured on every score, not just the one that accepted them: a
        # dispute is durable until the observation it targets changes (see models.Dispute). Loading
        # them here means a scheduled re-score keeps a mitigation applied without re-adjudicating.
        disputes = store.accepted_dispute_targets(vendor.ref)

        await _emit(progress, "scoring", {})
        score_result = ScoringEngine().score(vendor, results, evidence_ids,
                                             sector=vendor_sector, disputes=disputes,
                                             peers=_peer_context(store, vendor, profile))
        score_id = store.put_score(score_result.score)   # append-only published-score history
        # persist the signal-level interpreted evidence behind it (observation -> severity ->
        # penalty), linked to the raw receipts — per-signal auditability, append-only (Finding A).
        # Tagged with the score's id so a reader can ask for THIS run rather than every run ever.
        store.put_findings(vendor.ref, score_result.normalized, run_id=score_id)

        if profile is not None:
            store.put_profile(profile)
            await _emit(progress, "profiled", {
                "sector": vendor_sector,
                "cohort": profile.cohort.key if profile.cohort else None,
                "completeness": profile.completeness,
            })

            # V2 COHORT ATTRIBUTES — the row `bm_cohort_peers` actually reads. Isolated like every
            # other post-score step: a benchmarking write must never lose a score.
            _record_cohort_attributes(store, vendor.ref, profile)

            # PERCENTILE SNAPSHOT — freeze where this vendor stood among its peers AS AT this run.
            # The overall percentile is a read-time quantity (computed against today's cohort); a
            # TREND needs it frozen against the peers that existed THEN, or a later re-score would
            # compare an old posture to a new cohort. Computed AFTER put_profile so the widening
            # ladder sees a complete cohort, and excludes the subject from its own comparison. A
            # benchmark failure must never lose a score, so it is isolated like the profile build.
            try:
                bm = build_benchmark(
                    score_result.score.posture, profile.cohort,
                    lookup=peer_lookup(store, exclude_ref=vendor.ref),
                    subject_confidence=score_result.score.overall_confidence,
                )
                # A SYNTHETIC comparison is recorded as UNAVAILABLE, not as a data point. The
                # trend's own contract is that a thin cohort leaves an honest gap in the line
                # rather than a fabricated continuation of it — and a cohort with no real peer
                # at all is the thinnest case there is. Writing peer_n=6 here would put six
                # invented numbers into the historical record as though six companies had been
                # assessed, which is the same misreading the `synthetic` flag exists to stop.
                synthetic = getattr(bm, "synthetic", False)
                store.put_benchmark_snapshot(BenchmarkSnapshot(
                    id=uuid.uuid4().hex, vendor_ref=vendor.ref,
                    cohort_key=profile.cohort.key if profile.cohort else None,
                    level=bm.level,
                    available=bm.available and not synthetic,
                    percentile=None if synthetic else bm.percentile,
                    percentile_resolution=None if synthetic else bm.percentile_resolution,
                    quartile=None if synthetic else bm.quartile,
                    peer_n=0 if synthetic else (bm.stats.n if bm.stats else 0),
                    posture=score_result.score.posture,
                ))
            except Exception as exc:  # noqa: BLE001 — a snapshot is context, never worth a score
                log.warning("%s: benchmark snapshot failed: %r", vendor.ref, exc)

        await _emit(progress, "done", {
            "vendor_ref": vendor.ref,
            "blocked": score_result.score.blocked,
            "refused": score_result.score.refused,
            "posture": score_result.score.posture,
            "grade": score_result.score.grade,
            "overall_confidence": score_result.score.overall_confidence,
            "confidence_band": score_result.score.confidence_band,
        })
        return score_result
