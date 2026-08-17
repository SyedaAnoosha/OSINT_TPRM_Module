"""Tests for age-specific risk factors module."""

import pytest

from app.age_risk_factors import (
    compute_age_differentiation_profile,
    financial_transparency_score,
    historical_depth_score,
    leadership_risk_score,
    media_velocity_score,
    operational_maturity_score,
    structural_change_score,
)


def test_historical_depth_score_startup():
    """Test historical depth scoring for startup vendors."""
    # Startup with 5 findings is impressive (rich for <2yr)
    result = historical_depth_score(finding_count=5, years_of_data=1.5, age_band="startup")
    assert result.band in ("rich", "moderate")
    assert result.finding_count == 5
    assert result.age_adjusted_score >= 0.5


def test_historical_depth_score_veteran():
    """Test historical depth scoring for veteran vendors."""
    # Veteran with 10 findings is sparse (should have 100+)
    result = historical_depth_score(finding_count=10, years_of_data=25, age_band="veteran")
    assert result.band == "sparse"
    assert result.age_adjusted_score < 0.2  # Penalized for sparse data


def test_historical_depth_score_mature():
    """Test historical depth scoring for mature vendors."""
    # Mature with 50 findings is moderate
    result = historical_depth_score(finding_count=50, years_of_data=15, age_band="mature")
    assert result.band in ("moderate", "limited")


def test_financial_transparency_score_startup_no_data():
    """Test financial transparency for startup with no data (expected)."""
    result = financial_transparency_score(
        has_financial_data=False,
        revenue_plausible=None,
        growth_rate=None,
        age_band="startup",
        years_of_operation=1.5,
    )
    # Startups get no penalty for no data, so score is high
    assert result.band in ("comprehensive", "transparent")
    assert result.has_financial_data is False
    assert result.transparency_score >= 0.8


def test_financial_transparency_score_veteran_no_data():
    """Test financial transparency for veteran with no data (concerning)."""
    result = financial_transparency_score(
        has_financial_data=False,
        revenue_plausible=None,
        growth_rate=None,
        age_band="veteran",
        years_of_operation=25,
    )
    assert result.band in ("partial", "limited")
    assert result.transparency_score < 0.8  # Some penalty applied


def test_financial_transparency_score_rapid_growth():
    """Test financial transparency with rapid growth."""
    result = financial_transparency_score(
        has_financial_data=True,
        revenue_plausible=True,
        growth_rate=3.0,  # 300% annual growth
        age_band="established",
        years_of_operation=7,
    )
    # With data + plausible revenue, score remains high despite growth
    assert result.transparency_score >= 0.8


def test_leadership_risk_score_startup():
    """Test leadership risk for startup (founder-dependent)."""
    result = leadership_risk_score(
        founder_history_clean=True,
        recent_turnover=False,
        succession_plan_evident=False,
        age_band="startup",
    )
    assert result.band in ("low", "stable")
    assert result.rationale.find("founder") != -1


def test_leadership_risk_score_veteran():
    """Test leadership risk for veteran (succession focus)."""
    result = leadership_risk_score(
        founder_history_clean=True,
        recent_turnover=False,
        succession_plan_evident=False,
        age_band="veteran",
    )
    assert result.band in ("moderate", "high")  # No succession plan is concerning
    assert result.rationale.find("succession") != -1


def test_leadership_risk_score_bad_founder():
    """Test leadership risk with concerning founder history."""
    result = leadership_risk_score(
        founder_history_clean=False,
        recent_turnover=False,
        succession_plan_evident=False,
        age_band="young",
    )
    assert result.risk_score > 0.5


def test_operational_maturity_score_startup():
    """Test operational maturity for startup (scaling risk)."""
    result = operational_maturity_score(
        infrastructure_age_years=1,
        process_maturity_evident=False,
        scaling_risk_indicators=2,
        age_band="startup",
    )
    assert result.band in ("immature", "developing")
    assert result.rationale.find("scaling") != -1


def test_operational_maturity_score_veteran():
    """Test operational maturity for veteran (degradation focus)."""
    result = operational_maturity_score(
        infrastructure_age_years=15,
        process_maturity_evident=True,
        scaling_risk_indicators=0,
        age_band="veteran",
    )
    assert result.band in ("established", "legacy")
    assert result.maturity_score > 0.7


def test_media_velocity_score_startup():
    """Test media velocity for startup (single finding significant)."""
    result = media_velocity_score(
        adverse_media_count=1,
        recent_spike=False,
        trend_direction=None,
        age_band="startup",
        years_of_history=1,
    )
    # Single finding + absence of history = critical for startup
    assert result.band in ("critical", "high")
    assert result.rationale.find("single") != -1


def test_media_velocity_score_veteran():
    """Test media velocity for veteran (trends matter more)."""
    result = media_velocity_score(
        adverse_media_count=1,
        recent_spike=False,
        trend_direction="stable",
        age_band="veteran",
        years_of_history=20,
    )
    assert result.band in ("low", "unknown")
    assert result.velocity_score < 0.3  # Single finding less significant


def test_media_velocity_score_declining_trend():
    """Test media velocity with declining trend."""
    result = media_velocity_score(
        adverse_media_count=5,
        recent_spike=False,
        trend_direction="declining",
        age_band="mature",
        years_of_history=15,
    )
    assert result.band in ("high", "critical")


def test_structural_change_score_startup():
    """Test structural change for startup (high suspicion)."""
    result = structural_change_score(
        name_changes=1,
        address_changes=2,
        ownership_changes=0,
        acquisition_activity=False,
        age_band="startup",
        years_of_operation=1.5,
    )
    assert result.band in ("high_suspicion", "moderate")
    assert result.rationale.find("shell") != -1


def test_structural_change_score_veteran():
    """Test structural change for veteran (transformation signal)."""
    result = structural_change_score(
        name_changes=0,
        address_changes=0,
        ownership_changes=1,
        acquisition_activity=True,
        age_band="veteran",
        years_of_operation=25,
    )
    # Acquisition activity for veteran is significant
    assert result.band in ("high_suspicion", "moderate")
    assert result.rationale.find("acquisition") != -1


def test_compute_age_differentiation_profile():
    """Test complete age differentiation profile computation."""
    result = compute_age_differentiation_profile(
        age_band="young",
        finding_count=15,
        years_of_data=3,
        has_financial_data=True,
        revenue_plausible=True,
        growth_rate=0.5,
        years_of_operation=3,
        founder_history_clean=True,
        recent_turnover=False,
        succession_plan_evident=False,
        infrastructure_age_years=3,
        process_maturity_evident=False,
        scaling_risk_indicators=1,
        adverse_media_count=0,
        recent_spike=False,
        trend_direction=None,
        years_of_history=3,
        name_changes=0,
        address_changes=0,
        ownership_changes=0,
        acquisition_activity=False,
    )
    
    assert result.age_band == "young"
    assert 0 <= result.overall_age_risk_score <= 1
    assert result.historical_depth.band is not None
    assert result.financial_transparency.band is not None
    assert result.leadership_risk.band is not None
    assert result.operational_maturity.band is not None
    assert result.media_velocity.band is not None
    assert result.structural_change.band is not None
    assert result.rationale is not None


def test_age_differentiation_profile_minimal():
    """Test age differentiation profile with minimal data."""
    result = compute_age_differentiation_profile(
        age_band="unknown",
    )
    
    assert result.age_band == "unknown"
    assert result.overall_age_risk_score >= 0
    assert result.historical_depth.band == "sparse"


def test_age_differentiation_profile_startup_minimal():
    """Test startup profile with minimal data (common case)."""
    result = compute_age_differentiation_profile(
        age_band="startup",
        finding_count=2,
        years_of_operation=1,
    )
    
    assert result.age_band == "startup"
    # Startups with minimal data have moderate risk due to unknowns
    assert result.overall_age_risk_score >= 0.2


def test_age_differentiation_profile_veteran_minimal():
    """Test veteran profile with minimal data (concerning)."""
    result = compute_age_differentiation_profile(
        age_band="veteran",
        finding_count=5,
        years_of_operation=20,
    )
    
    assert result.age_band == "veteran"
    # Veterans with minimal data should have higher risk (should have rich corpus)
    assert result.overall_age_risk_score > 0.4
