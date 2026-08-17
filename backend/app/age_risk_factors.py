"""Age-specific risk factors for vendor differentiation.

This module implements advanced age-based risk differentiation beyond basic
age bands and maturity index. It provides age-specific scoring for:

1. Historical Depth - corpus richness and record availability
2. Financial Transparency - data availability and plausibility by age
3. Leadership Risk - founder dependence vs succession risk
4. Operational Maturity - scaling risk vs degradation detection
5. Media Velocity - adverse media interpretation by age
6. Structural Change Suspicion - corporate structure change scoring

The principle: a clean OSINT profile on a 2-year-old vendor is inherently less
reassuring than the same profile on a 20-year-old vendor with a long history.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .longevity import AgeBand

# Type aliases
HistoricalDepthBand = Literal["sparse", "limited", "moderate", "rich", "extensive"]
FinancialTransparencyBand = Literal["opaque", "limited", "partial", "transparent", "comprehensive"]
LeadershipRiskBand = Literal["founder_dependent", "high", "moderate", "low", "stable"]
OperationalMaturityBand = Literal["immature", "developing", "mature", "established", "legacy"]
MediaVelocityBand = Literal["unknown", "low", "moderate", "high", "critical"]
StructuralChangeSuspicionBand = Literal["high_suspicion", "moderate", "low", "neutral"]

# Historical depth thresholds by age band
# Young vendors: fewer years of data available, so "rich" means less absolute data
_HISTORICAL_DEPTH_THRESHOLDS: dict[AgeBand, dict[str, int]] = {
    "startup": {
        "sparse": 0,      # <1 finding
        "limited": 1,     # 1-2 findings
        "moderate": 3,    # 3-5 findings
        "rich": 6,        # 6+ findings (impressive for <2yr)
        "extensive": 10,   # 10+ findings
    },
    "young": {
        "sparse": 0,
        "limited": 2,
        "moderate": 5,
        "rich": 10,
        "extensive": 20,
    },
    "established": {
        "sparse": 0,
        "limited": 5,
        "moderate": 15,
        "rich": 30,
        "extensive": 50,
    },
    "mature": {
        "sparse": 0,
        "limited": 10,
        "moderate": 30,
        "rich": 60,
        "extensive": 100,
    },
    "veteran": {
        "sparse": 0,
        "limited": 15,
        "moderate": 50,
        "rich": 100,
        "extensive": 200,
    },
    "unknown": {
        "sparse": 0,
        "limited": 5,
        "moderate": 15,
        "rich": 30,
        "extensive": 50,
    },
}

# Financial transparency scoring by age
# Young vendors: lack of data is expected but rapid growth without data is suspicious
_FINANCIAL_TRANSPARENCY_WEIGHTS: dict[AgeBand, dict[str, float]] = {
    "startup": {
        "no_data_penalty": 0.0,      # Expected for startups
        "rapid_growth_suspicion": 0.3,  # High suspicion for unexplained growth
        "data_bonus": 0.2,          # Bonus for having any data
    },
    "young": {
        "no_data_penalty": 0.1,      # Mild penalty
        "rapid_growth_suspicion": 0.2,
        "data_bonus": 0.15,
    },
    "established": {
        "no_data_penalty": 0.2,      # Should have some data by 5-10 years
        "rapid_growth_suspicion": 0.1,
        "data_bonus": 0.1,
    },
    "mature": {
        "no_data_penalty": 0.4,      # Should have substantial data
        "rapid_growth_suspicion": 0.05,
        "data_bonus": 0.05,
    },
    "veteran": {
        "no_data_penalty": 0.5,      # Should have complete data
        "rapid_growth_suspicion": 0.0,  # Growth patterns well-established
        "data_bonus": 0.0,
    },
    "unknown": {
        "no_data_penalty": 0.2,
        "rapid_growth_suspicion": 0.1,
        "data_bonus": 0.1,
    },
}

# Leadership risk factors by age
_LEADERSHIP_RISK_WEIGHTS: dict[AgeBand, dict[str, float]] = {
    "startup": {
        "founder_history_weight": 0.8,   # Founder's history is primary signal
        "turnover_penalty": 0.3,          # Rapid turnover very concerning
        "succession_risk": 0.1,           # Low succession risk (founder present)
    },
    "young": {
        "founder_history_weight": 0.6,
        "turnover_penalty": 0.2,
        "succession_risk": 0.2,
    },
    "established": {
        "founder_history_weight": 0.3,
        "turnover_penalty": 0.15,
        "succession_risk": 0.4,           # Succession planning becomes relevant
    },
    "mature": {
        "founder_history_weight": 0.1,   # Less relevant for mature firms
        "turnover_penalty": 0.1,
        "succession_risk": 0.6,           # High succession risk concern
    },
    "veteran": {
        "founder_history_weight": 0.0,
        "turnover_penalty": 0.05,
        "succession_risk": 0.7,           # Succession is primary concern
    },
    "unknown": {
        "founder_history_weight": 0.4,
        "turnover_penalty": 0.15,
        "succession_risk": 0.3,
    },
}

# Operational maturity scoring
_OPERATIONAL_MATURITY_WEIGHTS: dict[AgeBand, dict[str, float]] = {
    "startup": {
        "scaling_risk": 0.5,              # High risk of scaling outpacing controls
        "infrastructure_age_weight": 0.2,
        "process_maturity_weight": 0.1,   # Low weight - processes not established
    },
    "young": {
        "scaling_risk": 0.3,
        "infrastructure_age_weight": 0.3,
        "process_maturity_weight": 0.2,
    },
    "established": {
        "scaling_risk": 0.15,
        "infrastructure_age_weight": 0.4,
        "process_maturity_weight": 0.4,
    },
    "mature": {
        "scaling_risk": 0.05,            # Low scaling risk
        "infrastructure_age_weight": 0.3, # Degradation becomes concern
        "process_maturity_weight": 0.6,  # High weight - processes should be mature
    },
    "veteran": {
        "scaling_risk": 0.0,
        "infrastructure_age_weight": 0.2, # Obsolescence risk
        "process_maturity_weight": 0.7,  # Very high weight
    },
    "unknown": {
        "scaling_risk": 0.2,
        "infrastructure_age_weight": 0.3,
        "process_maturity_weight": 0.3,
    },
}

# Media velocity interpretation by age
# Young vendors: single negative finding carries high weight
# Mature vendors: trends matter more than single findings
_MEDIA_VELOCITY_WEIGHTS: dict[AgeBand, dict[str, float]] = {
    "startup": {
        "single_finding_weight": 0.8,    # Single finding very significant
        "trend_weight": 0.2,             # Trends less relevant (short history)
        "absence_of_history_penalty": 0.3,  # No history is elevated risk
    },
    "young": {
        "single_finding_weight": 0.6,
        "trend_weight": 0.3,
        "absence_of_history_penalty": 0.2,
    },
    "established": {
        "single_finding_weight": 0.4,
        "trend_weight": 0.5,
        "absence_of_history_penalty": 0.1,
    },
    "mature": {
        "single_finding_weight": 0.2,    # Single finding less significant
        "trend_weight": 0.7,             # Trends are primary signal
        "absence_of_history_penalty": 0.0,  # History should exist
    },
    "veteran": {
        "single_finding_weight": 0.1,
        "trend_weight": 0.8,
        "absence_of_history_penalty": 0.0,
    },
    "unknown": {
        "single_finding_weight": 0.4,
        "trend_weight": 0.4,
        "absence_of_history_penalty": 0.2,
    },
}

# Structural change suspicion by age
# Young vendors: frequent changes suggest shell company or instability
# Mature vendors: changes may indicate transformation or concentration risk
_STRUCTURAL_CHANGE_WEIGHTS: dict[AgeBand, dict[str, float]] = {
    "startup": {
        "name_change_suspicion": 0.7,   # High suspicion
        "address_change_suspicion": 0.6,
        "ownership_change_suspicion": 0.5,
        "acquisition_signal": 0.2,       # Unlikely for startup
    },
    "young": {
        "name_change_suspicion": 0.5,
        "address_change_suspicion": 0.4,
        "ownership_change_suspicion": 0.3,
        "acquisition_signal": 0.3,
    },
    "established": {
        "name_change_suspicion": 0.3,
        "address_change_suspicion": 0.25,
        "ownership_change_suspicion": 0.2,
        "acquisition_signal": 0.5,
    },
    "mature": {
        "name_change_suspicion": 0.15,
        "address_change_suspicion": 0.15,
        "ownership_change_suspicion": 0.15,
        "acquisition_signal": 0.7,       # May indicate transformation
    },
    "veteran": {
        "name_change_suspicion": 0.1,
        "address_change_suspicion": 0.1,
        "ownership_change_suspicion": 0.1,
        "acquisition_signal": 0.8,       # Concentration risk
    },
    "unknown": {
        "name_change_suspicion": 0.3,
        "address_change_suspicion": 0.25,
        "ownership_change_suspicion": 0.25,
        "acquisition_signal": 0.4,
    },
}


@dataclass
class HistoricalDepthScore:
    """Historical depth assessment - how rich the OSINT corpus is for this vendor."""
    band: HistoricalDepthBand
    finding_count: int
    years_of_data: float | None
    corpus_richness_score: float  # 0-1, higher is better
    age_adjusted_score: float  # 0-1, adjusted for expected depth by age
    rationale: str


def historical_depth_score(
    finding_count: int,
    years_of_data: float | None,
    age_band: AgeBand,
) -> HistoricalDepthScore:
    """Calculate historical depth score based on finding count and age band.
    
    Young vendors are expected to have fewer findings, so the same absolute
    count represents higher relative corpus richness for a startup than for
    a veteran vendor.
    
    Args:
        finding_count: Total number of findings across all categories
        years_of_data: Years of available historical data
        age_band: Vendor age band
    
    Returns:
        HistoricalDepthScore with band, scores, and rationale
    """
    thresholds = _HISTORICAL_DEPTH_THRESHOLDS.get(age_band, _HISTORICAL_DEPTH_THRESHOLDS["unknown"])
    
    # Determine band based on finding count
    if finding_count >= thresholds["extensive"]:
        band = "extensive"
    elif finding_count >= thresholds["rich"]:
        band = "rich"
    elif finding_count >= thresholds["moderate"]:
        band = "moderate"
    elif finding_count >= thresholds["limited"]:
        band = "limited"
    else:
        band = "sparse"
    
    # Base corpus richness score (0-1)
    max_expected = thresholds["extensive"]
    corpus_richness_score = min(1.0, finding_count / max_expected) if max_expected > 0 else 0.0
    
    # Age-adjusted score: sparse data is more concerning for mature vendors
    # but less concerning for startups (expected)
    if age_band in ("startup", "young"):
        # Sparse data is expected, so don't penalize as heavily
        age_adjusted_score = corpus_richness_score
    elif age_band in ("mature", "veteran"):
        # Sparse data is concerning for mature vendors
        if band == "sparse":
            age_adjusted_score = corpus_richness_score * 0.5
        elif band == "limited":
            age_adjusted_score = corpus_richness_score * 0.7
        else:
            age_adjusted_score = corpus_richness_score
    else:
        age_adjusted_score = corpus_richness_score
    
    rationale = (
        f"Historical depth is {band} ({finding_count} findings). "
        f"For a {age_band} vendor, this represents "
        f"{'rich' if age_adjusted_score > 0.7 else 'moderate' if age_adjusted_score > 0.4 else 'limited'} "
        f"corpus richness relative to expectations."
    )
    
    return HistoricalDepthScore(
        band=band,
        finding_count=finding_count,
        years_of_data=years_of_data,
        corpus_richness_score=round(corpus_richness_score, 3),
        age_adjusted_score=round(age_adjusted_score, 3),
        rationale=rationale,
    )


@dataclass
class FinancialTransparencyScore:
    """Financial transparency assessment - data availability and plausibility."""
    band: FinancialTransparencyBand
    has_financial_data: bool
    revenue_plausible: bool | None
    growth_rate: float | None
    transparency_score: float  # 0-1, higher is better
    age_adjusted_score: float  # 0-1, adjusted for expected transparency by age
    rationale: str


def financial_transparency_score(
    has_financial_data: bool,
    revenue_plausible: bool | None,
    growth_rate: float | None,
    age_band: AgeBand,
    years_of_operation: float | None,
) -> FinancialTransparencyScore:
    """Calculate financial transparency score with age-specific expectations.
    
    Young vendors often lack deep financial transparency - this is expected.
    However, rapid unexplained growth is treated as higher inherent risk.
    Mature vendors should have substantial financial data; lack of data
    is concerning.
    
    Args:
        has_financial_data: Whether any financial data is available
        revenue_plausible: Whether claimed revenue is plausible given years
        growth_rate: Annual revenue growth rate (if available)
        age_band: Vendor age band
        years_of_operation: Years since incorporation
    
    Returns:
        FinancialTransparencyScore with band, scores, and rationale
    """
    weights = _FINANCIAL_TRANSPARENCY_WEIGHTS.get(age_band, _FINANCIAL_TRANSPARENCY_WEIGHTS["unknown"])
    
    # Base transparency score
    score = 1.0
    
    if not has_financial_data:
        score -= weights["no_data_penalty"]
    else:
        score += weights["data_bonus"]
    
    # Check for rapid unexplained growth
    if growth_rate is not None and growth_rate > 2.0:  # >200% annual growth
        # More suspicious for older vendors who should have established patterns
        if age_band in ("established", "mature", "veteran"):
            score -= weights["rapid_growth_suspicion"] * 1.5
        else:
            score -= weights["rapid_growth_suspicion"]
    
    # Revenue plausibility check
    if revenue_plausible is False:
        score -= 0.3  # Significant penalty for implausible revenue
    elif revenue_plausible is True:
        score += 0.1
    
    score = max(0.0, min(1.0, score))
    
    # Age-adjusted score
    age_adjusted_score = score
    
    # Determine band
    if score >= 0.8:
        band = "comprehensive"
    elif score >= 0.6:
        band = "transparent"
    elif score >= 0.4:
        band = "partial"
    elif score >= 0.2:
        band = "limited"
    else:
        band = "opaque"
    
    rationale_parts = []
    if not has_financial_data:
        rationale_parts.append(f"no financial data available (expected for {age_band} vendors)")
    else:
        rationale_parts.append("financial data available")
        if revenue_plausible is True:
            rationale_parts.append("revenue appears plausible")
        elif revenue_plausible is False:
            rationale_parts.append("revenue appears implausible given operating years")
    
    if growth_rate is not None and growth_rate > 2.0:
        rationale_parts.append(f"rapid growth ({growth_rate*100:.0f}% annually) requires scrutiny")
    
    rationale = "Financial transparency is " + band + ". " + "; ".join(rationale_parts) + "."
    
    return FinancialTransparencyScore(
        band=band,
        has_financial_data=has_financial_data,
        revenue_plausible=revenue_plausible,
        growth_rate=growth_rate,
        transparency_score=round(score, 3),
        age_adjusted_score=round(age_adjusted_score, 3),
        rationale=rationale,
    )


@dataclass
class LeadershipRiskScore:
    """Leadership risk assessment - founder dependence vs succession risk."""
    band: LeadershipRiskBand
    founder_history_clean: bool | None
    recent_turnover: bool
    succession_plan_evident: bool
    risk_score: float  # 0-1, higher is higher risk
    rationale: str


def leadership_risk_score(
    founder_history_clean: bool | None,
    recent_turnover: bool,
    succession_plan_evident: bool,
    age_band: AgeBand,
) -> LeadershipRiskScore:
    """Calculate leadership risk score with age-specific weighting.
    
    For young vendors, the founder's personal history is a primary risk signal.
    For mature vendors, the focus shifts to recent leadership changes and
    succession risk.
    
    Args:
        founder_history_clean: Whether founder has clean history (None if unknown)
        recent_turnover: Whether there has been recent executive turnover
        succession_plan_evident: Whether succession planning is evident
        age_band: Vendor age band
    
    Returns:
        LeadershipRiskScore with band, risk score, and rationale
    """
    weights = _LEADERSHIP_RISK_WEIGHTS.get(age_band, _LEADERSHIP_RISK_WEIGHTS["unknown"])
    
    risk_score = 0.0
    
    # Founder history (more important for young vendors)
    if founder_history_clean is False:
        risk_score += weights["founder_history_weight"]
    elif founder_history_clean is True:
        risk_score -= weights["founder_history_weight"] * 0.5
    
    # Recent turnover
    if recent_turnover:
        risk_score += weights["turnover_penalty"]
    
    # Succession risk (more important for mature vendors)
    if not succession_plan_evident:
        risk_score += weights["succession_risk"]
    else:
        risk_score -= weights["succession_risk"] * 0.3
    
    risk_score = max(0.0, min(1.0, risk_score))
    
    # Determine band
    if risk_score >= 0.7:
        band = "founder_dependent" if age_band in ("startup", "young") else "high"
    elif risk_score >= 0.5:
        band = "high"
    elif risk_score >= 0.3:
        band = "moderate"
    elif risk_score >= 0.15:
        band = "low"
    else:
        band = "stable"
    
    rationale_parts = []
    if age_band in ("startup", "young"):
        rationale_parts.append("founder's personal history is a primary risk signal")
    else:
        rationale_parts.append("focus on recent leadership changes and succession risk")
    
    if founder_history_clean is False:
        rationale_parts.append("founder has concerning history")
    elif founder_history_clean is True:
        rationale_parts.append("founder has clean history")
    
    if recent_turnover:
        rationale_parts.append("recent executive turnover detected")
    
    if not succession_plan_evident:
        rationale_parts.append("no evident succession planning")
    
    rationale = "Leadership risk is " + band + ". " + "; ".join(rationale_parts) + "."
    
    return LeadershipRiskScore(
        band=band,
        founder_history_clean=founder_history_clean,
        recent_turnover=recent_turnover,
        succession_plan_evident=succession_plan_evident,
        risk_score=round(risk_score, 3),
        rationale=rationale,
    )


@dataclass
class OperationalMaturityScore:
    """Operational maturity assessment - scaling risk vs degradation detection."""
    band: OperationalMaturityBand
    infrastructure_age_years: float | None
    process_maturity_evident: bool
    scaling_risk_indicators: int
    maturity_score: float  # 0-1, higher is more mature
    rationale: str


def operational_maturity_score(
    infrastructure_age_years: float | None,
    process_maturity_evident: bool,
    scaling_risk_indicators: int,
    age_band: AgeBand,
) -> OperationalMaturityScore:
    """Calculate operational maturity score with age-specific focus.
    
    Young vendors: focus on scaling risk (rapid growth outpacing controls).
    Mature vendors: focus on degradation detection and obsolescence.
    
    Args:
        infrastructure_age_years: Age of internet-facing infrastructure
        process_maturity_evident: Whether process maturity is evident (SOC2, ISO, etc.)
        scaling_risk_indicators: Count of scaling risk indicators
        age_band: Vendor age band
    
    Returns:
        OperationalMaturityScore with band, maturity score, and rationale
    """
    weights = _OPERATIONAL_MATURITY_WEIGHTS.get(age_band, _OPERATIONAL_MATURITY_WEIGHTS["unknown"])
    
    maturity_score = 0.5  # Base score
    
    # Infrastructure age
    if infrastructure_age_years is not None:
        if infrastructure_age_years >= 5:
            maturity_score += weights["infrastructure_age_weight"]
        elif infrastructure_age_years >= 2:
            maturity_score += weights["infrastructure_age_weight"] * 0.5
    
    # Process maturity
    if process_maturity_evident:
        maturity_score += weights["process_maturity_weight"]
    
    # Scaling risk (penalty)
    scaling_penalty = scaling_risk_indicators * weights["scaling_risk"]
    maturity_score -= scaling_penalty
    
    maturity_score = max(0.0, min(1.0, maturity_score))
    
    # Determine band
    if maturity_score >= 0.8:
        band = "legacy" if age_band == "veteran" else "established"
    elif maturity_score >= 0.6:
        band = "established"
    elif maturity_score >= 0.4:
        band = "mature"
    elif maturity_score >= 0.2:
        band = "developing"
    else:
        band = "immature"
    
    rationale_parts = []
    if age_band in ("startup", "young"):
        rationale_parts.append("focus on scaling risk - rapid growth may outpace controls")
    else:
        rationale_parts.append("focus on degradation detection and process maturity")
    
    if scaling_risk_indicators > 0:
        rationale_parts.append(f"{scaling_risk_indicators} scaling risk indicator(s) detected")
    
    if process_maturity_evident:
        rationale_parts.append("process maturity evident (certifications, controls)")
    else:
        rationale_parts.append("limited evidence of process maturity")
    
    rationale = "Operational maturity is " + band + ". " + "; ".join(rationale_parts) + "."
    
    return OperationalMaturityScore(
        band=band,
        infrastructure_age_years=infrastructure_age_years,
        process_maturity_evident=process_maturity_evident,
        scaling_risk_indicators=scaling_risk_indicators,
        maturity_score=round(maturity_score, 3),
        rationale=rationale,
    )


@dataclass
class MediaVelocityScore:
    """Media velocity assessment - adverse media interpretation by age."""
    band: MediaVelocityBand
    adverse_media_count: int
    recent_spike: bool
    trend_direction: str | None  # "improving", "declining", "stable", None
    velocity_score: float  # 0-1, higher is more concerning
    rationale: str


def media_velocity_score(
    adverse_media_count: int,
    recent_spike: bool,
    trend_direction: str | None,
    age_band: AgeBand,
    years_of_history: float | None,
) -> MediaVelocityScore:
    """Calculate media velocity score with age-specific interpretation.
    
    Young vendors: single negative finding carries high relative weight.
    Mature vendors: trends matter more than single findings.
    
    Args:
        adverse_media_count: Count of adverse media items
        recent_spike: Whether there's been a recent spike in negative coverage
        trend_direction: "improving", "declining", "stable", or None
        age_band: Vendor age band
        years_of_history: Years of media history available
    
    Returns:
        MediaVelocityScore with band, velocity score, and rationale
    """
    weights = _MEDIA_VELOCITY_WEIGHTS.get(age_band, _MEDIA_VELOCITY_WEIGHTS["unknown"])
    
    velocity_score = 0.0
    
    # Single finding weight (higher for young vendors)
    if adverse_media_count == 1:
        velocity_score += weights["single_finding_weight"]
    elif adverse_media_count > 1:
        velocity_score += weights["single_finding_weight"] * 1.5
    
    # Trend weight (higher for mature vendors)
    if trend_direction == "declining":
        velocity_score += weights["trend_weight"]
    elif trend_direction == "improving":
        velocity_score -= weights["trend_weight"] * 0.3
    
    # Recent spike (always concerning)
    if recent_spike:
        velocity_score += 0.3
    
    # Absence of history penalty (for young vendors, this is elevated risk)
    if years_of_history is None or years_of_history < 1:
        velocity_score += weights["absence_of_history_penalty"]
    
    velocity_score = max(0.0, min(1.0, velocity_score))
    
    # Determine band
    if velocity_score >= 0.7:
        band = "critical"
    elif velocity_score >= 0.5:
        band = "high"
    elif velocity_score >= 0.3:
        band = "moderate"
    elif velocity_score >= 0.1:
        band = "low"
    else:
        band = "unknown"
    
    rationale_parts = []
    if age_band in ("startup", "young"):
        rationale_parts.append("single negative findings carry high relative weight")
        rationale_parts.append("absence of history is itself elevated risk")
    else:
        rationale_parts.append("trends and patterns are more significant than single findings")
    
    if adverse_media_count > 0:
        rationale_parts.append(f"{adverse_media_count} adverse media item(s)")
    
    if recent_spike:
        rationale_parts.append("recent spike in negative coverage detected")
    
    if trend_direction:
        rationale_parts.append(f"trend is {trend_direction}")
    
    rationale = "Media velocity is " + band + ". " + "; ".join(rationale_parts) + "."
    
    return MediaVelocityScore(
        band=band,
        adverse_media_count=adverse_media_count,
        recent_spike=recent_spike,
        trend_direction=trend_direction,
        velocity_score=round(velocity_score, 3),
        rationale=rationale,
    )


@dataclass
class StructuralChangeScore:
    """Structural change suspicion assessment - corporate structure change scoring."""
    band: StructuralChangeSuspicionBand
    name_changes: int
    address_changes: int
    ownership_changes: int
    acquisition_activity: bool
    suspicion_score: float  # 0-1, higher is more suspicious
    rationale: str


def structural_change_score(
    name_changes: int,
    address_changes: int,
    ownership_changes: int,
    acquisition_activity: bool,
    age_band: AgeBand,
    years_of_operation: float | None,
) -> StructuralChangeScore:
    """Calculate structural change suspicion score with age-specific interpretation.
    
    Young vendors: frequent changes suggest shell company or instability.
    Mature vendors: changes may indicate transformation or concentration risk.
    
    Args:
        name_changes: Count of name changes
        address_changes: Count of address changes
        ownership_changes: Count of ownership changes
        acquisition_activity: Whether there's acquisition activity
        age_band: Vendor age band
        years_of_operation: Years since incorporation
    
    Returns:
        StructuralChangeScore with band, suspicion score, and rationale
    """
    weights = _STRUCTURAL_CHANGE_WEIGHTS.get(age_band, _STRUCTURAL_CHANGE_WEIGHTS["unknown"])
    
    suspicion_score = 0.0
    
    # Name changes
    suspicion_score += name_changes * weights["name_change_suspicion"]
    
    # Address changes
    suspicion_score += address_changes * weights["address_change_suspicion"]
    
    # Ownership changes
    suspicion_score += ownership_changes * weights["ownership_change_suspicion"]
    
    # Acquisition activity
    if acquisition_activity:
        suspicion_score += weights["acquisition_signal"]
    
    # Normalize by years of operation (more changes in less time = more suspicious)
    if years_of_operation and years_of_operation > 0:
        total_changes = name_changes + address_changes + ownership_changes
        change_rate = total_changes / years_of_operation
        if change_rate > 1.0:  # More than 1 change per year
            suspicion_score *= 1.5
    
    suspicion_score = max(0.0, min(1.0, suspicion_score))
    
    # Determine band
    if suspicion_score >= 0.6:
        band = "high_suspicion"
    elif suspicion_score >= 0.4:
        band = "moderate"
    elif suspicion_score >= 0.2:
        band = "low"
    else:
        band = "neutral"
    
    rationale_parts = []
    if age_band in ("startup", "young"):
        rationale_parts.append("frequent structural changes suggest possible shell company or instability")
    else:
        rationale_parts.append("structural changes may indicate transformation or concentration risk")
    
    total_changes = name_changes + address_changes + ownership_changes
    if total_changes > 0:
        rationale_parts.append(f"{total_changes} structural change(s) detected")
    
    if acquisition_activity:
        rationale_parts.append("acquisition activity detected")
    
    rationale = "Structural change suspicion is " + band + ". " + "; ".join(rationale_parts) + "."
    
    return StructuralChangeScore(
        band=band,
        name_changes=name_changes,
        address_changes=address_changes,
        ownership_changes=ownership_changes,
        acquisition_activity=acquisition_activity,
        suspicion_score=round(suspicion_score, 3),
        rationale=rationale,
    )


@dataclass
class AgeDifferentiationProfile:
    """Complete age differentiation profile for a vendor."""
    age_band: AgeBand
    historical_depth: HistoricalDepthScore
    financial_transparency: FinancialTransparencyScore
    leadership_risk: LeadershipRiskScore
    operational_maturity: OperationalMaturityScore
    media_velocity: MediaVelocityScore
    structural_change: StructuralChangeScore
    overall_age_risk_score: float  # 0-1, aggregated risk score
    rationale: str


def compute_age_differentiation_profile(
    age_band: AgeBand,
    finding_count: int = 0,
    years_of_data: float | None = None,
    has_financial_data: bool = False,
    revenue_plausible: bool | None = None,
    growth_rate: float | None = None,
    years_of_operation: float | None = None,
    founder_history_clean: bool | None = None,
    recent_turnover: bool = False,
    succession_plan_evident: bool = False,
    infrastructure_age_years: float | None = None,
    process_maturity_evident: bool = False,
    scaling_risk_indicators: int = 0,
    adverse_media_count: int = 0,
    recent_spike: bool = False,
    trend_direction: str | None = None,
    years_of_history: float | None = None,
    name_changes: int = 0,
    address_changes: int = 0,
    ownership_changes: int = 0,
    acquisition_activity: bool = False,
) -> AgeDifferentiationProfile:
    """Compute complete age differentiation profile.
    
    This aggregates all age-specific risk factors into a single profile
    that can be used to explain why vendors of different ages are treated
    differently even with similar current OSINT scores.
    
    Args:
        age_band: Vendor age band
        finding_count: Total OSINT findings count
        years_of_data: Years of available historical data
        has_financial_data: Whether financial data is available
        revenue_plausible: Whether claimed revenue is plausible
        growth_rate: Annual revenue growth rate
        years_of_operation: Years since incorporation
        founder_history_clean: Whether founder has clean history
        recent_turnover: Whether recent executive turnover occurred
        succession_plan_evident: Whether succession planning is evident
        infrastructure_age_years: Age of internet-facing infrastructure
        process_maturity_evident: Whether process maturity is evident
        scaling_risk_indicators: Count of scaling risk indicators
        adverse_media_count: Count of adverse media items
        recent_spike: Whether recent spike in negative coverage
        trend_direction: Media trend direction
        years_of_history: Years of media history
        name_changes: Count of name changes
        address_changes: Count of address changes
        ownership_changes: Count of ownership changes
        acquisition_activity: Whether acquisition activity detected
    
    Returns:
        AgeDifferentiationProfile with all component scores
    """
    historical_depth = historical_depth_score(finding_count, years_of_data, age_band)
    financial_transparency = financial_transparency_score(
        has_financial_data, revenue_plausible, growth_rate, age_band, years_of_operation
    )
    leadership_risk = leadership_risk_score(
        founder_history_clean, recent_turnover, succession_plan_evident, age_band
    )
    operational_maturity = operational_maturity_score(
        infrastructure_age_years, process_maturity_evident, scaling_risk_indicators, age_band
    )
    media_velocity = media_velocity_score(
        adverse_media_count, recent_spike, trend_direction, age_band, years_of_history
    )
    structural_change = structural_change_score(
        name_changes, address_changes, ownership_changes, acquisition_activity,
        age_band, years_of_operation
    )
    
    # Aggregate overall age risk score
    # Higher scores = higher risk
    risk_components = [
        (1.0 - historical_depth.age_adjusted_score) * 0.15,  # Sparse data = risk
        (1.0 - financial_transparency.age_adjusted_score) * 0.20,  # Low transparency = risk
        leadership_risk.risk_score * 0.15,  # Leadership risk
        (1.0 - operational_maturity.maturity_score) * 0.15,  # Low maturity = risk
        media_velocity.velocity_score * 0.20,  # Media velocity = risk
        structural_change.suspicion_score * 0.15,  # Structural change = risk
    ]
    
    overall_age_risk_score = sum(risk_components)
    overall_age_risk_score = max(0.0, min(1.0, overall_age_risk_score))
    
    rationale = (
        f"Age differentiation profile for {age_band} vendor. "
        f"Overall age risk score: {overall_age_risk_score:.2f}. "
        f"Key factors: historical depth ({historical_depth.band}), "
        f"financial transparency ({financial_transparency.band}), "
        f"leadership risk ({leadership_risk.band}), "
        f"operational maturity ({operational_maturity.band}), "
        f"media velocity ({media_velocity.band}), "
        f"structural change suspicion ({structural_change.band})."
    )
    
    return AgeDifferentiationProfile(
        age_band=age_band,
        historical_depth=historical_depth,
        financial_transparency=financial_transparency,
        leadership_risk=leadership_risk,
        operational_maturity=operational_maturity,
        media_velocity=media_velocity,
        structural_change=structural_change,
        overall_age_risk_score=round(overall_age_risk_score, 3),
        rationale=rationale,
    )
