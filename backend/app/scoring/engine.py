"""Scoring engine — penalty-based POSTURE model (methodology §5).

Pipeline order (scoring.yaml / §5.1):
    normalize (observation -> severity -> penalty) -> modifiers (age x frequency x mitigation)
    -> collapse each (category, signal) to its worst member -> sum penalties per category &
    overall -> GATE (block) -> posture = 100 - penalties -> CRITICAL CEILING
    -> grade + confidence (coverage)

The rules that keep it honest, enforced in the arithmetic:
  * **Every vendor starts at 100.** Each issue found SUBTRACTS a penalty sized by severity.
    A CATEGORY's posture is 100 minus its own penalties; the OVERALL posture is the mean of the
    covered category postures (a plain average, not a running sum — on a 0-100 scale summing
    every penalty would tank a merely-mediocre vendor to F).
    * **Missing data reduces CONFIDENCE, never posture.** Confidence is coverage-first (how many
        planned signals returned data), with an optional bounded assurance multiplier from
        entity maturity. An absent category lowers coverage, not the posture. A clean-LOOKING
        vendor we can't stand behind is refused as a Ghost, not published.
  * **Gates emit nothing; the ceiling caps, never sets.** A sanctions hit or ambiguous entity
    BLOCKS before scoring (no posture). A directly-observed current critical (an expired
    production cert) caps the posture so it can't be averaged away (the knockout, re-expressed).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from ..logging_config import get_logger
from ..models import CategoryScore, CollectorResult, Score, Vendor
from ..scoring_config import ScoringConfig, get_scoring_config
from .log_odds import NO_PEERS, PeerContext, shrink
from . import modifiers
from .normalize import NormalizedFinding, normalize_one

log = get_logger("scoring.engine")

# Which signals skip frequency amplification now lives in scoring.yaml
# (modifiers.frequency.exempt_signals), not here — the model must be arguable without a redeploy.


@dataclass
class ScoreResult:
    """Full, auditable result: the published Score plus the normalized findings behind it."""

    score: Score
    normalized: list[NormalizedFinding]


class ScoringEngine:
    def __init__(self, cfg: ScoringConfig | None = None) -> None:
        self.cfg = cfg or get_scoring_config()

    def score(
        self, vendor: Vendor, results: list[CollectorResult],
        evidence_ids: dict[str, str] | None = None, now: datetime | None = None,
        sector: str | None = None,
        disputes: dict[tuple[str, str], str] | None = None,
        peers: PeerContext | None = None,
    ) -> ScoreResult:
        """Score a vendor. `now` fixes the clock age decay is measured against — pass it to make a
        run reproducible (the regression corpus does; production leaves it None for wall-clock).

        `sector` IS ACCEPTED AND IGNORED (E1). It was the one piece of vendor context permitted to
        reach the arithmetic, promoting a severity by one step where scoring.yaml cited a named
        instrument. That is dynamic severity adjustment, and it made the same evidence score
        differently depending on a label we assigned — so NO vendor context now reaches the
        arithmetic at all. Revenue, headcount, country and ownership were already out under §7.3;
        sector has now joined them. `test_sector_never_changes_a_severity` asserts this.

        Sector still does real work, in two places that are not the arithmetic: it selects the peer
        cohort, and it selects the frameworks a vendor is measured against in the Compliance Gap.

        `disputes` maps `(signal, band_key)` -> 'nullify' | 'mitigate' for ACCEPTED refutes. A
        nullify zeroes the penalty (the finding does not apply here); a mitigate sets the NIST
        mitigation flag (×0.6). Both are recorded on the finding, so a discounted deduction shows
        why. A dispute only matches while that exact observation persists, so it self-expires.

        `peers` is E13's `L_peer`, and it reaches ONLY the side-by-side preview — never the
        published posture. Omitting it means `NO_PEERS`, which is the shipped default and produces
        the same stated refusal as before. The CALLER supplies the cohort because the engine has no
        store and must not grow one: a scoring engine that can query a population is one whose
        output depends on who else happens to have been assessed, and "missing data never changes
        posture" is only checkable while that stays false.
        """
        evidence_ids = evidence_ids or {}
        disputes = disputes or {}
        peers = peers or NO_PEERS

        # --- GATE 1: ambiguous entity — never score the wrong company ---
        if vendor.resolution_confidence is not None and (
            vendor.resolution_confidence < self.cfg.entity_block_below()
        ):
            reason = (f"entity ambiguous (resolution confidence "
                      f"{vendor.resolution_confidence:.2f} < {self.cfg.entity_block_below()})")
            if vendor.resolution_basis:
                # A blocked record goes to a human. It must arrive saying WHY, in words.
                reason = f"{reason}: {vendor.resolution_basis}"
            return self._blocked(vendor, reason)

        # --- E6: resolve denominators BEFORE normalising ---
        # A rate needs both numbers, and they arrive as two separate findings from the same
        # collector. `normalize_one` sees one finding at a time, so the pairing has to happen here,
        # where the whole collection run is in scope. Built from raw counts across every result so
        # a denominator emitted by one source can serve a numerator emitted by another.
        denominators: dict[str, int] = {}
        for r in results:
            for f in r.findings:
                if isinstance(f.value, dict) and "count" in f.value:
                    try:
                        denominators[f.signal] = int(f.value["count"])
                    except (TypeError, ValueError):
                        continue

        # --- normalize every finding, applying any ACCEPTED refute to the matching observation ---
        normalized: list[NormalizedFinding] = []
        for r in results:
            ev = evidence_ids.get(r.source)
            for f in r.findings:
                nf = normalize_one(f, self.cfg, ev, sector=sector, denominators=denominators)
                if nf is None:
                    continue
                self._apply_dispute(nf, disputes)
                normalized.append(nf)

        # --- GATE 2: sanctions hit -> BLOCKED, no score (Finding B) ---
        sanctions = [n for n in normalized if n.is_sanctions]
        if sanctions:
            names = ", ".join(sorted({n.observed for n in sanctions})[:3])
            return self._blocked(vendor, f"sanctions screen hit — adjudication required: {names}",
                                 normalized=normalized)

        # --- GATE 3: config-driven finding gates (E8) ---
        # A gate is NOT a low score. It emits no posture and no grade and routes to a human,
        # because the failure this prevents is arithmetic: a vendor with a disqualifying finding
        # publishing 60 clears a ">= 50" procurement threshold and gets onboarded by a rule nobody
        # re-read. Generalised from the two inline branches above so that adding a gate is a config
        # edit carrying a stated basis, reviewable as the policy decision it is.
        for name, spec in self.cfg.finding_gates():
            hit = next(
                (n for n in normalized
                 if self.cfg.gate_matches(spec, n.signal, n.band_key, n.value_snapshot, now)),
                None,
            )
            if hit is not None:
                return self._blocked(
                    vendor,
                    f"{name} — adjudication required: {hit.signal}={hit.observed}. "
                    f"{self.cfg.gate_basis(name)}",
                    normalized=normalized,
                )

        scored = [n for n in normalized if not n.is_sanctions]
        mods = self.cfg.modifiers()

        # --- penalties per category (decay applied per finding; worst-of for CVE bags) ---
        by_cat_sig: dict[tuple[str, str], list[NormalizedFinding]] = defaultdict(list)
        for n in scored:
            by_cat_sig[(n.category, n.signal)].append(n)

        freq_exempt = self.cfg.frequency_exempt_signals()
        freq_cfg = mods.get("frequency", {})
        never_decays = self.cfg.never_decays_signals()

        cat_penalty: dict[str, float] = defaultdict(float)
        cat_findings: dict[str, list[str]] = defaultdict(list)   # evidence ids of issues
        cat_issue_count: dict[str, int] = defaultdict(int)
        ceiling_causes: list[str] = []
        # E7a. Diminishing returns needs ALL of a category's penalties before it can rank them, so
        # the loop can no longer accumulate as it goes: it collects (penalty, representative) pairs
        # per category and the transform runs after the loop closes.
        collected: dict[str, list[tuple[float, NormalizedFinding]]] = defaultdict(list)
        for (cat, sig), items in by_cat_sig.items():
            # A current-state signal's event_date is a boundary, not an occurrence — pass None so
            # age leaves it alone (an expired cert does not soften with age; it worsens).
            effective = [
                (modifiers.apply(
                    it.penalty,
                    event_date=None if sig in never_decays else it.event_date,
                    n_events=1, mitigated=it.remediation_evidenced, now=now, config=mods), it)
                for it in items
            ]
            # Every (category, signal) group contributes ONE penalty — its worst decayed member.
            # Recurrence is then expressed exactly once, by the NIST frequency factor, instead of
            # by summing duplicates: three breaches are a pattern (x1.5), not one breach x3.
            # Note the representative is the worst AFTER decay, so a fresh High can outrank a
            # long-decayed Critical — the score-driving finding, not the highest raw band.
            penalty, rep = max(effective, key=lambda p: p[0])
            if penalty > 0 and sig not in freq_exempt:
                penalty *= modifiers.frequency_factor(
                    len(items),
                    increment=float(freq_cfg.get("increment", modifiers.DEFAULT_FREQ_INCREMENT)),
                    cap=float(freq_cfg.get("cap", modifiers.DEFAULT_FREQ_CAP)),
                )
            collected[cat].append((penalty, rep))
            rep.occurrences = len(items)

            # Bookkeeping spans the WHOLE group, not just the representative: every covered
            # finding's receipt is cited (a clean 'pass' proves "checked & clean"), every issue
            # is counted, and any critical arms the ceiling even if it wasn't the worst after decay.
            for pen, it in effective:
                if it.evidence_id and it.evidence_id not in cat_findings[cat]:
                    cat_findings[cat].append(it.evidence_id)
                if pen > 0:
                    cat_issue_count[cat] += 1
                if it.is_critical:
                    ceiling_causes.append(f"{it.signal}={it.observed}")

        # --- E7c: root-cause deduplication, BEFORE ranking ---
        # One remediation ticket, one penalty. A vendor who patches a KEV-listed CVE fixes the NVD
        # finding in the same action; charging both makes the model's arithmetic disagree with the
        # vendor's work plan. Suppression zeroes the PENALTY and never the EVIDENCE — the finding
        # stays on the record, marked, because "we saw this and did not charge for it" is a
        # different statement from "we did not see it".
        #
        # Runs before the aggregation transform on purpose: a suppressed penalty must not occupy a
        # rank. If it did, the discount ladder would be shifted down by findings charging nothing,
        # and a vendor could dilute their real penalties by accumulating duplicates.
        charged_signals = {
            cat: {rep.signal for pen, rep in rows if pen > 0} for cat, rows in collected.items()
        }
        for cat, rows in collected.items():
            deduped: list[tuple[float, NormalizedFinding]] = []
            for penalty, rep in rows:
                suppressor = self.cfg.root_cause_suppressor(
                    rep.signal, charged_signals.get(cat, set()),
                    {r.signal: r.band_key for _p, r in rows},
                )
                if penalty > 0 and suppressor is not None:
                    rep.suppressed_by = suppressor
                    penalty = 0.0
                deduped.append((penalty, rep))
            collected[cat] = deduped

        # --- E7a: diminishing returns within a category ---
        #     CategoryPenalty(c) = SUM_i p_i * lambda^(rank_i - 1),  rank by descending p_i
        #
        # The defect: twelve missing HTTP headers (12 x 3 = 36, or 56 with a few mediums) outranked
        # one actively-exploited KEV (40). A security team reading that is being told trivia matters
        # more than the thing attackers are using today, and no amount of per-finding explanation
        # repairs it — the arithmetic itself is making the claim.
        #
        # Ships WITH the widened ladder (E7b) because neither half reaches the target alone:
        #     flat ladder, no discount  -> 0.71 : 1   trivia wins
        #     discount only             -> 1.78 : 1
        #     ladder only               -> 1.39 : 1
        #     both                      -> 3.06 : 1   which is the point
        for cat, rows in collected.items():
            total = 0.0
            for rank, (penalty, rep) in enumerate(
                    sorted(rows, key=lambda p: p[0], reverse=True), start=1):
                discounted = penalty * (self.cfg.aggregation_decay() ** (rank - 1)) \
                    if penalty > 0 else 0.0
                # POST-discount, deliberately. `effective_penalty` exists so the stored receipts
                # reconstruct the published score; writing the pre-discount value here would make
                # the category's findings visibly fail to add up to the category's penalty, which
                # is the exact defect this field was added to prevent.
                rep.effective_penalty = discounted
                rep.aggregation_rank = rank if penalty > 0 else None
                total += discounted
            cat_penalty[cat] = total

        # --- coverage (confidence axis): planned vs covered signals ---
        # Business Stability signals are excluded on both sides of this ratio, not just the
        # denominator (scoring_config.business_stability_signals) — they DO reach `scored` (they
        # score, at `informational`), so leaving them in the numerator alone would let a fully
        # historically-covered vendor exceed 100% coverage the moment all three answer.
        covered_by_cat: dict[str, set[str]] = defaultdict(set)
        for n in scored:
            if n.signal in self.cfg.business_stability_signals():
                continue
            covered_by_cat[n.category].add(n.signal)
        total_covered = sum(len(s) for s in covered_by_cat.values())
        total_planned = self.cfg.planned_signal_count()
        base_coverage = (total_covered / total_planned) if total_planned else 0.0

        # Assurance adjustment (bounded): entity maturity can nudge confidence without touching
        # posture arithmetic. This keeps age from becoming "free security points" while still
        # reflecting operational-history uncertainty on the assurance axis.
        confidence = self._apply_assurance_multiplier(base_coverage, scored)
        confidence_band = self.cfg.confidence_band(confidence)

        # --- posture: 100 - total penalty / a FIXED divisor. Not a running sum (on a 0-100 scale
        # that tanks a merely-mediocre vendor to F), and NOT a mean over the categories that
        # happened to answer — that let a clean trust page buy +23 posture, because each clean
        # category entered the average as a 100 and pulled it up.
        # Each category's damage is capped at its own 100 first (one catastrophic category cannot
        # dominate without bound), then divided by a divisor FIXED BY THE MODEL — never by how many
        # categories happened to answer. That fixed divisor is the whole point: a silent source
        # contributes no penalty and cannot move the denominator, so coverage cannot leak into
        # posture and "missing data never changes posture" holds as arithmetic, not as a promise.
        # With every category covered this is algebraically the old mean (mean(100-p) = 100-Sum(p)/n);
        # the divisor is tunable because a plain /7 is very forgiving of concentrated failure.
        capped = {cat: min(p, float(self.cfg.max_score)) for cat, p in cat_penalty.items()}
        posture = max(0.0, self.cfg.max_score - sum(capped.values()) / self.cfg.penalty_divisor())

        # --- E13: the SIDE-BY-SIDE preview of the bounded log-odds transform ---
        #
        # `max(0.0, ...)` above is the defect E13 exists to fix: a vendor at three times the cap
        # and one at six times both publish 0, so the model cannot order the worst suppliers in a
        # book — which is exactly where triage matters. E7 made it worse before it makes it better
        # (diminishing returns moved `synthetic_floor` 16 -> 39).
        #
        # PUBLISHED ALONGSIDE, NEVER INSTEAD. The plan calls E13 a second release: it changes what
        # the number MEANS, so it needs a version bump, a notice period and side-by-side
        # publication. Shipping it as a preview field is what makes that notice period possible —
        # a client can see both numbers for a release before either moves.
        #
        # It refuses whenever `L_peer` would come from fewer than eight real peers, and the refusal
        # is the correct behaviour rather than a limitation: shrinking an under-evidenced vendor
        # toward six invented postures is worse than not shrinking at all.
        #
        # THE ARGUMENT IS NOW REAL RATHER THAN PROMISED. Until this change the engine inlined
        # `peers_are_synthetic=True` as a literal and nothing in the codebase computed a peer
        # penalty rate — so "when the pool is real this becomes a one-line switch" described a line
        # that did not exist. `peers` is that line. It defaults to `NO_PEERS`, which reproduces the
        # old literals exactly, and the pipeline fills it from the vendor's cohort when there is
        # one. On a seeded pool the preview starts publishing on its own, WITHOUT a code change —
        # which is the only version of that claim anyone can check.
        penalty_fraction = min(1.0, sum(capped.values())
                               / (self.cfg.max_score * self.cfg.penalty_divisor()))
        log_odds_preview = shrink(peers.as_shrinkage(
            penalty_fraction=penalty_fraction, confidence=confidence))

        # --- CRITICAL CEILING (knockout): a directly-observed current critical caps posture ---
        ceiling_applied = False
        ceiling_cause = None
        if ceiling_causes:
            ceil = self.cfg.ceiling_score()
            if posture > ceil:
                posture = ceil
                ceiling_applied = True
            ceiling_cause = "; ".join(dict.fromkeys(ceiling_causes))  # dedupe, keep order

        # --- E7d: CONFIDENCE CEILING RAMP. Thin evidence caps how good a vendor may LOOK. ---
        # Before E7d this was a single cliff at 40%: below it nothing published, above it a vendor
        # seen through four collectors could publish 100 and read exactly like one seen through
        # fourteen. Everything between "refuse" and "full marks" was flat, so the cheapest way to a
        # high score was to be hard to observe.
        #
        # A cap, never a deduction. It does not touch `cat_penalty`, so the honesty rule holds
        # unchanged — missing data still costs no posture; it only limits the CLAIM we are willing
        # to publish on the evidence we have. The vendor's findings are what they are; our
        # confidence in the ceiling above them is what coverage buys.
        conf_ceiling = self.cfg.confidence_ceiling(confidence)
        confidence_ceiling_applied = False
        if conf_ceiling is not None and posture > conf_ceiling:
            posture = conf_ceiling
            confidence_ceiling_applied = True

        posture_int = int(round(posture))

        # --- refusal: the GHOST. A clean-LOOKING vendor we can't stand behind (thin coverage)
        # is not published. A fired ceiling bypasses refusal — a directly-observed critical is
        # certain even under thin coverage. ---
        if confidence < self.cfg.refuse_below() and not ceiling_applied:
            return self._refused(vendor, confidence, confidence_band, normalized,
                                 cat_penalty, covered_by_cat, cat_findings, cat_issue_count)

        categories = self._category_models(cat_penalty, covered_by_cat, cat_findings, cat_issue_count)
        ghost = confidence_band == "Low"
        score = Score(
            vendor_ref=vendor.ref, blocked=False,
            posture=posture_int, grade=self.cfg.grade_for(posture_int),
            overall_confidence=round(confidence, 3), confidence_band=confidence_band,
            refused=False, ghost=ghost,
            critical_ceiling_applied=ceiling_applied, ceiling_cause=ceiling_cause,
            confidence_ceiling_applied=confidence_ceiling_applied,
            confidence_ceiling=conf_ceiling,
            log_odds_preview=(round(log_odds_preview.posture, 1)
                              if log_odds_preview.published else None),
            # When it refuses, the unmet precondition. When it publishes, WHERE L_peer came from —
            # a number shrunk toward an unnamed target cannot be reviewed, and the whole reason the
            # preview ships early is so it can be argued with before it means anything.
            log_odds_reason=log_odds_preview.reason or (peers.basis or None),
            categories=categories,
            # Always None since E1 — no sector rule can fire, so the card must never imply one did.
            # The field is retained for one release so stored Scores still deserialise.
            industry_profile=None,
        )
        return ScoreResult(score=score, normalized=normalized)

    def _apply_assurance_multiplier(
        self,
        coverage: float,
        findings: list[NormalizedFinding],
    ) -> float:
        """Apply confidence multiplier from the configured assurance signal, if observed.

        If multiple maturity observations exist, use the MOST CONSERVATIVE multiplier (lowest)
        so conflicting evidence cannot inflate assurance. That rule does real work now that sources
        are weighted: a vendor with a 2015 Wikidata inception and a 1998 domain registration takes
        the reading from the inception date, so an old domain in front of a young company cannot
        buy assurance the company has not earned.

        Per finding, the CONTINUOUS curve is preferred and the stepped band table is the fallback.
        Mixing the two across findings is intentional and safe — both produce a multiplier in the
        same bounded range, and taking the minimum across them stays conservative either way.
        """
        signal = self.cfg.confidence_assurance_signal()
        if not signal:
            return coverage
        multipliers: list[float] = []
        for n in findings:
            if n.signal != signal:
                continue
            # Explicit None check, not `or`: a curve legitimately configured with a 0.0 floor
            # would be falsy, and would silently fall through to the band table.
            continuous = self.cfg.confidence_multiplier_for_index(n.assurance_index)
            multipliers.append(
                continuous if continuous is not None
                else self.cfg.confidence_multiplier_for_band(n.band_key)
            )
        if not multipliers:
            return coverage
        return max(0.0, min(1.0, coverage * min(multipliers)))

    @staticmethod
    def _apply_dispute(nf: NormalizedFinding, disputes: dict[tuple[str, str], str]) -> None:
        """Apply an accepted refute to one finding, if it targets this exact observation.

        A dispute never touches sanctions (the gate is human by law, not by refute) and never
        touches a passing band (nothing to discount). Otherwise:
          * nullify — the finding does not apply here (attribution error / compensating control).
            Penalty and criticality go to zero; it stays in the record as evidence, marked.
          * mitigate — real but evidenced-remediated. Set the NIST mitigation flag; the engine's
            existing modifier applies the ×0.6, so a fix is discounted once, in one place.
        """
        if nf.is_sanctions or not nf.penalty:
            return
        kind = disputes.get((nf.signal, nf.band_key))
        if kind == "nullify":
            nf.penalty = 0.0
            nf.is_critical = False
            nf.dispute = "nullified"
        elif kind == "mitigate":
            nf.remediation_evidenced = True
            nf.dispute = "mitigated"

    # ------------------------------------------------------------------ breakdown

    def _category_models(
        self, cat_penalty: dict[str, float], covered_by_cat: dict[str, set[str]],
        cat_findings: dict[str, list[str]], cat_issue_count: dict[str, int],
    ) -> list[CategoryScore]:
        out: list[CategoryScore] = []
        unreachable = self.cfg.unreachable_signals()
        business_stability = self.cfg.business_stability_signals()
        for cat in self.cfg.category_names():
            # PLANNED means "this deployment intends to collect it", not "the model defines it" —
            # the same rule `planned_signal_count` applies to the overall denominator, and it has
            # to be applied here too or the two coverage figures disagree. E12 is the case that
            # forced it: `estate_*` signals are declared in the model but unproducible at
            # `probe_cap: 1`, and counting them dropped every vendor's attack-surface coverage
            # from 12/12 to 10/12 for a feature nobody had switched on. Business Stability signals
            # are excluded the same way, for the same reason `covered_by_cat` excludes them above:
            # they are reachable, but belong to a different axis with its own coverage figure
            # (`continuity.business_stability_coverage`), never this one.
            planned = len([s for s in self.cfg.signals_of(cat)
                          if s not in unreachable and s not in business_stability])
            covered = len(covered_by_cat.get(cat, set()))
            coverage = (covered / planned) if planned else 0.0
            if covered == 0:
                out.append(CategoryScore(category=cat, posture=None, grade=None, penalty=0.0,
                                         coverage=0.0, findings=0, contributing_finding_ids=[]))
                continue
            penalty = cat_penalty.get(cat, 0.0)
            posture = int(round(max(0.0, self.cfg.max_score - penalty)))
            out.append(CategoryScore(
                category=cat, posture=posture, grade=self.cfg.grade_for(posture),
                penalty=round(penalty, 2), coverage=round(coverage, 3),
                findings=cat_issue_count.get(cat, 0),
                contributing_finding_ids=cat_findings.get(cat, []),
            ))
        return out

    # ------------------------------------------------------------------ terminal states

    def _blocked(self, vendor: Vendor, reason: str,
                 normalized: list[NormalizedFinding] | None = None) -> ScoreResult:
        score = Score(vendor_ref=vendor.ref, blocked=True, blocked_reason=reason,
                      posture=None, grade=None, overall_confidence=0.0, confidence_band="Low")
        return ScoreResult(score=score, normalized=normalized or [])

    def _refused(
        self, vendor: Vendor, confidence: float, band: str, normalized: list[NormalizedFinding],
        cat_penalty: dict[str, float], covered_by_cat: dict[str, set[str]],
        cat_findings: dict[str, list[str]], cat_issue_count: dict[str, int],
    ) -> ScoreResult:
        categories = self._category_models(cat_penalty, covered_by_cat, cat_findings, cat_issue_count)
        score = Score(
            vendor_ref=vendor.ref, blocked=False, posture=None, grade=None,
            overall_confidence=round(confidence, 3), confidence_band=band,
            refused=True, ghost=True, categories=categories,
        )
        return ScoreResult(score=score, normalized=normalized)
