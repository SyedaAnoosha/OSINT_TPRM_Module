"""Business Stability scoring engine.

This module implements the Business Stability score — a separate 0-100 axis
measuring financial health and viability, distinct from cybersecurity posture.

The scoring model follows the same penalty-based approach as cybersecurity:
- Vendors start at a base score determined by age (70-100)
- Financial distress signals subtract penalties
- Survivorship bonuses add points back
- Active insolvency proceedings BLOCK (gate, not a score)

KEY PRINCIPLE: Financial distress ≠ poor security. A bankrupt company can
have excellent cybersecurity controls, and a secure startup can run out of
cash. These are separate risk dimensions that must not be conflated.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .age_risk_factors import (
    compute_age_differentiation_profile,
    financial_transparency_score,
    historical_depth_score,
    leadership_risk_score,
    media_velocity_score,
    operational_maturity_score,
    structural_change_score,
)
from .longevity import (
    age_band_from_years,
    apply_age_modifiers,
    base_age_score,
    confidence_adjustment,
    contingency_plan_required,
    operating_years,
    survivorship_bonus,
)
from .models import FinancialProfile, FinancialMetrics, InsolvencyRecord, InsolvencyStatus


def business_stability_standing(score: int | None, gate_triggered: bool) -> str:
    """Map Business Stability score to standing level.
    
    Similar to confidence bands, this provides human-readable status:
    - 80-100: "sound" (good financial health)
    - 60-79: "watch" (moderate risk, monitoring needed)
    - 40-59: "impaired" (significant financial concerns)
    - 0-39: "ceased" (severe distress, cannot contract)
    - None (gated): "ceased" (blocked from assessment)
    
    This matches the severity levels used in continuity.py for consistency.
    """
    if gate_triggered or score is None:
        return "ceased"
    
    if score >= 80:
        return "sound"
    elif score >= 60:
        return "watch"
    elif score >= 40:
        return "impaired"
    else:
        return "ceased"


class BusinessStabilityScore:
    """Business Stability score (0-100) for a vendor.

    The score measures financial health and viability using:
    1. Age-based base score (longevity)
    2. Financial penalty signals (revenue decline, debt ratios, etc.)
    3. Survivorship bonuses (demonstrated staying power)
    4. Gate logic (active insolvency = BLOCK)

    This is deliberately separate from cybersecurity posture — the two axes
    answer different questions and must not influence each other.
    """

    def __init__(self, profile: FinancialProfile):
        """Initialize with a FinancialProfile.

        The profile should contain:
        - incorporation_date (for age calculation)
        - insolvency_records (for gate check)
        - financial_metrics (for financial penalties)
        """
        self.profile = profile
        self._base_score: int | None = None
        self._final_score: int | None = None
        self._penalties: dict[str, float] = {}
        self._bonuses: dict[str, float] = {}
        self._gate_triggered: bool = False
        self._gate_reason: str | None = None

    def compute(self) -> dict[str, Any]:
        """Compute the full Business Stability score.

        Returns a dict with:
        - score: final 0-100 score (or None if gated)
        - base_score: starting score from age
        - penalties: dict of signal -> penalty points
        - bonuses: dict of signal -> bonus points
        - gate_triggered: whether insolvency gate fired
        - gate_reason: why gate fired (if applicable)
        - age_band: vendor's age classification
        - confidence_adjusted: confidence score after age adjustment
        """
        # Check insolvency gate first
        self._check_insolvency_gate()
        if self._gate_triggered:
            return {
                "score": None,
                "base_score": None,
                "penalties": self._penalties,
                "bonuses": self._bonuses,
                "gate_triggered": True,
                "gate_reason": self._gate_reason,
                "age_band": self.profile.age_band,
                "confidence_adjusted": None,
            }

        # Compute age-based base score
        self._compute_age_base()

        # Apply financial penalties
        self._apply_financial_penalties()

        # Apply survivorship bonuses
        self._apply_survivorship_bonuses()

        # Apply age-based adjustments to penalties and bonuses
        self._apply_age_based_adjustments()

        # Calculate final score
        self._final_score = max(0, min(100, self._base_score - sum(self._penalties.values()) + sum(self._bonuses.values())))

        # Compute age differentiation profile
        age_profile = self._compute_age_differentiation_profile()

        # Calculate standing based on score
        standing = business_stability_standing(self._final_score, self._gate_triggered)

        return {
            "score": self._final_score,
            "base_score": self._base_score,
            "penalties": self._penalties,
            "bonuses": self._bonuses,
            "gate_triggered": False,
            "gate_reason": None,
            "age_band": self.profile.age_band,
            "confidence_adjusted": None,  # Set by caller with base confidence
            "age_differentiation": age_profile,
            "standing": standing,  # Add standing based on score
        }

    def _check_insolvency_gate(self) -> None:
        """Check if active insolvency proceedings should BLOCK scoring.

        Active proceedings (liquidation, administration, receivership) trigger
        the gate. Historical insolvency is scored as a penalty but does not block.
        """
        for record in self.profile.insolvency_records:
            if record.status == "active":
                self._gate_triggered = True
                self._gate_reason = (
                    f"Active insolvency proceeding: {record.proceeding_type} "
                    f"({record.case_number or 'no case number'}) "
                    f"in {record.jurisdiction or 'unknown jurisdiction'}"
                )
                self.profile.insolvency_gate = True
                self.profile.insolvency_gate_reason = self._gate_reason
                return

        # Check company status for dissolved/liquidated
        if self.profile.company_status:
            status = str(self.profile.company_status.value).lower()
            if status in ("liquidation", "administration", "receivership", "dissolved"):
                self._gate_triggered = True
                self._gate_reason = f"Company status: {status}"
                self.profile.insolvency_gate = True
                self.profile.insolvency_gate_reason = self._gate_reason

    def _compute_age_base(self) -> None:
        """Compute base score from vendor age.

        Priority order for age sources:
        1. incorporation_date from entity registers (OpenCorporates, Companies House, etc.)
        2. entity_maturity from Wikidata (P571 - legal inception date)
        3. entity_maturity from RDAP (domain creation date - discounted but free)
        4. Fallback to "unknown" if no source available
        """
        # Try incorporation_date first (entity registers)
        if self.profile.incorporation_date:
            self.profile.operating_years = operating_years(self.profile.incorporation_date.value)
        else:
            # Fallback to Wikidata or RDAP maturity data from findings
            # These are stored as additional metadata in the profile
            wikidata_years = getattr(self.profile, 'wikidata_years', None)
            rdap_years = getattr(self.profile, 'rdap_years', None)

            # Prefer Wikidata (legal inception) over RDAP (domain age)
            if wikidata_years is not None:
                self.profile.operating_years = wikidata_years
            elif rdap_years is not None:
                self.profile.operating_years = rdap_years
            else:
                self.profile.operating_years = None

        # Determine age band
        if self.profile.age_band is None:
            self.profile.age_band = age_band_from_years(self.profile.operating_years)

        # Get base score (uses updated age-based scoring from longevity.py)
        self._base_score = base_age_score(self.profile.age_band or "unknown")

    def _apply_financial_penalties(self) -> None:
        """Apply penalties based on financial distress signals.

        Penalties are subtracted from the base score:
        - Historical insolvency: -20 (resolved but concerning)
        - Going-concern language (SEC EDGAR): -25 (severe financial distress)
        - Declining revenue (3+ consecutive quarters): -15
        - High debt-to-equity (>3): -10
        - Negative cash flow (2+ years): -15
        - Revenue concentration (>30% single customer): for startups only, -10
        """
        # SEC EDGAR going-concern language penalty (CRITICAL)
        # This is when the company's own auditor flags doubt about their ability to continue
        if hasattr(self.profile, 'going_concern_flagged') and self.profile.going_concern_flagged:
            self._penalties["going_concern_language"] = 25.0
            self.profile.going_concern_detected = True
        
        # Historical insolvency penalty
        for record in self.profile.insolvency_records:
            if record.status in ("historical", "resolved"):
                years_since = self._years_since(record.date)
                if years_since is not None and years_since > 3:
                    # Old insolvency, minor penalty
                    self._penalties["historical_insolvency_old"] = 5.0
                else:
                    # Recent insolvency, significant penalty
                    self._penalties["historical_insolvency_recent"] = 20.0
                break  # Only penalize once for historical insolvency

        # Financial metrics penalties
        if self.profile.financial_metrics:
            metrics = self.profile.financial_metrics

            # Revenue trend penalty
            revenue_trend = self._calculate_revenue_trend(metrics)
            if revenue_trend == "declining":
                self._penalties["revenue_decline"] = 15.0
            self.profile.revenue_trend = revenue_trend

            # Debt-to-equity penalty
            debt_to_equity = self._calculate_debt_to_equity(metrics)
            if debt_to_equity is not None and debt_to_equity > 3.0:
                self._penalties["high_debt_to_equity"] = 10.0
            elif debt_to_equity is not None and debt_to_equity > 2.0:
                self._penalties["elevated_debt_to_equity"] = 5.0
            self.profile.debt_to_equity = debt_to_equity

            # Cash flow penalty
            cash_flow = self._calculate_cash_flow_trend(metrics)
            if cash_flow == "negative":
                self._penalties["negative_cash_flow"] = 15.0
            self.profile.cash_flow_trend = cash_flow

    def _apply_survivorship_bonuses(self) -> None:
        """Apply bonuses for demonstrated staying power.

        Bonuses are added back to the score:
        - 10+ years in business: +5
        - 20+ years in business: +10
        - Survived economic downturns: +5 (if 10+ years old)
        """
        if self.profile.age_band:
            bonus = survivorship_bonus(self.profile.age_band)
            if bonus > 0:
                self._bonuses["survivorship"] = float(bonus)

    def _apply_age_based_adjustments(self) -> None:
        """Apply age-based adjustments to base score, penalties, and bonuses.

        Similar to confidence scoring, young companies should naturally have lower
        Business Stability scores because:
        - Less financial history to evaluate
        - Higher baseline risk of failure
        - Less proven business model
        - Less track record for financial stability

        Age-based adjustments:
        - startup (<2 years): Base score 70, 1.5x penalties, 0.5x bonuses
        - young (2-5 years): Base score 80, 1.2x penalties, 0.7x bonuses  
        - established (5-10 years): Base score 90, 1.0x penalties, 1.0x bonuses
        - mature (10-20 years): Base score 95, 0.9x penalties, 1.2x bonuses
        - veteran (20+ years): Base score 100, 0.8x penalties, 1.5x bonuses
        - unknown: Base score 85, 1.0x penalties, 1.0x bonuses
        """
        if not self.profile.age_band or self.profile.age_band == "unknown":
            return

        # Age-based multipliers for penalties and bonuses
        age_config = {
            "startup": {
                "penalty_multiplier": 1.5,
                "bonus_multiplier": 0.5,
                "base_adjustment": -30,  # Additional reduction for startups
            },
            "young": {
                "penalty_multiplier": 1.2,
                "bonus_multiplier": 0.7,
                "base_adjustment": -20,  # Additional reduction for young companies
            },
            "established": {
                "penalty_multiplier": 1.0,
                "bonus_multiplier": 1.0,
                "base_adjustment": 0,
            },
            "mature": {
                "penalty_multiplier": 0.9,
                "bonus_multiplier": 1.2,
                "base_adjustment": 0,
            },
            "veteran": {
                "penalty_multiplier": 0.8,
                "bonus_multiplier": 1.5,
                "base_adjustment": 0,
            },
            "unknown": {
                "penalty_multiplier": 1.0,
                "bonus_multiplier": 1.0,
                "base_adjustment": -15,  # Penalty for unknown age
            },
        }

        config = age_config.get(self.profile.age_band, age_config["unknown"])

        # Apply base score adjustment for young companies
        if config["base_adjustment"] != 0:
            self._base_score = max(0, self._base_score + config["base_adjustment"])

        # Apply penalty multiplier to financial penalties
        adjusted_penalties = {}
        for key, value in self._penalties.items():
            if (key.startswith("revenue_") or "debt" in key.lower() or 
                key.startswith("cash_flow_") or key.startswith("historical_insolvency") or
                key.startswith("elevated_") or key == "going_concern_language"):
                adjusted_penalties[key] = value * config["penalty_multiplier"]
            else:
                adjusted_penalties[key] = value

        self._penalties = adjusted_penalties

        # Apply bonus multiplier to survivorship bonuses
        adjusted_bonuses = {}
        for key, value in self._bonuses.items():
            if key == "survivorship":
                adjusted_bonuses[key] = value * config["bonus_multiplier"]
            else:
                adjusted_bonuses[key] = value

        self._bonuses = adjusted_bonuses

    def _years_since(self, date: datetime | None) -> float | None:
        """Calculate years since a given date."""
        if date is None:
            return None
        if date.tzinfo is None:
            date = date.replace(tzinfo=UTC)
        return (datetime.now(UTC) - date).days / 365.25

    def _calculate_revenue_trend(self, metrics: list[FinancialMetrics]) -> str:
        """Calculate revenue trend from time-series metrics.

        Returns: 'growing', 'stable', 'declining', or 'unknown'
        """
        if len(metrics) < 2:
            return "unknown"

        # Sort by period end (oldest first)
        sorted_metrics = sorted(metrics, key=lambda m: m.period_end)

        # Check last 3 periods for declining trend
        recent = sorted_metrics[-3:] if len(sorted_metrics) >= 3 else sorted_metrics

        revenues = [m.revenue for m in recent if m.revenue is not None]
        if len(revenues) < 2:
            return "unknown"

        # Simple trend: if each consecutive period is lower, it's declining
        declining_count = 0
        for i in range(1, len(revenues)):
            if revenues[i] < revenues[i-1]:
                declining_count += 1

        if declining_count == len(revenues) - 1:
            return "declining"
        if declining_count == 0:
            return "growing"
        return "stable"

    def _calculate_debt_to_equity(self, metrics: list[FinancialMetrics]) -> float | None:
        """Calculate debt-to-equity ratio from most recent metrics.

        Returns None if data insufficient.
        """
        if not metrics:
            return None

        # Get most recent metric
        latest = max(metrics, key=lambda m: m.period_end)

        if latest.long_term_debt is None or latest.equity is None or latest.equity == 0:
            return None

        return latest.long_term_debt / latest.equity

    def _compute_age_differentiation_profile(self) -> dict[str, Any] | None:
        """Compute age differentiation profile for this vendor.
        
        This provides age-specific risk assessment across multiple dimensions:
        - Historical depth (corpus richness)
        - Financial transparency (data availability)
        - Leadership risk (founder dependence vs succession)
        - Operational maturity (scaling risk vs degradation)
        - Media velocity (adverse media interpretation)
        - Structural change (corporate structure change suspicion)
        
        Returns:
            Dict with age differentiation profile or None if age_band is unknown
        """
        if not self.profile.age_band or self.profile.age_band == "unknown":
            return None
        
        # Extract data from profile for age differentiation scoring
        years_of_operation = self.profile.operating_years
        
        # Financial transparency data
        has_financial_data = bool(self.profile.financial_metrics)
        revenue_plausible = None  # Would need additional data to determine
        growth_rate = None  # Would need time-series revenue data
        if self.profile.financial_metrics and len(self.profile.financial_metrics) >= 2:
            # Calculate simple growth rate from first and last revenue
            metrics = sorted(self.profile.financial_metrics, key=lambda m: m.period_end)
            first_rev = metrics[0].revenue
            last_rev = metrics[-1].revenue
            if first_rev and last_rev and first_rev > 0:
                years = (metrics[-1].period_end - metrics[0].period_end).days / 365.25
                if years > 0:
                    growth_rate = (last_rev - first_rev) / first_rev / years
        
        # Leadership data (would need additional fields in FinancialProfile)
        founder_history_clean = None
        recent_turnover = False
        succession_plan_evident = False
        
        # Operational maturity data
        infrastructure_age_years = None  # Would need domain/infrastructure age data
        process_maturity_evident = False  # Would need certification data
        scaling_risk_indicators = 0  # Would need scaling indicators
        
        # Media velocity data (would need adverse media tracking)
        adverse_media_count = 0
        recent_spike = False
        trend_direction = None
        years_of_history = years_of_operation
        
        # Structural change data (would need change tracking)
        name_changes = 0
        address_changes = 0
        ownership_changes = 0
        acquisition_activity = False
        
        # Finding count for historical depth (would need to pass in or compute)
        finding_count = 0  # Placeholder - would need actual count
        
        # Compute the profile
        profile = compute_age_differentiation_profile(
            age_band=self.profile.age_band,
            finding_count=finding_count,
            years_of_data=years_of_operation,
            has_financial_data=has_financial_data,
            revenue_plausible=revenue_plausible,
            growth_rate=growth_rate,
            years_of_operation=years_of_operation,
            founder_history_clean=founder_history_clean,
            recent_turnover=recent_turnover,
            succession_plan_evident=succession_plan_evident,
            infrastructure_age_years=infrastructure_age_years,
            process_maturity_evident=process_maturity_evident,
            scaling_risk_indicators=scaling_risk_indicators,
            adverse_media_count=adverse_media_count,
            recent_spike=recent_spike,
            trend_direction=trend_direction,
            years_of_history=years_of_history,
            name_changes=name_changes,
            address_changes=address_changes,
            ownership_changes=ownership_changes,
            acquisition_activity=acquisition_activity,
        )
        
        return {
            "age_band": profile.age_band,
            "overall_age_risk_score": profile.overall_age_risk_score,
            "rationale": profile.rationale,
            "historical_depth": {
                "band": profile.historical_depth.band,
                "score": profile.historical_depth.age_adjusted_score,
                "rationale": profile.historical_depth.rationale,
            },
            "financial_transparency": {
                "band": profile.financial_transparency.band,
                "score": profile.financial_transparency.age_adjusted_score,
                "rationale": profile.financial_transparency.rationale,
            },
            "leadership_risk": {
                "band": profile.leadership_risk.band,
                "score": profile.leadership_risk.risk_score,
                "rationale": profile.leadership_risk.rationale,
            },
            "operational_maturity": {
                "band": profile.operational_maturity.band,
                "score": profile.operational_maturity.maturity_score,
                "rationale": profile.operational_maturity.rationale,
            },
            "media_velocity": {
                "band": profile.media_velocity.band,
                "score": profile.media_velocity.velocity_score,
                "rationale": profile.media_velocity.rationale,
            },
            "structural_change": {
                "band": profile.structural_change.band,
                "score": profile.structural_change.suspicion_score,
                "rationale": profile.structural_change.rationale,
            },
        }

    def _calculate_cash_flow_trend(self, metrics: list[FinancialMetrics]) -> str:
        """Calculate cash flow trend from time-series metrics.

        Returns: 'positive', 'negative', or 'unknown'
        """
        if len(metrics) < 2:
            return "unknown"

        # Use net_income as proxy for cash flow (simplified)
        sorted_metrics = sorted(metrics, key=lambda m: m.period_end)
        recent = sorted_metrics[-2:]

        net_incomes = [m.net_income for m in recent if m.net_income is not None]
        if len(net_incomes) < 2:
            return "unknown"

        # If both recent periods are negative, it's negative trend
        if all(ni < 0 for ni in net_incomes):
            return "negative"
        if all(ni > 0 for ni in net_incomes):
            return "positive"
        return "unknown"


def compute_business_stability(
    profile: FinancialProfile,
    base_confidence: float = 1.0,
) -> dict[str, Any]:
    """Compute Business Stability score for a vendor.

    This is the main entry point for Business Stability scoring.

    Args:
        profile: FinancialProfile with incorporation_date, insolvency_records,
                 and financial_metrics populated
        base_confidence: Base confidence from evidence coverage (0-1)

    Returns:
        Dict with score, penalties, bonuses, gate status, and age adjustments
    """
    # Compute age modifiers
    age_score, adjusted_confidence = apply_age_modifiers(profile, base_confidence)

    # Compute Business Stability score
    engine = BusinessStabilityScore(profile)
    result = engine.compute()

    # Add confidence adjustment to result
    result["confidence_adjusted"] = adjusted_confidence

    # Determine if contingency plan is required
    if profile.age_band:
        result["contingency_plan_required"] = contingency_plan_required(
            profile.age_band,
            getattr(profile, "criticality", None),
        )
    else:
        result["contingency_plan_required"] = False

    return result
