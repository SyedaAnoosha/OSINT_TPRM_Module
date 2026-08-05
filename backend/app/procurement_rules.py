"""Procurement rules — deterministic advisory text from Business Stability standing.

WHY THIS EXISTS. The feedback asked for financial signals to drive concrete action without becoming
a number. This module maps `Continuity.standing` (ceased/impaired/watch/sound/unknown) to
procurement-advisory text that a buyer can act on. It is separate from both posture and standing,
so the financial signal drives action without contaminating the security score.

LEGAL REVIEW REQUIRED. The advisory wording in `_RULES` needs legal/compliance sign-off before
shipping — it's advisory language a procurement team will act on, not an internal engineering
string. This module ships the *mechanism*; the *wording* must be reviewed.

NOT A SCORE. These rules produce TEXT, not numbers. They are lookups, not calculations. The
output is meant for the RecommendationsPanel (Phase 3), surfaced alongside remediation guidance.
"""

from __future__ import annotations

from dataclasses import dataclass

# Mapping from Continuity.standing to procurement advisory text. Each entry is a tuple of
# (headline, detail) — the headline is the Tier-2 summary, the detail is the full advisory.
#
# LEGAL REVIEW FLAG: Every string below needs legal/compliance review before production use.
# These are procurement recommendations that could affect contracting decisions.
_RULES = {
    "ceased": (
        "Do not proceed to contract",
        "This entity is recorded as dissolved, in liquidation, or under winding-up proceedings. "
        "Do not proceed to contract without evidence of a successor entity or novation. "
        "Route to legal for successor/novation review.",
    ),
    "impaired": (
        "Immediate continuity risk — escalate before renewal",
        "An administrator or receiver has been appointed, or the domain registration is suspended. "
        "Immediate continuity risk — escalate to security and legal before renewal or expansion. "
        "Request updated register extract and continuity plan.",
    ),
    "watch": (
        "Request updated register extract before signing",
        "Registration has lapsed, domain is expiring soon, or a new high secured-charge filing "
        "has been recorded. Request an updated register extract and confirmation of renewal "
        "before signing or renewing.",
    ),
    "sound": (
        "No continuity concerns identified",
        "No adverse filings identified from public registers within the lookback window. "
        "No continuity concerns identified from public registers.",
    ),
    "unknown": (
        "Business Stability could not be evidenced",
        "No coverage for this vendor's jurisdiction, or all collectors returned empty. "
        "Treat as unknown, not as clean — absence of data is not evidence of health. "
        "Consider manual registry check or request certificate of good standing.",
    ),
}


@dataclass(frozen=True)
class ProcurementRule:
    """One procurement advisory rule."""

    standing: str              # the Continuity.standing this rule applies to
    headline: str              # short summary for Tier-2 display
    detail: str                # full advisory text for RecommendationsPanel
    blocking: bool = False     # True if this should gate procurement workflow


def get_procurement_advice(standing: str) -> ProcurementRule:
    """Return the procurement advisory rule for the given Continuity.standing.

    Args:
        standing: One of "ceased", "impaired", "watch", "sound", "unknown"

    Returns:
        ProcurementRule with headline, detail, and blocking flag

    Raises:
        ValueError: If standing is not recognized
    """
    if standing not in _RULES:
        raise ValueError(f"Unknown standing: {standing}. Must be one of {list(_RULES.keys())}")

    headline, detail = _RULES[standing]
    blocking = standing in {"ceased", "impaired"}

    return ProcurementRule(
        standing=standing,
        headline=headline,
        detail=detail,
        blocking=blocking,
    )


def all_rules() -> list[ProcurementRule]:
    """Return all procurement rules, for documentation/reference purposes."""
    return [get_procurement_advice(standing) for standing in _RULES.keys()]


# Public API surface for the RecommendationsPanel to consume
__all__ = ["ProcurementRule", "get_procurement_advice", "all_rules"]