"""Phase 3 API tests — HTTP surface + async job/SSE mechanics.

Read endpoints run against an injected, disposable Postgres schema (the conftest `store` fixture);
the job runner and SSE fan-out are tested directly on `JobManager` with a stubbed pipeline, so no
live collector fires and nothing touches the network. What these lock down: a bare score is
unrepresentable, evidence receipts round-trip, history accrues, the ambiguity/adjudication paths
behave, and progress events stream in order and terminate.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import jobs as jobs_mod
from app.api import app, store_dep
from app.models import CategoryScore, CollectorResult, Score, Vendor, VendorProfile
from app.scoring.engine import ScoreResult
from app.scoring.normalize import NormalizedFinding


def _score(ref: str, *, blocked: bool = False) -> Score:
    if blocked:
        return Score(vendor_ref=ref, blocked=True,
                     blocked_reason="sanctions screen hit — adjudication required",
                     posture=None, grade=None, overall_confidence=0.0, confidence_band="Low")
    return Score(
        vendor_ref=ref, blocked=False, posture=90, grade="A", overall_confidence=0.77,
        confidence_band="Medium", refused=False,
        categories=[CategoryScore(category="cyber_hygiene_technical", posture=90, grade="A",
                                  penalty=10.0, coverage=1.0, findings=1,
                                  contributing_finding_ids=["ev1"])],
    )


@pytest.fixture
def client(store):  # noqa: ANN001, ANN201
    """`store` is the conftest fixture — a fresh, disposable Postgres schema per test. The same
    store object serves both the seeding done in the test and every request the client makes, so
    a seeded row is visible to the endpoint that reads it."""
    app.dependency_overrides[store_dep] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


# --------------------------------------------------------------------- surface

def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_score_request_needs_name_or_domain(client):
    assert client.post("/api/vendors/score", json={}).status_code == 422


def test_name_only_asks_for_domain_never_guesses(client):
    """A bare name is not scored: no job, no guessed domain — a candidate list to confirm."""
    body = client.post("/api/vendors/score", json={"name": "Asana"}).json()
    assert body["needs_domain"] is True
    assert "job_id" not in body
    assert "asana.com" in body["candidates"]
    assert len(body["candidates"]) > 1              # a LIST, not a single guess


def test_domain_supplied_starts_a_job(client):
    body = client.post("/api/vendors/score", json={"domain": "asana.com"}).json()
    assert "job_id" in body and body["domain"] == "asana.com"
    assert "needs_domain" not in body


def test_get_score_404_when_absent(client):
    assert client.get("/api/vendors/ghostco").status_code == 404


def test_read_score_is_never_a_bare_number(client, store):
    """A bare score is unrepresentable — a confidence axis always rides with the posture."""
    store.put_score(_score("acme"))
    body = client.get("/api/vendors/acme").json()
    assert body["posture"] == 90 and body["grade"] == "A"
    assert body["overall_confidence"] == 0.77         # always present
    assert body["confidence_band"] == "Medium"        # always present


def test_evidence_receipt_round_trips(client, store):
    cr = CollectorResult(source="dns", vendor_ref="acme", status="ok", reliability=0.9,
                         raw={"dmarc": "p=reject"}, findings=[])
    ev = store.put(cr)
    listing = client.get("/api/vendors/acme/evidence").json()
    assert listing[0]["id"] == ev.id and "content_hash" in listing[0] and "raw" not in listing[0]
    receipt = client.get(f"/api/vendors/acme/evidence/{ev.id}").json()
    assert receipt["raw"] == {"dmarc": "p=reject"}          # the receipt carries stored raw
    # cross-vendor id must not leak
    assert client.get(f"/api/vendors/other/evidence/{ev.id}").status_code == 404


def test_findings_endpoint_exposes_signal_level_evidence(client, store):
    """The per-signal audit trail: each observation, its severity/penalty, and the evidence link."""
    cr = CollectorResult(source="dns", vendor_ref="acme", status="ok", reliability=0.9,
                         raw={"dmarc": "p=none"}, findings=[])
    ev = store.put(cr)
    store.put_findings("acme", [NormalizedFinding(
        evidence_id=ev.id, source="dns", category="cyber_hygiene_technical", signal="dmarc",
        band_key="p_none", severity="medium", penalty=8.0, event_date=None,
        is_critical=False, is_sanctions=False, observed="p=none",
    )])
    rows = client.get("/api/vendors/acme/findings").json()
    assert len(rows) == 1
    assert rows[0]["signal"] == "dmarc" and rows[0]["severity"] == "medium"
    assert rows[0]["penalty"] == 8.0 and rows[0]["observed"] == "p=none"
    assert rows[0]["evidence_id"] == ev.id and rows[0]["content_hash"]
    assert client.get("/api/vendors/never-scored/findings").status_code == 404


def test_history_accrues(client, store):
    store.put_score(_score("acme"))
    store.put_score(_score("acme"))
    assert len(client.get("/api/vendors/acme/history").json()) >= 2


def test_adjudication_requires_a_blocked_score(client, store):
    store.put_score(_score("acme"))  # not blocked
    assert client.post("/api/adjudications/acme",
                       json={"decision": "cleared", "note": "n"}).status_code == 409
    store.put_score(_score("blockco", blocked=True))
    r = client.post("/api/adjudications/blockco",
                    json={"decision": "cleared", "note": "reviewed, false positive"})
    assert r.status_code == 200 and r.json()["recorded"] is True


def test_post_score_returns_202_with_job(client, monkeypatch):
    async def fake(vendor, **kw):  # noqa: ANN001, ANN003
        return ScoreResult(score=_score(vendor.ref), normalized=[])
    monkeypatch.setattr(jobs_mod, "run_pipeline", fake)
    r = client.post("/api/vendors/score", json={"domain": "acme.com"})
    assert r.status_code == 202
    body = r.json()
    assert body["vendor_ref"] == "acme" and body["job_id"]


# --------------------------------------------------------------------- job + SSE (direct)

async def test_jobmanager_runs_and_streams_in_order(monkeypatch):
    """submit -> stream yields progress events in order and terminates; job ends 'done'."""
    async def fake(vendor, *, store=None, http=None, progress=None, **kw):  # noqa: ANN001, ANN003
        if progress:
            await progress("collecting", {"total": 2})
            await progress("collector_done", {"source": "dns", "status": "ok", "findings": 1})
            await progress("done", {"vendor_ref": vendor.ref})
        return ScoreResult(score=_score(vendor.ref), normalized=[])

    monkeypatch.setattr(jobs_mod, "run_pipeline", fake)
    mgr = jobs_mod.JobManager()
    vendor = Vendor(ref="acme", name="Acme", domain="acme.com", resolved=True,
                    resolution_confidence=1.0)
    job = mgr.submit(vendor)

    events = [item["event"] async for item in mgr.stream(job)]
    assert events == ["collecting", "collector_done", "done"]
    assert job.status == "done"
    assert job.result is not None and job.result.score.grade == "A"


async def test_job_failure_is_isolated(monkeypatch):
    async def boom(vendor, **kw):  # noqa: ANN001, ANN003
        raise RuntimeError("collector meltdown")
    monkeypatch.setattr(jobs_mod, "run_pipeline", boom)
    mgr = jobs_mod.JobManager()
    vendor = Vendor(ref="acme", resolved=True, resolution_confidence=1.0)
    job = mgr.submit(vendor)
    events = [item async for item in mgr.stream(job)]
    assert job.status == "error"
    assert any(e["event"] == "error" for e in events)


# --------------------------------------------------------------------- P3 · the two renderings


def _pack_fixture(store):
    """One vendor with two outstanding findings in two different domains, at two severities."""
    cr = CollectorResult(source="dns", vendor_ref="acme", status="ok", reliability=0.9,
                         raw={"dmarc": "absent"}, findings=[])
    ev = store.put(cr)
    store.put_findings("acme", [
        NormalizedFinding(evidence_id=ev.id, source="dns", category="identity_email",
                          signal="dmarc", band_key="absent", severity="high", penalty=20.0,
                          effective_penalty=20.0, event_date=None, is_critical=False,
                          is_sanctions=False, observed="no DMARC record"),
        NormalizedFinding(evidence_id=ev.id, source="tls", category="attack_surface_hygiene",
                          signal="hsts", band_key="absent", severity="low", penalty=1.5,
                          effective_penalty=1.5, event_date=None, is_critical=False,
                          is_sanctions=False, observed="no HSTS header"),
    ])


def test_the_pack_route_offers_both_renderings_and_defaults_to_neither(client, store):
    """A default that silently picks an audience is a default that shows a security worklist to a
    procurement reader. The bare route returns the dataset and NAMES the two views."""
    _pack_fixture(store)
    body = client.get("/api/vendors/acme/evidence-request-pack").json()

    assert body["question_count"] == 2
    assert "view=procurement" in body["views"]["procurement"]
    assert "view=security" in body["views"]["security"]
    assert body["per_domain_coverage"], "per-domain coverage missing from the raw pack"
    assert client.get(
        "/api/vendors/acme/evidence-request-pack?view=nonsense").status_code == 422


def test_procurement_view_is_untagged_until_the_relationship_is_declared(client, store):
    """Neither criticality nor data access scope has been declared for this vendor, so no item can
    carry a blocking / condition / informational tag. That is an open question, not a low rating —
    the same refusal E10b makes for the residual cell, for the same reason."""
    _pack_fixture(store)
    body = client.get("/api/vendors/acme/evidence-request-pack?view=procurement").json()

    assert body["audience"] == "procurement"
    assert body["inherent_tier"] is None
    assert {i["decision"] for i in body["items"]} == {"untagged"}
    assert "NOT DECLARED" in body["headline"]
    assert body["inherent_basis"], "a refusal with no stated basis is a silent null"


def test_security_view_is_the_worklist_grouped_by_domain(client, store):
    _pack_fixture(store)
    body = client.get("/api/vendors/acme/evidence-request-pack?view=security").json()

    assert body["audience"] == "security"
    assert body["total_outstanding_points"] == 21.5
    assert body["in_dispute"] == 0
    heaviest = body["groups"][0]
    assert heaviest["category"] == "identity_email" and heaviest["outstanding_points"] == 20.0
    assert heaviest["coverage"]["note"]
    # Every domain appears, including the ones with no work — a category with nothing in it is
    # either clean or unobserved, and a worklist is exactly where somebody may ask which.
    assert len(body["groups"]) >= 7


# --------------------------------------------------------------------- P4 · P5 · P6 routes


def test_contract_flowdowns_route_cites_every_suggestion(client, store):
    """P4. A vendor with no published disclosure route gets ONE suggested protection, cited to the
    finding that argues for it — never a template dumped in full."""
    cr = CollectorResult(source="trust", vendor_ref="acme", status="ok", reliability=0.9,
                         raw={"domain": "acme.com"}, findings=[])
    ev = store.put(cr)
    store.put_findings("acme", [
        NormalizedFinding(evidence_id=ev.id, source="trust", category="transparency",
                          signal="vd_program", band_key="none", severity="medium", penalty=6.0,
                          effective_penalty=6.0, event_date=None, is_critical=False,
                          is_sanctions=False, observed="no disclosure route"),
    ])
    body = client.get("/api/vendors/acme/contract-flowdowns").json()

    assert body["count"] == 1
    row = body["flow_downs"][0]
    assert row["family"] == "no_incident_response_path"
    assert "notification" in row["suggested_protection"]
    assert row["citations"], "a suggestion with no citation is our opinion of the vendor"
    assert any("NOT LEGAL ADVICE" in c for c in body["caveats"])
    assert body["table_version"]


def test_contract_flowdowns_404_before_anything_is_scored(client):
    assert client.get("/api/vendors/ghostco/contract-flowdowns").status_code == 404


def test_assessment_plan_defaults_to_full_depth_when_the_tier_is_undeclared(client, store):
    """P5. Undeclared is NOT T4. Nothing has been declared for this vendor, so the plan is a
    placeholder at full depth on the T2 cadence — and says so rather than presenting as a tier."""
    _pack_fixture(store)
    body = client.get("/api/vendors/acme/assessment-plan").json()

    assert body["declared"] is False
    assert body["inherent_tier"] is None
    assert body["collection"]["depth"] == "full"
    assert body["collection"]["publishes_posture"] is True
    assert body["review_cadence"]["days"] == 182
    assert "not T4" in " ".join(body["caveats"])
    # The soonest re-check on the fixture's findings is 30d, which beats a 182-day cadence.
    assert body["next_action"]["driver"] == "outstanding finding"
    assert len(body["published_table"]) == 4


def test_assessment_plan_publishes_both_clocks_separately(client, store):
    """The review cadence and a finding's re-check date answer different questions. A card that
    prints one number for both is lying about one of them."""
    _pack_fixture(store)
    body = client.get("/api/vendors/acme/assessment-plan").json()
    assert body["review_cadence"]["days"] != body["next_action"]["days"]
    assert "neither replaces the other" in str(body["next_action"]["note"])


def _export_fixture(store):
    _pack_fixture(store)
    store.put_score(_score("acme"))


def test_export_defaults_to_the_whole_record(client, store):
    """P6 must not change what an existing caller gets."""
    _export_fixture(store)
    body = client.get("/api/vendors/acme/export").json()
    assert "reconstruction" in body and "evidence_receipts" in body
    assert "audience" not in body
    assert client.get("/api/vendors/acme/export?view=nonsense").status_code == 422


def test_export_renders_two_audiences_that_agree(client, store):
    """P6's whole risk is two internally-consistent documents quoting different numbers. The
    shipped `views_agree` helper is what the suite runs against the real route output."""
    from app.audience_views import views_agree

    _export_fixture(store)
    proc = client.get("/api/vendors/acme/export?view=procurement").json()
    sec = client.get("/api/vendors/acme/export?view=security").json()

    assert proc["audience"] == "procurement" and sec["audience"] == "security"
    assert views_agree(proc, sec) == []
    assert proc["posture"]["posture"] == sec["posture"]["posture"] == 90


def test_the_procurement_rendering_leads_with_the_decision(client, store):
    _export_fixture(store)
    proc = client.get("/api/vendors/acme/export?view=procurement").json()
    assert proc["section_order"][0] == "decision"
    assert proc["section_order"][-1] == "evidence_request_pack"
    keys = {s["key"] for s in proc["sections"]}
    assert {"residual_risk", "continuity", "concentration", "contract_conditions",
            "monitoring_cadence", "coverage_statement"} <= keys


def test_the_security_rendering_is_the_worklist_with_receipts(client, store):
    _export_fixture(store)
    sec = client.get("/api/vendors/acme/export?view=security").json()
    assert sec["total_outstanding_points"] == 21.5
    assert sec["drilldown"][0]["category"] == "identity_email"
    assert sec["evidence_receipts"], "a worklist without receipts cannot be re-verified"
    assert sec["coverage_statement"], "the limitation must travel on this view too"


# --------------------------------------------------------------------- P7 · P8 joins


def test_status_page_rides_on_the_export_and_the_procurement_continuity_section(client, store):
    """P7's join. A route nobody assembles is a route nobody reads — and "can they keep serving
    us?" is asked in the procurement file, not in a separate tab."""
    _export_fixture(store)

    full = client.get("/api/vendors/acme/export").json()
    assert "status_page" in full
    assert full["status_page"]["found"] is False           # nothing collected in this fixture
    assert "absence of evidence" in full["status_page"]["headline"]

    proc = client.get("/api/vendors/acme/export?view=procurement").json()
    cont = next(s for s in proc["sections"] if s["key"] == "continuity")
    assert cont["body"]["service_availability"] is not None
    # Availability sits BESIDE going-concern standing, never inside it.
    assert cont["body"]["standing"] != cont["body"]["service_availability"].get("indicator")


def test_a_missing_status_page_is_never_read_as_an_outage_record(client, store):
    _export_fixture(store)
    body = client.get("/api/vendors/acme/status-page").json()
    assert body["found"] is False
    assert body["open_incident_count"] == 0
    assert "not a Continuity finding" in body["headline"]
    assert any("COVERAGE GAP" in c for c in body["caveats"])


def test_sole_source_escalates_the_residual_tier_on_the_route(client, store):
    """P8's join into E10b. Declared through the ordinary client-input path, escalated on read,
    and the pre-escalation cell is published alongside so the lookup stays reconstructible."""
    _export_fixture(store)
    store.put_profile(VendorProfile(vendor_ref="acme", criticality="high",
                                    substitutability="sole_source"))

    body = client.get("/api/vendors/acme/residual-risk").json()
    assert body["substitutability"] == "sole_source"
    if body["published"]:
        assert body["escalated_for_sole_source"] is True
        assert body["escalated_from"] is not None
        assert body["escalated_from"] != body["residual"]


def test_sole_source_reaches_the_contract_flow_downs(client, store):
    """The plan says sole source "mandates exit-clause flow-downs". Declared on the profile, the
    clause appears on the route procurement actually reads."""
    _pack_fixture(store)
    store.put_profile(VendorProfile(vendor_ref="acme", substitutability="sole_source"))

    body = client.get("/api/vendors/acme/contract-flowdowns").json()
    families = [f["family"] for f in body["flow_downs"]]
    assert "sole_source_exit_rights" in families
    row = next(f for f in body["flow_downs"] if f["family"] == "sole_source_exit_rights")
    assert "escrow" in row["suggested_protection"]
    assert "client-declared" in row["citations"][0]


def test_exit_readiness_raises_the_alert_the_plan_calls_the_most_useful(client, store):
    """`sole_source × poor Posture` — a critical dependency, no fallback, weak observable
    controls, all three at once."""
    _pack_fixture(store)
    store.put_score(Score(vendor_ref="acme", blocked=False, posture=25, grade="F",
                          overall_confidence=0.8, confidence_band="Medium", refused=False))
    store.put_profile(VendorProfile(vendor_ref="acme", substitutability="sole_source"))

    body = client.get("/api/vendors/acme/exit-readiness").json()
    assert body["substitutability"] == "sole_source"
    assert body["alert_level"] == "critical"
    assert "SOLE SOURCE, POOR POSTURE" in body["headline"]
    assert body["not_derivable_from_osint"]["items"]


# --------------------------------------------------------------------- P9 · the programme


def test_program_maturity_is_the_minimum_and_names_its_limiters(client):
    """P9 asks a different question from every other route: not how is this vendor doing, but how
    good is our programme. It takes no vendor and reads no store."""
    body = client.get("/api/program/maturity").json()

    assert len(body["dimensions"]) == 8
    levels = [d["level"] for d in body["dimensions"]]
    assert body["overall_level"] == min(levels)
    assert body["overall_level"] < sum(levels) / len(levels)
    assert body["overall_rule"] == "minimum across dimensions, never the average"
    assert body["limiting_dimensions"]
    for d in body["dimensions"]:
        assert d["rationale"] and d["evidence"] and d["to_reach_next"]


def test_program_kpis_compute_against_a_real_store(client, store):
    """Twelve metrics computed from what the platform already produces — no new collection.

    E14 argued `stakeholder_satisfaction` (manually-supplied) out in favour of
    `gap_analysis_acceptance_rate` (platform-derived, read from the recommendation event log the
    feature already keeps for its own audit trail) — see program_kpis.py for the reasoning.
    """
    _export_fixture(store)
    body = client.get("/api/program/kpis").json()

    assert body["metric_count"] == 15
    assert body["platform_derived"] == 12
    assert body["manually_supplied"] == 3

    by_key = {m["key"]: m for m in body["metrics"]}
    assert by_key["published_posture_rate"]["value"] == 100.0     # one vendor, published
    assert by_key["ghost_rate"]["value"] == 0.0
    assert by_key["blocked_pending_adjudication"]["value"] == 0
    assert by_key["assessment_cycle_time_median"]["value"] is not None
    # The residual distribution is counted over RELATIONSHIPS, and a synthetic fixture vendor is on
    # nobody's inventory — so the distribution is legitimately empty here. It read
    # `{not_published: 146}` against the live book before the denominator was corrected, which was
    # a census of the wrong population rather than a distribution.
    assert by_key["residual_risk_distribution"]["value"] == {}
    assert by_key["residual_risk_distribution"]["detail"]["relationships"] == 0


def test_the_declaration_rate_reports_the_gap_rather_than_hiding_it(client, store):
    """The metric chosen because the programme is bad at it: residual risk, P3's decision tag and
    P5's cadence all degrade silently to "not declared" without this input.

    ON A FIXTURE BOOK IT IS NOT COMPUTABLE, AND THAT IS NOT THE SAME AS 0%. The denominator is the
    register's RELATIONSHIP population, and a synthetic vendor is on nobody's inventory — so there
    is no population to take a percentage of. Reporting 0% here would send somebody to chase
    relationship owners who have nothing to answer, which is the specific way a wrong empty-cell
    reason does damage: the reader stops asking.
    """
    _export_fixture(store)
    body = client.get("/api/program/kpis").json()
    row = next(m for m in body["metrics"] if m["key"] == "inherent_tier_declaration_rate")

    assert row["value"] is None
    assert "NO POPULATION TO MEASURE" in row["unavailable_reason"]
    assert "not on the register at all" in row["unavailable_reason"]
    assert row["detail"]["unregistered"], "an unregistered vendor must be named, not counted away"
    assert row["owner"] and row["formula"] and row["target"]
    assert "inherent_tier_declaration_rate" in body["not_computable"]


def test_unsupplied_manual_metrics_are_empty_and_never_estimated(client, store):
    _export_fixture(store)
    body = client.get("/api/program/kpis").json()

    manual = [m for m in body["metrics"] if m["provenance"] == "manually-supplied"]
    assert len(manual) == 3
    for m in manual:
        assert m["value"] is None
        assert "NOT SUPPLIED" in m["unavailable_reason"]
        assert m["owner"] in m["unavailable_reason"]
    assert set(body["unsupplied"]) >= {m["key"] for m in manual}


def test_the_program_page_serves_both_halves_and_reaches_no_vendor_score(client, store):
    _export_fixture(store)
    body = client.get("/api/program").json()

    assert "maturity" in body and "kpis" in body
    assert body["maturity"]["overall_level"] == \
        client.get("/api/program/maturity").json()["overall_level"]
    assert "reaches any vendor score" in body["note"]

    # ...and the vendor's own score is untouched by any of it.
    assert client.get("/api/vendors/acme").json()["posture"] == 90
