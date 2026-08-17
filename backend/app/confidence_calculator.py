"""Age-based confidence calculator - implements the (expected & found) / expected methodology.

This module replaces the flat penalty approach with a sophisticated confidence calculation
that scales expectations based on company age, size, and jurisdiction.

Key principles:
- Confidence = (sum of weights for expected signals that were found) / (sum of weights for expected signals)
- Signals not yet expected for a company's profile don't hurt confidence
- Found-but-not-expected signals are excluded from the ratio (capped at 100%)
- Search failures are tracked separately and don't penalize confidence
- Jurisdiction-specific signals are only expected where applicable
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from .confidence_config import (
    AgeBand,
    SizeBand,
    get_expected_signals,
    get_total_expected_weight,
    is_signal_expected,
    size_band_from_profile,
    SIGNAL_CATEGORIES,
)
from .longevity import age_band_from_years


class SignalStatus(Enum):
    """The status of a signal collection attempt."""
    FOUND = "found"                    # Successfully found and validated
    NOT_FOUND = "not_found"            # Searched and genuinely absent (counts against confidence)
    SEARCH_FAILED = "search_failed"    # Collection failed (excluded from confidence)
    NOT_APPLICABLE = "not_applicable"  # Doesn't apply to this company (excluded from confidence)
    NOT_CHECKED = "not_checked"        # Wasn't attempted (excluded from confidence)


@dataclass
class SignalResult:
    """Result of collecting a single signal."""
    
    signal_name: str
    status: SignalStatus
    weight: float
    is_expected: bool
    notes: str | None = None
    deduction_label: str = ""  # Human-readable label for confidence deduction
    deduction_category: str = ""  # Category for grouping deductions


@dataclass
class ConfidenceResult:
    """Result of confidence calculation."""
    
    confidence_score: float  # 0.0 to 1.0
    confidence_band: Literal["High", "Medium", "Low"]
    total_expected_weight: float
    found_expected_weight: float
    signal_results: list[SignalResult]
    age_band: AgeBand
    size_band: SizeBand
    operating_years: float | None
    jurisdiction: str | None
    
    # Additional context for debugging
    unexpected_bonuses: list[str]  # Signals found but not expected (positive signals)
    coverage_gaps: list[str]        # Expected signals that were missing
    search_failures: list[str]       # Signals that failed to collect
    
    # NEW: Clear deduction labels for user-facing display
    deduction_labels: list[dict[str, str]]  # Human-readable deduction reasons
    deductions_by_category: dict[str, list[dict[str, str]]]  # Grouped deductions
    
    @property
    def coverage_percentage(self) -> float:
        """Coverage as a percentage (0-100)."""
        return self.confidence_score * 100
    
    def get_summary(self) -> str:
        """Generate a human-readable summary of the confidence calculation."""
        lines = [
            f"Confidence: {self.coverage_percentage:.1f}% ({self.confidence_band})",
            f"Age Band: {self.age_band}",
            f"Size Band: {self.size_band}",
            f"Expected Signals Weight: {self.total_expected_weight:.1f}",
            f"Found Expected Weight: {self.found_expected_weight:.1f}",
        ]
        
        if self.coverage_gaps:
            lines.append(f"Coverage Gaps: {', '.join(self.coverage_gaps)}")
        
        if self.unexpected_bonuses:
            lines.append(f"Unexpected Bonuses: {', '.join(self.unexpected_bonuses)}")
        
        if self.search_failures:
            lines.append(f"Search Failures: {', '.join(self.search_failures)}")
        
        if self.deduction_labels:
            lines.append("Confidence Deductions:")
            for deduction in self.deduction_labels:
                lines.append(f"  - {deduction['label']} ({deduction['category']}, -{deduction['weight']:.1f} points)")
        
        return "\n".join(lines)
    
    def get_deduction_labels_for_display(self) -> list[dict[str, str]]:
        """Get formatted deduction labels for user-facing display.
        
        Returns a list of deduction reasons sorted by impact (weight) that can be
        displayed in the UI to explain why confidence was reduced.
        """
        if not self.deduction_labels:
            return []
        
        # Sort by weight (highest impact first)
        sorted_deductions = sorted(self.deduction_labels, key=lambda x: x['weight'], reverse=True)
        
        return [
            {
                "label": deduction['label'],
                "category": deduction['category'],
                "weight": deduction['weight'],
                "signal": deduction['signal'],
                "impact": "high" if deduction['weight'] >= 15 else "medium" if deduction['weight'] >= 8 else "low",
            }
            for deduction in sorted_deductions
        ]
    
    def get_deductions_by_category(self) -> dict[str, list[dict[str, str]]]:
        """Get deductions grouped by category for organized display.
        
        Returns a dict mapping category names to lists of deduction reasons.
        """
        return self.deductions_by_category


class ConfidenceCalculator:
    """Calculates age-based confidence scores using the (expected & found) / expected methodology."""
    
    def __init__(self):
        self.signal_categories = SIGNAL_CATEGORIES
    
    def calculate_confidence(
        self,
        signal_statuses: dict[str, SignalStatus],
        age_band: AgeBand,
        size_band: SizeBand = "unknown",
        operating_years: float | None = None,
        jurisdiction: str | None = None,
    ) -> ConfidenceResult:
        """Calculate confidence score based on signal collection results.
        
        Args:
            signal_statuses: Dict mapping signal names to their collection status
            age_band: Company's age band
            size_band: Company's size band
            operating_years: Actual operating years (if available)
            jurisdiction: Company's jurisdiction (for jurisdiction-specific signals)
        
        Returns:
            ConfidenceResult with detailed breakdown
        """
        # Determine which signals are expected for this profile
        expected_signals = get_expected_signals(age_band, size_band, operating_years, jurisdiction)

        # THE DENOMINATOR IS WHAT WE ACTUALLY ASSESSED, not everything the profile expects.
        #
        # It used to be `get_total_expected_weight(...)` — the whole expected set — while the
        # numerator only counted signals present in `signal_statuses`. That made two of this
        # module's three documented promises false at once:
        #
        #   * "Search failures are tracked separately and don't penalize confidence" — a
        #     SEARCH_FAILED signal left the numerator but STAYED in the denominator, so a collector
        #     outage was arithmetically identical to the vendor not having the control. That is the
        #     precise confusion the whole two-axis design exists to prevent, reappearing INSIDE the
        #     confidence axis: our failure to look, charged to them.
        #   * "Signals not yet expected ... don't hurt confidence" / "NOT_CHECKED is excluded" —
        #     a signal absent from the map was excluded from the numerator only.
        #
        # So the denominator is accumulated below over exactly the signals that are EXPECTED and
        # were genuinely assessed (FOUND or NOT_FOUND). NOT_APPLICABLE, NOT_CHECKED, SEARCH_FAILED
        # and signals never passed in leave BOTH sides of the ratio.
        #
        # THIS DOES NOT MOVE ANY PUBLISHED SCORE. On the pipeline path every planned signal is
        # seeded and resolved to FOUND or NOT_FOUND before this runs, so the accumulated
        # denominator equals the full expected weight, exactly as before. It changes the answer
        # only where a caller assesses a subset — which is what the unit tests do, and why they
        # were failing against a contract the docstring already stated.
        assessed_expected_weight = 0.0

        # Process each signal
        signal_results = []
        found_expected_weight = 0.0
        unexpected_bonuses = []
        coverage_gaps = []
        search_failures = []
        deduction_labels = []
        deductions_by_category: dict[str, list[dict[str, str]]] = {}
        
        for signal_name, status in signal_statuses.items():
            category = self.signal_categories.get(signal_name)
            if not category:
                continue  # Skip unknown signals
            
            is_expected = is_signal_expected(signal_name, age_band, size_band, operating_years, jurisdiction)
            
            result = SignalResult(
                signal_name=signal_name,
                status=status,
                weight=category.weight,
                is_expected=is_expected,
                deduction_label=category.deduction_label,
                deduction_category=category.deduction_category,
            )
            
            # Only an EXPECTED signal that was genuinely assessed enters the denominator.
            if is_expected and status in (SignalStatus.FOUND, SignalStatus.NOT_FOUND):
                assessed_expected_weight += category.weight

            # Handle different statuses
            if status == SignalStatus.FOUND:
                if is_expected:
                    # Expected and found - counts toward confidence
                    found_expected_weight += category.weight
                else:
                    # Found but not expected - bonus signal, doesn't count toward confidence
                    unexpected_bonuses.append(signal_name)
            
            elif status == SignalStatus.NOT_FOUND:
                if is_expected:
                    # Expected but missing - real coverage gap
                    coverage_gaps.append(signal_name)
                    
                    # Add human-readable deduction label
                    deduction_info = {
                        "signal": signal_name,
                        "label": category.deduction_label,
                        "category": category.deduction_category,
                        "weight": category.weight,
                        "reason": f"Expected for {age_band} companies but not found"
                    }
                    deduction_labels.append(deduction_info)
                    
                    # Group by category
                    if category.deduction_category not in deductions_by_category:
                        deductions_by_category[category.deduction_category] = []
                    deductions_by_category[category.deduction_category].append(deduction_info)
                # If not expected, not finding it is fine - no action needed
            
            elif status == SignalStatus.SEARCH_FAILED:
                # Collection failure - exclude from confidence but track for visibility
                search_failures.append(signal_name)
            
            elif status == SignalStatus.NOT_APPLICABLE:
                # Doesn't apply - exclude from both numerator and denominator
                pass
            
            elif status == SignalStatus.NOT_CHECKED:
                # Wasn't attempted - exclude from confidence
                pass
            
            signal_results.append(result)
        
        # Calculate confidence score against the assessed-expected denominator.
        total_expected_weight = assessed_expected_weight
        if total_expected_weight > 0:
            confidence_score = found_expected_weight / total_expected_weight
        else:
            # NOTHING EXPECTED WAS ASSESSED. Reported as 1.0 to preserve the existing contract for
            # a profile that legitimately expects nothing; note that on the pipeline path this
            # branch is unreachable, because every planned signal resolves to FOUND or NOT_FOUND.
            confidence_score = 1.0
        
        # Cap at 1.0 (100%)
        confidence_score = min(1.0, confidence_score)
        
        # Determine confidence band
        confidence_band = self._confidence_band(confidence_score)
        
        return ConfidenceResult(
            confidence_score=confidence_score,
            confidence_band=confidence_band,
            total_expected_weight=total_expected_weight,
            found_expected_weight=found_expected_weight,
            signal_results=signal_results,
            age_band=age_band,
            size_band=size_band,
            operating_years=operating_years,
            jurisdiction=jurisdiction,
            unexpected_bonuses=unexpected_bonuses,
            coverage_gaps=coverage_gaps,
            search_failures=search_failures,
            deduction_labels=deduction_labels,
            deductions_by_category=deductions_by_category,
        )
    
    def _confidence_band(self, score: float) -> Literal["High", "Medium", "Low"]:
        """Convert confidence score to band."""
        if score >= 0.90:
            return "High"
        elif score >= 0.70:
            return "Medium"
        else:
            return "Low"
    
    def calculate_from_findings(
        self,
        findings: list,  # NormalizedFinding objects from scoring engine
        age_band: AgeBand,
        size_band: SizeBand = "unknown",
        operating_years: float | None = None,
        jurisdiction: str | None = None,
        planned_signals: set[str] | None = None,
    ) -> ConfidenceResult:
        """Calculate confidence from actual findings (pipeline integration).
        
        This is the main integration point with the existing scoring pipeline.
        
        Args:
            findings: List of NormalizedFinding objects from the scoring engine
            age_band: Company's age band
            size_band: Company's size band
            operating_years: Actual operating years
            jurisdiction: Company's jurisdiction
            planned_signals: Set of signals that were planned for collection
        
        Returns:
            ConfidenceResult with detailed breakdown
        """
        # Convert findings to signal statuses
        signal_statuses: dict[str, SignalStatus] = {}
        
        # Mark all planned signals as checked
        if planned_signals:
            for signal in planned_signals:
                signal_statuses[signal] = SignalStatus.NOT_CHECKED
        
        # Update based on actual findings
        for finding in findings:
            signal_name = finding.signal
            
            # Determine status based on finding
            if hasattr(finding, 'effective_penalty') and finding.effective_penalty == 0:
                # Clean finding = signal found and passing
                signal_statuses[signal_name] = SignalStatus.FOUND
            elif hasattr(finding, 'effective_penalty') and finding.effective_penalty > 0:
                # Finding with penalty = signal found but failing
                signal_statuses[signal_name] = SignalStatus.FOUND  # Still counts as found
            elif hasattr(finding, 'severity_base') and finding.severity_base == 0:
                # Informational finding = signal found
                signal_statuses[signal_name] = SignalStatus.FOUND
            else:
                # No finding or error = not found
                signal_statuses[signal_name] = SignalStatus.NOT_FOUND
        
        # Handle signals that were planned but had no findings.
        #
        # THE TEST HERE IS `NOT_CHECKED`, NOT `not in signal_statuses`. Every planned signal was
        # seeded as NOT_CHECKED above, so a membership test can never be true and this loop was
        # dead: a planned signal that returned nothing stayed NOT_CHECKED, which
        # `calculate_confidence` deliberately EXCLUDES from the gap list. The confidence figure was
        # unaffected (the denominator is the profile's expected weight, not the status map), but
        # every gap and every deduction label came back empty — so the endpoint whose entire purpose
        # is explaining a low confidence explained nothing.
        #
        # PLANNED MEANS ATTEMPTED. A signal this run intended to collect and got no finding for is
        # genuinely absent, and absence is the thing a reader needs itemised. Only signals the run
        # never planned stay NOT_CHECKED.
        if planned_signals:
            for signal in planned_signals:
                if signal_statuses.get(signal) is SignalStatus.NOT_CHECKED:
                    signal_statuses[signal] = SignalStatus.NOT_FOUND
        
        return self.calculate_confidence(
            signal_statuses=signal_statuses,
            age_band=age_band,
            size_band=size_band,
            operating_years=operating_years,
            jurisdiction=jurisdiction,
        )
    
    def calculate_from_profile(
        self,
        findings: list,
        profile,  # VendorProfile or Vendor object
        planned_signals: set[str] | None = None,
    ) -> ConfidenceResult:
        """Calculate confidence from a vendor profile (convenience method).
        
        Args:
            findings: List of NormalizedFinding objects
            profile: VendorProfile or Vendor with age, size, jurisdiction info
            planned_signals: Set of planned signals
        
        Returns:
            ConfidenceResult with detailed breakdown
        """
        # Extract profile information - handle both Vendor and VendorProfile objects
        operating_years = None
        if hasattr(profile, 'operating_years') and profile.operating_years is not None:
            operating_years = profile.operating_years
        
        age_band = age_band_from_years(operating_years) if operating_years else "unknown"
        
        size_band = "unknown"
        if hasattr(profile, 'size_band') and profile.size_band:
            if hasattr(profile.size_band, 'value'):
                size_band = size_band_from_profile(profile.size_band.value)
            else:
                size_band = size_band_from_profile(str(profile.size_band))
        
        jurisdiction = None
        if hasattr(profile, 'sector') and profile.sector:
            if hasattr(profile.sector, 'value'):
                jurisdiction = profile.sector.value
            else:
                jurisdiction = str(profile.sector)
        
        return self.calculate_from_findings(
            findings=findings,
            age_band=age_band,
            size_band=size_band,
            operating_years=operating_years,
            jurisdiction=jurisdiction,
            planned_signals=planned_signals,
        )


def calculate_age_based_confidence(
    findings: list,
    profile,
    planned_signals: set[str] | None = None,
) -> ConfidenceResult:
    """Convenience function to calculate age-based confidence.
    
    This is the main entry point for integration with the existing pipeline.
    
    Args:
        findings: List of NormalizedFinding objects from scoring engine
        profile: VendorProfile with company information
        planned_signals: Set of signals that were planned for collection
    
    Returns:
        ConfidenceResult with detailed breakdown
    """
    calculator = ConfidenceCalculator()
    return calculator.calculate_from_profile(findings, profile, planned_signals)