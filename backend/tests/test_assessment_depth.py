"""P5 — inherent tier decides collection depth and review cadence.

The four-row table is the least interesting part. What is worth pinning are the two decisions the
table forced, because both could have gone the flattering way:

  * A SHALLOWER RUN'S CONFIDENCE IS ALLOWED TO FALL. The denominator is not rebased onto whatever
    the chosen depth planned, so a screening run refuses rather than reporting high confidence in
    four collectors. If that is ever "fixed", `0.8` starts meaning two different things in one
    column and nothing in the book is comparable again.
  * UNDECLARED IS NOT T4. Routing unclassified relationships to the cheapest treatment would put
    the thinnest assessment exactly where the unknown risk is.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.assessment_depth import (
    AssessmentPlan,
    as_dict,
    is_due,
    plan_for,
    sources_for_depth,
    table,
)
from app.collectors import all_collectors
from app.scoring_config import load_scoring_config

# ============================================================ the table


@pytest.mark.parametrize(
    "tier,depth,cadence,days",
    [
        ("critical", "full", "quarterly", 90),
        ("high", "full", "semi_annual", 182),
        ("medium", "core", "annual", 365),
        ("low", "screening", "passive", None),
    ],
)
def test_the_published_table_is_the_plans_table(tier, depth, cadence, days):
    p = plan_for(tier)
    assert (p.depth, p.cadence, p.cadence_days) == (depth, cadence, days)


def test_effort_is_monotone_in_exposure():
    """A higher tier never gets a shallower run or a longer interval than a lower one.

    The whole claim of P5 is "effort matches exposure". A table that inverted anywhere would be
    worse than one clock for the whole book, because it would look principled while doing the
    opposite.
    """
    order = ["low", "medium", "high", "critical"]
    rank = {"screening": 0, "core": 1, "full": 2}
    depths = [rank[plan_for(t).depth] for t in order]
    assert depths == sorted(depths)
    # A passive cadence is the longest possible interval, so it sorts as infinity.
    intervals = [plan_for(t).cadence_days or 10**9 for t in order]
    assert intervals == sorted(intervals, reverse=True)


def test_only_the_critical_tier_gets_the_fourth_party_map():
    assert "fourth-party dependency map" in plan_for("critical").artefacts
    for tier in ("high", "medium", "low"):
        assert "fourth-party dependency map" not in plan_for(tier).artefacts


# ============================================================ the confidence decision


def test_a_screening_run_cannot_reach_the_evidence_floor_so_it_publishes_no_posture():
    """The refusal is arithmetic, not a policy flag — and this asserts the arithmetic.

    A screening run queries seven sources, none of which feed the hygiene categories. Even counting
    every signal those seven sources could possibly produce, the coverage they can reach is below
    `refuse_below`, so the run refuses. `publishes_posture=False` reports a fact about the model
    rather than a decision someone made.
    """
    plan = plan_for("low")
    assert plan.publishes_posture is False
    cfg = load_scoring_config()
    sources = sources_for_depth("screening")
    assert sources is not None
    fraction = len(sources) / len([c for c in all_collectors() if c.on_demand])
    assert fraction < cfg.refuse_below(), (
        "a screening run must sit below the evidence floor; if this ever passes the floor, "
        "`publishes_posture` is claiming something the engine will not do"
    )


def test_the_denominator_is_never_rebased_onto_the_chosen_depth():
    """The one change that would quietly destroy comparability, pinned as a structural fact.

    `assessment_depth` must not import the scoring config or reference `planned_signal_count` —
    both would be the machinery of shrinking the denominator to flatter a deliberately shallow run.
    Depth restricts what we ASK FOR. It must never restrict what we MEASURE OURSELVES AGAINST.
    """
    src = Path("app/assessment_depth.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not {"scoring_config", ".scoring_config"} & imported

    # Named in the docstring on purpose — the module EXPLAINS why it does not do this. So the
    # assertion is over the syntax tree, not the source text: what matters is that no denominator
    # machinery is CALLED, and prose arguing against a thing is not the thing.
    referenced = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    } | {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    assert not {"planned_signal_count", "unreachable_signals", "refuse_below"} & referenced


def test_core_depth_says_out_loud_that_its_confidence_will_be_lower():
    joined = " ".join(plan_for("medium").caveats)
    assert "GENUINELY SEES LESS" in joined
    assert "denominator is not reduced" in joined


# ============================================================ undeclared


def test_an_undeclared_tier_gets_full_depth_and_is_not_t4():
    p = plan_for(None)
    assert p.tier is None
    assert p.declared is False
    assert p.depth == "full"
    assert p.publishes_posture is True
    assert p.cadence_days == plan_for("high").cadence_days
    assert "not T4" in " ".join(p.caveats)


def test_an_unknown_tier_string_falls_to_undeclared_rather_than_to_low():
    """Defensive, and in the safe direction. A tier this module does not know must not silently
    become the cheapest row — the same reason `inherent_tier` refuses to default to `low`."""
    p = plan_for("wildly_unexpected")  # type: ignore[arg-type]
    assert p.depth == "full"
    assert p.tier_label == "Unclassified"


# ============================================================ two clocks


def test_the_sooner_clock_wins_and_names_itself():
    p = plan_for("low")                       # passive: no review cadence at all
    nxt = p.next_action_in("7d")
    assert nxt["days"] == 7
    assert nxt["driver"] == "outstanding finding"

    p = plan_for("critical")                  # quarterly
    assert p.next_action_in(None)["driver"] == "review cadence"
    assert p.next_action_in("30d")["days"] == 30
    assert p.next_action_in("30d")["driver"] == "outstanding finding"


def test_a_passive_relationship_with_nothing_outstanding_has_no_next_date():
    nxt = plan_for("low").next_action_in(None)
    assert nxt["days"] is None
    assert "not on a clock" in str(nxt["note"])


def test_an_urgent_finding_pulls_a_passive_vendor_forward():
    """The failure this guards: `--by-tier` parking a real problem because the RELATIONSHIP is
    unimportant. An expired certificate serving production is a seven-day item on any tier."""
    plan = plan_for("low")
    due, why = is_due(plan, days_since_last_score=9.0, finding_recheck="7d")
    assert due is True
    assert "outstanding finding" in why


def test_a_passive_vendor_with_no_findings_is_never_due():
    due, why = is_due(plan_for("low"), days_since_last_score=900.0, finding_recheck=None)
    assert due is False
    assert "passive" in why


def test_a_vendor_that_has_never_been_scored_is_always_due():
    due, why = is_due(plan_for("low"), days_since_last_score=None)
    assert due is True and why == "never scored"


def test_a_tier_interval_actually_gates():
    plan = plan_for("critical")               # 90 days
    assert is_due(plan, 89.0)[0] is False
    assert is_due(plan, 90.0)[0] is True


# ============================================================ depth -> collectors


def test_each_depth_is_a_superset_of_the_shallower_one():
    screening, core = sources_for_depth("screening"), sources_for_depth("core")
    assert screening is not None and core is not None
    assert screening < core
    assert sources_for_depth("full") is None


def test_full_is_expressed_as_no_restriction_so_a_new_collector_is_never_orphaned():
    """An allowlist for `full` would need updating every time a collector ships, and forgetting is
    silent: the collector runs nowhere and the only symptom is a slightly lower confidence."""
    assert sources_for_depth("full") is None
    src = Path("app/assessment_depth.py").read_text(encoding="utf-8")
    assert '"full": None' in src


def test_every_named_source_is_a_collector_that_exists():
    """A depth naming a source no collector registers would silently narrow the run further than
    intended — and the symptom is, again, a confidence figure nobody can explain."""
    registered = {c.source for c in all_collectors()}
    for depth in ("screening", "core"):
        named = sources_for_depth(depth)
        assert named is not None
        assert named <= registered, f"{depth} names unregistered source(s): {named - registered}"


def test_screening_carries_the_sanctions_and_entity_sources_the_plan_names():
    screening = sources_for_depth("screening")
    assert screening is not None
    assert "ita" in screening          # the sanctions gate's evidence
    assert {"gleif", "rdap"} <= screening
    # ...and none of the hygiene probing, which is the whole point of the saving.
    assert not {"tls", "headers", "dns", "ct", "nvd", "kev"} & screening


# ============================================================ rendering


def test_as_dict_publishes_the_depth_the_cadence_and_why():
    d = as_dict(plan_for("critical"), "7d")
    assert d["collection"]["depth"] == "full"
    assert d["collection"]["sources"] is None
    assert d["review_cadence"]["days"] == 90
    assert d["next_action"]["days"] == 7
    assert "Inherent tier is critical" in str(d["basis"])


def test_the_published_table_covers_every_declared_tier():
    rows = table()
    assert [r["inherent_tier"] for r in rows] == ["critical", "high", "medium", "low"]
    assert sum(1 for r in rows if not r["publishes_posture"]) == 1


def test_a_plan_is_frozen_so_nothing_downstream_can_edit_a_cadence():
    """Stored nowhere and immutable once built — the same discipline `ResidualRisk` follows. A
    mutable plan is one a renderer can 'adjust', and an adjusted cadence has no basis behind it."""
    p = plan_for("high")
    assert isinstance(p, AssessmentPlan)
    with pytest.raises(Exception):
        p.cadence_days = 1  # type: ignore[misc]
