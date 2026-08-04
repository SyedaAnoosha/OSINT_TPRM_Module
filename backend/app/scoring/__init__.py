"""Scoring engine (Phase 2) — the deliverable, in code.

Pipeline (scoring.yaml PIPELINE ORDER, not negotiable):
    findings -> normalize (band lookup) -> NIST SP 1326 modifiers -> signal score
    -> subcategory mean -> category mean -> GATE -> overall mean (scored, present)
    -> KNOCKOUT FLOOR -> confidence + quadrant

Modules:
    modifiers   NIST SP 1326 age/frequency/mitigation (pure functions)
    normalize   Finding -> ScoredFinding (band -> base severity, carries evidence ref)
    engine      roll-up + gate + floor + confidence + quadrant -> Score
"""

from .engine import ScoreResult, ScoringEngine

__all__ = ["ScoreResult", "ScoringEngine"]
