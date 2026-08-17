"""Continuity — going-concern facts leave Posture and become cited flags (E4).

The defect this phase fixed, stated plainly: Companies House maps `liquidation`, `receivership`,
`administration` and `insolvency-proceedings` onto `entity_inactive`, which cost **20 points of
technical security posture**. A vendor entering administration does not thereby have worse TLS.

Two properties are load-bearing and each has a test that fails loudly:
  * no going-concern signal reaches a penalty — asserted against the SHIPPED config;
  * every published flag carries a citation and a retrieval date, because an uncited assertion
    about another company's solvency is the one thing this axis must never emit.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.continuity import continuity_report
from app.models import PersistedFinding
from app.scoring_config import get_scoring_config

CLASS_C = ("entity_status", "entity_existence", "entity_maturity", "domain_registration")


def _bands(cfg, signal: str) -> dict[str, str]:
    """The model's bands for a signal, found wherever the model currently keeps it.

    These four signals lived in `business_financial_stability` when E4 was written and moved to
    `continuity_context` at E5. Hard-coding the category made two of these tests pass VACUOUSLY
    after the rename — `signals_of("business_financial_stability")` returned `{}`, so the
    "nothing here penalises" assertions were true of an empty set. Resolving through the model
    means a signal that goes missing fails loudly instead.
    """
    category = cfg.category_of(signal)
    assert category is not None, f"{signal} has no home in the model at all"
    return cfg.signals_of(category)[signal]


def _finding(signal: str, band: str, *, source: str = "companies_house",
             observed: str = "observed") -> PersistedFinding:
    return PersistedFinding(
        id="f1", vendor_ref="acme", evidence_id="ev_abc123", source=source,
        category="business_financial_stability", signal=signal, band_key=band,
        severity="informational", penalty=0.0, observed=observed,
        content_hash="0" * 64, stored_at=datetime(2026, 7, 30, tzinfo=UTC),
    )


# --------------------------------------------------------------------- it left Posture


def test_no_going_concern_signal_carries_a_posture_penalty():
    """The whole point of E4. A company in administration has a business-continuity problem, and
    it is not expressed by deducting points from a technical security score."""
    cfg = get_scoring_config()
    charging = [
        f"{sig}.{band}"
        for sig in CLASS_C
        for band, sev in _bands(cfg, sig).items()
        if cfg.penalty_for(sev) > 0
    ]
    assert charging == [], f"going-concern signals still penalising posture: {charging}"


def test_company_age_never_reaches_a_penalty():
    """No published evidence links founding date to compromise likelihood, and not one major
    provider scores by it. Age's legitimate homes are the Confidence assurance multiplier, the
    Assurity attainability rule, and cohort assignment — never posture."""
    cfg = get_scoring_config()
    bands = _bands(cfg, "entity_maturity")
    assert bands, "entity_maturity lost its bands entirely — it must stay a coverage signal"
    assert all(cfg.penalty_for(sev) == 0 for sev in bands.values())


def test_the_signals_still_count_toward_coverage():
    """Relocated, not deleted. Removing them would drop planned_signal_count and lift every
    vendor's confidence for no evidential reason — the check still runs."""
    cfg = get_scoring_config()
    # At E5 these moved into `continuity_context`, a category that is reported and never scored.
    assert {cfg.category_of(s) for s in CLASS_C} == {"continuity_context"}
    assert cfg.planned_signal_count() == 27


def test_entity_maturity_remains_the_confidence_assurance_signal():
    """Age keeps its ONE legitimate arithmetic role. Removing the penalty must not remove the
    bounded multiplier, which is where the engine always said age belonged."""
    cfg = get_scoring_config()
    assert cfg.confidence_assurance_signal() == "entity_maturity"
    assert cfg.confidence_multiplier_for_band("new_lt_1") < 1.0
    assert cfg.confidence_multiplier_for_band("mature_gt_10") > 1.0


# --------------------------------------------------------------------- what it became


def test_administration_is_reported_as_ceased_not_as_a_deduction():
    report = continuity_report("acme", [_finding("entity_status", "entity_inactive")])
    assert report.standing == "ceased"
    flag = report.flags[0]
    assert "administration" in flag.statement or "liquidation" in flag.statement


def test_every_flag_carries_a_citation_and_a_retrieval_date():
    """An uncited assertion about another company's solvency is the one thing this axis must never
    publish. The register and the date are what keep it on the same footing as any other observed
    fact — and what make it disputable."""
    report = continuity_report("acme", [
        _finding("entity_status", "entity_inactive"),
        _finding("domain_registration", "domain_suspended", source="rdap"),
    ])
    for flag in report.flags:
        assert flag.source, "a flag with no register behind it is an opinion"
        assert flag.retrieved_at, "a register fact without a date cannot be checked"
        assert flag.evidence_id, "no receipt means the claim cannot be reconstructed"
        assert flag.source in flag.cited()
        assert "2026-07-30" in flag.cited()


def test_the_worst_standing_is_the_headline_and_is_not_averaged_away():
    """Non-compensatory, like the critical ceiling one level up: three healthy registry facts do
    not dilute one dissolution."""
    report = continuity_report("acme", [
        _finding("entity_status", "active_good_standing"),
        _finding("domain_registration", "domain_established", source="rdap"),
        _finding("entity_existence", "entity_dissolved", source="gleif"),
    ])
    assert report.standing == "ceased"
    assert report.flags[0].standing == "ceased"


def test_age_is_context_never_a_standing():
    """A young company is not an impaired counterparty. Reporting age as a going-concern STANDING
    would reintroduce founding-date scoring one axis over."""
    report = continuity_report("acme", [_finding("entity_maturity", "new_lt_1", source="gleif")])
    assert report.flags == []
    assert report.standing == "unknown"
    assert any("under a year" in a for a in report.age_context)


def test_a_healthy_vendor_reads_as_sound():
    report = continuity_report("acme", [
        _finding("entity_status", "active_good_standing"),
        _finding("entity_existence", "entity_active_confirmed", source="gleif"),
    ])
    assert report.standing == "sound"


def test_absence_of_financial_distress_data_is_disclosed_not_implied_healthy():
    """Runway, cash burn and credit ratings have no lawful free source. Silence on them must never
    read as evidence of financial health."""
    report = continuity_report("acme", [_finding("entity_status", "active_good_standing")])
    joined = " ".join(report.caveats).lower()
    assert "no lawful free source" in joined
    assert "not evidence of financial health" in joined


def test_continuity_is_not_a_score():
    """Deliberate refusal, not an unfinished feature — see the module docstring."""
    report = continuity_report("acme", [_finding("entity_status", "entity_inactive")])
    assert isinstance(report.standing, str)
    assert not hasattr(report, "score")
    assert any("not a score" in c.lower() for c in report.caveats)


# --------------------------------------------------------------------- Business Stability (§1.3)

# The Business Stability axis: three registry/filing facts plus `sec_going_concern`, added at
# Phase 2. The set is duplicated in `app/continuity.py`, and `test_business_stability_signal_sets_
# match` is what stops the two drifting apart — as they did when Phase 2 grew one side to nine.
CLASS_D = ("sec_filing", "sec_going_concern", "insolvency_notice", "bankruptcy_petition")


def test_business_stability_signals_never_carry_a_posture_penalty():
    """Same invariant as CLASS_C (E4), extended to the three new financial sources — Gazette,
    EDGAR, CourtListener. A bankruptcy filing is real and must be visible, but it is not a
    security-posture fact."""
    cfg = get_scoring_config()
    charging = [
        f"{sig}.{band}"
        for sig in CLASS_D
        for band, sev in _bands(cfg, sig).items()
        if cfg.penalty_for(sev) > 0
    ]
    assert charging == [], f"Business Stability signals still penalising posture: {charging}"


def test_business_stability_signals_excluded_from_planned_signal_count():
    """The whole reason this axis exists as a SEPARATE denominator (docs/tprm_feedback_redesign.md
    §1.3): these four signals are reachable and do score (at `informational`), but must never
    move Posture's confidence-ceiling / Ghost-detection math. Replaying the frozen regression
    corpus's pre-existing evidence against a grown denominator silently dropped every real
    vendor's confidence band — this is the regression guard for that defect."""
    cfg = get_scoring_config()
    assert cfg.business_stability_signals() == set(CLASS_D)
    assert cfg.planned_signal_count() == 27  # unchanged — CLASS_D is not counted here


def test_business_stability_signal_sets_match():
    """continuity.py duplicates this set rather than importing scoring_config (module
    independence, by design — see continuity.py's module docstring). The two must never drift."""
    from app.continuity import BUSINESS_STABILITY_SIGNALS
    cfg = get_scoring_config()
    assert BUSINESS_STABILITY_SIGNALS == cfg.business_stability_signals()


def test_business_stability_coverage_counts_only_class_d_signals():
    from app.continuity import business_stability_coverage
    findings = [
        _finding("sec_filing", "no_adverse_filings", source="sec_edgar"),
        _finding("insolvency_notice", "entity_inactive", source="the_gazette"),
        _finding("entity_status", "active_good_standing"),  # a Continuity signal, not Class D
    ]
    answered, tracked = business_stability_coverage(findings)
    assert (answered, tracked) == (2, len(CLASS_D))


def test_business_stability_coverage_is_zero_of_tracked_when_nothing_collected():
    """No coverage for this vendor's jurisdiction reads as (0, N), never as clean — the same
    'absence is not health' principle as `continuity_report`'s own `unknown` standing.

    The denominator is `len(CLASS_D)` rather than a literal so that adding a signal to the axis
    updates one place. A literal here is how the previous drift went unnoticed for a release."""
    from app.continuity import business_stability_coverage
    answered, tracked = business_stability_coverage([_finding("entity_status", "entity_inactive")])
    assert (answered, tracked) == (0, len(CLASS_D))


def test_bankruptcy_filing_flags_ceased_and_reorganisation_flags_watch():
    report = continuity_report("acme", [_finding("bankruptcy_petition", "entity_inactive",
                                                  source="courtlistener_bankruptcy")])
    assert report.standing == "ceased"

    report = continuity_report("acme", [_finding("sec_filing", "registration_lapsed",
                                                  source="sec_edgar")])
    assert report.standing == "watch"


def test_business_stability_clean_receipt_is_not_asserted_as_sound():
    """`no_adverse_filings` is deliberately unmapped in `_FLAGS` — a name-search finding nothing
    is weaker evidence than a registry's explicit good-standing confirmation, so it must not
    produce a 'sound' flag the way `entity_status.active_good_standing` does."""
    report = continuity_report("acme", [
        _finding("sec_filing", "no_adverse_filings", source="sec_edgar"),
        _finding("insolvency_notice", "no_adverse_filings", source="the_gazette"),
        _finding("bankruptcy_petition", "no_adverse_filings", source="courtlistener_bankruptcy"),
    ])
    assert report.standing == "unknown"
    assert report.flags == []
