"""The decision layer: actions and recommendations.

Two properties are load-bearing here and each has a test that fails loudly:
  * every penalising band carries an action and a re-check date (loader-enforced, like reasons);
  * the recommendation is a deterministic rule table — same inputs, same output, no LLM.

A third used to live here — industry profiles promoting a severity by one step — and was removed
at E1 along with the mechanism. See the 1.3 tombstone below.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.models import Score
from app.scoring import ScoringEngine
from app.scoring.recommend import recommend, soonest_recheck
from app.scoring_config import ScoringConfig, ScoringConfigError, get_scoring_config
from tests.test_corpus import ALL_REFS, AS_AT, load_fixture


def _score(grade="B", conf=0.95, band="High", **kw) -> Score:
    return Score(vendor_ref="acme", posture=80, grade=grade, overall_confidence=conf,
                 confidence_band=band, **kw)


# --------------------------------------------------------------------- 1.1 actions


def test_every_penalising_band_has_an_action_and_a_recheck():
    """The loader enforces this, but assert it on the SHIPPED file too: a band that explains
    itself and stops there hands the reader the translation work this product exists to remove."""
    cfg = get_scoring_config()
    missing = [f"{sig}.{band}" for _c, sig, band in cfg.penalising_bands()
               if not (cfg.action_for(sig, band) or {}).get("action")]
    assert missing == []
    # A TRIPWIRE, not a specification. It exists so a band added without a reason and an action
    # fails loudly here rather than shipping unexplained. Update it in the SAME commit as the
    # scoring.yaml change, and say why in the message. History: 57 at v4.2.0 -> 49 (E2, eight
    # bands informational) -> 47 (E3, contactability) -> 36 (E4, going-concern relocated) ->
    # 35 (E6, subdomain_estate stops penalising, stale_hosts gains `negligible`)
    # -> 41 (E12, two estate RATE signals x three penalising bands each).
    #
    # The E12 additions are SILENT AT `estate.probe_cap: 1`, which is the shipped default: no
    # second wave runs, no finding is emitted, and no vendor's score moves. They are declared in
    # the model rather than added later because a signal a collector can emit and the model does
    # not band scores nothing while looking live — the drift `_validate_no_dead_config` exists to
    # catch, arriving from the other direction. `planned_signal_count` excludes them from the
    # coverage denominator until the cap is raised, so declaring them costs no vendor confidence.
    assert len(cfg.penalising_bands()) == 41, (
        "penalising band count moved. If that was intentional, update this number in the same "
        "commit as the scoring.yaml change and record the reason; if not, a band just gained or "
        "lost a penalty by accident."
    )


def test_actions_carry_the_dispute_input():
    """`accepts_as_refute` is what a vendor needs in order to contest a finding fairly.
    'Prove me wrong' is not a specification."""
    cfg = get_scoring_config()
    without = [f"{sig}.{band}" for _c, sig, band in cfg.penalising_bands()
               if not (cfg.action_for(sig, band) or {}).get("accepts_as_refute")]
    assert without == []


def test_recheck_cadences_are_from_the_agreed_set():
    cfg = get_scoring_config()
    allowed = {"7d", "14d", "30d", "90d"}
    for _c, sig, band in cfg.penalising_bands():
        assert (cfg.action_for(sig, band) or {}).get("recheck_after") in allowed, f"{sig}.{band}"


def test_live_criticals_are_rechecked_soonest():
    """A finding that says a certificate is expired right now cannot carry a 90-day cadence.

    `domain_registration.domain_suspended` was in this list until E4. It is still urgent — a
    suspended domain interrupts service immediately — but it is a going-concern fact rather than
    a security control, so it now surfaces as a Continuity flag with its own cadence. See
    test_continuity.py.
    """
    cfg = get_scoring_config()
    for signal, band in [("cert_validity", "expired_serving_prod"), ("kev_listed_cve", "listed")]:
        assert cfg.action_for(signal, band)["recheck_after"] == "7d"


def test_a_penalising_band_without_an_action_fails_the_loader(tmp_path: Path):
    data = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "scoring.yaml").read_text(encoding="utf-8"))
    del data["actions"]["dmarc"]["absent"]
    with pytest.raises(ScoringConfigError, match="no action"):
        ScoringConfig(data, tmp_path / "scoring.yaml")


def test_an_action_for_a_band_that_does_not_exist_fails_the_loader(tmp_path: Path):
    """Advice that has drifted from its finding is worse than none — it is confidently wrong."""
    data = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "scoring.yaml").read_text(encoding="utf-8"))
    data["actions"]["dmarc"]["p_invented"] = {"action": "x", "recheck_after": "30d"}
    with pytest.raises(ScoringConfigError, match="do not exist"):
        ScoringConfig(data, tmp_path / "scoring.yaml")


# --------------------------------------------------------------------- 1.2 recommendation


def test_a_ghost_never_gets_a_plain_approve():
    """The single most important row. A vendor can look clean because nothing is publicly visible
    about it; approving on that basis is the worst call this system could make."""
    clean = recommend(_score(grade="A"))
    ghost = recommend(_score(grade="A", conf=0.45, band="Low", ghost=True))
    assert clean.decision == "approve"
    assert ghost.decision == "approve_pending_questionnaire"
    assert "not a clean bill of health" in ghost.detail


def test_criticality_changes_the_call_at_the_same_grade():
    low = recommend(_score(grade="C"), criticality="low")
    high = recommend(_score(grade="C"), criticality="high")
    assert low.decision == "approve_with_conditions"
    assert high.decision == "request_remediation"
    assert high.recheck_after == "7d"


def test_blocked_never_produces_a_recommendation_to_proceed():
    blocked = recommend(Score(vendor_ref="x", blocked=True, blocked_reason="sanctions screen hit",
                              overall_confidence=0.0, confidence_band="Low"))
    assert blocked.decision == "blocked"
    assert blocked.recheck_after is None
    assert "adjudicat" in blocked.detail


def test_refused_is_not_read_as_clean():
    refused = recommend(Score(vendor_ref="x", refused=True, ghost=True, posture=None,
                              overall_confidence=0.2, confidence_band="Low"))
    assert refused.decision == "insufficient_evidence"
    assert "must not be read as one" in refused.detail


@pytest.mark.parametrize("grade,expected", [
    ("A", "approve"), ("B", "approve"), ("C", "approve_with_conditions"),
    ("D", "full_due_diligence"), ("F", "reject"),
])
def test_grade_drives_the_decision(grade, expected):
    assert recommend(_score(grade=grade)).decision == expected


def test_recommendation_is_deterministic():
    a = recommend(_score(grade="C"), criticality="high", soonest="30d")
    b = recommend(_score(grade="C"), criticality="high", soonest="30d")
    assert a.model_dump() == b.model_dump()


def test_recommendation_is_always_advisory():
    assert recommend(_score(grade="F")).advisory is True


def test_critical_ceiling_is_called_out_and_pulls_the_recheck_forward():
    r = recommend(_score(grade="D", critical_ceiling_applied=True,
                         ceiling_cause="cert_validity=expired"), criticality="low")
    assert "capped this grade" in r.detail
    assert r.recheck_after == "7d"


def test_soonest_recheck_wins():
    """A 90-day cadence is wrong if one finding on the card says look again in seven days."""
    assert soonest_recheck("90d", "7d") == "7d"
    assert soonest_recheck("30d", None) == "30d"
    assert recommend(_score(grade="A"), soonest="7d").recheck_after == "7d"


def test_urgency_follows_the_cadence():
    """Found live on a real vendor: a grade-B score with a KEV finding read
    'Proceed · routine · re-check in 7 days'. A reader resolving that contradiction believes the
    headline and ignores the cadence — the wrong half to believe."""
    routine = recommend(_score(grade="A"))
    urgent = recommend(_score(grade="A"), soonest="7d")
    assert routine.urgency == "routine"
    assert urgent.urgency == "act"
    assert "within the week" in urgent.detail


# --------------------------------------------------------------------- 1.3 REMOVED at E1
# `industry_profiles` promoted a severity by one step where a sector cited a named instrument.
# Eleven tests covering that machinery were deleted with it — they asserted the promotion fired,
# was capped at one step, never demoted, required a basis, and was disclosed on the finding.
# Every one of those properties was a sensible guard on a mechanism that should not exist.
#
# What replaces them: test_scoring.test_sector_never_changes_a_severity asserts the INVERSE
# invariant at the engine boundary, and test_scoring_config pins that the machinery is gone from
# both the config and the loader. The sector obligation moves to the Compliance Gap (E9c) —
# the design notes preserves both `basis:` strings verbatim.
# --------------------------------------------------------------------- end-to-end


@pytest.mark.parametrize("ref", ALL_REFS)
def test_a_sector_with_no_profile_leaves_the_corpus_untouched(ref):
    """The corpus vendors are `technology`, which ships no profile. Passing their sector must
    produce byte-identical scores — proof that the base model is genuinely the default.

    Runs over ALL_REFS since E0.2: the archetypes include a blocked and a refused vendor, whose
    Score objects take a different code path through the engine entirely.
    """
    vendor, results = load_fixture(ref)
    base = ScoringEngine().score(vendor, results, now=AS_AT).score
    with_sector = ScoringEngine().score(vendor, results, now=AS_AT, sector="technology").score
    drop = {"computed_at"}
    assert {k: v for k, v in with_sector.model_dump().items() if k not in drop} == \
           {k: v for k, v in base.model_dump().items() if k not in drop}

# ------------------------------------------------- E10a -> monitoring cadence, and NOTHING else


def test_a_material_peer_gap_moves_the_clock_and_only_the_clock():
    """The one integration industry guidance names that this system did not have: *"a higher gap or
    lower peer rank can increase review frequency for high-inherent suppliers."*

    THE LINE IT MUST NOT CROSS. A vendor materially below its peers at the same grade as one
    sitting on the median is not a worse vendor by our arithmetic — it is a vendor whose position
    is harder to explain, and the honest response is to look again sooner, not to score them lower.
    Letting a peer comparison move a DECISION would be the firmographic multiplier E1 deleted,
    arriving through the benchmark instead of through the sector table.
    """
    baseline = recommend(_score(grade="B"), criticality="low")
    behind = recommend(_score(grade="B"), criticality="low", expectation_gap=-20)

    assert behind.decision == baseline.decision, "a peer gap must not change the call"
    assert behind.headline == baseline.headline
    assert behind.recheck_after == "30d" and baseline.recheck_after == "90d"
    assert "materially behind comparable suppliers" in behind.detail
    assert "does not change the grade" in behind.detail


def test_the_cadence_response_scales_with_what_the_buyer_has_at_stake():
    """Being fifteen points behind your peers is informative for any supplier and ACTIONABLE for
    one the buyer depends on."""
    replaceable = recommend(_score(grade="B"), criticality="low", expectation_gap=-20)
    depended_on = recommend(_score(grade="B"), criticality="high", expectation_gap=-20)
    assert replaceable.recheck_after == "30d"
    assert depended_on.recheck_after == "14d"


def test_a_vendor_at_or_above_its_peers_is_unchanged():
    """The gap reaches the cadence only when it is MATERIAL and NEGATIVE. Sitting level with your
    peer group is not an event, and sitting above it is certainly not one."""
    baseline = recommend(_score(grade="B"), criticality="low")
    for gap in (None, 0, 12, -5, -14):
        assert recommend(_score(grade="B"), criticality="low",
                         expectation_gap=gap).model_dump() == baseline.model_dump()


def test_no_peer_group_leaves_the_recommendation_exactly_as_it_was():
    """Most vendors will have no cohort for a long time (E11 is the pool). A missing peer group
    must cost a reader their peer context and nothing else — never a different recommendation."""
    assert (recommend(_score(grade="C"), criticality="high", expectation_gap=None).model_dump()
            == recommend(_score(grade="C"), criticality="high").model_dump())
