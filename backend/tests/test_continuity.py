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
