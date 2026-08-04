"""E13 — bounded log-odds. Built, tested, and asserted to be OFF.

    L̃ = c^τ · L + (1 − c^τ) · L_peer          Posture = 100 · (1 − σ(L̃))

THE DEFECT IT FIXES. Today a vendor with three Criticals and one with fifteen both publish 0 — the
model has no ordering at the bottom of the scale, which is exactly where triage matters. E7 made it
worse before it makes it better: diminishing returns moved `synthetic_floor` from 16 to 39.

THE PROPERTY THAT MATTERS MOST is not the ordering, it is the incentive. An unmeasurable vendor
shrinks toward their cohort median rather than toward a flattering 100, so **hiding stops being
better than being average**. That removes the incentive rather than penalising the response to it,
which is why the Ghost cliff becomes unnecessary rather than merely redundant.

WHY THESE TESTS ASSERT A REFUSAL. `L_peer` needs a real pool, and E11 has not seeded one. Shrinking
toward six invented postures would be worse than not shrinking — so the refusal is the shipped
behaviour and it is held here.
"""

from __future__ import annotations

import pytest

from app.scoring.log_odds import (
    ShrinkageInput,
    enabled,
    logit,
    posture_from_log_odds,
    preconditions,
    shrink,
    sigmoid,
)


def _real_cohort(penalty: float, confidence: float, peer: float = 0.30,
                 n: int = 20) -> ShrinkageInput:
    """What the input looks like once E11 has seeded the pool."""
    return ShrinkageInput(penalty_fraction=penalty, confidence=confidence,
                          peer_penalty_fraction=peer, n_peers=n, peers_are_synthetic=False)


# --------------------------------------------------------------------- the refusal, today


def test_the_transform_refuses_while_the_peer_pool_is_synthetic():
    """THE SHIPPED BEHAVIOUR. Shrinking an under-evidenced vendor toward six invented postures
    replaces the system's most defensible property — we refuse to publish what we cannot evidence —
    with a confident number derived from fiction, applied hardest to exactly the vendors we know
    least about. That is materially worse than not shrinking at all."""
    synthetic = ShrinkageInput(penalty_fraction=0.4, confidence=0.3,
                               peer_penalty_fraction=0.3, n_peers=30, peers_are_synthetic=True)
    assert enabled(synthetic) is False
    out = shrink(synthetic)
    assert out.published is False
    assert out.posture is None
    assert "SYNTHETIC" in out.reason
    assert "E11" in out.reason


def test_the_precondition_cannot_be_waived_by_configuration():
    """A precondition that an `enabled: true` can override is not a precondition. `min_cohort_n: 1`
    is the standing evidence in this codebase that a setting which CAN be lowered eventually is —
    it shipped for months because a demo value survived into production.

    So the gate lives in code and reads nothing from YAML. Asserted by parsing the module's
    imports: there is no path from a config file to this decision.
    """
    import ast
    import inspect
    from pathlib import Path

    from app.scoring import log_odds

    tree = ast.parse(Path(inspect.getfile(log_odds)).read_text(encoding="utf-8"))
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert imported == {"math", "dataclasses", "__future__"}, (
        f"log_odds imports {sorted(imported)} — a precondition reachable from config is not one"
    )


def test_each_precondition_is_reported_separately():
    """A single boolean would collapse "the pool is not seeded yet" into "this vendor has no
    cohort". One is a programme task and the other is a per-vendor fact, and they go to different
    people."""
    assert preconditions(ShrinkageInput(0.4, 0.5, None, 0, True)) == [
        "no cohort penalty rate available — nothing to shrink toward",
        preconditions(ShrinkageInput(0.4, 0.5, 0.3, 30, True))[0],
        "cohort holds 0 peers, below the floor of 8",
    ]
    assert preconditions(_real_cohort(0.4, 0.5)) == []


def test_the_engine_computes_the_preview_and_consumes_it_nowhere():
    """The invariant that replaced *"the engine must not import this module"*.

    That earlier assertion was right while E13 was entirely absent, and became wrong the moment
    the preview shipped side-by-side — which is the point of a second release: both numbers
    visible, only one of them published. So the property is no longer *no import*, it is
    **computed and never consumed**.

    Asserted structurally, by parsing the engine: `log_odds_preview` may appear only where the
    `Score` is constructed. If it ever appears in an arithmetic expression, the notice period is
    decorative and a client's published number moved without a release.
    """
    import ast
    import inspect
    from pathlib import Path

    from app.scoring import engine

    tree = ast.parse(Path(inspect.getfile(engine)).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        # Any binary arithmetic touching the preview would fold it into a published figure.
        if isinstance(node, ast.BinOp):
            names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            assert "log_odds_preview" not in names, (
                "the E13 preview reaches the live arithmetic — it must be published beside the "
                "posture, never folded into it"
            )
        # And it must never be assigned to the published posture.
        if isinstance(node, ast.Assign):
            targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if "posture" in targets:
                sources = {n.id for n in ast.walk(node.value) if isinstance(n, ast.Name)}
                assert "log_odds_preview" not in sources


# --------------------------------------------------------------------- the shape, once enabled


def test_the_bottom_of_the_scale_keeps_ordering_vendors():
    """THE DEFECT, DEMONSTRATED. Under the current transform a vendor at 3x the cap and one at 6x
    both publish 0 — the model cannot triage the worst suppliers in a book, which is where triage
    is most needed."""
    def current(fraction: float) -> float:
        return max(0.0, 100.0 * (1.0 - fraction))     # clamped, exactly as the engine does

    assert current(3.0) == current(6.0) == 0.0, "the defect, stated"

    three = shrink(_real_cohort(0.97, 1.0)).posture
    fifteen = shrink(_real_cohort(0.999, 1.0)).posture
    assert three > fifteen > 0, "the transform must still separate them"


def test_it_never_floors_and_never_saturates():
    """σ is asymptotic at both ends. Neither 'certainly compromised' nor 'certainly clean' is a
    claim external observation can support, so the published range is honestly 0.5-99.5."""
    for fraction in (0.0, 1e-9, 0.5, 1 - 1e-9, 1.0):
        posture = shrink(_real_cohort(fraction, 1.0)).posture
        assert 0.0 < posture < 100.0, f"pinned at {posture} for fraction {fraction}"


def test_thin_evidence_pulls_toward_the_cohort_not_toward_a_hundred():
    """THE STRUCTURAL ARGUMENT, and the strongest one in the plan: it removes the incentive to hide
    rather than penalising the response to it.

    A vendor returning almost nothing to public OSINT currently looks clean — which is why the
    Ghost cliff exists. Here they shrink toward what is typical for their peer group, so being
    invisible lands near average instead of near excellent.

    THE RESIDUAL, STATED RATHER THAN ASSUMED AWAY. "Near" is not "at", and the first draft of this
    test asserted it was. At τ=1 and 5% coverage a vendor with nothing observable still lands about
    SIX POINTS above their cohort median, because 5% weight on very clean own-evidence is still
    weight. So the transform SHRINKS the incentive to hide from roughly thirty points to roughly
    six; it does not eliminate it.

    That is a real improvement and an honest limit, and it is the concrete thing τ is for: τ=2 at
    the same coverage cuts the residual to under two points. Which τ to ship is a judgement call
    that should be made with a seeded pool in front of the people making it (E11), not settled here
    by picking the number that makes this assertion pass.
    """
    peer = 0.30
    invisible = shrink(_real_cohort(0.001, confidence=0.05, peer=peer))
    peer_posture = posture_from_log_odds(logit(peer))
    residual = invisible.posture - peer_posture

    # Nothing like the ~30 points that looking clean buys under the current transform.
    assert 0 < residual < 8, f"residual pull toward a flattering score was {residual:.1f}"
    assert invisible.posture < 80, "hiding still bought a high score"
    assert invisible.weight < 0.1

    # And τ is the lever, which is why it is a parameter rather than a constant.
    sharper = shrink(_real_cohort(0.001, confidence=0.05, peer=peer), tau=2.0)
    assert sharper.posture - peer_posture < residual / 2


def test_full_coverage_uses_the_vendor_s_own_evidence_and_nothing_else():
    """The counterpart. Shrinkage must not quietly average away a well-evidenced result — a vendor
    we can see clearly is scored on what we can see."""
    seen = shrink(_real_cohort(0.20, confidence=1.0, peer=0.80))
    assert seen.weight == 1.0
    assert seen.posture == pytest.approx(posture_from_log_odds(logit(0.20)), abs=1e-6)


def test_shrinkage_is_monotone_in_the_vendor_s_own_penalty():
    """E7's property, re-run against the new transform as the plan requires. More penalty must
    never produce a better posture, at ANY confidence — this is the invariant most likely to break
    silently when a transform changes."""
    for confidence in (0.1, 0.4, 0.75, 1.0):
        postures = [shrink(_real_cohort(f, confidence)).posture
                    for f in (0.05, 0.15, 0.3, 0.5, 0.7, 0.9)]
        assert postures == sorted(postures, reverse=True), (
            f"posture improved as penalty rose at confidence={confidence}: {postures}"
        )


def test_more_evidence_never_changes_the_direction_of_a_finding():
    """A vendor worse than their cohort gets worse as coverage improves; one better than their
    cohort gets better. Confidence moves a score toward the truth, never across it."""
    for confidence in (0.2, 0.5, 0.9):
        worse = shrink(_real_cohort(0.60, confidence, peer=0.30)).posture
        better = shrink(_real_cohort(0.10, confidence, peer=0.30)).posture
        peer_posture = posture_from_log_odds(logit(0.30))
        assert worse < peer_posture < better


def test_tau_shapes_how_fast_trust_in_own_evidence_decays():
    """The one genuine judgement call in the transform, exposed as a parameter rather than buried
    as a constant — it should be argued over with a real pool in front of the people arguing."""
    inp = _real_cohort(0.10, confidence=0.5, peer=0.60)
    trusting = shrink(inp, tau=2.0)      # c^2 = 0.25 -> LESS of the vendor's own evidence
    linear = shrink(inp, tau=1.0)        # c^1 = 0.50
    assert trusting.weight < linear.weight
    assert trusting.posture < linear.posture, "less own-evidence must pull further toward the peer"


# --------------------------------------------------------------------- numerics


def test_the_transform_is_stable_at_the_asymptotes():
    assert sigmoid(-1000) == pytest.approx(0.0, abs=1e-9)
    assert sigmoid(1000) == pytest.approx(1.0, abs=1e-9)
    assert logit(0.0) < 0 and logit(1.0) > 0, "clamped, not infinite"
    assert posture_from_log_odds(logit(0.5)) == pytest.approx(50.0)


# --------------------------------------------------------------------- the side-by-side release


def test_every_score_carries_the_preview_field_and_the_reason_it_is_empty():
    """SIDE BY SIDE IS WHAT MAKES THE NOTICE PERIOD POSSIBLE.

    The plan calls E13 a second release because it changes what the number MEANS — same evidence,
    different published figure — so it needs a version bump, a notice period and both numbers
    visible at once. A client cannot be given a notice period for a number they cannot yet see.

    Today the field is None on every score and `log_odds_reason` says which precondition is unmet,
    which is the honest state rather than a missing feature: the reason is a sentence a reader can
    act on, not a silent null.
    """
    from tests.test_corpus import AS_AT, load_fixture

    from app.scoring import ScoringEngine

    for ref in ("atlassian", "synthetic_floor", "synthetic_weak"):
        vendor, results = load_fixture(ref)
        score = ScoringEngine().score(vendor, results, now=AS_AT).score
        assert score.posture is not None
        assert score.log_odds_preview is None, "E13 published while the peer pool is synthetic"
        assert score.log_odds_reason, "a refusal with no reason is a silent null"


def test_the_preview_never_touches_the_published_posture():
    """The transform is computed on every score and consumed by nothing. If E13 could move the
    live number before its release, the notice period would be decorative."""
    from tests.test_corpus import AS_AT, load_fixture

    from app.scoring import ScoringEngine

    vendor, results = load_fixture("synthetic_floor")
    out = ScoringEngine().score(vendor, results, now=AS_AT)
    assert out.score.posture == 39, (
        "synthetic_floor's published posture moved — E13 is leaking into the live arithmetic"
    )


def test_switching_on_is_one_argument_once_the_pool_is_real():
    """What the switch-on actually costs, demonstrated rather than promised.

    The engine passes `peers_are_synthetic=True` unconditionally BECAUSE THAT IS TRUE today. When
    E11's pool is seeded that argument changes and the transform runs — no new code, no new
    preconditions. This asserts the seam is genuinely that small.
    """
    real = ShrinkageInput(penalty_fraction=0.62, confidence=0.91,
                          peer_penalty_fraction=0.30, n_peers=18, peers_are_synthetic=False)
    out = shrink(real)
    assert out.published is True
    assert 0 < out.posture < 100
    assert out.weight == pytest.approx(0.91)


# ------------------------------------------------- L_peer: the argument that did not exist


def test_the_argument_the_switch_on_was_promised_on_now_exists():
    """THE DEFECT THIS SECTION CLOSES, AND IT WAS A DOCUMENTATION DEFECT WITH TEETH.

    Every E13 exit criterion but the switch-on was marked met, on the strength of *"switching on is
    one argument, demonstrated rather than promised"*. But the engine wrote
    `peer_penalty_fraction=None, n_peers=0, peers_are_synthetic=True` as three literals, and **no
    code anywhere computed a peer penalty rate**. There was no argument to change. The test above
    demonstrated that `shrink()` works when handed real numbers — which was true, and which nothing
    in the system was in a position to hand it.

    The seam is `ScoringEngine.score(peers=...)`, and this asserts it end to end: the same vendor,
    the same evidence, refusing without a cohort and publishing with one.
    """
    from tests.test_corpus import AS_AT, load_fixture

    from app.scoring import ScoringEngine
    from app.scoring.log_odds import peer_context

    vendor, results = load_fixture("synthetic_weak")

    without = ScoringEngine().score(vendor, results, now=AS_AT).score
    assert without.log_odds_preview is None
    assert "SYNTHETIC" in without.log_odds_reason

    cohort = peer_context([71, 68, 74, 66, 80, 62, 77, 70, 73],
                          is_synthetic=False, cohort_label="technology|rev=?|emp=large|anz")
    with_peers = ScoringEngine().score(vendor, results, now=AS_AT, peers=cohort).score

    assert with_peers.log_odds_preview is not None, "the seam does not reach the preview"
    assert with_peers.posture == without.posture, (
        "the published posture moved — L_peer reached the live arithmetic"
    )
    # And the reason now says WHERE it was shrunk toward. A number pulled toward an unnamed target
    # cannot be reviewed, and being reviewable before it means anything is the whole point of
    # shipping the preview a release early.
    assert "median posture 71" in with_peers.log_odds_reason
    assert "technology|rev=?|emp=large|anz" in with_peers.log_odds_reason


def test_the_default_engine_path_is_byte_for_byte_the_old_refusal():
    """`NO_PEERS` has to reproduce the three literals it replaced, or this change moved the shipped
    product while claiming to add an argument."""
    from app.scoring.log_odds import NO_PEERS

    inp = NO_PEERS.as_shrinkage(penalty_fraction=0.4, confidence=0.8)
    assert (inp.peer_penalty_fraction, inp.n_peers, inp.peers_are_synthetic) == (None, 0, True)
    assert preconditions(inp) == preconditions(ShrinkageInput(
        penalty_fraction=0.4, confidence=0.8, peer_penalty_fraction=None,
        n_peers=0, peers_are_synthetic=True))


def test_a_posture_inverts_to_the_penalty_fraction_it_came_from():
    """`penalty_fraction = (100 − posture)/100`, exactly — no divisor, so L_peer does not inherit a
    dependency on the one tuning constant in the model."""
    from app.scoring.log_odds import penalty_fraction_from_posture

    assert penalty_fraction_from_posture(100) == 0.0
    assert penalty_fraction_from_posture(70) == pytest.approx(0.30)
    assert penalty_fraction_from_posture(0) == 1.0
    # Clamped both ways: a posture outside 0-100 is a bug elsewhere, not a negative rate here.
    assert penalty_fraction_from_posture(120) == 0.0
    assert penalty_fraction_from_posture(-5) == 1.0


def test_l_peer_is_a_median_because_the_inversion_breaks_at_the_clamps():
    """THE CORRECTNESS ARGUMENT FOR THE MEDIAN, held as a test rather than a comment.

    A peer at the 0 floor and a peer capped at 49 by the critical ceiling both invert to a penalty
    fraction they did not earn, and they distort in OPPOSITE directions — so no adjustment fixes
    both. A median in a cohort of eight or more does not move for either.
    """
    from app.scoring.log_odds import peer_context

    clean = [70, 71, 72, 73, 74, 75, 76, 77, 78]
    distorted = [0, 49, 72, 73, 74, 75, 76, 77, 78]     # one floored, one ceiling-capped

    assert peer_context(clean, is_synthetic=False).median_posture == 74
    assert peer_context(distorted, is_synthetic=False).median_posture == 74

    mean_clean = sum(clean) / len(clean)
    mean_distorted = sum(distorted) / len(distorted)
    # Ten posture points, from two peers out of nine, neither of which is actually that bad — the
    # floored one may be at 3x the cap or at 6x, and the capped one may have earned almost nothing.
    assert abs(mean_clean - mean_distorted) == pytest.approx(10.22, abs=0.01)
    assert peer_context(clean, is_synthetic=False).penalty_fraction == pytest.approx(
        peer_context(distorted, is_synthetic=False).penalty_fraction
    ), "the median kept L_peer identical across the distortion"


def test_a_capped_peer_is_disclosed_rather_than_corrected():
    """We cannot tell from a published posture how much of it was earned and how much was a cap, so
    the count travels with the cohort and a reader decides what it is worth."""
    from app.scoring.log_odds import peer_context

    ctx = peer_context([60] * 9, is_synthetic=False, capped_peers=3, cohort_label="healthcare|anz")
    assert ctx.capped_peers == 3
    assert "3 of them published a CAPPED posture" in ctx.basis
    assert ctx.penalty_fraction == pytest.approx(0.40)


def test_an_empty_cohort_is_a_refusal_and_never_a_zero_rate():
    """A cohort with no members has NO peer rate. Reporting 0.0 would say every peer is spotless and
    shrink thin vendors toward a perfect score — the failure in the flattering direction, and the
    exact one the whole module exists to prevent."""
    from app.scoring.log_odds import peer_context

    ctx = peer_context([], is_synthetic=False, cohort_label="mining|rev=?|emp=?|anz")
    assert ctx.penalty_fraction is None
    assert ctx.n_peers == 0
    assert "holds no scored peer" in ctx.basis
    assert shrink(ctx.as_shrinkage(penalty_fraction=0.4, confidence=0.9)).published is False


def test_the_pipeline_supplies_the_exact_cohort_and_never_a_widened_one():
    """Ranking against a widened group is worth doing WITH the widening disclosed. Shrinking toward
    one is a different act — it moves the vendor's own number toward a population they were not
    compared to, and the caption does not travel with the figure. So `_peer_context` reads
    `cohort_members` (the exact key) and never `build_benchmark` (the ladder)."""
    import ast
    import inspect
    from pathlib import Path

    from app import pipeline

    tree = ast.parse(Path(inspect.getfile(pipeline)).read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_peer_context")
    called = {n.func.attr for n in ast.walk(fn)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "cohort_members" in called
    assert "build_benchmark" not in called and "peer_lookup" not in called
