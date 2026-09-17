"""Normalizer — Finding -> NormalizedFinding (observation -> severity -> penalty).

The collector says WHAT it observed; the model (scoring.yaml) says how BAD that is — a severity
(pass / low / medium / high / critical / informational) and therefore a penalty. Keeping that
mapping here, not in the collector, makes the model the single source of truth (methodology §5.3):
changing a score means editing config, not code.

A 'pass' observation still produces a NormalizedFinding (penalty 0) — it is EVIDENCE that a
signal was checked and is clean, which counts toward coverage (the confidence axis). Sanctions
findings carry no severity: they are gate input, never a penalty (Finding B).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..logging_config import get_logger
from ..models import Finding
from ..scoring_config import ScoringConfig
from . import exposure

log = get_logger("scoring.normalize")

_SANCTIONS_CATEGORY = "regulatory_legal_sanctions"
# Count signals whose raw count is bucketed into a band before severity lookup (footprint).
# `stale_hosts` left this set at E6 — it is banded on an exposure RATE now, not on a raw count.
# `subdomain_estate` stays: it is still bucketed for context, it just no longer penalises.
_COUNT_SIGNALS = {"subdomain_estate"}


@dataclass
class NormalizedFinding:
    """A finding after severity lookup, before modifiers/roll-up. `penalty` is the base points
    subtracted (0 for pass/informational); `severity` is None for sanctions (gate input)."""

    evidence_id: str | None
    source: str
    category: str
    signal: str
    band_key: str
    severity: str | None
    penalty: float
    event_date: datetime | None
    is_critical: bool          # a directly-observed current critical -> auto ceiling (knockout)
    is_sanctions: bool
    observed: str
    remediation_evidenced: bool = False   # -> NIST mitigation factor (x0.6), never a mere claim
    note: str | None = None
    # DEPRECATED at E1, removal scheduled for the following release. These recorded a sector
    # severity promotion; that mechanism is gone, so `base_severity` always equals `severity` and
    # `promoted_by` is always None. Retained only so receipts stored before E1 still deserialise.
    base_severity: str | None = None
    promoted_by: str | None = None
    dispute: str | None = None   # 'nullified' | 'mitigated' when an accepted refute changed this

    # Operating history as a continuous 0-1 index, already discounted for how well the claim is
    # evidenced (maturity.py). Carried alongside `band_key` because the band saturates at ten years
    # and cannot distinguish an 11-year-old vendor from a 40-year-old one. Only the CONFIDENCE
    # multiplier reads it — it never reaches `penalty`, and there is no path by which it could.
    assurance_index: float | None = None

    # E6. For a rate-normalised signal: how many things were checked, how many failed, and the
    # blended index the band came from. Carried onto the finding rather than recomputed at render
    # time because E6's exit criterion is PUBLISH THE DENOMINATOR — "9 of 900 hosts" is the
    # sentence, and a rate whose denominator is not shown cannot be disputed. Attribution
    # disagreements ("you counted 340, we operate 40") are a top-two dispute category.
    denominator: int | None = None
    exposure_index: float | None = None

    # E7. `suppressed_by` is the SENTENCE explaining why this finding's penalty was waived under
    # root-cause deduplication — carried, not dropped, because "we saw this and did not charge for
    # it" is a different statement from "we did not see it", and only one of them is true.
    # `aggregation_rank` is where the finding sat in its category's descending penalty order, which
    # is what makes the diminishing-returns discount reconstructable from the stored receipt.
    suppressed_by: str | None = None
    aggregation_rank: int | None = None

    # The collector's structured value, carried through so a GATE can read fields the band does
    # not encode — CISA's KEV due date being the case it was added for (E8). Kept as the raw
    # snapshot rather than a parsed subset: a gate's trigger is config, so the fields it may need
    # are not known here, and pre-selecting them would make enabling a gate a code change again.
    value_snapshot: Any = None

    # Filled by the ENGINE after the modifiers run, so the stored record can reproduce the
    # published score. Without these, a 4-year-old breach shows its -40 base against a category
    # that only lost -16, and the receipts visibly fail to add up.
    effective_penalty: float = 0.0
    occurrences: int = 1


def _band_key(finding: Finding) -> str:
    if isinstance(finding.value, dict) and "band" in finding.value:
        return str(finding.value["band"])
    return finding.observed


def _assurance_index_of(finding: Finding) -> float | None:
    """Read the collector's pre-computed assurance index, or derive one from raw years.

    Deriving here as a fallback keeps a collector that emits `years` but predates the index from
    silently dropping back to the stepped band table.
    """
    if not isinstance(finding.value, dict):
        return None
    raw = finding.value.get("assurance_index")
    if raw is None and finding.value.get("years") is not None:
        from ..maturity import assurance_index

        try:
            return assurance_index(float(finding.value["years"]), finding.source)
        except (TypeError, ValueError):
            return None
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _count_of(finding: Finding) -> int | None:
    if isinstance(finding.value, dict) and "count" in finding.value:
        try:
            return int(finding.value["count"])
        except (TypeError, ValueError):
            return None
    return None


def _category_of(signal: str, cfg: ScoringConfig) -> str | None:
    """Where the MODEL says this signal lives — not where the collector guessed.

    This file's opening line is that the collector says WHAT it observed and the model says how
    bad that is, so the model is the single source of truth. Category assignment was the one place
    that principle was not honoured: every collector hard-coded a `_CAT` constant, and the engine
    trusted it. The cost showed up at E5, when reorganising categories would have meant editing
    twelve collectors AND rewriting five frozen fixtures whose whole value is that they are
    captured once and never touched.

    Worse, a collector and the config could disagree silently. `normalize_one` dropped any finding
    whose declared category did not contain its signal — so a category rename in scoring.yaml would
    have quietly stopped scoring a signal, logging a warning nobody reads and moving every affected
    vendor's posture with no diff to explain it.

    Signals are unique across categories (asserted by test), so this lookup is unambiguous, and
    recategorisation becomes a config-only edit — which is what a model held in config is for.
    """
    return cfg.category_of(signal)


def _denominator_for(finding: Finding, cfg: ScoringConfig,
                     denominators: dict[str, int] | None) -> int | None:
    """How many things were checked, for a rate-normalised signal.

    Two sources, in order:
      1. a `denominator` on the finding's own value — what a collector supplies when it knows;
      2. the raw count of the DENOMINATOR SIGNAL from the same collection run.

    (2) is what makes E6 work against frozen evidence. The five corpus fixtures were captured
    before this phase existed and carry no `denominator` key; requiring one would have meant
    re-capturing evidence to satisfy a config change, which is precisely what a frozen corpus
    exists to prevent. `ct_collector` now emits (1) as well, so a stored receipt is
    self-contained going forward, and (2) remains the fallback for everything captured earlier.
    """
    if isinstance(finding.value, dict) and finding.value.get("denominator") is not None:
        try:
            return int(finding.value["denominator"])
        except (TypeError, ValueError):
            pass
    source_signal = cfg.exposure_denominator_signal(finding.signal)
    if source_signal and denominators:
        return denominators.get(source_signal)
    return None


def normalize_one(finding: Finding, cfg: ScoringConfig, evidence_id: str | None,
                  sector: str | None = None,
                  denominators: dict[str, int] | None = None) -> NormalizedFinding | None:
    """Map one finding onto a severity + penalty. Returns None if it has no scoring home.

    `sector` IS ACCEPTED AND DELIBERATELY IGNORED (E1). It used to select an industry profile that
    promoted a severity by one step — a missing DMARC record read as a hygiene gap for a farm
    supplier and a live fraud exposure for a bank. That is dynamic severity adjustment: the same
    evidence scoring differently because of a label we assigned, which destroys the cross-vendor
    comparability the whole model rests on.

    The parameter stays on the signature so callers do not have to change in lockstep, and so a
    future reader finds this note rather than wondering where sector handling went. The sector
    obligation survives as a Compliance Gap finding (E9c); see the design notes.
    """
    if not finding.category or not finding.signal:
        return None

    # The MODEL decides where a signal lives; the collector's declared category is a routing hint
    # kept only for the sanctions gate, which is not a scoring category at all.
    category = _category_of(finding.signal, cfg)

    exposure_result = None

    def make(severity: str | None, *, is_critical: bool = False, is_sanctions: bool = False,
             band_key: str, note: str | None = None) -> NormalizedFinding:
        # `base_severity` now always equals `severity` and `promoted_by` is always None. Both are
        # retained for ONE RELEASE so stored receipts written before E1 still deserialise; remove
        # them, and the api.py `promoted_from` projection, in the release after this one.
        base = severity
        promoted_by = None
        return NormalizedFinding(
            evidence_id=evidence_id, source=finding.source, category=category or finding.category,
            signal=finding.signal, band_key=band_key, severity=severity,
            penalty=cfg.penalty_for(severity) if severity else 0.0,
            event_date=finding.event_date, is_critical=is_critical, is_sanctions=is_sanctions,
            observed=finding.observed,
            remediation_evidenced=finding.remediation_evidenced, note=note,
            base_severity=base, promoted_by=promoted_by,
            assurance_index=_assurance_index_of(finding),
            value_snapshot=finding.value,
            denominator=exposure_result.denominator if exposure_result else None,
            exposure_index=exposure_result.index if exposure_result else None,
        )

    # Sanctions never carry a severity — gate input, routed to the sanctions gate (Finding B).
    if finding.category == _SANCTIONS_CATEGORY:
        return make(None, is_sanctions=True, band_key=_band_key(finding),
                    note="gate input — sanctions, never scored")

    if category is None:
        log.warning("signal %r is in no scoring.yaml category — not scored", finding.signal)
        return None
    if category != finding.category:
        # Not an error: the collector's constant simply predates a recategorisation. Logged at
        # debug so a drift is discoverable without becoming noise on every run.
        log.debug("signal %r: collector said %r, model says %r — using the model",
                  finding.signal, finding.category, category)

    # Exposure signals (E6): band on the RATE, not the count. A vendor with 9 abandoned hosts out
    # of 900 and one with 9 out of 20 are not running the same estate, and until this branch
    # existed the model could not tell them apart — it charged the second less, because a raw
    # count of 9 is a raw count of 9.
    spec = cfg.exposure_spec(finding.signal)
    if spec is not None:
        failures = _count_of(finding)
        denominator = _denominator_for(finding, cfg, denominators)
        if failures is None or denominator is None:
            # No usable pair. Fall back to the count bands rather than inventing a rate — a
            # denominator we could not observe must not be guessed at, and a signal that silently
            # scored on an assumed estate size would be indefensible in a dispute.
            band_key = cfg.count_band(finding.signal, failures) if failures is not None else None
            if band_key is None:
                return make("informational", band_key=str(failures),
                            note="exposure signal without a usable count and denominator")
        else:
            exposure_result = exposure.evaluate(failures, denominator, spec)
            band_key = exposure_result.band
    # Count signals: bucket the raw count into a band first, then look up its severity.
    # `exposure_signals()` is included and is NOT gated on `enabled` — that is what makes
    # `exposure.enabled: false` a true revert. Without it, switching the feature off would send
    # stale_hosts to the plain-band path, where its observed string ("13 stale/dev/staging names")
    # matches no band and the signal would quietly stop scoring instead of returning to E5.
    elif finding.signal in _COUNT_SIGNALS or finding.signal in cfg.exposure_signals():
        n = _count_of(finding)
        band_key = cfg.count_band(finding.signal, n) if n is not None else None
        if band_key is None:
            return make("informational", band_key=str(n), note="count signal without a usable count")
    else:
        band_key = _band_key(finding)

    severity = cfg.signal_severity(category, finding.signal, band_key)
    if severity is None:
        # A band the model doesn't list — record it as evidence (coverage) but don't invent a
        # penalty. Keeps an unexpected collector value from silently scoring.
        return make("informational", band_key=band_key,
                    note=f"unmapped band {band_key!r} — treated as informational")

    # The ceiling arms off the BASE severity, deliberately. It is a non-compensatory response to a
    # directly-OBSERVED current critical; a sector promotion is a policy judgement about how much
    # an observation matters, not a new observation. Letting a config edit cap a vendor's grade at
    # D would make the knockout an opinion.
    # E12 interaction, enforced now so the fan-out cannot silently widen it. Today every collector
    # probes the apex once and `ceiling_scope_satisfied` is trivially true; once `cert_validity`
    # becomes a per-host rate, only the APEX host may arm the knockout. See
    # `ScoringConfig.ceiling_scope_satisfied` for why any-host and rate-threshold are both wrong.
    is_critical = (severity == "critical"
                   and finding.signal in cfg.ceiling_auto_signals()
                   and cfg.ceiling_scope_satisfied(finding.signal, finding.value))
    return make(severity, is_critical=is_critical, band_key=band_key)
