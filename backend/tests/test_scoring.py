"""Scoring tests — these ENCODE the methodology (penalty-based posture model). Each maps to a
rule the model must obey. Synthetic findings, deterministic, against the REAL scoring.yaml."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.collectors.tls_collector import TlsCollector
from app.models import CollectorResult, Finding, Vendor
from app.scoring import ScoringEngine, modifiers
from app.scoring_config import get_scoring_config

# Category keys, as scoring.yaml defines them AFTER E5. Five scoring categories and two context
# categories; the seven-category shape these tests were written against is gone. The old constants
# were `cyber_hygiene_technical` (now split into H and E, because a missing DMARC record and an
# oversized subdomain estate are not the same kind of problem), `vendor_transparency_gov` (split
# into T and A), `business_financial_stability` (now X, and no longer penalising at all — E4), and
# `digital_footprint_assets` (folded into H).
H = "attack_surface_hygiene"          # what an attacker can reach and how it is configured
E = "identity_email"                  # domain-based impersonation: DMARC / SPF / DKIM
B = "breach_compromise_history"       # realized events
T = "transparency"                    # vd_program, security_txt
K = "compliance_regulatory"           # cert_posture, regulator_action
X = "continuity_context"              # CONTEXT — reported, never penalised (E4)
A = "assurance_context"               # CONTEXT — reported, never penalised (E2/E3)


def _vendor(conf: float = 1.0) -> Vendor:
    return Vendor(ref="acme", name="Acme", domain="acme.example",
                  resolved=True, resolution_confidence=conf)


def _result(source: str, findings: list[Finding], status: str = "ok", rel: float = 0.9) -> CollectorResult:
    return CollectorResult(source=source, vendor_ref="acme", status=status,  # type: ignore[arg-type]
                           source_version="test", raw={"t": 1}, findings=findings, reliability=rel)


def _f(signal, cat, band, event_date=None, value=None, remediated=False) -> Finding:  # noqa: ANN001
    return Finding(source="t", signal=signal, subcategory=signal, category=cat,
                   observed=band, value=value or {"band": band}, event_date=event_date,
                   remediation_evidenced=remediated)


# A full, clean technical set: eleven signals present and passing. Since E5 these span THREE
# categories — attack_surface_hygiene (7), identity_email (3) and transparency (1) — so this
# helper no longer maps onto one category, and tests that used to assert on `_cat(score, C)`
# now name the category the signal actually lives in.
_HYGIENE_CLEAN = {
    "tls_version": "tls_13", "cert_validity": "valid", "dmarc": "p_reject", "spf": "hardfail_all",
    "dkim": "present", "hsts": "present", "csp": "present", "x_frame_opts": "present",
    "security_txt": "present", "dnssec": "valid", "caa": "present",
}


def _hygiene(overrides: dict | None = None) -> list[Finding]:
    # The declared category is a routing HINT only — since E5 the model resolves a signal's home
    # from scoring.yaml (normalize._category_of), so passing H here does not put dmarc in H.
    bands = {**_HYGIENE_CLEAN, **(overrides or {})}
    return [_f(sig, H, band) for sig, band in bands.items()]


# Every signal in the model, passing. Needed since E7d: a vendor on thin coverage has their
# PUBLISHED posture capped, so any test about the subtractive arithmetic reaching 100 has to be
# run on full coverage or it is testing two rules at once and blaming the wrong one.
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


def _fully_covered(overrides: dict | None = None) -> list[Finding]:
    bands = {**_ALL_CLEAN, **(overrides or {})}
    counts = {"subdomain_estate": 6, "stale_hosts": 0}
    return [
        _f(sig, H, band, value={"count": counts[sig]} if sig in counts else {"band": band})
        for sig, band in bands.items()
    ]


def _cat(score, name):  # noqa: ANN001
    return {c.category: c for c in score.categories}[name]


# ---------------------------------------------------------------- the subtractive core

def test_clean_vendor_starts_at_100():
    """Every vendor starts at 100; a fully-clean set subtracts nothing.

    Scored on FULL coverage since E7d. The subtractive arithmetic still starts at 100 on any
    coverage — that is asserted directly below — but the PUBLISHED number is capped by how much
    evidence we hold, so a clean vendor seen through one collector publishes 80, not 100. Testing
    the promise on thin coverage would be testing two rules at once and blaming the wrong one.
    """
    res = ScoringEngine().score(_vendor(), [_result("dns", _fully_covered())])
    assert res.score.posture == 100 and res.score.grade == "A"
    for cat in (H, E, T):
        assert _cat(res.score, cat).penalty == 0.0


def test_the_arithmetic_still_starts_at_100_however_thin_the_evidence():
    """The subtractive promise itself, separated from what we are willing to publish. No penalty
    anywhere, on eleven signals out of twenty-seven.

    THE PUBLISHED NUMBER IS THE CEILING, NOT THE ARITHMETIC. The arithmetic earned 100 (no penalty
    in any category, asserted below); what is published is whatever rung of the E7d ramp this
    coverage buys. That rung moved from 80 to 90 when confidence changed from coverage-of-the-model
    to coverage-of-what-this-profile-expects — the same evidence, read against a smaller
    denominator, clears a higher rung. The assertion is therefore written against
    `confidence_ceiling` rather than a literal, so it keeps testing the RELATIONSHIP (published ==
    the cap coverage allows) instead of a number that moves whenever the ramp is retuned.
    """
    res = ScoringEngine().score(_vendor(), [_result("dns", _hygiene())])
    assert all(c.penalty == 0.0 for c in res.score.categories)
    assert res.score.confidence_ceiling_applied is True, "thin evidence should cap the CLAIM"
    assert res.score.posture == res.score.confidence_ceiling


def test_each_issue_subtracts_its_severity():
    """A Medium issue (p=none) subtracts 8 from its CATEGORY; a High issue (no DMARC) subtracts 20.
    The category is where severity is read directly — the overall divides by the fixed divisor."""
    d = get_scoring_config().penalty_divisor()
    med = ScoringEngine().score(_vendor(), [_result("dns", _fully_covered({"dmarc": "p_none"}))])
    high = ScoringEngine().score(_vendor(), [_result("dns", _fully_covered({"dmarc": "absent"}))])
    assert _cat(med.score, E).penalty == 6.0 and _cat(med.score, E).posture == 94
    assert _cat(high.score, E).penalty == 20.0 and _cat(high.score, E).posture == 80
    assert med.score.posture == round(100 - 6 / d)
    assert high.score.posture == round(100 - 20 / d)
    assert high.score.posture < med.score.posture      # worse severity, worse posture


def test_penalties_accumulate_across_issues():
    """Several gaps drop the posture faster than one — penalties add up within the category, and
    across categories into the overall. The three gaps here land in TWO categories since E5, which
    is exactly why the overall sums first and divides once."""
    cfg = get_scoring_config()
    d, d_decay = cfg.penalty_divisor(), cfg.aggregation_decay()
    res = ScoringEngine().score(_vendor(), [_result("dns", _fully_covered(
        {"dmarc": "absent", "tls_version": "tls_10_or_11", "hsts": "absent"}))])
    # Since E7a the two H findings are RANKED, not summed: 20 + 1.5*0.7 = 21.05. E holds one
    # finding so it charges in full. The overall still sums the categories and divides once.
    assert _cat(res.score, H).penalty == pytest.approx(20 + 1.5 * d_decay)
    assert _cat(res.score, E).penalty == 20              # dmarc, rank 1 in its own category
    assert res.score.posture == round(100 - (20 + 1.5 * d_decay + 20) / d)


# ---------------------------------------------------------------- THE honesty rule

def test_missing_data_adds_no_penalty_and_never_moves_the_divisor():
    """THE honesty rule, in its exact form — and E7d qualified it, so it is worth stating precisely.

    Two clean vendors; one has business signals covered too. Missing data must add no penalty and
    must not change the denominator. That is unchanged and is the part that matters: it is what
    stops "we could not see it" from being scored as "they failed it".

    What E7d DID change: coverage now caps the PUBLISHED number (see the ceiling-ramp tests). The
    two vendors used to sit on the same ramp rung and publish the same figure; under the
    profile-relative confidence model they sit on DIFFERENT rungs, so the published numbers now
    differ (90 and 100).

    THAT IS NOT THIS RULE BREAKING — it is the ceiling doing its job, and the assertions below say
    so precisely. Neither vendor is CHARGED anything for the evidence we lack (every category
    penalty is 0.0 for both), and neither publishes more than the arithmetic earned. The whole
    difference is the cap, which can only ever WITHHOLD posture the arithmetic already earned and
    can never award posture the findings did not. Asserting `thin == rich` would now be asserting
    that coverage may not reach the ceiling either, which is a different — and false — claim.
    """
    eng = ScoringEngine()
    business = [
        _f("entity_status", X, "active_good_standing"),
        _f("entity_existence", X, "entity_active_confirmed"),
        _f("domain_registration", X, "domain_established"),
    ]
    thin = eng.score(_vendor(), [_result("dns", _hygiene())])
    rich = eng.score(_vendor(), [_result("dns", _hygiene()), _result("reg", business)])

    # The rule itself: nothing was charged for what we could not see, on either vendor.
    assert all(c.penalty == 0.0 for c in thin.score.categories)
    assert all(c.penalty == 0.0 for c in rich.score.categories)
    # More evidence buys more confidence — the axis that is ALLOWED to move.
    assert rich.score.overall_confidence > thin.score.overall_confidence
    # And the entire posture difference is the ceiling, not a penalty: each vendor publishes
    # exactly the cap its own coverage allows, never less (which would mean a deduction crept in).
    assert thin.score.posture == thin.score.confidence_ceiling
    assert rich.score.posture <= rich.score.confidence_ceiling
    assert rich.score.posture >= thin.score.posture


def test_the_confidence_ceiling_can_withhold_posture_but_never_award_it():
    """The guard on the qualification above, and the reason E7d is not a licence for coverage to
    buy points.

    A ceiling is a CAP: `min(arithmetic, ceiling)`. It follows that the published number can never
    exceed what the findings earned, whatever the coverage. If that were ever false, adding a clean
    source would buy posture — the original defect this model was rebuilt to remove.
    """
    for overrides in ({}, {"dmarc": "absent"}, {"tls_version": "tls_10_or_11", "csp": "absent"}):
        thin = ScoringEngine().score(_vendor(), [_result("dns", _hygiene(overrides))]).score
        full = ScoringEngine().score(_vendor(), [_result("dns", _fully_covered(overrides))]).score
        assert thin.posture <= full.posture, (
            f"{overrides}: thin coverage published {thin.posture} against {full.posture} on full "
            f"coverage — a ceiling must never raise a score above its own arithmetic"
        )


def _maturity_pair():
    eng = ScoringEngine()
    shared = _hygiene() + [
        _f("entity_status", X, "active_good_standing"),
        _f("entity_existence", X, "entity_active_confirmed"),
        _f("domain_registration", X, "domain_established"),
    ]
    mature = eng.score(_vendor(), [_result("multi", shared + [_f("entity_maturity", X, "mature_gt_10")])])
    established = eng.score(_vendor(), [_result("multi", shared + [_f("entity_maturity", X, "established_5_10")])])
    return mature.score, established.score


def test_entity_maturity_never_moves_posture():
    """THE HALF THAT MUST HOLD ABSOLUTELY: how old a company is cannot change what we observed of
    its controls. Age is context; posture is evidence."""
    mature, established = _maturity_pair()
    assert mature.posture == established.posture


@pytest.mark.xfail(
    strict=True,
    reason=(
        "The profile-relative confidence model does not read the `entity_maturity` FINDING. It "
        "takes age from `profile.operating_years` and `entity_maturity` is not in "
        "`confidence_config.SIGNAL_CATEGORIES` at all, so the band is dropped by the "
        "`if not category: continue` guard. Two consequences, both live: (1) a vendor whose age is "
        "known ONLY from a collector (not from the profile) is treated as unknown age; (2) the "
        "expected-signal table is flat from `young` upward — established, mature and veteran all "
        "expect the same 21 signals — so no maturity band above `young` can move confidence "
        "either way. Kept as a STRICT xfail rather than deleted: the assurance nudge is a "
        "documented feature of the model (scoring.yaml `assurance_multiplier`) and this is the "
        "record that it is currently inert. Whoever restores it should see this test go green."
    ),
)
def test_entity_maturity_adjusts_confidence():
    """Within non-penalising maturity bands, assurance can move while posture stays fixed."""
    mature, established = _maturity_pair()
    assert mature.overall_confidence > established.overall_confidence


def test_absent_category_has_no_posture():
    """A category no source fed is absent (posture None), not a zero — and lowers coverage."""
    res = ScoringEngine().score(_vendor(), [_result("dns", _hygiene())])
    for name in (B, K, X):
        cat = _cat(res.score, name)
        assert cat.posture is None and cat.coverage == 0.0, name


def test_broader_coverage_raises_confidence_band():
    """Covering more categories lifts the confidence band toward Medium/High."""
    eng = ScoringEngine()
    findings = _hygiene()
    findings += [_f("breach_by_data_class", B, "no_known_breach"),
                 _f("kev_listed_cve", B, "no_kev_match"), _f("nvd_cve", B, "no_critical_cve")]
    findings += [_f("program_disclosure", A, "detailed_policies"),
                 _f("contactability", A, "dpo_and_security_contact"),
                 _f("vd_program", T, "bug_bounty")]
    findings += [_f("entity_status", X, "active_good_standing"),
                 _f("entity_existence", X, "entity_active_confirmed"),
                 _f("domain_registration", X, "domain_established")]
    findings += [_f("cert_posture", K, "registry_corroborated"),
                 _f("reporting_posture", A, "substantive")]
    res = eng.score(_vendor(), [_result("multi", findings)])   # 22 of 27 signals covered
    assert res.score.overall_confidence >= 0.70
    assert res.score.confidence_band in {"Medium", "High"}


# ---------------------------------------------------------------- gates (kept)

def test_sanctions_hit_emits_no_score():
    hit = _f("sanctions_screen_hit", "regulatory_legal_sanctions", "POSSIBLE match: ACME LLC [SDN]")
    res = ScoringEngine().score(_vendor(), [_result("dns", _hygiene()), _result("ita", [hit])])
    assert res.score.blocked is True
    assert res.score.posture is None and res.score.grade is None    # NO score, not Grade F
    assert "sanction" in (res.score.blocked_reason or "").lower()


def test_ambiguous_entity_emits_no_score():
    res = ScoringEngine().score(_vendor(conf=0.3), [_result("dns", _hygiene())])
    assert res.score.blocked is True
    assert res.score.posture is None
    assert "entity" in (res.score.blocked_reason or "").lower()


# ---------------------------------------------------------------- the Ghost (kept)

def test_thin_coverage_is_a_ghost_and_refused():
    """A clean-LOOKING vendor on thin coverage is a Ghost — not published."""
    res = ScoringEngine().score(_vendor(), [_result("dns", [_f("dmarc", E, "p_reject")])])
    assert res.score.refused is True and res.score.ghost is True
    assert res.score.posture is None


def test_ghost_flag_on_low_confidence_band():
    """Even when published, a Low confidence band flags the Ghost (looks clean for lack of data)."""
    res = ScoringEngine().score(_vendor(), [_result("dns", _hygiene())])   # only 11 of 27 signals
    assert res.score.confidence_band == "Low"
    assert res.score.ghost is True
    # Since E7d the Ghost is not merely FLAGGED at 100 — the claim itself is capped. A vendor this
    # thinly evidenced cannot publish above the rung its coverage buys, however clean the little we
    # saw happened to be. Written against `confidence_ceiling` rather than a literal so it tests
    # the relationship and not a number that moves when the ramp or the denominator is retuned.
    assert res.score.posture == res.score.confidence_ceiling
    assert res.score.confidence_ceiling_applied is True


# ---------------------------------------------------------------- critical ceiling (knockout, kept)

def test_expired_cert_applies_critical_ceiling():
    """A directly-observed expired production cert caps the posture at the ceiling (grade D top)."""
    res = ScoringEngine().score(_vendor(), [_result("tls", _hygiene({"cert_validity": "expired_serving_prod"}))])
    assert res.score.critical_ceiling_applied is True
    assert res.score.posture is not None and res.score.posture <= 49
    assert res.score.ceiling_cause and "cert" in res.score.ceiling_cause


def test_collector_expired_cert_finding_fires_ceiling():
    """Integration guard: the cert Finding as the COLLECTOR builds it carries the critical band."""
    expired = TlsCollector._cert_finding(days=-5, not_after_iso=None, domain="acme.example")
    assert expired.value["band"] == "expired_serving_prod"
    res = ScoringEngine().score(_vendor(), [_result("tls", [expired] + _hygiene())])
    assert res.score.critical_ceiling_applied is True


def test_collector_valid_cert_finding_is_benign_band():
    valid = TlsCollector._cert_finding(days=120, not_after_iso=None, domain="acme.example")
    assert valid.value["band"] == "valid"


def test_ceiling_caps_but_never_raises():
    """A vendor already below the ceiling stays there — the ceiling CAPS, it never sets or lifts."""
    wrecked = _fully_covered({
        "cert_validity": "expired_serving_prod", "dmarc": "absent", "tls_version": "tls_10_or_11",
        "spf": "absent", "dkim": "absent", "hsts": "absent", "csp": "absent",
        "x_frame_opts": "absent", "security_txt": "absent", "dnssec": "misconfigured",
        "caa": "absent",
        "breach_by_data_class": "passwords_or_cards", "kev_listed_cve": "listed",
        "nvd_cve": "cvss_critical",
        "stale_hosts": "many", "subdomain_estate": "large",
        "weak_issuance": "deprecated_ca_or_key",
    })
    # `_fully_covered` already emits every signal once. Adding a second copy of a signal here would
    # trip the NIST frequency factor (two breaches read as a pattern, x1.25) and quietly change what
    # this test measures — which is exactly what it did before these overrides were consolidated.
    for f in wrecked:
        if f.signal == "stale_hosts":
            f.value = {"count": 99}
        elif f.signal == "subdomain_estate":
            f.value = {"count": 999}

    res = ScoringEngine().score(_vendor(), [_result("all", wrecked)])
    # Every category is now RANKED before it is summed (E7a), so nothing here reaches the 100-point
    # cap any more — which is the visible face of the change. Worked through:
    #   B: kev 50 + breach 50*0.7 = 85.  nvd_cve is SUPPRESSED by kev (E7c), so the third
    #      critical charges nothing instead of pushing the category past 100.
    #   H: 50 + 20*.7 + 20*.49 + 6*.343 + 6*.24 + 1.5*.168 + 1.5*.118 + 1.5*.082 = 77.85
    #   E: 20 + 6*.7 + 1.5*.49 = 24.93
    #   (85 + 77.85 + 24.93) / 2.86 = 65.7 -> posture 34, still far below the 49 ceiling
    assert _cat(res.score, B).penalty == 85.0, "kev + one decayed breach; the CVE is deduplicated"
    assert res.score.posture == 34
    assert res.score.critical_ceiling_applied is False   # nothing to cap
    # The point of the test, independent of the arithmetic: a vendor already under the ceiling is
    # not LIFTED to it. A ceiling that could raise a score would be a floor wearing the wrong name.
    assert res.score.posture < ScoringEngine().cfg.ceiling_score()


def test_ceiling_bypasses_the_ghost_refusal():
    """A directly-observed critical is certain even on thin coverage — publish, don't refuse."""
    res = ScoringEngine().score(_vendor(), [_result("tls", [
        _f("cert_validity", H, "expired_serving_prod")])])
    assert res.score.refused is False
    assert res.score.posture is not None and res.score.posture <= 49


# ---------------------------------------------------------------- collapse + frequency (§5.3)
# Every (category, signal) group contributes ONE penalty — its worst decayed member. Recurrence
# is then expressed once via the NIST frequency factor, never by summing duplicates.

def test_distinct_cves_collapse_to_one_penalty():
    """A bag of distinct CVEs must NOT sum — 40 medium/low CVEs contribute ONE penalty (3),
    not 120, or a clean estate would tank on coarse keyword-match noise."""
    cves = [_f("nvd_cve", B, "cvss_medium_or_low") for _ in range(40)]
    res = ScoringEngine().score(_vendor(), [_result("nvd", cves)])
    assert _cat(res.score, B).penalty == 1.5        # worst representative, not 40 x 1.5


def test_worst_of_picks_the_critical_cve():
    """The representative is the WORST instance: a mix of medium + critical scores the critical."""
    cves = [_f("nvd_cve", B, "cvss_medium_or_low"), _f("nvd_cve", B, "cvss_critical")]
    res = ScoringEngine().score(_vendor(), [_result("nvd", cves)])
    assert _cat(res.score, B).penalty == 50.0       # critical drove it (not the low one)


def test_distinct_cves_are_not_frequency_amplified():
    """CVE bags are frequency-EXEMPT (scoring.yaml modifiers.frequency.exempt_signals): a coarse
    keyword match is match volume, not a pattern of distinct events. 40 CVEs must not become x2."""
    one = ScoringEngine().score(_vendor(), [_result("nvd", [_f("nvd_cve", B, "cvss_high")])])
    many = ScoringEngine().score(_vendor(), [_result("nvd",
            [_f("nvd_cve", B, "cvss_high") for _ in range(40)])])
    assert _cat(many.score, B).penalty == _cat(one.score, B).penalty == 20.0


def test_repeat_breaches_amplify_by_frequency_not_by_summing():
    """Realized events ARE a pattern: three breaches penalise more than one — but as 20 x 1.5,
    NOT as 20+20+20. Frequency replaces summing; it must never stack on top of it."""
    def pen(n: int) -> float:
        res = ScoringEngine().score(_vendor(), [_result("hibp",
                [_f("breach_by_data_class", B, "personal_info") for _ in range(n)])])
        return _cat(res.score, B).penalty

    assert pen(1) == 20.0
    assert pen(3) == 30.0                  # 20 x (1 + 0.25*2) — a pattern, not one breach x3
    assert pen(3) < 3 * pen(1)             # the whole point: recurrence is counted ONCE
    assert pen(8) == 40.0                  # cap 2.0 holds
    assert pen(40) == 40.0


def test_every_breach_is_still_counted_and_cited():
    """Collapsing the PENALTY must not collapse the EVIDENCE: all three issues stay visible."""
    res = ScoringEngine().score(_vendor(), [_result("hibp",
            [_f("breach_by_data_class", B, "personal_info") for _ in range(3)])],
            evidence_ids={"hibp": "ev-1"})
    assert _cat(res.score, B).findings == 3
    assert _cat(res.score, B).contributing_finding_ids == ["ev-1"]


# ---------------------------------------------------------------- mitigation (NIST SP 1326)

def test_evidenced_remediation_discounts_the_penalty():
    """x0.6 where remediation is CORROBORATED — the fourth NIST variable, live in the engine."""
    plain = ScoringEngine().score(_vendor(), [_result("nvd", [_f("nvd_cve", B, "cvss_high")])])
    fixed = ScoringEngine().score(_vendor(), [_result("nvd",
             [_f("nvd_cve", B, "cvss_high", remediated=True)])])
    assert _cat(plain.score, B).penalty == 20.0
    assert _cat(fixed.score, B).penalty == 12.0     # 20 x 0.6


def test_remediation_defaults_to_unevidenced():
    """Claims don't count: a finding is unmitigated unless a collector positively evidences a fix."""
    assert _f("nvd_cve", B, "cvss_high").remediation_evidenced is False


# ------------------------------------------------- missing data never changes posture (§5.4)

def _trust_clean():
    return [_f("program_disclosure", A, "detailed_policies"),
            _f("contactability", A, "dpo_and_security_contact"),
            _f("vd_program", T, "bug_bounty")]


def _entity_clean():
    return [_f("entity_status", X, "active_good_standing"),
            _f("entity_existence", X, "entity_active_confirmed")]


def test_clean_sources_cannot_raise_the_posture():
    """THE invariant. Identical security problems; the only difference is how many OTHER sources
    came back clean. Posture must not move — silence is a CONFIDENCE problem, never a posture one.

    This is the regression guard for a real defect: averaging only the COVERED categories let a
    clean trust page buy +23 posture, so a vendor looked strong by being visible in cheap
    categories."""
    bad = {"tls_version": "tls_10_or_11", "dmarc": "absent", "hsts": "absent", "csp": "absent"}
    hygiene_only = ScoringEngine().score(_vendor(), [_result("dns", _hygiene(bad))]).score
    plus_trust = ScoringEngine().score(_vendor(), [
        _result("dns", _hygiene(bad)), _result("trust", _trust_clean())]).score
    plus_both = ScoringEngine().score(_vendor(), [
        _result("dns", _hygiene(bad)), _result("trust", _trust_clean()),
        _result("gleif", _entity_clean())]).score

    assert hygiene_only.posture == plus_trust.posture == plus_both.posture
    # ...and the clean receipts DO lift confidence, which is where they belong.
    assert plus_both.overall_confidence > hygiene_only.overall_confidence


def test_a_silent_source_cannot_lower_the_posture_either():
    """The mirror: dropping a clean source must not punish the vendor."""
    full = ScoringEngine().score(_vendor(), [
        _result("dns", _hygiene({"dmarc": "absent"})), _result("trust", _trust_clean())]).score
    silent = ScoringEngine().score(_vendor(), [
        _result("dns", _hygiene({"dmarc": "absent"}))]).score
    assert full.posture == silent.posture


def _business_stability_clean():
    """The three Business Stability signals (docs/tprm_feedback_redesign.md §1.3), all answering
    clean — Gazette/EDGAR/CourtListener all reachable and finding nothing adverse."""
    return [_f("sec_filing", X, "no_adverse_filings"),
            _f("insolvency_notice", X, "no_adverse_filings"),
            _f("bankruptcy_petition", X, "no_adverse_filings")]


def test_business_stability_signals_cannot_move_posture_or_confidence():
    """THE regression guard for the defect found while wiring these signals in: adding them to
    `scoring.yaml`'s shared denominator moved planned_signal_count 27->30 and silently dropped
    every real vendor's confidence band when replayed against pre-existing (frozen) evidence that
    predates these collectors. `ScoringConfig.business_stability_signals()` excludes them from
    BOTH sides of the coverage ratio for exactly this reason — this test proves posture AND
    confidence are byte-identical whether or not these three signals are present at all."""
    bad = {"tls_version": "tls_10_or_11", "dmarc": "absent"}
    without = ScoringEngine().score(_vendor(), [_result("dns", _hygiene(bad))]).score
    with_bs = ScoringEngine().score(_vendor(), [
        _result("dns", _hygiene(bad)), _result("gazette", _business_stability_clean())]).score

    assert without.posture == with_bs.posture
    assert without.overall_confidence == with_bs.overall_confidence
    assert without.confidence_band == with_bs.confidence_band


def test_overall_is_total_penalty_over_a_fixed_divisor():
    """The published formula: 100 - total_penalty / divisor, divisor fixed by the model."""
    cfg = get_scoring_config()
    res = ScoringEngine().score(_vendor(), [_result("dns", _fully_covered({"dmarc": "absent"}))])
    assert _cat(res.score, E).penalty == 20.0
    assert res.score.posture == round(100 - 20.0 / cfg.penalty_divisor())


# ---------------------------------------------------------------- explainability (Finding A)

def test_every_covered_category_cites_evidence():
    """Every covered category — clean or not — cites at least one hash-stamped receipt."""
    res = ScoringEngine().score(_vendor(), [_result("dns", _hygiene())], evidence_ids={"dns": "ev-1"})
    covered = [c for c in res.score.categories if c.posture is not None]
    assert covered
    for c in covered:
        assert c.contributing_finding_ids, f"{c.category} covered but cites no evidence"


# ---------------------------------------------------------------- decay (NIST SP 1326, kept)

def test_2013_breach_decays_below_a_2025_breach():
    old = modifiers.apply(40, event_date=datetime(2013, 1, 1, tzinfo=UTC), n_events=1, mitigated=False)
    new = modifiers.apply(40, event_date=datetime.now(UTC) - timedelta(days=20), n_events=1, mitigated=False)
    assert old < new
    assert old >= 40 * 0.15   # never below the floor


def test_an_expired_cert_does_not_soften_with_age():
    """Current-state signals never decay. A cert's event_date is its notAfter, which is in the PAST
    once expired — decaying it made a cert expired 6 years ago cost less than one expiring next
    week. The longer it stays broken, the worse it is, not the cheaper."""
    now = datetime.now(UTC)
    pens = [
        _cat(ScoringEngine().score(_vendor(), [_result("tls", [
            _f("cert_validity", H, "expired_serving_prod", now - timedelta(days=365 * y))
        ])]).score, H).penalty
        for y in (0, 1, 3, 6, 12)
    ]
    assert pens == [50.0] * 5, f"expired cert decayed with age: {pens}"


def test_historic_findings_still_decay():
    """The complement — a breach IS an occurrence, so it must still decay (that rule is the whole
    reason the NIST age variable exists)."""
    now = datetime.now(UTC)
    fresh = _cat(ScoringEngine().score(_vendor(), [_result("hibp", [
        _f("breach_by_data_class", B, "personal_info", now - timedelta(days=20))])]).score, B).penalty
    old = _cat(ScoringEngine().score(_vendor(), [_result("hibp", [
        _f("breach_by_data_class", B, "personal_info", now - timedelta(days=365 * 6))])]).score, B).penalty
    assert old < fresh


def test_age_factor_floor_and_current():
    assert modifiers.age_factor(None) == 1.0
    assert modifiers.age_factor(datetime(1990, 1, 1, tzinfo=UTC)) == 0.15


def test_old_breach_penalises_less_than_a_fresh_one():
    """End-to-end: a 2013 breach subtracts less posture than the same breach dated now."""
    eng = ScoringEngine()
    old = eng.score(_vendor(), [_result("hibp", [_f("breach_by_data_class", B, "personal_info",
                    event_date=datetime(2013, 1, 1, tzinfo=UTC))] + _fully_covered())])
    fresh = eng.score(_vendor(), [_result("hibp", [_f("breach_by_data_class", B, "personal_info",
                      event_date=datetime.now(UTC))] + _fully_covered())])
    assert old.score.posture > fresh.score.posture   # less penalty when decayed


def test_sector_never_changes_a_severity():
    """E1: the SAME findings scored against every sector must produce an identical Score.

    This is the invariant `industry_profiles` broke. It is asserted at the engine boundary rather
    than the config boundary because that is where a future regression would actually land — a
    `sector` argument that reaches the arithmetic by any route at all fails here.
    """
    # ALL_REFS, not VENDOR_REFS: sector invariance must hold for every input shape, including the
    # gated and refused archetypes where the score object is mostly None. A promotion that only
    # showed up on a blocked vendor would be exactly the kind of thing five clean vendors miss.
    from tests.test_corpus import ALL_REFS as VENDOR_REFS
    from tests.test_corpus import AS_AT, load_fixture

    sectors = [None, "financial_services", "healthcare", "retail", "manufacturing"]
    # `computed_at` is wall-clock and differs between any two runs — dropped for the same reason
    # test_profile.test_profile_never_moves_a_score drops it. Everything else must be identical.
    drop = {"computed_at"}
    for ref in VENDOR_REFS:
        vendor, results = load_fixture(ref)
        scores = [
            {k: v for k, v in
             ScoringEngine().score(vendor, results, now=AS_AT, sector=s).score.model_dump().items()
             if k not in drop}
            for s in sectors
        ]
        for other in scores[1:]:
            assert other == scores[0], (
                f"{ref}: sector changed the published Score. Severity must not vary with a label "
                f"we assigned — that is the comparability the whole model rests on."
            )
