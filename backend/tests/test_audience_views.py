"""P6 — one immutable score object, two renderings.

The risk a split rendering introduces is not that one view is wrong; it is that BOTH are internally
consistent and quote different numbers, or that a limitation lands on one page and not the other.
So most of what is pinned here is agreement rather than content:

  * neither view may publish a posture the other lacks,
  * neither may publish one at all when the record is blocked or refused,
  * the coverage statement travels on both,
  * and the module holds no arithmetic, so there is nothing that COULD diverge.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.audience_views import procurement_dossier, security_dossier, views_agree


def _score(**over):
    base = dict(
        posture=71, grade="C", overall_confidence=0.81, confidence_band="Medium",
        blocked=False, blocked_reason=None, refused=False, ghost=False,
        critical_ceiling_applied=False, confidence_ceiling_applied=False,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _continuity(standing="sound"):
    flag = SimpleNamespace(cited=lambda: "The register records this entity as active — GLEIF.")
    return SimpleNamespace(standing=standing, flags=[flag], age_context=["Operating 12 years."],
                           caveats=["Continuity is not scored."])


_COVERAGE = {"signals_covered": 21, "signals_planned": 27, "held": ["insurance"]}
_PACK = {"vendor_ref": "acme", "question_count": 3}


def _findings():
    return [
        {"signal": "dmarc", "band_key": "absent", "severity": "high", "observed": "none",
         "effective_penalty": 17.5, "category": "identity_email", "evidence_id": "ev-1",
         "reason": "No DMARC policy.", "action": "Publish p=reject.",
         "ask_of_vendor": "Send your DMARC record.", "accepts_as_refute": "A p=reject record.",
         "recheck_after": "30d", "dispute_status": None},
        {"signal": "hsts", "band_key": "absent", "severity": "medium", "observed": "absent",
         "effective_penalty": 6.0, "category": "attack_surface_hygiene", "evidence_id": "ev-2",
         "reason": "No HSTS.", "action": "Add the header.", "ask_of_vendor": "Confirm HSTS.",
         "accepts_as_refute": "A response carrying HSTS.", "recheck_after": "90d",
         "dispute_status": "mitigate"},
        {"signal": "cert_validity", "band_key": "valid", "severity": "informational",
         "observed": "valid", "effective_penalty": 0.0, "category": "attack_surface_hygiene",
         "evidence_id": "ev-3", "reason": None, "action": None, "ask_of_vendor": None,
         "accepts_as_refute": None, "recheck_after": None, "dispute_status": None},
    ]


def _proc(score=None, **over):
    kwargs = dict(
        vendor_ref="acme", score=score or _score(),
        recommendation={"decision": "approve_with_conditions", "headline": "Proceed with conditions"},
        residual={"published": True, "residual": "high", "residual_label": "High"},
        continuity=_continuity(), concentration=[],
        flowdowns={"count": 0, "flow_downs": []},
        assessment_plan={"tier_label": "T2 Important", "review_cadence": {"days": 182}},
        coverage=_COVERAGE, evidence_pack=_PACK,
    )
    kwargs.update(over)
    return procurement_dossier(**kwargs)


def _sec(score=None, **over):
    kwargs = dict(
        vendor_ref="acme", score=score or _score(), findings=_findings(),
        receipts=[{"evidence_id": "ev-1", "source": "dns"}],
        category_postures=[{"category": "identity_email", "posture": 40}],
        peer_signals=[{"signal": "dmarc", "peers_passing": 6, "peers": 8}],
        evidence_pack=_PACK, coverage=_COVERAGE,
        assessment_plan={"tier_label": "T2 Important"}, soonest_recheck="30d",
    )
    kwargs.update(over)
    return security_dossier(**kwargs)


# ============================================================ the ordering IS the design


def test_procurement_leads_with_the_decision_and_ends_with_the_ask():
    """A reader who stops halfway must have stopped AFTER the decision and the exposure it was made
    against — never before them, and never on a task list."""
    assert _proc()["section_order"] == [
        "decision", "residual_risk", "continuity", "concentration",
        "contract_conditions", "monitoring_cadence", "coverage_statement",
        "evidence_request_pack",
    ]


def test_procurement_is_not_handed_a_per_signal_worklist():
    """Not secrecy — /export serves the whole record. Twenty-eight rows of DNS minutiae in front of
    a signer produces a decision made on the first row, or a skipped page."""
    body = _proc()
    assert "drilldown" not in body
    keys = {s["key"] for s in body["sections"]}
    assert "findings" not in keys


def test_security_is_not_handed_a_decision_banner():
    """The decision is not theirs and it does not change what needs fixing."""
    body = _sec()
    assert "recommendation" not in body
    assert "residual_risk" not in body


# ============================================================ the two must not diverge


def test_the_two_views_agree_on_every_published_figure():
    assert views_agree(_proc(), _sec()) == []


def test_views_agree_actually_catches_a_divergence():
    """A guard that cannot fail is not a guard. Hand it two views of different scores."""
    problems = views_agree(_proc(), _sec(score=_score(posture=40, grade="D")))
    assert any("posture" in p for p in problems)
    assert any("grade" in p for p in problems)


def test_views_agree_catches_a_limitation_that_landed_on_only_one_page():
    """The failure this whole helper exists for, and the one that is wrong in the dangerous
    direction every time: the person who SIGNS never learns what the assessment could not see."""
    problems = views_agree(_proc(), _sec(coverage={"signals_covered": 0}))
    assert any("coverage statement differs" in p for p in problems)


@pytest.mark.parametrize("state", [
    {"refused": True, "posture": 12},
    {"blocked": True, "blocked_reason": "Sanctions match pending adjudication.", "posture": 30},
])
def test_neither_view_publishes_a_number_for_a_refusal_or_a_block(state):
    """A refusal rendered as a low number is the single most dangerous transformation this system
    could perform, and a 'friendlier for procurement' rendering is exactly where it would appear."""
    score = _score(**state)
    for body in (_proc(score=score), _sec(score=score)):
        assert body["posture"]["posture"] is None
        assert body["posture"]["grade"] is None
        assert body["posture"]["published"] is False
        assert body["posture"]["not_published_because"]
    assert views_agree(_proc(score=score), _sec(score=score)) == []


def test_confidence_survives_a_refusal_on_both_views():
    """Posture goes; confidence stays. It is the axis that EXPLAINS the refusal, so dropping it
    would leave a reader with a blank where the reason is."""
    score = _score(refused=True, overall_confidence=0.22, confidence_band="Low")
    for body in (_proc(score=score), _sec(score=score)):
        assert body["posture"]["confidence"] == 0.22
        assert body["posture"]["confidence_band"] == "Low"


def test_the_shared_caveats_are_on_both_renderings():
    proc, sec = " ".join(_proc()["caveats"]), " ".join(_sec()["caveats"])
    for phrase in ("THREE SEPARATE MEASUREMENTS", "OUTSIDE-IN", "coverage statement"):
        assert phrase in proc and phrase in sec


# ============================================================ the security worklist


def test_the_worklist_is_ordered_by_what_it_is_worth_and_grouped_by_who_owns_it():
    groups = _sec()["drilldown"]
    assert [g["category"] for g in groups] == ["identity_email", "attack_surface_hygiene"]
    assert groups[0]["outstanding_points"] == 17.5


def test_a_finding_that_cost_nothing_is_not_on_the_worklist():
    """...and the caveat says where it went, so the front-page arithmetic still balances."""
    signals = [f["signal"] for g in _sec()["drilldown"] for f in g["findings"]]
    assert "cert_validity" not in signals
    assert _sec()["total_outstanding_points"] == 23.5
    assert any("still balances" in c for c in _sec()["caveats"])


def test_every_row_carries_its_receipt_its_ask_and_its_dispute_state():
    rows = {f["signal"]: f for g in _sec()["drilldown"] for f in g["findings"]}
    assert rows["dmarc"]["evidence_id"] == "ev-1"
    assert rows["dmarc"]["accepts_as_refute"] == "A p=reject record."
    assert rows["hsts"]["dispute_status"] == "mitigate"
    assert rows["dmarc"]["dispute_status"] is None


def test_peer_prevalence_rides_on_the_finding_it_describes():
    rows = {f["signal"]: f for g in _sec()["drilldown"] for f in g["findings"]}
    assert rows["dmarc"]["peer_prevalence"] == {"signal": "dmarc", "peers_passing": 6, "peers": 8}
    assert rows["hsts"]["peer_prevalence"] is None
    assert any("MOVES NOTHING" in c for c in _sec()["caveats"])


# ============================================================ no second source of truth


def test_the_assembly_module_holds_no_arithmetic_on_a_posture():
    """THE INVARIANT. The moment this module computes rather than copies, the two views can
    disagree with each other and with /export, and a reader has no way to tell which is right.

    Rounding a SUM OF PENALTIES that was handed over already computed is arrangement, not
    derivation, so `sum(...)` and `round(...)` are allowed. What is refused is any operator applied
    to a posture, a grade or a confidence.
    """
    tree = ast.parse(Path("app/audience_views.py").read_text(encoding="utf-8"))
    posture_words = {"posture", "grade", "confidence", "overall_confidence"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp):
            continue
        names = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
        names |= {n.value for n in ast.walk(node) if isinstance(n, ast.Constant)
                  and isinstance(n.value, str)}
        assert not (posture_words & names), f"arithmetic on a published figure: {ast.dump(node)}"


def test_the_assembly_module_reaches_no_store_and_no_engine():
    """It arranges what it is handed. A module that can fetch can also fetch something different
    from what the caller already rendered, which is how two views of one vendor drift apart."""
    tree = ast.parse(Path("app/audience_views.py").read_text(encoding="utf-8"))
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert imported <= {"__future__", "typing"}, f"unexpected imports: {imported}"
