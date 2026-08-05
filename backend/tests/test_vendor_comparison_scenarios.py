"""Vendor comparison scenarios — Phase 2 of docs/tprm_feedback_redesign.md.

Nine numbered scenarios (ten test functions — scenario 2 has a companion 2b isolating the new
Business Stability collectors specifically), each demonstrating one thing the scoring model must
get right —
written as executable tests against the REAL scoring.yaml (never a mock), matching the convention
in test_scoring.py. Each scenario also has a plain-English writeup in
docs/vendor_comparison_scenarios.md so procurement/security/exec stakeholders can review the same
acceptance criteria without reading Python.

Two scenarios below deliberately DIVERGE from a naive reading of the original feedback request:

  * "Adverse media" is implemented via `breach_by_data_class` (a REAL scored signal), not GDELT.
    GDELT-sourced adverse media is enrichment/review-queue only today (`held`/`ai_adjudicated`,
    per docs/source_assessment.md) — it does not reach scoring.yaml and cannot move posture. A
    scenario asserting otherwise would be testing a signal that doesn't exist in the shipped
    model. Scenario 1 tests the real breach-history signal and states the GDELT gap explicitly.
  * The "compounding findings" scenario uses two signals in the SAME category
    (`attack_surface_hygiene`), not signals spanning categories. `aggregation_decay` (E7a) applies
    WITHIN a category, never across (scoring.yaml `aggregation:` block) — a cross-category
    "expired cert + no DMARC" pairing would not exercise decay at all.
"""

from __future__ import annotations

import pytest

from app.models import CollectorResult, Finding, Vendor
from app.scoring import ScoringEngine
from app.scoring_config import get_scoring_config

# Category keys as scoring.yaml defines them (matches test_scoring.py's constants).
H = "attack_surface_hygiene"
E = "identity_email"
B = "breach_compromise_history"
T = "transparency"
K = "compliance_regulatory"
X = "continuity_context"
A = "assurance_context"
_SANCTIONS_CATEGORY = "regulatory_legal_sanctions"


def _vendor(conf: float = 1.0) -> Vendor:
    return Vendor(ref="acme", name="Acme", domain="acme.example",
                  resolved=True, resolution_confidence=conf)


def _result(source: str, findings: list[Finding], status: str = "ok", rel: float = 0.9) -> CollectorResult:
    return CollectorResult(source=source, vendor_ref="acme", status=status,  # type: ignore[arg-type]
                           source_version="test", raw={"t": 1}, findings=findings, reliability=rel)


def _f(signal, cat, band, value=None) -> Finding:  # noqa: ANN001
    return Finding(source="t", signal=signal, subcategory=signal, category=cat,
                   observed=band, value=value or {"band": band})


_HYGIENE_CLEAN = {
    "tls_version": "tls_13", "cert_validity": "valid", "dmarc": "p_reject", "spf": "hardfail_all",
    "dkim": "present", "hsts": "present", "csp": "present", "x_frame_opts": "present",
    "security_txt": "present", "dnssec": "valid", "caa": "present",
}


def _hygiene(overrides: dict | None = None) -> list[Finding]:
    bands = {**_HYGIENE_CLEAN, **(overrides or {})}
    return [_f(sig, H, band) for sig, band in bands.items()]


_ALL_CLEAN = {
    **_HYGIENE_CLEAN,
    "subdomain_estate": "small", "stale_hosts": "none", "weak_issuance": "none",
    "breach_by_data_class": "no_known_breach", "kev_listed_cve": "no_kev_match",
    "nvd_cve": "no_critical_cve",
    "vd_program": "bug_bounty",
    "cert_posture": "registry_corroborated", "regulator_action": "no_action_found",
    "entity_status": "active_good_standing", "entity_existence": "entity_active_confirmed",
    "entity_maturity": "mature_gt_10", "domain_registration": "domain_established",
    "program_disclosure": "detailed_policies", "contactability": "dpo_and_security_contact",
    "reporting_posture": "substantive",
}


def _all_clean(overrides: dict | None = None) -> list[Finding]:
    bands = {**_ALL_CLEAN, **(overrides or {})}
    return [_f(sig, H, band) for sig, band in bands.items()]


# ============================================================================================
# Scenario 1 — severe breach history vs none
# ============================================================================================

def test_scenario_1_severe_breach_history_vs_none():
    """Vendor A: confirmed breach exposing passwords/cards (the most severe `breach_by_data_class`
    band), on an otherwise-clean baseline. Vendor B: identical baseline, no known breach. A must
    score materially lower on `breach_compromise_history`, and posture overall.

    Both vendors carry the full `_all_clean()` baseline rather than the single breach finding
    alone — thin coverage triggers the confidence-ceiling (scenario 6): it caps PUBLISHED posture
    at 80 regardless of the underlying penalty, which would clip both sides to the same visible
    80 and hide the very difference this scenario exists to show. Full coverage keeps the
    comparison honest."""
    a = ScoringEngine().score(_vendor(), [
        _result("multi", _all_clean({"breach_by_data_class": "passwords_or_cards"}))]).score
    b = ScoringEngine().score(_vendor(), [_result("multi", _all_clean())]).score

    assert a.posture < b.posture
    cat_a = next(c for c in a.categories if c.category == B)
    cat_b = next(c for c in b.categories if c.category == B)
    assert cat_a.penalty > 0
    assert cat_b.penalty == 0


def test_scenario_1b_gdelt_adverse_media_does_not_move_posture_today():
    """The explicit gap: GDELT-sourced adverse media is enrichment-only (`held`/`ai_adjudicated`,
    source_assessment.md) — it has no signal declared in scoring.yaml, so a collector emitting one
    is silently dropped by the normalizer rather than scored. This is a fact worth stating to
    stakeholders directly, not leaving implicit."""
    cfg = get_scoring_config()
    assert cfg.category_of("adverse_media") is None
    assert cfg.category_of("tone_volume") is None  # the actual signal name GDELT emits today


# ============================================================================================
# Scenario 2 — bankrupt vs financially healthy vendor (Business Stability)
# ============================================================================================

def test_scenario_2_bankrupt_vs_healthy_posture_is_byte_identical():
    """THE central regression guard for the whole Business Stability feature
    (docs/tprm_feedback_redesign.md §1.3, extending E4/change-notice-v5.md §3.4). All cyber
    signals held identical; only the financial-standing evidence differs (`entity_status`, the
    Companies House going-concern signal — the exact one E4 removed from Posture). Posture AND
    confidence must be byte-identical — financial distress is real and must be visible (via
    Continuity), but it must never touch the security number.

    Same `entity_status` SIGNAL both sides, different BAND — not a different signal — because
    that is the controlled comparison: swapping signals (e.g. this vendor's `entity_status` for a
    different vendor's `bankruptcy_petition`) would also swap which coverage axis each side counts
    toward (`entity_status` counts toward Posture confidence; the new `bankruptcy_petition` is
    deliberately excluded from it — scenario 2b below), confounding the comparison this scenario
    exists to make."""
    cyber = _hygiene()
    bankrupt_score = ScoringEngine().score(_vendor(), [
        _result("dns", cyber),
        _result("companies_house", [_f("entity_status", X, "entity_inactive")]),
    ]).score
    healthy_score = ScoringEngine().score(_vendor(), [
        _result("dns", cyber),
        _result("companies_house", [_f("entity_status", X, "active_good_standing")]),
    ]).score

    assert bankrupt_score.posture == healthy_score.posture
    assert bankrupt_score.overall_confidence == healthy_score.overall_confidence
    assert bankrupt_score.grade == healthy_score.grade

    from app.continuity import continuity_report
    from app.models import PersistedFinding
    from datetime import UTC, datetime

    def _pf(signal, band, source):
        return PersistedFinding(
            id="f1", vendor_ref="acme", source=source, category=X, signal=signal, band_key=band,
            severity="informational", penalty=0.0, observed=band,
            content_hash="0" * 64, stored_at=datetime(2026, 8, 4, tzinfo=UTC),
        )

    bankrupt_standing = continuity_report(
        "acme", [_pf("entity_status", "entity_inactive", "companies_house")]).standing
    healthy_standing = continuity_report(
        "acme", [_pf("entity_status", "active_good_standing", "companies_house")]).standing
    assert bankrupt_standing == "ceased"
    assert healthy_standing == "sound"
    assert bankrupt_standing != healthy_standing  # the difference IS visible — just not in posture


def test_scenario_2b_new_business_stability_collectors_follow_the_same_invariant():
    """The NEW signals specifically (Gazette/EDGAR/CourtListener, not the pre-existing
    `entity_status`): a `bankruptcy_petition` finding is excluded from Posture confidence
    entirely (`ScoringConfig.business_stability_signals`), so adding one changes NEITHER posture
    NOR confidence versus not having collected it at all — the per-axis design from
    docs/tprm_feedback_redesign.md §1.3, built after scenario 2's original all-in-one-denominator
    version broke the frozen regression corpus (see test_scoring.py::
    test_business_stability_signals_cannot_move_posture_or_confidence for the full guard)."""
    cyber = _hygiene()
    without = ScoringEngine().score(_vendor(), [_result("dns", cyber)]).score
    with_bankruptcy = ScoringEngine().score(_vendor(), [
        _result("dns", cyber),
        _result("courtlistener_bankruptcy", [_f("bankruptcy_petition", X, "entity_inactive")]),
    ]).score

    assert without.posture == with_bankruptcy.posture
    assert without.overall_confidence == with_bankruptcy.overall_confidence

    from app.continuity import continuity_report
    from app.models import PersistedFinding
    from datetime import UTC, datetime

    flag = PersistedFinding(
        id="f1", vendor_ref="acme", source="courtlistener_bankruptcy", category=X,
        signal="bankruptcy_petition", band_key="entity_inactive", severity="informational",
        penalty=0.0, observed="entity_inactive", content_hash="0" * 64,
        stored_at=datetime(2026, 8, 4, tzinfo=UTC),
    )
    assert continuity_report("acme", [flag]).standing == "ceased"  # visible — just not in posture


# ============================================================================================
# Scenario 3 — multiple historical breaches vs none
# ============================================================================================

def test_scenario_3_multiple_breach_signals_vs_none():
    """Vendor A: a confirmed breach AND a KEV-listed (actively-exploited) CVE — both in
    `breach_compromise_history`, on an otherwise fully-clean baseline. Vendor B: identical
    baseline, clean on both. A's category penalty reflects both findings (with E7a diminishing
    returns applied — see scenario 9), never just the worse one. Full `_all_clean()` coverage —
    see scenario 1's note on why thin coverage's confidence-ceiling would risk clipping both
    sides to the same visible number."""
    a = ScoringEngine().score(_vendor(), [_result("multi", _all_clean({
        "breach_by_data_class": "passwords_or_cards", "kev_listed_cve": "listed",
    }))]).score
    b = ScoringEngine().score(_vendor(), [_result("multi", _all_clean())]).score

    cat_a = next(c for c in a.categories if c.category == B)
    cat_b = next(c for c in b.categories if c.category == B)
    assert cat_a.penalty > cat_b.penalty == 0
    assert a.posture < b.posture


# ============================================================================================
# Scenario 4 — poor email security vs strong
# ============================================================================================

def test_scenario_4_poor_vs_strong_email_security():
    """Vendor A: no DMARC, no SPF, otherwise fully clean. Vendor B: the fully clean baseline.
    `identity_email` category penalty must differ; overall posture must differ in the same
    direction. Full `_all_clean()` coverage, not the thinner `_hygiene()` set — see scenario 1's
    note on why thin coverage's confidence-ceiling would clip both sides to the same visible 80
    and hide the difference."""
    a = ScoringEngine().score(_vendor(), [_result(
        "multi", _all_clean({"dmarc": "absent", "spf": "absent", "dkim": "absent"}))]).score
    b = ScoringEngine().score(_vendor(), [_result("multi", _all_clean())]).score

    cat_a = next(c for c in a.categories if c.category == E)
    cat_b = next(c for c in b.categories if c.category == E)
    assert cat_a.penalty > 0
    assert cat_b.penalty == 0
    assert a.posture < b.posture


# ============================================================================================
# Scenario 5 — expired certificate vs valid (critical ceiling, not just a penalty)
# ============================================================================================

def test_scenario_5_expired_cert_trips_the_critical_ceiling():
    """`cert_validity` is the ONLY signal wired to `critical_ceiling.auto_signals` — an expired
    production certificate doesn't just cost points, it CAPS the whole vendor at 49 (top of Grade
    D) regardless of how clean everything else is. Vendor A is otherwise fully clean; Vendor B is
    identical except for a valid certificate. A must be capped; B must not be."""
    a = ScoringEngine().score(_vendor(), [
        _result("tls", _all_clean({"cert_validity": "expired_serving_prod"}))]).score
    b = ScoringEngine().score(_vendor(), [_result("tls", _all_clean())]).score

    assert a.posture <= 49
    assert b.posture > 49
    assert a.grade in {"D", "F"}
    assert b.posture > a.posture


# ============================================================================================
# Scenario 6 — low evidence coverage vs high (the Ghost)
# ============================================================================================

def test_scenario_6_thin_coverage_is_a_ghost_high_coverage_is_not():
    """Vendor A: only 11 of 27 signals covered (all clean). Vendor B: full 27/27 coverage (all
    clean). A CLEAN-LOOKING vendor on thin evidence must band Low confidence and be flagged as a
    Ghost — this is the scenario that most directly motivates showing Confidence as its own tile,
    never folded into Posture, on the executive dashboard (Phase 3)."""
    thin = ScoringEngine().score(_vendor(), [_result("dns", _hygiene())]).score
    full = ScoringEngine().score(_vendor(), [_result("multi", _all_clean())]).score

    assert thin.confidence_band == "Low"
    assert thin.ghost is True
    assert full.confidence_band == "High"
    assert full.ghost is not True
    assert full.overall_confidence > thin.overall_confidence


# ============================================================================================
# Scenario 7 — independent assurance (corroborated) vs disclosure-only claim
# ============================================================================================

def test_scenario_7_corroborated_certification_scores_disclosure_alone_does_not():
    """Vendor A claims a certification NOT corroborated against a registry (`cert_posture.
    claimed_unverified` — `compliance_regulatory`, SCORES). Vendor B merely publishes a detailed
    trust/policy page with no verifiable certification claim (`program_disclosure.
    detailed_policies` — `assurance_context`, NEVER scores). This is the E5 distinction
    (change-notice-v5.md §3.6): a claim corroborated against a registry is evidence; a marketing
    trust page is not."""
    a = ScoringEngine().score(_vendor(), [
        _result("trust", [_f("cert_posture", K, "claimed_unverified")])]).score
    b = ScoringEngine().score(_vendor(), [
        _result("trust", [_f("program_disclosure", A, "detailed_policies")])]).score

    cat_a = next(c for c in a.categories if c.category == K)
    cat_a_context = next((c for c in a.categories if c.category == A), None)
    cat_b_context = next(c for c in b.categories if c.category == A)
    assert cat_a.penalty > 0                                   # the unverified claim scores
    assert cat_b_context.penalty == 0                          # disclosure alone never scores
    if cat_a_context is not None:
        assert cat_a_context.penalty == 0                      # context categories never score


# ============================================================================================
# Scenario 8 — regulatory action (penalty) vs sanctions match (gate)
# ============================================================================================

def test_scenario_8_regulator_action_penalises_sanctions_match_gates_entirely():
    """Two different mechanisms for 'this is bad', and the dashboard must render them
    differently (Phase 3). Vendor A: a formal enforcement action — a soft penalty in
    `compliance_regulatory`, still published. Vendor B: a sanctions-list match — the sanctions
    GATE fires, blocking the score entirely pending human adjudication. B gets NO posture, not a
    Grade F."""
    a = ScoringEngine().score(_vendor(), [
        _result("dns", _hygiene()),
        _result("regulatory", [_f("regulator_action", K, "enforcement_action")])]).score
    b = ScoringEngine().score(_vendor(), [_result("dns", _hygiene()), _result(
        "ita", [_f("sanctions_screen_hit", _SANCTIONS_CATEGORY, "POSSIBLE match: ACME LLC [SDN]")])]).score

    cat_a = next(c for c in a.categories if c.category == K)
    assert cat_a.penalty > 0
    assert a.posture is not None and a.grade is not None       # A publishes, penalised

    assert b.blocked is True
    assert b.posture is None and b.grade is None                # B does NOT publish — gated
    assert "sanction" in (b.blocked_reason or "").lower()


# ============================================================================================
# Scenario 9 — compounding findings within a category: diminishing returns (E7a)
# ============================================================================================

def test_scenario_9_diminishing_returns_within_a_category():
    """`aggregation_decay` (0.7) applies WITHIN a category, never across (scoring.yaml
    `aggregation:` block) — three `low` findings (1.5 pts each) in `attack_surface_hygiene` must
    total LESS than their naive sum, because the third missing header on a vendor already missing
    two tells a reader almost nothing new. Exact arithmetic: 1.5 * (1 + 0.7 + 0.7^2) = 3.285,
    not 1.5 * 3 = 4.5."""
    combined = ScoringEngine().score(_vendor(), [_result("headers", [
        _f("hsts", H, "absent"), _f("csp", H, "absent"), _f("x_frame_opts", H, "absent"),
    ])]).score
    single = ScoringEngine().score(_vendor(), [_result("headers", [
        _f("hsts", H, "absent"),
    ])]).score

    cat_combined = next(c for c in combined.categories if c.category == H)
    cat_single = next(c for c in single.categories if c.category == H)

    assert cat_combined.penalty == pytest.approx(1.5 * (1 + 0.7 + 0.7 ** 2), abs=0.01)
    assert cat_combined.penalty < 3 * cat_single.penalty        # strictly less than naive scaling
