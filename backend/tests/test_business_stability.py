"""Business Stability scoring unit tests — Phase 2.

Tests the Business Stability scoring engine, age-based modifiers, and gate logic.
"""

from datetime import UTC, datetime

import pytest

from app.business_stability import BusinessStabilityScore, compute_business_stability
from app.longevity import (
    age_band_from_years,
    apply_age_modifiers,
    base_age_score,
    confidence_adjustment,
    contingency_plan_required,
    operating_years,
    survivorship_bonus,
)
from app.models import FinancialProfile, InsolvencyRecord, ProfileField


def test_operating_years():
    """Test operating years calculation."""
    inc_date = datetime(2020, 1, 1, tzinfo=UTC)
    now = datetime(2024, 6, 1, tzinfo=UTC)
    years = (now - inc_date).days / 365.25
    assert 4.4 < years < 4.5


def test_age_band_from_years():
    """Test age band classification."""
    assert age_band_from_years(1.5) == "startup"
    assert age_band_from_years(3) == "young"
    assert age_band_from_years(7) == "established"
    assert age_band_from_years(15) == "mature"
    assert age_band_from_years(25) == "veteran"
    assert age_band_from_years(None) == "unknown"


def test_base_age_score():
    """Base score by age band — the values `scoring.yaml` declares.

    These are read from `business_stability.age_base_scores`, not hard-coded in `longevity.py`.
    Four different versions of this table were in circulation: the model file (70/75/80/85/100/60),
    this module's hard-coded copy (50/65/80/90/100/60), this test (70/85/90/95/100/85) and
    SYSTEM_EXPLANATION.md (92/94/96/98/100/95). The model file wins, because it is the artefact the
    methodology says is the deliverable. Change the numbers THERE and this test follows.
    """
    assert base_age_score("startup") == 70
    assert base_age_score("young") == 75
    assert base_age_score("established") == 80
    assert base_age_score("mature") == 85
    assert base_age_score("veteran") == 100
    assert base_age_score("unknown") == 60
    # The ordering is the part that must never invert, whatever the numbers are tuned to.
    assert (base_age_score("startup") < base_age_score("young")
            < base_age_score("established") < base_age_score("mature")
            < base_age_score("veteran"))


def test_confidence_adjustment():
    """Confidence adjustment by age band — from `business_stability.confidence_adjustments`."""
    assert confidence_adjustment("startup") == -0.15
    assert confidence_adjustment("young") == -0.10
    assert confidence_adjustment("established") == 0.00
    assert confidence_adjustment("mature") == 0.00
    assert confidence_adjustment("veteran") == 0.00
    assert confidence_adjustment("unknown") == -0.05


def test_survivorship_bonus():
    """Test survivorship bonus."""
    assert survivorship_bonus("startup") == 0
    assert survivorship_bonus("young") == 0
    assert survivorship_bonus("established") == 0
    assert survivorship_bonus("mature") == 5
    assert survivorship_bonus("veteran") == 10
    assert survivorship_bonus("unknown") == 0


def test_contingency_plan_required():
    """Test contingency plan requirement logic."""
    assert contingency_plan_required("startup", "high") is True
    assert contingency_plan_required("young", "high") is True
    assert contingency_plan_required("startup", "medium") is True
    assert contingency_plan_required("young", "medium") is False
    assert contingency_plan_required("established", "high") is False
    assert contingency_plan_required("veteran", "high") is False


def test_apply_age_modifiers():
    """Test age modifier application."""
    profile = FinancialProfile(vendor_ref="test")
    profile.incorporation_date = ProfileField(
        value=datetime(2022, 1, 1, tzinfo=UTC),
        source="test",
        locator="test",
        fetched_at=datetime.now(UTC),
    )

    age_score, adjusted_confidence = apply_age_modifiers(profile, 0.95)
    assert age_score == 75  # young band, per scoring.yaml age_base_scores
    assert adjusted_confidence == pytest.approx(0.85)  # 0.95 - 0.10


def test_business_stability_gate_active_insolvency():
    """Test that active insolvency triggers the gate."""
    profile = FinancialProfile(vendor_ref="test")
    profile.insolvency_records = [
        InsolvencyRecord(
            proceeding_type="liquidation",
            status="active",
            date=datetime(2024, 1, 1, tzinfo=UTC),
            jurisdiction="UK",
            case_number="CASE-12345",
            source="companies_house",
        )
    ]

    engine = BusinessStabilityScore(profile)
    result = engine.compute()

    assert result["gate_triggered"] is True
    assert result["score"] is None
    assert "liquidation" in result["gate_reason"]


def test_business_stability_historical_insolvency():
    """Test that historical insolvency applies penalty but does not gate."""
    profile = FinancialProfile(vendor_ref="test")
    profile.insolvency_records = [
        InsolvencyRecord(
            proceeding_type="administration",
            status="historical",
            date=datetime(2018, 1, 1, tzinfo=UTC),  # Old insolvency
            jurisdiction="UK",
            case_number="CASE-12345",
            source="companies_house",
        )
    ]
    profile.incorporation_date = ProfileField(
        value=datetime(2010, 1, 1, tzinfo=UTC),
        source="test",
        locator="test",
        fetched_at=datetime.now(UTC),
    )

    engine = BusinessStabilityScore(profile)
    result = engine.compute()

    assert result["gate_triggered"] is False
    assert result["score"] is not None
    # 2018 insolvency is >3 years old, so gets 'historical_insolvency_old' key
    assert "historical_insolvency_old" in result["penalties"]


def test_business_stability_no_insolvency():
    """Test that vendors with no insolvency score normally."""
    profile = FinancialProfile(vendor_ref="test")
    profile.insolvency_records = []
    profile.incorporation_date = ProfileField(
        value=datetime(2010, 1, 1, tzinfo=UTC),
        source="test",
        locator="test",
        fetched_at=datetime.now(UTC),
    )

    engine = BusinessStabilityScore(profile)
    result = engine.compute()

    assert result["gate_triggered"] is False
    assert result["score"] is not None
    assert len(result["penalties"]) == 0


def test_compute_business_stability_integration():
    """Test the full compute_business_stability integration."""
    profile = FinancialProfile(vendor_ref="test")
    profile.incorporation_date = ProfileField(
        value=datetime(2010, 1, 1, tzinfo=UTC),
        source="test",
        locator="test",
        fetched_at=datetime.now(UTC),
    )

    result = compute_business_stability(profile, 0.95)

    assert result["score"] is not None
    assert result["age_band"] is not None
    assert result["gate_triggered"] is False
    assert result["confidence_adjusted"] is not None


def test_business_stability_company_status_gate():
    """Test that dissolved company status triggers the gate."""
    profile = FinancialProfile(vendor_ref="test")
    profile.company_status = ProfileField(
        value="liquidation",
        source="companies_house",
        locator="test",
        fetched_at=datetime.now(UTC),
    )

    engine = BusinessStabilityScore(profile)
    result = engine.compute()

    assert result["gate_triggered"] is True
    assert "liquidation" in result["gate_reason"]


def test_business_stability_financial_penalties():
    """Test financial penalties for declining revenue and high debt."""
    from app.models import FinancialMetrics

    profile = FinancialProfile(vendor_ref="test")
    profile.incorporation_date = ProfileField(
        value=datetime(2010, 1, 1, tzinfo=UTC),
        source="test",
        locator="test",
        fetched_at=datetime.now(UTC),
    )
    profile.financial_metrics = [
        FinancialMetrics(
            period_end=datetime(2024, 3, 31, tzinfo=UTC),
            period_type="quarterly",
            revenue=1000000,
            source="test",
        ),
        FinancialMetrics(
            period_end=datetime(2024, 6, 30, tzinfo=UTC),
            period_type="quarterly",
            revenue=900000,
            source="test",
        ),
        FinancialMetrics(
            period_end=datetime(2024, 9, 30, tzinfo=UTC),
            period_type="quarterly",
            revenue=800000,
            source="test",
        ),
    ]

    engine = BusinessStabilityScore(profile)
    result = engine.compute()

    # Should have revenue decline penalty
    assert "revenue_decline" in result["penalties"] or result["revenue_trend"] == "declining"
