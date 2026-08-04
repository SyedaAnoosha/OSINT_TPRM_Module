"""Recommendation — the step from "here is a score" to "here is what to do about it".

WHY THIS IS A RULE TABLE AND NOT A MODEL. Under Finding A the reasonable-grounds representation
attaches to what we PUBLISH, and a recommendation is published. So it has to be reconstructible:
same inputs, same output, forever, with the rule that produced it nameable in a sentence. A
learned or generated recommendation could not be defended in a dispute, and *"the model said do
not sign"* is not reasonable grounds. This is thirteen lines of table.

WHAT IT CONSUMES, AND WHY EACH IS THERE:
  * `grade`      — how bad the observable posture is.
  * `confidence` — how much of that posture we actually saw. This is the axis that stops the
                   recommendation being wrong in the most dangerous direction: a clean-LOOKING
                   vendor with thin evidence (a Ghost) must route to a questionnaire, not to
                   "approve". Invisibility is not safety.
  * `criticality`— how much THIS buyer depends on the vendor. Client-supplied, never inferred.
                   The same grade C is "conditions" for a replaceable supplier and "do not sign
                   yet" for one holding your production data.

WHAT IT IS NOT. It is **advisory**, and says so on every response. The client decides; we are
telling them what the evidence supports, not making their risk decision for them.
"""

from __future__ import annotations

from ..models import Criticality, Recommendation, Score

# Ordered most urgent first — a re-check cadence is only useful if it is the SOONEST one that
# matters, not an average of the findings.
_RECHECK_ORDER = ["7d", "14d", "30d", "90d"]


def soonest_recheck(a: str | None, b: str | None) -> str | None:
    known = [x for x in (a, b) if x in _RECHECK_ORDER]
    if not known:
        return a or b
    return min(known, key=_RECHECK_ORDER.index)


#: How far below the peer median counts as "materially below peers". Not a scoring threshold —
#: nothing here touches posture — it is a MONITORING CADENCE threshold, and it exists because a
#: supplier that is normal for its industry and one that is fifteen points behind it warrant
#: different review frequencies even at the same grade.
#:
#: 15 rather than a percentile: a percentile needs n>=30 and most cohorts will not have it for a
#: long time, whereas a signed point gap is meaningful from n=8 and is the figure E10a publishes.
_MATERIAL_GAP = -15


def recommend(
    score: Score,
    criticality: Criticality | None = None,
    soonest: str | None = None,
    expectation_gap: int | None = None,
) -> Recommendation:
    """The published recommendation for one score. Deterministic; no LLM anywhere in this path.

    `expectation_gap` is E10a's signed `Posture − E[Posture | cohort]`, and it reaches ONLY the
    monitoring cadence — never the grade, never the decision. A vendor materially below its peers
    at the same grade as one sitting on the median is not a worse vendor by our arithmetic; it is a
    vendor whose position is harder to explain, and the honest response to that is to look again
    sooner, not to score them lower. Letting a peer comparison move a decision would be the
    firmographic multiplier E1 deleted, arriving through the benchmark instead of the sector table.
    """

    # --- terminal states first: these are not gradations of "how risky", they are refusals ---

    if score.blocked:
        return Recommendation(
            decision="blocked",
            headline="Blocked — human adjudication required",
            detail=(
                f"{score.blocked_reason or 'A gate was triggered.'} No score is published for a "
                "blocked record, by design: a sanctions match is adjudicated by a person, and the "
                "adjudication is the evidence. Do not proceed until it is resolved."
            ),
            recheck_after=None,
            urgency="stop",
        )

    if score.refused:
        return Recommendation(
            decision="insufficient_evidence",
            headline="Insufficient evidence to publish a score",
            detail=(
                f"Only {round(score.overall_confidence * 100)}% of the planned evidence returned. "
                "This is not a clean result and must not be read as one — it means we could not "
                "see enough to say anything. Send a security questionnaire."
            ),
            recheck_after="30d",
            urgency="assess",
        )

    grade = (score.grade or "F").upper()
    thin = score.ghost or score.confidence_band == "Low"
    high_stakes = criticality == "high"

    # --- the table ---

    if grade in ("A", "B"):
        if thin:
            # The most important row here. A vendor can look clean simply because nothing is
            # publicly visible about it, and a "proceed" on that basis is the single worst call
            # this system could make.
            decision, headline = "approve_pending_questionnaire", "Proceed with a questionnaire"
            detail = (
                "The observable posture is good, but evidence coverage is thin — this may reflect "
                "a small public footprint rather than strong security. Thin evidence is not a "
                "clean bill of health. Send a questionnaire to cover what OSINT cannot see."
            )
            recheck, urgency = "30d", "assess"
        else:
            decision, headline = "approve", "Proceed"
            detail = (
                "No material issues found in public evidence, with good coverage. Remaining risk "
                "sits in what no external observer can see — access controls, monitoring, data "
                "handling — so this complements a questionnaire rather than replacing one."
            )
            recheck, urgency = "90d", "routine"

    elif grade == "C":
        if high_stakes:
            decision, headline = "request_remediation", "Do not sign yet — request remediation"
            detail = (
                "Serious gaps are visible in public evidence and you have marked this vendor "
                "business-critical. Send the findings below to the vendor, ask for the remediation "
                "evidence each one names, and re-scan before signing."
            )
            recheck, urgency = "7d", "act"
        else:
            decision, headline = "approve_with_conditions", "Proceed with conditions"
            detail = (
                "Serious gaps are visible, but this vendor is not business-critical. Proceed with "
                "the named remediations as contract conditions, and re-check that they land."
            )
            recheck, urgency = "30d", "act"

    elif grade == "D":
        decision, headline = "full_due_diligence", "Full due diligence + executive acceptance"
        detail = (
            "Severe issues are visible from outside. Do not proceed on this evidence alone: run "
            "full due diligence, and if the relationship goes ahead, record an explicit executive "
            "risk acceptance with a named owner, compensating controls, and an expiry date."
        )
        recheck, urgency = "7d", "act"

    else:  # F
        decision, headline = "reject", "Do not proceed"
        detail = (
            "Little evidence of basic security investment. Reject, or proceed only with an "
            "executive risk acceptance, compensating controls (isolate access, no production "
            "data), a named owner and an expiry date."
        )
        recheck, urgency = "7d", "stop"

    if score.critical_ceiling_applied:
        detail += (
            f" A directly-observed critical issue capped this grade ({score.ceiling_cause}); it "
            "cannot be offset by strength elsewhere and should be resolved first."
        )
        recheck = soonest_recheck(recheck, "7d")

    # E10a -> MONITORING CADENCE, and nothing else. `decision`, `headline` and `urgency` are all
    # already fixed by this point; the gap can only shorten the interval.
    #
    # The pairing with criticality is the whole of it: being fifteen points behind your peers is
    # informative for any supplier and ACTIONABLE for one the buyer depends on. A replaceable
    # supplier below its cohort gets a 30-day look rather than 90; a business-critical one gets 14.
    if expectation_gap is not None and expectation_gap <= _MATERIAL_GAP:
        recheck = soonest_recheck(recheck, "14d" if high_stakes else "30d")
        detail += (
            f" This vendor also sits {abs(expectation_gap)} points below the median for its peer "
            f"group, which is materially behind comparable suppliers. That does not change the "
            f"grade — the same evidence scores the same everywhere — but a position this far from "
            f"the norm is worth re-checking sooner than the grade alone would suggest."
        )

    # The soonest re-check any individual finding asks for wins: a 90-day cadence is wrong if one
    # finding on the card says look again in seven days.
    final_recheck = soonest_recheck(recheck, soonest)

    # ...and the urgency has to follow it. A banner reading "Proceed · routine · re-check in 7
    # days" contradicts itself, and a reader resolving that contradiction will believe the headline
    # and ignore the cadence — which is the wrong half to believe. A seven-day cadence means
    # something on this card needs chasing now.
    if final_recheck == "7d" and urgency == "routine":
        urgency = "act"
        detail += (
            " One or more findings below need chasing within the week — see the re-check dates."
        )

    return Recommendation(
        decision=decision, headline=headline, detail=detail,
        recheck_after=final_recheck,
        urgency=urgency,
        criticality=criticality,
    )
