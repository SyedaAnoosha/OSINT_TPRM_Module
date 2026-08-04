"""E10b — Inherent Risk Tier and the Residual Risk view procurement decides from.

THREE THINGS, KEPT APART:

    Posture   — how strong the vendor looks. Ours to measure.
    Inherent  — how much this buyer stands to lose. Theirs to declare.
    Residual  — the published combination. A deterministic lookup, not a third measurement.

The load-bearing assertion in this file is that a strong posture does not cancel high inherent
exposure. A vendor holding your production data with an A grade is still a vendor holding your
production data, and the day their posture moves you find out how much you had riding on it.
"""

from __future__ import annotations

import itertools

import pytest

from app.residual_risk import (
    _RESIDUAL_LABELS,
    inherent_tier,
    matrix,
    posture_band,
    residual_risk,
)

_ORDER = ["low", "low_medium", "medium", "medium_high", "high", "critical"]
_TIERS = ["low", "medium", "high", "critical"]


# --------------------------------------------------------------------- the inherent tier


def test_the_inherent_tier_is_the_worse_of_the_two_declarations():
    """Non-compensatory, on purpose. A vendor holding production customer data is a critical
    exposure even if the service is replaceable, and a vendor running a business-critical process
    is a high exposure even if they hold nothing sensitive. Averaging would let each excuse the
    other — the compensatory move this system refuses in continuity and in the critical ceiling."""
    assert inherent_tier("low", "critical").tier == "critical"
    assert inherent_tier("high", "low").tier == "high"
    assert inherent_tier("medium", "medium").tier == "medium"
    assert "HIGHER of the two" in inherent_tier("high", "low").basis


def test_an_undeclared_exposure_is_not_low():
    """The failure in the dangerous direction. Defaulting an undeclared exposure to `low` would
    present every unclassified vendor as low-residual — and the unclassified ones are
    disproportionately the ones nobody has looked at."""
    undeclared = inherent_tier(None, None)
    assert undeclared.tier is None
    assert undeclared.published is False
    assert undeclared.label == "Not declared"
    assert "not the same as low" in undeclared.basis

    out = residual_risk(95, None, None)
    assert out.published is False
    assert out.residual is None


def test_one_input_is_used_and_the_understatement_is_disclosed():
    """Half an answer beats none, but the reader must know it is half."""
    only_criticality = inherent_tier("high", None)
    assert only_criticality.tier == "high"
    assert "may understate" in only_criticality.basis


def test_data_access_scope_is_reused_not_reinvented():
    """EB deliberately kept `data_access_scope` OUT of cohort keying — it is a property of the
    RELATIONSHIP, so keying on it would put one supplier in different cohorts for different buyers
    and fragment the pool ~4x exactly where n>=30 is needed. EB routed it to "interpretation".
    This is the interpretation it routes to, and reusing it means a client answers once."""
    from app.benchmarking.config import _SCOPES

    for scope in _SCOPES:
        assert inherent_tier(None, scope).tier == scope


# --------------------------------------------------------------------- the matrix


def test_high_inherent_plus_strong_posture_never_resolves_to_low():
    """THE CELL THAT MATTERS MOST, and the one a compensatory model gets wrong. Inherent exposure
    does not vanish because controls look good."""
    strong_high = residual_risk(95, "high", None)
    assert strong_high.residual == "medium"
    assert strong_high.residual != "low"

    strong_critical = residual_risk(100, None, "critical")
    assert strong_critical.residual == "medium_high"
    assert any("does not resolve to low residual risk" in c for c in strong_critical.caveats)


def test_the_matrix_is_monotone_in_both_directions():
    """A worse posture can never improve residual risk, and greater exposure can never reduce it.
    Sixteen hand-written cells are exactly the sort of table where one transposed entry survives
    review — this is the property that catches it."""
    postures = [95, 70, 50, 20]                       # strong, moderate, weak, poor
    for tier in _TIERS:
        rank = [_ORDER.index(residual_risk(p, None, tier).residual) for p in postures]
        assert rank == sorted(rank), f"residual improves as posture worsens at inherent={tier}"

    for posture in postures:
        rank = [_ORDER.index(residual_risk(posture, None, t).residual) for t in _TIERS]
        assert rank == sorted(rank), f"residual improves as exposure rises at posture={posture}"


def test_every_cell_is_reachable_and_labelled():
    """A cell nobody can land in is dead config wearing a table; a label nobody set is a blank on
    an executive summary."""
    seen = set()
    for posture, tier in itertools.product([95, 70, 50, 20], _TIERS):
        out = residual_risk(posture, None, tier)
        assert out.residual in _RESIDUAL_LABELS
        assert out.residual_label == _RESIDUAL_LABELS[out.residual]
        seen.add(out.residual)
    assert seen == set(_ORDER), f"unreachable residual tiers: {set(_ORDER) - seen}"


def test_the_posture_band_boundaries_match_the_published_table():
    """80 / 60 / 40, inclusive at the bottom. Off-by-one here moves a vendor a whole row."""
    assert posture_band(100) == posture_band(80) == "strong"
    assert posture_band(79) == posture_band(60) == "moderate"
    assert posture_band(59) == posture_band(40) == "weak"
    assert posture_band(39) == posture_band(0) == "poor"


def test_the_published_matrix_matches_what_the_lookup_does():
    """The table a UI renders and the table the API computes from must be the same table."""
    for row in matrix():
        for tier, label in row["cells"].items():
            posture = {"strong": 95, "moderate": 70, "weak": 50, "poor": 20}[row["posture_band"]]
            assert residual_risk(posture, None, tier).residual_label == label


# --------------------------------------------------------------------- the refusals


def test_a_blocked_vendor_gets_no_residual_tier():
    """A residual tier computed against a missing posture is an inherent tier wearing a residual
    label, and it would clear a "≤ High" procurement threshold that the block exists to stop."""
    out = residual_risk(None, "high", "critical", blocked=True)
    assert out.published is False
    assert "blocked pending human adjudication" in out.reason
    assert out.headline() is None


def test_insufficient_evidence_is_adverse_here_too():
    """Consistent with E7d. The absence of a posture is not a neutral input to a risk view."""
    out = residual_risk(None, "high", None, refused=True)
    assert out.published is False
    assert "ADVERSE result, not a neutral one" in out.reason
    assert "inherent tier as the current exposure" in out.reason


# --------------------------------------------------------------------- the invariant


def test_residual_risk_is_never_stored_and_never_reaches_a_score():
    """A RENDERING, NOT A SCORE. The moment there is a `residual` column it can drift from the
    posture and inherent tier it was derived from, and a reader has no way to tell which is stale.
    Recomputed on read, always."""
    import inspect

    from app import residual_risk as module
    from app.models import Score

    assert not hasattr(Score, "residual")
    assert "residual" not in Score.model_fields

    source = inspect.getsource(module)
    for forbidden in ("store.", "put_", "INSERT", "UPDATE"):
        assert forbidden not in source, f"{forbidden!r} — residual risk must not be persisted"


def test_inherent_risk_is_never_inferred_from_public_data():
    """Both inputs are client-supplied. Inferring what a vendor holds for a buyer would be
    `industry_profiles` in a third costume: our label, published as their exposure."""
    import inspect

    from app import residual_risk as module

    source = inspect.getsource(module)
    for forbidden in ("sector", "collector", "finding", "Finding"):
        assert forbidden not in source, (
            f"{forbidden!r} reaches the inherent tier — it must come from the client, not from us"
        )


# ------------------------------------------------------------------ P8 · the sole-source escalation


def test_sole_source_escalates_the_published_tier_by_one_band():
    """The plan's own table row. A vendor you cannot replace does not have weaker controls — it
    changes what a control failure COSTS, which is why it moves the residual tier and not the
    posture."""
    plain = residual_risk(85, criticality="high", data_access_scope="high")
    sole = residual_risk(85, criticality="high", data_access_scope="high",
                         substitutability="sole_source")
    assert plain.residual == "medium"
    assert sole.residual == "medium_high"
    assert sole.escalated_from == "medium"
    assert sole.escalated is True


def test_the_escalation_is_disclosed_never_absorbed():
    """`escalated_from` keeps the cell the matrix actually produced. An escalation nobody can undo
    in their head is an adjustment, not a lookup — and the whole reason this is a table."""
    sole = residual_risk(85, criticality="high", data_access_scope="high",
                         substitutability="sole_source")
    assert sole.escalated_from == "medium"
    joined = " ".join(sole.caveats)
    assert "ESCALATED ONE BAND FOR SOLE SOURCE" in joined
    assert "Medium" in joined and "Medium-High" in joined


@pytest.mark.parametrize("value", ["low", "medium", "high", None])
def test_only_sole_source_escalates(value):
    """There is no de-escalation. An easily replaced vendor is not LESS exposed to a control
    failure while you are still using them, and a rule that could lower a residual tier on a
    client's own declaration is a rule that will be used to lower it."""
    plain = residual_risk(85, criticality="high", data_access_scope="high")
    got = residual_risk(85, criticality="high", data_access_scope="high", substitutability=value)
    assert got.residual == plain.residual
    assert got.escalated is False


def test_a_tier_already_critical_has_nowhere_to_escalate_and_says_so():
    """Inventing a band above the top to express "worse than critical" would break the published
    vocabulary to say something the word critical already says."""
    out = residual_risk(20, criticality="high", data_access_scope="critical",
                        substitutability="sole_source")
    assert out.residual == "critical"
    assert out.escalated is False
    assert any("no band to escalate into" in c for c in out.caveats)


def test_the_escalation_cannot_manufacture_a_tier_out_of_a_refusal():
    """A refused or blocked record publishes no residual tier at all, and sole source does not
    change that — escalating nothing is still nothing."""
    for kwargs in ({"refused": True}, {"blocked": True}):
        out = residual_risk(30, criticality="high", data_access_scope="high",
                            substitutability="sole_source", **kwargs)
        assert out.published is False
        assert out.residual is None
        assert out.escalated is False
        assert out.substitutability == "sole_source"   # still reported, just not acted on
