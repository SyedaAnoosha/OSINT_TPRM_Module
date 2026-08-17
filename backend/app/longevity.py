"""Age-based modifiers for vendor risk assessment.

This module implements the longevity scoring logic — how a vendor's age affects
its Business Stability score and confidence adjustments. The core principle:

- Young vendors (<2 years) have higher failure rates (3× established businesses)
- Age is CONTEXT, not a direct penalty — it affects confidence and base scores
- Survivorship bonus rewards vendors that have demonstrated staying power

The methodology deliberately separates age effects from cybersecurity posture:
a 2-year-old startup can have excellent security, and a 40-year-old company
can have poor controls. Age affects BUSINESS STABILITY only.

Reference: research on "liability of newness" (Stinchcombe, 1965) and vendor
risk assessment best practices.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from .models import FinancialProfile


AgeBand = Literal["startup", "young", "established", "mature", "veteran", "unknown"]


def _bs_table(key: str, fallback: dict[str, float]) -> dict[str, float]:
    """One table from `scoring.yaml`'s `business_stability:` block, with a code fallback.

    THE MODEL FILE IS THE MODEL. These numbers were previously hard-coded here as well as being
    declared in `scoring.yaml`, and the two had drifted apart — `age_base_scores.startup` read 70
    in the model file and 50 in this module, and `confidence_adjustments.startup` read -0.15 there
    and -0.60 here. Whichever a reader consulted, the other was quietly doing the work. That defeats
    the point of having a model file a non-engineer can read and defend: a value they can change
    and see take effect is the whole contract.

    The fallback keeps this module importable against a minimal config (the unit-test fixtures
    declare no `business_stability:` block at all) without letting the fallback become a second
    source of truth for the real one — on the shipped model file the config always wins.
    """
    try:
        from .scoring_config import get_scoring_config
        table = (get_scoring_config().data.get("business_stability") or {}).get(key)
    except Exception:  # noqa: BLE001 — a config read must never break a stability lookup
        table = None
    return {**fallback, **table} if isinstance(table, dict) else dict(fallback)


def operating_years(incorporation_date: datetime | None) -> float | None:
    """Calculate years since incorporation.

    Returns None if incorporation_date is not available.
    """
    if incorporation_date is None:
        return None
    now = datetime.now(UTC)
    if incorporation_date.tzinfo is None:
        incorporation_date = incorporation_date.replace(tzinfo=UTC)
    return (now - incorporation_date).days / 365.25


def age_band_from_years(years: float | None) -> AgeBand:
    """Determine age band from operating years.

    Bands:
    - startup: < 2 years (highest risk, 3× failure rate)
    - young: 2-5 years (moderate risk)
    - established: 5-10 years (lower risk)
    - mature: 10-20 years (low risk)
    - veteran: 20+ years (lowest risk, survivorship bonus)
    - unknown: age not determinable
    """
    if years is None:
        return "unknown"
    if years < 2:
        return "startup"
    if years < 5:
        return "young"
    if years < 10:
        return "established"
    if years < 20:
        return "mature"
    return "veteran"


def base_age_score(age_band: AgeBand) -> int:
    """Base Business Stability score by age band.

    Age is a significant context factor. The majority of the Business Stability
    score should come from actual financial evidence, but the base spread must
    be wide enough to meaningfully differentiate a 2-year-old startup from a
    25-year-old veteran.

    Similar to confidence scoring, young companies should naturally have lower
    Business Stability scores because:
    - Higher baseline risk of failure
    - Less financial history to evaluate
    - Less proven business model
    - Less track record for financial stability

    THE NUMBERS LIVE IN `scoring.yaml` (`business_stability.age_base_scores`), not here — the
    values below are the fallback for a config that declares no such block, and are what this
    module used to hard-code. Read the model file for what is actually in force.

    Fallback scores (wide spread to reflect real-world failure rates):
    - startup: 50 (very high risk - 50% fail within 2 years)
    - young: 65 (high risk - still establishing market position)
    - established: 80 (moderate risk - proven business model)
    - mature: 90 (lower risk - demonstrated staying power)
    - veteran: 100 (maximum survivorship credit)
    - unknown: 60 (assume elevated risk when age unknown)
    """
    base_scores = _bs_table("age_base_scores", {
        "startup": 50, "young": 65, "established": 80,
        "mature": 90, "veteran": 100, "unknown": 60,
    })
    return int(base_scores.get(age_band, base_scores.get("unknown", 85)))


def confidence_adjustment(age_band: AgeBand) -> float:
    """Confidence score adjustment by age band.

    Young vendors get a confidence penalty because their limited track record
    means we have less evidence of their stability. This is a COVERAGE adjustment,
    not a risk penalty — it reflects uncertainty, not poor performance.

    THE NUMBERS LIVE IN `scoring.yaml` (`business_stability.confidence_adjustments`). Below is the
    fallback only.

    Fallback adjustments (subtracted from confidence):
    - startup: -0.60 (60% reduction)
    - young: -0.50 (50% reduction)
    - established: 0.00 (no adjustment)
    - mature: 0.00 (no adjustment)
    - veteran: 0.00 (no adjustment)
    - unknown: -0.05 (5% reduction for uncertainty)
    """
    adjustments = _bs_table("confidence_adjustments", {
        "startup": -0.60, "young": -0.50, "established": 0.00,
        "mature": 0.00, "veteran": 0.00, "unknown": -0.05,
    })
    return float(adjustments.get(age_band, adjustments.get("unknown", -0.05)))


def survivorship_bonus(age_band: AgeBand, survived_downturn: bool = False) -> int:
    """Bonus for vendors that have demonstrated staying power.

    Survivorship is a positive signal — companies that weather economic
    downturns or simply survive for decades have proven business models.

    Bonuses:
    - startup: 0 (no survivorship yet)
    - young: 0 (too early for survivorship credit)
    - established: 0 (not yet demonstrated long-term survival)
    - mature: +5 (survived 10+ years)
    - veteran: +10 (survived 20+ years)
    - unknown: 0 (cannot determine survivorship)

    Additional +5 for surviving known economic downturns (2008, 2020) if
    the vendor was in business during those periods.
    """
    base_bonus = {
        "startup": 0,
        "young": 0,
        "established": 0,
        "mature": 5,
        "veteran": 10,
        "unknown": 0,
    }
    bonus = base_bonus.get(age_band, 0)
    if survived_downturn and age_band in ("mature", "veteran"):
        bonus += 5
    return bonus


def apply_age_modifiers(
    profile: FinancialProfile,
    base_confidence: float,
) -> tuple[int, float]:
    """Apply all age-based modifiers to Business Stability score and confidence.

    Args:
        profile: FinancialProfile with incorporation_date and derived fields
        base_confidence: Base confidence score from evidence coverage

    Returns:
        (base_age_score, adjusted_confidence) tuple
    """
    # Calculate operating years if not already computed
    if profile.operating_years is None and profile.incorporation_date:
        profile.operating_years = operating_years(profile.incorporation_date.value)

    # Determine age band if not already computed
    if profile.age_band is None:
        profile.age_band = age_band_from_years(profile.operating_years)

    # Get base score from age band
    age_score = base_age_score(profile.age_band or "unknown")

    # Apply confidence adjustment
    conf_adj = confidence_adjustment(profile.age_band or "unknown")
    adjusted_confidence = max(0.0, min(1.0, base_confidence + conf_adj))

    return age_score, adjusted_confidence


def age_risk_factors(age_band: AgeBand) -> dict[str, str]:
    """Return age-specific risk factors for display and scoring.

    Different risk factors matter at different ages:
    - Startups: funding runway, customer concentration, founder dependency
    - Young companies: growth sustainability, market fit validation
    - Established: market position, competitive pressure
    - Mature/veteran: decline signals, acquisition risk, stagnation

    Returns a dict of risk factor descriptions keyed by factor name.
    """
    factors = {
        "startup": {
            "funding_status": "Recent funding rounds and runway remaining",
            "customer_concentration": "Revenue concentration in few customers",
            "founder_dependency": "Key person risk in founder-led structure",
        },
        "young": {
            "growth_sustainability": "Ability to sustain growth trajectory",
            "market_validation": "Evidence of product-market fit",
            "team_completeness": "Executive team gaps and hiring ability",
        },
        "established": {
            "market_position": "Competitive position in industry",
            "operational_efficiency": "Margin pressure and cost structure",
            "scalability": "Ability to scale without breaking operations",
        },
        "mature": {
            "decline_signals": "Revenue or market share decline trends",
            "acquisition_risk": "Leadership changes or PE ownership signals",
            "innovation_stagnation": "R&D investment and product pipeline health",
        },
        "veteran": {
            "institutional_health": "Governance and succession planning",
            "adaptability": "Ability to pivot to market changes",
            "legacy_risk": "Technical debt and outdated systems",
        },
        "unknown": {
            "age_uncertainty": "Unable to determine company age from public sources",
            "track_record_gap": "No evidence of operating history available",
        },
    }
    return factors.get(age_band, {})


def age_appropriate_benchmarking(age_band: AgeBand) -> str:
    """Return benchmarking guidance based on vendor age.

    Young vendors should be benchmarked against peers of similar age,
    not against established companies. This prevents unfair comparisons.
    """
    guidance = {
        "startup": "Benchmark against other startups (<2 years) where possible",
        "young": "Benchmark against young companies (2-5 years) where possible",
        "established": "Benchmark against established peers (5-10 years)",
        "mature": "Benchmark against mature companies (10-20 years)",
        "veteran": "Benchmark against veteran companies (20+ years)",
        "unknown": "Benchmark against all vendors in sector/size cohort",
    }
    return guidance.get(age_band, "Benchmark against all vendors in sector/size cohort")


def contingency_plan_required(age_band: AgeBand, criticality: str | None = None) -> bool:
    """Determine if a contingency plan is required based on age and criticality.

    Young vendors providing critical services require contingency planning
    because their higher failure rate represents unacceptable business risk.

    Args:
        age_band: Vendor's age band
        criticality: Client-supplied criticality (low/medium/high)

    Returns:
        True if contingency plan should be required
    """
    if criticality == "high" and age_band in ("startup", "young"):
        return True
    if criticality == "medium" and age_band == "startup":
        return True
    return False
