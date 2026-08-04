"""P4 — contract flow-downs: findings become drafting points procurement can act on.

WHY THIS EXISTS. P3 tells a vendor what to answer. Nothing yet tells PROCUREMENT what to put in the
contract if the answer does not close the gap. A finding that stays a finding is a line on a report;
the same finding written as a clause is a line in the agreement — this module is the translation,
and it is the last hop from "outside-in observation" to "inside-out protection".

A FIXED TABLE, NOT A GENERATOR. Seven observation families, each mapped to one suggested protection,
argued over once and then held constant — the same discipline `recommend.py` and `residual_risk.py`
apply for the same reason: what procurement is shown must be reconstructible and nameable in a
sentence, never an LLM's opinion about a contract.

SUGGESTED DRAFTING POINTS, NOT LEGAL ADVICE, and every row says so. This module names a category of
protection a lawyer would recognise (breach notification, right-to-audit, escrow); it does not draft
clause language, and it never should — that is legal work, and dressing it up as anything else is
the one claim this product must never make.

EVERY ROW IS CITED TO WHAT ACTUALLY FIRED. A suggestion with nothing behind it is our opinion of the
vendor; a suggestion citing the finding, the continuity flag, or the concentration statement that
produced it is an argument the reader can check, in the same style `evidence_pack.py` cites its
questions and `continuity.py` cites its flags.

THE KEV ROW IS DELIBERATELY SOFTER THAN THE PLAN'S LABEL. The plan calls this row "Overdue KEV", but
`kev_listed_cve` is a PRODUCT-LINE name match (source_assessment.md §9) and the CISA due date is not
carried past the collector into a stored finding — the same limitation that keeps `gates.kev_overdue`
declared and disabled in `scoring.yaml`. Suggesting a remediation-SLA clause off a KEV match is still
sound (an actively-exploited CVE naming this vendor's product line is worth a milestone regardless of
whether THIS due date has passed), but claiming "overdue" would assert evidence this system does not
have. Say what we know; the caveat carries the rest.

WHAT THIS MODULE MUST NOT DO: score anything, or claim a suggestion is a term the vendor has agreed
to. It reads findings, continuity flags, and a portfolio concentration fact already computed
elsewhere, and returns text. Nothing here writes back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Version travels with the table, the same discipline `scoring.yaml` applies to the model itself —
#: a suggested clause read from row 3 of v1.0.0 should not be silently reinterpreted as row 3 of a
#: later revision that changed what row 3 means.
TABLE_VERSION = "1.0.0"

_INCIDENT_PATH_BANDS = {("vd_program", "none"), ("vd_program", "security_txt_only")}
_AUDIT_EVIDENCE_BANDS = {("cert_posture", "claimed_unverified"), ("cert_posture", "claimed_expired")}

_CAVEATS = [
    "SUGGESTED DRAFTING POINTS, NOT LEGAL ADVICE. These name a category of protection a lawyer "
    "would recognise; they are not clause language, and a suggestion appearing here is not a term "
    "any vendor has agreed to. Have counsel draft and negotiate before anything here reaches a "
    f"contract. (Table version {TABLE_VERSION}.)",
    "Every suggestion is cited to the finding, continuity flag, or concentration statement that "
    "produced it. A row with no citation would be our opinion of the vendor rather than an argument "
    "the reader can check — this module does not produce those.",
    "Absence of a suggestion is not a clean bill of health. It means none of the seven observation "
    "families fired on this run, which is a different claim from 'we checked and there is nothing "
    "to add' — see the coverage statement for what this run could and could not see.",
]


@dataclass(frozen=True)
class FlowDown:
    """One suggested protection, and the evidence that argues for it."""

    family: str
    observed: str
    protection: str
    basis: str
    citations: list[str] = field(default_factory=list)

    def cited(self) -> str:
        lead = f"Observed: {self.observed} Suggested: {self.protection}."
        if self.citations:
            lead += " Evidence: " + " · ".join(self.citations)
        return lead


def _finding_citation(f: Any) -> str:
    observed = getattr(f, "observed", None) or f.band_key
    evidence_id = getattr(f, "evidence_id", None)
    tail = f" (evidence {evidence_id})" if evidence_id else ""
    return f"{f.signal} = {observed}{tail}"


def _incident_path_flowdown(findings: list[Any]) -> FlowDown | None:
    hits = [f for f in findings if (f.signal, f.band_key) in _INCIDENT_PATH_BANDS]
    if not hits:
        return None
    return FlowDown(
        family="no_incident_response_path",
        observed="No published route exists for reporting a security problem to this vendor.",
        protection="24-72h breach/incident notification clause",
        basis=(
            "Without a published disclosure or incident-reporting route, a notification obligation "
            "has to be established contractually rather than assumed to already operate — the "
            "absence itself is the evidence that nothing enforces one today."
        ),
        citations=[_finding_citation(f) for f in hits],
    )


def _audit_evidence_flowdown(findings: list[Any]) -> FlowDown | None:
    hits = [f for f in findings if (f.signal, f.band_key) in _AUDIT_EVIDENCE_BANDS]
    if not hits:
        return None
    return FlowDown(
        family="no_independent_audit_evidence",
        observed="A claimed security certification could not be confirmed against an independent register.",
        protection="Right-to-audit clause, or annual SOC 2 / ISO 27001 report delivery",
        basis=(
            "An unverifiable claim is not evidence of the control it names. A contractual audit "
            "right, or a report delivered on a cadence, closes the gap the claim alone does not."
        ),
        citations=[_finding_citation(f) for f in hits],
    )


def _kev_flowdown(findings: list[Any]) -> FlowDown | None:
    hits = [f for f in findings if f.signal == "kev_listed_cve" and f.band_key == "listed"]
    if not hits:
        return None
    return FlowDown(
        family="kev_listed",
        observed="A known-exploited vulnerability (CISA KEV) name-matches this vendor's product line.",
        protection="Remediation SLA with a contractual milestone",
        basis=(
            "KEV membership means observed exploitation somewhere, not theoretical badness — worth "
            "a milestone regardless. The match is against the PRODUCT LINE, not a confirmed "
            "deployment at this vendor, and the CISA due date is not carried into this evidence, so "
            "this is NOT the same claim as 'this vendor is overdue' — confirm the component is "
            "deployed and obtain patch status before treating it as more than a prompt to ask."
        ),
        citations=[_finding_citation(f) for f in hits],
    )


def _concentration_flowdown(spof_providers: list[str]) -> FlowDown | None:
    if not spof_providers:
        return None
    names = ", ".join(spof_providers)
    return FlowDown(
        family="concentrated_fourth_party_dependency",
        observed=(
            f"This vendor is one of several across the book depending on {names} — a provider on "
            f"which at least half of the book's business-critical vendors depend."
        ),
        protection="Subprocessor change-notification and approval right",
        basis=(
            "A single outage at a shared provider removes multiple suppliers from the book at once. "
            "A change of subprocessor is a change nobody in this relationship individually agreed "
            "to unless the contract requires notice and gives a right to object."
        ),
        citations=[f"portfolio concentration: single point of failure at {names}"],
    )


def _going_concern_flowdown(continuity_flags: list[Any]) -> FlowDown | None:
    hits = [flag for flag in continuity_flags if getattr(flag, "standing", "sound") != "sound"]
    if not hits:
        return None
    return FlowDown(
        family="going_concern_flag",
        observed="A registry-cited going-concern flag is recorded against this entity.",
        protection="Termination for convenience, data/source escrow, and exit-assistance obligations",
        basis=(
            "A going-concern flag is not security posture and is not scored as one, but a buyer "
            "who signs without an exit path is betting the relationship survives on evidence that "
            "already says it might not."
        ),
        citations=[flag.cited() for flag in hits],
    )


def _thin_coverage_flowdown(*, ghost: bool, thin_coverage: bool) -> FlowDown | None:
    if not (ghost or thin_coverage):
        return None
    return FlowDown(
        family="thin_coverage_or_ghost",
        observed=(
            "Public evidence coverage on this vendor is too thin to support a decision on its own "
            "— it may reflect a small public footprint rather than strong security."
        ),
        protection="Security questionnaire as a condition precedent to signing",
        basis=(
            "A Ghost is unassessed, not safe. Thin coverage that happens to look clean is the single "
            "most dangerous read in this system, and the contractual answer is to obtain the "
            "evidence outside-in assessment could not see before relying on the absence of findings."
        ),
        citations=["overall evidence coverage" + (" — Ghost" if ghost else " — Low confidence band")],
    )


def _substitutability_flowdown(substitutability: str | None) -> FlowDown | None:
    """P8's row of the plan's table, which is a flow-down and always was.

    THE PLAN SAYS `sole_source` "MANDATES EXIT-CLAUSE FLOW-DOWNS" — that sentence names this module,
    and until this existed P8 published an alert with nowhere for it to land. An alert that does not
    reach the contract is a fact the buyer now knows and still cannot act on.

    NOT DERIVED FROM ANY OBSERVATION. Substitutability is client-declared, like `criticality` and
    `data_access_scope`, so this row cites the declaration rather than a finding — the same shape
    as the concentration and thin-coverage rows, which cite the module that produced them.
    """
    if substitutability == "sole_source":
        return FlowDown(
            family="sole_source_exit_rights",
            observed=("This relationship is declared SOLE SOURCE — the buyer has stated there is no "
                      "ready replacement for this vendor."),
            protection=("Exit-assistance obligations, data/source escrow, transition-services "
                        "period, and a contractual notice period long enough to run a replacement"),
            basis=(
                "A vendor you cannot replace is one whose exit terms you will never renegotiate "
                "from a position of strength — the moment you need them is the moment you have "
                "least leverage. These are the terms that have to be won at signature or not at "
                "all, which is why sole source mandates them rather than suggesting them."
            ),
            citations=["client-declared substitutability: sole_source"],
        )
    if substitutability == "low":
        return FlowDown(
            family="low_substitutability_exit_assistance",
            observed=("Substitutability is declared LOW — a replacement exists but switching would "
                      "be slow or costly."),
            protection="Exit-assistance clause with a defined transition period",
            basis=(
                "Low substitutability is not sole source and does not warrant escrow, but a "
                "migration that is merely difficult still fails without an obligation on the "
                "outgoing vendor to help. The clause costs little at signature and is unobtainable "
                "afterwards."
            ),
            citations=["client-declared substitutability: low"],
        )
    return None


def flow_downs(
    vendor_ref: str,
    findings: list[Any],
    *,
    continuity_flags: list[Any] = (),
    spof_providers: list[str] = (),
    ghost: bool = False,
    thin_coverage: bool = False,
    substitutability: str | None = None,
) -> list[FlowDown]:
    """Seven fixed observation families, checked in the plan's published order. Only families that
    actually fired for this vendor are returned — this is not a template filled in seven times.

    The seventh is P8's, and it is client-declared rather than observed. `medium` and `high`
    substitutability produce nothing, which is the plan's table exactly: *standard terms* and *no
    exit conditions needed* are the absence of a clause, not a clause saying nothing is needed.
    """
    candidates = [
        _incident_path_flowdown(findings),
        _audit_evidence_flowdown(findings),
        _concentration_flowdown(list(spof_providers)),
        _going_concern_flowdown(list(continuity_flags)),
        _thin_coverage_flowdown(ghost=ghost, thin_coverage=thin_coverage),
        _kev_flowdown(findings),
        _substitutability_flowdown(substitutability),
    ]
    return [c for c in candidates if c is not None]


def as_dict(vendor_ref: str, flowdowns: list[FlowDown]) -> dict[str, Any]:
    return {
        "vendor_ref": vendor_ref,
        "table_version": TABLE_VERSION,
        "count": len(flowdowns),
        "summary": (
            f"{len(flowdowns)} suggested contractual protection(s), each tied to an observation "
            f"already in this assessment."
            if flowdowns else
            "No observation on this run matches one of the seven flow-down families, so this module "
            "suggests nothing. That is a real result, not an empty template."
        ),
        "flow_downs": [
            {
                "family": fd.family,
                "observed": fd.observed,
                "suggested_protection": fd.protection,
                "basis": fd.basis,
                "citations": fd.citations,
                "cited": fd.cited(),
            }
            for fd in flowdowns
        ],
        "caveats": list(_CAVEATS),
    }
