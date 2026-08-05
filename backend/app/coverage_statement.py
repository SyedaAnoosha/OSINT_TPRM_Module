"""P2 — the coverage statement: what this assessment could NOT see, derived, never written.

    "This assessment covers externally observable evidence only. We could not observe: internal
     access controls, BCP/DR testing, subprocessor contracts, insurance coverage, or Tier-3 supply
     chain. It does not replace internal due diligence."

COUNTER-INTUITIVELY THIS INCREASES CREDIBILITY WITH MATURE BUYERS. A report that claims less is a
report a security team can check, and the first thing an experienced reader does with an
outside-in assessment is look for the boundary. Finding it stated is the difference between a
product and a marketing artefact. It is also **the cheapest legal protection in the plan** — under
Finding A, what makes a published number defensible is that its limits travelled with it.

DERIVED MECHANICALLY, NEVER HAND-WRITTEN PER VENDOR. Three inputs, all already in the system:

  1. WHICH COLLECTORS RETURNED DATA on this run — a per-vendor, per-run fact.
  2. The **HELD** list — `held_roadmap` in `scoring.yaml`, categories that are designed and have no
     lawful free source yet. Each says why in its own words.
  3. The **STRUCTURAL** list — limits that do not close with more sources, because nothing
     externally observable can reach them.

A hand-written statement is wrong the moment a collector fails on one run and nobody edits the
prose. Worse, it is wrong in the flattering direction: the sentence still claims coverage the run
did not achieve. Deriving it means a source that failed at 03:00 shows up as a gap in that
morning's report without anyone noticing it needed to.

THE DISTINCTION THAT DOES THE WORK: **NOT COLLECTED THIS RUN** vs **NEVER OBSERVABLE**. The first
is our operational problem and may be fixed by re-running; the second is a property of outside-in
assessment and no amount of re-running touches it. A reader who cannot tell them apart will either
dismiss a real gap as a transient or wait indefinitely for a limit that will never close.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: What outside-in assessment CANNOT see, at all, ever. Not a disclaimer list — every item here is
#: something a buyer genuinely needs and must obtain another way, which is what makes P3's Evidence
#: Request Pack the natural next step rather than an upsell.
_NEVER_OBSERVABLE: list[dict[str, str]] = [
    {"area": "Internal access controls",
     "detail": "Who can reach production, how privilege is granted and revoked, whether MFA is "
               "enforced internally. None of it is visible from outside the perimeter."},
    {"area": "BCP / DR testing",
     "detail": "Whether continuity plans exist is sometimes claimed on a trust page; whether they "
               "have ever been TESTED, and what the last test found, is not observable."},
    {"area": "Subprocessor contracts and data flows",
     "detail": "We enumerate fourth parties from public traces (MX, SPF, certificates, headers). "
               "The contracts governing them, and what data actually flows where, are not public."},
    {"area": "Insurance coverage",
     "detail": "Cyber liability limits, exclusions and whether a policy would respond to a given "
               "incident. Never externally observable."},
    {"area": "Tier-3 supply chain",
     "detail": "Who our vendor's vendors depend on. Concentration analysis stops at Tier 2, and a "
               "book with no visible concentration may still funnel through one provider deeper."},
    {"area": "Security programme execution",
     "detail": "Patch cadence, alert response times, whether findings are actually closed. A "
               "published policy is a claim about intent, not evidence of practice."},
    {"area": "Encryption at rest and internal segmentation",
     "detail": "We observe the perimeter's transport security. What happens to data after it "
               "arrives is invisible from the outside."},
    {"area": "Funding runway and financial reserves",
     "detail": "Cash position, burn rate, and months of operational runway for private companies. "
               "No lawful free source exists. Its absence is not evidence of health — the signals "
               "this system CAN reach (EDGAR going-concern language, The Gazette insolvency "
               "notices, Companies House status) are in Continuity. A private startup's remaining "
               "runway is not."},
    {"area": "Key-person and talent-retention risk",
     "detail": "Whether service delivery depends on a small number of named individuals, what "
               "the attrition risk is, or whether key engineers have recently departed. Not "
               "observable from public sources. Headcount from Wikidata is a proxy for scale, "
               "not for dependency concentration."},
]

@dataclass
class CoverageStatement:
    vendor_ref: str
    observed_sources: list[str] = field(default_factory=list)
    failed_sources: list[dict[str, str]] = field(default_factory=list)
    signals_covered: int = 0
    signals_planned: int = 0
    held_categories: list[dict[str, str]] = field(default_factory=list)
    never_observable: list[dict[str, str]] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        return (self.signals_covered / self.signals_planned) if self.signals_planned else 0.0

    def statement(self) -> str:
        """The published paragraph. Assembled, not stored — improving the wording improves every
        past report rather than rewriting history, the same discipline `reasons:` follows."""
        areas = ", ".join(a["area"].lower() for a in self.never_observable)
        lead = (
            f"This assessment covers externally observable evidence only. "
            f"{self.signals_covered} of {self.signals_planned} planned signals returned data "
            f"({self.coverage:.0%} coverage) from {len(self.observed_sources)} sources."
        )
        if self.failed_sources:
            names = ", ".join(sorted({f['source'] for f in self.failed_sources}))
            lead += (f" {len(self.failed_sources)} source(s) did not return on this run "
                     f"({names}); those gaps may close on a re-run.")
        return (
            f"{lead} We could not observe, and cannot observe from outside: {areas}. "
            f"It does not replace internal due diligence."
        )


def coverage_statement(
    vendor_ref: str,
    results: list[Any],
    *,
    signals_covered: int,
    signals_planned: int,
    held: dict[str, str] | None = None,
) -> CoverageStatement:
    """Build the statement from what this run actually did.

    `results` are `CollectorResult`s — anything carrying `.source`, `.status` and `.notes`. A
    source with status `ok` or `empty` was REACHED; `empty` is a real answer ("we asked, there was
    nothing") and must not be reported as a failure, which is the same rule the engine applies to a
    clean finding.
    """
    observed: list[str] = []
    failed: list[dict[str, str]] = []
    for r in results:
        status = getattr(r, "status", "")
        source = getattr(r, "source", "?")
        if status in ("ok", "empty"):
            observed.append(source)
        else:
            # A failed source is OUR gap, not the vendor's. Naming it, with its reason, is what
            # stops a collection outage reading as a finding about the company.
            failed.append({"source": source, "status": status,
                           "note": str(getattr(r, "notes", "") or "")[:200]})

    held_out = [
        {"category": key, "reason": str(reason)}
        for key, reason in sorted((held or {}).items())
    ]
    return CoverageStatement(
        vendor_ref=vendor_ref,
        observed_sources=sorted(set(observed)),
        failed_sources=failed,
        signals_covered=signals_covered,
        signals_planned=signals_planned,
        held_categories=held_out,
        never_observable=list(_NEVER_OBSERVABLE),
    )


def as_dict(cs: CoverageStatement) -> dict[str, Any]:
    return {
        "vendor_ref": cs.vendor_ref,
        "statement": cs.statement(),
        "coverage": round(cs.coverage, 3),
        "signals_covered": cs.signals_covered,
        "signals_planned": cs.signals_planned,
        "sources_observed": cs.observed_sources,
        # Kept apart deliberately — see the module docstring. One may close on a re-run; the other
        # never closes, and a reader who cannot tell them apart will either dismiss a real gap as a
        # transient or wait indefinitely for a limit that will never lift.
        "not_collected_this_run": cs.failed_sources,
        "held_no_lawful_free_source": cs.held_categories,
        "never_observable_from_outside": cs.never_observable,
        "next_step": (
            "Everything under `never_observable_from_outside` is obtainable — but only from the "
            "vendor. That is what an Evidence Request Pack is for, and it should be scoped to the "
            "findings this assessment actually raised rather than to a 300-question standard."
        ),
    }
