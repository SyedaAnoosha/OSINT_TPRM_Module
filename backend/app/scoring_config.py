"""Loader + validator for scoring.yaml — the penalty-based posture model (the deliverable).

The model is the product, and it lives in config so it can be argued with a client in a room
without a deploy (methodology §5). This module loads that file and checks the invariants the
methodology insists on, so a malformed edit fails loudly here rather than scoring quietly wrong:

  * direction convention present (100 = strongest posture … 0 = weakest);
  * the four severity penalties are defined;
  * the grade table is present;
  * sanctions is a GATE that BLOCKS, never a grade (Finding B).

It does NOT re-implement the scoring maths (that is the engine). It guarantees the config it
hands over is structurally sound.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .config import get_settings
from .logging_config import get_logger

log = get_logger("scoring.config")

_SEVERITIES = ("critical", "high", "medium", "low", "informational")

# --- the drift guard -------------------------------------------------------------------------
# Config that nothing reads is how this model drifted from its own documentation three separate
# times: two NIST variables sat inert behind hardcoded identity values, a KEV band no collector
# ever emitted, and an NVD band named `remediated` that only meant "below HIGH". Each read as a
# live rule in the docs and in the UI. None of them scored anything.
#
# So every top-level key must be declared here as one or the other. A key that is neither fails
# loudly at load, which makes "the engine uses this" a conscious decision rather than a hope.
_ENGINE_READS = {
    "version",             # ScoringConfig.version
    "direction",           # _validate — the 100=strongest convention
    "max_score",           # engine: category posture + overall
    "severity_penalties",  # penalty_for
    "overall",             # penalty_divisor
    "grades",              # grade_for
    "confidence",          # refuse_below, confidence_band
    "categories",          # signal_severity, signals_of, planned_signal_count
    "count_bands",         # count_band
    "exposure",            # exposure_enabled, exposure_spec — E6's rate normalisation
    "aggregation",         # aggregation_decay — E7a's diminishing returns. MOVED from
                           # _DOCUMENTATION_ONLY at E7: `method`/`rule` are still declarative
                           # (multi-asset roll-up is not built), but `decay` is now live.
    "root_cause",          # root_cause_suppressor — E7c, one ticket one penalty
    "assurity",            # app/assurity.py — E9a's third axis. Read OUTSIDE the posture engine
                           # by design: it must never be able to move a posture score.
    "compliance_frameworks",  # app/compliance_gap.py — E9c, where E1's sector expectation landed
    "business_stability",  # app/business_stability.py — Phase 2 financial risk axis. Read OUTSIDE
                           # the posture engine by design: financial health is a separate axis from
                           # cybersecurity posture. A bankrupt company can have excellent security.
    "estate",              # E12 — probe_cap and the published sampling rule. Read by the
                           # COLLECTORS rather than the engine, but it belongs here: the rule is
                           # part of the published model (it IS the denominator), and an orphaned
                           # `estate:` block would mean a sampling rule nothing obeys.
    "critical_ceiling",    # ceiling_score, ceiling_auto_signals, auto_signal_scope (E12)
    "gates",               # entity_block_below + the sanctions block invariant
    "modifiers",           # age / frequency / mitigation, incl. their exempt lists
    "reasons",             # reason_for — the plain-English sentence shown per finding
    "actions",             # action_for — what to DO about it, and when to look again
}
# `industry_profiles` was here until E1. It promoted a severity by one step where a sector cited a
# named instrument — dynamic severity adjustment, which the research rejects because it makes the
# same evidence score differently depending on a label we assigned. Deliberately NOT moved to
# _DOCUMENTATION_ONLY: the block is gone from scoring.yaml entirely, and leaving the key declared
# anywhere would let six lines of YAML silently re-enable it. The sector obligation survives as a
# Compliance Gap finding (E9c) — see docs/compliance-gap-frameworks.md.
_DOCUMENTATION_ONLY = {
    "supersedes":       "provenance — which version this replaces",
    "model":            "names the model family (penalty_subtractive)",
    "excluded_signals": "§4.2 bright line — refusals recorded so they are auditable, never scored",
    "held_roadmap":     "designed categories with no lawful free source yet",
}
# Nested keys that are documented but deliberately not wired. Same rule, one level down.
_NESTED_DOCUMENTATION_ONLY = {
    ("critical_ceiling", "requires_confirmation"):
        "signals that need human confirmation before they may ceiling — no workflow yet",
}


class ScoringConfigError(ValueError):
    """Raised when scoring.yaml violates a methodology invariant."""


class ScoringConfig:
    """Parsed, validated view over the penalty-based scoring.yaml."""

    def __init__(self, data: dict[str, Any], path: Path) -> None:
        self.data = data
        self.path = path
        self.version: str = str(data.get("version", "unknown"))
        self.direction: str = str(data.get("direction", ""))
        self.max_score: int = int(data.get("max_score", 100))
        self.categories: dict[str, Any] = data.get("categories", {})
        self._validate()

    # --- penalties / severities ---

    def penalty_for(self, severity: str) -> float:
        """Points subtracted for a finding of this severity ('pass' -> 0)."""
        if severity in {"pass", "informational", None}:
            return 0.0
        return float(self.data.get("severity_penalties", {}).get(severity, 0.0))

    def signal_severity(self, category: str, signal: str, band_key: str) -> str | None:
        """The severity ('pass'/'low'/…/'critical') a signal's observation maps to, or None if
        the signal/band isn't in the model."""
        band = self.categories.get(category, {}).get(signal)
        if not isinstance(band, dict):
            return None
        return band.get(band_key)

    def signals_of(self, category: str) -> dict[str, Any]:
        return {k: v for k, v in self.categories.get(category, {}).items() if isinstance(v, dict)}

    def category_names(self) -> list[str]:
        return list(self.categories.keys())

    def category_of(self, signal: str) -> str | None:
        """Which category the MODEL puts this signal in, or None if it has no home.

        The single place that question is answered. Collectors each carry a `_CAT` constant and
        the frozen fixtures record whatever that constant said on the day they were captured, so
        a finding's declared category drifts the moment scoring.yaml is reorganised — as it was at
        E5. Resolving from config instead makes recategorisation a config-only edit; see
        `scoring.normalize._category_of` for the full argument.

        Signals are unique across categories (asserted by test), so this is unambiguous.
        """
        for category in self.categories:
            if signal in self.signals_of(category):
                return category
        return None

    def planned_signal_count(self) -> int:
        """The COVERAGE DENOMINATOR: how many signals this deployment actually intends to collect.

        PLANNED, not merely defined. A signal the current configuration CANNOT produce must leave
        this denominator, or every vendor's confidence falls for a feature nobody switched on —
        which is the same error as counting an unchecked signal as a failure, arriving one axis
        over. E12 is the case that forced the distinction: adding the two estate rates to the model
        dropped every corpus vendor's coverage by ~7% while `estate.probe_cap: 1` guaranteed no
        collector could ever emit them.

        The signals are in `categories:` rather than added later on purpose — a signal a collector
        can emit and the model does not band is a signal that scores nothing while looking live,
        which is the drift `_validate_no_dead_config` exists to catch. So the model declares them
        and the denominator excludes them until the feature that produces them is enabled.
        """
        return sum(
            1
            for category in self.categories
            for signal in self.signals_of(category)
            if signal not in self.unreachable_signals()
            and signal not in self.business_stability_signals()
        )

    def business_stability_signals(self) -> set[str]:
        """Signals that feed the Business Stability axis, not Posture confidence.

        `sec_filing`/`insolvency_notice`/`bankruptcy_petition` are declared in
        `continuity_context` — so they score (at `informational`), persist, and reach
        `continuity.py` — but they answer a different question than Posture confidence does
        ("how much do we know about this vendor's SECURITY"). Counting them in the SAME
        denominator that gates the Posture confidence-ceiling and Ghost detection would let
        Business Stability coverage move Posture's calibration, which is exactly the E4 defect
        (change-notice-v5.md §3.4) one layer up — same mistake, different axis.
        Business Stability gets its OWN coverage instead: `continuity.business_stability_
        coverage()`. This is a HARD EXCLUSION, not a config-gated one like
        `unreachable_signals()` — these signals ARE reachable, they simply belong elsewhere.
        docs/tprm_feedback_redesign.md §1.3.

        ONLY SIGNALS THE MODEL ACTUALLY DECLARES BELONG HERE. A previous revision added
        `revenue_stability`, `debt_position`, `cash_flow`, `current_status` and `operating_years`
        on the grounds that they had been "removed from Posture categories to prevent denominator
        regression" — but they are declared in no category, emitted by no registered collector, and
        banded nowhere in `scoring.yaml`. They are names, not signals.

        Excluding a name that cannot occur is a no-op here, so it looked harmless. It was not:
        `continuity.BUSINESS_STABILITY_SIGNALS` must equal this set (the two are duplicated
        deliberately, and `test_business_stability_signal_sets_match` enforces it), and that set is
        the DENOMINATOR of the Business Stability coverage figure. Carrying the five phantoms
        across would have published "2 of 9 checks answered" for an axis that only ever runs four —
        inventing five permanent gaps a reader could never close.

        If those financial signals are later given real bands in `scoring.yaml`, add them back in
        BOTH places. Two tests already guard the pair: `test_business_stability_signal_sets_match`
        catches the two sets drifting apart, and
        `test_business_stability_signals_never_carry_a_posture_penalty` walks every member and
        fails on one with no home in the model — which is how the five phantoms were found.
        """
        return {
            "sec_filing", "sec_going_concern", "insolvency_notice", "bankruptcy_petition",
        }

    def unreachable_signals(self) -> set[str]:
        """Signals no collector can emit under the CURRENT configuration.

        Config-gated, never a hardcoded list: the point is that the set changes when the operator
        changes a setting, and a hardcoded one would silently be wrong the moment they did.
        """
        out: set[str] = set()
        if int((self.data.get("estate") or {}).get("probe_cap", 1)) <= 1:
            # No second wave runs at cap 1, so `estate_*` findings are not merely absent — they
            # are unproducible. Absent evidence lowers confidence; unproducible evidence must not.
            out |= {s for s in self._all_signal_names() if s.startswith("estate_")}
        return out

    def _all_signal_names(self) -> set[str]:
        return {s for c in self.categories for s in self.signals_of(c)}
    
    def all_signal_names(self) -> set[str]:
        """Public method to get all signal names in the model.
        
        This is used by the age-based confidence calculator to determine
        which signals were planned for collection.
        """
        return self._all_signal_names()

    def penalty_divisor(self) -> float:
        """Divisor for the OVERALL posture: `100 - total_penalty / divisor`.

        Fixed by the model, never by how many categories returned data — that is what stops
        evidence coverage leaking into posture. Defaults to the category count, which makes the
        overall exactly the mean of the seven category postures.
        """
        d = self.data.get("overall", {}).get("penalty_divisor")
        return float(d) if d else float(len(self.categories) or 1)

    # --- grades / confidence ---

    def grades(self) -> dict[str, Any]:
        return self.data.get("grades", {})

    def grade_for(self, posture: float) -> str:
        """Letter grade for a posture score — highest grade whose `min` the score meets."""
        best = "F"
        best_min = -1.0
        for letter, spec in self.grades().items():
            lo = float(spec.get("min", 0))
            if posture >= lo and lo > best_min:
                best, best_min = letter, lo
        return best

    def refuse_below(self) -> float:
        return float(self.data.get("confidence", {}).get("refuse_below", 0.4))

    def _bands(self) -> dict[str, Any]:
        return self.data.get("confidence", {}).get("bands", {})

    def confidence_band(self, coverage: float, operating_years: float | None = None) -> str:
        """Confidence band for coverage.

        Age does NOT move these thresholds. The assurance_multiplier (scoring.yaml
        confidence.assurance_multiplier) is the ONE place operating history touches
        confidence, and it acts on the coverage NUMBER before banding, not on the
        band thresholds themselves. Shifting thresholds by age would make the same
        coverage read differently for different vendors, which is the comparability
        violation E1 was built to prevent.

        The `operating_years` parameter is accepted but ignored for backward
        compatibility with callers that already pass it.
        """
        high_threshold = float(self._bands().get("high", 0.9))
        medium_threshold = float(self._bands().get("medium", 0.7))

        if coverage >= high_threshold:
            return "High"
        if coverage >= medium_threshold:
            return "Medium"
        return "Low"

    def confidence_assurance_signal(self) -> str | None:
        """Signal whose observed band can adjust confidence as an assurance multiplier."""
        v = self.data.get("confidence", {}).get("assurance_multiplier", {}).get("signal")
        return str(v) if v else None

    def confidence_multiplier_for_band(self, band_key: str | None) -> float:
        """Bounded multiplier for a confidence-driving band (defaults to 1.0).

        The STEPPED fallback, used when a maturity finding carries no year count. Prefer
        `confidence_multiplier_for_index` — five bands cannot separate an 11-year-old vendor from
        a 40-year-old one, which is the flattening this pair of methods exists to fix.
        """
        if not band_key:
            return 1.0
        table = self.data.get("confidence", {}).get("assurance_multiplier", {}).get("by_band", {})
        try:
            return float(table.get(band_key, 1.0))
        except (TypeError, ValueError):
            return 1.0

    def _assurance_curve(self) -> tuple[float, float] | None:
        """`(floor, ceiling)` for the continuous multiplier, or None when the file ships no curve.

        None means "fall back to the band table" rather than "use a built-in default": a scoring
        file that predates the curve must keep scoring exactly as it did, or upgrading the code
        would silently move every stored vendor's confidence.
        """
        curve = self.data.get("confidence", {}).get("assurance_multiplier", {}).get("curve")
        if not isinstance(curve, dict):
            return None
        try:
            return float(curve["floor"]), float(curve["ceiling"])
        except (KeyError, TypeError, ValueError):
            return None

    def confidence_multiplier_for_index(self, index: float | None) -> float | None:
        """Bounded multiplier interpolated across a 0-1 maturity index, or None when unavailable.

        None is returned — rather than 1.0 — so the caller can tell "this file has no curve" from
        "this vendor's curve landed on neutral", and fall back to the band table only in the first
        case.
        """
        if index is None:
            return None
        curve = self._assurance_curve()
        if curve is None:
            return None
        from .maturity import multiplier_from

        return multiplier_from(index, curve[0], curve[1])

    # --- count bands (footprint) ---

    def count_band(self, signal: str, n: int) -> str | None:
        """Bucket a raw count into a band key (small/medium/large or none/some/many).

        For an exposure signal this is the REVERT PATH, not the normal one. `stale_hosts` left
        `count_bands:` at E6; its old thresholds live under `exposure.signals.stale_hosts.
        fallback_count_bands` so that `exposure.enabled: false` restores the pre-E6 behaviour
        exactly, rather than dropping the signal because its bands are no longer anywhere.
        """
        spec = self.data.get("count_bands", {}).get(signal)
        if not spec:
            spec = (self.data.get("exposure", {}).get("signals", {})
                    .get(signal, {}).get("fallback_count_bands"))
        if not spec:
            return None
        if signal == "subdomain_estate":
            return "small" if n <= spec["small"] else "medium" if n <= spec["medium"] else "large"
        if signal == "stale_hosts":
            return "none" if n <= spec["none"] else "some" if n <= spec["some"] else "many"
        return None

    # --- exposure (E6): a failure RATE rather than a failure COUNT ---

    def exposure_enabled(self) -> bool:
        """The revert switch. False sends every exposure signal back to its `count_bands` entry."""
        return bool(self.data.get("exposure", {}).get("enabled", False))

    def exposure_spec(self, signal: str) -> dict[str, Any] | None:
        """This signal's exposure parameters, or None if it is not rate-normalised.

        Returns None when the feature is off, so one call site answers both "is this signal
        rate-normalised" and "is the mechanism live" — a caller cannot honour one and forget the
        other.
        """
        if not self.exposure_enabled():
            return None
        spec = self.data.get("exposure", {}).get("signals", {}).get(signal)
        return spec if isinstance(spec, dict) else None

    def exposure_signals(self) -> set[str]:
        """Every signal with an exposure spec, whether or not the feature is enabled.

        Deliberately NOT gated on `enabled`: `normalize` needs to know a signal is rate-normalised
        in order to fall back to its count bands when the switch is off. Gating this would make
        `enabled: false` silently drop the signal instead of reverting it.
        """
        return set(self.data.get("exposure", {}).get("signals", {}))

    def exposure_denominator_signal(self, signal: str) -> str | None:
        return (self.data.get("exposure", {}).get("signals", {})
                .get(signal, {}).get("denominator_signal"))

    # --- E8: config-driven gates ---

    def finding_gates(self) -> list[tuple[str, dict[str, Any]]]:
        """Enabled gates that fire on a FINDING, in declaration order.

        `sanctions` and `entity_ambiguous` are excluded: they fire on inputs the engine holds
        before normalisation (a screen hit, an entity-resolution score) and keep their own
        branches. Everything with a `when:` clause is evaluated here.
        """
        out = []
        for name, spec in (self.data.get("gates") or {}).items():
            if not isinstance(spec, dict) or not spec.get("when"):
                continue
            if spec.get("enabled") is False:
                continue
            out.append((name, spec))
        return out

    @staticmethod
    def gate_matches(spec: dict[str, Any], signal: str, band_key: str,
                     value: Any = None, now: datetime | None = None) -> bool:
        """Does this finding trip this gate?

        `value_date_before_now` names a DATE FIELD in the finding's value that must already have
        passed — CISA's KEV due date being the case it was written for. Kept declarative rather
        than as a code branch per gate, so enabling a gate stays a config edit with a basis
        attached rather than a pull request nobody reviews as a policy change.
        """
        when = spec.get("when") or {}
        if when.get("signal") != signal:
            return False
        bands = when.get("bands")
        if bands and band_key not in bands:
            return False
        date_field = when.get("value_date_before_now")
        if date_field:
            raw = value.get(date_field) if isinstance(value, dict) else None
            if not raw:
                return False
            try:
                due = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                return False
            if due.tzinfo is None:
                due = due.replace(tzinfo=UTC)
            if due >= (now or datetime.now(UTC)):
                return False
        return True

    def gate_basis(self, name: str) -> str:
        return str((self.data.get("gates") or {}).get(name, {}).get("basis", "")).strip()

    def gate_adjudication(self, name: str) -> str:
        return str((self.data.get("gates") or {}).get(name, {}).get("adjudication", "")).strip()

    # --- E7d: the confidence ceiling ramp ---

    def confidence_ceiling(self, coverage: float) -> float | None:
        """The highest posture publishable on this much evidence, or None for no cap.

        Picks the HIGHEST rung the coverage clears, so adding a rung can only ever be read one
        way. Returns None when no ramp is configured, which leaves pre-E7d behaviour intact — the
        feature is additive and removing the block removes the feature.
        """
        ramp = self.data.get("confidence", {}).get("ceiling_ramp") or []
        best: float | None = None
        best_at = -1.0
        for rung in ramp:
            at = float(rung.get("coverage_at_least", 0.0))
            if coverage >= at and at > best_at:
                best, best_at = float(rung.get("ceiling", self.max_score)), at
        return best

    def insufficient_evidence_caveat(self) -> str:
        return str(self.data.get("confidence", {}).get("insufficient_evidence_caveat", "")).strip()

    # --- aggregation + root cause (E7) ---

    def aggregation_decay(self) -> float:
        """E7a's λ. 1.0 disables diminishing returns and restores the plain sum."""
        d = self.data.get("aggregation", {}).get("decay")
        return float(d) if d is not None else 1.0

    def root_cause_suppressor(self, signal: str, charged_in_category: set[str],
                              bands_in_category: dict[str, str]) -> str | None:
        """Why this signal's penalty is waived, or None if it stands.

        Returns the SENTENCE, not a bool, because a suppressed finding still appears on the report
        and the reader is owed the reason. Two rule kinds, deliberately kept apart:

          * `precedence` fires when the dominant signal is also CHARGING — one vulnerability, one
            patch, one penalty.
          * `satisfied_by` fires when the superseding control is PASSING — the vendor has the
            control, just by a different mechanism.

        Collapsing them into one shape would hide that difference, and the difference is exactly
        what a vendor disputing a suppression would argue about.
        """
        rc = self.data.get("root_cause", {})
        for rule in rc.get("precedence", []):
            if signal in (rule.get("suppresses") or []) and rule.get("dominant") in charged_in_category:
                return (f"superseded by {rule['dominant']} — "
                        f"{str(rule.get('basis', '')).strip()}")
        for rule in rc.get("satisfied_by", []):
            if rule.get("control") != signal:
                continue
            observed = bands_in_category.get(str(rule.get("signal")))
            if observed is not None and observed in (rule.get("bands") or []):
                return (f"satisfied by {rule['signal']}={observed} — "
                        f"{str(rule.get('basis', '')).strip()}")
        return None

    # --- critical ceiling (knockout) ---

    def ceiling_score(self) -> float:
        return float(self.data.get("critical_ceiling", {}).get("ceiling_score", 49))

    # --- estate (E12) ---

    def estate_probe_cap(self) -> int:
        """How many hosts to probe. 1 is apex-only, which is exactly the pre-E12 behaviour."""
        return max(1, int((self.data.get("estate") or {}).get("probe_cap", 1)))

    def estate_spec(self) -> dict[str, Any]:
        return dict(self.data.get("estate") or {})

    def _validate_estate(self) -> None:
        """The sampling rule is part of the published model, so it validates like one (E12).

        `probe_cap` is a RUNTIME AND POLITENESS BUDGET before it is a statistical choice: every
        collector queries someone else's free service and the cap multiplies every one of them. A
        cap raised without anyone noticing is how a polite client becomes an impolite one, so an
        absurd value fails at startup rather than at somebody else's rate limiter.
        """
        spec = self.data.get("estate")
        if not spec:
            return
        cap = int(spec.get("probe_cap", 1))
        if cap < 1:
            raise ScoringConfigError(
                "estate.probe_cap must be at least 1 — the apex is always probed, because the "
                "critical ceiling arms on it specifically and a sample that could omit it would "
                "make the knockout depend on the dice."
            )
        if cap > 2000:
            raise ScoringConfigError(
                f"estate.probe_cap is {cap}. Every collector queries someone else's free service "
                f"and this multiplies all of them; a cap this size is a rate-limit incident "
                f"waiting to happen. Raise the ceiling here deliberately if it is really wanted."
            )
        if len(str(spec.get("basis", "")).strip()) < 40:
            raise ScoringConfigError(
                "estate has no substantive `basis`. The sampling rule IS the denominator, and a "
                "denominator a vendor cannot be walked through is one they cannot dispute."
            )

    def ceiling_auto_signals(self) -> set[str]:
        return set(self.data.get("critical_ceiling", {}).get("auto_signals", []))

    def ceiling_scope_satisfied(self, signal: str, value: Any) -> bool:
        """Whether this observation is in scope to ARM the critical ceiling (E12 interaction).

        Trivially true today: every collector probes the apex once, so there is one observation and
        it is the apex one. It exists now rather than at E12 because the failure it prevents is
        silent and arrives as a one-line diff.

        When the estate fans out, `cert_validity` becomes a rate and the ceiling has to arm off
        something. Arming on ANY host would cap every large vendor at 49 on one abandoned staging
        certificate — and a non-compensatory knockout that fires constantly is one nobody reads,
        which is strictly worse than not having it. Arming on a rate threshold would make the most
        severe response in the model a tunable percentage, and invite the argument that 3% of hosts
        is acceptable.

        So the scope is the APEX, declared in config with its reasoning. A fanned-out collector
        must set `host_role` on its findings; one that does not, and emits a per-host expired cert
        without saying which host, cannot arm the ceiling — which is the safe direction, because
        the alternative is a knockout firing on evidence that does not support it.
        """
        scope = (self.data.get("critical_ceiling", {}).get("auto_signal_scope") or {}).get(signal)
        if not scope:
            return True
        required = scope.get("host_role")
        if not required:
            return True
        # No `host_role` on the finding means a single-target probe, which is the apex by
        # construction. Once a collector fans out it must say which host it is talking about.
        observed = value.get("host_role") if isinstance(value, dict) else None
        return observed is None or observed == required

    # --- modifiers / gates ---

    def modifiers(self) -> dict[str, Any]:
        return self.data.get("modifiers", {})

    def reason_for(self, signal: str, band_key: str) -> str | None:
        """The plain-English sentence for a failing band — what the client actually reads.

        None for passing bands (nothing was deducted, so there is nothing to explain).
        """
        return self.data.get("reasons", {}).get(signal, {}).get(band_key)

    def action_for(self, signal: str, band_key: str) -> dict[str, Any] | None:
        """What to do about a failing band: `action`, `ask_of_vendor`, `recheck_after`,
        `accepts_as_refute`. None for passing bands — nothing was deducted, so there is nothing
        to act on."""
        entry = self.data.get("actions", {}).get(signal, {}).get(band_key)
        return dict(entry) if isinstance(entry, dict) else None

    def penalising_bands(self) -> list[tuple[str, str, str]]:
        """Every (category, signal, band) that carries a penalty. Drives the reasons validator."""
        out = []
        for cat in self.categories:
            for signal, bands in self.signals_of(cat).items():
                for band, severity in bands.items():
                    if self.penalty_for(severity) > 0:
                        out.append((cat, signal, band))
        return out

    def never_decays_signals(self) -> set[str]:
        """Signals observed as CURRENT state, whose `event_date` is a boundary and not an event.

        Age decay must not apply to them: an expired certificate does not become less dangerous
        the longer it stays expired.
        """
        return set(self.modifiers().get("age", {}).get("never_decays", []))

    def frequency_exempt_signals(self) -> set[str]:
        """Signals whose repeats are a coarse-match BAG, not a pattern of distinct events.

        These collapse to their worst representative WITHOUT frequency amplification, so a bag of
        keyword-matched CVEs cannot tank a clean estate on match volume alone.
        """
        return set(self.modifiers().get("frequency", {}).get("exempt_signals", []))

    def entity_block_below(self) -> float:
        return float(self.data.get("gates", {}).get("entity_ambiguous", {}).get("below_confidence", 0.5))

    # --- validation ---

    def _validate(self) -> None:
        d = self.direction.lower()
        if "posture" not in d or "100" not in d:
            raise ScoringConfigError(
                f"direction convention missing/incorrect in {self.path.name}: {self.direction!r} "
                "(expected '100 = strongest posture … 0 = weakest')"
            )
        pens = self.data.get("severity_penalties", {})
        for sev in ("critical", "high", "medium", "low"):
            if sev not in pens:
                raise ScoringConfigError(f"severity_penalties missing {sev!r}")
        if not (pens["critical"] >= pens["high"] >= pens["medium"] >= pens["low"] >= 0):
            raise ScoringConfigError("severity_penalties must be monotonic: critical≥high≥medium≥low≥0")
        if not self.grades():
            raise ScoringConfigError("grades table is required")
        if not self.categories:
            raise ScoringConfigError("no categories defined")

        gates = self.data.get("gates", {})
        if "sanctions" not in gates:
            raise ScoringConfigError("gates.sanctions is required")
        if gates["sanctions"].get("behaviour") != "block":
            raise ScoringConfigError("gates.sanctions.behaviour must be 'block' (emits no score, s16(7))")

        self._validate_no_dead_config()
        self._validate_every_penalty_is_explainable()
        self._validate_every_penalty_is_actionable()
        self._validate_gates()
        self._validate_assurity()
        self._validate_compliance_frameworks()
        self._validate_estate()

    def _validate_assurity(self) -> None:
        """ABSENCE NEVER SUBTRACTS — enforced at load, not merely intended (E9a).

        The whole argument for a separate assurance axis is that a vendor without certifications
        has UNEVIDENCED security rather than bad security. A negative credit would reintroduce the
        audit-budget tax E2 removed, one axis over, where nobody is watching for it. Every credit
        must also name a real band, or it is dead config claiming to reward something unreachable.
        """
        spec = self.data.get("assurity")
        if not spec:
            return
        known: dict[str, set[str]] = {}
        for cat in self.categories:
            for signal, bands in self.signals_of(cat).items():
                known[signal] = set(bands)
        for signal, table in (spec.get("credit") or {}).items():
            if signal not in known:
                raise ScoringConfigError(
                    f"assurity.credit.{signal} is in no category — it can never be observed")
            for band, value in table.items():
                if band not in known[signal]:
                    raise ScoringConfigError(
                        f"assurity.credit.{signal}.{band} is not a band of {signal}")
                if float(value) < 0:
                    raise ScoringConfigError(
                        f"assurity.credit.{signal}.{band} is negative. Absence never subtracts on "
                        f"this axis — that is the whole reason it exists. Only a compliance gap "
                        f"may reduce Assurity."
                    )

    def _validate_compliance_frameworks(self) -> None:
        """Every framework names a real instrument, and every control a real band (E9c).

        This is the guard that keeps the Compliance Gap from becoming what `industry_profiles` was:
        a plausible-sounding expectation with an official-looking citation, asserted by us. A
        control referencing a band the model does not have would emit a finding that could never
        fire, which reads as coverage and provides none.
        """
        from .sectors import known_sectors

        vocabulary = known_sectors()
        for key, spec in (self.data.get("compliance_frameworks") or {}).items():
            # A framework may be DECLARED AND OFF — the same pattern `gates:` uses for
            # `kev_overdue`. It is off because the evidence for it does not exist yet, and saying
            # so in the tree is worth far more than silence: the reason is reviewable, the
            # research is not repeated, and switching it on is a one-line change once the input
            # arrives. A disabled framework must still validate fully; nothing rots.
            if not spec.get("enabled", True) and len(
                    str(spec.get("disabled_because", "")).strip()) < 40:
                raise ScoringConfigError(
                    f"compliance_frameworks.{key} is disabled but states no substantive "
                    f"`disabled_because`. A framework that is off for a reason nobody recorded is "
                    f"indistinguishable from one somebody forgot."
                )
            if len(str(spec.get("basis", "")).strip()) < 40:
                raise ScoringConfigError(
                    f"compliance_frameworks.{key} has no substantive `basis`. A framework "
                    f"expectation without a named instrument is our opinion about somebody's "
                    f"legal obligations."
                )
            if not spec.get("applies_to_sectors") and not spec.get("asserted_by"):
                raise ScoringConfigError(
                    f"compliance_frameworks.{key} can never apply: it names no sector and no "
                    f"assertion signal."
                )
            # The sector must be one the whole system knows, not one this file invented. A
            # framework bound to `banking` while cohorts are keyed on `financial_services` applies
            # to nobody the client can actually be asked about, and it fails SILENTLY IN THE UNSAFE
            # DIRECTION: no gaps found, which a reader takes as no obligations breached.
            off_vocabulary = set(spec.get("applies_to_sectors") or []) - vocabulary
            if off_vocabulary:
                raise ScoringConfigError(
                    f"compliance_frameworks.{key}.applies_to_sectors names sectors outside the "
                    f"controlled vocabulary: {sorted(off_vocabulary)}. Sectors come from "
                    f"benchmarking's `sector_groups` partition (app/sectors.py) and client "
                    f"spellings belong in the alias table, not here — otherwise the obligation and "
                    f"the peer cohort key off different words for the same industry."
                )
            asserted = spec.get("asserted_by")
            if asserted is not None:
                # WHICH standard, not merely THAT there is one. `cert_posture` bands say
                # `claimed_unverified`; they do not say what was claimed. Matching on the band
                # alone fires every asserted framework for any vendor claiming any certification,
                # which publishes an assertion the vendor never made and then finds them short
                # against it.
                if not asserted.get("claim_contains"):
                    raise ScoringConfigError(
                        f"compliance_frameworks.{key}.asserted_by names no `claim_contains`. A "
                        f"band records THAT a certification was claimed, never WHICH one, so "
                        f"without this the framework fires for vendors who never asserted it."
                    )
                if not asserted.get("bands"):
                    raise ScoringConfigError(
                        f"compliance_frameworks.{key}.asserted_by names no `bands`")
                sig = str(asserted.get("signal", ""))
                sig_bands = self.signals_of(self.category_of(sig) or "").get(sig)
                if sig_bands is None:
                    raise ScoringConfigError(
                        f"compliance_frameworks.{key}.asserted_by.signal {sig!r} is in no category")
                unknown = set(asserted["bands"]) - set(sig_bands)
                if unknown:
                    raise ScoringConfigError(
                        f"compliance_frameworks.{key}.asserted_by names bands that do not exist "
                        f"on {sig}: {sorted(unknown)}")
            for signal, control in (spec.get("controls") or {}).items():
                bands = self.signals_of(self.category_of(signal) or "").get(signal)
                if bands is None:
                    raise ScoringConfigError(
                        f"compliance_frameworks.{key}.controls.{signal} is in no category")
                unknown = set(control.get("failing_bands") or []) - set(bands)
                if unknown:
                    raise ScoringConfigError(
                        f"compliance_frameworks.{key}.controls.{signal} names bands that do not "
                        f"exist: {sorted(unknown)}")
                if len(str(control.get("expectation", "")).strip()) < 30:
                    raise ScoringConfigError(
                        f"compliance_frameworks.{key}.controls.{signal} states no expectation")

    def _validate_gates(self) -> None:
        """Every gate states a BASIS, and a disabled one states why it is off (E8).

        A gate stops a company being onboarded. That is the most consequential thing this system
        does, and it must never be possible to add one without a reason someone can be shown —
        the discipline `industry_profiles` had, which was right even though its mechanism was
        wrong. A `when:` clause naming a signal the model does not band is dead config and fails
        here, the same way an orphaned `reasons` entry does.
        """
        known = {s for c in self.categories for s in self.signals_of(c)}
        for name, spec in (self.data.get("gates") or {}).items():
            if not isinstance(spec, dict):
                raise ScoringConfigError(f"gates.{name} must be a mapping")
            if len(str(spec.get("basis", "")).strip()) < 40:
                raise ScoringConfigError(
                    f"gates.{name} has no substantive `basis`. A gate blocks a vendor from being "
                    f"onboarded — it needs a named legal, registry or standards ground."
                )
            if spec.get("enabled") is False and not str(spec.get("disabled_because", "")).strip():
                raise ScoringConfigError(
                    f"gates.{name} is disabled with no `disabled_because`. A declared-but-off gate "
                    f"is a decision; record it, or delete the gate."
                )
            when = spec.get("when")
            if when and when.get("signal") not in known:
                raise ScoringConfigError(
                    f"gates.{name}.when.signal {when.get('signal')!r} is in no category — the gate "
                    f"could never fire"
                )

    def _validate_every_penalty_is_explainable(self) -> None:
        """No unexplained deductions. Every band that costs points must have a plain-English reason.

        A score a client cannot have explained to them is the thing this product exists not to
        produce, so a missing sentence is a startup failure, not a rendering gap. Skipped when the
        file declares no `reasons` block at all (minimal configs in tests).
        """
        if "reasons" not in self.data:
            return
        missing = [f"{sig}.{band}" for _cat, sig, band in self.penalising_bands()
                   if not self.reason_for(sig, band)]
        if missing:
            raise ScoringConfigError(
                f"{self.path.name}: {len(missing)} band(s) subtract points with no reason to show "
                f"a client: {sorted(missing)}. Add a sentence under `reasons:` for each."
            )
        # The reverse: a reason for a band that no longer exists is stale text waiting to mislead.
        real = {(sig, band) for _c, sig, band in self.penalising_bands()}
        orphans = [f"{sig}.{band}" for sig, bands in self.data.get("reasons", {}).items()
                   for band in bands if (sig, band) not in real]
        if orphans:
            raise ScoringConfigError(
                f"{self.path.name}: reason(s) for band(s) that do not exist or no longer "
                f"penalise: {sorted(orphans)}. Remove them, or fix the band name."
            )

    def _validate_every_penalty_is_actionable(self) -> None:
        """No deduction without a next step. The same rule as `reasons`, one level further on.

        A finding that explains itself and stops there hands the reader the translation work —
        "posture 65, expired certificate" into "do not sign, ask for X, re-check in 7 days" — which
        is the work this product exists to remove. In procurement that gap is where an unactioned
        amber score becomes a signed contract.

        Skipped when the file declares no `actions` block at all (minimal configs in tests).
        """
        if "actions" not in self.data:
            return
        required = ("action", "recheck_after")
        missing: list[str] = []
        for _cat, sig, band in self.penalising_bands():
            entry = self.action_for(sig, band)
            if not entry or any(not str(entry.get(k) or "").strip() for k in required):
                missing.append(f"{sig}.{band}")
        if missing:
            raise ScoringConfigError(
                f"{self.path.name}: {len(missing)} band(s) subtract points with no action and "
                f"re-check date: {sorted(missing)}. Add them under `actions:`."
            )
        # The reverse: advice for a band that no longer penalises is stale text waiting to mislead
        # — and advice that has drifted from its finding is worse than none, because it is
        # confidently wrong.
        real = {(sig, band) for _c, sig, band in self.penalising_bands()}
        orphans = [f"{sig}.{band}" for sig, bands in self.data.get("actions", {}).items()
                   if isinstance(bands, dict)
                   for band in bands if (sig, band) not in real]
        if orphans:
            raise ScoringConfigError(
                f"{self.path.name}: action(s) for band(s) that do not exist or no longer "
                f"penalise: {sorted(orphans)}. Remove them, or fix the band name."
            )

    def _validate_no_dead_config(self) -> None:
        """Fail on config the engine never reads — see the drift guard note at the top of this file.

        The model is the deliverable, so a key sitting in it is a CLAIM. An unread key is a claim
        the code does not honour, and that is precisely the failure this file exists to prevent.
        """
        declared = set(self.data)
        unknown = declared - _ENGINE_READS - set(_DOCUMENTATION_ONLY)
        if unknown:
            raise ScoringConfigError(
                f"{self.path.name} declares key(s) nothing reads: {sorted(unknown)}. "
                "Either wire them into the engine, or add them to _DOCUMENTATION_ONLY in "
                "scoring_config.py with a note saying why they are inert. Config that scores "
                "nothing must not look like config that scores something."
            )
        for (parent, child), _why in _NESTED_DOCUMENTATION_ONLY.items():
            block = self.data.get(parent)
            if isinstance(block, dict) and child in block:
                log.debug("%s.%s is documentation-only (not read by the engine)", parent, child)


def load_scoring_config(path: Path | None = None) -> ScoringConfig:
    p = path or get_settings().scoring_yaml_path
    if not p.exists():
        raise ScoringConfigError(f"scoring.yaml not found at {p}")
    with p.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ScoringConfigError(f"scoring.yaml did not parse to a mapping: {type(data)}")
    return ScoringConfig(data, p)


@lru_cache
def get_scoring_config() -> ScoringConfig:
    return load_scoring_config()
