"""P9 — the KPI/KRI dashboard. Fifteen metrics, built only from what the platform already produces.

THE RULE THAT SHAPES EVERY LINE OF THIS FILE: *"build from data the platform already produces — do
not invent new collection for this."* A programme dashboard that needs its own collectors is a
second product, and the metrics it would add are the ones nobody maintains after the first quarter.

═══ TWO KINDS OF NUMBER, NEVER PRINTED AS ONE ═══

    platform-derived   Computed here, from the store, on every read. Reproducible, and wrong only
                       if the underlying data is wrong.
    manually-supplied  Staffing ratio, cost per assessment, policy exception rate. NO OSINT SOURCE
                       EXISTS. They are declared with a value or they are `null`.
                       (`stakeholder_satisfaction` was the fourth; E14 argued it out in favour of
                       `gap_analysis_acceptance_rate` — see the note above `MetricValue`.)

**A manually-supplied metric is never backfilled, estimated, or defaulted to make the dashboard look
complete.** An unsupplied metric renders as "not supplied" and says who owns supplying it. The
temptation is exactly the one P2 refuses for coverage and E10b refuses for the residual cell: a
plausible number in an empty cell is worse than an empty cell, because the empty cell asks a
question and the plausible number answers it wrongly.

═══ THE METRICS ARE CHOSEN TO BE ACTIONABLE, NOT FLATTERING ═══

Three of them measure things this programme is currently bad at, and they were chosen for that
reason. `inherent_tier_declaration_rate` is the input on which residual risk, P3's decision tag and
P5's cadence all silently degrade. `blocked_pending_adjudication` is the queue whose depth turns
adjudication into a rubber stamp — the failure mode the sanctions matcher fix was about.
`overdue_rechecks` is the SLA that `recheck_after` states per finding and nothing has ever enforced
in aggregate.

A dashboard whose every metric is green is a dashboard measuring the wrong things.

═══ EXTERNAL PEER FIGURES ═══

Participation in Shared Assessments / Gartner / Crowe surveys happens outside this codebase. What
is built here is a place to RECORD the resulting figures, and a refusal: a peer figure without a
survey name, a year and an `n` is not published. Same discipline EB enforces for vendor cohorts,
and for the same reason — a comparison whose population is unstated is a number pretending to be a
benchmark.

═══ NOTHING HERE REACHES A VENDOR SCORE ═══

Every metric READS the store. None writes, and no KPI value is an input to any vendor-level number.
Asserted by test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .assessment_depth import is_due, plan_for
from .inherent_register import classify as register_classify
from .inherent_register import coverage as register_coverage
from .inherent_register import relationships as register_relationships
from .logging_config import get_logger
from .models import utcnow
from .residual_risk import inherent_tier, residual_risk
from .scheduler import monitoring_health

log = get_logger("program_kpis")

Provenance = Literal["platform-derived", "manually-supplied"]


@dataclass(frozen=True)
class Metric:
    """A metric DEFINITION — everything a reader needs to argue with the number."""

    key: str
    name: str
    owner: str
    formula: str
    source: str
    target: str
    cadence: str
    provenance: Provenance
    #: True when a lower number is better, so a UI cannot invert a KRI by accident.
    lower_is_better: bool = False


#: ═══ THE FIFTEEN ═══ Eleven computed, four declared. The plan caps this at fifteen and the cap is
#: the point: a dashboard nobody reads is one with thirty rows on it.
METRICS: tuple[Metric, ...] = (
    Metric("tier1_assessment_currency", "Tier-1 assessment currency",
           owner="TPRM lead",
           formula="critical-tier vendors scored within their P5 review cadence / all critical-tier vendors",
           source="latest scores + E10b inherent tier + P5 cadence",
           target="100%", cadence="monthly", provenance="platform-derived"),
    Metric("inherent_tier_declaration_rate", "Inherent tier declaration rate",
           owner="Vendor relationship owners",
           formula="RELATIONSHIPS with criticality OR data access scope declared / all "
                   "relationships. The denominator is the register's relationship population, NOT "
                   "every scored row: a seeded benchmarking vendor has no relationship and so no "
                   "exposure to declare. Confirmed and provisional are reported separately.",
           source="app/inherent_register.py + VendorProfile.criticality + supplier attributes",
           target="100% declared, 100% confirmed", cadence="monthly", provenance="platform-derived"),
    Metric("substitutability_declaration_rate", "Substitutability declaration rate",
           owner="Vendor relationship owners",
           formula="relationships with substitutability declared / all relationships",
           source="app/inherent_register.py + VendorProfile.substitutability (P8)",
           target="100% of critical-tier", cadence="quarterly", provenance="platform-derived"),
    Metric("published_posture_rate", "Published posture rate",
           owner="TPRM lead",
           formula="scores that are neither blocked nor refused / all scored vendors",
           source="latest scores",
           target=">=90%", cadence="monthly", provenance="platform-derived"),
    Metric("ghost_rate", "Ghost rate (refused for thin evidence)",
           owner="Platform owner",
           formula="refused scores / all scored vendors",
           source="latest scores",
           target="<=10%", cadence="monthly", provenance="platform-derived",
           lower_is_better=True),
    Metric("blocked_pending_adjudication", "Blocked, pending human adjudication",
           owner="Sanctions adjudicator",
           formula="count of latest scores with blocked = true",
           source="latest scores + the sanctions gate",
           target="0 older than 5 business days", cadence="weekly",
           provenance="platform-derived", lower_is_better=True),
    Metric("assessment_cycle_time_median", "Assessment cycle time (median, seconds)",
           owner="Platform owner",
           formula="median(score.computed_at - earliest evidence.fetched_at) per vendor",
           source="pipeline timestamps",
           target="survey median 30-45 days for a full cycle; this measures the AUTOMATED leg only",
           cadence="quarterly", provenance="platform-derived", lower_is_better=True),
    Metric("overdue_rechecks", "Findings past their re-check date",
           owner="Security remediation owner",
           formula="charged findings whose recheck_after has elapsed since the score was computed",
           source="P3 recheck_after + score timestamps",
           target="0", cadence="weekly", provenance="platform-derived", lower_is_better=True),
    Metric("residual_risk_distribution", "Residual risk distribution",
           owner="TPRM lead",
           formula="count of vendors per residual tier (E10b lookup, recomputed on read)",
           source="E10b matrix over posture x inherent tier",
           target="no critical-tier residual unaccepted", cadence="monthly",
           provenance="platform-derived"),
    Metric("fourth_party_spof_count", "Fourth-party single points of failure",
           owner="TPRM lead",
           formula="providers on which >=50% of critical-tier vendors depend (P1)",
           source="app/concentration.py",
           target="0 unmitigated", cadence="quarterly", provenance="platform-derived",
           lower_is_better=True),
    Metric("monitoring_currency", "Monitoring currency",
           owner="Platform owner",
           formula="vendors NOT overdue against their P5 tier interval / all scored vendors",
           source="P5 assessment plan + latest score timestamps",
           target=">=95%", cadence="monthly", provenance="platform-derived"),
    # E14. THE METRIC THAT ARGUED ANOTHER ONE OUT — see the note below the tuple. Genuinely
    # platform-derived (the accept/edit/reject log costs nothing extra to read), which the four
    # manually-supplied metrics below it are not.
    Metric("gap_analysis_acceptance_rate", "Gap analysis recommendation acceptance rate",
           owner="TPRM lead",
           formula="(accepted + edited) recommendation events / (accepted + edited + rejected) "
                   "recommendation events, across every generated analysis. Pending "
                   "(never dispositioned) recommendations are excluded from both sides.",
           source="app/gap_analysis.py + GapAnalysisRecommendationEvent log, reported per provider",
           target="trend upward; a persistently low rate says analysts do not trust the feature",
           cadence="monthly", provenance="platform-derived"),
    # ── no OSINT source exists for any of these ─────────────────────────────────────────────────
    Metric("staffing_ratio", "Vendors per TPRM FTE",
           owner="TPRM lead", formula="active vendors / TPRM full-time equivalents",
           source="MANUAL — headcount is not observable from this platform",
           target="benchmark against survey data", cadence="annual",
           provenance="manually-supplied"),
    Metric("cost_per_assessment", "Cost per assessment",
           owner="Finance partner", formula="programme cost / assessments completed",
           source="MANUAL — no cost data enters this platform",
           target="benchmark against survey data", cadence="annual",
           provenance="manually-supplied", lower_is_better=True),
    Metric("policy_exception_rate", "Policy exception rate",
           owner="Risk committee",
           formula="approved exceptions / decisions requiring one",
           source="MANUAL — exceptions are recorded in the GRC system, not here",
           target="declining trend", cadence="quarterly", provenance="manually-supplied",
           lower_is_better=True),
)

assert len(METRICS) <= 15, "the phase plan caps this dashboard at 15 metrics, and the cap is the point"

# E14's exit criteria required this dashboard to add `gap_analysis_acceptance_rate` — and required
# arguing one existing metric out, since the cap above is already at 15 ("that argument is part of
# this phase, not a footnote to it"). `stakeholder_satisfaction` is the one removed.
#
# WHY THAT ONE. Of the four manually-supplied metrics, three name a specific owner and a specific
# system of record that does not exist yet but plausibly will (finance's cost ledger, the GRC
# system's exception log, HR's headcount). `stakeholder_satisfaction` names neither — "a survey, run
# outside this platform" is the vaguest source on the whole dashboard, and it is also the one this
# programme is least likely to ever actually run: P9's own maturity assessment already found
# lifecycle coverage is the sole dimension at the floor, and a satisfaction survey was not the
# measurement priority that finding produced. Keeping four empty manually-supplied metrics with no
# near-term owner would have meant removing `gap_analysis_acceptance_rate` instead — a metric this
# module can compute FOR FREE from a log the feature already has to keep for its own audit trail —
# in favour of a fifth empty cell nobody was about to fill. That trade is the wrong one twice over:
# it drops a real number to protect a placeholder, and it leaves the one LLM-shaped feature on this
# platform with no accept/reject measurement, which is exactly the "data-quality defects surface by
# accident" pattern P9 marks Technology down for everywhere else.


@dataclass
class MetricValue:
    metric: Metric
    value: Any = None
    detail: dict[str, Any] = field(default_factory=dict)
    #: Why there is no value. Present ONLY when `value is None`, and never empty in that case —
    #: a null with no reason is indistinguishable from a zero somebody forgot to compute.
    unavailable_reason: str | None = None

    @property
    def supplied(self) -> bool:
        return self.value is not None


@dataclass(frozen=True)
class PeerFigure:
    """An external benchmark figure. Unpublishable without its provenance."""

    metric_key: str
    value: Any
    survey: str
    year: int
    n: int

    def caption(self) -> str:
        return f"{self.survey} {self.year}, n={self.n}"


class PeerFigureError(ValueError):
    """Raised when a peer figure is offered without a survey name, year, or n."""


def peer_figure(metric_key: str, value: Any, *, survey: str, year: int, n: int) -> PeerFigure:
    """Construct a peer figure, refusing any that cannot be captioned.

    THE REFUSAL IS THE FEATURE. A peer comparison whose population is unstated is a number
    pretending to be a benchmark — EB refuses the same thing for vendor cohorts, and a programme
    dashboard quoting "industry average: 42" with no survey behind it is the version of that
    mistake a board actually sees.
    """
    if not str(survey).strip():
        raise PeerFigureError("a peer figure needs the SURVEY it came from")
    if not isinstance(year, int) or year < 1990:
        raise PeerFigureError("a peer figure needs the YEAR it was published")
    if not isinstance(n, int) or n < 1:
        raise PeerFigureError("a peer figure needs the SAMPLE SIZE (n) behind it")
    return PeerFigure(metric_key=metric_key, value=value, survey=survey, year=year, n=n)


# ============================================================ computation


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    mid, odd = divmod(len(s), 2)
    return s[mid] if odd else (s[mid - 1] + s[mid]) / 2.0


def _tier_of(profile: Any, attrs: dict[str, Any]) -> str | None:
    return inherent_tier(
        profile.criticality if profile else None, attrs.get("data_access_scope"),
        provisional=getattr(profile, "inherent_provisional", False) if profile else False,
    ).tier


def compute(store: Any, *, spof_count: int | None = None,
            manual: dict[str, Any] | None = None) -> list[MetricValue]:
    """Every metric, computed from the store. One failing metric never takes the dashboard down.

    `spof_count` is passed in rather than recomputed: P1's concentration is a portfolio query the
    API already performs, and recomputing it here would make this module a second source of truth
    about the same number. `manual` carries whatever the programme has actually supplied for the
    four metrics that have no OSINT source.
    """
    manual = manual or {}
    now = utcnow()

    scores = list(store.latest_scores_all())
    total = len(scores)
    out: list[MetricValue] = []

    # THE WHOLE BOOK, IN FIVE QUERIES. Every metric below reads per-vendor state, and each used to
    # fetch it per vendor: profile, supplier attributes, evidence and findings, once each for 146
    # vendors — around seven hundred sequential round trips to Neon for one dashboard, which is
    # why this endpoint took seventy-five seconds. The metrics are unchanged; only where they
    # read from is. Anything absent stays absent — `.get` returns None exactly as the per-vendor
    # call returned None, so "undeclared" is still undeclared and never silently a default.
    profiles = store.latest_profiles_all()
    attrs_all = store.latest_supplier_attributes_all()
    findings_all = store.findings_all()
    first_evidence = store.first_evidence_at_all()

    def add(key: str, fn) -> None:  # noqa: ANN001
        metric = next(m for m in METRICS if m.key == key)
        if metric.provenance == "manually-supplied":
            value = manual.get(key)
            out.append(MetricValue(
                metric, value=value,
                unavailable_reason=None if value is not None else (
                    f"NOT SUPPLIED. This metric has no OSINT source — {metric.source}. It is left "
                    f"empty rather than estimated; {metric.owner} owns supplying it."),
            ))
            return
        try:
            value, detail = fn()
            # A metric may supply its own reason for being empty. The generic fallback — "no
            # scored vendors yet" — is the WRONG sentence for most of the ways a metric can have no
            # population, and a wrong reason in an empty cell is the same failure as a plausible
            # number in one: the reader stops asking.
            reason = detail.pop("unavailable_reason", None) if isinstance(detail, dict) else None
            out.append(MetricValue(
                metric, value=value, detail=detail,
                unavailable_reason=None if value is not None else (
                    reason or "No scored vendors yet, so this metric has no population.")))
        except Exception as exc:  # noqa: BLE001 — one metric never takes the dashboard down
            log.warning("KPI %s failed: %r", key, exc)
            out.append(MetricValue(metric, value=None,
                                   unavailable_reason=f"computation failed: {type(exc).__name__}"))

    tiers = {}
    for s in scores:
        try:
            tiers[s.vendor_ref] = _tier_of(profiles.get(s.vendor_ref),
                                           attrs_all.get(s.vendor_ref) or {})
        except Exception:  # noqa: BLE001
            tiers[s.vendor_ref] = None

    def _currency():
        crit = [s for s in scores if tiers.get(s.vendor_ref) == "critical"]
        if not crit:
            return None, {"critical_tier_vendors": 0,
                          "note": "No vendor is declared critical-tier, so there is nothing to "
                                  "measure. That is a declaration gap, not a clean result — see "
                                  "inherent_tier_declaration_rate."}
        current = 0
        for s in crit:
            age = (now - s.computed_at).total_seconds() / 86400.0
            due, _ = is_due(plan_for("critical"), age)
            if not due:
                current += 1
        return round(100.0 * current / len(crit), 1), {
            "current": current, "critical_tier_vendors": len(crit)}

    def _declaration_rate():
        """Declared relationships over RELATIONSHIPS, not over every scored row.

        THE DENOMINATOR USED TO BE WRONG, AND IT MATTERED MORE THAN THE NUMERATOR. This metric
        first reported 0.0% of 146 vendors — but 146 scored rows are not 146 relationships. The
        book holds a seeded benchmarking corpus (no commercial relationship, therefore no exposure
        to declare) and a handful of inventory defects (typos, products, the buyer's own domains).
        Counting those as undeclared makes the programme look negligent about a question that does
        not apply to them, and — worse — it buries the relationships that genuinely are undeclared
        in a number too large to act on.

        `app/inherent_register.py` is the inventory of record that makes the split possible, and
        `unregistered` is reported because a vendor nobody has classified at all is the one bucket
        that must never sit quietly at a non-zero value.

        CONFIRMED AND PROVISIONAL ARE COUNTED SEPARATELY. A provisional declaration is real — it
        routes P5 and publishes an E10b tier — but reporting the two as one green number is exactly
        how an unconfirmed answer gets read as a confirmed one.
        """
        cov = register_coverage(store)
        if not cov["relationships"]:
            # NOT THE SAME AS 0%, and the difference matters. 0% says "we have suppliers and nobody
            # has classified them"; this says "the inventory of record does not cover this book at
            # all" — which is a gap in the register, not in anybody's declaration habits. Reporting
            # it as 0% would send somebody to chase relationship owners who have nothing to answer.
            unreg = len(cov["unregistered"])
            return None, {
                **cov,
                "unavailable_reason": (
                    f"NO POPULATION TO MEASURE. None of the {cov['in_book']} scored vendors is "
                    f"classified as a relationship on `app/inherent_register.py`"
                    + (f", and {unreg} are not on the register at all. Extend the register: an "
                       f"unregistered vendor is neither declared nor excused."
                       if unreg else ". The book is entirely seeded corpus and inventory defects.")
                ),
            }
        return round(100.0 * cov["declared"] / cov["relationships"], 1), {
            **cov,
            "why_it_matters": "Residual risk, P3's decision tag and P5's cadence all degrade to "
                              "'not declared' without this. It is the single input the most "
                              "downstream features depend on.",
            "read_this_first": (
                f"{cov['declared']} of {cov['relationships']} relationships declared, and "
                f"{cov['provisional']} of those are PROVISIONAL — declared on the register, not "
                f"yet confirmed by the accountable relationship owner. The confirmed rate is "
                f"{(cov['confirmed_rate'] or 0):.0%}."),
            "excluded_from_denominator": {
                "corpus": cov["corpus"],
                "not_a_relationship": cov["not_a_relationship"],
            },
        }

    def _substitutability_rate():
        """Same corrected denominator as the tier rate — substitutability is equally a property of
        a RELATIONSHIP, and a seeded corpus vendor has none to declare."""
        cov = register_coverage(store)
        n_rel = cov["relationships"]
        if not n_rel:
            return None, {**cov}
        refs = {s.vendor_ref for s in scores}
        n = 0
        for e in register_relationships():
            if e.ref not in refs:
                continue
            p = profiles.get(e.ref)
            if p is not None and getattr(p, "substitutability", None):
                n += 1
        return round(100.0 * n / n_rel, 1), {"declared": n, "relationships": n_rel,
                                             "vendors_in_book": total}

    def _published_rate():
        if not total:
            return None, {}
        pub = sum(1 for s in scores if not s.blocked and not s.refused)
        return round(100.0 * pub / total, 1), {"published": pub, "vendors": total}

    def _ghost_rate():
        if not total:
            return None, {}
        n = sum(1 for s in scores if s.refused)
        return round(100.0 * n / total, 1), {"refused": n, "vendors": total}

    def _blocked():
        blocked = [s for s in scores if s.blocked]
        return len(blocked), {
            "refs": sorted(s.vendor_ref for s in blocked)[:25],
            "why_it_matters": "A blocking queue is only as safe as the speed at which a human can "
                              "clear a false positive from it. Depth here is what turns "
                              "adjudication into a rubber stamp.",
        }

    def _cycle_time():
        durations = []
        for s in scores:
            first = first_evidence.get(s.vendor_ref)
            if first is not None:
                durations.append((s.computed_at - first).total_seconds())
        med = _median([d for d in durations if d >= 0])
        return (round(med, 1) if med is not None else None), {
            "vendors_measured": len(durations),
            "note": "The AUTOMATED leg only — evidence collection to published score. Survey "
                    "figures of 30-45 days measure a full human cycle and are not comparable.",
        }

    def _overdue():
        from .scoring_config import get_scoring_config
        cfg = get_scoring_config()
        days = {"7d": 7, "14d": 14, "30d": 30, "90d": 90}
        overdue = 0
        for s in scores:
            age = (now - s.computed_at).total_seconds() / 86400.0
            for row in findings_all.get(s.vendor_ref) or []:
                if row.effective_penalty <= 0:
                    continue
                after = (cfg.action_for(row.signal, row.band_key) or {}).get("recheck_after")
                if after in days and age >= days[after]:
                    overdue += 1
        return overdue, {"note": "recheck_after is stated per finding and, until this metric, was "
                                 "enforced nowhere in aggregate."}

    def _residual():
        """Over RELATIONSHIPS ONLY, for the same reason the declaration rate is.

        This metric read `{not_published: 146}` on its first live run, and the honest reading was
        never "146 vendors have no residual tier" — it was "the 114 seeded corpus vendors have no
        relationship, and therefore no residual risk to publish, and they were drowning out the
        two dozen rows that do." A distribution over a population that includes rows which can
        never have a value is not a distribution, it is a census of the wrong thing.
        """
        rel = [s for s in scores if register_classify(s.vendor_ref) == "relationship"]
        dist: dict[str, int] = {}
        provisional = 0
        for s in rel:
            profile = profiles.get(s.vendor_ref)
            attrs = attrs_all.get(s.vendor_ref) or {}
            is_prov = getattr(profile, "inherent_provisional", False) if profile else False
            r = residual_risk(
                s.posture, profile.criticality if profile else None,
                attrs.get("data_access_scope"), blocked=s.blocked, refused=s.refused,
                substitutability=getattr(profile, "substitutability", None) if profile else None,
                provisional=is_prov)
            key = r.residual if r.published else "not_published"
            dist[key] = dist.get(key, 0) + 1
            if r.published and is_prov:
                provisional += 1
        return dist, {
            "relationships": len(rel), "vendors_in_book": total,
            "resting_on_a_provisional_declaration": provisional,
            "note": "Recomputed on read from the E10b lookup, stored nowhere. Counted over "
                    "relationships only — a seeded corpus vendor has no relationship and so has "
                    "no residual tier to publish.",
        }

    def _spof():
        if spof_count is None:
            return None, {}
        return spof_count, {}

    def _monitoring():
        """Vendors inside their P5 interval — AND, beside it, whether anything is actually sweeping.

        THIS METRIC CAN READ 100% ON A DEAD SCHEDULE, and that is why the health of the schedule
        travels in the same row. If the monitor stops running, currency does not fall off a cliff;
        it decays slowly and plausibly, which is indistinguishable from a book that happens to be
        current. `app/scheduler.py` reads the append-only run ledger instead, where silence is the
        alarm condition — the only signal that separates "nothing needed re-scoring" from "nothing
        has run since March".
        """
        if not total:
            return None, {}
        current = 0
        for s in scores:
            plan = plan_for(tiers.get(s.vendor_ref))  # type: ignore[arg-type]
            age = (now - s.computed_at).total_seconds() / 86400.0
            due, _ = is_due(plan, age)
            if not due:
                current += 1

        try:
            health = monitoring_health(store)
        except Exception as exc:  # noqa: BLE001 — an unledgered store must not take the row down
            health = {"healthy": False, "reason": f"run ledger unavailable: {type(exc).__name__}"}

        return round(100.0 * current / total, 1), {
            "current": current, "vendors": total,
            "schedule_healthy": health.get("healthy"),
            "schedule_status": health.get("reason"),
            "last_run_at": health.get("last_run_at"),
            "read_this_first": (
                "This percentage is about the BOOK. `schedule_healthy` is about the SCHEDULE, and "
                "a high currency figure with an unhealthy schedule is the most misleading pair on "
                "this dashboard: it means nothing has been re-scored into staleness because "
                "nothing has been re-scored."),
        }

    def _acceptance_rate():
        """E14. Of every DISPOSITIONED recommendation (latest event per (analysis_id, rec_index)),
        how many were accepted or edited rather than rejected. Pending recommendations — generated,
        not yet actioned — are excluded from both sides: they are not a "no" yet, and counting them
        as one would understate a feature an analyst simply has not gotten to.
        """
        try:
            events = store.gap_analysis_events_all()
        except Exception as exc:  # noqa: BLE001 — one metric never takes the dashboard down
            return None, {"unavailable_reason": f"event log unavailable: {type(exc).__name__}"}
        if not events:
            return None, {
                "unavailable_reason": "No recommendation has been dispositioned yet — nobody has "
                                      "generated a gap analysis, or nobody has accepted, edited or "
                                      "rejected one of its recommendations."}

        latest: dict[tuple[str, int], Any] = {}
        for e in events:   # oldest-first, so the last write wins — same rule accepted_dispute_targets uses
            latest[(e.analysis_id, e.rec_index)] = e

        analyses = store.gap_analyses_all()
        accepted_or_edited = 0
        rejected = 0
        by_provider: dict[str, dict[str, int]] = {}
        for (analysis_id, _idx), ev in latest.items():
            provider = (analyses.get(analysis_id).provider if analyses.get(analysis_id) else "unknown")
            bucket = by_provider.setdefault(provider, {"accepted_or_edited": 0, "rejected": 0})
            if ev.event in ("accepted", "edited"):
                accepted_or_edited += 1
                bucket["accepted_or_edited"] += 1
            else:
                rejected += 1
                bucket["rejected"] += 1

        dispositioned = accepted_or_edited + rejected
        if not dispositioned:
            return None, {"unavailable_reason": "Every logged event is malformed or unrecognised — "
                                                "nothing to compute a rate from."}
        per_provider = {
            p: round(100.0 * b["accepted_or_edited"] / (b["accepted_or_edited"] + b["rejected"]), 1)
            for p, b in by_provider.items() if (b["accepted_or_edited"] + b["rejected"])
        }
        return round(100.0 * accepted_or_edited / dispositioned, 1), {
            "dispositioned": dispositioned, "accepted_or_edited": accepted_or_edited,
            "rejected": rejected, "by_provider": per_provider,
            "note": "Pending recommendations (generated, not yet actioned) are excluded from both "
                    "the numerator and the denominator.",
        }

    for key, fn in (
        ("tier1_assessment_currency", _currency),
        ("inherent_tier_declaration_rate", _declaration_rate),
        ("substitutability_declaration_rate", _substitutability_rate),
        ("published_posture_rate", _published_rate),
        ("ghost_rate", _ghost_rate),
        ("blocked_pending_adjudication", _blocked),
        ("assessment_cycle_time_median", _cycle_time),
        ("overdue_rechecks", _overdue),
        ("residual_risk_distribution", _residual),
        ("fourth_party_spof_count", _spof),
        ("monitoring_currency", _monitoring),
        ("gap_analysis_acceptance_rate", _acceptance_rate),
        ("staffing_ratio", None),
        ("cost_per_assessment", None),
        ("policy_exception_rate", None),
    ):
        add(key, fn)
    return out


def as_dict(values: list[MetricValue],
            peers: list[PeerFigure] | None = None) -> dict[str, Any]:
    peers = peers or []
    by_metric: dict[str, list[PeerFigure]] = {}
    for p in peers:
        by_metric.setdefault(p.metric_key, []).append(p)

    return {
        "metric_count": len(values),
        "platform_derived": sum(1 for v in values
                                if v.metric.provenance == "platform-derived"),
        "manually_supplied": sum(1 for v in values
                                 if v.metric.provenance == "manually-supplied"),
        # TWO KINDS OF MISSING, KEPT APART — the same rule P2 applies to coverage buckets. "Nobody
        # supplied it" is a programme gap somebody owns; "there is no population to measure" is a
        # fact about the book. Collapsing them into one "missing" list would let an unmeasurable
        # metric read as an unassigned chore, and an unassigned chore as a data problem.
        "unsupplied": [v.metric.key for v in values
                       if not v.supplied and v.metric.provenance == "manually-supplied"],
        "not_computable": [v.metric.key for v in values
                           if not v.supplied and v.metric.provenance == "platform-derived"],
        "metrics": [
            {
                "key": v.metric.key,
                "name": v.metric.name,
                "value": v.value,
                "provenance": v.metric.provenance,
                "owner": v.metric.owner,
                "formula": v.metric.formula,
                "source": v.metric.source,
                "target": v.metric.target,
                "cadence": v.metric.cadence,
                "lower_is_better": v.metric.lower_is_better,
                "detail": v.detail or None,
                "unavailable_reason": v.unavailable_reason,
                "peer_comparison": [
                    {"value": p.value, "survey": p.survey, "year": p.year, "n": p.n,
                     "caption": p.caption()}
                    for p in by_metric.get(v.metric.key, [])
                ] or None,
            }
            for v in values
        ],
        "caveats": [
            "TWO KINDS OF NUMBER, NEVER PRINTED AS ONE. `platform-derived` metrics are computed "
            "from the store on every read. `manually-supplied` metrics have NO OSINT SOURCE and "
            "are empty until somebody supplies them — never backfilled, estimated, or defaulted to "
            "make the dashboard look complete.",
            "An empty cell asks a question; a plausible number answers it wrongly. Every "
            "unsupplied metric names its owner instead of showing a figure.",
            "No peer figure is published without its survey, year and sample size. A comparison "
            "whose population is unstated is a number pretending to be a benchmark.",
            "No metric here reaches a vendor score. Every one READS the store; none writes, and no "
            "KPI value is an input to Posture, Confidence, Assurity or any vendor-level number.",
            "Cycle time measures the AUTOMATED leg — evidence collection to published score. "
            "Industry survey figures of 30-45 days measure a full human assessment cycle and are "
            "not comparable to it.",
        ],
    }
