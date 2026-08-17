"""Tests for age-based confidence calculation.

This demonstrates the new (expected & found) / expected methodology
vs the old flat penalty approach.
"""

import pytest

from app.confidence_calculator import (
    ConfidenceCalculator,
    SignalStatus,
    calculate_age_based_confidence,
)
from app.confidence_config import (
    AgeBand,
    SizeBand,
    get_expected_signals,
    get_total_expected_weight,
    is_signal_expected,
)


def test_signal_expectation_by_age():
    """Test that signal expectations scale appropriately with company age."""
    
    # 2-month-old startup - should NOT expect financial filings or certifications
    startup_expected = get_expected_signals(
        age_band="startup",
        size_band="small",
        operating_years=0.2,
    )
    
    # Financial filings and certifications should NOT be expected for startups
    assert "sec_filing" not in startup_expected
    assert "cert_posture" not in startup_expected
    assert "vd_program" not in startup_expected
    
    # But basic security and domain signals SHOULD be expected
    assert "domain_registration" in startup_expected
    assert "tls_version" in startup_expected
    assert "dmarc" in startup_expected
    assert "entity_status" in startup_expected
    
    # 15-year-old company - SHOULD expect more signals
    veteran_expected = get_expected_signals(
        age_band="veteran",
        size_band="large",
        operating_years=15.0,
    )
    
    # Veterans should expect financial filings and certifications
    assert "sec_filing" in veteran_expected
    assert "cert_posture" in veteran_expected
    assert "vd_program" in veteran_expected
    
    # But still expect the basics
    assert "domain_registration" in veteran_expected
    assert "tls_version" in veteran_expected


def test_confidence_calculation_startup():
    """Test confidence calculation for a startup with basic security but no advanced signals."""
    
    calculator = ConfidenceCalculator()
    
    # Startup has basic security (expected) but no advanced signals (not expected yet)
    signal_statuses = {
        # Always expected - FOUND
        "domain_registration": SignalStatus.FOUND,
        "tls_version": SignalStatus.FOUND,
        "cert_validity": SignalStatus.FOUND,
        "dmarc": SignalStatus.FOUND,
        "entity_status": SignalStatus.FOUND,
        
        # Not expected for startup - NOT FOUND (shouldn't hurt confidence)
        "sec_filing": SignalStatus.NOT_FOUND,
        "cert_posture": SignalStatus.NOT_FOUND,
        "vd_program": SignalStatus.NOT_FOUND,
        "regulator_action": SignalStatus.NOT_FOUND,
    }
    
    result = calculator.calculate_confidence(
        signal_statuses=signal_statuses,
        age_band="startup",
        size_band="small",
        operating_years=0.5,
    )
    
    # Startup should have high confidence (all expected signals found)
    assert result.confidence_score >= 0.90
    assert result.confidence_band == "High"
    
    # The missing advanced signals should NOT count as coverage gaps
    assert "sec_filing" not in result.coverage_gaps
    assert "cert_posture" not in result.coverage_gaps


def test_confidence_calculation_veteran():
    """Test confidence calculation for a veteran company missing expected signals."""
    
    calculator = ConfidenceCalculator()
    
    # Veteran has basic security but MISSING advanced signals (which ARE expected)
    signal_statuses = {
        # Always expected - FOUND
        "domain_registration": SignalStatus.FOUND,
        "tls_version": SignalStatus.FOUND,
        "cert_validity": SignalStatus.FOUND,
        "dmarc": SignalStatus.FOUND,
        "entity_status": SignalStatus.FOUND,
        
        # Expected for veteran - NOT FOUND (should hurt confidence)
        "sec_filing": SignalStatus.NOT_FOUND,
        "cert_posture": SignalStatus.NOT_FOUND,
        "vd_program": SignalStatus.NOT_FOUND,
        "regulator_action": SignalStatus.NOT_FOUND,
    }
    
    result = calculator.calculate_confidence(
        signal_statuses=signal_statuses,
        age_band="veteran",
        size_band="large",
        operating_years=15.0,
    )
    
    # Veteran should have lower confidence (missing expected advanced signals)
    assert result.confidence_score < 0.90
    assert result.confidence_band in ["Medium", "Low"]
    
    # The missing advanced signals SHOULD count as coverage gaps
    assert "sec_filing" in result.coverage_gaps
    assert "cert_posture" in result.coverage_gaps
    assert "vd_program" in result.coverage_gaps


def test_confidence_calculation_startup_missing_basics():
    """Test that a startup missing BASIC security gets penalized appropriately."""
    
    calculator = ConfidenceCalculator()
    
    # Startup missing basic security (which IS expected)
    signal_statuses = {
        # Always expected - NOT FOUND (should hurt confidence)
        "domain_registration": SignalStatus.NOT_FOUND,
        "tls_version": SignalStatus.NOT_FOUND,
        "cert_validity": SignalStatus.NOT_FOUND,
        "dmarc": SignalStatus.NOT_FOUND,
        "entity_status": SignalStatus.NOT_FOUND,
        
        # Not expected for startup - NOT FOUND (shouldn't hurt confidence)
        "sec_filing": SignalStatus.NOT_FOUND,
        "cert_posture": SignalStatus.NOT_FOUND,
    }
    
    result = calculator.calculate_confidence(
        signal_statuses=signal_statuses,
        age_band="startup",
        size_band="small",
        operating_years=0.5,
    )
    
    # Startup should have very low confidence (missing expected basic signals)
    assert result.confidence_score < 0.50
    assert result.confidence_band == "Low"
    
    # The missing basic signals SHOULD count as coverage gaps
    assert "domain_registration" in result.coverage_gaps
    assert "tls_version" in result.coverage_gaps
    assert "dmarc" in result.coverage_gaps


def test_unexpected_bonus_signals():
    """Test that found-but-not-expected signals don't break the confidence cap."""
    
    calculator = ConfidenceCalculator()
    
    # Startup with unexpected advanced signals (over-performing for age)
    signal_statuses = {
        # Always expected - FOUND
        "domain_registration": SignalStatus.FOUND,
        "tls_version": SignalStatus.FOUND,
        "dmarc": SignalStatus.FOUND,
        "entity_status": SignalStatus.FOUND,
        
        # Not expected for startup - FOUND (bonus, shouldn't break 100% cap)
        "sec_filing": SignalStatus.FOUND,
        "cert_posture": SignalStatus.FOUND,
        "vd_program": SignalStatus.FOUND,
    }
    
    result = calculator.calculate_confidence(
        signal_statuses=signal_statuses,
        age_band="startup",
        size_band="small",
        operating_years=0.5,
    )
    
    # Confidence should still be capped at 100%
    assert result.confidence_score <= 1.0
    assert result.confidence_band == "High"
    
    # The unexpected signals should be tracked as bonuses
    assert "sec_filing" in result.unexpected_bonuses
    assert "cert_posture" in result.unexpected_bonuses
    assert "vd_program" in result.unexpected_bonuses


def test_search_failures_dont_penalize():
    """Test that search failures are tracked separately and don't hurt confidence."""
    
    calculator = ConfidenceCalculator()
    
    signal_statuses = {
        # Always expected - FOUND
        "domain_registration": SignalStatus.FOUND,
        "tls_version": SignalStatus.FOUND,
        "dmarc": SignalStatus.FOUND,
        
        # Search failures (shouldn't hurt confidence)
        "cert_validity": SignalStatus.SEARCH_FAILED,
        "entity_status": SignalStatus.SEARCH_FAILED,
    }
    
    result = calculator.calculate_confidence(
        signal_statuses=signal_statuses,
        age_band="startup",
        size_band="small",
        operating_years=0.5,
    )
    
    # Search failures shouldn't penalize confidence
    assert result.confidence_score >= 0.80
    
    # But they should be tracked
    assert "cert_validity" in result.search_failures
    assert "entity_status" in result.search_failures
    
    # And shouldn't count as coverage gaps
    assert "cert_validity" not in result.coverage_gaps
    assert "entity_status" not in result.coverage_gaps


def test_weighted_confidence_calculation():
    """Test that the confidence calculation properly weights signals."""
    
    calculator = ConfidenceCalculator()
    
    # Small company missing a high-weight signal (domain registration = 15 points)
    signal_statuses = {
        # High-weight signal missing
        "domain_registration": SignalStatus.NOT_FOUND,
        
        # Other expected signals found
        "tls_version": SignalStatus.FOUND,
        "cert_validity": SignalStatus.FOUND,
        "dmarc": SignalStatus.FOUND,
        "entity_status": SignalStatus.FOUND,
    }
    
    result = calculator.calculate_confidence(
        signal_statuses=signal_statuses,
        age_band="startup",
        size_band="small",
        operating_years=0.5,
    )
    
    # Should have reduced confidence due to missing high-weight signal
    assert result.confidence_score < 0.90
    
    # The missing domain registration should be in coverage gaps
    assert "domain_registration" in result.coverage_gaps


def test_confidence_comparison_old_vs_new():
    """Demonstrate the difference between old flat penalty and new age-based approach."""
    
    calculator = ConfidenceCalculator()
    
    # OLD APPROACH: Both companies would get same penalty for missing financial filings
    # NEW APPROACH: Startup not penalized, veteran penalized
    
    # Startup with no financial filings (normal for age)
    startup_result = calculator.calculate_confidence(
        signal_statuses={
            "domain_registration": SignalStatus.FOUND,
            "tls_version": SignalStatus.FOUND,
            "dmarc": SignalStatus.FOUND,
            "sec_filing": SignalStatus.NOT_FOUND,  # Not expected, shouldn't hurt
            "cert_posture": SignalStatus.NOT_FOUND,  # Not expected, shouldn't hurt
        },
        age_band="startup",
        size_band="small",
        operating_years=0.5,
    )
    
    # Veteran with no financial filings (suspicious for age)
    veteran_result = calculator.calculate_confidence(
        signal_statuses={
            "domain_registration": SignalStatus.FOUND,
            "tls_version": SignalStatus.FOUND,
            "dmarc": SignalStatus.FOUND,
            "sec_filing": SignalStatus.NOT_FOUND,  # Expected, should hurt
            "cert_posture": SignalStatus.NOT_FOUND,  # Expected, should hurt
        },
        age_band="veteran",
        size_band="large",
        operating_years=15.0,
    )
    
    # Startup should have higher confidence than veteran
    assert startup_result.confidence_score > veteran_result.confidence_score
    
    # Startup should have no coverage gaps for financial signals
    assert "sec_filing" not in startup_result.coverage_gaps
    assert "cert_posture" not in startup_result.coverage_gaps
    
    # Veteran should have coverage gaps for financial signals
    assert "sec_filing" in veteran_result.coverage_gaps
    assert "cert_posture" in veteran_result.coverage_gaps


def test_jurisdiction_specific_signals():
    """Test that jurisdiction-specific signals are only expected where applicable."""
    
    calculator = ConfidenceCalculator()
    
    # US company - SEC filings expected
    us_company_result = calculator.calculate_confidence(
        signal_statuses={
            "domain_registration": SignalStatus.FOUND,
            "tls_version": SignalStatus.FOUND,
            "sec_filing": SignalStatus.NOT_FOUND,  # Expected for US
        },
        age_band="established",
        size_band="medium",
        operating_years=5.0,
        jurisdiction="US",
    )
    
    # Non-US company - SEC filings not expected
    non_us_company_result = calculator.calculate_confidence(
        signal_statuses={
            "domain_registration": SignalStatus.FOUND,
            "tls_version": SignalStatus.FOUND,
            "sec_filing": SignalStatus.NOT_FOUND,  # Not expected for non-US
        },
        age_band="established",
        size_band="medium",
        operating_years=5.0,
        jurisdiction="UK",
    )
    
    # Non-US company should have higher confidence (SEC not expected)
    assert non_us_company_result.confidence_score > us_company_result.confidence_score
    
    # US company should have SEC in coverage gaps
    assert "sec_filing" in us_company_result.coverage_gaps
    
    # Non-US company should NOT have SEC in coverage gaps
    assert "sec_filing" not in non_us_company_result.coverage_gaps


def test_confidence_result_summary():
    """Test that the confidence result generates a readable summary."""
    
    calculator = ConfidenceCalculator()
    
    result = calculator.calculate_confidence(
        signal_statuses={
            "domain_registration": SignalStatus.FOUND,
            "tls_version": SignalStatus.FOUND,
            "dmarc": SignalStatus.NOT_FOUND,
        },
        age_band="startup",
        size_band="small",
        operating_years=0.5,
    )
    
    summary = result.get_summary()
    
    # Summary should contain key information
    assert "Confidence:" in summary
    assert "Age Band:" in summary
    assert "Expected Signals Weight:" in summary
    assert "Found Expected Weight:" in summary


if __name__ == "__main__":
    # Run a simple demonstration
    print("=== Age-Based Confidence Calculation Demo ===\n")
    
    calculator = ConfidenceCalculator()
    
    # Example 1: Startup with basic security
    print("Example 1: Startup (0.5 years) with basic security")
    startup_result = calculator.calculate_confidence(
        signal_statuses={
            "domain_registration": SignalStatus.FOUND,
            "tls_version": SignalStatus.FOUND,
            "dmarc": SignalStatus.FOUND,
            "sec_filing": SignalStatus.NOT_FOUND,
            "cert_posture": SignalStatus.NOT_FOUND,
        },
        age_band="startup",
        size_band="small",
        operating_years=0.5,
    )
    print(startup_result.get_summary())
    print()
    
    # Example 2: Veteran missing advanced signals
    print("Example 2: Veteran (15 years) missing advanced signals")
    veteran_result = calculator.calculate_confidence(
        signal_statuses={
            "domain_registration": SignalStatus.FOUND,
            "tls_version": SignalStatus.FOUND,
            "dmarc": SignalStatus.FOUND,
            "sec_filing": SignalStatus.NOT_FOUND,
            "cert_posture": SignalStatus.NOT_FOUND,
        },
        age_band="veteran",
        size_band="large",
        operating_years=15.0,
    )
    print(veteran_result.get_summary())
    print()
    
    # Example 3: Startup over-performing
    print("Example 3: Startup (0.5 years) with unexpected certifications")
    overperforming_startup = calculator.calculate_confidence(
        signal_statuses={
            "domain_registration": SignalStatus.FOUND,
            "tls_version": SignalStatus.FOUND,
            "dmarc": SignalStatus.FOUND,
            "sec_filing": SignalStatus.FOUND,  # Unexpected bonus
            "cert_posture": SignalStatus.FOUND,  # Unexpected bonus
        },
        age_band="startup",
        size_band="small",
        operating_years=0.5,
    )
    print(overperforming_startup.get_summary())
    print()
    
    print("=== Key Insight ===")
    print(f"Startup confidence: {startup_result.coverage_percentage:.1f}%")
    print(f"Veteran confidence: {veteran_result.coverage_percentage:.1f}%")
    print(f"Overperforming startup: {overperforming_startup.coverage_percentage:.1f}%")
    print("\nThe veteran is penalized for missing expected signals that the startup isn't expected to have yet.")
    print("The overperforming startup gets bonus signals tracked but doesn't break the 100% cap.")