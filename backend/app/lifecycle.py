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
# Descriptions are age-aware: the same finding means something different for young vs mature vendors.
# ---------------------------------------------------------------------------
def _obsolescence_description(signal: str, band: str, operating_years: float | None) -> str:
    """Return age-aware description for obsolescence signals.

    A TLS 1.0 finding on a 2-year-old vendor is a config decision (unusual, fixable).
    A TLS 1.0 finding on a 20-year-old vendor is path-dependency (legacy debt, harder to fix).
    """
    if signal == "tls_version" and band == "tls_10_or_11":
        if operating_years is None:
            return "TLS 1.0/1.1 still offered — deprecated since RFC 8996 (2021)."
        if operating_years < 3:
            return (
                "TLS 1.0/1.1 still offered — unusual for a young vendor, indicates a specific "
                "configuration decision rather than legacy debt. Remediation is a config change."
            )
        elif operating_years < 10:
            return (
                "TLS 1.0/1.1 still offered — atypical for this age. May indicate legacy "
                "infrastructure or delayed modernization. Remediation may require system upgrades."
            )
        else:
            return (
                "TLS 1.0/1.1 still offered — likely path-dependency from legacy infrastructure. "
                "Mature vendors accumulate technical debt; this finding may indicate old services "
                "never modernized. Remediation may require system replacement, not just config."
            )
    elif signal == "kev_listed_cve" and band == "listed":
        if operating_years is None:
            return "CISA Known Exploited Vulnerability match — typically indicates unpatched legacy components."
        if operating_years < 3:
            return (
                "CISA Known Exploited Vulnerability match — uncommon for a young vendor with modern "
                "stack. Indicates either inherited vulnerable components or delayed patching."
            )
        elif operating_years < 10:
            return (
                "CISA Known Exploited Vulnerability match — suggests patch cadence gaps or use of "
                "vulnerable third-party components. Review patch management practices."
            )
        else:
            return (
                "CISA Known Exploited Vulnerability match — likely path-dependency from legacy "
                "components. Mature vendors often have accumulated technical debt; this may indicate "
                "end-of-life systems or constrained modernization budgets."
            )
    return f"{signal} / {band} — obsolescence indicator"

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
                "Note attainable_after_years in target maturity — some controls cannot yet exist. "
                "DMARC/TLS gaps are greenfield misses: security hygiene not embedded in founding habits."
            ),
            "go_go": (
                "Rapid growth phase: processes are forming. Financial model may still be "
                "unproven. Compliance infrastructure typically incomplete. DMARC/TLS gaps "
                "indicate security not prioritized during growth. SOC 2 Type 2 unlikely (insufficient "
                "observation window)."
            ),
            "adolescence": (
                "Structure is emerging but not yet stable. Governance improvements expected. "
                "Cohort benchmarking against similarly-aged peers is more meaningful than "
                "comparison with mature incumbents. DMARC/TLS gaps at this stage suggest "
                "deliberate inaction rather than resource constraints."
            ),
            "prime": (
                "Peak operational balance. Established processes and governance. Monitor for "
                "emerging path-dependency as legacy decisions accumulate. DMARC/TLS gaps here "
                "are concerning — the vendor has had years to implement these basics. SOC 2 "
                "absence is a deliberate choice or programme failure."
            ),
            "aging": (
                "Established but accumulating path-dependency. Legacy systems and processes "
                "may constrain modernization. Technical debt management is a key concern. "
                "DMARC/TLS gaps suggest either deliberate obsolescence acceptance or "
                "insufficient investment in modernization."
            ),
            "unknown": (
                "Age not determinable from public sources. Cannot assess lifecycle-specific "
                "risks or path-dependency. Consider requesting incorporation evidence directly "
                "from the vendor."
            ),
        }.get(self.lifecycle_stage, "Unknown lifecycle stage.")


def lifecycle_stage_from_years(operating_years: float | None) -> LifecycleStage:
    """Map operating years to lifecycle stage (Infancy, Go-Go, Adolescence, Prime, Aging)."""
    if operating_years is None:
        return "unknown"
    if operating_years < 1:
        return "infancy"
    if operating_years < 2:
        return "go_go"
    if operating_years < 5:
        return "adolescence"
    if operating_years < 15:
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
    # DEDUPLICATION: A signal observed on multiple hosts (E12 fan-out) or across multiple
    # runs produces multiple PersistedFinding rows with the same (signal, band_key).
    # We only want to show the re-framed context ONCE per unique observation type,
    # otherwise the UI will repeat the exact same sentence multiple times.
    obs_signals: list[ObsolescenceSignal] = []
    seen_obs: set[tuple[str, str]] = set()
    
    for f in findings:
        key = (f.signal, f.band_key)
        if key in seen_obs:
            continue
            
        desc = _obsolescence_description(f.signal, f.band_key, operating_years)
        # Only include if it's a recognized obsolescence signal (not the fallback)
        if "obsolescence indicator" not in desc:
            obs_signals.append(ObsolescenceSignal(
                signal=f.signal,
                band=f.band_key,
                description=desc,
                evidence_id=f.evidence_id,
                finding_id=f.id,
            ))
            seen_obs.add(key)

    return LifecycleReport(
        vendor_ref=vendor_ref,
        lifecycle_stage=stage,
        operating_years=operating_years,
        key_person_risk=key_person_risk,
        key_person_basis=key_person_basis,
        obsolescence_signals=obs_signals,
        caveats=list(_CAVEATS),
    )
