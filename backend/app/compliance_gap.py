"""Compliance Gap (E9c) — where E1's deleted sector expectation lands, correctly this time.

WHAT E1 REMOVED AND WHY THIS IS NOT IT COMING BACK. `industry_profiles` promoted a finding's
severity by one step when a sector cited a named instrument: a missing DMARC record read as a
hygiene gap for a farm supplier and a live fraud exposure for a bank. That destroyed the
cross-vendor comparability the whole model rests on — the same evidence scoring differently
because of a label WE assigned.

The obligation was never the problem. The expression of it was. Compare:

    "This DMARC finding is worth more points."          <- an opinion wearing a number
    "Vendor is APRA-regulated and publishes no DMARC    <- disputable, citable, actionable
     record; CPS 234 requires controls commensurate
     with the threat."

The second changes no arithmetic. It states an obligation, names the instrument, names the
observation, and can be argued with — which the first cannot, because there is nothing to argue
with except our judgement.

DISCLOSED, NEVER SCORED INTO POSTURE. A Compliance Gap has exactly one arithmetic effect, and it
is on ASSURITY: a vendor asserting a framework and failing one of its controls has a
claim-reliability problem, which is what that axis measures. Posture is untouched — the underlying
finding already charged whatever it charges, and charging it again here would be the double-count
E3 spent a phase removing.

BOUND-BY vs ASSERTED, kept apart deliberately. A framework applies either because the client told
us the vendor is subject to it (`sector` — client-supplied, never inferred) or because the VENDOR
CLAIMS it. Both are recorded, because they carry different weight in a conversation: one is a legal
obligation the vendor cannot decline, the other is the vendor's own marketing. The asserted case is
the higher-signal one precisely because gaming it means dropping the claim.

WHICH CERTIFICATION, NOT MERELY THAT THERE IS ONE. `cert_posture` bands say `claimed_unverified`,
not `claimed ISO 27001`. Matching a framework on the band alone therefore fires for every framework
keyed to that signal, so a vendor claiming SOC 2 and nothing else would have been published as
"asserts ISO/IEC 27001:2022" — us putting a claim in the vendor's mouth and then finding them
short against it. That is the same failure mode as `industry_profiles`, one layer over: our label,
presented as their position. Every `asserted_by` block must therefore name `claim_contains`, and
the claim is matched against what the collector actually read off the trust page.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .scoring_config import ScoringConfig, get_scoring_config
from .sectors import canonical_sector


@dataclass(frozen=True)
class ComplianceGap:
    """One framework expectation, one observation that fails it, and the citation for both."""

    framework: str            # config key
    framework_name: str       # human name, e.g. "APRA CPS 234 / CPS 230"
    basis: str                # the named instrument, verbatim
    applies_because: str      # 'bound_by_sector' | 'asserted_by_vendor'
    applies_detail: str       # the sector, or the certification claim we observed
    signal: str
    band_key: str
    observed: str
    expectation: str
    evidence_id: str | None = None

    def cited(self) -> str:
        """The published sentence. Names the obligation, the source of it, and the observation —
        in that order, because a reader who stops after one clause should still have the claim."""
        return (f"{self.framework_name} applies ({self.applies_detail}). {self.expectation} "
                f"Observed: {self.signal} = {self.band_key}.")


@dataclass
class ComplianceGapReport:
    vendor_ref: str
    gaps: list[ComplianceGap] = field(default_factory=list)
    frameworks_considered: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)

    @property
    def gap_count(self) -> int:
        return len(self.gaps)

    @property
    def distinct_observations(self) -> int:
        """How many separate OBSERVATIONS underlie these gaps — usually fewer than `gap_count`.

        This, not `gap_count`, is what may reduce Assurity. A vendor asserting ISO 27001, SOC 2 and
        PCI DSS while negotiating TLS 1.0 breaches three frameworks with one weakness, and charging
        three times would mean the axis punished a vendor for CLAIMING MORE — which inverts what it
        measures, since publishing more certifications is the transparency the axis rewards
        everywhere else. The three gaps are all still reported: they are genuinely three separate
        claim-reliability problems and a buyer should see each one. They are simply not billed
        three times for one fact, which is E3's rule (one fact, charged once) applied on this axis.
        """
        return len({g.signal for g in self.gaps})


def _claim_matches(patterns: list[str], observed: str, value: Any) -> str | None:
    """The specific certification the vendor named, or None if this framework was not among them.

    Reads `observed` (`"ISO 27001, SOC 2"`) as well as a `certs` list on the collector's value, so
    it works on a `PersistedFinding` — which carries no value payload at all — as well as on a
    fresh `NormalizedFinding`. That choice is deliberate and it is the same one E6 made for the
    exposure denominator: resolve it from data already flowing rather than adding a field that
    would require every frozen fixture to be re-captured to satisfy a config change.
    """
    haystack = (observed or "").lower()
    if isinstance(value, dict):
        certs = value.get("certs") or value.get("certifications_claimed") or []
        if isinstance(certs, (list, tuple)):
            haystack = " | ".join([haystack, *(str(c).lower() for c in certs)])
    for pattern in patterns:
        if pattern.strip().lower() in haystack:
            return pattern.strip()
    return None


def _asserted_frameworks(cfg: ScoringConfig, findings: list[Any]) -> dict[str, str]:
    """Frameworks the VENDOR claims, keyed to the certification name we actually read.

    The value is the claim itself (`"ISO 27001"`), not the band, because the band is what made this
    ambiguous in the first place — see the module docstring.
    """
    by_signal = {f.signal: f for f in findings}
    out: dict[str, str] = {}
    for key, spec in (cfg.data.get("compliance_frameworks") or {}).items():
        asserted = spec.get("asserted_by")
        if not asserted:
            continue
        finding = by_signal.get(str(asserted.get("signal")))
        if finding is None or finding.band_key not in (asserted.get("bands") or []):
            continue
        claim = _claim_matches(list(asserted.get("claim_contains") or []),
                               getattr(finding, "observed", "") or "",
                               getattr(finding, "value_snapshot", None))
        if claim is not None:
            out[key] = claim
    return out


def compliance_gaps(vendor_ref: str, findings: list[Any], *,
                    sector: str | None = None,
                    cfg: ScoringConfig | None = None) -> ComplianceGapReport:
    """Every framework expectation this vendor is observed failing.

    `findings` are NormalizedFindings (or anything carrying `.signal`, `.band_key`, `.observed`
    and `.evidence_id`). `sector` is CLIENT-SUPPLIED and reaches only this function — it selects
    which obligations apply and never what an observation is worth. That separation is the whole
    correction E1 made, and it is enforced by test_sector_never_changes_a_severity at the engine
    boundary one level up.
    """
    cfg = cfg or get_scoring_config()
    frameworks = cfg.data.get("compliance_frameworks") or {}
    observed = {f.signal: f.band_key for f in findings}
    evidence = {f.signal: getattr(f, "evidence_id", None) for f in findings}

    # Resolve whatever the client typed onto the one vocabulary this system uses. `banking` and
    # `financial_services` are the same obligation and must not produce different reports.
    resolved = canonical_sector(sector)

    asserted = _asserted_frameworks(cfg, findings)
    report = ComplianceGapReport(vendor_ref=vendor_ref)

    for key, spec in frameworks.items():
        if not spec.get("enabled", True):
            # Declared and off, with a reason in config. Recorded on the report rather than
            # skipped in silence: "we model this framework but cannot yet observe it" is a
            # materially different statement from "we have never heard of it", and only the
            # second is an argument for the report being complete.
            report.caveats.append(
                f"{spec.get('name', key)} is modelled but NOT ASSESSED in this deployment. "
                f"{str(spec.get('disabled_because', '')).strip()}"
            )
            continue
        sectors = spec.get("applies_to_sectors") or []
        bound = bool(resolved) and resolved in sectors

        if bound:
            because, detail = "bound_by_sector", f"sector: {resolved}"
        elif key in asserted:
            because, detail = "asserted_by_vendor", f"vendor asserts: {asserted[key]}"
        else:
            continue

        report.frameworks_considered.append(key)
        for signal, control in (spec.get("controls") or {}).items():
            band = observed.get(signal)
            if band is None or band not in (control.get("failing_bands") or []):
                continue
            report.gaps.append(ComplianceGap(
                framework=key,
                framework_name=str(spec.get("name", key)),
                basis=str(spec.get("basis", "")).strip(),
                applies_because=because,
                applies_detail=detail,
                signal=signal,
                band_key=band,
                observed=next((f.observed for f in findings if f.signal == signal), band),
                expectation=str(control.get("expectation", "")).strip(),
                evidence_id=evidence.get(signal),
            ))

    if not sector:
        report.caveats.append(
            "No sector was supplied, so only frameworks the vendor ASSERTS were considered. "
            "Regulatory obligations are a property of the buyer's relationship with the vendor "
            "and are not inferred from public data — supply the sector to widen this."
        )
    elif resolved is None:
        # The unsafe-direction failure this vocabulary exists to stop. Silence here reads as
        # "no obligations breached" when it actually means "we did not understand your industry".
        report.caveats.insert(0, (
            f"Sector {sector!r} is not one this system recognises, so NO sector-bound framework "
            f"was applied and only frameworks the vendor asserts were considered. This is a gap "
            f"in our vocabulary, not a finding about the vendor — do not read the absence of "
            f"sector obligations below as evidence that none exist."
        ))
    elif resolved != (sector or "").strip().lower():
        report.caveats.append(
            f"Sector {sector!r} was read as {resolved!r} — the canonical term this system uses "
            f"for both compliance obligations and peer cohorts."
        )

    report.caveats.append(
        "A compliance gap does not change the posture score. It is a finding about the "
        "reliability of the vendor's own compliance position, and the underlying observation has "
        "already been scored once on its own merits."
    )
    report.caveats.append(
        "Compliance gaps are assessed only against the frameworks this system models, and only "
        "against controls that are externally observable. NO GAPS FOUND DOES NOT MEAN NO "
        "OBLIGATIONS EXIST: a vendor in a sector we do not yet model, or bound by an instrument "
        "not listed above, will show no gaps regardless of their actual compliance position."
    )
    if any(g.applies_because == "asserted_by_vendor" for g in report.gaps):
        # E9c open question 4, answered by disclosure rather than by modelling. A certificate
        # covers a DEFINED SCOPE that may exclude the product being bought, and we read the claim
        # off a marketing page that rarely states it. Implying whole-company coverage would be a
        # stronger assertion than the evidence carries.
        report.caveats.append(
            "A certification covers a defined scope — specific systems, sites or products — which "
            "trust pages rarely publish and this system does not model. A gap against an asserted "
            "framework is a question to put to the vendor about their certificate's scope, not a "
            "finding that the certificate is invalid."
        )
    return report
