"""Standalone demonstration of age-based confidence calculation.

This script demonstrates the new (expected & found) / expected methodology
without requiring full module imports.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Literal


class SignalStatus(Enum):
    """The status of a signal collection attempt."""
    FOUND = "found"
    NOT_FOUND = "not_found"
    SEARCH_FAILED = "search_failed"
    NOT_APPLICABLE = "not_applicable"


class AgeBand:
    STARTUP = "startup"      # < 2 years
    YOUNG = "young"          # 2-5 years
    ESTABLISHED = "established"  # 5-10 years
    MATURE = "mature"        # 10-20 years
    VETERAN = "veteran"      # 20+ years


class SizeBand:
    MICRO = "micro"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    ENTERPRISE = "enterprise"


    # Simplified signal categories for demonstration
SIGNAL_CATEGORIES = {
    # ALWAYS EXPECTED (Day 1, regardless of age/size)
    "domain_registration": {"weight": 15.0, "always_expected": True, "deduction_label": "Domain registration not found", "deduction_category": "infrastructure"},
    "tls_version": {"weight": 10.0, "always_expected": True, "deduction_label": "TLS security not configured", "deduction_category": "security_controls"},
    "cert_validity": {"weight": 12.0, "always_expected": True, "deduction_label": "SSL certificate issues detected", "deduction_category": "security_controls"},
    "dmarc": {"weight": 12.0, "always_expected": True, "deduction_label": "DMARC email authentication missing", "deduction_category": "email_security"},
    "entity_status": {"weight": 15.0, "always_expected": True, "deduction_label": "Company registration not found", "deduction_category": "legal_compliance"},
    
    # SCALES WITH AGE/SIZE
    "sec_filing": {"weight": 20.0, "always_expected": False, "min_age_years": 2.0, "deduction_label": "SEC regulatory filings missing", "deduction_category": "financial_transparency"},
    "cert_posture": {"weight": 15.0, "always_expected": False, "min_age_years": 3.0, "deduction_label": "Security certifications missing", "deduction_category": "assurance"},
    "vd_program": {"weight": 12.0, "always_expected": False, "min_age_years": 2.0, "deduction_label": "Vulnerability disclosure program missing", "deduction_category": "transparency"},
    "regulator_action": {"weight": 20.0, "always_expected": False, "min_age_years": 2.0, "deduction_label": "Regulatory compliance status unknown", "deduction_category": "compliance"},
}


def is_signal_expected(signal_name: str, age_band: str, operating_years: float | None = None) -> bool:
    """Determine if a signal is expected given the company's profile."""
    category = SIGNAL_CATEGORIES.get(signal_name)
    if not category:
        return False
    
    # Always expected signals are always expected
    if category["always_expected"]:
        return True
    
    # Check age requirement
    min_age = category.get("min_age_years")
    if min_age is not None:
        if operating_years is not None:
            if operating_years < min_age:
                return False
        else:
            # Fall back to age band check
            age_thresholds = {
                AgeBand.STARTUP: 0,
                AgeBand.YOUNG: 2,
                AgeBand.ESTABLISHED: 5,
                AgeBand.MATURE: 10,
                AgeBand.VETERAN: 20,
            }
            if age_thresholds.get(age_band, 0) < min_age:
                return False
    
    return True


def calculate_confidence(
    signal_statuses: dict[str, SignalStatus],
    age_band: str,
    operating_years: float | None = None,
) -> dict:
    """Calculate confidence using the (expected & found) / expected methodology."""
    
    # Determine expected signals and their total weight
    expected_signals = []
    total_expected_weight = 0.0
    
    for signal_name in SIGNAL_CATEGORIES:
        if is_signal_expected(signal_name, age_band, operating_years):
            expected_signals.append(signal_name)
            total_expected_weight += SIGNAL_CATEGORIES[signal_name]["weight"]
    
    # Calculate found expected weight
    found_expected_weight = 0.0
    coverage_gaps = []
    unexpected_bonuses = []
    deduction_labels = []
    deductions_by_category = {}
    
    for signal_name, status in signal_statuses.items():
        category = SIGNAL_CATEGORIES.get(signal_name)
        if not category:
            continue
        
        is_expected = is_signal_expected(signal_name, age_band, operating_years)
        
        if status == SignalStatus.FOUND:
            if is_expected:
                found_expected_weight += category["weight"]
            else:
                unexpected_bonuses.append(signal_name)
        
        elif status == SignalStatus.NOT_FOUND:
            if is_expected:
                coverage_gaps.append(signal_name)
                
                # Add human-readable deduction label
                deduction_info = {
                    "signal": signal_name,
                    "label": category["deduction_label"],
                    "category": category["deduction_category"],
                    "weight": category["weight"],
                    "reason": f"Expected for {age_band} companies but not found"
                }
                deduction_labels.append(deduction_info)
                
                # Group by category
                cat = category["deduction_category"]
                if cat not in deductions_by_category:
                    deductions_by_category[cat] = []
                deductions_by_category[cat].append(deduction_info)
    
    # Calculate confidence score
    if total_expected_weight > 0:
        confidence_score = found_expected_weight / total_expected_weight
    else:
        confidence_score = 1.0
    
    # Cap at 1.0
    confidence_score = min(1.0, confidence_score)
    
    # Determine confidence band
    if confidence_score >= 0.90:
        confidence_band = "High"
    elif confidence_score >= 0.70:
        confidence_band = "Medium"
    else:
        confidence_band = "Low"
    
    return {
        "confidence_score": confidence_score,
        "confidence_band": confidence_band,
        "confidence_percentage": confidence_score * 100,
        "total_expected_weight": total_expected_weight,
        "found_expected_weight": found_expected_weight,
        "coverage_gaps": coverage_gaps,
        "unexpected_bonuses": unexpected_bonuses,
        "deduction_labels": deduction_labels,
        "deductions_by_category": deductions_by_category,
    }


def main():
    """Demonstrate the age-based confidence calculation with examples."""
    
    print("=" * 70)
    print("AGE-BASED CONFIDENCE CALCULATION DEMONSTRATION")
    print("=" * 70)
    print()
    
    # Example 1: Startup with basic security but no advanced signals
    print("Example 1: Startup (0.5 years) with basic security")
    print("-" * 70)
    
    startup_signals = {
        "domain_registration": SignalStatus.FOUND,
        "tls_version": SignalStatus.FOUND,
        "cert_validity": SignalStatus.FOUND,
        "dmarc": SignalStatus.FOUND,
        "entity_status": SignalStatus.FOUND,
        "sec_filing": SignalStatus.NOT_FOUND,  # Not expected for startup
        "cert_posture": SignalStatus.NOT_FOUND,  # Not expected for startup
        "vd_program": SignalStatus.NOT_FOUND,  # Not expected for startup
    }
    
    startup_result = calculate_confidence(
        signal_statuses=startup_signals,
        age_band=AgeBand.STARTUP,
        operating_years=0.5,
    )
    
    print(f"Confidence: {startup_result['confidence_percentage']:.1f}% ({startup_result['confidence_band']})")
    print(f"Expected weight: {startup_result['total_expected_weight']:.1f}")
    print(f"Found weight: {startup_result['found_expected_weight']:.1f}")
    print(f"Coverage gaps: {startup_result['coverage_gaps']}")
    print(f"Unexpected bonuses: {startup_result['unexpected_bonuses']}")
    
    if startup_result['deduction_labels']:
        print("Confidence Deductions:")
        for deduction in startup_result['deduction_labels']:
            print(f"  - {deduction['label']} ({deduction['category']}, -{deduction['weight']:.1f} points)")
    print()
    
    # Example 2: Veteran company missing advanced signals
    print("Example 2: Veteran (15 years) missing advanced signals")
    print("-" * 70)
    
    veteran_signals = {
        "domain_registration": SignalStatus.FOUND,
        "tls_version": SignalStatus.FOUND,
        "cert_validity": SignalStatus.FOUND,
        "dmarc": SignalStatus.FOUND,
        "entity_status": SignalStatus.FOUND,
        "sec_filing": SignalStatus.NOT_FOUND,  # Expected for veteran
        "cert_posture": SignalStatus.NOT_FOUND,  # Expected for veteran
        "vd_program": SignalStatus.NOT_FOUND,  # Expected for veteran
    }
    
    veteran_result = calculate_confidence(
        signal_statuses=veteran_signals,
        age_band=AgeBand.VETERAN,
        operating_years=15.0,
    )
    
    print(f"Confidence: {veteran_result['confidence_percentage']:.1f}% ({veteran_result['confidence_band']})")
    print(f"Expected weight: {veteran_result['total_expected_weight']:.1f}")
    print(f"Found weight: {veteran_result['found_expected_weight']:.1f}")
    print(f"Coverage gaps: {veteran_result['coverage_gaps']}")
    print(f"Unexpected bonuses: {veteran_result['unexpected_bonuses']}")
    
    if veteran_result['deduction_labels']:
        print("Confidence Deductions:")
        for deduction in veteran_result['deduction_labels']:
            print(f"  - {deduction['label']} ({deduction['category']}, -{deduction['weight']:.1f} points)")
    print()
    
    # Example 3: Startup over-performing (has unexpected advanced signals)
    print("Example 3: Startup (0.5 years) with unexpected certifications")
    print("-" * 70)
    
    overperforming_signals = {
        "domain_registration": SignalStatus.FOUND,
        "tls_version": SignalStatus.FOUND,
        "cert_validity": SignalStatus.FOUND,
        "dmarc": SignalStatus.FOUND,
        "entity_status": SignalStatus.FOUND,
        "sec_filing": SignalStatus.FOUND,  # Unexpected bonus
        "cert_posture": SignalStatus.FOUND,  # Unexpected bonus
        "vd_program": SignalStatus.FOUND,  # Unexpected bonus
    }
    
    overperforming_result = calculate_confidence(
        signal_statuses=overperforming_signals,
        age_band=AgeBand.STARTUP,
        operating_years=0.5,
    )
    
    print(f"Confidence: {overperforming_result['confidence_percentage']:.1f}% ({overperforming_result['confidence_band']})")
    print(f"Expected weight: {overperforming_result['total_expected_weight']:.1f}")
    print(f"Found weight: {overperforming_result['found_expected_weight']:.1f}")
    print(f"Coverage gaps: {overperforming_result['coverage_gaps']}")
    print(f"Unexpected bonuses: {overperforming_result['unexpected_bonuses']}")
    
    if overperforming_result['deduction_labels']:
        print("Confidence Deductions:")
        for deduction in overperforming_result['deduction_labels']:
            print(f"  - {deduction['label']} ({deduction['category']}, -{deduction['weight']:.1f} points)")
    print()
    
    # Example 4: Startup missing basic security
    print("Example 4: Startup (0.5 years) missing basic security")
    print("-" * 70)
    
    startup_missing_basics = {
        "domain_registration": SignalStatus.NOT_FOUND,  # Expected
        "tls_version": SignalStatus.NOT_FOUND,  # Expected
        "cert_validity": SignalStatus.NOT_FOUND,  # Expected
        "dmarc": SignalStatus.NOT_FOUND,  # Expected
        "entity_status": SignalStatus.NOT_FOUND,  # Expected
        "sec_filing": SignalStatus.NOT_FOUND,  # Not expected
        "cert_posture": SignalStatus.NOT_FOUND,  # Not expected
    }
    
    missing_basics_result = calculate_confidence(
        signal_statuses=startup_missing_basics,
        age_band=AgeBand.STARTUP,
        operating_years=0.5,
    )
    
    print(f"Confidence: {missing_basics_result['confidence_percentage']:.1f}% ({missing_basics_result['confidence_band']})")
    print(f"Expected weight: {missing_basics_result['total_expected_weight']:.1f}")
    print(f"Found weight: {missing_basics_result['found_expected_weight']:.1f}")
    print(f"Coverage gaps: {missing_basics_result['coverage_gaps']}")
    
    if missing_basics_result['deduction_labels']:
        print("Confidence Deductions:")
        for deduction in missing_basics_result['deduction_labels']:
            print(f"  - {deduction['label']} ({deduction['category']}, -{deduction['weight']:.1f} points)")
    print()
    
    # Key insight comparison
    print("=" * 70)
    print("KEY INSIGHT: COMPARISON")
    print("=" * 70)
    print()
    print(f"Startup (normal for age): {startup_result['confidence_percentage']:.1f}%")
    print(f"Veteran (suspicious for age): {veteran_result['confidence_percentage']:.1f}%")
    print(f"Startup (over-performing): {overperforming_result['confidence_percentage']:.1f}%")
    print(f"Startup (missing basics): {missing_basics_result['confidence_percentage']:.1f}%")
    print()
    print("OLD APPROACH: Startup and Veteran would get same penalty for missing financial filings")
    print("NEW APPROACH: Startup not penalized (not expected), Veteran penalized (expected)")
    print()
    print("The veteran is penalized for missing expected signals that the startup isn't")
    print("expected to have yet. The overperforming startup gets bonus signals tracked but")
    print("doesn't break the 100% cap. The startup missing basics is severely penalized")
    print("because those ARE expected for any company, regardless of age.")
    print()
    print("=" * 70)
    print("CONFIDENCE DEDUCTION LABELS")
    print("=" * 70)
    print()
    print("Each confidence deduction now has a clear, human-readable label explaining")
    print("why confidence was reduced. These are grouped by category for better understanding:")
    print()
    
    # Show deductions by category for veteran example
    if veteran_result['deductions_by_category']:
        print("Veteran Company Deductions by Category:")
        for category, deductions in veteran_result['deductions_by_category'].items():
            print(f"\n{category.upper()}:")
            for deduction in deductions:
                print(f"  - {deduction['label']} (-{deduction['weight']:.1f} points)")
    print()
    print("This makes it immediately clear to users exactly which missing signals")
    print("are reducing confidence and why, without requiring them to understand")
    print("the underlying scoring methodology.")


if __name__ == "__main__":
    main()