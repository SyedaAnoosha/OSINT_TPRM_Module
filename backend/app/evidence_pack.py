"""P3 — the Evidence Request Pack. The bridge from outside-in to inside-out.

THE FEATURE THAT MAKES THIS A TPRM MODULE RATHER THAN A RATING. A rating tells a buyer a number. A
TPRM module tells them what to ask, why, and what answer would close it.

                    │ SIG Lite                │ Evidence Request Pack
    ────────────────┼─────────────────────────┼──────────────────────────────────────────
    Questions       │ ~300, fixed             │ ONLY what was observed failing
    Basis           │ Generic                 │ Cited to a finding + evidence id
    Resolution      │ Manual                  │ The evidence standard is stated up front
    Closure         │ An email thread         │ Dispute -> nullify/mitigate -> re-score

WHY THIS IS ~80% BUILT ALREADY, AND WHY THAT IS THE POINT. `scoring.yaml` carries 41
`ask_of_vendor`, 41 `accepts_as_refute` and 41 `recheck_after` entries — one per penalising band,
written when the band was written and, until now, read by nothing. (The plan says 58; that was
measured against v4.2.0, before E2/E3/E5 reclassified bands to informational. Nothing here depends
on the count — `_validate_every_penalty_is_actionable` asserts the correspondence, not a literal.) The dispute-adjudication half
(`nullify` / `mitigate` -> re-score with the reason recorded) has existed and been tested since
Phase 4. **The loop was two finished halves and no join**, which is exactly the shape P1 was in.

WHAT THIS MODULE ADDS is the assembly and the discipline around it:

  * ONLY WHAT WAS OBSERVED FAILING. A pack scoped to a vendor's actual findings is answerable in an
    afternoon; a 300-question standard is answered by an intern copying last year's. The value is
    in what is NOT asked.
  * EVERY QUESTION CITES ITS FINDING AND ITS EVIDENCE ID. A vendor who can see what we saw argues
    about the observation rather than about our motives, and an observation is arguable in a way a
    score is not.
  * THE REFUTE STANDARD TRAVELS WITH THE QUESTION. `accepts_as_refute` says what evidence would
    close this, up front. A request that does not say what would satisfy it is a request that
    generates a thread rather than an answer.
  * ORDERED BY WHAT IT IS WORTH. The pack leads with the finding carrying the most posture points,
    so a vendor with limited time spends it where it moves the number.

AND THE THING IT MUST NOT DO: it computes nothing, scores nothing, and changes no posture. A pack
is a set of questions. The answers travel back through the DISPUTE path, which already adjudicates,
records the reason, and re-scores — and which is the only route by which a vendor's response may
touch a number.

TWO RENDERINGS OVER ONE DATASET, because the two readers are answering different questions and a
single ordering serves neither.

  * PROCUREMENT is deciding whether to sign, and their question is *which of these stops the deal*.
    So each item carries a **blocking / condition / informational** tag, and that tag cannot come
    from severity alone: a missing DMARC record is a footnote on a stationery supplier and a
    blocking item on the vendor holding production customer data. It is severity × INHERENT TIER —
    the same non-compensatory input E10b takes, and the one element the plan correctly identified
    as not already living in `scoring.yaml`.
  * SECURITY is doing the work, and their question is *what do I chase first*. Ordered by effective
    penalty, grouped by category so one person can take one domain, and carrying dispute state so
    an item already under adjudication is not chased twice.

PER-DOMAIN COVERAGE TRAVELS ON BOTH. A pack built from five collectors is not the same artefact as
one built from twelve, and the failure is silent and flattering: a category nothing reported on
produces no questions, which is indistinguishable on the page from a category that was checked and
came back clean. Naming the covered ratio per category is what separates *"we asked and it was
fine"* from *"we never got to look"* — the same distinction P2 draws for the assessment as a whole.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: The re-check cadences, most urgent first — the pack inherits each item's own cadence rather than
#: imposing one, because "answer everything in 7 days" is how a pack gets ignored wholesale.
_URGENCY = ["7d", "14d", "30d", "90d"]

#: PROCUREMENT'S TAG: severity × inherent tier -> what this item does to the decision. Sixteen
#: cells, deterministic, and deliberately shaped like E10b's residual matrix because it is the same
#: argument applied to one finding rather than to the whole vendor.
#:
#: READ DOWN A COLUMN and the point is visible: the same missing DMARC record is `informational`
#: against a low-exposure supplier and `blocking` against one holding production data. A tag derived
#: from severity alone would either block every deal on a header or wave through a critical finding
#: on the vendor with the most to lose — which is why the plan flagged this as the one element not
#: already in the model.
_DECISION: dict[str, dict[str, str]] = {
    "critical": {"low": "condition", "medium": "blocking", "high": "blocking",
                 "critical": "blocking"},
    "high": {"low": "informational", "medium": "condition", "high": "blocking",
             "critical": "blocking"},
    "medium": {"low": "informational", "medium": "informational", "high": "condition",
               "critical": "condition"},
    "low": {"low": "informational", "medium": "informational", "high": "informational",
            "critical": "condition"},
}

_DECISION_MEANING: dict[str, str] = {
    "blocking": "Do not sign until this is answered. The finding is serious enough, and this "
                "relationship exposed enough, that an unanswered question is an accepted risk "
                "nobody has decided to accept.",
    "condition": "Sign if you must, with this written in as a condition precedent or a remediation "
                 "milestone with a date. Escalating it to blocking is a judgement call; leaving it "
                 "unwritten is not.",
    "informational": "Record it and re-check on the stated cadence. It does not carry this "
                     "decision on its own.",
}

#: Order for rendering — the reader must meet the deal-stoppers first.
_DECISION_RANK = {"blocking": 0, "condition": 1, "informational": 2, "untagged": 3}


@dataclass
class EvidenceRequest:
    """One question, the observation behind it, and what would close it."""

    signal: str
    band_key: str
    severity: str | None
    observed: str
    charged: float
    question: str
    accepts_as_refute: str
    recheck_after: str | None
    reason: str | None = None
    action: str | None = None
    evidence_id: str | None = None
    category: str | None = None
    dispute_status: str | None = None

    def cited(self) -> str:
        """The question as it appears in the pack — observation first, then the ask.

        Leading with what we SAW rather than with what we want is deliberate: a vendor who is shown
        the observation can correct it, and a correction is a better outcome for both sides than a
        defended score.
        """
        return (f"We observed {self.signal} = {self.observed}. {self.question} "
                f"What would close this: {self.accepts_as_refute}.")


@dataclass
class DomainCoverage:
    """What one category actually contributed to this pack — and whether it was looked at.

    THE DISTINCTION THIS EXISTS FOR. A category that raised no questions reads as clean. It is
    equally consistent with a collector that never returned, and those are opposite facts about the
    vendor. Silence is only good news once you know somebody asked.
    """

    category: str
    signals_observed: int
    signals_planned: int
    questions: int

    @property
    def coverage(self) -> float:
        return (self.signals_observed / self.signals_planned) if self.signals_planned else 0.0

    def note(self) -> str:
        if self.signals_planned and not self.signals_observed:
            return (f"NOT OBSERVED — no signal in {self.category} returned data on this run, so "
                    f"the absence of questions here says nothing about the vendor.")
        if self.questions == 0:
            return (f"{self.signals_observed} of {self.signals_planned} signals observed, none "
                    f"failing. Clean, and evidenced as clean.")
        return (f"{self.signals_observed} of {self.signals_planned} signals observed, "
                f"{self.questions} raising a question.")


@dataclass
class EvidencePack:
    vendor_ref: str
    requests: list[EvidenceRequest] = field(default_factory=list)
    not_asked: int = 0
    soonest_recheck: str | None = None
    caveats: list[str] = field(default_factory=list)
    domains: list[DomainCoverage] = field(default_factory=list)

    @property
    def question_count(self) -> int:
        return len(self.requests)

    def summary(self) -> str:
        if not self.requests:
            return ("No externally observable findings are outstanding for this vendor, so this "
                    "pack asks nothing. That is a real result, not an empty template — but it "
                    "covers only what is observable from outside.")
        return (f"{self.question_count} question(s), each tied to something we observed and each "
                f"stating what evidence would close it. "
                f"{self.not_asked} scored signal(s) are clean and are not asked about.")


def _domain_coverage(findings: list[Any], asked: list[EvidenceRequest], cfg: Any
                     ) -> list[DomainCoverage]:
    """Per-category coverage, planned from the model and observed from this run's findings.

    `unreachable_signals()` is subtracted from the plan for the same reason E12 had to subtract it
    from the confidence denominator: a signal that cannot fire under the shipped configuration is
    not a gap in what we looked at, and counting it as one understates coverage for a feature that
    is switched off.
    """
    unreachable = cfg.unreachable_signals()
    observed: dict[str, set[str]] = {}
    for f in findings:
        cat = getattr(f, "category", None)
        if cat:
            observed.setdefault(cat, set()).add(f.signal)
    asked_by_cat: dict[str, int] = {}
    for r in asked:
        if r.category:
            asked_by_cat[r.category] = asked_by_cat.get(r.category, 0) + 1

    out: list[DomainCoverage] = []
    for category in cfg.categories:
        planned = [s for s in cfg.signals_of(category) if s not in unreachable]
        out.append(DomainCoverage(
            category=category,
            signals_observed=len(observed.get(category, set()) & set(planned)),
            signals_planned=len(planned),
            questions=asked_by_cat.get(category, 0),
        ))
    return out


def build_pack(vendor_ref: str, findings: list[Any], cfg: Any,
               disputes: dict[tuple[str, str], str] | None = None) -> EvidencePack:
    """Assemble the pack from findings that actually cost this vendor something.

    `findings` are `PersistedFinding`s (or anything carrying `.signal`, `.band_key`,
    `.effective_penalty`, `.observed` and `.evidence_id`). `cfg` is the `ScoringConfig` — the
    questions live in the model beside the bands they belong to, which is what keeps a question and
    the rule that raised it from drifting apart.

    A FINDING THAT COST NOTHING RAISES NO QUESTION. Asking a vendor about a passing control wastes
    the one commodity this process runs on, which is their willingness to answer the next one.
    """
    requests: list[EvidenceRequest] = []
    clean = 0
    seen: set[tuple[str, str]] = set()

    for f in findings:
        charged = float(getattr(f, "effective_penalty", 0.0) or 0.0)
        if charged <= 0:
            clean += 1
            continue
        key = (f.signal, f.band_key)
        if key in seen:
            continue          # one question per observation, however many times it fired
        seen.add(key)

        action = cfg.action_for(f.signal, f.band_key) or {}
        question = str(action.get("ask_of_vendor") or "").strip()
        refute = str(action.get("accepts_as_refute") or "").strip()
        if not question or not refute:
            # Unreachable on the shipped config — `_validate_every_penalty_is_actionable` refuses a
            # penalising band without both. Guarded anyway: a pack that silently drops a question
            # would understate what is outstanding, and a caller cannot tell the difference.
            continue
        requests.append(EvidenceRequest(
            signal=f.signal, band_key=f.band_key,
            severity=getattr(f, "severity", None),
            observed=getattr(f, "observed", f.band_key),
            charged=round(charged, 2),
            question=question,
            accepts_as_refute=refute,
            recheck_after=action.get("recheck_after"),
            reason=cfg.reason_for(f.signal, f.band_key),
            action=action.get("action"),
            evidence_id=getattr(f, "evidence_id", None),
            category=getattr(f, "category", None),
            # An item already under adjudication is still ASKED — the question is what was
            # outstanding when the pack was cut — but a security reader chasing it a second time is
            # wasted work, and a vendor asked about something they have already refuted reasonably
            # concludes nobody read their response.
            dispute_status=(disputes or {}).get(key),
        ))

    # Worth the most first. A vendor with limited time should spend it where it moves the number,
    # and a pack that opens with a low-severity header is a pack that gets triaged into a backlog.
    requests.sort(key=lambda r: (-r.charged, r.signal))

    cadences = [r.recheck_after for r in requests if r.recheck_after in _URGENCY]
    soonest = min(cadences, key=_URGENCY.index) if cadences else None

    return EvidencePack(
        vendor_ref=vendor_ref, requests=requests, not_asked=clean, soonest_recheck=soonest,
        domains=_domain_coverage(findings, requests, cfg),
        caveats=[
            "This pack asks ONLY about what we observed failing. It is not a substitute for a "
            "full security questionnaire: everything outside-in assessment cannot see — internal "
            "access controls, BCP/DR testing, subprocessor contracts, insurance — is absent here "
            "by construction. See the coverage statement for the full boundary.",
            "Every question cites the observation behind it and an evidence id. If an observation "
            "is wrong, correcting it is the fastest route to closing the item — raise a dispute "
            "rather than answering the question.",
            "Answering a question does not by itself change the score. Responses travel through "
            "the dispute path, which adjudicates, records the reason, and re-scores — so a change "
            "to a published number always has a decision behind it.",
        ],
    )


# ============================================================ the two renderings


def decision_tag(severity: str | None, inherent_tier: str | None) -> str | None:
    """`blocking` / `condition` / `informational`, or None when the tier is not declared.

    NONE IS A REAL ANSWER AND MUST STAY ONE. Defaulting an undeclared inherent tier to `low` would
    tag every item on every un-triaged relationship as informational — and the relationships nobody
    has classified are disproportionately the ones nobody has looked at, so the failure lands
    exactly where it does the most damage. Same rule E10b applies to the residual cell, for the same
    reason.

    An `informational` SEVERITY is never tagged either: it is recorded and not scored, so it cannot
    carry a procurement decision at any exposure.
    """
    if not inherent_tier or not severity:
        return None
    return _DECISION.get(severity, {}).get(inherent_tier)


def procurement_view(pack: EvidencePack, inherent_tier: str | None,
                     inherent_basis: str | None = None) -> dict[str, Any]:
    """The outbound request, ordered by what it does to the DECISION rather than to the score.

    A procurement reader is not triaging remediation; they are deciding whether to sign, and on
    that question a 17.5-point finding on a low-exposure supplier genuinely matters less than an
    8-point one on the vendor holding production data. Ordering by penalty would put those the wrong
    way round on the page, so the tag leads and the penalty breaks ties within it.
    """
    items = []
    for r in pack.requests:
        tag = decision_tag(r.severity, inherent_tier)
        items.append({
            "decision": tag or "untagged",
            "what_it_means": _DECISION_MEANING.get(tag or "", (
                "Inherent exposure has not been declared for this relationship, so this item "
                "cannot be tagged. That is an open question, not a low rating — declare business "
                "criticality and data access scope to resolve it."
            )),
            "signal": r.signal, "severity": r.severity, "category": r.category,
            "request": r.cited(), "recheck_after": r.recheck_after,
            "evidence_id": r.evidence_id, "posture_points_charged": r.charged,
        })
    items.sort(key=lambda i: (_DECISION_RANK[i["decision"]], -i["posture_points_charged"],
                              i["signal"]))

    counts: dict[str, int] = {}
    for i in items:
        counts[i["decision"]] = counts.get(i["decision"], 0) + 1

    return {
        "audience": "procurement",
        "vendor_ref": pack.vendor_ref,
        "inherent_tier": inherent_tier,
        "inherent_basis": inherent_basis,
        "tag_counts": counts,
        "headline": (
            f"{counts.get('blocking', 0)} blocking, {counts.get('condition', 0)} to write into the "
            f"contract, {counts.get('informational', 0)} for the record."
            if inherent_tier else
            "Inherent exposure is NOT DECLARED for this relationship, so no item carries a "
            "blocking / condition / informational tag. Severity alone cannot produce one: the same "
            "missing DMARC record is a footnote on a stationery supplier and a deal-stopper on the "
            "vendor holding production customer data."
        ),
        "items": items,
        "coverage": [{"category": d.category, "note": d.note()} for d in pack.domains],
        "caveats": pack.caveats,
    }


def security_view(pack: EvidencePack) -> dict[str, Any]:
    """The inbound worklist: by effective penalty, grouped so one person can take one domain.

    GROUPED BY CATEGORY BECAUSE THAT IS HOW THE WORK DIVIDES. A flat list ordered by penalty sends
    one engineer between DNS, TLS and headers three times over; the domains are owned by different
    people and often by different teams. Within a group the ordering is still by what it is worth.

    EVERY GROUP APPEARS, INCLUDING THE EMPTY ONES, carrying its coverage note — because a category
    with no work in it is either clean or unobserved, and the worklist is exactly where somebody is
    entitled to know which.
    """
    by_cat: dict[str, list[EvidenceRequest]] = {}
    for r in pack.requests:
        by_cat.setdefault(r.category or "uncategorised", []).append(r)

    groups = []
    for d in pack.domains:
        rows = sorted(by_cat.pop(d.category, []), key=lambda r: (-r.charged, r.signal))
        groups.append({
            "category": d.category,
            "coverage": {"observed": d.signals_observed, "planned": d.signals_planned,
                         "ratio": round(d.coverage, 3), "note": d.note()},
            "outstanding_points": round(sum(r.charged for r in rows), 2),
            "items": [{
                "signal": r.signal, "band": r.band_key, "severity": r.severity,
                "observed": r.observed, "posture_points_charged": r.charged,
                "why_it_matters": r.reason, "recommended_action": r.action,
                "accepts_as_refute": r.accepts_as_refute, "recheck_after": r.recheck_after,
                "evidence_id": r.evidence_id,
                # `None` means no dispute has been raised. An ACCEPTED refute would already have
                # zeroed or discounted the penalty, so anything still listed here with a status is
                # in flight — which is the one state worth surfacing on a worklist.
                "dispute_status": r.dispute_status,
            } for r in rows],
        })
    # Anything whose category is not in the model still has to appear. Dropping it would make a
    # config drift look like clean work.
    for category, rows in sorted(by_cat.items()):
        groups.append({
            "category": category,
            "coverage": {"observed": None, "planned": None, "ratio": None,
                         "note": "This category is not in the shipped model — the finding carries a "
                                 "category the config does not define. Investigate rather than "
                                 "ignore."},
            "outstanding_points": round(sum(r.charged for r in rows), 2),
            "items": [{"signal": r.signal, "band": r.band_key, "severity": r.severity,
                       "posture_points_charged": r.charged, "dispute_status": r.dispute_status}
                      for r in rows],
        })

    groups.sort(key=lambda g: (-g["outstanding_points"], g["category"]))
    return {
        "audience": "security",
        "vendor_ref": pack.vendor_ref,
        "total_outstanding_points": round(sum(r.charged for r in pack.requests), 2),
        "soonest_recheck": pack.soonest_recheck,
        "in_dispute": sum(1 for r in pack.requests if r.dispute_status),
        "groups": groups,
        "caveats": pack.caveats,
    }


def as_dict(pack: EvidencePack) -> dict[str, Any]:
    return {
        "vendor_ref": pack.vendor_ref,
        "summary": pack.summary(),
        "question_count": pack.question_count,
        "clean_signals_not_asked": pack.not_asked,
        "soonest_recheck": pack.soonest_recheck,
        "requests": [
            {
                "signal": r.signal, "band": r.band_key, "severity": r.severity,
                "observed": r.observed, "posture_points_charged": r.charged,
                "question": r.question, "accepts_as_refute": r.accepts_as_refute,
                "recheck_after": r.recheck_after, "why_it_matters": r.reason,
                "recommended_action": r.action, "evidence_id": r.evidence_id,
                "category": r.category, "dispute_status": r.dispute_status,
                "cited": r.cited(),
            }
            for r in pack.requests
        ],
        # A pack built from five collectors is not the same artefact as one built from twelve, and
        # a category that raised no questions is either clean or unobserved. Both readers get this.
        "per_domain_coverage": [
            {"category": d.category, "signals_observed": d.signals_observed,
             "signals_planned": d.signals_planned, "coverage": round(d.coverage, 3),
             "questions": d.questions, "note": d.note()}
            for d in pack.domains
        ],
        "caveats": pack.caveats,
    }
