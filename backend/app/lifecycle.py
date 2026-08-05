"""Lifecycle context — organisational stage and key-person risk, read from the profile.

WHY THIS EXISTS. `continuity.py` explicitly records that age belongs in three places: the
confidence assurance_multiplier (scoring.yaml), the attainability rule (benchmarks.yaml),
and cohort assignment. This is the FOURTH home: the display layer, for a reader who needs
to know they are looking at a 2-year-old vendor, not merely a vendor with a lower confidence
multiplier they cannot see.

The assurance_multiplier already moves a number. This module names what moved it. A reader
who sees a confidence of 0.97 deserves a sentence explaining that it is 0.97 because the
entity has operated for under two years, not because collectors failed.

KEY-PERSON RISK is derived here rather than inferred from a collector because no free source
publishes individual dependency concentration. What WE CAN observe is headcount scale from
Wikidata — a proxy for how many people a service delivery could depend on. It is a weak
proxy deliberately reported as a flag with a stated basis, not as a scored finding.

TECH OBSOLESCENCE FRAMING aggregates signals the scoring engine already charged for (TLS
version, KEV matches) and presents them as path-dependency context. It adds no new arithmetic;
it re-labels existing findings for a reader who needs to understand WHAT the penalty means
in the context of a 40-year-old vendor's legacy infrastructure.

DISCLOSED, NEVER SCORED. Like `continuity.py` and `fourth_party.py`, this module:
  - adds no source
  - emits no finding
  - writes nothing to the store
  - cannot reach the scoring engine
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import LifecycleStage, PersistedFinding

# ---------------------------------------------------------------------------
# Tech signals that, when present, indicate path-dependency / aged infrastructure.
# These are ALREADY scored by the engine; this module only re-frames them as context.
# ---------------------------------------------------------------------------
_OBSOLESCENCE_SIGNALS: dict[tuple[str, str], str] = {
    ("tls_version", "tls_10_or_11"): "TLS 1.0/1.1 still offered — deprecated since RFC 8996 (2021).",
    ("kev_listed_cve", "listed"): "CISA Known Exploited Vulnerability match — "
                                   "typically indicates unpatched legacy components.",
}

# Key-person threshold. A vendor with ≤ this headcount in a high-criticality relationship
# warrants the flag. Not a score; a flag with a stated basis.
_KEY_PERSON_HEADCOUNT_THRESHOLD = 10

_CAVEATS = [
    "Lifecycle stage is derived from operating years (entity inception or domain age) and is "
    "context only. It is NOT a score and does not affect posture. A young company is not "
    "thereby an impaired counterparty — that is the founding-date scoring this system refuses.",
    "Key-person risk is derived from observable headcount proxies only. Internal talent "
    "dependencies are not observable from outside; headcount is a scale proxy, not a "
    "concentration measure. See coverage_statement.py's never-observable list.",
    "Technology obsolescence indicators re-frame findings the scoring engine already charged "
    "for. They add no new arithmetic — they are labels for findings a reader may otherwise "
    "read as isolated control gaps rather than as systemic infrastructure age.",
]


@dataclass(frozen=True)
class ObsolescenceSignal:
    """One re-framed existing finding."""
    signal: str
    band: str
    description: str
    evidence_id: str | None
    finding_id: str | None


@dataclass(frozen=True)
class LifecycleReport:
    """Lifecycle context for one vendor. Computed on read, stored nowhere."""
    vendor_ref: str
    lifecycle_stage: LifecycleStage
    operating_years: float | None
    # Key-person risk
    key_person_risk: bool
    key_person_basis: str | None
    # Tech obsolescence (re-framed from existing findings)
    obsolescence_signals: list[ObsolescenceSignal]
    caveats: list[str]

    @property
    def stage_label(self) -> str:
        return {
            "infancy":     "Infancy — under 1 year of operation",
            "go_go":       "Go-Go — 1–2 years, rapid growth phase",
            "adolescence": "Adolescence — 2–5 years, structure forming",
            "prime":       "Prime — 5–15 years, peak balance of control and flexibility",
            "aging":       "Aging — over 15 years, established but path-dependency risk",
            "unknown":     "Unknown — no reliable inception date available",
        }.get(self.lifecycle_stage, self.lifecycle_stage)

    @property
    def risk_profile_note(self) -> str:
        """Plain-English note about what this stage means for a TPRM buyer."""
        return {
            "infancy": (
                "Structural risks: financial fragility (no revenue history), compliance "
                "immaturity (no time for SOC 2 observation window), key-person dependency. "
                "Note attainable_after_years in target maturity — some controls cannot yet exist."
            ),
            "go_go": (
                "Rapid growth phase: processes are forming. Financial model may still be "
                "unproven. Compliance infrastructure typically incomplete."
            ),
            "adolescence": (
                "Structure is emerging but not yet stable. Governance improvements expected. "
                "Cohort benchmarking against similarly-aged peers is more meaningful than "
                "comparison with mature incumbents."
            ),
            "prime": (
                "Peak operational balance. Established processes and governance. Monitor for "
                "emerging path-dependency as legacy decisions accumulate."
            ),
            "aging": (
                "Institutional knowledge and process depth are strengths. Path-dependency risk: "
                "technology lock-in, legacy infrastructure, and structural inertia can slow "
                "incident response and adaptation. See obsolescence signals below."
            ),
            "unknown": (
                "No reliable operating history available. Treat as emerging for assessment "
                "purposes; attainable_after_years exemptions do not apply."
            ),
        }.get(self.lifecycle_stage, "")


def lifecycle_stage_from_years(operating_years: float | None) -> LifecycleStage:
    """Map operating years to an Adizes-derived stage label.

    Thresholds are approximate — the model does not publish hard boundaries. These are
    calibrated to the five bands already in scoring.yaml's `entity_maturity` signal:
    new_lt_1 / startup_lt_2 / young_2_5 / established_5_10 / mature_gt_10, widened at
    the top (>10 stays 'prime' until 15, beyond which institutional path-dependency
    typically dominates). Adjust here; there is no other place.
    """
    if operating_years is None:
        return "unknown"
    if operating_years < 1.0:
        return "infancy"
    if operating_years < 2.0:
        return "go_go"
    if operating_years < 5.0:
        return "adolescence"
    if operating_years < 15.0:
        return "prime"
    return "aging"


def lifecycle_report(
    vendor_ref: str,
    operating_years: float | None,
    headcount: int | None,
    criticality: str | None,
    findings: list[PersistedFinding],
) -> LifecycleReport:
    """Build the lifecycle context from profile facts and already-stored findings.

    Never writes to the store. Never adds a finding. Never touches posture.
    """
    stage = lifecycle_stage_from_years(operating_years)

    # Key-person: micro headcount + high criticality relationship
    key_person_risk = False
    key_person_basis: str | None = None
    if (
        headcount is not None
        and headcount <= _KEY_PERSON_HEADCOUNT_THRESHOLD
        and criticality == "high"
    ):
        key_person_risk = True
        key_person_basis = (
            f"Headcount ≤{_KEY_PERSON_HEADCOUNT_THRESHOLD} (observed: {headcount}) in a "
            f"high-criticality relationship. A small number of departures could impair "
            f"service delivery. This is a proxy observation — internal dependency "
            f"concentration is not externally observable."
        )

    # Tech obsolescence: re-frame existing scored findings as path-dependency context
    obs_signals: list[ObsolescenceSignal] = []
    for f in findings:
        desc = _OBSOLESCENCE_SIGNALS.get((f.signal, f.band_key))
        if desc:
            obs_signals.append(ObsolescenceSignal(
                signal=f.signal,
                band=f.band_key,
                description=desc,
                evidence_id=f.evidence_id,
                finding_id=f.id,
            ))

    return LifecycleReport(
        vendor_ref=vendor_ref,
        lifecycle_stage=stage,
        operating_years=operating_years,
        key_person_risk=key_person_risk,
        key_person_basis=key_person_basis,
        obsolescence_signals=obs_signals,
        caveats=list(_CAVEATS),
    )