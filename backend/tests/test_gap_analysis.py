"""E14 — gap analysis & recommendations, the LLM read layer over a finished assessment.

Locked-down invariants, in the order the exit criteria list them:
  * the context is assembled deterministically, by code, never by the prompt reaching into a store;
  * nothing here can reach a vendor score — no import of the scoring engine or the pipeline;
  * the provider chain falls back on transport failure and rate limits, never on content;
  * the answering provider and model travel on the artefact;
  * chain exhaustion is 503, never a template;
  * every citation is validated against the context's own finding ids, invented ones dropped and
    counted;
  * `limitations` is byte-identical to the coverage statement, never generated;
  * the four stated gate refusals, each on its own, and a provisional tier that annotates only;
  * accept/edit/reject are append-only, in the store and over the API.

No network: an httpx.MockTransport stands in for every provider, exactly as test_summariser.py
does it. DB-backed tests use the conftest `store`/`dsn` fixtures and skip cleanly with no
DATABASE_URL configured.
"""

from __future__ import annotations

import inspect
import json
import uuid

import httpx
import pytest

from app import gap_analysis as ga
from app.compliance_gap import ComplianceGap, ComplianceGapReport
from app.config import Settings
from app.continuity import ContinuityFlag, ContinuityReport
from app.models import (
    CategoryScore,
    GapAnalysisRecommendationEvent,
    GapAnalysisRecord,
    PeerCohort,
    ProfileField,
    Score,
    VendorProfile,
)
from app.residual_risk import residual_risk

# ============================================================ module boundary


def test_module_touches_no_scoring_machinery():
    """Structural, not behavioural: the source text must not even NAME the engine or the pipeline,
    so a future import cannot sneak a re-score in through a helper. `put_score` gets the same
    treatment — this module writes nothing to the score store at all."""
    src = inspect.getsource(ga)
    for forbidden in ("scoring.engine", "from .pipeline", "import pipeline", "put_score("):
        assert forbidden not in src, f"gap_analysis.py must never reference {forbidden!r}"


# ============================================================ config: the provider chain


def test_partial_provider_config_is_a_startup_error():
    with pytest.raises(Exception):  # pydantic ValidationError wrapping our ValueError
        Settings(gemini_base_url="https://x", _env_file=None)


def test_fully_configured_provider_is_accepted():
    s = Settings(gemini_base_url="https://x", gemini_api_key="k", gemini_model="m", _env_file=None)
    assert s.gap_analysis_chain() == [("gemini", "https://x", "k", "m")]
    assert s.gap_analysis_configured() is True


def test_unconfigured_chain_is_empty():
    s = Settings(_env_file=None)
    assert s.gap_analysis_chain() == []
    assert s.gap_analysis_configured() is False


def test_chain_order_is_gemini_groq_openrouter():
    s = Settings(
        openrouter_base_url="https://o", openrouter_api_key="k", openrouter_model="m",
        groq_base_url="https://g", groq_api_key="k", groq_model="m",
        gemini_base_url="https://z", gemini_api_key="k", gemini_model="m",
        _env_file=None,
    )
    assert [name for name, *_ in s.gap_analysis_chain()] == ["gemini", "groq", "openrouter"]


# ============================================================ fixtures shared below


def _score(*, blocked=False, refused=False, band="Medium", posture=70) -> Score:
    return Score(
        vendor_ref="acme", blocked=blocked,
        blocked_reason="sanctions screen hit" if blocked else None,
        refused=refused, posture=None if (blocked or refused) else posture,
        grade=None if (blocked or refused) else "B",
        overall_confidence=0.8, confidence_band=band, ghost=(band == "Low"),
        categories=[CategoryScore(category="attack_surface_hygiene", posture=posture, grade="B",
                                  penalty=20.0, coverage=0.9, findings=1,
                                  contributing_finding_ids=["f1"])] if not (blocked or refused) else [],
    )


def _profile() -> VendorProfile:
    return VendorProfile(
        vendor_ref="acme",
        legal_name=ProfileField(value="Acme Pty Ltd", source="gleif"),
        jurisdiction=ProfileField(value="AU", source="gleif"),
        sector=ProfileField(value="technology", source="wikidata"),
        employees=ProfileField(value=500, source="wikidata"),
        ownership=ProfileField(value="private", source="wikidata"),
        cohort=PeerCohort(sector="technology", region="anz",
                          key="technology|rev=?|emp=medium|anz"),
    )


def _coverage() -> dict:
    return {
        "vendor_ref": "acme", "statement": "This assessment covers externally observable evidence only.",
        "coverage": 0.7, "signals_covered": 12, "signals_planned": 18,
        "sources_observed": ["dns", "tls"], "not_collected_this_run": [],
        "held_no_lawful_free_source": [], "never_observable_from_outside": [],
        "next_step": "ask the vendor",
    }


def _findings_rows() -> list[dict]:
    return [
        {"evidence_id": "ev1", "signal": "dmarc", "band_key": "absent", "category": "identity_email",
         "severity": "medium", "observed": "no DMARC record", "effective_penalty": 6.0,
         "ask_of_vendor": "publish a DMARC record", "accepts_as_refute": "policy screenshot",
         "recheck_after": "30d", "dispute_status": None},
        {"evidence_id": "ev2", "signal": "cert_validity", "band_key": "valid", "category": "attack_surface_hygiene",
         "severity": "none", "observed": "valid cert", "effective_penalty": 0.0,
         "ask_of_vendor": None, "accepts_as_refute": None, "recheck_after": None,
         "dispute_status": None},
    ]


def _context(**overrides) -> ga.GapAnalysisContext:
    residual = residual_risk(overrides.pop("posture", 70), "high", "high")
    kwargs = dict(
        vendor_ref="acme", profile=_profile(), score=_score(), findings=_findings_rows(),
        penalty_divisor=2.86, coverage_statement=_coverage(),
        assurity=None,
        continuity=ContinuityReport(vendor_ref="acme", standing="sound", flags=[], age_context=[], caveats=[]),
        compliance_gap=ComplianceGapReport(vendor_ref="acme", gaps=[], frameworks_considered=[]),
        expectation_gap=None, residual=residual, concentration=["okta"],
        assessment_plan={"depth": "full", "cadence": "quarterly"},
    )
    kwargs.update(overrides)
    return ga.assemble_context(**kwargs)


# ============================================================ context assembly


def test_context_is_assembled_deterministically_and_reviewable():
    ctx = _context()
    d = ctx.as_dict()
    assert set(d) == {"vendor_ref", "identity", "posture", "findings", "confidence",
                      "assurity", "continuity", "gaps", "exposure", "context"}
    assert d["identity"]["legal_name"] == "Acme Pty Ltd"
    assert d["identity"]["sector"] == "technology"
    assert d["exposure"]["inherent_tier"] == "high"
    # ONLY THE CHARGED FINDING travels — ev2 cost nothing and must not appear as a "gap".
    assert [f["evidence_id"] for f in d["findings"]] == ["ev1"]
    # Assembling the same inputs twice must produce the identical hash — no hidden clock, no
    # randomness. This is the property the exit criterion actually needs.
    assert ctx.content_hash() == _context().content_hash()


def test_finding_ids_are_only_the_charged_ones():
    ctx = _context()
    assert ctx.finding_ids() == {"ev1"}


def test_render_prompt_is_pure_and_cites_only_context_ids():
    ctx = _context()
    prompt = ga.render_prompt(ctx)
    assert "ev1" in prompt
    assert "ev2" not in prompt          # uncharged finding never reaches the model
    assert "Acme Pty Ltd" in prompt
    # No store, no network object anywhere near this function.
    assert "store" not in inspect.signature(ga.render_prompt).parameters


def test_limitations_is_the_coverage_statement_object_itself():
    ctx = _context()
    assert ctx.coverage_statement == _coverage()


# ============================================================ gating


def test_gate_refuses_no_score():
    r = ga.gate(score=None, inherent_tier="high")
    assert r.allowed is False
    assert any("not been scored" in x for x in r.reasons)


def test_gate_refuses_blocked():
    r = ga.gate(score=_score(blocked=True), inherent_tier="high")
    assert r.allowed is False
    assert any("blocked" in x for x in r.reasons)


def test_gate_refuses_refused():
    r = ga.gate(score=_score(refused=True), inherent_tier="high")
    assert r.allowed is False
    assert any("refused" in x for x in r.reasons)


def test_gate_refuses_thin_confidence():
    r = ga.gate(score=_score(band="Low"), inherent_tier="high")
    assert r.allowed is False
    assert any("Confidence is Low" in x for x in r.reasons)


def test_gate_refuses_undeclared_tier():
    r = ga.gate(score=_score(), inherent_tier=None)
    assert r.allowed is False
    assert any("Inherent tier is not declared" in x for x in r.reasons)


def test_gate_refuses_when_no_provider_configured(monkeypatch):
    monkeypatch.setattr(ga, "get_settings", lambda: Settings(_env_file=None))
    r = ga.gate(score=_score(), inherent_tier="high")
    assert r.allowed is False
    assert any("No LLM is configured" in x for x in r.reasons)


def test_gate_allows_a_clean_published_declared_vendor(monkeypatch):
    monkeypatch.setattr(ga, "get_settings", lambda: Settings(
        gemini_base_url="https://x", gemini_api_key="k", gemini_model="m", _env_file=None))
    r = ga.gate(score=_score(), inherent_tier="high")
    assert r.allowed is True
    assert r.reasons == []


def test_provisional_tier_does_not_gate(monkeypatch):
    """A provisional inherent tier ANNOTATES, never gates — a real tier from the register beats no
    tier at all, and `gate()` never even sees the provisional flag: it only sees a tier or None."""
    monkeypatch.setattr(ga, "get_settings", lambda: Settings(
        gemini_base_url="https://x", gemini_api_key="k", gemini_model="m", _env_file=None))
    r = ga.gate(score=_score(), inherent_tier="high")   # provisional-or-not is invisible to gate()
    assert r.allowed is True


# ============================================================ the provider chain


def _settings_with_chain(*names: str) -> Settings:
    kwargs = {}
    for n in names:
        kwargs[f"{n}_base_url"] = f"https://{n}.test/v1"
        kwargs[f"{n}_api_key"] = "sk-test"
        kwargs[f"{n}_model"] = f"{n}/model-1"
    return Settings(**kwargs, _env_file=None)


_GOOD_BODY = json.dumps({
    "executive_summary": "Acme is a high-exposure vendor with a thin email-auth gap.",
    "gaps": [{"theme": "email auth", "what_we_observed": "no DMARC", "what_we_expected": "p=reject",
             "why_it_matters": "spoofing", "evidence_finding_ids": ["ev1"],
             "confidence_caveat": "coverage 70%"}],
    "recommendations": [{"priority": "high", "recommendation": "publish DMARC p=reject",
                         "rationale": "closes the gap", "effort": "low", "owner_hint": "IT",
                         "contract_flowdown_ref": None, "evidence_finding_ids": ["ev1", "ev999"],
                         "addresses_gap": "email auth"}],
})


@pytest.mark.asyncio
async def test_unconfigured_raises_unavailable(monkeypatch):
    monkeypatch.setattr(ga, "get_settings", lambda: Settings(_env_file=None))
    with pytest.raises(ga.GapAnalysisUnavailable):
        await ga.generate(_context())


@pytest.mark.asyncio
async def test_happy_path_single_provider(monkeypatch):
    settings = _settings_with_chain("gemini")
    monkeypatch.setattr(ga, "get_settings", lambda: settings)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={
            "model": "gemini/model-1", "choices": [{"message": {"content": _GOOD_BODY}}],
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        out = await ga.generate(_context(), client=client)

    assert seen["url"] == "https://gemini.test/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    assert out["provenance"]["provider"] == "gemini"
    assert out["provenance"]["model"] == "gemini/model-1"
    assert out["provenance"]["prompt_version"] == ga.PROMPT_VERSION
    assert out["ai_generated"] is True
    # limitations is the SAME object as the context's coverage statement — copied, not generated.
    assert out["limitations"] == _coverage()
    # ev999 was never a real finding id — dropped, and the drop is counted.
    assert out["recommendations"][0]["evidence_finding_ids"] == ["ev1"]
    assert out["dropped_evidence_ids"] == 1
    assert out["gaps"][0]["evidence_finding_ids"] == ["ev1"]


@pytest.mark.asyncio
async def test_chain_falls_back_on_429_then_5xx_then_succeeds(monkeypatch):
    """429 -> next, 5xx -> next, 200 -> returned. Exactly the sequence the exit criterion names."""
    settings = _settings_with_chain("gemini", "groq", "openrouter")
    monkeypatch.setattr(ga, "get_settings", lambda: settings)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "gemini" in str(request.url):
            return httpx.Response(429, text="rate limited")
        if "groq" in str(request.url):
            return httpx.Response(503, text="server error")
        return httpx.Response(200, json={
            "model": "openrouter/model-1", "choices": [{"message": {"content": _GOOD_BODY}}],
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        out = await ga.generate(_context(), client=client)

    assert len(calls) == 3
    assert out["provenance"]["provider"] == "openrouter"


@pytest.mark.asyncio
async def test_chain_falls_back_on_timeout(monkeypatch):
    settings = _settings_with_chain("gemini", "groq")
    monkeypatch.setattr(ga, "get_settings", lambda: settings)

    def handler(request: httpx.Request) -> httpx.Response:
        if "gemini" in str(request.url):
            raise httpx.ConnectTimeout("timed out", request=request)
        return httpx.Response(200, json={
            "model": "groq/model-1", "choices": [{"message": {"content": _GOOD_BODY}}],
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        out = await ga.generate(_context(), client=client)

    assert out["provenance"]["provider"] == "groq"


@pytest.mark.asyncio
async def test_200_with_poor_content_is_returned_not_retried(monkeypatch):
    """A 200 whose content is not valid JSON is STILL a 200 — returned as-is, never sent to the
    next provider. This is the design rule the whole chain exists to protect."""
    settings = _settings_with_chain("gemini", "groq")
    monkeypatch.setattr(ga, "get_settings", lambda: settings)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={
            "model": "gemini/model-1",
            "choices": [{"message": {"content": "sorry, I cannot help with that today"}}],
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        out = await ga.generate(_context(), client=client)

    assert len(calls) == 1   # groq was NEVER called — a 200 is never retried for quality
    assert out["provenance"]["provider"] == "gemini"
    assert out["gaps"] == []
    assert out["recommendations"] == []
    assert "cannot help" in out["executive_summary"]
    assert out["parse_warning"] is not None


@pytest.mark.asyncio
async def test_chain_exhaustion_raises_never_a_template(monkeypatch):
    settings = _settings_with_chain("gemini", "groq")
    monkeypatch.setattr(ga, "get_settings", lambda: settings)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="down")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ga.GapAnalysisExhausted):
            await ga.generate(_context(), client=client)


@pytest.mark.asyncio
async def test_identical_context_and_prompt_reach_every_provider(monkeypatch):
    """Design rule 3: every provider gets the identical context and the identical prompt."""
    settings = _settings_with_chain("gemini", "groq")
    monkeypatch.setattr(ga, "get_settings", lambda: settings)
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content)["messages"][1]["content"])
        return httpx.Response(429, text="rate limited") if "gemini" in str(request.url) else \
            httpx.Response(200, json={"choices": [{"message": {"content": _GOOD_BODY}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await ga.generate(_context(), client=client)

    assert bodies[0] == bodies[1]


# ============================================================ storage (DB-backed; skips with no DATABASE_URL)


def test_gap_analysis_round_trips_and_is_append_only(store):
    record = GapAnalysisRecord(
        id=uuid.uuid4().hex, vendor_ref="acme", provider="gemini", model="gemini/model-1",
        prompt_version="e14-v1", context_hash="deadbeef",
        executive_summary="summary text", gaps=[{"theme": "x"}],
        recommendations=[{"priority": "high", "recommendation": "do X"}],
        limitations=_coverage(), dropped_evidence_ids=1,
    )
    store.put_gap_analysis(record)

    fetched = store.get_gap_analysis(record.id)
    assert fetched is not None
    assert fetched.executive_summary == "summary text"
    assert fetched.limitations == _coverage()
    assert fetched.recommendations == [{"priority": "high", "recommendation": "do X"}]

    history = store.gap_analysis_history("acme")
    assert [h.id for h in history] == [record.id]

    import psycopg
    with pytest.raises(psycopg.errors.RaiseException):
        store._conn.execute(f"UPDATE gap_analyses SET executive_summary='x' WHERE id='{record.id}'")
    with pytest.raises(psycopg.errors.RaiseException):
        store._conn.execute(f"DELETE FROM gap_analyses WHERE id='{record.id}'")


def test_recommendation_events_are_append_only_and_keep_the_original(store):
    record = GapAnalysisRecord(
        id=uuid.uuid4().hex, vendor_ref="acme", provider="gemini", model="m",
        prompt_version="e14-v1", context_hash="h",
        executive_summary="s", gaps=[],
        recommendations=[{"priority": "high", "recommendation": "publish DMARC"}],
        limitations={},
    )
    store.put_gap_analysis(record)

    accept = GapAnalysisRecommendationEvent(
        id=uuid.uuid4().hex, analysis_id=record.id, vendor_ref="acme", rec_index=0,
        event="accepted", actor="alice")
    store.put_gap_analysis_event(accept)
    events = store.gap_analysis_events(record.id)
    assert [e.event for e in events] == ["accepted"]

    edit = GapAnalysisRecommendationEvent(
        id=uuid.uuid4().hex, analysis_id=record.id, vendor_ref="acme", rec_index=0,
        event="edited", edited_text="publish DMARC p=reject within 30 days", actor="bob")
    store.put_gap_analysis_event(edit)
    events = store.gap_analysis_events(record.id)
    # BOTH events remain — "the analyst agreed" and "the analyst rewrote it" are different facts.
    assert [e.event for e in events] == ["accepted", "edited"]
    assert events[-1].edited_text == "publish DMARC p=reject within 30 days"
    # The ORIGINAL recommendation text is untouched — nothing was edited in place.
    assert store.get_gap_analysis(record.id).recommendations[0]["recommendation"] == "publish DMARC"

    import psycopg
    with pytest.raises(psycopg.errors.RaiseException):
        store._conn.execute(f"DELETE FROM gap_analysis_events WHERE analysis_id='{record.id}'")


# ============================================================ program KPI: acceptance rate


def test_acceptance_rate_metric_replaces_stakeholder_satisfaction():
    from app.program_kpis import METRICS
    keys = {m.key for m in METRICS}
    assert "gap_analysis_acceptance_rate" in keys
    assert "stakeholder_satisfaction" not in keys
    assert len(METRICS) <= 15
    assert len({m.key for m in METRICS}) == len(METRICS)


def test_acceptance_rate_excludes_pending_and_reports_per_provider(store):
    a = GapAnalysisRecord(id=uuid.uuid4().hex, vendor_ref="acme", provider="gemini", model="m",
                          prompt_version="v", context_hash="h", executive_summary="s", gaps=[],
                          recommendations=[{"recommendation": "1"}, {"recommendation": "2"},
                                           {"recommendation": "3"}],
                          limitations={})
    store.put_gap_analysis(a)
    b = GapAnalysisRecord(id=uuid.uuid4().hex, vendor_ref="acme", provider="openrouter", model="m",
                          prompt_version="v", context_hash="h2", executive_summary="s", gaps=[],
                          recommendations=[{"recommendation": "1"}], limitations={})
    store.put_gap_analysis(b)

    store.put_gap_analysis_event(GapAnalysisRecommendationEvent(
        id=uuid.uuid4().hex, analysis_id=a.id, vendor_ref="acme", rec_index=0, event="accepted"))
    store.put_gap_analysis_event(GapAnalysisRecommendationEvent(
        id=uuid.uuid4().hex, analysis_id=a.id, vendor_ref="acme", rec_index=1, event="rejected"))
    # rec_index 2 on `a` is left PENDING — must not count either way.
    store.put_gap_analysis_event(GapAnalysisRecommendationEvent(
        id=uuid.uuid4().hex, analysis_id=b.id, vendor_ref="acme", rec_index=0, event="edited"))

    from app.program_kpis import METRICS, compute
    metric = next(m for m in METRICS if m.key == "gap_analysis_acceptance_rate")
    assert metric.provenance == "platform-derived"

    values = compute(store)
    mv = next(v for v in values if v.metric.key == "gap_analysis_acceptance_rate")
    assert mv.value == pytest.approx(66.7, abs=0.1)   # 2 of 3 dispositioned (1 accepted, 1 edited, 1 rejected)
    assert mv.detail["dispositioned"] == 3
    assert mv.detail["by_provider"]["gemini"] == pytest.approx(50.0, abs=0.1)
    assert mv.detail["by_provider"]["openrouter"] == pytest.approx(100.0, abs=0.1)
