"""Peer benchmarking v2 — the hard rules, asserted.

Organised around the five success criteria and the seven hard rules in
`docs/design_decisions.md` Part 1, because those are the specification and a test suite that does not map
onto it cannot tell anyone whether the thing was built.

NO DATABASE. Every test drives the pure layers through an in-memory `PeerLookup`. That is the payoff
for keeping `cohorts.py`, `snapshot.py` and `placement.py` free of persistence concerns: the ladder,
the thresholds and the estimators are all testable without Postgres, so these run in milliseconds and
are exercised on every commit rather than only in CI.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.benchmarking.cohorts import assign_cohort, derive_size_band
from app.benchmarking.config import BenchmarkingConfig, BenchmarkingConfigError
from app.benchmarking.discrimination import discrimination_report
from app.benchmarking.models import PeerRecord, SupplierFirmographics
from app.benchmarking.narrative import TemplateRefused, render
from app.benchmarking.placement import (
    build_placement,
    midrank_percentile,
    place,
    rank_of,
)
from app.benchmarking.snapshot import build_snapshot
from app.models import utcnow

# --------------------------------------------------------------------------- fixtures


def peer(ref: str, posture: int, **kw) -> PeerRecord:
    return PeerRecord(supplier_ref=ref, posture=posture, **kw)


def peers(n: int, start: int = 50, step: int = 1, **kw) -> list[PeerRecord]:
    """`n` peers with ascending postures — a cohort that discriminates by construction.

    Refs are prefixed `peer-` rather than `p`, because `p25` and `p75` are real field names on
    `Distribution`: a leak test searching a serialised placement for `"p25"` would match the quartile
    bound and fail on a payload that is entirely correct.

    Postures clamp at 100 since that is the model's range. For n large enough to hit the ceiling the
    tail ties, which is fine — the tests that use those sizes are asserting on `n`, not on spread.
    """
    return [peer(f"peer-{i}", min(100, start + i * step), **kw) for i in range(n)]


def lookup_of(*, exact: list[PeerRecord] | None = None,
              floor: list[PeerRecord] | None = None,
              sector: list[PeerRecord] | None = None,
              group: list[PeerRecord] | None = None):
    """A lookup keyed on which rung is asking, so a test can make any rung thin on purpose."""
    def lookup(dims: dict[str, str]) -> list[PeerRecord]:
        if "delivery_model" in dims:
            return exact or []
        if "size_band" in dims:
            return floor or []
        if "sector" in dims:
            return sector or []
        if "sector_group" in dims:
            return group or []
        return []
    return lookup


ACME = SupplierFirmographics(
    supplier_ref="acme", supplier_name="Acme Ltd", sector="technology",
    delivery_model="saas", employees=5000, data_access_scope="critical",
)


def placement_for(subject: int, cohort_peers: list[PeerRecord], *,
                  firmographics=ACME, **kw):
    """Assign -> snapshot -> place, against one frozen population."""
    lookup = lookup_of(floor=cohort_peers)
    assignment = assign_cohort(firmographics, lookup)
    snapshot = build_snapshot(assignment, cohort_peers, **kw.pop("snapshot_kw", {}))
    return build_placement(firmographics, subject, assignment, snapshot, **kw)


# =========================================================================================
# SUCCESS CRITERION 1 — a supplier with a posture and firmographics gets a cohort assignment
#                       with full metadata.
# =========================================================================================


def test_supplier_gets_a_cohort_assignment_with_full_metadata():
    assignment = assign_cohort(ACME, lookup_of(exact=peers(40)))

    assert assignment.cohort_key
    assert assignment.dimensions == {
        "sector": "technology", "size_band": "large", "delivery_model": "saas",
    }
    assert assignment.n == 40
    assert assignment.placeable is True
    assert assignment.rung_label
    assert assignment.size_band.band == "large", "5,000 staff bands `large` (1,000-9,999)"
    assert assignment.rationale, "the rungs tried ARE the rationale; an empty list explains nothing"


def test_every_supplier_gets_exactly_one_cohort_even_when_far_too_thin():
    """Assignment and placement are separate.

    A supplier in a sparse sector still needs a cohort — otherwise there is nothing to show them,
    nothing to dispute, and nothing to fill as the pool grows.
    """
    assignment = assign_cohort(ACME, lookup_of(exact=peers(2), floor=peers(3), sector=peers(4)))

    assert assignment.cohort_key, "assigned"
    assert assignment.placeable is False, "but not comparable"
    assert assignment.n == 4


def test_a_supplier_with_no_sector_is_not_guessed_into_one():
    """The superseded module defaulted an unknown sector to `technology`, which silently filed every
    unclassifiable vendor into one cohort. That is the specific regression this guards."""
    nameless = SupplierFirmographics(supplier_ref="x", employees=100)
    assignment = assign_cohort(nameless, lookup_of(exact=peers(40), floor=peers(40),
                                                  sector=peers(40)))

    assert assignment.dimensions == {}
    assert assignment.placeable is False
    assert "technology" not in assignment.cohort_key


# =========================================================================================
# SUCCESS CRITERION 2 — n is always visible and never misrepresented.
# =========================================================================================


@pytest.mark.parametrize("n", [0, 3, 7, 8, 29, 30, 100])
def test_n_is_published_on_every_placement_whatever_it_is(n):
    p = placement_for(70, peers(n))
    assert p.overall.n == n
    assert p.snapshot.n == n


def test_n_counts_peers_and_not_the_subject():
    """At the boundary this is a correctness issue, not a nicety: an "n=30" that counts the subject is
    29 peers, and the percentile rule would then be wrong by one on the exact case it governs."""
    pool = peers(30)
    p = placement_for(70, pool)
    assert p.overall.n == 30
    assert "acme" not in p.snapshot.model_dump_json()


def test_data_sources_composition_travels_with_n():
    """Cohort quality is not inferable from cohort size. 'n=23, of which 3 attested' is a different
    claim from 'n=23'."""
    pool = (peers(20, source_class="osint_only")
            + [peer(f"a{i}", 80, source_class="attested") for i in range(3)])
    p = placement_for(70, pool)

    assert p.snapshot.data_sources == {"osint_only": 20, "attested": 3}
    assert sum(p.snapshot.data_sources.values()) == p.snapshot.n


# =========================================================================================
# SUCCESS CRITERION 3 — percentiles suppressed below n=30; quartiles below n=8 replaced with
#                       "Insufficient peer data".
# =========================================================================================


@pytest.mark.parametrize("n", [0, 1, 7])
def test_below_eight_peers_there_is_no_quartile_and_no_percentile(n):
    p = place(70, [50 + i for i in range(n)])
    assert p.sufficient is False
    assert p.quartile is None
    assert p.percentile is None
    assert "Insufficient peer data" in (p.reason or "")
    assert str(n) in (p.reason or ""), "the actual n must appear in the refusal"


@pytest.mark.parametrize("n", [8, 15, 29])
def test_between_eight_and_thirty_a_quartile_is_published_but_never_a_percentile(n):
    p = place(70, [50 + i for i in range(n)])
    assert p.sufficient is True
    assert p.quartile in (1, 2, 3, 4)
    assert p.rank_of_n is not None, "rank-of-n is required, not optional"
    assert p.percentile is None, "a percentile below n=30 asserts precision the sample cannot support"


@pytest.mark.parametrize("n", [30, 31, 200])
def test_at_thirty_peers_the_percentile_appears_with_its_resolution(n):
    p = place(70, [50 + i for i in range(n)])
    assert p.percentile is not None
    assert p.percentile_resolution is not None
    assert p.quartile is not None, "the coarser statistic does not disappear when the finer arrives"


def test_the_thresholds_cannot_be_lowered_in_config():
    """`min_cohort_n: 1` shipped in the superseded module because a demo setting survived into
    production. A floor in code is the only thing that stops that recurring."""
    for key, bad in (("min_quartile_n", 3), ("min_percentile_n", 10)):
        with pytest.raises(BenchmarkingConfigError, match="floor"):
            _config_with(**{key: bad})


def _config_with(**cohort_overrides) -> BenchmarkingConfig:
    """A minimal valid config with the cohort block overridden — for validation tests only."""
    from pathlib import Path

    import yaml

    from app.benchmarking.config import _DEFAULT_PATH

    data = yaml.safe_load(_DEFAULT_PATH.read_text(encoding="utf-8"))
    data["benchmarking"]["cohort"].update(cohort_overrides)
    return BenchmarkingConfig(data, Path("test"))


# =========================================================================================
# HARD RULE — synthetic reference points are a gate, not a label (decision 3).
# =========================================================================================


@pytest.mark.parametrize("n", [8, 30, 60])
def test_synthetic_peers_yield_no_quartile_and_no_percentile_at_any_n(n):
    """Thirty invented numbers still make a screenshottable fake percentile, and the label under it
    does not travel with the screenshot. So the gate is on the data, not on the caption."""
    p = place(70, [50 + i for i in range(n)], is_synthetic=True)

    assert p.sufficient is False
    assert p.quartile is None
    assert p.percentile is None
    assert p.rank_of_n is None
    assert "not assessed suppliers" in (p.reason or "")


def test_synthetic_is_labelled_in_the_output_and_the_caveats():
    p = placement_for(70, peers(40), snapshot_kw={"is_synthetic": True})
    assert p.snapshot.is_synthetic is True
    assert any("NOT REAL PEERS" in c for c in p.caveats)


# =========================================================================================
# HARD RULE — member refs are stored, never published (decision 4).
# =========================================================================================


def test_snapshot_stores_member_refs_for_the_dispute_path():
    snapshot = build_snapshot(assign_cohort(ACME, lookup_of(floor=peers(12))), peers(12))
    assert len(snapshot.member_refs) == 12
    assert snapshot.member_hash, "the hash pins the population without disclosing it"


def test_public_projection_cannot_carry_member_refs():
    """Structural, not procedural: `PublicCohortSnapshot` has no field for them, so a route cannot
    leak them by omission."""
    snapshot = build_snapshot(assign_cohort(ACME, lookup_of(floor=peers(12))), peers(12))
    public = snapshot.public().model_dump()

    assert "member_refs" not in public
    assert "member_postures" not in public
    assert public["member_hash"] == snapshot.member_hash


def test_no_peer_ref_appears_anywhere_in_a_serialised_placement():
    p = placement_for(70, peers(40))
    serialised = p.model_dump_json()
    for i in range(40):
        assert f"peer-{i}" not in serialised


# =========================================================================================
# HARD RULE — posture and confidence never blend; low confidence is labelled, not suppressed.
# =========================================================================================


def test_low_supplier_confidence_is_flagged_and_the_placement_is_still_published():
    p = placement_for(70, peers(40), supplier_confidence=0.4)

    assert p.confidence_flagged is True
    assert p.overall.sufficient is True, "labelled, never suppressed"
    assert p.overall.quartile is not None
    assert any("may be unreliable" in c for c in p.caveats)


def test_supplier_confidence_is_passed_through_unchanged():
    p = placement_for(70, peers(40), supplier_confidence=0.83)
    assert p.supplier_confidence == 0.83


def test_confidence_never_moves_the_placement():
    """The two axes stay apart. Identical postures and peers must place identically whatever the
    supplier's coverage is — otherwise coverage has leaked into the comparison."""
    high = placement_for(70, peers(40), supplier_confidence=0.99)
    low = placement_for(70, peers(40), supplier_confidence=0.10)

    assert high.overall.quartile == low.overall.quartile
    assert high.overall.percentile == low.overall.percentile
    assert high.overall.rank_of_n == low.overall.rank_of_n


def test_reliability_is_itemised_rather_than_one_opaque_number():
    p = placement_for(70, peers(40), supplier_confidence=0.9)
    r = p.reliability

    assert 0.0 <= r.value <= 1.0
    assert r.band in ("High", "Medium", "Low")
    for factor in (r.sample_adequacy, r.rung_exactness, r.peer_evidence, r.freshness):
        assert 0.0 <= factor <= 1.0
    if r.band != "High":
        assert r.notes, "a band with no explanation is the opaque number this object replaces"


# =========================================================================================
# HARD RULE — the module contextualises scores; it never modifies them.
# =========================================================================================


def test_benchmarking_never_alters_input_scores():
    """The one-sentence contract of the whole package."""
    domains = {"email_auth": 55, "attack_surface": 80}
    original = dict(domains)
    p = placement_for(68, peers(40), domains=domains, supplier_confidence=0.7)

    assert domains == original, "the input dict was mutated"
    assert p.overall.subject == 68
    for dp in p.domains:
        if dp.domain in original:
            assert dp.placement.subject == original[dp.domain]


def test_firmographics_never_reach_the_placed_value():
    """Firmographics determine cohort MEMBERSHIP only. Two suppliers with the same posture and the
    same peers must place identically even when their size and delivery model differ."""
    small = SupplierFirmographics(supplier_ref="s", sector="technology",
                                  delivery_model="on_prem", employees=15)
    pool = peers(40)
    a = placement_for(70, pool, firmographics=ACME)
    b = placement_for(70, pool, firmographics=small)

    assert a.overall.quartile == b.overall.quartile
    assert a.overall.percentile == b.overall.percentile
    assert a.overall.delta_from_median == b.overall.delta_from_median


# =========================================================================================
# SUCCESS CRITERION 4 — a discrimination test runs on cohort build and flags non-discriminating
#                       signals.
# =========================================================================================


def test_a_signal_every_peer_fails_is_flagged_as_non_discriminating():
    """The flat tax. Six signals in the real corpus penalise 100% of it; a penalty everyone pays
    shifts the intercept and ranks nobody."""
    pool = [peer(f"p{i}", 60 + i, signals={"stale_hosts": "many"}) for i in range(20)]
    verdicts = {v.key: v for v in discrimination_report(pool)}

    assert verdicts["stale_hosts"].verdict == "non_discriminating"
    assert verdicts["stale_hosts"].statistic == "modal_share"
    assert verdicts["stale_hosts"].value == 1.0


def test_a_signal_every_peer_passes_is_flagged_too():
    """Both directions. All-pass is exactly as useless for ranking as all-fail."""
    pool = [peer(f"p{i}", 60 + i, signals={"tls_version": "tls_13"}) for i in range(20)]
    verdicts = {v.key: v for v in discrimination_report(pool)}
    assert verdicts["tls_version"].verdict == "non_discriminating"


def test_a_varying_signal_is_not_flagged():
    bands = ["reject", "none", "quarantine", "none"]
    pool = [peer(f"p{i}", 60 + i, signals={"dmarc": bands[i % 4]}) for i in range(20)]
    verdicts = {v.key: v for v in discrimination_report(pool)}
    assert verdicts["dmarc"].verdict == "discriminating"


def test_a_domain_with_zero_iqr_is_flagged():
    pool = [peer(f"p{i}", 60 + i, domains={"breach_history": 100}) for i in range(20)]
    verdicts = {v.key: v for v in discrimination_report(pool)}

    assert verdicts["breach_history"].verdict == "non_discriminating"
    assert verdicts["breach_history"].statistic == "iqr"


def test_below_the_observation_floor_the_verdict_is_untested_not_a_guess():
    pool = [peer(f"p{i}", 60 + i, signals={"dmarc": "none"}) for i in range(4)]
    verdicts = {v.key: v for v in discrimination_report(pool)}
    assert verdicts["dmarc"].verdict == "untested"


def test_the_report_runs_on_snapshot_build_and_flags_land_on_the_snapshot():
    pool = [peer(f"p{i}", 60 + i, signals={"stale_hosts": "many"},
                 domains={"breach_history": 100}) for i in range(20)]
    snapshot = build_snapshot(assign_cohort(ACME, lookup_of(floor=pool)), pool)

    flagged = {v.key for v in snapshot.non_discriminating}
    assert flagged == {"stale_hosts", "breach_history"}


def test_a_non_discriminating_domain_is_suppressed_from_peer_gap_reporting_not_dropped():
    pool = [peer(f"p{i}", 60 + i, domains={"breach_history": 100, "email_auth": 40 + i})
            for i in range(20)]
    p = placement_for(70, pool, domains={"breach_history": 100, "email_auth": 45})

    by_domain = {dp.domain: dp for dp in p.domains}
    assert by_domain["breach_history"].suppressed is True, "excluded from the gap list"
    assert by_domain["breach_history"].placement is not None, "but not dropped"
    assert by_domain["email_auth"].suppressed is False
    assert any("do not vary across this cohort" in c for c in p.caveats), "and disclosed"
    assert not any("Breach history" in line for line in p.security_narrative)


# =========================================================================================
# THE LADDER — deepen while density allows, widen below the floor, refuse beneath that.
# =========================================================================================


def test_the_ladder_deepens_when_the_most_specific_rung_is_dense_enough():
    assignment = assign_cohort(ACME, lookup_of(exact=peers(40), floor=peers(90)))
    assert assignment.dimensions.keys() == {"sector", "size_band", "delivery_model"}
    assert assignment.widened is False


def test_the_ladder_falls_back_to_the_floor_and_records_what_it_tried():
    assignment = assign_cohort(ACME, lookup_of(exact=peers(6), floor=peers(34)))

    assert assignment.dimensions.keys() == {"sector", "size_band"}
    assert assignment.n == 34
    assert assignment.widened is False, "the floor is not a widening"
    tried = {r.label: r.n for r in assignment.rationale}
    assert tried["sector + size + delivery model"] == 6
    assert "n=6" in assignment.rationale_text() or "(n=6)" in assignment.rationale_text()


def test_widening_below_the_floor_is_disclosed():
    assignment = assign_cohort(ACME, lookup_of(exact=peers(2), floor=peers(3), sector=peers(20)))

    assert assignment.dimensions.keys() == {"sector"}
    assert assignment.widened is True


def test_the_ladder_reaches_the_sector_group_rollup_but_no_further():
    assignment = assign_cohort(
        ACME, lookup_of(exact=peers(1), floor=peers(1), sector=peers(2), group=peers(40)),
    )
    assert assignment.dimensions.keys() == {"sector_group"}
    assert assignment.n == 40


def test_no_ladder_rung_may_pool_every_industry():
    """A peer group spanning all industries is not a peer group — the comparison this whole feature
    exists to refuse. Enforced at config load."""
    with pytest.raises(BenchmarkingConfigError, match="not a peer group"):
        _config_with(ladder=[["size_band", "delivery_model"], ["sector"]])


def test_a_misordered_ladder_is_rejected_at_load():
    """Assignment takes the FIRST satisfying rung, so a ladder that is not most-specific-first would
    quietly assign the loosest cohort that clears the threshold."""
    with pytest.raises(BenchmarkingConfigError, match="most-specific first"):
        _config_with(ladder=[["sector"], ["sector", "size_band", "delivery_model"]])


def test_a_rung_needing_a_dimension_the_supplier_lacks_is_skipped_not_matched_on_null():
    """Matching on a null would pool every unsized supplier into a cohort whose only shared property
    is that we could not size them."""
    unsized = SupplierFirmographics(supplier_ref="u", sector="technology", delivery_model="saas")
    assignment = assign_cohort(unsized, lookup_of(exact=peers(40), sector=peers(40)))

    skipped = [r for r in assignment.rationale if r.skipped_reason]
    assert any("size_band" in (r.skipped_reason or "") for r in skipped)
    assert "size_band" not in assignment.dimensions


# =========================================================================================
# SIZE BAND — derived, versioned, disputable, and the disagreement retained.
# =========================================================================================


@pytest.mark.parametrize("employees,expected", [
    (5, "micro"), (19, "micro"), (20, "small"), (199, "small"),
    (200, "mid"), (999, "mid"), (1000, "large"), (9999, "large"), (10000, "enterprise"),
])
def test_headcount_bands_at_their_boundaries(employees, expected):
    d = derive_size_band(SupplierFirmographics(supplier_ref="x", employees=employees))
    assert d.band == expected


def test_disagreement_between_the_two_size_inputs_is_retained_not_resolved_away():
    """A 240-person firm turning over A$310M bands `small` on headcount and `large` on revenue. One
    band is what n>=30 can afford; recording the disagreement is what keeps it honest."""
    d = derive_size_band(SupplierFirmographics(
        supplier_ref="x", employees=240, revenue=310_000_000, revenue_currency="AUD",
    ))
    assert d.employee_band == "mid"
    assert d.revenue_band == "large"
    assert d.band == "large", "`max`: the higher expectation is the defensible one"
    assert d.disagreed is True
    assert d.resolved_by == "revenue"
    assert "disagreed" in d.basis()


def test_no_size_input_yields_no_band_rather_than_a_guess():
    d = derive_size_band(SupplierFirmographics(supplier_ref="x"))
    assert d.band is None
    assert d.resolved_by == "none"
    assert "No size band" in d.basis()


def test_an_unconvertible_currency_yields_no_revenue_band():
    """Better no band than a band derived from a rate we do not hold."""
    d = derive_size_band(SupplierFirmographics(
        supplier_ref="x", revenue=500_000_000, revenue_currency="ZZZ",
    ))
    assert d.revenue_band is None


def test_the_basis_names_the_rule_version_so_a_dispute_has_something_to_argue_with():
    d = derive_size_band(SupplierFirmographics(supplier_ref="x", employees=5000))
    assert "rule v1" in d.basis()
    assert "max" in d.basis()


# =========================================================================================
# ESTIMATORS — ties, ranks, resolution, outliers, quartile direction.
# =========================================================================================


def test_midrank_credits_half_a_tie_where_at_or_below_credits_all_of_it():
    """The conventional `at-or-below / n` reports a supplier tied with ten others at the median as
    ABOVE the 50th percentile — it inherits credit for beating suppliers it merely matched."""
    values = [40] * 5 + [70] * 11 + [90] * 5

    assert midrank_percentile(values, 70) == pytest.approx(50.0)
    at_or_below = 100 * sum(1 for v in values if v <= 70) / len(values)
    assert at_or_below > 76, "the error this correction removes is ~26 percentile points"


def test_rank_is_one_for_the_highest_posture_and_ties_share_a_rank():
    values = [50, 60, 70, 70, 70, 90]
    assert rank_of(values, 90) == (1, 1)
    assert rank_of(values, 70) == (2, 3), "three tied suppliers all rank 2"
    assert rank_of(values, 50) == (6, 1)


def test_rank_of_n_is_always_present_when_a_placement_is_published():
    for n in (8, 20, 30, 100):
        p = place(70, [50 + i for i in range(n)])
        assert p.rank_of_n is not None
        assert 1 <= p.rank_of_n <= n + 1


def test_percentile_resolution_never_overstates_what_the_sample_can_express():
    """At n=30 the achievable step is 4 points; claiming a 67th percentile implies a precision the
    sample does not have, so the step is published beside it."""
    p = place(70, [50 + i for i in range(30)])
    assert p.percentile_resolution == 4
    assert p.percentile % p.percentile_resolution == 0


def test_quartile_direction_is_always_stated_because_q1_is_ambiguous():
    """Q1 means the best quarter in finance and the worst quarter almost everywhere else."""
    p = place(70, [50 + i for i in range(40)])
    assert p.quartile_label is not None
    assert "1 = lowest" in p.quartile_direction


def test_outliers_use_the_iqr_fence_and_survive_one_extreme_member():
    """A standard-deviation fence would be dragged open by the single 100, and would then fail to
    flag the 10. At n=12 one member is a large share of the population."""
    pool = peers(11, start=70) + [peer("x", 100)]
    p = placement_for(10, pool)
    assert p.overall.outlier_low is True
    assert any("below the normal range" in c for c in p.caveats)


def test_the_median_is_never_interpolated():
    """An interpolated median between two real suppliers is a company that does not exist."""
    pool = [peer("a", 60), peer("b", 61), peer("c", 62), peer("d", 63),
            peer("e", 64), peer("f", 65), peer("g", 66), peer("h", 67)]
    snapshot = build_snapshot(assign_cohort(ACME, lookup_of(floor=pool)), pool)
    assert snapshot.distribution.median in {p.posture for p in pool}


# =========================================================================================
# PER-DOMAIN — every row carries its own n and its own resolution.
# =========================================================================================


def test_a_domain_n_is_its_own_and_not_the_cohort_n():
    """A cohort of 40 may hold only 12 suppliers with an email_auth score."""
    pool = peers(40)
    for i, p in enumerate(pool):
        p.domains = {"attack_surface": 60 + (i % 20)}
        if i < 12:
            p.domains["email_auth"] = 50 + i

    placement = placement_for(70, pool, domains={"email_auth": 55, "attack_surface": 70})
    by_domain = {dp.domain: dp.placement for dp in placement.domains}

    assert placement.overall.n == 40
    assert by_domain["attack_surface"].n == 40
    assert by_domain["email_auth"].n == 12


def test_a_domain_below_its_own_floor_refuses_while_the_overall_still_publishes():
    """The card legitimately shows an overall percentile beside a domain refusal. That reads as an
    inconsistency only if the rows do not carry their own n — so they do."""
    pool = peers(40)
    for i, p in enumerate(pool):
        p.domains = {"breach_history": 70 + i} if i < 5 else {}

    placement = placement_for(70, pool, domains={"breach_history": 60})
    by_domain = {dp.domain: dp.placement for dp in placement.domains}

    assert placement.overall.sufficient is True
    assert placement.overall.percentile is not None
    assert by_domain["breach_history"].sufficient is False
    assert by_domain["breach_history"].n == 5


def test_a_peer_never_assessed_for_a_domain_is_not_a_peer_that_scored_zero():
    """Treating absence as zero would drag a domain median down with a collection failure."""
    pool = peers(20)
    for i, p in enumerate(pool):
        p.domains = {"email_auth": 90} if i < 10 else {}

    snapshot = build_snapshot(assign_cohort(ACME, lookup_of(floor=pool)), pool)
    stats = {s.domain: s for s in snapshot.domains}
    assert stats["email_auth"].distribution.n == 10
    assert stats["email_auth"].distribution.median == 90


def test_there_is_no_composite_benchmark_score_across_domains():
    """A blend would hide the single domain a given buyer cares about."""
    p = placement_for(70, peers(40), domains={"email_auth": 20, "attack_surface": 95})
    dumped = p.model_dump()
    assert "benchmark_score" not in dumped
    assert "composite" not in dumped


# =========================================================================================
# NARRATIVE — versioned templates that refuse rather than print a blank.
# =========================================================================================


def test_a_template_refuses_to_render_when_a_required_field_is_missing():
    """`str.format` on a partial dict prints '...for  by  points' — a confident sentence with the
    numbers silently removed. A refusal is loud; a blank is not."""
    with pytest.raises(TemplateRefused, match="missing or null"):
        render("security", "placed", {"domain_label": "Email authentication"})


def test_a_template_refuses_on_a_null_as_well_as_an_absence():
    """A None reaching str.format renders the four characters 'None' into a sentence, which looks
    deliberate and is worse than a blank."""
    fields = {"domain_label": "X", "direction": "below", "cohort_label": "tech",
              "delta_abs": None, "subject": 50, "median": 60, "n": 30}
    with pytest.raises(TemplateRefused):
        render("security", "placed", fields)


def test_both_audiences_get_prose_from_the_same_placement():
    p = placement_for(60, peers(40), domains={"email_auth": 40})
    assert p.security_narrative, "security wants per-domain comparison"
    assert p.procurement_narrative, "procurement wants a placement and an action"
    assert p.narrative_version >= 1, "the version that produced this prose is recorded"


def test_the_procurement_action_comes_from_the_scope_table_and_is_marked_as_guidance():
    p = placement_for(50, peers(40))
    assert p.action, "bottom-quartile x critical scope must yield an action"
    assert "not legal advice" in (p.action_disclaimer or "")


def test_data_access_scope_changes_the_action_but_never_the_placement():
    """The one place scope enters, and it enters interpretation rather than the cohort key."""
    critical = SupplierFirmographics(supplier_ref="a", sector="technology",
                                     delivery_model="saas", employees=5000,
                                     data_access_scope="critical")
    low = critical.model_copy(update={"data_access_scope": "low"})
    pool = peers(40)

    a = placement_for(50, pool, firmographics=critical)
    b = placement_for(50, pool, firmographics=low)

    assert a.action != b.action, "scope drives the recommendation"
    assert a.assignment.cohort_key == b.assignment.cohort_key, "and nothing else"
    assert a.overall.quartile == b.overall.quartile


def test_the_self_selection_caveat_is_never_omitted():
    """Peers are suppliers this deployment happened to assess — a convenience sample. A reader who
    mistakes that for an industry norm misreads every variance computed against it."""
    for n in (0, 8, 40):
        p = placement_for(70, peers(n))
        assert any("not a random sample" in c for c in p.caveats)


# =========================================================================================
# SUCCESS CRITERION 5 — a supplier can dispute cohort assignment and the dispute is logged.
#                       (Store-backed paths are covered in test_api.py; this is the shape.)
# =========================================================================================


def test_only_inputs_are_disputable_and_the_cell_is_not_representable():
    """The placement is a deterministic lookup over disputable inputs and carries no independent
    judgement, so a request to dispute one cannot be constructed."""
    from typing import get_args

    from app.benchmarking.models import DisputeTarget

    targets = set(get_args(DisputeTarget))
    assert targets == {"sector", "size_band", "delivery_model", "headcount", "revenue"}
    for forbidden in ("cohort", "quartile", "percentile", "snapshot", "placement", "rank"):
        assert forbidden not in targets


def test_an_open_dispute_notates_the_placement():
    """The US Chamber / FCRA principle: a disputed rating is marked as disputed until resolved.
    Silence during review is the exposure."""
    from app.benchmarking.models import CohortDispute

    dispute = CohortDispute(
        id="e1", dispute_id="d1", supplier_ref="acme", state="submitted",
        target="sector", evidence="We are financial services, not technology.",
    )
    p = placement_for(70, peers(40), disputes=[dispute])

    assert p.disputed is True
    assert "d1" in p.open_dispute_ids
    assert any("DISPUTED" in line for line in p.procurement_narrative)


def test_a_resolved_dispute_stops_notating_the_placement():
    from app.benchmarking.models import CohortDispute

    resolved = CohortDispute(
        id="e2", dispute_id="d1", supplier_ref="acme", state="rejected",
        target="sector", evidence="...", note="Sector confirmed against ABN registry.",
    )
    p = placement_for(70, peers(40), disputes=[resolved])
    assert p.disputed is False


# =========================================================================================
# REPRODUCIBILITY — the snapshot, and the delta that falls out of it.
# =========================================================================================


def test_a_placement_carries_the_snapshot_it_was_computed_from():
    p = placement_for(70, peers(40))
    assert p.snapshot.snapshot_id
    assert p.snapshot.member_hash
    assert p.snapshot.n == 40


def test_the_same_population_hashes_the_same_and_a_different_one_does_not():
    pool = peers(12)
    a = build_snapshot(assign_cohort(ACME, lookup_of(floor=pool)), pool)
    b = build_snapshot(assign_cohort(ACME, lookup_of(floor=pool)), list(reversed(pool)))
    c = build_snapshot(assign_cohort(ACME, lookup_of(floor=pool)), pool + [peer("z", 88)])

    assert a.member_hash == b.member_hash, "order must not change the identity of a population"
    assert a.member_hash != c.member_hash


def test_stored_peer_values_make_a_placement_exactly_reproducible():
    """Five order statistics can rebuild a median but not a rank, so the snapshot stores the sorted
    values — otherwise a historical placement re-derived from summary stats would not reproduce."""
    pool = peers(40)
    snapshot = build_snapshot(assign_cohort(ACME, lookup_of(floor=pool)), pool)
    assert snapshot.member_postures == sorted(p.posture for p in pool)

    first = build_placement(ACME, 70, assign_cohort(ACME, lookup_of(floor=pool)), snapshot)
    again = build_placement(ACME, 70, assign_cohort(ACME, lookup_of(floor=pool)), snapshot)
    assert first.overall.model_dump() == again.overall.model_dump()


def test_the_delta_separates_supplier_movement_from_cohort_movement():
    """The output that justifies storing snapshots at all: a supplier that gained three points while
    its cohort gained seven has lost ground without doing anything wrong."""
    before_pool = peers(40, start=40)
    before = placement_for(60, before_pool)

    after_pool = peers(40, start=47)
    after = placement_for(63, after_pool, previous=before)

    assert after.delta is not None
    assert after.delta.posture_change == 3
    assert after.delta.cohort_median_change == 7
    assert after.delta.previous_snapshot_id == before.snapshot.snapshot_id
    assert "cohort" in (after.delta.net_effect or "").lower()


def test_stale_peers_are_disclosed_and_counted_never_dropped():
    """Dropping them would bias the cohort toward whoever we happen to have rescored recently."""
    now = utcnow()
    fresh = [peer(f"f{i}", 70 + i, computed_at=now) for i in range(10)]
    old = [peer(f"o{i}", 50 + i, computed_at=now - timedelta(days=500)) for i in range(5)]
    pool = fresh + old

    snapshot = build_snapshot(assign_cohort(ACME, lookup_of(floor=pool)), pool, now=now)
    assert snapshot.stale_peers == 5
    assert snapshot.distribution.n == 15, "counted, not dropped"


def test_peer_confidence_is_disclosed_and_not_filtered_on():
    """Excluding thinly-evidenced peers biases the cohort toward the observable — i.e. toward large
    companies — which is the observability bias this platform exists to remove."""
    pool = [peer(f"p{i}", 60 + i, confidence=0.2) for i in range(20)]
    snapshot = build_snapshot(assign_cohort(ACME, lookup_of(floor=pool)), pool)

    assert snapshot.distribution.n == 20, "kept"
    assert snapshot.peer_confidence_median == pytest.approx(0.2), "and disclosed"


# =========================================================================================
# CONFIG VALIDATION — the file fails at startup, never at serve time.
# =========================================================================================


def test_the_shipped_config_loads_and_meets_its_own_floors():
    from app.benchmarking.config import get_benchmarking_config

    cfg = get_benchmarking_config()
    assert cfg.min_quartile_n() >= 8
    assert cfg.min_percentile_n() >= 30
    assert cfg.action_disclaimer()
    assert cfg.self_selection_caveat()


def test_a_sector_in_two_groups_is_rejected_because_the_rollup_must_be_a_partition():
    from pathlib import Path

    import yaml

    from app.benchmarking.config import _DEFAULT_PATH

    data = yaml.safe_load(_DEFAULT_PATH.read_text(encoding="utf-8"))
    data["benchmarking"]["sector_groups"]["extra"] = ["technology"]
    with pytest.raises(BenchmarkingConfigError, match="partition"):
        BenchmarkingConfig(data, Path("test"))


def test_an_incomplete_action_table_is_rejected_at_load():
    """A missing cell would silently drop the recommendation from a card, which reads as 'no action
    required'."""
    from pathlib import Path

    import yaml

    from app.benchmarking.config import _DEFAULT_PATH

    data = yaml.safe_load(_DEFAULT_PATH.read_text(encoding="utf-8"))
    del data["benchmarking"]["narrative"]["actions"]["bottom_quartile"]["critical"]
    with pytest.raises(BenchmarkingConfigError, match="incomplete"):
        BenchmarkingConfig(data, Path("test"))
