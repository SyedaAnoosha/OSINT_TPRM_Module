"""P9 — the programme maturity self-assessment and the KPI dashboard.

Two things are worth pinning here, and neither is the levels themselves (those are judgements, and
a test that asserted "governance is 3" would just be the same opinion written twice):

  * **THE CLAIMS EACH LEVEL RESTS ON ARE CHECKED AGAINST THE TREE.** A hardcoded self-assessment
    goes stale the moment somebody builds the thing it says is missing. Every dimension cites
    checkable facts — a module that must exist, a module that must NOT — and this file walks them.
    Building `app/offboarding.py` fails the test that says lifecycle coverage is Reactive *because*
    offboarding is absent, which is precisely when a human should re-score that dimension.
  * **NOTHING HERE REACHES A VENDOR SCORE.** A programme that lets its own self-assessment adjust
    its vendors' numbers has built a mirror.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app import program_maturity as pm
from app.program_kpis import (
    METRICS,
    MetricValue,
    PeerFigureError,
    as_dict as kpis_as_dict,
    peer_figure,
)

# ============================================================ the assessment holds together


def test_every_dimension_the_plan_names_is_assessed():
    """Eight dimensions, verbatim from the phase plan. A missing one is a dimension nobody scored,
    which reads on the page as a dimension with no problems."""
    keys = {d.key for d in pm.dimensions()}
    assert keys == {
        "governance_policy", "inventory_tiering", "assessment_methodology",
        "continuous_monitoring", "remediation_issues", "lifecycle_coverage",
        "technology_data_quality", "reporting_engagement",
    }
    assert len(pm.dimensions()) == 8


@pytest.mark.parametrize("d", pm.dimensions(), ids=lambda d: d.key)
def test_every_dimension_carries_a_rationale_evidence_and_a_next_step(d):
    """A level with no rationale is a number; a level with no next step is a complaint."""
    assert 1 <= d.level <= 5
    assert len(d.rationale) > 200, "a one-line rationale is not a documented self-assessment"
    assert d.claims, "a level resting on nothing checkable is an opinion"
    assert len(d.to_reach_next) > 60


def test_the_overall_level_is_the_minimum_and_not_the_average():
    """THE RULE THE PLAN NAMES. An average would let the dimensions this codebase is naturally
    good at conceal the ones that will fail an audit."""
    levels = [d.level for d in pm.dimensions()]
    assert pm.overall_level() == min(levels)
    average = sum(levels) / len(levels)
    assert pm.overall_level() < average, (
        "if the minimum ever equals the average, this test stops proving anything — check that "
        "the distinction is still being drawn"
    )


def test_the_headline_names_what_is_holding_the_level_down():
    """The useful output is not the number, it is which dimensions produced it."""
    headline = pm.headline()
    assert "MINIMUM" in headline and "not an average" in headline
    for d in pm.limiting_dimensions():
        assert d.name in headline
    assert pm.limiting_dimensions()
    assert all(d.level == pm.overall_level() for d in pm.limiting_dimensions())


def test_there_is_no_formula_producing_the_levels():
    """The plan is explicit: "do not build a formula that produces a fake precision." The levels
    are literals with rationales, so the module must contain no arithmetic over them."""
    tree = ast.parse(Path("app/program_maturity.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp):
            names = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
            assert "level" not in names, f"arithmetic on a maturity level: {ast.dump(node)}"


# ============================================================ the claims are still true


@pytest.mark.parametrize(
    "claim",
    [c for d in pm.dimensions() for c in d.claims],
    ids=lambda c: f"{c.kind}:{c.target}",
)
def test_each_level_rests_on_a_claim_that_is_still_true(claim):
    """THE ANTI-STALENESS MECHANISM, and the reason this file is worth more than the levels.

    A FAILURE HERE IS NOT A BUG — it is the signal that the codebase moved and a dimension needs
    re-scoring by a person. `module_absent` claims are the valuable ones: they are the gaps the
    assessment is *held down by*, so building one of those modules should force somebody to
    revisit the level that cited its absence.
    """
    if claim.kind in ("module_present", "module_absent"):
        exists = Path(claim.target).exists()
        want = claim.kind == "module_present"
        assert exists is want, (
            f"{claim.target} {'is now present' if exists else 'has gone'} — the maturity "
            f"assessment cites its {'absence' if want is False else 'presence'} as evidence. "
            f"Re-score the dimension rather than editing this test."
        )
    else:
        routes = Path("app/api.py").read_text(encoding="utf-8")
        served = f'"{claim.target}"' in routes
        assert served is (claim.kind == "route_present"), (
            f"{claim.target} is {'served' if served else 'no longer served'}; the assessment "
            f"cites the opposite."
        )


def test_the_module_absent_claims_are_the_ones_holding_the_level_down():
    """A sanity check on the shape of the assessment: the dimensions at the floor should be the
    ones citing something missing, not ones citing only what exists."""
    limiting = pm.limiting_dimensions()
    assert limiting
    for d in limiting:
        assert any(c.kind == "module_absent" for c in d.claims), (
            f"{d.key} is at the floor but cites nothing missing — either the rationale or the "
            f"level is wrong"
        )


# ============================================================ nothing reaches a vendor score


@pytest.mark.parametrize("module", ["app/program_maturity.py", "app/program_kpis.py"])
def test_p9_never_writes_and_never_scores(module):
    """The same discipline as `test_benchmarking_never_alters_input_scores`. A programme that
    scores its own maturity and then lets that maturity move its vendors' scores has built a
    mirror — and every number in it would be self-confirming."""
    src = Path(module).read_text(encoding="utf-8")
    tree = ast.parse(src)

    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not {"scoring.engine", ".scoring.engine", "pipeline", ".pipeline"} & imported

    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    writes = {c for c in called if c.startswith("put_") or c.startswith("save")}
    assert not writes, f"{module} writes to the store: {writes}"


def test_the_maturity_module_reads_no_store_at_all():
    """A maturity level that varied by which vendor you asked about would be measuring the wrong
    subject entirely."""
    tree = ast.parse(Path("app/program_maturity.py").read_text(encoding="utf-8"))
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert imported <= {"__future__", "dataclasses", "typing"}, f"unexpected: {imported}"


# ============================================================ the dashboard's honesty rules


def test_the_dashboard_is_capped_at_fifteen_metrics():
    """The cap is the point: a dashboard nobody reads is one with thirty rows on it."""
    assert len(METRICS) <= 15
    assert len({m.key for m in METRICS}) == len(METRICS)


@pytest.mark.parametrize("m", METRICS, ids=lambda m: m.key)
def test_every_metric_names_its_owner_formula_source_target_and_cadence(m):
    """The plan's list, and each element is what lets a reader argue with the number."""
    assert m.owner and m.formula and m.source and m.target and m.cadence
    assert m.provenance in ("platform-derived", "manually-supplied")


def test_metrics_with_no_osint_source_are_tagged_and_never_computed():
    """E14 argued `stakeholder_satisfaction` out to add `gap_analysis_acceptance_rate` — see the
    reasoning recorded above `METRICS` in program_kpis.py. The three remaining manually-supplied
    metrics still have no OSINT source; the fourth slot is now platform-derived."""
    manual = [m for m in METRICS if m.provenance == "manually-supplied"]
    assert {m.key for m in manual} == {
        "staffing_ratio", "cost_per_assessment", "policy_exception_rate",
    }
    for m in manual:
        assert "MANUAL" in m.source


def test_an_unsupplied_metric_is_empty_and_names_its_owner_rather_than_showing_a_number():
    """NEVER BACKFILLED, ESTIMATED OR DEFAULTED. An empty cell asks a question; a plausible number
    answers it wrongly — the same refusal P2 makes for coverage and E10b for the residual cell."""
    metric = next(m for m in METRICS if m.key == "staffing_ratio")
    v = MetricValue(metric, value=None,
                    unavailable_reason=f"NOT SUPPLIED. {metric.owner} owns supplying it.")
    body = kpis_as_dict([v])
    row = body["metrics"][0]
    assert row["value"] is None
    assert row["unavailable_reason"]
    assert metric.owner in row["unavailable_reason"]
    assert "staffing_ratio" in body["unsupplied"]
    assert body["not_computable"] == [], "a manual metric is unsupplied, never uncomputable"


def test_a_supplied_manual_metric_is_still_tagged_as_manual():
    """Supplying a value must not launder it into a platform-derived number."""
    metric = next(m for m in METRICS if m.key == "cost_per_assessment")
    body = kpis_as_dict([MetricValue(metric, value=1234)])
    assert body["metrics"][0]["value"] == 1234
    assert body["metrics"][0]["provenance"] == "manually-supplied"
    assert body["unsupplied"] == []


def test_the_dashboard_measures_things_the_programme_is_bad_at():
    """Chosen on purpose. A dashboard whose every metric is green is measuring the wrong things."""
    keys = {m.key for m in METRICS}
    assert {"inherent_tier_declaration_rate", "blocked_pending_adjudication",
            "overdue_rechecks"} <= keys


def test_a_kri_declares_which_direction_is_good():
    """So a UI cannot invert a risk indicator by accident and render a rising ghost rate as
    improvement."""
    for key in ("ghost_rate", "overdue_rechecks", "blocked_pending_adjudication",
                "fourth_party_spof_count"):
        assert next(m for m in METRICS if m.key == key).lower_is_better is True
    assert next(m for m in METRICS if m.key == "published_posture_rate").lower_is_better is False


# ============================================================ peer figures


def test_a_peer_figure_carries_its_survey_year_and_n():
    p = peer_figure("cost_per_assessment", 4200, survey="Shared Assessments", year=2025, n=214)
    assert p.caption() == "Shared Assessments 2025, n=214"


@pytest.mark.parametrize("kwargs", [
    {"survey": "", "year": 2025, "n": 214},
    {"survey": "Gartner", "year": None, "n": 214},
    {"survey": "Gartner", "year": 2025, "n": 0},
    {"survey": "Gartner", "year": 2025, "n": None},
])
def test_a_peer_figure_without_provenance_is_refused(kwargs):
    """THE REFUSAL IS THE FEATURE. "Industry average: 42" with no survey behind it is the version
    of EB's unlabelled-cohort mistake that a board actually sees."""
    with pytest.raises((PeerFigureError, TypeError)):
        peer_figure("cost_per_assessment", 4200, **kwargs)


def test_a_peer_comparison_renders_with_its_caption_attached():
    metric = next(m for m in METRICS if m.key == "cost_per_assessment")
    body = kpis_as_dict(
        [MetricValue(metric, value=5100)],
        peers=[peer_figure("cost_per_assessment", 4200,
                           survey="Shared Assessments", year=2025, n=214)],
    )
    row = body["metrics"][0]
    assert row["peer_comparison"][0]["caption"] == "Shared Assessments 2025, n=214"


def test_two_kinds_of_missing_are_kept_apart():
    """"Nobody supplied it" is a programme gap somebody owns; "there is no population to measure"
    is a fact about the book. One list for both would let an unmeasurable metric read as an
    unassigned chore — the same collapse P2 refuses for its coverage buckets."""
    manual = next(m for m in METRICS if m.key == "staffing_ratio")
    derived = next(m for m in METRICS if m.key == "tier1_assessment_currency")
    body = kpis_as_dict([
        MetricValue(manual, value=None, unavailable_reason="NOT SUPPLIED."),
        MetricValue(derived, value=None, unavailable_reason="no critical-tier vendors"),
    ])
    assert body["unsupplied"] == ["staffing_ratio"]
    assert body["not_computable"] == ["tier1_assessment_currency"]


def test_metrics_with_no_peer_figure_say_none_rather_than_an_empty_promise():
    metric = next(m for m in METRICS if m.key == "ghost_rate")
    body = kpis_as_dict([MetricValue(metric, value=4.4)])
    assert body["metrics"][0]["peer_comparison"] is None
