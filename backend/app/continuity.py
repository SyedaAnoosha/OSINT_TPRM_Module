"""Continuity — going-concern status, read from findings already collected.

WHY THIS EXISTS. `business_financial_stability` was a POSTURE category holding going-concern
facts. Companies House maps `liquidation`, `receivership`, `administration` and
`insolvency-proceedings` onto `entity_inactive`, which cost **20 points of technical security
posture**. A vendor entering administration does not thereby have worse TLS. `entity_maturity`
penalised companies under ten years old — scoring by founding date, which the research explicitly
rules out (no published evidence links founding date to compromise likelihood, and not one of
Bitsight, SecurityScorecard, RiskRecon, Cyentia, NIST, ENISA or CISA does it). `rdap_collector`
had already tagged `domain_registration` with `subcategory="business_continuity"`.

These are real risks a buyer must see. They are simply not *security posture*, and mixing them in
made both numbers mean less.

FLAGS, NOT A SCORE — and this is a deliberate refusal, not an unfinished feature.

  1. The research establishes that these signals must LEAVE Posture. It does not specify an
     arithmetic to replace them. A 0-100 Continuity score would be invention wearing the report's
     authority.
  2. Four registry bands cannot support hundred-point precision. `entity_status` has four states;
     compressing them onto a hundred-point scale asserts a resolution the registers do not have.
  3. Legal exposure differs in KIND from posture. A cited register fact — "Companies House
     records administration proceedings, retrieved 2026-07-30" — sits on the same footing as every
     other published observation. A DERIVED distress index (inferred runway, a bankruptcy-risk
     score) is credit-rating territory and is defamation-adjacent when wrong. Publish the fact and
     its retrieval date; do not publish an inference about solvency.

DISCLOSED, NEVER SCORED. Like `fourth_party`, this adds no source, emits no finding, and cannot
reach the scoring engine. It re-reads findings the pipeline already stored and presents them as
what they are. The signals remain in `scoring.yaml` at `informational` so they still count toward
coverage — deleting them would shrink the confidence denominator and lift every vendor's
confidence for no evidential reason.

WHAT IS NOT HERE. Funding runway, cash burn, down-rounds, Altman Z-score, market share and
layoffs all stay in `held_roadmap`: no lawful free source — a derived distress INDEX is exactly
the credit-rating-territory invention item 3 above refuses, regardless of whether the underlying
numbers could technically be sourced. General litigation and ownership-change also remain held.

UPDATED (docs/tprm_feedback_redesign.md §1.2). Going-concern doubt and formal insolvency/
bankruptcy filings themselves are no longer fully held: `edgar_collector` reads SEC 8-K Item 1.03
bankruptcy disclosures and 10-K/10-Q going-concern language for US SEC-registered entities,
`gazette_collector` reads The Gazette's official UK corporate-insolvency notices (winding-up,
administration, receivership — filtered to notice-codes 2401-2465 specifically to exclude
personal bankruptcy, which the Gazette's insolvency search otherwise mixes in), and
`courtlistener_bankruptcy_collector` reads US federal bankruptcy-petition dockets. Each is a
CITED FACT from the register or filer itself, not an inference — the same footing as the
Companies House/GLEIF/RDAP facts above, never a computed score.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import PersistedFinding

# Severity of a going-concern flag as a WORD, never a number. These order a list and colour a
# badge; they are not summed, averaged or blended into anything.
Standing = str  # "ceased" | "impaired" | "watch" | "sound" | "unknown"

_ORDER = {"ceased": 0, "impaired": 1, "watch": 2, "unknown": 3, "sound": 4}

# Formalized 5-state traffic-light summary and procurement actions.
# Maps Standing -> (action_key, action_label, action_detail)
_STANDING_ACTIONS: dict[Standing, tuple[str, str, str]] = {
    "ceased": (
        "hard_gate",
        "Hard Gate",
        "Entity is dissolved, struck off, or liquidated. Cannot contract. "
        "This is a hard gate — no agreement can be signed with a non-existent legal person."
    ),
    "impaired": (
        "escalation",
        "Escalation",
        "Entity is in administration, receivership, or subject to a winding-up petition/CVA. "
        "Escalate to legal and risk for immediate review of insolvency proceedings before any signature."
    ),
    "watch": (
        "condition",
        "Condition",
        "Going-concern doubt, reorganisation (e.g., Chapter 11), or administrative lapse. "
        "Condition precedent: require recent management accounts, a going-concern confirmation, "
        "or termination-for-convenience and escrow clauses before signing."
    ),
    "sound": (
        "standard_terms",
        "Standard Terms",
        "Entity is active and in good standing. No specific continuity action required; "
        "standard contractual terms apply."
    ),
    "unknown": (
        "standard_due_diligence",
        "Standard Due Diligence",
        "No definitive registry facts found (either no adverse filings, or the entity is outside "
        "covered jurisdictions). Rely on standard due diligence or request a certificate of good "
        "standing if the relationship tier warrants it."
    ),
}

# (signal, band) -> (standing, plain-English statement).
#
# The statement is what a procurement reader sees. It states the OBSERVATION and leaves the
# inference to them: "the register records X" rather than "this vendor is failing". Every entry
# is a fact a registry published, which is exactly what keeps this publishable.
_FLAGS: dict[tuple[str, str], tuple[Standing, str]] = {
    # --- legal entity standing -------------------------------------------------------------
    ("entity_status", "entity_inactive"): (
        "ceased",
        "The register records this entity as inactive — dissolved, in liquidation, in "
        "receivership, under administration, or in insolvency proceedings.",
    ),
    ("entity_status", "registration_retired"): (
        "ceased",
        "The entity's registration has been retired: the legal person you would contract with "
        "no longer holds an active registration.",
    ),
    ("entity_status", "registration_lapsed"): (
        "watch",
        "The entity's registration has lapsed — commonly an administrative oversight, but it is "
        "the register's own record of the company's standing and worth confirming before signing.",
    ),
    ("entity_status", "active_good_standing"): (
        "sound",
        "The register records this entity as active and in good standing.",
    ),
    ("entity_existence", "entity_dissolved"): (
        "ceased",
        "The register records this entity as dissolved. There may be no legal person capable of "
        "holding the contract.",
    ),
    ("entity_existence", "entity_active_confirmed"): (
        "sound", "The entity's existence is confirmed against an authoritative register.",
    ),
    # --- domain registration: the service's own continuity ----------------------------------
    ("domain_registration", "domain_suspended"): (
        "impaired",
        "The domain registration is suspended. Service delivered over this domain is at immediate "
        "risk of interruption.",
    ),
    ("domain_registration", "domain_expiring"): (
        "watch",
        "The domain registration expires soon. An unrenewed domain interrupts service and can be "
        "re-registered by someone else.",
    ),
    ("domain_registration", "domain_established"): (
        "sound", "The domain registration is long-established and current.",
    ),

    # --- financial/business-stability filings (docs/tprm_feedback_redesign.md §1.2) --------
    # `no_adverse_filings` (the clean receipt for all three signals below) is deliberately NOT
    # mapped here. Absence of a matching filing is weaker evidence than a registry's explicit
    # confirmation of good standing — it is a name-search finding nothing, not a positive
    # attestation — so it contributes to Business Stability COVERAGE without asserting "sound".
    ("sec_filing", "entity_inactive"): (
        "ceased",
        "SEC EDGAR records an 8-K Item 1.03 filing — a bankruptcy event disclosed within the "
        "SEC's required 4-business-day window.",
    ),
    ("sec_filing", "registration_lapsed"): (
        "watch",
        "SEC EDGAR records going-concern / substantial-doubt language in this entity's own "
        "recent 10-K or 10-Q filing — the company's own auditor has flagged doubt about its "
        "ability to continue as a going concern.",
    ),
    ("sec_going_concern", "audit_qualification"): (
        "watch",
        "SEC EDGAR 10-K/10-Q filing contains a going-concern audit qualification — the company's "
        "own auditor has flagged doubt about its ability to continue as a going concern.",
    ),
    ("insolvency_notice", "entity_inactive"): (
        "ceased",
        "The Gazette (the UK's official public record) records a winding-up or liquidation "
        "notice for this entity.",
    ),
    ("insolvency_notice", "registration_lapsed"): (
        "watch",
        "The Gazette records an administration or receivership notice for this entity — a "
        "corporate insolvency procedure that may still end in recovery rather than liquidation.",
    ),
    ("bankruptcy_petition", "entity_inactive"): (
        "ceased",
        "US federal court records (via CourtListener/RECAP) show a Chapter 7 or Chapter 9 "
        "bankruptcy petition — liquidation proceedings — filed by or against this entity.",
    ),
    ("bankruptcy_petition", "registration_lapsed"): (
        "watch",
        "US federal court records (via CourtListener/RECAP) show a Chapter 11, 12, or 13 "
        "bankruptcy petition — reorganisation proceedings — filed by or against this entity.",
    ),
    ("gazette_insolvency", "winding_up_petition"): ("impaired", "The Gazette records a winding-up petition against this entity."),
    ("gazette_insolvency", "administration"): ("impaired", "The Gazette records an administration order."),
    ("gazette_insolvency", "cva"): ("impaired", "The Gazette records a Company Voluntary Arrangement (CVA)."),
    ("gazette_insolvency", "dissolved"): ("ceased", "The Gazette records the entity has been struck off or dissolved."),
    ("sec_bankruptcy", "chapter_11"): ("impaired", "SEC EDGAR 8-K filing indicates bankruptcy or receivership proceedings."),
    ("sec_going_concern", "audit_qualification"): ("watch", "SEC EDGAR 10-K/10-Q filing contains a going-concern audit qualification."),
    ("asx_announcement", "voluntary_administration"): ("impaired", "ASX announcement indicates voluntary administration."),
    ("asx_announcement", "delisting"): ("impaired", "ASX announcement indicates the entity is to be delisted."),
    ("asic_administration", "external_administration"): ("impaired", "ASIC records the entity is under external administration."),
}

# Bands recording only how OLD a company is. Reported as context, never as a standing, because a
# young company is not thereby an impaired counterparty — that is the founding-date scoring this
# whole relocation exists to remove. Age's legitimate homes are the Confidence assurance
# multiplier, the Assurity attainability rule, and cohort assignment.
_AGE_CONTEXT = {
    "entity_maturity": {
        "new_lt_1": "Operating for under a year.",
        "startup_lt_2": "Operating for one to two years.",
        "young_2_5": "Operating for two to five years.",
        "established_5_10": "Operating for five to ten years.",
        "mature_gt_10": "Operating for more than ten years.",
    },
    "domain_registration": {
        "domain_new": "The domain was registered recently.",
        "domain_recent": "The domain was registered within the last couple of years.",
    },
}


@dataclass(frozen=True)
class BusinessStabilitySummary:
    vendor_ref: str
    standing: Standing
    listed_status: str | None
    registry_facts: list[str]
    flags: list[ContinuityFlag]
    procurement_action: str
    procurement_action_label: str
    action_detail: str
    caveats: list[str]


def business_stability_summary(vendor_ref: str, continuity: ContinuityReport, profile: Any, stability_score: int | None = None) -> BusinessStabilitySummary:
    """A structured summary of registry facts for the UI.
    Never blended into a score. Provides a procurement-facing label and action.
    
    Args:
        vendor_ref: Vendor reference
        continuity: Continuity report with registry flags
        profile: Vendor profile for additional context
        stability_score: Optional Business Stability score to override standing calculation
    
    If stability_score is provided, it will be used to determine the standing instead of
    just registry flags. This ensures the Business Stability score matches the displayed status.
    """
    
    listed_status = None
    if profile and getattr(profile, "ownership", None) and profile.ownership.value == "listed":
        listed_status = "Publicly Listed" 
        
    registry_facts = []
    for f in continuity.flags:
        if f.signal in ("entity_status", "entity_existence"):
            # Only include substantive observations, not generic positive confirmations
            # Filter out "active_good_standing", "entity_active_confirmed", "domain_established"
            # which are neutral/positive and don't need to be highlighted as warnings
            if f.band not in ("pass", "active_good_standing", "entity_active_confirmed", "domain_established"):
                registry_facts.append(f"{f.source}: {f.observed}")
    
    # Determine standing based on Business Stability score if provided
    # This ensures the standing matches the actual financial health score
    if stability_score is not None:
        if stability_score >= 80:
            standing = "sound"
        elif stability_score >= 60:
            standing = "watch"
        elif stability_score >= 40:
            standing = "impaired"
        else:
            standing = "ceased"
    else:
        standing = continuity.standing
            
    action_key, action_label, action_detail = _STANDING_ACTIONS.get(
        standing, _STANDING_ACTIONS["unknown"]
    )
        
    caveats = [
        "This is NOT a score. It is a structured summary of registry facts.",
        "This does not affect the security posture score.",
        "Insolvency feeds (The Gazette, ASX, SEC) cover listed/registered entities only."
    ]
    
    return BusinessStabilitySummary(
        vendor_ref=vendor_ref, standing=standing, listed_status=listed_status,
        registry_facts=registry_facts, flags=continuity.flags,
        procurement_action=action_key,
        procurement_action_label=action_label,
        action_detail=action_detail,
        caveats=caveats
    )


@dataclass(frozen=True)
class ContinuityFlag:
    """One going-concern observation, with the citation that makes it publishable."""

    signal: str
    band: str
    standing: Standing
    statement: str
    source: str                    # which collector/register said so
    observed: str                  # the raw observed value, verbatim
    evidence_id: str | None        # the stored receipt
    retrieved_at: str | None       # ISO date the evidence was fetched

    def cited(self) -> str:
        """The sentence as it should be published — claim, register, and retrieval date."""
        where = f" — {self.source}" if self.source else ""
        when = f", retrieved {self.retrieved_at[:10]}" if self.retrieved_at else ""
        return f"{self.statement}{where}{when}"


@dataclass(frozen=True)
class ContinuityReport:
    vendor_ref: str
    standing: Standing
    flags: list[ContinuityFlag]
    age_context: list[str]
    caveats: list[str]


_CAVEATS = [
    "Continuity reports registry-cited facts and their retrieval dates. It is deliberately NOT a "
    "score: four registry bands cannot support hundred-point precision, and a derived distress "
    "index is a different kind of claim from an observed one.",
    "Going-concern status is not security posture and does not affect it. A vendor in "
    "administration does not thereby have weaker technical controls.",
    "Financial-distress markers (funding runway, cash burn, credit ratings) are NOT covered: no "
    "lawful free source. Their absence here is not evidence of financial health.",
]


def continuity_report(vendor_ref: str, findings: list[PersistedFinding]) -> ContinuityReport:
    """Build the going-concern view from findings the pipeline already stored.

    Adds no source and emits no finding. The worst standing observed becomes the headline, because
    a single `ceased` flag is not averaged away by three `sound` ones — the same non-compensatory
    logic the critical ceiling applies one level up.
    """
    flags: list[ContinuityFlag] = []
    age: list[str] = []

    for f in findings:
        entry = _FLAGS.get((f.signal, f.band_key))
        if entry is not None:
            standing, statement = entry
            flags.append(ContinuityFlag(
                signal=f.signal, band=f.band_key, standing=standing, statement=statement,
                source=f.source, observed=f.observed, evidence_id=f.evidence_id,
                retrieved_at=f.stored_at.isoformat() if getattr(f, "stored_at", None) else None,
            ))
            continue
        note = _AGE_CONTEXT.get(f.signal, {}).get(f.band_key)
        if note:
            age.append(note)

    flags.sort(key=lambda x: _ORDER.get(x.standing, 9))
    headline = flags[0].standing if flags else "unknown"
    return ContinuityReport(
        vendor_ref=vendor_ref, standing=headline, flags=flags,
        age_context=sorted(set(age)), caveats=list(_CAVEATS),
    )


# Must stay in sync with `ScoringConfig.business_stability_signals()` — duplicated here rather
# than imported so this module keeps its documented independence from the scoring engine (it
# re-reads persisted findings and never touches engine/config machinery). Both are guarded by
# `test_business_stability_signal_sets_match` (test_continuity.py).
# The original three registry/filing facts plus `sec_going_concern`, added at Phase 2. Phase 2's
# financial-health names (`revenue_stability`, `debt_position`, `cash_flow`, `current_status`,
# `operating_years`) are deliberately NOT here: the model declares no bands for them, so they are
# checks that can never be answered, and putting them in this denominator would publish five
# permanent gaps a reader could do nothing about. See `ScoringConfig.business_stability_signals`.
BUSINESS_STABILITY_SIGNALS = frozenset({
    "sec_filing", "sec_going_concern", "insolvency_notice", "bankruptcy_petition",
})


def business_stability_coverage(findings: list[PersistedFinding]) -> tuple[int, int]:
    """(checks answered, checks tracked) for the Business Stability axis — never Posture's.

    Deliberately separate from `continuity_report`'s Continuity standing and from engine.py's
    Posture-confidence coverage (`ScoringConfig.business_stability_signals` excludes these same
    four signals from that computation for exactly this reason — see its docstring). A vendor
    outside every source's jurisdiction (not UK, not a US SEC registrant, no US federal
    bankruptcy record) still gets an `(0, 4)` or partial result here rather than silently
    inflating or shrinking Posture's own confidence number.
    """
    seen = {f.signal for f in findings if f.signal in BUSINESS_STABILITY_SIGNALS}
    return len(seen), len(BUSINESS_STABILITY_SIGNALS)