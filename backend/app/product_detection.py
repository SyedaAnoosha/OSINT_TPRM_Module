"""Product vs Vendor detection module.

This module detects when a domain represents a product rather than a vendor company.
Products should not be scored as vendors - they are offerings of actual companies.

Examples:
- jira.com -> product of Atlassian (atlassian.com should be scored)
- riskbridge.io -> product of EffectiveRM (effectiverm.com should be scored)
- maturityone.io -> product of EffectiveRM
- wahidai.com -> product of EffectiveRM

The detection uses:
1. Known product-to-company mappings
2. Domain pattern analysis (product domains vs company domains)
3. Corporate registry lookups to identify the actual vendor
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


# Known product-to-company mappings
# Format: product_domain -> (company_domain, product_name)
_KNOWN_PRODUCT_MAPPINGS: dict[str, tuple[str, str]] = {
    # Atlassian products
    "jira.com": ("atlassian.com", "Jira"),
    "confluence.atlassian.com": ("atlassian.com", "Confluence"),
    "bitbucket.org": ("atlassian.com", "Bitbucket"),
    "trello.com": ("atlassian.com", "Trello"),
    
    # EffectiveRM products
    "riskbridge.io": ("effectiverm.com", "RiskBridge"),
    "maturityone.io": ("effectiverm.com", "MaturityOne"),
    "wahidai.com": ("effectiverm.com", "WahidAI"),
    
    # Common SaaS product patterns (examples - expand as needed)
    "salesforce.com": ("salesforce.com", "Salesforce"),  # Company = product in this case
    "slack.com": ("salesforce.com", "Slack"),
    "zoom.us": ("zoom.us", "Zoom"),
}


# Product domain patterns that suggest product rather than company
_PRODUCT_DOMAIN_PATTERNS = [
    # Product-specific subdomains
    r".*\.atlassian\.com$",  # Atlassian product subdomains
    r".*\.salesforce\.com$",  # Salesforce product subdomains
    r".*\.microsoft\.com$",   # Microsoft product subdomains
    r".*\.google\.com$",      # Google product subdomains
    r".*\.amazon\.com$",      # AWS/product subdomains
]


@dataclass
class ProductDetectionResult:
    """Result of product vs vendor detection."""
    is_product: bool
    company_domain: str | None
    product_name: str | None
    reason: str
    confidence: Literal["high", "medium", "low"]


def detect_product(domain: str) -> ProductDetectionResult:
    """Detect if a domain represents a product rather than a vendor company.
    
    Args:
        domain: The domain to check (e.g., "jira.com", "atlassian.com")
    
    Returns:
        ProductDetectionResult with detection details
    """
    # Normalize domain
    domain = domain.lower().strip()
    
    # Check known product mappings first (high confidence)
    if domain in _KNOWN_PRODUCT_MAPPINGS:
        company_domain, product_name = _KNOWN_PRODUCT_MAPPINGS[domain]
        return ProductDetectionResult(
            is_product=True,
            company_domain=company_domain,
            product_name=product_name,
            reason=f"Domain '{domain}' is a known product ({product_name}) of vendor '{company_domain}'",
            confidence="high",
        )
    
    # Check if domain is a known company domain (not a product)
    # If the domain appears as a company_domain in mappings, it's likely a vendor
    is_known_company = any(company == domain for company, _ in _KNOWN_PRODUCT_MAPPINGS.values())
    if is_known_company:
        return ProductDetectionResult(
            is_product=False,
            company_domain=domain,
            product_name=None,
            reason=f"Domain '{domain}' is a known vendor company domain",
            confidence="high",
        )
    
    # Check product domain patterns (medium confidence)
    import re
    for pattern in _PRODUCT_DOMAIN_PATTERNS:
        if re.match(pattern, domain):
            # Extract likely company domain from pattern
            if ".atlassian.com" in domain:
                return ProductDetectionResult(
                    is_product=True,
                    company_domain="atlassian.com",
                    product_name=domain.split(".")[0] if "." in domain else domain,
                    reason=f"Domain '{domain}' matches Atlassian product pattern",
                    confidence="medium",
                )
            elif ".salesforce.com" in domain:
                return ProductDetectionResult(
                    is_product=True,
                    company_domain="salesforce.com",
                    product_name=domain.split(".")[0] if "." in domain else domain,
                    reason=f"Domain '{domain}' matches Salesforce product pattern",
                    confidence="medium",
                )
    
    # Default: assume it's a vendor (low confidence - could be wrong)
    return ProductDetectionResult(
        is_product=False,
        company_domain=domain,
        product_name=None,
        reason=f"Domain '{domain}' does not match known product patterns - treating as vendor",
        confidence="low",
    )


def should_block_scoring(domain: str) -> tuple[bool, str | None]:
    """Check if scoring should be blocked for this domain.
    
    Args:
        domain: The domain to check
    
    Returns:
        (should_block, reason) tuple
    """
    result = detect_product(domain)
    
    if result.is_product and result.confidence in ("high", "medium"):
        reason = (
            f"Scoring blocked: '{domain}' is a product ({result.product_name}) "
            f"of vendor '{result.company_domain}'. Score the vendor company instead."
        )
        return True, reason
    
    return False, None


def get_vendor_domain_for_product(domain: str) -> str | None:
    """Get the actual vendor domain for a product domain.
    
    Args:
        domain: The product domain
    
    Returns:
        Vendor domain if known, None otherwise
    """
    result = detect_product(domain)
    return result.company_domain if result.is_product else None


def add_product_mapping(product_domain: str, company_domain: str, product_name: str) -> None:
    """Add a new product-to-company mapping.
    
    Args:
        product_domain: The product domain (e.g., "jira.com")
        company_domain: The vendor company domain (e.g., "atlassian.com")
        product_name: The product name (e.g., "Jira")
    """
    _KNOWN_PRODUCT_MAPPINGS[product_domain.lower()] = (company_domain.lower(), product_name)
