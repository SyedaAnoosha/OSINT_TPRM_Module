"""Operating history — the curve, and the invariants it is not allowed to break.

The bug these tests exist to prevent from coming back: age was five step-bands with the top one
opening at ten years, so an 11-year-old vendor and a 40-year-old vendor produced identical output
and a 2-year-old differed from a 40-year-old by less than the width of a grade band.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app import maturity
from app.models import Finding
from app.scoring.normalize import normalize_one
from app.scoring_config import get_scoring_config


# --------------------------------------------------------------------- the curve

def test_index_is_strictly_increasing_up_to_saturation():
    """The whole point: more operating history must never read as less."""
    years = [0, 0.5, 1, 2, 3, 5, 7, 10, 15, 20, 24]
    values = [maturity.maturity_index(y) for y in years]
    assert values == sorted(values)
    assert all(a < b for a, b in zip(values, values[1:], strict=False))


def test_a_forty_year_old_outranks_an_eleven_year_old():
    """THE REGRESSION. Both are `mature_gt_10`; the band cannot separate them and the index must."""
    assert maturity.maturity_band(11) == maturity.maturity_band(40) == "mature_gt_10"
    assert maturity.maturity_index(40) > maturity.maturity_index(11)


def test_two_years_and_twenty_years_are_materially_apart():
    """The user-visible complaint, asserted as arithmetic rather than trusted to the bands."""
    assert maturity.maturity_index(20) - maturity.maturity_index(2) > 0.5


def test_index_saturates_and_never_exceeds_one():
    assert maturity.maturity_index(maturity.SATURATION_YEARS) == 1.0
    assert maturity.maturity_index(40) == 1.0
    assert maturity.maturity_index(500) == 1.0


def test_growth_decelerates():
    """Diminishing returns is the claim the log curve makes — so assert it, don't assume it.
    Five more years matters more early than late."""
    early = maturity.maturity_index(5) - maturity.maturity_index(0)
    late = maturity.maturity_index(25) - maturity.maturity_index(20)
    assert early > late * 5


def test_unknown_age_is_none_not_zero():
    """A missing inception date is unknown, never 'founded today' — a different claim entirely."""
    assert maturity.maturity_index(None) is None
    assert maturity.maturity_band(None) is None
    assert maturity.assurance_index(None) is None


def test_a_future_inception_does_not_produce_a_negative_index():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    later = datetime(2030, 1, 1, tzinfo=UTC)
    assert maturity.years_between(later, now) == 0.0
    assert maturity.maturity_index(-5) == 0.0


# --------------------------------------------------------------------- band compatibility

@pytest.mark.parametrize(("years", "band"), [
    (0.5, "new_lt_1"), (1, "startup_lt_2"), (1.9, "startup_lt_2"),
    (2, "young_2_5"), (4.9, "young_2_5"),
    (5, "established_5_10"), (9.9, "established_5_10"),
    (10, "mature_gt_10"), (40, "mature_gt_10"),
])
def test_band_edges_are_unchanged(years: float, band: str):
    """scoring.yaml maps these keys to severities, reasons and actions. Moving an edge would
    silently re-score every stored vendor, so the edges are pinned."""
    assert maturity.maturity_band(years) == band


def test_both_collectors_agree_on_the_band():
    """They used to carry private copies of the same ladder. One model, one answer."""
    from app.collectors.rdap_collector import RdapCollector
    from app.collectors.wikidata_collector import _maturity_band as wikidata_band

    now = datetime.now(UTC)
    created = datetime(now.year - 12, 1, 1, tzinfo=UTC)
    rdap_band, rdap_years = RdapCollector._maturity_band(created, now=now)
    wd_band, wd_years = wikidata_band(created)
    assert rdap_band == wd_band == "mature_gt_10"
    assert rdap_years == pytest.approx(wd_years, abs=0.01)


# --------------------------------------------------------------------- evidence strength

def test_a_bought_domain_cannot_buy_the_assurance_of_a_trading_record():
    """An aged domain is purchasable at auction; a registry inception date is not. A 40-year
    RDAP-only claim must land near a mid-single-digit registry-evidenced company, not at the top."""
    rdap_40 = maturity.assurance_index(40, "rdap")
    registry_40 = maturity.assurance_index(40, "gleif")
    assert rdap_40 < registry_40
    assert rdap_40 == pytest.approx(maturity.maturity_index(5), abs=0.06)


def test_evidence_discount_is_one_directional():
    """A weak source can lower assurance; it can never raise it above the honest age curve."""
    for years in (0.5, 2, 10, 40):
        for source in ("rdap", "wikidata", "gleif", "something_new"):
            assert maturity.assurance_index(years, source) <= maturity.maturity_index(years)


def test_an_unknown_source_gets_the_weakest_weight_not_full_credit():
    """A new collector earns its weight in the table; it does not inherit it by being absent."""
    assert maturity.evidence_strength("brand_new_collector") == maturity.DEFAULT_EVIDENCE_STRENGTH
    assert maturity.evidence_strength(None) == maturity.DEFAULT_EVIDENCE_STRENGTH
    assert maturity.evidence_strength("brand_new_collector") < maturity.evidence_strength("gleif")


# --------------------------------------------------------------------- the multiplier

def test_multiplier_spans_the_configured_bounds():
    assert maturity.multiplier_from(0.0, 0.96, 1.04) == 0.96
    assert maturity.multiplier_from(1.0, 0.96, 1.04) == 1.04
    assert maturity.multiplier_from(0.5, 0.96, 1.04) == 1.0


def test_multiplier_is_neutral_when_age_is_unknown():
    assert maturity.multiplier_from(None, 0.96, 1.04) == 1.0


def test_config_curve_separates_ages_the_band_table_could_not():
    cfg = get_scoring_config()
    m11 = cfg.confidence_multiplier_for_index(maturity.assurance_index(11, "gleif"))
    m40 = cfg.confidence_multiplier_for_index(maturity.assurance_index(40, "gleif"))
    assert m11 is not None and m40 is not None
    assert m40 > m11
    # The stepped fallback, by contrast, still cannot tell them apart — which is why it is only
    # ever the fallback.
    assert (cfg.confidence_multiplier_for_band("mature_gt_10")
            == cfg.confidence_multiplier_for_band("mature_gt_10"))


def test_missing_curve_falls_back_rather_than_inventing_a_default():
    """A scoring file predating the curve must keep scoring exactly as it did."""
    from app.scoring_config import ScoringConfig

    cfg = ScoringConfig.__new__(ScoringConfig)
    cfg.data = {"confidence": {"assurance_multiplier": {"signal": "entity_maturity",
                                                        "by_band": {"mature_gt_10": 1.02}}}}
    assert cfg.confidence_multiplier_for_index(0.9) is None
    assert cfg.confidence_multiplier_for_band("mature_gt_10") == 1.02


# --------------------------------------------------------------------- the invariant that matters

def test_maturity_never_reaches_a_penalty():
    """The bright line. Age informs CONFIDENCE and the peer cohort; it must not move posture.
    A 40-year-old and a 2-year-old with the same band carry the same penalty."""
    cfg = get_scoring_config()

    def penalty_for(years: float, source: str) -> float:
        finding = Finding(
            source=source, signal="entity_maturity", subcategory="business_continuity",
            category="business_financial_stability",
            observed=f"operating ~{years} year(s)",
            value={"band": maturity.maturity_band(years), "years": years,
                   "assurance_index": maturity.assurance_index(years, source)},
        )
        nf = normalize_one(finding, cfg, evidence_id=None)
        assert nf is not None
        return nf.penalty

    assert penalty_for(40, "gleif") == penalty_for(11, "gleif") == 0.0
    # Two vendors in the SAME band carry the same penalty regardless of their index.
    assert penalty_for(2, "gleif") == penalty_for(4.9, "rdap")


def test_normalizer_carries_the_index_onto_the_finding():
    cfg = get_scoring_config()
    finding = Finding(
        source="gleif", signal="entity_maturity", subcategory="business_continuity",
        category="business_financial_stability", observed="operating ~30 year(s)",
        value={"band": "mature_gt_10", "years": 30},
    )
    nf = normalize_one(finding, cfg, evidence_id=None)
    assert nf is not None
    # Derived from raw `years` even though the collector emitted no index — the fallback path.
    assert nf.assurance_index == pytest.approx(1.0, abs=0.01)
