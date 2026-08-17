"""Validation corpus for Business Stability scoring — Phase 5.4.

Test fixtures for known vendor scenarios to validate scoring logic.
Each fixture represents a real-world scenario with expected outcomes.
"""

from datetime import UTC, datetime

from app.models import (
    FinancialMetrics,
    FinancialProfile,
    InsolvencyRecord,
    InsolvencyStatus,
    ProfileField,
)


# ============================================================================
# FIXTURE 1: Bankrupt Vendor (should BLOCK)
# ============================================================================

def bankrupt_vendor_fixture() -> FinancialProfile:
    """A vendor with active insolvency proceedings.

    Expected outcome: gate_triggered=True, score=None
    Reason: Active liquidation proceedings block Business Stability assessment.
    """
    profile = FinancialProfile(vendor_ref="bankrupt-vendor")
    profile.incorporation_date = ProfileField(
        value="2015-01-01",
        source="companies_house",
        locator="12345678",
        fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    profile.company_status = ProfileField(
        value="liquidation",
        source="companies_house",
        locator="12345678",
        fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    profile.insolvency_records = [
        InsolvencyRecord(
            proceeding_type="liquidation",
            status=InsolvencyStatus.ACTIVE,
            date=datetime(2024, 1, 1, tzinfo=UTC),
            jurisdiction="UK",
            case_number="CASE-2024-001",
            source="companies_house",
        )
    ]
    profile.operating_years = 9.0
    profile.age_band = "established"
    profile.insolvency_gate = True
    profile.insolvency_gate_reason = "Active insolvency proceedings — vendor cannot be assessed"

    return profile


def bankrupt_vendor_expected_outcome() -> dict:
    """Expected outcome for bankrupt vendor."""
    return {
        "gate_triggered": True,
        "score": None,
        "gate_reason": "Active insolvency proceedings — vendor cannot be assessed",
        "age_band": "established",
        "base_score": 90,
    }


# ============================================================================
# FIXTURE 2: 2-Year Startup (should show age penalty)
# ============================================================================

def startup_vendor_fixture() -> FinancialProfile:
    """A 2-year-old startup with no financial distress.

    Expected outcome: score=70-85 (base score for startup), contingency_plan_required=True
    Reason: Young vendors get lower base scores due to higher failure rate.
    """
    profile = FinancialProfile(vendor_ref="startup-vendor")
    profile.incorporation_date = ProfileField(
        value="2022-01-01",
        source="companies_house",
        locator="87654321",
        fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    profile.company_status = ProfileField(
        value="active",
        source="companies_house",
        locator="87654321",
        fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    profile.insolvency_records = []
    profile.operating_years = 2.0
    profile.age_band = "startup"
    profile.insolvency_gate = False
    profile.revenue_trend = "growing"
    profile.cash_flow_trend = "positive"

    return profile


def startup_vendor_expected_outcome() -> dict:
    """Expected outcome for 2-year startup."""
    return {
        "gate_triggered": False,
        "score": 70,  # Base score for startup
        "base_score": 70,
        "age_band": "startup",
        "penalties": [],
        "bonuses": [],
        "confidence_adjusted": 0.76,  # 0.95 - 0.20 (startup adjustment)
        "contingency_plan_required": True,
    }


# ============================================================================
# FIXTURE 3: 40-Year Established Vendor (should show survivorship bonus)
# ============================================================================

def veteran_vendor_fixture() -> FinancialProfile:
    """A 40-year-old established vendor with good financial health.

    Expected outcome: score=100+ (base score + survivorship bonus)
    Reason Veteran companies get survivorship bonus for demonstrated staying power.
    """
    profile = FinancialProfile(vendor_ref="veteran-vendor")
    profile.incorporation_date = ProfileField(
        value="1984-01-01",
        source="companies_house",
        locator="11111111",
        fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    profile.company_status = ProfileField(
        value="active",
        source="companies_house",
        locator="11111111",
        fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    profile.insolvency_records = []
    profile.operating_years = 40.0
    profile.age_band = "veteran"
    profile.insolvency_gate = False
    profile.revenue_trend = "stable"
    profile.cash_flow_trend = "positive"
    profile.debt_to_equity = 0.5

    return profile


def veteran_vendor_expected_outcome() -> dict:
    """Expected outcome for 40-year veteran vendor."""
    return {
        "gate_triggered": False,
        "score": 100,  # Base score for veteran
        "base_score": 100,
        "age_band": "veteran",
        "penalties": [],
        "bonuses": ["survivorship_veteran_20_plus"],
        "confidence_adjusted": 0.95,  # No adjustment for veteran
        "contingency_plan_required": False,
    }


# ============================================================================
# FIXTURE 4: Declining Mature Company (should show financial penalties)
# ============================================================================

def declining_mature_vendor_fixture() -> FinancialProfile:
    """A 15-year-old company with declining revenue and high debt.

    Expected outcome: score reduced by financial penalties
    Reason: Declining revenue and high debt-to-equity ratio indicate financial stress.
    """
    profile = FinancialProfile(vendor_ref="declining-vendor")
    profile.incorporation_date = ProfileField(
        value="2009-01-01",
        source="companies_house",
        locator="22222222",
        fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    profile.company_status = ProfileField(
        value="active",
        source="companies_house",
        locator="22222222",
        fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    profile.insolvency_records = []
    profile.operating_years = 15.0
    profile.age_band = "mature"
    profile.insolvency_gate = False
    profile.revenue_trend = "declining"
    profile.cash_flow_trend = "negative"
    profile.debt_to_equity = 3.5  # High debt-to-equity

    # Add financial metrics showing decline
    profile.financial_metrics = [
        FinancialMetrics(
            period_end=datetime(2024, 3, 31, tzinfo=UTC),
            period_type="quarterly",
            revenue=1000000,
            net_income=-50000,
            total_assets=5000000,
            total_liabilities=4000000,
            long_term_debt=3500000,
            equity=1000000,
            source="sec_xbrl",
        ),
        FinancialMetrics(
            period_end=datetime(2024, 6, 30, tzinfo=UTC),
            period_type="quarterly",
            revenue=900000,
            net_income=-75000,
            total_assets=4900000,
            total_liabilities=4100000,
            long_term_debt=3600000,
            equity=800000,
            source="sec_xbrl",
        ),
        FinancialMetrics(
            period_end=datetime(2024, 9, 30, tzinfo=UTC),
            period_type="quarterly",
            revenue=800000,
            net_income=-100000,
            total_assets=4800000,
            total_liabilities=4200000,
            long_term_debt=3700000,
            equity=600000,
            source="sec_xbrl",
        ),
    ]

    return profile


def declining_mature_vendor_expected_outcome() -> dict:
    """Expected outcome for declining mature vendor."""
    return {
        "gate_triggered": False,
        "score": 80,  # Base 95 - 15 (revenue decline penalty)
        "base_score": 95,
        "age_band": "mature",
        "penalties": ["revenue_decline_3_quarters", "high_debt_to_equity_gt_3", "negative_cash_flow_2_years"],
        "bonuses": ["survivorship_mature_10_plus"],
        "confidence_adjusted": 0.95,
        "contingency_plan_required": False,
    }


# ============================================================================
# FIXTURE 5: Historical Insolvency (should show penalty but not block)
# ============================================================================

def historical_insolvency_vendor_fixture() -> FinancialProfile:
    """A vendor with historical insolvency resolved 5 years ago.

    Expected outcome: score reduced by historical insolvency penalty, but not blocked
    Reason: Historical insolvency is a risk factor but does not gate assessment.
    """
    profile = FinancialProfile(vendor_ref="historical-insolvency-vendor")
    profile.incorporation_date = ProfileField(
        value="2010-01-01",
        source="companies_house",
        locator="33333333",
        fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    profile.company_status = ProfileField(
        value="active",
        source="companies_house",
        locator="33333333",
        fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    profile.insolvency_records = [
        InsolvencyRecord(
            proceeding_type="administration",
            status=InsolvencyStatus.HISTORICAL,
            date=datetime(2018, 1, 1, tzinfo=UTC),  # Resolved 6 years ago
            jurisdiction="UK",
            case_number="CASE-2018-001",
            source="companies_house",
        )
    ]
    profile.operating_years = 14.0
    profile.age_band = "mature"
    profile.insolvency_gate = False
    profile.revenue_trend = "stable"
    profile.cash_flow_trend = "positive"

    return profile


def historical_insolvency_vendor_expected_outcome() -> dict:
    """Expected outcome for vendor with historical insolvency."""
    return {
        "gate_triggered": False,
        "score": 90,  # Base 95 - 5 (historical insolvency penalty)
        "base_score": 95,
        "age_band": "mature",
        "penalties": ["historical_insolvency_old"],
        "bonuses": ["survivorship_mature_10_plus"],
        "confidence_adjusted": 0.95,
        "contingency_plan_required": False,
    }


# ============================================================================
# VALIDATION TESTS
# ============================================================================

VALIDATION_CORPUS = [
    {
        "name": "Bankrupt Vendor",
        "fixture": bankrupt_vendor_fixture,
        "expected": bankrupt_vendor_expected_outcome,
        "description": "Active insolvency should BLOCK assessment",
    },
    {
        "name": "2-Year Startup",
        "fixture": startup_vendor_fixture,
        "expected": startup_vendor_expected_outcome,
        "description": "Young vendor should have lower base score and contingency plan requirement",
    },
    {
        "name": "40-Year Veteran",
        "fixture": veteran_vendor_fixture,
        "expected": veteran_vendor_expected_outcome,
        "description": "Established vendor should have high base score and survivorship bonus",
    },
    {
        "name": "Declining Mature Company",
        "fixture": declining_mature_vendor_fixture,
        "expected": declining_mature_vendor_expected_outcome,
        "description": "Financial distress should apply penalties to mature company",
    },
    {
        "name": "Historical Insolvency",
        "fixture": historical_insolvency_vendor_fixture,
        "expected": historical_insolvency_vendor_expected_outcome,
        "description": "Historical insolvency should apply penalty but not block",
    },
]


def run_validation_corpus() -> dict[str, dict]:
    """Run all validation corpus tests and return results."""
    from app.business_stability import compute_business_stability

    results = {}

    for test_case in VALIDATION_CORPUS:
        profile = test_case["fixture"]()
        expected = test_case["expected"]()

        result = compute_business_stability(profile, 0.95)

        # Validate key fields
        passed = True
        mismatches = []

        if result.get("gate_triggered") != expected["gate_triggered"]:
            passed = False
            mismatches.append(f"gate_triggered: expected {expected['gate_triggered']}, got {result.get('gate_triggered')}")

        if result.get("gate_triggered") is False and result.get("score") != expected["score"]:
            passed = False
            mismatches.append(f"score: expected {expected['score']}, got {result.get('score')}")

        if result.get("age_band") != expected["age_band"]:
            passed = False
            mismatches.append(f"age_band: expected {expected['age_band']}, got {result.get('age_band')}")

        results[test_case["name"]] = {
            "passed": passed,
            "mismatches": mismatches,
            "result": result,
            "expected": expected,
        }

    return results
