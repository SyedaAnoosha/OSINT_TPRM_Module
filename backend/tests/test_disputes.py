"""Phase 4 — the vendor dispute / refute path.

Three things carry the weight here:
  * the engine applies an accepted refute correctly — nullify zeroes the penalty and disarms the
    ceiling, mitigate finally drives the dormant NIST ×0.6 factor, and both are marked on the
    finding so a discounted deduction says why;
  * disputes are append-only EVENTS whose current state is the latest one, so an acceptance can be
    superseded and a rejection drops out;
  * the API validates a dispute against the real findings, and only an ACCEPTED refute re-scores.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app import api as api_mod
from app.api import app, store_dep
from app.models import CollectorResult, Dispute, Finding, Vendor
from app.scoring import ScoringEngine

# --------------------------------------------------------------------- engine semantics


# EVERY signal in the model, passing. This used to be a partial list, sized only to clear
# `refuse_below` (0.4) so that a posture published at all. Since E7d that is not enough: coverage
# also CAPS the published number, and at ~50% coverage the cap was 80 — so nullifying a finding
# moved the arithmetic from 98 to 100 and the published posture not at all. Both dispute tests
# failed on `80 > 80`, measuring the ceiling rather than the dispute.
#
# The declared categories are routing hints only (E5: the model resolves a signal's home), which
# is why the stale pre-E5 names here did no harm — but they are corrected anyway, because a
# reader should not have to know that to trust the fixture.
_PASSING = [
    ("attack_surface_hygiene", "tls_version", "tls_13"),
    ("attack_surface_hygiene", "cert_validity", "valid"),
    ("attack_surface_hygiene", "hsts", "present"),
    ("attack_surface_hygiene", "csp", "present"),
    ("attack_surface_hygiene", "x_frame_opts", "present"),
    ("attack_surface_hygiene", "dnssec", "valid"),
    ("attack_surface_hygiene", "caa", "present"),
    ("attack_surface_hygiene", "weak_issuance", "none"),
    ("identity_email", "spf", "hardfail_all"),
    ("identity_email", "dkim", "present"),
    ("identity_email", "dmarc", "p_reject"),
    ("breach_compromise_history", "kev_listed_cve", "no_kev_match"),
    ("breach_compromise_history", "nvd_cve", "no_critical_cve"),
    ("breach_compromise_history", "breach_by_data_class", "no_known_breach"),
    ("transparency", "vd_program", "bug_bounty"),
    ("transparency", "security_txt", "present"),
    ("compliance_regulatory", "cert_posture", "registry_corroborated"),
    ("compliance_regulatory", "regulator_action", "no_action_found"),
    ("continuity_context", "entity_status", "active_good_standing"),
    ("continuity_context", "entity_existence", "entity_active_confirmed"),
    ("continuity_context", "entity_maturity", "mature_gt_10"),
    ("continuity_context", "domain_registration", "domain_established"),
    ("assurance_context", "program_disclosure", "detailed_policies"),
    ("assurance_context", "contactability", "dpo_and_security_contact"),
    ("assurance_context", "reporting_posture", "substantive"),
]
# Count signals need a raw count, not a band, or they normalise as unmapped.
_PASSING_COUNTS = {"stale_hosts": 0, "subdomain_estate": 6}


def _results(*bands: tuple[str, str, str, str]) -> list[CollectorResult]:
    """A one-collector result with the given (category, signal, band, observed) findings, padded
    with passing signals so coverage clears the Ghost threshold and a posture publishes."""
    findings = [Finding(source="dns", signal=sig, category=cat, observed=obs,
                        value={"band": band}) for cat, sig, band, obs in bands]
    findings += [Finding(source="dns", signal=sig, category=cat, observed="ok",
                         value={"band": band})
                 for cat, sig, band in _PASSING
                 if not any(b[1] == sig for b in bands)]
    findings += [Finding(source="dns", signal=sig, category="attack_surface_hygiene",
                         observed=str(n), value={"count": n})
                 for sig, n in _PASSING_COUNTS.items()
                 if not any(b[1] == sig for b in bands)]
    return [CollectorResult(source="dns", vendor_ref="acme", status="ok",
                            findings=findings, reliability=0.9)]


def test_nullify_zeroes_the_penalty_and_marks_the_finding():
    results = _results(("cyber_hygiene_technical", "dmarc", "absent", "no DMARC"))
    base = ScoringEngine().score(Vendor(ref="acme"), results).score
    nulled = ScoringEngine().score(Vendor(ref="acme"), results,
                                   disputes={("dmarc", "absent"): "nullify"}).score
    assert nulled.posture > base.posture
    nf = [n for n in ScoringEngine().score(Vendor(ref="acme"), results,
          disputes={("dmarc", "absent"): "nullify"}).normalized if n.signal == "dmarc"][0]
    assert nf.dispute == "nullified"
    assert nf.penalty == 0.0


def test_mitigate_drives_the_dormant_nist_factor():
    """The ×0.6 mitigation modifier was wired end-to-end but DORMANT — nothing free evidences a fix.
    A human-adjudicated refute is that evidence, and this is the first thing that sets it."""
    results = _results(("cyber_hygiene_technical", "dmarc", "absent", "no DMARC"))
    nf = [n for n in ScoringEngine().score(Vendor(ref="acme"), results,
          disputes={("dmarc", "absent"): "mitigate"}).normalized if n.signal == "dmarc"][0]
    assert nf.dispute == "mitigated"
    assert nf.remediation_evidenced is True     # this is what the ×0.6 factor keys off


def test_mitigate_and_nullify_differ_on_a_large_finding():
    """On a big penalty the two outcomes are visibly different: nullify removes it, mitigate keeps
    60% of it."""
    results = _results(("breach_compromise_history", "breach_by_data_class",
                        "passwords_or_cards", "credential breach"))
    base = ScoringEngine().score(Vendor(ref="acme"), results).score.posture
    mit = ScoringEngine().score(Vendor(ref="acme"), results,
                                disputes={("breach_by_data_class", "passwords_or_cards"): "mitigate"}).score.posture
    nul = ScoringEngine().score(Vendor(ref="acme"), results,
                                disputes={("breach_by_data_class", "passwords_or_cards"): "nullify"}).score.posture
    assert base < mit < nul


def test_nullify_disarms_the_critical_ceiling():
    """A directly-observed critical caps the grade — unless the vendor evidences it does not apply.
    An attribution error on the one finding driving the ceiling should lift it."""
    results = _results(("cyber_hygiene_technical", "cert_validity", "expired_serving_prod",
                        "expired cert"))
    capped = ScoringEngine().score(Vendor(ref="acme"), results).score
    lifted = ScoringEngine().score(Vendor(ref="acme"), results,
                                   disputes={("cert_validity", "expired_serving_prod"): "nullify"}).score
    assert capped.critical_ceiling_applied is True
    assert lifted.critical_ceiling_applied is False


def test_a_dispute_only_matches_its_exact_observation():
    """Keyed to (signal, band): a refute for `absent` does nothing once the band is `p_none`. This
    is what makes an accepted dispute self-expire when the next scan changes."""
    results = _results(("cyber_hygiene_technical", "dmarc", "p_none", "p=none"))
    scored = ScoringEngine().score(Vendor(ref="acme"), results,
                                   disputes={("dmarc", "absent"): "nullify"}).score
    base = ScoringEngine().score(Vendor(ref="acme"), results).score
    assert scored.posture == base.posture     # the stale refute didn't apply


def test_disputes_never_touch_sanctions():
    """The sanctions gate is human by law (s 16(7)), not by refute — a dispute cannot clear it."""
    findings = [Finding(source="ita", signal="sanctions_hit",
                        category="regulatory_legal_sanctions", observed="SDN match",
                        value={"band": "match"})]
    results = [CollectorResult(source="ita", vendor_ref="acme", status="ok",
                               findings=findings, reliability=0.9)]
    blocked = ScoringEngine().score(Vendor(ref="acme"), results,
                                    disputes={("sanctions_hit", "match"): "nullify"}).score
    assert blocked.blocked is True            # still blocked; the refute was ignored


# --------------------------------------------------------------------- store: append-only events


@pytest.fixture
def client(store):
    app.dependency_overrides[store_dep] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def _event(store, did, event, signal="dmarc", band="absent", kind="mitigate"):
    store.put_dispute(Dispute(
        id=uuid.uuid4().hex, dispute_id=did, vendor_ref="acme", event=event,
        signal=signal, band_key=band, kind=kind, evidence="a SOC 2 report", content_hash=""))


def test_accepted_targets_reflect_the_latest_event(store):
    did = "d1"
    _event(store, did, "submitted")
    assert store.accepted_dispute_targets("acme") == {}
    _event(store, did, "accepted")
    assert store.accepted_dispute_targets("acme") == {("dmarc", "absent"): "mitigate"}


def test_a_rejected_dispute_does_not_apply(store):
    _event(store, "d2", "submitted")
    _event(store, "d2", "rejected")
    assert store.accepted_dispute_targets("acme") == {}


def test_the_full_event_history_is_retained(store):
    _event(store, "d3", "submitted")
    _event(store, "d3", "accepted")
    events = [d.event for d in store.disputes_for_vendor("acme")]
    assert events == ["submitted", "accepted"]   # nothing overwritten


def test_disputes_are_append_only(store):
    _event(store, "d4", "submitted")
    import psycopg
    with pytest.raises(psycopg.errors.RaiseException):
        store._conn.execute("UPDATE disputes SET event='accepted' WHERE dispute_id='d4'")
    with pytest.raises(psycopg.errors.RaiseException):
        store._conn.execute("DELETE FROM disputes WHERE dispute_id='d4'")


# --------------------------------------------------------------------- API flow


def _seed_scored_vendor(store):
    """A vendor with one penalising finding and a domain, so a dispute has something to target and
    a re-score can reconstruct the vendor."""
    from app.models import Score
    store.put(CollectorResult(source="dns", vendor_ref="acme", status="ok",
                              raw={"domain": "acme.com"}, reliability=0.9))
    store.put_score(Score(vendor_ref="acme", posture=70, grade="B",
                          overall_confidence=0.9, confidence_band="High"))
    store.put_findings("acme", ScoringEngine().score(
        Vendor(ref="acme"),
        _results(("cyber_hygiene_technical", "dmarc", "absent", "no DMARC")),
    ).normalized, run_id="run-1")


def test_submit_validates_against_real_findings(client, store):
    _seed_scored_vendor(store)
    # a finding that is on the card can be disputed
    ok = client.post("/api/vendors/acme/disputes",
                     json={"signal": "dmarc", "band_key": "absent", "kind": "mitigate",
                           "evidence": "DMARC deployed at p=reject, screenshot attached"})
    assert ok.status_code == 201
    assert ok.json()["status"] == "submitted"
    # a finding that is NOT on the card cannot
    bad = client.post("/api/vendors/acme/disputes",
                      json={"signal": "kev_listed_cve", "band_key": "listed", "kind": "nullify",
                            "evidence": "not us"})
    assert bad.status_code == 409


def test_reject_records_but_does_not_rescore(client, store, monkeypatch):
    _seed_scored_vendor(store)
    did = client.post("/api/vendors/acme/disputes",
                      json={"signal": "dmarc", "band_key": "absent", "kind": "mitigate",
                            "evidence": "x"}).json()["dispute_id"]

    called = {"rescored": False}

    async def _fake_pipeline(*a, **k):  # noqa: ANN002, ANN003
        called["rescored"] = True
        raise AssertionError("reject must not re-score")

    monkeypatch.setattr(api_mod, "run_pipeline", _fake_pipeline)
    r = client.post(f"/api/disputes/{did}/adjudicate",
                    json={"decision": "reject", "note": "evidence insufficient"})
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"
    assert called["rescored"] is False
    assert store.accepted_dispute_targets("acme") == {}


def test_accept_rescores_with_the_refute_applied(client, store, monkeypatch):
    _seed_scored_vendor(store)
    did = client.post("/api/vendors/acme/disputes",
                      json={"signal": "dmarc", "band_key": "absent", "kind": "mitigate",
                            "evidence": "DMARC now enforced"}).json()["dispute_id"]

    seen = {}

    async def _fake_pipeline(vendor, **k):  # noqa: ANN001, ANN003
        # by the time the re-score runs, the acceptance is recorded and visible to the engine
        seen["targets"] = store.accepted_dispute_targets("acme")
        from app.models import Score
        from app.scoring.engine import ScoreResult
        return ScoreResult(score=Score(vendor_ref="acme", posture=73, grade="B",
                                       overall_confidence=0.9, confidence_band="High"),
                           normalized=[])

    monkeypatch.setattr(api_mod, "run_pipeline", _fake_pipeline)
    r = client.post(f"/api/disputes/{did}/adjudicate",
                    json={"decision": "accept", "note": "verified"})
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"
    assert r.json()["rescored"]["posture"] == 73
    assert seen["targets"] == {("dmarc", "absent"): "mitigate"}


def test_a_resolved_dispute_cannot_be_adjudicated_again(client, store, monkeypatch):
    _seed_scored_vendor(store)
    did = client.post("/api/vendors/acme/disputes",
                      json={"signal": "dmarc", "band_key": "absent", "kind": "nullify",
                            "evidence": "that host is our CDN"}).json()["dispute_id"]
    monkeypatch.setattr(api_mod, "run_pipeline",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError()))
    client.post(f"/api/disputes/{did}/adjudicate", json={"decision": "reject", "note": "no"})
    again = client.post(f"/api/disputes/{did}/adjudicate", json={"decision": "accept", "note": "y"})
    assert again.status_code == 409


def test_list_disputes_shows_state_and_history(client, store):
    _seed_scored_vendor(store)
    client.post("/api/vendors/acme/disputes",
                json={"signal": "dmarc", "band_key": "absent", "kind": "mitigate",
                      "evidence": "e"})
    body = client.get("/api/vendors/acme/disputes").json()
    assert len(body["disputes"]) == 1
    assert body["disputes"][0]["status"] == "submitted"
    assert body["disputes"][0]["history"][0]["event"] == "submitted"
