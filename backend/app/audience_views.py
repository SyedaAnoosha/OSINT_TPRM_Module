"""P6 — one immutable score object, two renderings, for two readers who want opposite things.

WHY THIS IS AN ASSEMBLY MODULE AND NOTHING ELSE. Every number these views publish is already
computed by the module that owns it: posture by the engine, residual by the sixteen-cell lookup,
continuity by the registry reader, concentration by P1, contract points by P4, cadence by P5,
coverage by P2, questions by P3. **Nothing is recomputed here.** The moment this file does
arithmetic it becomes a second source of truth about a vendor, and the two views can then disagree
with each other and with `/export` — which is precisely the failure `/assessment` was built to stop
one layer down. A test parses this module and asserts it holds no arithmetic on a posture.

═══ THE TWO READERS ═══

    PROCUREMENT is deciding whether to sign. They read top-down and may stop early, so the order is
    the design: DECISION first, then the exposure it was made against, then what to write into the
    agreement, then what we could not see. A reader who stops halfway has stopped AFTER the decision
    and after the residual tier, never before them.

    SECURITY is doing the work. They read to find the next task, so the order is by what it is
    worth: findings by effective penalty, grouped by the domain that owns them, each carrying its
    receipt, its peer prevalence, its ask and its dispute state. A decision banner would be noise —
    the decision is not theirs and it does not change what needs fixing.

═══ THE RULE THAT KEEPS TWO VIEWS FROM BECOMING TWO STORIES ═══

**A LIMITATION MAY NOT APPEAR ON ONLY ONE VIEW.** This is the one thing a split rendering makes
easy to get wrong, and it is wrong in the dangerous direction every time: put the coverage statement
on the security view alone and the person who SIGNS never learns what the assessment could not see.
So the coverage statement, the confidence figure, and the three-axes caveat travel on BOTH, and a
test asserts it — not by comparing prose, which would drift, but by requiring the same coverage
object and the same posture/confidence pair on each.

The corollary is also enforced: neither view may publish a posture the other lacks, and neither may
publish one at all when the score is blocked or refused. A refusal rendered as a low number is the
single most dangerous transformation this system could perform, and it is exactly the kind of thing
a "make it friendlier for procurement" rendering invites.

═══ WHAT PROCUREMENT DELIBERATELY DOES NOT GET ═══

Not a per-signal worklist. Not because it is secret — `/export` serves the whole record to anyone
who asks — but because twenty-eight rows of DNS minutiae in front of a signer produces one of two
outcomes: the decision is made on the first row, or the page is skipped. The evidence request pack
is attached instead: the same findings, already turned into questions with a stated closing
standard, which is the form a non-specialist can actually act on.
"""

from __future__ import annotations

from typing import Any

#: Carried on BOTH views. Each is a limitation on the whole assessment rather than on one section,
#: and a limitation that only one reader sees is a limitation the other one acts without.
_SHARED_CAVEATS = [
    "THREE SEPARATE MEASUREMENTS, never collapsed into one number. Posture is what we observed of "
    "the vendor's controls. Confidence is how much of the model we managed to see. Inherent "
    "exposure is declared by the buyer and is not about the vendor at all. A single 'risk score' "
    "would hide which of the three moved.",
    "This is an OUTSIDE-IN assessment. Internal access control, BCP/DR testing, subprocessor "
    "contracts, insurance and staff practices are invisible to it by construction — see the "
    "coverage statement, which is attached to both renderings for exactly this reason.",
    "Both renderings are arrangements of ONE immutable score object. Neither recomputes anything, "
    "so they cannot disagree; if a figure looks different between them, that is a defect and not "
    "a difference of opinion.",
]


def _posture_block(score: Any) -> dict[str, Any]:
    """The one place either view reads the score. Copied, never derived.

    `posture` is None whenever the record is blocked or refused, and that is load-bearing: a
    refusal must never surface as a low number on a rendering built for a reader in a hurry.
    """
    publishable = not (score.blocked or score.refused)
    return {
        "posture": score.posture if publishable else None,
        "grade": score.grade if publishable else None,
        "confidence": score.overall_confidence,
        "confidence_band": score.confidence_band,
        "published": publishable,
        "blocked": score.blocked,
        "blocked_reason": score.blocked_reason,
        "refused": score.refused,
        "ghost": score.ghost,
        "not_published_because": (
            score.blocked_reason if score.blocked else
            "Evidence coverage is below the floor. This is an ADVERSE result, not a neutral one — "
            "it means we could not see enough to say anything." if score.refused else None
        ),
        "critical_ceiling_applied": score.critical_ceiling_applied,
        "confidence_ceiling_applied": score.confidence_ceiling_applied,
    }


def procurement_dossier(
    *,
    vendor_ref: str,
    score: Any,
    recommendation: Any,
    residual: dict[str, Any],
    continuity: Any,
    concentration: list[str],
    flowdowns: dict[str, Any],
    assessment_plan: dict[str, Any],
    coverage: dict[str, Any],
    evidence_pack: dict[str, Any],
    status_page: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The signer's page, in the plan's published order — decision first, ask last.

    THE ORDER IS THE FEATURE. It is asserted by test rather than left to whoever renders it, because
    a template that floats the evidence pack above the residual tier turns a decision aid into a
    task list, and the reader most likely to stop early is the one whose signature matters most.
    """
    sections: list[dict[str, Any]] = [
        {
            "key": "decision",
            "title": "Recommended decision",
            "body": recommendation,
            "note": "ADVISORY. The evidence supports this; the risk decision is yours.",
        },
        {
            "key": "residual_risk",
            "title": "Residual risk — posture against declared exposure",
            "body": residual,
            "note": ("A deterministic lookup over the published posture and the client-declared "
                     "inherent tier. Dispute an input, never the cell."),
        },
        {
            "key": "continuity",
            "title": "Continuity — will they still be here",
            "body": {
                "standing": continuity.standing,
                "flags": [f.cited() for f in continuity.flags],
                "age_context": list(continuity.age_context),
                # P7 — SERVICE AVAILABILITY SITS BESIDE GOING-CONCERN, NEVER INSIDE IT. "Is this
                # entity still a legal person" and "does their service fall over" are different
                # questions, and folding the second into the first `standing` would let an outage
                # read as a solvency signal — the same conflation E4 undid when it moved
                # going-concern out of Posture.
                "service_availability": status_page,
                "caveats": list(continuity.caveats),
            },
            "note": ("Registry-cited facts with retrieval dates, deliberately NOT scored. A "
                     "going-concern flag is not weaker security, and a missing status page is not "
                     "an outage record — both are absences of evidence, stated as such."),
        },
        {
            "key": "concentration",
            "title": "Fourth-party concentration",
            "body": {
                "single_points_of_failure": concentration,
                "statement": (
                    f"This vendor depends on {len(concentration)} provider(s) that at least half "
                    f"the book's business-critical vendors also depend on: "
                    f"{', '.join(concentration)}."
                    if concentration else
                    "No provider this vendor depends on is a book-wide single point of failure on "
                    "the current portfolio. That is a portfolio fact and it changes as the book "
                    "changes."
                ),
            },
            "note": "A shared outage removes several suppliers at once, not one.",
        },
        {
            "key": "contract_conditions",
            "title": "Suggested contract flow-downs",
            "body": flowdowns,
            "note": "SUGGESTED DRAFTING POINTS, NOT LEGAL ADVICE. Have counsel draft and negotiate.",
        },
        {
            "key": "monitoring_cadence",
            "title": "Monitoring cadence and assessment depth",
            "body": assessment_plan,
            "note": ("Two clocks: the review cadence tracks the relationship, a finding's re-check "
                     "date tracks one thing we found. The sooner wins and neither replaces the "
                     "other."),
        },
        {
            "key": "coverage_statement",
            "title": "What this assessment could not see",
            "body": coverage,
            "note": ("Derived from what this run actually did, never written by hand. Read it "
                     "before relying on an absence of findings."),
        },
        {
            "key": "evidence_request_pack",
            "title": "What to ask the vendor",
            "body": evidence_pack,
            "note": ("Only what we observed failing, each question stating what evidence would "
                     "close it. Answers travel back through the dispute path."),
        },
    ]
    return {
        "audience": "procurement",
        "vendor_ref": vendor_ref,
        "posture": _posture_block(score),
        "sections": sections,
        "section_order": [s["key"] for s in sections],
        "caveats": list(_SHARED_CAVEATS),
    }


def security_dossier(
    *,
    vendor_ref: str,
    score: Any,
    findings: list[dict[str, Any]],
    receipts: list[dict[str, Any]],
    category_postures: list[dict[str, Any]],
    peer_signals: list[dict[str, Any]],
    evidence_pack: dict[str, Any],
    coverage: dict[str, Any],
    assessment_plan: dict[str, Any],
    soonest_recheck: str | None,
) -> dict[str, Any]:
    """The worklist. Ordered by what it is worth, grouped by who owns it, every row with a receipt.

    PEER PREVALENCE IS CONTEXT AND CANNOT MOVE A NUMBER — the same rule E10a follows. Knowing that
    six of eight peers publish a DMARC policy does not make this vendor's missing one worse; it
    makes it harder to defend, which is a different and more useful fact for the person who has to
    argue for the remediation ticket.
    """
    charged = [f for f in findings if float(f.get("effective_penalty") or 0.0) > 0]
    charged.sort(key=lambda f: (-float(f.get("effective_penalty") or 0.0), f.get("signal") or ""))

    by_domain: dict[str, list[dict[str, Any]]] = {}
    for f in charged:
        by_domain.setdefault(f.get("category") or "uncategorised", []).append(f)

    prevalence = {s.get("signal"): s for s in peer_signals if s.get("signal")}
    drilldown = []
    for cat, rows in sorted(by_domain.items(),
                            key=lambda kv: -sum(float(r.get("effective_penalty") or 0.0)
                                                for r in kv[1])):
        drilldown.append({
            "category": cat,
            "outstanding_points": round(
                sum(float(r.get("effective_penalty") or 0.0) for r in rows), 2),
            "findings": [
                {
                    "signal": r.get("signal"), "band": r.get("band_key"),
                    "severity": r.get("severity"), "observed": r.get("observed"),
                    "effective_penalty": r.get("effective_penalty"),
                    "why_it_matters": r.get("reason"),
                    "recommended_action": r.get("action"),
                    "ask_of_vendor": r.get("ask_of_vendor"),
                    "accepts_as_refute": r.get("accepts_as_refute"),
                    "recheck_after": r.get("recheck_after"),
                    "evidence_id": r.get("evidence_id"),
                    "dispute_status": r.get("dispute_status"),
                    "peer_prevalence": prevalence.get(r.get("signal")),
                }
                for r in rows
            ],
        })

    return {
        "audience": "security",
        "vendor_ref": vendor_ref,
        "posture": _posture_block(score),
        "total_outstanding_points": round(
            sum(float(f.get("effective_penalty") or 0.0) for f in charged), 2),
        "soonest_recheck": soonest_recheck,
        "category_postures": category_postures,
        "drilldown": drilldown,
        "evidence_receipts": receipts,
        "remediation_asks": evidence_pack,
        # Carried here as well as on the procurement view — see the module docstring. A worklist
        # that does not say which domains were never observed lets an engineer close a category on
        # the strength of a collector that failed.
        "coverage_statement": coverage,
        "assessment_plan": assessment_plan,
        "caveats": list(_SHARED_CAVEATS) + [
            "PEER PREVALENCE IS CONTEXT AND MOVES NOTHING. The same evidence scores identically in "
            "every cohort; how many peers pass a control changes how easy the gap is to defend, "
            "not what it costs.",
            "Findings with no penalty are not listed here. They are in /export and in the "
            "reconstruction block, so the arithmetic on the front page still balances.",
        ],
    }


def views_agree(procurement: dict[str, Any], security: dict[str, Any]) -> list[str]:
    """Every way the two renderings disagree. Empty list means they do not.

    THIS IS AN ASSERTION HELPER THAT SHIPS, not a test fixture. A split rendering can drift the day
    someone adds a field to one view, and the failure is silent: two documents about one vendor,
    each internally consistent, quoting different numbers. Callers can run this in a smoke test or
    a health check; the test suite runs it on every shape it builds.
    """
    problems: list[str] = []
    p, s = procurement["posture"], security["posture"]
    for field in ("posture", "grade", "confidence", "published", "blocked", "refused", "ghost"):
        if p.get(field) != s.get(field):
            problems.append(f"{field}: procurement={p.get(field)!r} security={s.get(field)!r}")
    if procurement["vendor_ref"] != security["vendor_ref"]:
        problems.append("vendor_ref differs")

    # A LIMITATION ON ONLY ONE VIEW is the failure this whole helper exists for.
    proc_coverage = next((sec["body"] for sec in procurement["sections"]
                          if sec["key"] == "coverage_statement"), None)
    if proc_coverage != security.get("coverage_statement"):
        problems.append("coverage statement differs between the two renderings")
    return problems
