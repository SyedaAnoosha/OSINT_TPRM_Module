"""Benchmarking — four-factor cohorts, the widening ladder, and the refusals.

The tests that matter most are the ones asserting the system says NO or says LESS: it refuses
below the minimum peer count, it refuses to compare across industries at any width, and where it
widens the cohort it must say so. A benchmark that always produced a number would be easier to
demo and would be the single most misleading thing this system could emit — authoritative-looking
and meaningless.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
import yaml

from app.benchmark import (
    BenchmarkConfig,
    BenchmarkConfigError,
    Peer,
    build_benchmark,
    cohort_key,
    cohort_stats,
    employee_band_for,
    get_benchmark_config,
    load_benchmark_config,
    resolve_peers,
    revenue_band_for,
)
from app.models import PeerCohort, utcnow

COHORT = PeerCohort(
    sector="technology", revenue_band="large", employee_band="large", region="anz",
    key=cohort_key("technology", "large", "large", "anz"),
)


def _peers(n: int, start: int = 60, **kw) -> list[Peer]:
    return [Peer(vendor_ref=f"p{i}", posture=start + i, confidence=kw.get("confidence", 0.9),
                 computed_at=kw.get("computed_at", utcnow()),
                 categories=kw.get("categories", {})) for i in range(n)]


def _lookup(mapping: dict[tuple[str, ...], list[Peer]]):
    """Fake peer source keyed by the dimension names a rung asks for."""
    return lambda dims: mapping.get(tuple(sorted(dims)), [])


def _ladder_cfg(min_n: int = 8, **over):
    """An EXPLICIT threshold for the ladder tests.

    These used to read the shipped `benchmarks.yaml`, which ships `min_cohort_n: 1` for live
    demo use. At a threshold of one, the exact cohort always satisfies, so the widening ladder
    never runs and the tests that exist to prove it works could not observe it. Pinning the
    threshold here makes each test state the condition it is actually testing, and means E11
    can change the shipped setting without dragging these back to red.
    """
    cohort = {"min_cohort_n": min_n}
    cohort.update(over)
    return BenchmarkConfig({"cohort": cohort}, Path("t"))


# --------------------------------------------------------------------- four factors


def test_cohort_key_names_all_four_factors():
    key = cohort_key("technology", "mega", "large", "north_america")
    assert key == "technology|rev=mega|emp=large|north_america"


def test_unknown_size_dimension_is_explicit_in_the_key():
    """`?` rather than an empty string, so a key never silently means two different things."""
    assert cohort_key("retail", None, "small", "anz") == "retail|rev=?|emp=small|anz"


def test_revenue_and_headcount_band_independently():
    """The disagreement is the signal. A 40-person firm at $400M and a 4,000-person firm at $400M
    are different risk propositions, and an earlier design that blended them lost that."""
    assert employee_band_for(40) == "small"
    assert revenue_band_for(400_000_000, "AUD") == "large"


def test_revenue_converts_for_banding_only():
    # US$50M ~ A$77M — must band on the converted figure or every US vendor lands a band low.
    assert revenue_band_for(50_000_000, "USD") == "medium"


def test_unknown_currency_does_not_guess():
    assert revenue_band_for(50_000_000, "XBT") is None


def test_missing_size_signals_yield_no_band():
    assert employee_band_for(None) is None
    assert revenue_band_for(None) is None


# --------------------------------------------------------------------- the widening ladder


def test_exact_cohort_is_used_when_deep_enough():
    lookup = _lookup({
        ("employee_band", "region", "revenue_band", "sector"): _peers(10),
        ("sector",): _peers(50),
    })
    result = build_benchmark(78, COHORT, lookup)
    assert result.available is True
    assert result.widened is False
    assert result.stats.n == 10
    assert "region" in result.level


def test_ladder_widens_when_the_exact_cohort_is_thin():
    """1,500 possible cohorts means the exact match usually cannot fill. Widening is what makes
    the feature work at all — and it must be disclosed, or a loose comparison looks precise."""
    lookup = _lookup({
        ("employee_band", "region", "revenue_band", "sector"): _peers(3),
        ("employee_band", "revenue_band", "sector"): _peers(9, start=70),
    })
    result = build_benchmark(78, COHORT, lookup, cfg=_ladder_cfg())
    assert result.available is True
    assert result.widened is True
    assert result.stats.n == 9
    assert any("wider population" in c for c in result.caveats)
    assert any("region not matched" in c or "region" in c for c in result.caveats)


def test_ladder_drops_revenue_before_headcount():
    """Revenue is the sparsest field in free sources, so requiring it costs the most cohort
    density for the least coverage. Headcount is given up last of the two."""
    lookup = _lookup({
        ("employee_band", "region", "revenue_band", "sector"): _peers(2),
        ("employee_band", "revenue_band", "sector"): _peers(2),
        ("employee_band", "region", "sector"): _peers(12, start=65),
    })
    result = build_benchmark(78, COHORT, lookup, cfg=_ladder_cfg())
    assert result.available is True
    assert result.stats.n == 12
    assert "headcount" in result.level and "revenue" not in result.level


def test_ladder_never_widens_past_industry():
    """There is deliberately no rung below 'same industry'. A bank compared against every vendor
    ever scored is the meaningless comparison this whole feature exists to refuse."""
    cfg = get_benchmark_config()
    for level in cfg.widening():
        assert "sector" in level


def test_a_rung_without_sector_is_rejected_at_load(tmp_path: Path):
    bad = {"cohort": {"min_cohort_n": 8, "widening": [["employee_band", "region"]]}}
    path = tmp_path / "benchmarks.yaml"
    path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(BenchmarkConfigError, match="not a peer group"):
        load_benchmark_config(path)


def test_rungs_needing_an_unknown_dimension_are_skipped():
    """A vendor with no revenue figure must still reach the rungs that do not need one, rather
    than matching on a null and silently pooling every unsized vendor together."""
    cohort = PeerCohort(sector="technology", revenue_band=None, employee_band="large",
                        region="anz", key=cohort_key("technology", None, "large", "anz"))
    lookup = _lookup({("employee_band", "region", "sector"): _peers(10)})
    peers, level, _, _ = resolve_peers(cohort, lookup)
    assert level == ("sector", "employee_band", "region")
    assert len(peers) == 10


def test_insufficient_at_every_width_falls_back_and_says_so():
    """BEHAVIOUR CHANGE, recorded deliberately (E0.1).

    This test previously required a REFUSAL — `available is False`, "insufficient peers (4 of 8)".
    The shipped system no longer refuses: when no rung meets the threshold it substitutes the
    hard-coded industry reference baseline so every vendor still gets a comparison.

    That fallback is a product decision, not a bug, and it is defensible. What is NOT defensible
    is a reader mistaking it for a real peer group — so the property worth pinning is no longer
    "it refuses" but "it is unmistakably labelled". Restoring the refusal is E11, once a seeded
    pool makes a real cohort reachable; until then this test guards the disclosure.
    """
    lookup = _lookup({("sector",): _peers(4)})
    result = build_benchmark(78, COHORT, lookup, cfg=_ladder_cfg())
    assert result.synthetic is True, "four peers against a threshold of eight is not a cohort"
    assert "not real peers" in result.caveats[0].lower()


# --------------------------------------------------------------------- peer quality


def test_stale_peers_are_excluded_and_disclosed():
    # 9 live peers, not 4: `min_cohort_n` is now floored at 8 in code, so a cohort that used to
    # squeak past a `min_cohort_n: 3` config falls through to the synthetic baseline and this test
    # would silently stop measuring stale exclusion at all.
    cfg = BenchmarkConfig({"cohort": {"min_cohort_n": 8, "max_peer_age_days": 30}}, Path("t"))
    old = utcnow() - timedelta(days=200)
    peers = _peers(9) + _peers(3, start=90, computed_at=old)
    result = build_benchmark(78, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): peers}), cfg=cfg)
    assert result.stats.n == 9
    assert result.stats.excluded_stale == 3
    assert any("stale" in c for c in result.caveats)


def test_thinly_evidenced_peers_are_excluded():
    """A vendor too thinly evidenced to publish is too thinly evidenced to define what 'normal'
    looks like for everyone else."""
    cfg = BenchmarkConfig({"cohort": {"min_cohort_n": 8, "min_peer_confidence": 0.4}}, Path("t"))
    peers = _peers(9) + _peers(5, start=95, confidence=0.2)
    result = build_benchmark(78, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): peers}), cfg=cfg)
    assert result.stats.n == 9


def test_low_confidence_cohort_is_flagged():
    cfg = BenchmarkConfig({"cohort": {"min_cohort_n": 8}}, Path("t"))
    result = build_benchmark(78, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): _peers(9, confidence=0.5)}), cfg=cfg)
    assert result.stats.median_confidence == 0.5
    assert any("thinly evidenced" in c for c in result.caveats)


def test_self_selection_caveat_is_always_present():
    """The limitation that never goes away: peers are vendors this deployment happened to score,
    not a random sample of the industry."""
    lookup = _lookup({("employee_band", "region", "revenue_band", "sector"): _peers(10)})
    available = build_benchmark(78, COHORT, lookup)
    refused = build_benchmark(78, COHORT, _lookup({}))
    for result in (available, refused):
        assert any("not a random sample" in c for c in result.caveats)


# --------------------------------------------------------------------- statistics


def test_percentile_is_rounded_to_the_resolution_the_sample_supports():
    """With 8 peers the achievable steps are 12.5 apart, so an 83rd percentile would be false
    precision. Resolution is rounded UP (13, never 12) so it never overstates what the sample can
    express, and it is published alongside the value."""
    lookup = _lookup({("employee_band", "region", "revenue_band", "sector"): _peers(8, start=60)})
    # posture 63 beats 4 of 8 peers -> 50% raw, snapped to the nearest 13.
    result = build_benchmark(63, COHORT, lookup)
    assert result.percentile_resolution == 13
    assert result.percentile % 13 == 0


def test_percentile_never_exceeds_100_when_snapped_to_a_coarse_step():
    """Snapping to a coarse step can overshoot — 8 peers gives a step of 13, and 8x13 is 104.

    Eight rather than the six this used before: `min_cohort_n` is floored at 8 in code now, so a
    six-peer cohort falls through to the synthetic baseline, which publishes no percentile at all —
    and the overshoot this test exists to catch would have gone permanently unmeasured."""
    cfg = BenchmarkConfig({"cohort": {"min_cohort_n": 8}}, Path("t"))
    lookup = _lookup({("employee_band", "region", "revenue_band", "sector"): _peers(8, start=50)})
    result = build_benchmark(99, COHORT, lookup, cfg=cfg)
    assert result.percentile == 100


def test_quartile_is_reported_alongside_the_percentile():
    lookup = _lookup({("employee_band", "region", "revenue_band", "sector"): _peers(12, start=50)})
    top = build_benchmark(99, COHORT, lookup)
    bottom = build_benchmark(10, COHORT, lookup)
    assert top.quartile == 4
    assert bottom.quartile == 1


def test_small_sample_is_flagged_as_unstable():
    cfg = BenchmarkConfig({"cohort": {"min_cohort_n": 4}}, Path("t"))
    result = build_benchmark(78, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): _peers(5)}), cfg=cfg)
    assert any("Small sample" in c for c in result.caveats)


def test_median_is_a_real_vendor_not_an_interpolation():
    """Nearest-rank, no interpolation: with small samples an interpolated median is a company that
    does not exist, and every number on the card should correspond to something real."""
    stats = cohort_stats(COHORT, [Peer(vendor_ref="a", posture=60),
                                  Peer(vendor_ref="b", posture=80)])
    assert stats.median in (60, 80)


def test_cohort_stats_reports_distribution_and_n():
    peers = [Peer(vendor_ref=f"p{i}", posture=p) for i, p in enumerate([50, 60, 70, 80, 90])]
    stats = cohort_stats(COHORT, peers)
    assert stats.n == 5 and stats.median == 70
    assert stats.minimum == 50 and stats.maximum == 90
    assert stats.p25 <= stats.median <= stats.p75


# --------------------------------------------------------------------- per-category


def test_per_category_comparison_uses_the_same_peers():
    """'Your cyber hygiene is below peers but your business stability is above' is far more
    actionable than one overall variance."""
    peers = _peers(10, categories={"cyber_hygiene_technical": 90, "compliance_regulatory": 60})
    result = build_benchmark(
        78, COHORT, _lookup({("employee_band", "region", "revenue_band", "sector"): peers}),
        categories={"cyber_hygiene_technical": 70, "compliance_regulatory": 85},
    )
    by_cat = {c.category: c for c in result.categories}
    assert by_cat["cyber_hygiene_technical"].variance_from_median == -20
    assert by_cat["compliance_regulatory"].variance_from_median == 25


def test_category_median_ignores_peers_that_did_not_cover_it():
    """A vendor whose trust page was unreachable has no compliance posture. Treating that absence
    as a low score would drag the median down with a collection failure — the same 'missing data
    is not a bad result' rule the engine applies one level up."""
    peers = _peers(5, categories={"compliance_regulatory": 80}) + _peers(5, start=70)
    result = build_benchmark(
        78, COHORT, _lookup({("employee_band", "region", "revenue_band", "sector"): peers}),
        categories={"compliance_regulatory": 60},
    )
    cat = result.categories[0]
    assert cat.n == 5, "only peers that covered the category should count"
    assert cat.median == 80


# --------------------------------------------------------------------- signal prevalence


def _sig_cfg(**over):
    base = {"cohort": {"min_cohort_n": 3, "min_signal_peers": 3}}
    base["cohort"].update(over)
    return BenchmarkConfig(base, Path("t"))


def test_prevalence_says_how_common_a_control_is():
    """The sharpest line the benchmark can produce: '-20, no DMARC' says you fell short of our
    model; '79% of your peers publish one' says you fell short of your own industry."""
    peers = [Peer(vendor_ref=f"p{i}", posture=80, signals={"dmarc": "p_reject"}) for i in range(8)]
    peers += [Peer(vendor_ref="laggard", posture=70, signals={"dmarc": "absent"})]
    result = build_benchmark(75, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): peers}),
        signals={"dmarc": "absent"}, cfg=_sig_cfg())

    dmarc = next(s for s in result.signals if s.signal == "dmarc")
    assert dmarc.passing is False
    assert dmarc.peers_checked == 9 and dmarc.peers_passing == 8
    assert dmarc.peer_pass_rate == pytest.approx(0.889, abs=0.01)
    assert dmarc.standing == "behind"


def test_a_peer_never_checked_is_not_a_peer_that_failed():
    """The denominator counts vendors ASSESSED on the control. Counting an uncollected signal as a
    failure would blame the industry for our own collection gap — the same 'missing data is not a
    bad result' rule the engine applies one level up."""
    peers = [Peer(vendor_ref=f"chk{i}", posture=80, signals={"dmarc": "p_reject"})
             for i in range(3)]
    # Five never-checked peers, so the cohort clears the floor of 8 and the DENOMINATOR question
    # this test exists to ask is still being asked of a real cohort rather than of a fallback.
    peers += [Peer(vendor_ref=f"unchk{i}", posture=80, signals={}) for i in range(5)]
    result = build_benchmark(75, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): peers}),
        signals={"dmarc": "absent"}, cfg=_sig_cfg())
    dmarc = next(s for s in result.signals if s.signal == "dmarc")
    assert dmarc.peers_checked == 3
    assert dmarc.peer_pass_rate == 1.0


def test_prevalence_needs_a_minimum_sample():
    """A pass rate over two vendors is a rumour with a percent sign on it."""
    peers = [Peer(vendor_ref=f"p{i}", posture=80, signals={"dmarc": "p_reject"}) for i in range(2)]
    result = build_benchmark(75, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): peers + _peers(6)}),
        signals={"dmarc": "absent"}, cfg=_sig_cfg())
    assert [s for s in result.signals if s.signal == "dmarc"] == []


def test_a_control_everyone_has_including_you_is_not_reported():
    """Noise suppression: a card listing every control the vendor already passes buries the ones
    it does not."""
    peers = [Peer(vendor_ref=f"p{i}", posture=80, signals={"dmarc": "p_reject"}) for i in range(8)]
    result = build_benchmark(75, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): peers}),
        signals={"dmarc": "p_reject"}, cfg=_sig_cfg())
    assert [s for s in result.signals if s.signal == "dmarc"] == []


def test_passing_a_control_most_peers_lack_is_reported_as_ahead():
    peers = [Peer(vendor_ref=f"p{i}", posture=80, signals={"dnssec": "absent"}) for i in range(8)]
    result = build_benchmark(75, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): peers}),
        signals={"dnssec": "valid"}, cfg=_sig_cfg())
    dnssec = next(s for s in result.signals if s.signal == "dnssec")
    assert dnssec.passing is True and dnssec.standing == "ahead"


def test_prevalence_uses_the_scoring_model_to_decide_what_passes():
    """One definition of 'pass', in scoring.yaml. If prevalence re-decided it, the card could tell
    a vendor they are behind their peers on a control the score treats as fine."""
    cfg = _sig_cfg()
    assert cfg.severity_of("dmarc", "p_reject") == "pass"
    assert cfg.severity_of("dmarc", "absent") == "high"


# --------------------------------------------------------------------- outliers & confidence


def test_outlier_uses_the_iqr_fence_not_standard_deviations():
    """SD assumes a roughly normal spread and is destabilised by one extreme member — and at n=8-20
    one member IS a large share of the population. The IQR fence is the robust alternative."""
    tight = [80, 81, 82, 83, 84, 85, 86, 87]
    peers = [Peer(vendor_ref=f"p{i}", posture=v) for i, v in enumerate(tight)]
    lookup = _lookup({("employee_band", "region", "revenue_band", "sector"): peers})

    assert build_benchmark(40, COHORT, lookup, cfg=_sig_cfg()).outlier is True
    assert build_benchmark(79, COHORT, lookup, cfg=_sig_cfg()).outlier is False


def test_outlier_is_flagged_in_the_caveats():
    peers = [Peer(vendor_ref=f"p{i}", posture=v) for i, v in enumerate([80, 81, 82, 83, 84, 85])]
    result = build_benchmark(30, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): peers}), cfg=_sig_cfg())
    assert result.outlier is True
    assert any("below the normal range" in c for c in result.caveats)


def test_benchmark_confidence_is_its_own_axis():
    """A benchmark can be computed from a thin, widened, stale cohort of Ghosts and still print a
    confident-looking percentile. This says how much to trust the COMPARISON."""
    strong = build_benchmark(80, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): _peers(20, confidence=0.95)}),
        cfg=_sig_cfg(), subject_confidence=0.95)
    weak = build_benchmark(80, COHORT, _lookup({
        ("sector",): _peers(3, confidence=0.45)}), cfg=_sig_cfg(), subject_confidence=0.45)

    assert strong.confidence > weak.confidence
    assert strong.confidence_band == "High"
    assert weak.confidence_band == "Low"
    assert any("Low benchmark confidence" in c for c in weak.caveats)


def test_widening_lowers_benchmark_confidence():
    exact = build_benchmark(80, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): _peers(16)}), cfg=_sig_cfg())
    widened = build_benchmark(80, COHORT, _lookup({
        ("employee_band", "region", "sector"): _peers(16)}), cfg=_sig_cfg())
    assert widened.confidence < exact.confidence


# --------------------------------------------------------------------- category depth


def test_category_percentile_exposes_what_the_overall_hides():
    """A vendor can be top-quartile overall and bottom-quartile on the one category a given buyer
    actually cares about."""
    peers = [Peer(vendor_ref=f"p{i}", posture=60,
                  categories={"cyber_hygiene_technical": 95}) for i in range(8)]
    result = build_benchmark(90, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): peers}),
        categories={"cyber_hygiene_technical": 50}, cfg=_sig_cfg())

    assert result.percentile == 100                       # top overall
    cat = result.categories[0]
    assert cat.percentile == 0                            # bottom on this category
    assert cat.variance_from_median == -45


def test_gap_drivers_name_what_caused_a_negative_gap():
    """A gap with no named cause is a number; a gap with three named causes is a to-do list."""
    peers = [Peer(vendor_ref=f"p{i}", posture=80,
                  categories={"cyber_hygiene_technical": 90}) for i in range(8)]
    result = build_benchmark(70, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): peers}),
        categories={"cyber_hygiene_technical": 60},
        gap_drivers={"cyber_hygiene_technical": ["No DMARC record", "TLS 1.0 accepted"]},
        cfg=_sig_cfg())
    assert result.categories[0].gap_drivers == ["No DMARC record", "TLS 1.0 accepted"]


def test_gap_drivers_are_not_shown_where_the_vendor_leads():
    """Naming 'what put you here' on a category you lead is noise."""
    peers = [Peer(vendor_ref=f"p{i}", posture=80,
                  categories={"cyber_hygiene_technical": 50}) for i in range(8)]
    result = build_benchmark(90, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): peers}),
        categories={"cyber_hygiene_technical": 95},
        gap_drivers={"cyber_hygiene_technical": ["something"]}, cfg=_sig_cfg())
    assert result.categories[0].gap_drivers == []


# --------------------------------------------------------------------- refusals


def test_no_cohort_still_produces_a_labelled_comparison():
    """BEHAVIOUR CHANGE, recorded deliberately (E0.1).

    Previously a vendor with no derivable cohort got no comparison at all. `build_benchmark` now
    constructs a fallback cohort so the card is never blank, which then resolves to the synthetic
    baseline. Same reasoning as above: the guarantee moved from "we refuse" to "we label".
    """
    result = build_benchmark(78, None, _lookup({}))
    assert result.synthetic is True
    assert "not real peers" in result.caveats[0].lower()


def test_no_posture_means_no_comparison():
    """A blocked or refused vendor has no posture. Comparing 'we could not assess this' against a
    distribution would treat an absence of evidence as a result."""
    result = build_benchmark(None, COHORT, _lookup({("sector",): _peers(50)}))
    assert result.available is False
    assert "no published posture" in result.reason


# --------------------------------------------------------------------- config discipline


def test_shipped_config_asserts_no_sector_targets():
    """§5.6 deleted category weights because no authority publishes them; 'financial services
    should score 95' has the same defect. The empty map is the honest state, and this test makes
    filling it in a deliberate act with a visible diff."""
    cfg = get_benchmark_config()
    assert cfg.expected_posture("financial_services") is None
    assert cfg.expected_posture("technology") is None


def test_expected_posture_without_a_basis_is_rejected(tmp_path: Path):
    bad = {"cohort": {"min_cohort_n": 8},
           "expected_posture": {"financial_services": {"value": 95}}}
    path = tmp_path / "benchmarks.yaml"
    path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(BenchmarkConfigError, match="basis"):
        load_benchmark_config(path)


def test_expected_posture_travels_with_its_basis(tmp_path: Path):
    data = {"cohort": {"min_cohort_n": 2},
            "expected_posture": {"technology": {"value": 88, "basis": "Observed cohort median"}}}
    path = tmp_path / "benchmarks.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    cfg = load_benchmark_config(path)
    result = build_benchmark(78, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): _peers(5)}), cfg=cfg)
    assert result.expected_posture == 88
    assert result.expected_basis, "an expected posture without its basis must never be published"


def test_unknown_dimension_in_the_ladder_is_rejected(tmp_path: Path):
    bad = {"cohort": {"widening": [["sector", "turnover"]]}}
    path = tmp_path / "benchmarks.yaml"
    path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(BenchmarkConfigError, match="unknown dimension"):
        load_benchmark_config(path)


def test_min_cohort_n_is_tunable_upward_only():
    """The threshold still decides whether a REAL cohort is used — that is what tunable means. It
    may be RAISED in YAML and it may not be lowered past the code floor of 8.

    Below the threshold the synthetic baseline stands in, so the observable difference is
    `synthetic`, not `available`.
    """
    strict = BenchmarkConfig({"cohort": {"min_cohort_n": 12}}, Path("t"))
    lookup12 = _lookup({("employee_band", "region", "revenue_band", "sector"): _peers(12)})
    lookup9 = _lookup({("employee_band", "region", "revenue_band", "sector"): _peers(9)})

    assert build_benchmark(78, COHORT, lookup12, cfg=strict).synthetic is False
    assert build_benchmark(78, COHORT, lookup9, cfg=strict).synthetic is True, (
        "nine peers is below a threshold of twelve — must not pass as a real cohort"
    )
    # And the same nine peers ARE a real cohort under the shipped floor.
    assert build_benchmark(78, COHORT, lookup9).synthetic is False


def test_the_peer_floor_cannot_be_lowered_by_a_config_edit():
    """E11's actual defect, closed.

    The shipped file carried `min_cohort_n: 1` — a demo setting that survived into production,
    which is indistinguishable from a decision nobody made — and it let this module publish a
    "median" and a "percentile" over a SINGLE company. A percentile against one peer is not a weak
    comparison; it is a coin flip presented as a statistic.

    EB floors its thresholds IN CODE and says why in its module docstring: a YAML floor alone
    would let exactly this recur. The deprecated path now gets the same treatment, because it is
    still the DEFAULT route and `run_pipeline` writes its output onto every scored vendor — so
    "it goes away next release" is a reason to fix it now, not a reason to leave it.
    """
    for attempt in (0, 1, 2, 7):
        cfg = BenchmarkConfig({"cohort": {"min_cohort_n": attempt}}, Path("t"))
        assert cfg.min_cohort_n() == 8, f"min_cohort_n: {attempt} was honoured"
    assert BenchmarkConfig({"cohort": {"min_cohort_n": 30}}, Path("t")).min_cohort_n() == 30
    assert get_benchmark_config().min_cohort_n() >= 8


# --------------------------------------------------------------------- synthetic baseline
# When NO real peer exists the comparison falls back to a hard-coded industry reference baseline
# (`_synthetic_baseline_peers`, six invented postures). That fallback is defensible; publishing
# its count as "n=6 peers" is not. A reader sees 6 beside the word "peers" and believes six real
# companies were assessed. These tests pin the disclosure, not the fallback.


def _synthetic_benchmark(posture: int = 70):
    """A cohort no real peer can satisfy — forces the reference-baseline path."""
    return build_benchmark(posture, COHORT, lookup=_lookup({}))


def test_a_synthetic_baseline_publishes_no_ordinal_placement_at_any_n():
    """E11 / EB DECISION 3, APPLIED TO THE DEPRECATED PATH — the Sprint-0 defect, closed.

    The caveat on this path is strong, leads the list, and is still not enough. Six invented
    postures produced a real-looking "78th percentile" that a reader screenshots into a slide, and
    THE CAPTION DOES NOT TRAVEL WITH THE SCREENSHOT. That is the whole reason `is_synthetic` is a
    hard gate in EB rather than a label, and this module is not a museum piece: it still serves
    `/api/vendors/{ref}/benchmark`, and `run_pipeline` still writes its output onto every scored
    vendor. Leaving it until the cutover means shipping it for another release.

    THE REFERENCE BASELINE ITSELF STAYS. EB's cold-start decision is that a labelled external
    reference line is legitimate context — it is a population statistic, never a peer median. So
    the categories, the signal prevalence and the caveat survive. Only the ORDINAL PLACEMENT is
    withheld, because a rank against invented companies has no meaning to withhold anything from.
    """
    for posture in (10, 50, 70, 99):
        bm = _synthetic_benchmark(posture)
        assert bm.synthetic is True
        assert bm.percentile is None, "a percentile against invented peers is the Sprint-0 defect"
        assert bm.percentile_resolution is None
        assert bm.quartile is None
        assert bm.variance_from_median is None
        # Still available, still caveated, still carrying the reference context.
        assert bm.available is True
        assert any("NOT REAL PEERS" in c for c in bm.caveats)


def test_a_real_cohort_still_gets_its_placement():
    """The counterpart. Withholding on synthetic must not become withholding on everything —
    a refusal that fires always is not a refusal, it is a broken feature."""
    real = build_benchmark(78, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): _peers(12, start=50)}))
    assert real.synthetic is False
    assert real.percentile is not None
    assert real.quartile is not None
    assert real.variance_from_median is not None


def test_synthetic_cohort_is_flagged_as_a_field_not_only_as_prose():
    """A renderer must be able to badge this WITHOUT string-matching a caveat sentence."""
    bm = _synthetic_benchmark()
    assert bm.synthetic is True, "synthetic fallback must be machine-readable on the Benchmark"


def test_a_real_cohort_is_not_flagged_synthetic():
    bm = build_benchmark(70, COHORT, lookup=_lookup({
        ("employee_band", "region", "revenue_band", "sector"): _peers(10),
    }))
    assert bm.synthetic is False


def test_synthetic_caveat_says_plainly_that_these_are_not_companies():
    """The exact misreading being prevented: 'n=6' read as six real companies."""
    bm = _synthetic_benchmark()
    joined = " ".join(bm.caveats).lower()
    assert "not real peers" in joined
    assert "not companies" in joined
    # and it must be the FIRST thing read, ahead of any other qualifier
    assert "not real peers" in bm.caveats[0].lower()


def test_synthetic_peer_count_is_never_published_unlabelled():
    """If stats.n is present at all it must travel with the flag that explains what it counts."""
    bm = _synthetic_benchmark()
    if bm.stats is not None and bm.stats.n:
        assert bm.synthetic is True, "a peer count without the synthetic flag is the defect itself"


def test_a_reclassified_control_is_still_reported_as_prevalence():
    """E2 REGRESSION GUARD.

    Reclassifying `dnssec.absent` to `informational` removed the penalty — correctly, at 7-18%
    adoption. It also, unintentionally, told the benchmark that a peer WITHOUT DNSSEC had it: every
    peer "passed", so nobody was ever ahead or behind, and prevalence reporting silently died for
    the six controls where a peer comparison is most informative.

    Not charging for a control and pretending everyone has it are different claims.
    """
    peers = [Peer(vendor_ref=f"p{i}", posture=80, signals={"dnssec": "absent"}) for i in range(8)]
    result = build_benchmark(75, COHORT, _lookup({
        ("employee_band", "region", "revenue_band", "sector"): peers}),
        signals={"dnssec": "valid"}, cfg=_sig_cfg())
    dnssec = next(s for s in result.signals if s.signal == "dnssec")
    assert dnssec.standing == "ahead"
    assert dnssec.peer_pass_rate == 0.0, "eight peers without DNSSEC is a 0% pass rate, not 100%"
