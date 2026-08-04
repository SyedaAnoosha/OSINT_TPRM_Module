"""P5 — Inherent Tier decides how much assessment a relationship is worth, and how often.

THE PROBLEM. Every vendor in this system gets the same treatment: nineteen collectors, twenty-seven
planned signals, and one `--stale-days` clock for the whole book. A stationery supplier and the
vendor holding production customer data cost the same to assess and are re-checked on the same day.
That is wrong in both directions at once — it overspends a politeness budget on relationships that
do not warrant it, and it gives the critical ones no more attention than the trivial ones.

WHAT THIS MODULE IS. A lookup from E10b's Inherent Tier to a COLLECTION DEPTH and a REVIEW CADENCE.
Four tiers, three depths, four cadences. Like `residual_risk` and `recommend`, it is a table rather
than a formula: what we publish must be reconstructible and nameable in a sentence, and "the model
chose quarterly" is not a defensible answer to "why is this vendor on a 90-day cycle".

═══ THE DECISION THAT MAKES THIS MORE THAN A TABLE ═══

A SHALLOWER RUN DOES NOT PUBLISH A COMPARABLE POSTURE, AND THE DENOMINATOR MUST NOT BE ADJUSTED TO
HIDE THAT. Confidence is `signals observed / signals planned`. Run four collectors instead of
nineteen and coverage collapses — a screening-depth run reaches roughly a fifth of the model, which
is below `refuse_below` and correctly refuses as a Ghost.

The tempting fix is to shrink the denominator to what the chosen depth planned, so a screening run
reports high confidence "of what it set out to do". **That is refused here**, for the reason E6 and
E12 both give: confidence has to mean ONE thing across the whole book. If the denominator moves with
the depth, then `0.8` means "we saw most of the model" on one vendor and "we saw most of four
collectors" on the next, the two are printed in the same column, and no reader can tell them apart.
`unreachable_signals()` shrinks the denominator for signals that CANNOT fire under the shipped
config — a property of the model. Depth is a property of the RELATIONSHIP, and adjusting a published
measurement to flatter a deliberate choice is the whole failure mode this system is built against.

So the honest consequence is stated up front: **a screening-depth run is a watchlist check, not an
assessment, and publishes no posture.** That is the correct outcome for a T4 relationship — nobody
needs a control-posture score for the stationery supplier; they need to know the entity exists and
is not sanctioned. `publishes_posture` says so on the plan, before the run, rather than leaving a
reader to discover a refusal and read it as a finding about the vendor.

═══ TWO CLOCKS, AND THEY MUST NOT BE COLLAPSED ═══

    Review cadence  (here)          — how often we REASSESS THE RELATIONSHIP regardless of findings.
                                      Driven by inherent exposure. Moves when the contract moves.
    Re-check date   (`recommend`)   — when a SPECIFIC FINDING needs chasing. 7d / 14d / 30d / 90d.
                                      Driven by what we found. Moves when the vendor's controls move.

They answer different questions and a card that prints one number for both is lying about one of
them. A T4 supplier with an expired certificate serving production still needs that certificate
chased inside a week — the relationship is unimportant, the finding is not. Conversely a T1 vendor
with nothing outstanding is still re-assessed quarterly, because the reason to look is the exposure,
not the last result.

`next_action_in()` returns the SOONER of the two, which is the only number a scheduler should act
on, and it says which clock produced it.

═══ UNDECLARED IS NOT T4 ═══

An undeclared inherent tier gets FULL depth on the T2 cadence, not screening. The same argument
E10b makes for the residual cell and P3 makes for the decision tag: relationships nobody has
classified are disproportionately the ones nobody has looked at, so routing them to the cheapest
treatment puts the thinnest assessment exactly where the unknown risk is. It costs budget, and the
way to stop paying it is to declare the tier — which is the behaviour we want.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .residual_risk import InherentTier

Depth = Literal["screening", "core", "full"]
Cadence = Literal["quarterly", "semi_annual", "annual", "passive"]

#: SANCTIONS + ENTITY. What a passive relationship actually needs: does this company exist, is it
#: trading, and is it on a list. No hygiene probing, no CVE lookups, no certificate transparency.
_SCREENING_SOURCES: frozenset[str] = frozenset({
    "ita",              # ITA Consolidated Screening List — the sanctions gate's evidence
    "gleif", "wikidata",  # entity existence + corroboration, global
    "abn", "companies_house",  # authoritative national registers (AU, UK)
    "rdap",             # universal domain standing — works for any domain, no auth
    "regulatory",       # hard-fact regulator enforcement feeds
})

#: CORE. Screening plus the cheap, high-yield control hygiene: DNS records, TLS, response headers,
#: and the vendor's own published disclosure posture. Everything that costs a request to the
#: vendor's own infrastructure and nothing to a third-party quota.
_CORE_SOURCES: frozenset[str] = _SCREENING_SOURCES | frozenset({
    "dns", "tls", "headers", "trust",
})

#: FULL is expressed as `None` — NO RESTRICTION — rather than as an allowlist of nineteen sources.
#: An allowlist would mean every new collector has to be remembered here, and forgetting is silent:
#: the collector ships, runs nowhere, and the only symptom is a confidence figure slightly lower
#: than it should be. `None` means a new collector is in `full` the moment it is registered.
_DEPTH_SOURCES: dict[Depth, frozenset[str] | None] = {
    "screening": _SCREENING_SOURCES,
    "core": _CORE_SOURCES,
    "full": None,
}

_CADENCE_DAYS: dict[Cadence, int | None] = {
    "quarterly": 90, "semi_annual": 182, "annual": 365, "passive": None,
}

_CADENCE_LABEL: dict[Cadence, str] = {
    "quarterly": "Quarterly", "semi_annual": "Semi-annual", "annual": "Annual",
    "passive": "Passive — no scheduled re-score",
}

#: The published table, verbatim from the phase plan. Rows are inherent tiers; `None` is the
#: undeclared row and is deliberately NOT the bottom one.
_PLAN: dict[str, tuple[str, Depth, Cadence, tuple[str, ...]]] = {
    "critical": ("T1 Critical", "full", "quarterly",
                 ("fourth-party dependency map", "evidence request pack",
                  "contract flow-downs")),
    "high":     ("T2 Important", "full", "semi_annual", ("evidence request pack",)),
    "medium":   ("T3 Standard", "core", "annual", ()),
    "low":      ("T4 Low", "screening", "passive", ()),
}

_UNDECLARED = ("Unclassified", "full", "semi_annual", ("evidence request pack",))

#: `recommend()`'s finding-level re-check vocabulary, in days, so the two clocks can be compared.
#: Kept here rather than imported because the mapping from a label to a number is a scheduling
#: concern, not a scoring one — `recommend` deliberately publishes labels, not arithmetic.
_RECHECK_DAYS: dict[str, int] = {"7d": 7, "14d": 14, "30d": 30, "90d": 90}


@dataclass(frozen=True)
class AssessmentPlan:
    """How much assessment this relationship warrants, and how often. Computed, never stored.

    Stored nowhere for the same reason `ResidualRisk` is: it is derived from a declared tier that
    can change with the contract, and a persisted copy would drift from the declaration it came
    from with no way for a reader to tell which is current.
    """

    tier: InherentTier | None
    tier_label: str
    depth: Depth
    cadence: Cadence
    cadence_days: int | None
    sources: frozenset[str] | None
    artefacts: tuple[str, ...]
    publishes_posture: bool
    basis: str
    caveats: list[str] = field(default_factory=list)

    @property
    def declared(self) -> bool:
        return self.tier is not None

    @property
    def cadence_label(self) -> str:
        return _CADENCE_LABEL[self.cadence]

    @property
    def source_count(self) -> str:
        return "every on-demand collector" if self.sources is None else f"{len(self.sources)} sources"

    def headline(self) -> str:
        return (f"{self.tier_label} — {self.depth} collection ({self.source_count}), "
                f"{self.cadence_label.lower()}.")

    def next_action_in(self, finding_recheck: str | None = None) -> dict[str, object]:
        """The SOONER of the review cadence and the soonest finding re-check, and which one won.

        A scheduler needs one number. A reader needs to know which clock produced it, because the
        two are fixed by different things and a T4 vendor on a 7-day date is not on a short cycle —
        it has one urgent finding, and closing that finding returns it to passive.
        """
        finding_days = _RECHECK_DAYS.get(finding_recheck or "")
        candidates = [(d, src) for d, src in
                      ((self.cadence_days, "review cadence"), (finding_days, "outstanding finding"))
                      if d is not None]
        if not candidates:
            return {
                "days": None, "driver": None, "recheck_after": finding_recheck,
                "note": ("No scheduled re-score. This relationship is passive and carries no "
                         "outstanding finding with a re-check date. It is re-screened when the "
                         "relationship changes, not on a clock."),
            }
        days, driver = min(candidates, key=lambda c: c[0])
        return {
            "days": days, "driver": driver, "recheck_after": finding_recheck,
            "note": (f"Next look in {days} day(s), set by the {driver}. The review cadence "
                     f"({self.cadence_label.lower()}) tracks how much this relationship is worth "
                     f"reassessing; a finding re-check tracks one thing we found. The sooner wins, "
                     f"and neither replaces the other."),
        }


def _caveats(depth: Depth, publishes: bool, declared: bool) -> list[str]:
    out = [
        "Assessment depth and review cadence are derived from the CLIENT-DECLARED inherent tier "
        "and nothing else. They are not a judgement about the vendor — a low-tier supplier is not "
        "a safe one, it is one this buyer has less riding on.",
        "This plan is recomputed on read and stored nowhere. Change the declared criticality or "
        "data access scope and the plan changes with it, on the next read.",
    ]
    if not publishes:
        out.append(
            "A SCREENING-DEPTH RUN PUBLISHES NO POSTURE. It reaches roughly a fifth of the scored "
            "model, which is below the evidence floor, so the run correctly refuses rather than "
            "publishing a score built on four collectors. That is the intended outcome at this "
            "tier: the question a passive relationship asks is whether the entity exists and is "
            "not sanctioned, not how its TLS is configured."
        )
    if depth == "core":
        out.append(
            "A CORE-DEPTH RUN GENUINELY SEES LESS, AND ITS CONFIDENCE SAYS SO. The denominator is "
            "not reduced to match the chosen depth: confidence means the same thing on every "
            "vendor in the book — the fraction of the full model we observed — or it means nothing "
            "on any of them. Expect a lower confidence figure here than on a full run, and read it "
            "as what it is."
        )
    if not declared:
        out.append(
            "INHERENT EXPOSURE IS NOT DECLARED for this relationship, so this plan is a placeholder "
            "at full depth rather than a tier. Undeclared is not T4: the relationships nobody has "
            "classified are disproportionately the ones nobody has looked at, and routing them to "
            "the cheapest treatment would put the thinnest assessment exactly where the unknown "
            "risk is. Declare business criticality and data access scope to resolve it."
        )
    return out


def plan_for(tier: InherentTier | None) -> AssessmentPlan:
    """The lookup. `None` is the undeclared row, and it is not the bottom one."""
    label, depth, cadence, artefacts = _PLAN.get(tier or "", _UNDECLARED)  # type: ignore[assignment]
    publishes = depth != "screening"
    if tier:
        basis = (f"Inherent tier is {tier}, so this relationship is {label}. Collection runs at "
                 f"{depth} depth on a {_CADENCE_LABEL[cadence].lower()} review cycle.")
    else:
        basis = ("Inherent tier has not been declared, so no tier applies. The plan defaults to "
                 "FULL depth on a semi-annual cycle — the conservative direction — and says so.")
    return AssessmentPlan(
        tier=tier, tier_label=label, depth=depth, cadence=cadence,
        cadence_days=_CADENCE_DAYS[cadence], sources=_DEPTH_SOURCES[depth],
        artefacts=artefacts, publishes_posture=publishes, basis=basis,
        caveats=_caveats(depth, publishes, declared=tier is not None),
    )


def sources_for_depth(depth: Depth) -> frozenset[str] | None:
    """Collector source ids a run at `depth` may use. `None` means no restriction."""
    return _DEPTH_SOURCES[depth]


def is_due(plan: AssessmentPlan, days_since_last_score: float | None,
           finding_recheck: str | None = None) -> tuple[bool, str]:
    """Whether a scheduled sweep should re-score this vendor now, and why.

    A vendor with no prior score is always due — there is nothing to be stale. A passive
    relationship with no outstanding finding is NEVER due on a clock, which is the whole of P5's
    budget win: the suppliers that consume the free-API quota stop being the ones nobody depends on.
    """
    if days_since_last_score is None:
        return True, "never scored"
    due_in = plan.next_action_in(finding_recheck)
    days = due_in["days"]
    if days is None:
        return False, ("passive — no review cadence and no outstanding finding re-check. "
                       "Re-screened when the relationship changes, not on a clock.")
    if days_since_last_score >= float(days):
        return True, (f"{round(days_since_last_score)} day(s) since last score, against a "
                      f"{days}-day interval set by the {due_in['driver']}")
    return False, (f"{round(days_since_last_score)} of {days} day(s) elapsed — next look set by "
                   f"the {due_in['driver']}")


def as_dict(plan: AssessmentPlan, finding_recheck: str | None = None) -> dict[str, object]:
    return {
        "inherent_tier": plan.tier,
        "tier_label": plan.tier_label,
        "declared": plan.declared,
        "headline": plan.headline(),
        "collection": {
            "depth": plan.depth,
            "sources": sorted(plan.sources) if plan.sources is not None else None,
            "source_note": ("Every on-demand collector runs. `null` rather than a list, so a "
                            "newly registered collector is included automatically."
                            if plan.sources is None else
                            f"Only these {len(plan.sources)} sources run. The rest are not "
                            f"queried, which is where the budget saving comes from."),
            "publishes_posture": plan.publishes_posture,
        },
        "review_cadence": {
            "cadence": plan.cadence,
            "label": plan.cadence_label,
            "days": plan.cadence_days,
        },
        "next_action": plan.next_action_in(finding_recheck),
        "artefacts": list(plan.artefacts),
        "basis": plan.basis,
        "caveats": plan.caveats,
    }


def table() -> list[dict[str, object]]:
    """The published table, for a UI that wants to show a reader where their relationship sits."""
    rows = []
    for tier in ("critical", "high", "medium", "low"):
        p = plan_for(tier)  # type: ignore[arg-type]
        rows.append({
            "inherent_tier": tier, "tier_label": p.tier_label, "depth": p.depth,
            "sources": "all" if p.sources is None else len(p.sources),
            "cadence": p.cadence_label, "cadence_days": p.cadence_days,
            "publishes_posture": p.publishes_posture, "artefacts": list(p.artefacts),
        })
    return rows
