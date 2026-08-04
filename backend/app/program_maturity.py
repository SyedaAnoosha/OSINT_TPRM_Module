"""P9 — how good is OUR TPRM PROGRAM, not how good is this vendor.

THE SUBJECT IS DIFFERENT FROM EVERY OTHER PHASE, and that is the whole reason this must not be
merged into EB. EB asks *"is this vendor's posture normal for its peer group of vendors."* P9 asks
*"is our programme — governance, coverage, cycle time, automation — normal for a peer group of TPRM
programmes."* Different subject, different peer group, different output. Conflating them produces a
metric nobody can explain.

(Not to be confused with `app/maturity.py`, which is a VENDOR's operating history — years on the
record. Same English word, unrelated question. The module is named `program_maturity` for exactly
that reason.)

═══ A SELF-ASSESSMENT, NOT A COMPUTED SCORE ═══

The phase plan is explicit: *"do not build a formula that produces a fake precision."* So there is no
arithmetic here. Eight dimensions, each with a level, a written rationale, and — the part that makes
it more than an opinion — **the specific thing in this codebase that justifies it** and **what would
have to become true to reach the next level**.

Levels: `Informal(1) → Reactive(2) → Defined(3) → Managed(4) → Optimized(5)`.

═══ THE OVERALL LEVEL IS THE MINIMUM, NEVER THE AVERAGE ═══

A programme is not "Managed overall" because three dimensions are and five are not. An average lets
strength in the easy dimensions — we are good at assessment methodology, it is what this codebase
is — conceal the dimension that will actually fail an audit. The minimum is the honest summary and
it is the one the plan asks for. The same non-compensatory rule as the critical ceiling, the
inherent tier, and continuity's worst-standing headline.

The current answer is **Level 2 (Reactive)**, held down by three dimensions, and that is the useful
output: it names what to fix rather than flattering what is already good.

═══ THE STALENESS PROBLEM, AND THE MECHANISM AGAINST IT ═══

A hardcoded self-assessment is wrong the moment somebody builds the thing it says is missing — and
wrong in the FLATTERING direction is not the risk here; wrong in the *understating* direction is,
because a programme that fixed something and still reports Reactive stops being believed, and then
nobody reads any of it.

So every dimension's evidence is written as a CHECKABLE CLAIM about the tree — a module that must
exist, a module that must NOT exist, a route, a config value. `tests/test_program_maturity.py`
walks them, and a claim that has gone stale fails the suite. Building `app/offboarding.py` breaks
the test that says lifecycle coverage is Reactive *because* there is no offboarding, which is
exactly when a human should be re-scoring that dimension.

That is the same discipline `_validate_no_dead_config` applies to `scoring.yaml`: the assessment is
a claim, and a claim nothing checks is a claim that drifts.

═══ NOTHING HERE TOUCHES A VENDOR SCORE ═══

No maturity level and no KPI may reach Posture, Confidence, Assurity, or any vendor-level number.
A programme that scores its own maturity and then lets that maturity adjust its vendors' scores has
built a mirror. Asserted by test, the same discipline as
`test_benchmarking_never_alters_input_scores`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Level = Literal[1, 2, 3, 4, 5]

LEVEL_NAMES: dict[int, str] = {
    1: "Informal", 2: "Reactive", 3: "Defined", 4: "Managed", 5: "Optimized",
}

#: The kinds of claim a dimension may cite. Each is mechanically checkable against the tree, which
#: is what stops this file from becoming a wish list.
ClaimKind = Literal["module_present", "module_absent", "route_present", "route_absent"]


@dataclass(frozen=True)
class Claim:
    """One checkable fact about the codebase that a level rests on."""

    kind: ClaimKind
    target: str
    why: str

    def describe(self) -> str:
        verb = {"module_present": "exists", "module_absent": "does NOT exist",
                "route_present": "is served", "route_absent": "is NOT served"}[self.kind]
        return f"`{self.target}` {verb} — {self.why}"


@dataclass(frozen=True)
class Dimension:
    key: str
    name: str
    level: Level
    rationale: str
    claims: tuple[Claim, ...]
    to_reach_next: str

    @property
    def level_name(self) -> str:
        return LEVEL_NAMES[self.level]


#: ═══ THE ASSESSMENT ═══
#: Scored against what this codebase DOES, on 2026-07-31, not against what it is meant to do. Where
#: a dimension is unflattering it is unflattering on purpose: the value of this artefact is entirely
#: in the dimensions that score low.
_DIMENSIONS: tuple[Dimension, ...] = (
    Dimension(
        key="governance_policy",
        name="Governance & policy",
        level=3,
        rationale=(
            "The scoring model is the deliverable and it is published, versioned and validated at "
            "load: `scoring.yaml` carries its own version and supersedes chain, the loader REFUSES "
            "TO START on config nothing reads or on a penalising band with no reason, action and "
            "re-check date, and material changes ship with a written change notice. Methodology "
            "decisions are recorded with their arguments rather than as settings. What is missing "
            "for Managed is ownership and cadence: no named owner is recorded in the repository "
            "and no review cycle for the model itself is scheduled or evidenced."
        ),
        claims=(
            Claim("module_present", "app/scoring_config.py",
                  "the loader that refuses invalid config is where policy is actually enforced"),
            Claim("module_present", "app/disclosures.py",
                  "source attributions and legal notices travel with every published pack"),
        ),
        to_reach_next=(
            "A named owner per model area and a scheduled model review with recorded outcomes. "
            "Governance that exists only as validation is Defined; Managed needs someone "
            "accountable and a date."
        ),
    ),
    Dimension(
        key="inventory_tiering",
        name="Inventory completeness & risk tiering",
        level=3,
        rationale=(
            "RE-SCORED FROM 2 ON 2026-08-01. An inventory of record now exists: "
            "`app/inherent_register.py` classifies every row in the book as a relationship, a "
            "seeded benchmarking corpus vendor, or an inventory defect, refuses at import to "
            "carry a declaration without a written basis and an author, and refuses to let a "
            "non-relationship carry one at all. That last refusal is what makes the declaration "
            "rate mean something. The rate itself went 0% to 100% of relationships — and the "
            "bigger correction was the DENOMINATOR: 146 scored rows were never 146 relationships, "
            "and the old figure buried two dozen real suppliers among a corpus that has no "
            "exposure to declare. Managed is not claimed for two reasons, both structural: every "
            "declaration is PROVISIONAL with none confirmed by an accountable owner, and there is "
            "still no reconciliation against a procurement, AP or contract system — so the "
            "platform can enumerate what it has seen and still cannot know what it has not."
        ),
        claims=(
            Claim("module_present", "app/residual_risk.py",
                  "the inherent tier and its non-compensatory maximum are built"),
            Claim("module_present", "app/assessment_depth.py",
                  "the tier reaches collection depth and review cadence (P5)"),
            Claim("module_present", "app/inherent_register.py",
                  "the inventory of record, with a declaration path that does not cost a re-scan"),
            Claim("route_present", "/api/program/inventory",
                  "the three populations and the corrected denominator are served, not just "
                  "computed"),
            Claim("module_absent", "app/procurement_reconciliation.py",
                  "nothing reconciles the register against a system outside this platform, so "
                  "completeness remains unmeasurable"),
        ),
        to_reach_next=(
            "Two things, and neither is code we can write alone: relationship owners CONFIRMING "
            "their provisional declarations, and a reconciliation against procurement or AP so "
            "'completeness' stops meaning 'everything somebody happened to score'. The register "
            "reports both gaps by name — `confirmed_rate` and `unregistered` — which is what "
            "makes them chaseable rather than assumed."
        ),
    ),
    Dimension(
        key="assessment_methodology",
        name="Assessment methodology & depth",
        level=4,
        rationale=(
            "The strongest dimension, and it is what this codebase is. A penalty-subtractive model "
            "with a calibrated severity ladder, a separate confidence axis that can REFUSE to "
            "publish, non-compensatory ceilings, hard gates, root-cause de-duplication, and a "
            "frozen regression corpus that moves only through `python -m tests.regolden` with the "
            "diff read as the change. Depth is now matched to exposure rather than uniform (P5). "
            "Optimized is not claimed: the model has never been calibrated against REALISED "
            "OUTCOMES — E0.4's outcome labels are deferred in writing — so severity remains expert "
            "judgement, correctly labelled as such."
        ),
        claims=(
            Claim("module_present", "app/scoring/engine.py", "the scoring path itself"),
            Claim("module_present", "app/scoring/log_odds.py",
                  "a bounded alternative built, published side by side, and refusing until its "
                  "preconditions hold"),
            Claim("module_absent", "app/outcomes.py",
                  "no outcome-label corpus exists, so severity is uncalibrated against incidents"),
        ),
        to_reach_next=(
            "Outcome labels (E0.4) and a discrimination analysis re-run against them. Until a "
            "severity ladder is tested against what actually went wrong, Optimized would be a "
            "claim about our confidence rather than about the model."
        ),
    ),
    Dimension(
        key="continuous_monitoring",
        name="Continuous monitoring & threat intel",
        level=3,
        rationale=(
            "RE-SCORED FROM 2 ON 2026-08-01, and the re-score was forced by this file's own test "
            "rather than volunteered: the assessment cited the ABSENCE of `app/scheduler.py`, that "
            "module now exists, and the suite failed until a person revisited the level. "
            "`app/monitor.py` is still the unit of work and still not a daemon; the schedule lives "
            "in `ops/schedule/` as a cron entry, a systemd timer and a Windows Scheduled Task, "
            "because which host runs the sweep and who is paged when it stops are operational "
            "decisions that should not be buried in Python. What lifts this to Defined is not the "
            "timer but the LEDGER: `monitor_runs` is append-only, records started/finished as "
            "separate events so a run that dies leaves a visible orphan, and `--health` treats "
            "SILENCE as the alarm condition — which is the only way to tell a monitored book from "
            "one whose currency figure is high because nothing has been re-scored at all. Managed "
            "is not claimed: one run has been recorded, by hand, and no host yet has the timer "
            "installed. Threat intel is also still point-in-time at scan (KEV, NVD, OTX) with no "
            "continuous feed and no watch list, which alone would cap this below Managed."
        ),
        claims=(
            Claim("module_present", "app/monitor.py",
                  "the re-score unit of work, with per-tier cadence"),
            Claim("module_present", "app/scheduler.py",
                  "the scheduled entrypoint and the run ledger that makes 'we monitor "
                  "continuously' a checkable claim rather than an assertion"),
            Claim("route_present", "/api/program/monitoring",
                  "schedule health and retained drift reports are served, not just logged"),
            Claim("module_absent", "app/threat_feed.py",
                  "threat intel is point-in-time at scan; there is no continuous feed or watch "
                  "list, which is the remaining half of this dimension"),
        ),
        to_reach_next=(
            "A run history that somebody did not have to start — the timer installed on a real "
            "host, several weeks of ledger, and a recorded instance of drift being acted on. Plus "
            "the other half of the dimension: a continuous threat feed and a watch list, so a KEV "
            "entry published on a Tuesday does not wait for a vendor's next scheduled sweep."
        ),
    ),
    Dimension(
        key="remediation_issues",
        name="Remediation & issue management",
        level=3,
        rationale=(
            "The loop is closed and defined end to end: every penalising band carries an "
            "`ask_of_vendor`, an `accepts_as_refute` and a `recheck_after` — the loader will not "
            "start otherwise — P3 assembles them into a pack scoped to what actually failed, and "
            "the dispute path adjudicates to `nullify` or `mitigate`, records the reason, and "
            "re-scores. P4 turns what a response cannot close into a drafting point. What is "
            "absent for Managed is measurement: nothing tracks whether a `recheck_after` date was "
            "honoured, so the SLA is stated per finding and unenforced in aggregate."
        ),
        claims=(
            Claim("module_present", "app/evidence_pack.py", "the request pack (P3)"),
            Claim("module_present", "app/contract_flowdowns.py",
                  "what a response cannot close becomes a contract term (P4)"),
            Claim("route_present", "/api/disputes/{dispute_id}/adjudicate",
                  "the only route by which a vendor response may move a number"),
        ),
        to_reach_next=(
            "Track re-check dates to closure and report the breach rate. The KPI dashboard now "
            "publishes overdue re-checks, which is the measurement this dimension was missing; "
            "acting on it is what makes it Managed."
        ),
    ),
    Dimension(
        key="lifecycle_coverage",
        name="Lifecycle coverage (incl. offboarding, fourth parties)",
        level=2,
        rationale=(
            "Onboarding and ongoing assessment are covered, and fourth parties are genuinely "
            "covered — P1 enumerates providers from public traces and publishes book-wide "
            "concentration ranked by critical share, which is the part most programmes lack. "
            "OFFBOARDING IS NOT COVERED. P8 answers *what happens if they have to go* — exit "
            "readiness, substitutability, escalation, exit-clause flow-downs — but there is no "
            "offboarding workflow, no collector, and nothing that observes whether access was "
            "actually revoked or data actually returned. The phase plan names this exact gap, and "
            "it is the one that keeps the dimension at Reactive."
        ),
        claims=(
            Claim("module_present", "app/concentration.py", "fourth-party concentration (P1)"),
            Claim("module_present", "app/exit_readiness.py",
                  "exit readiness and substitutability (P8) — planning, not execution"),
            Claim("module_absent", "app/offboarding.py",
                  "no offboarding workflow or collector exists; the plan names this gap"),
        ),
        to_reach_next=(
            "An offboarding record: termination date, access-revocation confirmation, data-return "
            "attestation, and a final screening run. None of it is observable from outside, so it "
            "is an inside-out workflow this platform would record rather than collect."
        ),
    ),
    Dimension(
        key="technology_data_quality",
        name="Technology / automation & data quality",
        level=3,
        rationale=(
            "Automation is Managed-grade: nineteen collectors behind one failure-isolated pipeline, "
            "evidence written BEFORE scoring and hash-stamped, append-only history, entity "
            "resolution with a confidence gate, and a suite that refuses to start on invalid "
            "config. DATA QUALITY IS NOT, and there is a measured reason rather than a suspicion. "
            "The sanctions matcher blocked 10 of 114 household-name companies — an 8.8% "
            "false-positive rate that had gone unmeasured for months because nothing tested matcher "
            "PRECISION against the real list. It was found by a seeding run, not by an instrument, "
            "and it is now fixed and pinned. A programme whose data-quality defects are found by "
            "accident is Defined, not Managed. Two instruments have since been added — "
            "`app/adjudication_queue.py` puts the discriminating facts on every blocked row so a "
            "decision takes seconds rather than research, and `app/estate_readiness.py` measures "
            "whether E12's fan-out can be switched on instead of asserting it — but neither is "
            "standing PRECISION measurement on the matching paths, which is what Managed requires."
        ),
        claims=(
            Claim("module_present", "app/pipeline.py", "one path, failure-isolated"),
            Claim("module_present", "app/entity_resolution.py",
                  "resolution confidence is measured rather than assumed"),
            Claim("module_present", "app/collectors/ita_collector.py",
                  "the matcher whose precision was unmeasured until a 114-vendor run forced it"),
            Claim("module_present", "app/estate_readiness.py",
                  "E12's switch-on is now a measurement with a written threshold, not a guess"),
            Claim("module_absent", "app/matcher_precision.py",
                  "no standing precision/recall instrumentation exists on the matching paths; "
                  "the 8.8% sanctions rate was found by a seeding run, not by an instrument"),
        ),
        to_reach_next=(
            "Standing precision and recall instrumentation on the matching paths — sanctions, "
            "entity resolution, KEV product-line matching — measured on a schedule rather than "
            "when a seeding run happens to reveal a rate. The adjudication queue makes each "
            "decision cheap; it does not yet count how often the matcher was wrong."
        ),
    ),
    Dimension(
        key="reporting_engagement",
        name="Reporting & stakeholder engagement",
        level=4,
        rationale=(
            "Two audiences are served from one immutable score object with an invariant asserting "
            "they cannot quote different numbers (P6), the procurement rendering leads with the "
            "decision and ends with the ask, and a limitation may not appear on only one view — so "
            "the person who signs cannot miss what the assessment could not see. The evidence pack "
            "reconstructs the published score from its own contents, which is what makes it a pack "
            "rather than a summary. Optimized would need evidence of USE: a governance forum that "
            "consumes these and records decisions against them."
        ),
        claims=(
            Claim("module_present", "app/audience_views.py", "the two renderings (P6)"),
            Claim("module_present", "app/coverage_statement.py",
                  "the limitation that travels with the number (P2)"),
            Claim("route_present", "/api/vendors/{ref}/export",
                  "the reconstructible record procurement files"),
        ),
        to_reach_next=(
            "Evidence that the reports drive decisions: a recorded governance forum, decisions "
            "logged against the packs that informed them. The decision endpoint exists; nothing "
            "yet shows it being used."
        ),
    ),
)

#: Bumped whenever a level or rationale changes, so a maturity figure quoted in a board pack can be
#: traced to the assessment that produced it. The date is the assessment date, not a build date.
ASSESSMENT_VERSION = "1.1.0"
ASSESSED_ON = "2026-08-01"

#: What changed and why, so a figure quoted from v1.0.0 can be reconciled with one quoted from here.
#: THE FIRST TWO RE-SCORES WERE FORCED BY THE TEST SUITE, NOT VOLUNTEERED — which is the mechanism
#: working: `app/scheduler.py` and `app/inherent_register.py` were built, the claims citing their
#: absence failed, and a person had to come back and re-argue the levels.
ASSESSMENT_CHANGELOG = (
    ("1.1.0", "2026-08-01",
     "inventory_tiering 2 -> 3 (an inventory of record exists and the declaration rate is tracked "
     "against a corrected denominator); continuous_monitoring 2 -> 3 (a scheduled entrypoint, "
     "deployment artefacts outside the repo, and an append-only run ledger where silence is the "
     "alarm). OVERALL STAYS LEVEL 2 — lifecycle coverage is now the only dimension at the floor, "
     "which is a more useful sentence than the one three dimensions produced."),
    ("1.0.0", "2026-07-31", "Initial assessment. Level 2, held there by three dimensions."),
)

_CAVEATS = [
    "A SELF-ASSESSMENT WITH A WRITTEN RATIONALE, not a computed score. There is no formula here on "
    "purpose: a maturity level derived by arithmetic would carry a precision the underlying "
    "judgements do not have, and the phase plan rules it out explicitly.",
    "THE OVERALL LEVEL IS THE MINIMUM ACROSS DIMENSIONS, never the average. A programme is not "
    "'Managed overall' because three dimensions are and five are not — an average lets strength "
    "where we are naturally strong conceal the dimension that will fail an audit.",
    "Every level cites a checkable fact about the codebase, and the test suite walks those claims. "
    "A claim that has gone stale — a module built, a route added — fails the suite, which is the "
    "signal to re-assess that dimension rather than let the number drift.",
    "Nothing here reaches a vendor score. No maturity level and no KPI may touch Posture, "
    "Confidence, Assurity, or any vendor-level number; a programme that let its own self-assessment "
    "adjust its vendors' scores would have built a mirror.",
]


def dimensions() -> tuple[Dimension, ...]:
    return _DIMENSIONS


def overall_level() -> int:
    """THE MINIMUM, and the docstring is here so nobody 'improves' it into an average."""
    return min(d.level for d in _DIMENSIONS)


def limiting_dimensions() -> list[Dimension]:
    """The dimensions holding the overall level down — the only ones worth acting on first."""
    floor = overall_level()
    return [d for d in _DIMENSIONS if d.level == floor]


def headline() -> str:
    floor = overall_level()
    limiters = limiting_dimensions()
    best = max(d.level for d in _DIMENSIONS)
    names = ", ".join(d.name for d in limiters)
    return (
        f"Level {floor}/5 ({LEVEL_NAMES[floor]}) overall — the MINIMUM across eight dimensions, "
        f"not an average. Held there by: {names}. "
        f"Strongest dimension reaches Level {best} ({LEVEL_NAMES[best]}), which is why an average "
        f"would read a full band higher and mean nothing."
    )


def as_dict() -> dict[str, object]:
    return {
        "assessment_version": ASSESSMENT_VERSION,
        "assessed_on": ASSESSED_ON,
        "changelog": [{"version": v, "date": d, "change": c}
                      for v, d, c in ASSESSMENT_CHANGELOG],
        "scale": {str(k): v for k, v in LEVEL_NAMES.items()},
        "overall_level": overall_level(),
        "overall_level_name": LEVEL_NAMES[overall_level()],
        "overall_rule": "minimum across dimensions, never the average",
        "headline": headline(),
        "limiting_dimensions": [d.key for d in limiting_dimensions()],
        "dimensions": [
            {
                "key": d.key,
                "name": d.name,
                "level": d.level,
                "level_name": d.level_name,
                "rationale": d.rationale,
                "evidence": [c.describe() for c in d.claims],
                "to_reach_next": d.to_reach_next,
            }
            for d in _DIMENSIONS
        ],
        "caveats": _CAVEATS,
    }
