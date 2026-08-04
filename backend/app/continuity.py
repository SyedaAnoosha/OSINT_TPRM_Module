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
layoffs all stay in `held_roadmap`: no lawful free source. `gleif_collector` already records the
same finding — *"Financial-distress (going concern), litigation, and ownership-CHANGE remain
HELD: no free authoritative source."* Roughly four of ten candidate financial markers are
obtainable today, and this module carries only those four.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import PersistedFinding

# Severity of a going-concern flag as a WORD, never a number. These order a list and colour a
# badge; they are not summed, averaged or blended into anything.
Standing = str  # "ceased" | "impaired" | "watch" | "sound" | "unknown"

_ORDER = {"ceased": 0, "impaired": 1, "watch": 2, "unknown": 3, "sound": 4}

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
