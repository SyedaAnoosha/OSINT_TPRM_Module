"""Assurity (E9a) — the third axis: how much independent assurance does this vendor actually have?

THE QUESTION POSTURE CANNOT ANSWER. "Their TLS is current and they have no known breaches" and
"an independent auditor has examined their controls" are different claims, and a buyer needs both.
Until E9 the model expressed the second by SUBTRACTING for its absence — `cert_posture.none_claimed`
cost 8 points and fired on five of five corpus vendors. That is a tax on audit budget, not a
measure of risk, and it falls hardest on exactly the small suppliers this product exists to assess
fairly. E2 stopped the charging. This is the half that was always missing.

    Assurity = 100 * sigmoid( A0 + SUM_j credit_j - SUM_k gamma * ComplianceGap_k )

ABSENCE NEVER SUBTRACTS — enforced, not merely intended. `_validate` rejects a negative credit at
load. A vendor with nothing observable sits at the intercept, which is deliberately LOW rather than
zero, because unevidenced is not disproved and a 0 would read as "audited and failed".

THE ONLY THING THAT SUBTRACTS IS A COMPLIANCE GAP, and a gap is not an absence: it is a vendor
asserting a framework and being observed failing one of its controls (E9c). That is a statement
about the reliability of their own claims, which is precisely what this axis measures.

WHY A SIGMOID RATHER THAN A SUM. Bounded without a cliff at either end: the twentieth certification
cannot buy what the second did, and no vendor is ever pinned at 0 or 100 — so the axis keeps
resolving differences at both extremes, which is the defect E13 is being written to fix for Posture.

WHY IT IS A SEPARATE AXIS AND NOT A POSTURE BONUS. Credit for publishing a trust page must never
buy back points lost to an expired certificate. Keeping them apart is what stops assurance
theatre from becoming a security score, and it is the same discipline that keeps Confidence out of
Posture.

BELOW `min_observed_signals` WE PUBLISH NOTHING. "2 of 3" assembled from whichever signals happened
to return is the same false precision as a median over three peers — the discipline `targets.py`
already applies, carried here deliberately.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .scoring_config import ScoringConfig, get_scoring_config


@dataclass(frozen=True)
class AssurityInput:
    """One observation that moved the axis, and by how much. The report is the sum of these."""

    signal: str
    band_key: str
    credit: float
    evidence_id: str | None = None

    def cited(self) -> str:
        return f"{self.signal} = {self.band_key} (+{self.credit:.2f})"


@dataclass
class AssurityReport:
    vendor_ref: str
    score: int | None                       # 0-100, or None when too little was observed
    observed_signals: int
    inputs: list[AssurityInput] = field(default_factory=list)
    gap_penalty: float = 0.0
    gap_count: int = 0
    caveats: list[str] = field(default_factory=list)

    @property
    def published(self) -> bool:
        return self.score is not None


def sigmoid(x: float) -> float:
    # Written this way rather than as 1/(1+exp(-x)) so a large negative x cannot overflow exp().
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def assurity_report(vendor_ref: str, findings: list[Any], *,
                    compliance_gap_count: int = 0,
                    cfg: ScoringConfig | None = None) -> AssurityReport:
    """Score the assurance axis from the observations that evidence it.

    `findings` are NormalizedFindings, or anything carrying `.signal`, `.band_key` and
    `.evidence_id`. Only signals with a configured credit are read; everything else is ignored
    rather than counted as a zero, because a signal that carries no assurance meaning must not
    dilute an axis that is about assurance.
    """
    cfg = cfg or get_scoring_config()
    spec = cfg.data.get("assurity") or {}

    if not spec.get("enabled", False):
        return AssurityReport(vendor_ref=vendor_ref, score=None, observed_signals=0,
                              caveats=["Assurity is not enabled in this deployment."])

    credits: dict[str, dict[str, float]] = spec.get("credit") or {}
    inputs: list[AssurityInput] = []
    observed = 0

    for f in findings:
        table = credits.get(f.signal)
        if table is None:
            continue
        observed += 1                      # the signal was CHECKED — that is what counts here
        credit = table.get(f.band_key)
        if credit is None:
            continue                       # checked, and evidenced nothing. Not a subtraction.
        inputs.append(AssurityInput(signal=f.signal, band_key=f.band_key, credit=float(credit),
                                    evidence_id=getattr(f, "evidence_id", None)))

    caveats = [
        "Assurity measures INDEPENDENT ASSURANCE, not security. A low score means little "
        "externally verifiable evidence of an audited security programme — it does not mean the "
        "vendor's controls are weak, and it must never be read as a posture score.",
        "Absence never subtracts on this axis. A vendor with no observable assurance sits at the "
        "floor because they are unevidenced, not because they were examined and failed.",
    ]

    minimum = int(spec.get("min_observed_signals", 0))
    if observed < minimum:
        caveats.insert(0, (
            f"Not published: {observed} of the {minimum} assurance signals needed were observed. "
            f"A score assembled from whichever checks happened to return is false precision."
        ))
        return AssurityReport(vendor_ref=vendor_ref, score=None, observed_signals=observed,
                              inputs=inputs, gap_count=compliance_gap_count, caveats=caveats)

    gamma = float(spec.get("gamma", 0.0))
    gap_penalty = gamma * compliance_gap_count
    x = (float(spec.get("intercept", 0.0))
         + sum(i.credit for i in inputs) * float(spec.get("scale", 1.0))
         - gap_penalty)

    if compliance_gap_count:
        caveats.append(
            f"{compliance_gap_count} compliance gap(s) reduced this score. A gap is the vendor "
            f"asserting a framework and being observed failing one of its controls — a "
            f"claim-reliability finding, which is what this axis is for."
        )

    return AssurityReport(
        vendor_ref=vendor_ref,
        score=int(round(100 * sigmoid(x))),
        observed_signals=observed,
        inputs=sorted(inputs, key=lambda i: -i.credit),
        gap_penalty=gap_penalty,
        gap_count=compliance_gap_count,
        caveats=caveats,
    )
