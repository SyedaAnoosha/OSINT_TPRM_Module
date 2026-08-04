"""E12 — is the fan-out worth switching on, and at what cap? Measured, not asserted.

WHY THIS IS AN INSTRUMENT AND NOT A NUMBER IN A COMMIT MESSAGE. `estate.probe_cap` has shipped at
`1` since E12 was built, described as *"a capacity and resourcing decision rather than a technical
design problem"*. That framing is only half right, and the missing half is measurable: the fan-out's
input is certificate transparency, and **CT availability is not a constant**. crt.sh returns 404s
under load and Certspotter rate-limits keyless clients at 429. A cap raised on a day when CT is
answering looks free; the same cap on a day it is not costs every vendor confidence and returns
nothing.

So the cap is chosen from what the book actually contains, and this module is how that is re-checked
rather than remembered.

═══ THE COST OF SWITCHING ON, STATED PLAINLY ═══

At `probe_cap: 1` the two `estate_*` signals are **unreachable** — no collector can emit them — and
`scoring_config.unreachable_signals()` takes them out of the coverage denominator. That is correct:
absent evidence lowers confidence, unproducible evidence must not.

Above 1 they become reachable, so they re-enter the denominator **for every vendor**, including the
ones whose CT lookup returned nothing. Those vendors' confidence falls.

**THAT FALL IS THE SYSTEM TELLING THE TRUTH AND MUST NOT BE ENGINEERED AWAY.** Once the feature is
switched on, we DID intend to look at the estate and DID fail to; that is a genuine coverage gap and
the confidence axis exists to show exactly that. The tempting fix — rebase the denominator per
vendor so each is measured only against what its own sources could produce — is the move
`assessment_depth.py` already refuses in writing for P5's depths: it would make `0.8` mean "most of
the model" on one vendor and "most of whatever answered" on the next, in the same column.

So the honest question is not *"how do we switch this on for free"* — there is no free — but
*"does the estate rate buy more than the confidence it costs"*, and that is answerable from the
book.

USAGE
    python -m app.estate_readiness              # the measurement, and what it implies for the cap
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from .scoring_config import get_scoring_config

#: Below this share of the book carrying a usable estate, switching on costs more confidence than
#: it buys signal. Written down so the decision is arguable rather than a feeling — and so that a
#: later run against a better CT day can be compared with this one.
#:
#: HALF is not arbitrary: below it, the MAJORITY of the book pays confidence for a signal it cannot
#: produce, and a metric that penalises most of its population for a source's availability is
#: measuring the source, not the vendors. It is the same objection `stale_hosts` banding on raw
#: counts ran into — a penalty nobody escapes ranks nobody.
READINESS_THRESHOLD = 0.50

#: The rate a single probed host can express. A denominator of 10 means one bad host reads as 10%,
#: which is a coarse rate to publish against a real estate; 25 gives 4% resolution and matches the
#: order of `estate.tenant_sibling_threshold`, which is the other place this model decides how many
#: names constitute a namespace rather than a team.
SUGGESTED_CAP = 25


@dataclass
class EstateReadiness:
    vendors: int
    with_ct_row: int
    with_usable_estate: int
    estate_sizes: list[int] = field(default_factory=list)
    by_source: dict[str, int] = field(default_factory=dict)
    #: Relationships specifically. The book-wide figure is dominated by the 114-vendor seeded
    #: corpus, and a feature can be worth switching on for the vendors somebody actually buys from
    #: even when the corpus drags the average down — so the two are counted separately rather than
    #: averaged into one misleading number.
    relationships: int = 0
    relationships_with_estate: int = 0
    #: THE HARD STOP. Vendors currently publishing a posture whose confidence would fall BELOW the
    #: ghost floor once the two estate signals re-enter their denominator. These do not degrade
    #: gracefully — they stop publishing a posture at all.
    would_go_dark: list[str] = field(default_factory=list)

    @property
    def availability(self) -> float:
        return (self.with_usable_estate / self.vendors) if self.vendors else 0.0

    @property
    def relationship_availability(self) -> float:
        return ((self.relationships_with_estate / self.relationships)
                if self.relationships else 0.0)

    @property
    def ready(self) -> bool:
        """Two conditions, and the second is non-compensatory.

        Enough of the book must be able to produce the signal, AND no vendor that currently
        publishes a posture may stop publishing one because of the switch. The second is not a
        threshold to be traded against the first: a vendor going dark is not a degraded number, it
        is the disappearance of the number, and no amount of estate coverage elsewhere compensates
        a buyer for losing the posture of a vendor they are actually using.
        """
        return self.availability >= READINESS_THRESHOLD and not self.would_go_dark

    @property
    def median_estate(self) -> float | None:
        return statistics.median(self.estate_sizes) if self.estate_sizes else None

    def probes_per_sweep(self, cap: int) -> int:
        """Upper bound on TLS handshakes a full-book sweep would make at this cap.

        Two handshakes per host — one to test whether legacy protocol versions are offered, one for
        the certificate — and only vendors with an estate probe at all. This is the politeness
        budget `_validate_estate` refuses to let anyone raise by accident.
        """
        return 2 * sum(min(cap, n) for n in self.estate_sizes)

    def verdict(self) -> str:
        pct = f"{self.availability:.0%}"
        if self.would_go_dark:
            return (
                f"DO NOT SWITCH ON. {len(self.would_go_dark)} vendors that publish a posture today "
                f"would fall below the ghost floor and publish NOTHING: "
                f"{', '.join(self.would_go_dark)}. Adding two unfillable signals to their "
                f"denominator is what does it. This is not a trade against the estate rate's "
                f"value — a vendor going dark is the loss of the number, not a worse number — and "
                f"it is the failure that would be discovered by a buyer, not by us. "
                f"(Book-wide estate availability is {pct}; relationships "
                f"{self.relationship_availability:.0%}.)"
            )
        if self.ready:
            return (
                f"READY. {self.with_usable_estate} of {self.vendors} vendors ({pct}) carry a "
                f"usable estate, at or above the {READINESS_THRESHOLD:.0%} threshold. Raising "
                f"`estate.probe_cap` above 1 buys a rate for the majority of the book, and the "
                f"minority that cannot produce one will show a genuine coverage gap — which is "
                f"what the confidence axis is for."
            )
        return (
            f"NOT READY, AND THE BLOCKER IS NOT CAPACITY. Only {self.with_usable_estate} of "
            f"{self.vendors} vendors ({pct}) carry a usable estate — below the "
            f"{READINESS_THRESHOLD:.0%} threshold — because certificate transparency is not "
            f"answering: crt.sh returns 404 under load and Certspotter rate-limits keyless "
            f"clients at 429. Raising the cap today would re-enter both `estate_*` signals into "
            f"every vendor's coverage denominator while at most {pct} of them could ever fill it, "
            f"so the majority of the book would lose confidence to a feature it cannot "
            f"participate in. THE UNBLOCKER IS A CERTSPOTTER API KEY, not a bigger cap."
        )


def measure(store: Any) -> EstateReadiness:
    """What the book can actually support, read from the CT evidence already collected.

    Reads stored evidence rather than re-querying: the question is what the last real run of each
    collector returned, and asking CT 146 more times to find out whether CT is rate-limiting us
    would be a strange way to answer it.
    """
    from .inherent_register import relationships as register_relationships

    cfg = get_scoring_config()
    scores = list(store.latest_scores_all())
    refs = [s.vendor_ref for s in scores]
    rel_refs = {e.ref for e in register_relationships()}
    out = EstateReadiness(vendors=len(refs), with_ct_row=0, with_usable_estate=0)

    # How much confidence the switch costs: two signals re-entering a denominator that currently
    # excludes them. Computed from the config rather than hardcoded, so a model that adds a third
    # estate signal changes this projection automatically.
    estate_signals = {s for s in cfg.unreachable_signals() if s.startswith("estate_")}
    planned_after = cfg.planned_signal_count() + len(estate_signals)
    floor = cfg.refuse_below() if hasattr(cfg, "refuse_below") else 0.0

    has_estate: set[str] = set()
    for ref in refs:
        rows = [e for e in store.for_vendor(ref) if e.source == "ct"]
        if not rows:
            continue
        out.with_ct_row += 1
        rows.sort(key=lambda e: e.fetched_at, reverse=True)
        raw = rows[0].raw or {}
        n = raw.get("unique_subdomains")
        if not isinstance(n, int) or n <= 1:
            # A vendor with one name has no estate to sample — probing it is the apex again, and
            # a rate of "0 of 1" is not a rate.
            continue
        has_estate.add(ref)
        out.with_usable_estate += 1
        out.estate_sizes.append(n)
        src = raw.get("ct_source") or "unknown"
        out.by_source[src] = out.by_source.get(src, 0) + 1

    out.relationships = sum(1 for r in refs if r in rel_refs)
    out.relationships_with_estate = len(has_estate & rel_refs)

    for score in scores:
        if score.blocked or score.refused or score.overall_confidence is None:
            continue
        # A vendor WITH an estate gains the two signals as covered as well as planned, so its ratio
        # barely moves. A vendor without one gains them as planned only — that is the fall.
        covered = score.overall_confidence * (planned_after - len(estate_signals))
        projected = covered / planned_after if planned_after else 0.0
        if score.vendor_ref in has_estate:
            projected = (covered + len(estate_signals)) / planned_after
        if score.overall_confidence >= floor > projected:
            out.would_go_dark.append(score.vendor_ref)
    out.would_go_dark.sort()
    return out


def as_dict(r: EstateReadiness) -> dict[str, Any]:
    cfg = get_scoring_config()
    cap_now = cfg.estate_probe_cap()
    return {
        "current_probe_cap": cap_now,
        "fan_out_active": cap_now > 1,
        "vendors": r.vendors,
        "with_ct_row": r.with_ct_row,
        "with_usable_estate": r.with_usable_estate,
        "availability": round(r.availability, 3),
        "relationships": r.relationships,
        "relationships_with_estate": r.relationships_with_estate,
        "relationship_availability": round(r.relationship_availability, 3),
        "threshold": READINESS_THRESHOLD,
        "ready": r.ready,
        "would_go_dark": r.would_go_dark,
        "verdict": r.verdict(),
        "estate_size": {
            "median": r.median_estate,
            "mean": round(statistics.mean(r.estate_sizes), 1) if r.estate_sizes else None,
            "max": max(r.estate_sizes) if r.estate_sizes else None,
        },
        "ct_sources": r.by_source,
        "probe_budget": {
            str(cap): r.probes_per_sweep(cap) for cap in (5, 10, 25, 50, 100)
        },
        "suggested_cap_when_ready": SUGGESTED_CAP,
        "coverage_cost_of_switching_on": (
            f"Both `estate_*` signals re-enter the coverage denominator for ALL {r.vendors} "
            f"vendors, while only {r.with_usable_estate} can fill them. The other "
            f"{r.vendors - r.with_usable_estate} lose the two signals' worth of confidence. That "
            f"is not a bug to engineer around: once the feature is on, those vendors genuinely "
            f"have an estate nobody looked at. Rebasing the denominator per vendor to hide it is "
            f"the move P5 refuses for assessment depth, and for the same reason."
        ),
    }


def main() -> None:
    import json

    from .logging_config import setup_logging
    from .storage import get_store

    setup_logging()
    body = as_dict(measure(get_store()))
    print(json.dumps(body, indent=2, default=str))


if __name__ == "__main__":
    main()
