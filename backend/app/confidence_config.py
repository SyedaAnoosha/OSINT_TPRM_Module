"""Age-based confidence configuration - what evidence we expect based on company profile.

This module implements the methodology where confidence = (expected & found) / expected
rather than (found) / (all possible). The key insight is that different signals are
"expected" at different company ages and sizes.

A 2-month-old startup should NOT be expected to have the same evidence footprint as a
15-year-old company. This configuration defines what's reasonable to expect at each stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AgeBand = Literal["startup", "young", "established", "mature", "veteran", "unknown"]
SizeBand = Literal["micro", "small", "medium", "large", "enterprise", "unknown"]


@dataclass(frozen=True)
class SignalCategory:
    """A signal category with its properties for confidence calculation."""
    
    name: str
    description: str
    weight: float  # Importance weight (0-100 scale)
    always_expected: bool  # True = expected from day 1, False = scales with age/size
    min_age_years: float | None = None  # Minimum age before this signal is expected
    min_size: SizeBand | None = None  # Minimum size before this signal is expected
    jurisdiction_required: bool = False  # Whether this only applies in certain jurisdictions
    deduction_label: str = ""  # Human-readable label for confidence deduction
    deduction_category: str = "general"  # Category of deduction for grouping


# Signal categorization based on your existing scoring.yaml structure
SIGNAL_CATEGORIES: dict[str, SignalCategory] = {
    # === ALWAYS EXPECTED (Day 1, regardless of age/size) ===
    
    # Domain/WHOIS - fundamental infrastructure
    "domain_registration": SignalCategory(
        name="domain_registration",
        description="Domain registration age and status",
        weight=15.0,
        always_expected=True,
        deduction_label="Domain registration not found",
        deduction_category="infrastructure",
    ),
    
    # Security posture - technical controls that can be implemented immediately
    "tls_version": SignalCategory(
        name="tls_version",
        description="TLS version configuration",
        weight=10.0,
        always_expected=True,
        deduction_label="TLS security not configured",
        deduction_category="security_controls",
    ),
    "cert_validity": SignalCategory(
        name="cert_validity", 
        description="SSL certificate validity",
        weight=12.0,
        always_expected=True,
        deduction_label="SSL certificate issues detected",
        deduction_category="security_controls",
    ),
    "hsts": SignalCategory(
        name="hsts",
        description="HTTP Strict Transport Security",
        weight=5.0,
        always_expected=True,
        deduction_label="HSTS security header missing",
        deduction_category="security_controls",
    ),
    "csp": SignalCategory(
        name="csp",
        description="Content Security Policy",
        weight=5.0,
        always_expected=True,
        deduction_label="CSP security header missing",
        deduction_category="security_controls",
    ),
    "x_frame_opts": SignalCategory(
        name="x_frame_opts",
        description="X-Frame-Options header",
        weight=3.0,
        always_expected=True,
        deduction_label="X-Frame-Options header missing",
        deduction_category="security_controls",
    ),
    "dnssec": SignalCategory(
        name="dnssec",
        description="DNSSEC configuration",
        weight=5.0,
        always_expected=True,
        deduction_label="DNSSEC not configured",
        deduction_category="security_controls",
    ),
    "caa": SignalCategory(
        name="caa",
        description="CAA records",
        weight=3.0,
        always_expected=True,
        deduction_label="CAA records not configured",
        deduction_category="security_controls",
    ),
    
    # Identity & Email - fundamental communication security
    "dmarc": SignalCategory(
        name="dmarc",
        description="DMARC email authentication",
        weight=12.0,
        always_expected=True,
        deduction_label="DMARC email authentication missing",
        deduction_category="email_security",
    ),
    "spf": SignalCategory(
        name="spf",
        description="SPF email authentication",
        weight=8.0,
        always_expected=True,
        deduction_label="SPF email authentication missing",
        deduction_category="email_security",
    ),
    "dkim": SignalCategory(
        name="dkim",
        description="DKIM email authentication",
        weight=5.0,
        always_expected=True,
        deduction_label="DKIM email authentication missing",
        deduction_category="email_security",
    ),
    
    # Entity registration - basic legal existence
    "entity_status": SignalCategory(
        name="entity_status",
        description="Company registration status",
        weight=15.0,
        always_expected=True,
        deduction_label="Company registration not found",
        deduction_category="legal_compliance",
    ),
    "entity_existence": SignalCategory(
        name="entity_existence",
        description="Entity existence confirmation",
        weight=10.0,
        always_expected=True,
        deduction_label="Entity existence not confirmed",
        deduction_category="legal_compliance",
    ),
    
    # === SCALES WITH AGE/SIZE (Only expected after sufficient maturity) ===
    
    # Financial filings - require time and often jurisdiction
    "sec_filing": SignalCategory(
        name="sec_filing",
        description="SEC regulatory filings",
        weight=20.0,
        always_expected=False,
        min_age_years=2.0,
        min_size="medium",
        jurisdiction_required=True,  # Only US SEC registrants
        deduction_label="SEC regulatory filings missing",
        deduction_category="financial_transparency",
    ),
    "insolvency_notice": SignalCategory(
        name="insolvency_notice",
        description="Insolvency proceedings notices",
        weight=15.0,
        always_expected=False,
        min_age_years=1.0,
        deduction_label="Insolvency notices not found",
        deduction_category="financial_transparency",
    ),
    "bankruptcy_petition": SignalCategory(
        name="bankruptcy_petition",
        description="Bankruptcy petitions",
        weight=15.0,
        always_expected=False,
        min_age_years=1.0,
        deduction_label="Bankruptcy records not found",
        deduction_category="financial_transparency",
    ),
    
    # Assurance & Certifications - require maturity and resources
    "cert_posture": SignalCategory(
        name="cert_posture",
        description="Security certifications (ISO 27001, SOC 2, etc.)",
        weight=15.0,
        always_expected=False,
        min_age_years=3.0,
        min_size="small",
        deduction_label="Security certifications missing",
        deduction_category="assurance",
    ),
    "regulator_action": SignalCategory(
        name="regulator_action",
        description="Regulatory enforcement actions",
        weight=20.0,
        always_expected=False,
        min_age_years=2.0,
        deduction_label="Regulatory compliance status unknown",
        deduction_category="compliance",
    ),
    
    # Transparency - requires maturity and security program maturity
    "vd_program": SignalCategory(
        name="vd_program",
        description="Vulnerability disclosure program",
        weight=12.0,
        always_expected=False,
        min_age_years=2.0,
        min_size="small",
        deduction_label="Vulnerability disclosure program missing",
        deduction_category="transparency",
    ),
    "security_txt": SignalCategory(
        name="security_txt",
        description="Security.txt disclosure",
        weight=5.0,
        always_expected=False,
        min_age_years=1.0,
        deduction_label="Security.txt disclosure missing",
        deduction_category="transparency",
    ),
    
    # Assurance programs - require organizational maturity
    "program_disclosure": SignalCategory(
        name="program_disclosure",
        description="Security program documentation",
        weight=10.0,
        always_expected=False,
        min_age_years=2.0,
        min_size="small",
        deduction_label="Security program documentation missing",
        deduction_category="assurance",
    ),
    "contactability": SignalCategory(
        name="contactability",
        description="Security contact accessibility",
        weight=8.0,
        always_expected=False,
        min_age_years=1.0,
        deduction_label="Security contact information missing",
        deduction_category="transparency",
    ),
    "reporting_posture": SignalCategory(
        name="reporting_posture",
        description="Security reporting practices",
        weight=8.0,
        always_expected=False,
        min_age_years=2.0,
        min_size="small",
        deduction_label="Security reporting practices missing",
        deduction_category="transparency",
    ),
    
    # Estate management - scales with company size
    "subdomain_estate": SignalCategory(
        name="subdomain_estate",
        description="Subdomain estate management",
        weight=8.0,
        always_expected=False,
        min_size="medium",
        deduction_label="Subdomain estate management not assessed",
        deduction_category="estate_management",
    ),
    "stale_hosts": SignalCategory(
        name="stale_hosts",
        description="Stale host management",
        weight=10.0,
        always_expected=False,
        min_size="medium",
        deduction_label="Stale host management issues detected",
        deduction_category="estate_management",
    ),
    "weak_issuance": SignalCategory(
        name="weak_issuance",
        description="Certificate issuance practices",
        weight=8.0,
        always_expected=False,
        min_size="small",
        deduction_label="Certificate issuance practices weak",
        deduction_category="estate_management",
    ),
    "estate_tls_legacy": SignalCategory(
        name="estate_tls_legacy",
        description="Estate-wide TLS legacy support",
        weight=10.0,
        always_expected=False,
        min_size="medium",
        deduction_label="Estate TLS legacy issues detected",
        deduction_category="estate_management",
    ),
    "estate_cert_expired": SignalCategory(
        name="estate_cert_expired",
        description="Estate-wide certificate expiry",
        weight=10.0,
        always_expected=False,
        min_size="medium",
        deduction_label="Estate certificate expiry issues detected",
        deduction_category="estate_management",
    ),
    
    # Breach history - accumulates over time
    "breach_by_data_class": SignalCategory(
        name="breach_by_data_class",
        description="Data breach history",
        weight=15.0,
        always_expected=False,
        min_age_years=2.0,
        deduction_label="Breach history not found",
        deduction_category="incident_history",
    ),
    "kev_listed_cve": SignalCategory(
        name="kev_listed_cve",
        description="Known exploited vulnerabilities",
        weight=15.0,
        always_expected=False,
        min_age_years=1.0,
        deduction_label="Known exploited vulnerabilities not found",
        deduction_category="incident_history",
    ),
    "nvd_cve": SignalCategory(
        name="nvd_cve",
        description="NVD CVE history",
        weight=10.0,
        always_expected=False,
        min_age_years=1.0,
        deduction_label="CVE history not found",
        deduction_category="incident_history",
    ),
}


def is_signal_expected(
    signal_name: str,
    age_band: AgeBand,
    size_band: SizeBand = "unknown",
    operating_years: float | None = None,
    jurisdiction: str | None = None,
) -> bool:
    """Determine if a signal is expected given the company's profile.
    
    Args:
        signal_name: The signal to check
        age_band: Company's age band
        size_band: Company's size band
        operating_years: Actual operating years (if available)
        jurisdiction: Company's jurisdiction (for jurisdiction-specific signals)
    
    Returns:
        True if this signal should be expected for this company profile
    """
    category = SIGNAL_CATEGORIES.get(signal_name)
    if not category:
        return False  # Unknown signals are not expected
    
    # Always expected signals are always expected
    if category.always_expected:
        return True
    
    # Check age requirement
    if category.min_age_years is not None:
        if operating_years is not None:
            if operating_years < category.min_age_years:
                return False
        else:
            # Fall back to age band check
            age_thresholds = {
                "startup": 0,    # < 2 years
                "young": 2,      # 2-5 years  
                "established": 5, # 5-10 years
                "mature": 10,    # 10-20 years
                "veteran": 20,   # 20+ years
            }
            if age_thresholds.get(age_band, 0) < category.min_age_years:
                return False
    
    # Check size requirement
    if category.min_size is not None and category.min_size != "unknown":
        size_order = ["micro", "small", "medium", "large", "enterprise"]
        try:
            current_idx = size_order.index(size_band) if size_band in size_order else 0
            min_idx = size_order.index(category.min_size)
            if current_idx < min_idx:
                return False
        except ValueError:
            pass  # Invalid size band, assume not expected
    
    # Check jurisdiction requirement
    if category.jurisdiction_required and jurisdiction:
        # This is a simplified check - in practice you'd have a mapping of
        # which jurisdictions require which filings
        us_jurisdictions = ["US", "USA", "United States"]
        if signal_name == "sec_filing" and jurisdiction not in us_jurisdictions:
            return False
    
    return True


def get_expected_signals(
    age_band: AgeBand,
    size_band: SizeBand = "unknown", 
    operating_years: float | None = None,
    jurisdiction: str | None = None,
) -> list[str]:
    """Get all signals that are expected for a given company profile.
    
    Args:
        age_band: Company's age band
        size_band: Company's size band
        operating_years: Actual operating years (if available)
        jurisdiction: Company's jurisdiction
    
    Returns:
        List of signal names that should be expected for this profile
    """
    expected = []
    for signal_name in SIGNAL_CATEGORIES:
        if is_signal_expected(signal_name, age_band, size_band, operating_years, jurisdiction):
            expected.append(signal_name)
    return expected


def get_total_expected_weight(
    age_band: AgeBand,
    size_band: SizeBand = "unknown",
    operating_years: float | None = None,
    jurisdiction: str | None = None,
) -> float:
    """Get the total weight of all expected signals for a given profile.
    
    This is the denominator for confidence calculation.
    """
    expected_signals = get_expected_signals(age_band, size_band, operating_years, jurisdiction)
    return sum(SIGNAL_CATEGORIES[signal].weight for signal in expected_signals)


def size_band_from_profile(size_band: str | None) -> SizeBand:
    """Convert profile size band to confidence config size band."""
    if size_band is None:
        return "unknown"
    size_mapping = {
        "micro": "micro",
        "small": "small", 
        "medium": "medium",
        "large": "large",
        "enterprise": "enterprise",
    }
    return size_mapping.get(size_band.lower(), "unknown")
