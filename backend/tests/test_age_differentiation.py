"""Age differentiation enhancement tests.

Tests for the age-based enhancements to vendor risk assessment:
- Inherent risk baseline adjustment by age
- Age-specific residual risk thresholds
- Age-adjusted monitoring cadence
- Age-specific evidence weighting
"""

from datetime import UTC, datetime

import pytest

from app.assessment_depth import plan_for
from app.longevity import AgeBand
from app.maturity import age_adjusted_assurance, maturity_index
from app.residual_risk import inherent_tier, residual_risk
from app.models import Criticality


def test_inherent_tier_age_adjustment_startup():
    """Test that startup vendors get elevated inherent risk."""
    # Base tier: medium (criticality=medium, scope=medium)
    # Startup adjustment: +1 tier -> high
    result = inherent_tier(
        criticality="medium",
        data_access_scope="medium",
        age_band="startup"
    )
    assert result.tier == "high"
    assert "Age-based adjustment" in result.basis
    assert "elevated" in result.basis.lower()


def test_inherent_tier_age_adjustment_young():
    """Test that young vendors get elevated inherent risk."""
    # Base tier: low (criticality=low, scope=low)
    # Young adjustment: +1 tier -> medium
    result = inherent_tier(
        criticality="low",
        data_access_scope="low",
        age_band="young"
    )
    assert result.tier == "medium"
    assert "Age-based adjustment" in result.basis


def test_inherent_tier_age_adjustment_mature():
    """Test that mature vendors get reduced inherent risk."""
    # Base tier: high (criticality=high, scope=medium)
    # Mature adjustment: -1 tier -> medium
    result = inherent_tier(
        criticality="high",
        data_access_scope="medium",
        age_band="mature"
    )
    assert result.tier == "medium"
    assert "Age-based adjustment" in result.basis
    assert "reduced" in result.basis.lower()


def test_inherent_tier_age_adjustment_veteran():
    """Test that veteran vendors get reduced inherent risk."""
    # Base tier: high (criticality=high, scope=medium)
    # Veteran adjustment: -1 tier -> medium
    result = inherent_tier(
        criticality="high",
        data_access_scope="medium",
        age_band="veteran"
    )
    assert result.tier == "medium"
    assert "Age-based adjustment" in result.basis


def test_inherent_tier_age_adjustment_established():
    """Test that established vendors get no age adjustment."""
    result = inherent_tier(
        criticality="medium",
        data_access_scope="medium",
        age_band="established"
    )
    assert result.tier == "medium"
    assert "Age-based adjustment" not in result.basis


def test_inherent_tier_age_adjustment_unknown():
    """Test that unknown age gets no adjustment."""
    result = inherent_tier(
        criticality="medium",
        data_access_scope="medium",
        age_band="unknown"
    )
    assert result.tier == "medium"
    assert "Age-based adjustment" not in result.basis


def test_inherent_tier_age_adjustment_no_age_band():
    """Test that missing age_band parameter works correctly."""
    result = inherent_tier(
        criticality="medium",
        data_access_scope="medium",
        age_band=None
    )
    assert result.tier == "medium"
    assert "Age-based adjustment" not in result.basis


def test_inherent_tier_age_adjustment_bounds():
    """Test that age adjustments respect tier bounds."""
    # Startup with low base tier should not go below low
    result = inherent_tier(
        criticality="low",
        data_access_scope="low",
        age_band="startup"
    )
    assert result.tier == "medium"  # low + 1 = medium

    # Veteran with critical base tier gets reduced to high
    result = inherent_tier(
        criticality="high",
        data_access_scope="critical",
        age_band="veteran"
    )
    assert result.tier == "high"  # critical - 1 = high


def test_residual_risk_age_adjusted_matrix_young():
    """Test that young vendors use the age-adjusted residual risk matrix."""
    # Strong posture + low inherent = low for standard vendors
    # Young vendors: strong posture + low inherent = medium (elevated)
    result = residual_risk(
        posture=85,
        criticality="low",
        data_access_scope="low",
        age_band="young"
    )
    assert result.residual == "medium"
    assert result.published is True


def test_residual_risk_age_adjusted_matrix_startup():
    """Test that startup vendors use the age-adjusted residual risk matrix."""
    # Strong posture + medium inherent = low_medium for standard vendors
    # Startup vendors: strong posture + medium inherent = medium_high (elevated)
    result = residual_risk(
        posture=85,
        criticality="medium",
        data_access_scope="low",
        age_band="startup"
    )
    assert result.residual == "medium_high"


def test_residual_risk_standard_matrix_mature():
    """Test that mature vendors use the standard residual risk matrix."""
    # Strong posture + low inherent = low for standard vendors
    result = residual_risk(
        posture=85,
        criticality="low",
        data_access_scope="low",
        age_band="mature"
    )
    assert result.residual == "low"


def test_residual_risk_standard_matrix_veteran():
    """Test that veteran vendors use the standard residual risk matrix."""
    result = residual_risk(
        posture=85,
        criticality="low",
        data_access_scope="low",
        age_band="veteran"
    )
    assert result.residual == "low"


def test_monitoring_cadence_age_adjustment_startup():
    """Test that startup vendors get elevated monitoring cadence."""
    # T2 standard: semi_annual
    # Startup adjustment: quarterly
    plan = plan_for(tier="high", age_band="startup")
    assert plan.cadence == "quarterly"
    assert "Age-based adjustment" in plan.basis


def test_monitoring_cadence_age_adjustment_young():
    """Test that young vendors get elevated monitoring cadence."""
    # T3 standard: annual
    # Young adjustment: semi_annual
    plan = plan_for(tier="medium", age_band="young")
    assert plan.cadence == "semi_annual"
    assert "Age-based adjustment" in plan.basis


def test_monitoring_cadence_age_adjustment_startup_from_passive():
    """Test that startup vendors are never passive."""
    # T4 standard: passive
    # Startup adjustment: quarterly
    plan = plan_for(tier="low", age_band="startup")
    assert plan.cadence == "quarterly"
    assert "Age-based adjustment" in plan.basis


def test_monitoring_cadence_age_adjustment_young_from_passive():
    """Test that young vendors get at least annual monitoring."""
    # T4 standard: passive
    # Young adjustment: annual
    plan = plan_for(tier="low", age_band="young")
    assert plan.cadence == "annual"
    assert "Age-based adjustment" in plan.basis


def test_monitoring_cadence_no_adjustment_mature():
    """Test that mature vendors use standard cadence."""
    plan = plan_for(tier="medium", age_band="mature")
    assert plan.cadence == "annual"
    assert "Age-based adjustment" not in plan.basis


def test_monitoring_cadence_no_adjustment_veteran():
    """Test that veteran vendors use standard cadence."""
    plan = plan_for(tier="high", age_band="veteran")
    assert plan.cadence == "semi_annual"
    assert "Age-based adjustment" not in plan.basis


def test_monitoring_cadence_quarterly_no_change():
    """Test that quarterly cadence is not further elevated."""
    # T1 is already quarterly, should remain quarterly for all ages
    for age_band in ["startup", "young", "established", "mature", "veteran"]:
        plan = plan_for(tier="critical", age_band=age_band)
        assert plan.cadence == "quarterly"


def test_age_adjusted_assurance_startup():
    """Test that startup vendors get discounted assurance."""
    base = maturity_index(1.5)  # ~0.3
    adjusted = age_adjusted_assurance(1.5, source="gleif", age_band="startup")
    assert adjusted is not None
    assert adjusted < base  # Should be discounted
    assert adjusted == pytest.approx(base * 0.85, abs=0.01)


def test_age_adjusted_assurance_young():
    """Test that young vendors get discounted assurance."""
    base = maturity_index(3.0)  # ~0.45
    adjusted = age_adjusted_assurance(3.0, source="gleif", age_band="young")
    assert adjusted is not None
    assert adjusted < base  # Should be discounted
    assert adjusted == pytest.approx(base * 0.90, abs=0.01)


def test_age_adjusted_assurance_mature():
    """Test that mature vendors get no additional discount."""
    base = maturity_index(15.0)  # ~0.8
    adjusted = age_adjusted_assurance(15.0, source="gleif", age_band="mature")
    assert adjusted is not None
    assert adjusted == base  # No additional discount


def test_age_adjusted_assurance_veteran():
    """Test that veteran vendors get no additional discount."""
    base = maturity_index(25.0)  # 1.0
    adjusted = age_adjusted_assurance(25.0, source="gleif", age_band="veteran")
    assert adjusted is not None
    assert adjusted == base  # No additional discount


def test_age_adjusted_assurance_established():
    """Test that established vendors get no age adjustment."""
    base = maturity_index(7.0)  # ~0.6
    adjusted = age_adjusted_assurance(7.0, source="gleif", age_band="established")
    assert adjusted is not None
    assert adjusted == pytest.approx(base, abs=0.0001)  # No adjustment


def test_age_adjusted_assurance_unknown():
    """Test that unknown age gets no adjustment."""
    base = maturity_index(5.0)  # ~0.55
    adjusted = age_adjusted_assurance(5.0, source="gleif", age_band="unknown")
    assert adjusted is not None
    assert adjusted == pytest.approx(base, abs=0.0001)  # No adjustment


def test_age_adjusted_assurance_no_age_band():
    """Test that missing age_band returns base assurance."""
    base = maturity_index(5.0)
    adjusted = age_adjusted_assurance(5.0, source="gleif", age_band=None)
    assert adjusted == pytest.approx(base, abs=0.0001)


def test_age_adjusted_assurance_none_years():
    """Test that None years returns None."""
    adjusted = age_adjusted_assurance(None, source="gleif", age_band="startup")
    assert adjusted is None


def test_age_adjusted_assurance_with_weak_source():
    """Test that weak sources are still discounted by evidence strength."""
    # RDAP is weak (0.6), startup should get additional discount
    base = maturity_index(20.0)  # ~0.93
    adjusted = age_adjusted_assurance(20.0, source="rdap", age_band="startup")
    assert adjusted is not None
    # Should be discounted by both evidence strength (0.6) and age (0.85)
    assert adjusted < base * 0.6  # Evidence strength discount
    assert adjusted < base * 0.85  # Age discount


def test_age_differentiation_integration():
    """Test full integration of age differentiation across all modules."""
    # Young vendor scenario
    age_band = "young"
    
    # 1. Inherent risk elevated
    inherent = inherent_tier(
        criticality="medium",
        data_access_scope="medium",
        age_band=age_band
    )
    assert inherent.tier == "high"  # Elevated from medium
    
    # 2. Residual risk uses adjusted matrix
    residual = residual_risk(
        posture=70,
        criticality="medium",
        data_access_scope="medium",
        age_band=age_band
    )
    assert residual.residual == "high"  # Adjusted matrix
    
    # 3. Monitoring cadence elevated
    plan = plan_for(tier="medium", age_band=age_band)
    assert plan.cadence == "semi_annual"  # Elevated from annual
    
    # 4. Assurance discounted
    assurance = age_adjusted_assurance(3.0, source="gleif", age_band=age_band)
    base = maturity_index(3.0)
    assert assurance < base  # Discounted


def test_mature_vendor_integration():
    """Test full integration for mature vendor scenario."""
    age_band = "mature"
    
    # 1. Inherent risk reduced
    inherent = inherent_tier(
        criticality="high",
        data_access_scope="medium",
        age_band=age_band
    )
    assert inherent.tier == "medium"  # Reduced from high
    
    # 2. Residual risk uses standard matrix with reduced inherent tier
    residual = residual_risk(
        posture=70,
        criticality="high",
        data_access_scope="medium",
        age_band=age_band
    )
    # With inherent reduced to medium and moderate posture, residual is medium
    assert residual.residual == "medium"  # Standard matrix: moderate + medium = medium
    
    # 3. Monitoring cadence standard
    plan = plan_for(tier="high", age_band=age_band)
    assert plan.cadence == "semi_annual"  # Standard
    
    # 4. Assurance not additionally discounted
    assurance = age_adjusted_assurance(15.0, source="gleif", age_band=age_band)
    base = maturity_index(15.0)
    assert assurance == base  # No additional discount
