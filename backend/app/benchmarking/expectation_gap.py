"""E10a — the Expectation Gap, and what is driving it.

    EG = Posture − E[Posture | cohort]

THE SENTENCE THIS EXISTS TO PRODUCE, which is the answer to the whole research question:

    "Posture 68. Median for financial services, 1,000-10,000 staff (n=14): 87. This vendor sits
     19 points below its peer group, and the gap is driven by absent DMARC — 12 of its 14 peers
     publish one."

WHY THIS IS NOT JUST `delta_from_median` RENAMED. The signed delta is arithmetically the same
number and it comes from the same estimator on purpose (see below). What E10a owes beyond EB is the
second half of that sentence: WHICH observations account for the gap. A buyer given "-19" has a
fact; a buyer given "-19, driven by DMARC, which 12 of 14 peers publish" has a remediation.

E[·] IS THE COHORT MEDIAN, AND IT IS THE SAME MEDIAN THE PLACEMENT USES. Two reasons, and the
second is the load-bearing one:

  * The mean is destabilised by one extreme member, and at the sample sizes this runs at (n=8-30)
    ONE MEMBER IS A LARGE SHARE OF THE POPULATION. That is the same reasoning the placement module
    gives for using IQR fences rather than standard deviations.
  * It calls `_percentile_value` rather than reimplementing a median, so an expectation quoted here
    and a median quoted in a placement CANNOT DISAGREE. A second definition of the middle of a
    distribution is a second answer to the same question, and the two drift within a release.

THE DRIVERS ARE AN ORDERING, NOT A DECOMPOSITION — and this is the thing most likely to be
misread. Since E7a, penalties within a category are rank-discounted (`λ^(rank−1)`), so the points a
signal cost DEPEND ON WHAT ELSE WAS CHARGED ALONGSIDE IT. Per-signal contributions therefore do not
add up to EG and no arrangement of them can be made to. Presenting them as a decomposition —
"here is where your 19 points went" — would be arithmetically false, so this module ranks them,
publishes the attribution each carries, and says in the caveats that they do not sum.

A SIGNAL EXPLAINS THE GAP ONLY TO THE EXTENT PEERS DO NOT SHARE IT:

    attribution(s) = charged_posture_points(s) × (1 − peer_failure_rate(s))

A vendor failing DMARC in a cohort where every peer also fails DMARC is not behind on DMARC. It
cost them points, but it cost their peers the same points, so it explains none of their POSITION.
This is the discrimination test reached from the other direction, and it agrees with it by
construction — which is why non-discriminating signals are additionally suppressed by name rather
than silently dropped: "every supplier in your cohort fails this" is worth knowing, it is just not
an answer to "why am I behind".
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .config import BenchmarkingConfig, get_benchmarking_config
from .discrimination import _percentile_value, discrimination_report
from .models import PeerRecord

#: Named once so the report, the caveat and any renderer quote the same words. The estimator is
#: part of the claim, not a footnote to it: "19 points below the median" and "19 points below the
#: mean" are different findings and a reader must be able to tell which one they were handed.
_ESTIMATOR = "cohort median (nearest-rank, no interpolation)"


@dataclass(frozen=True)
class GapDriver:
    """One observation, what it cost this vendor, and how much of that their peers also pay."""

    signal: str
    subject_band: str
    peers_observed: int
    peers_sharing_band: int
    charged_posture_points: float
    attribution: float

    @property
    def peer_failure_rate(self) -> float:
        return (self.peers_sharing_band / self.peers_observed) if self.peers_observed else 0.0

    def cited(self) -> str:
        """The published sentence. Leads with the peer fact, because that is the part the vendor
        cannot argue is our opinion — it is a count of their own peer group."""
        clean = self.peers_observed - self.peers_sharing_band
        return (
            f"{self.signal} = {self.subject_band}: {clean} of {self.peers_observed} peers are not "
            f"in this band. Worth {self.attribution:.1f} posture points of the gap."
        )


@dataclass
class ExpectationGapReport:
    """The signed gap, its estimator, and the ranked drivers. Published or refused, never guessed."""

    supplier_ref: str
    posture: int | None
    expected_posture: int | None
    gap: int | None
    n: int
    published: bool
    estimator: str = _ESTIMATOR
    direction: str | None = None            # 'above' | 'at' | 'below'
    drivers: list[GapDriver] = field(default_factory=list)
    suppressed_signals: list[str] = field(default_factory=list)
    reason: str | None = None
    caveats: list[str] = field(default_factory=list)

    def headline(self) -> str | None:
        """The one sentence. None when nothing is published — a caller must not compose its own."""
        if not self.published or self.gap is None:
            return None
        if self.gap == 0:
            return (f"Posture {self.posture}. Cohort median (n={self.n}): {self.expected_posture}. "
                    f"This vendor sits level with its peer group.")
        side = "above" if self.gap > 0 else "below"
        lead = (f"Posture {self.posture}. Cohort median (n={self.n}): {self.expected_posture}. "
                f"This vendor sits {abs(self.gap)} points {side} its peer group.")
        if self.gap < 0 and self.drivers:
            top = self.drivers[0]
            clean = top.peers_observed - top.peers_sharing_band
            lead += (f" The gap is driven by {top.signal} ({top.subject_band}) — "
                     f"{clean} of {top.peers_observed} peers are not in this band.")
        return lead


def expectation_gap(
    supplier_ref: str,
    posture: int | None,
    peers: list[PeerRecord],
    *,
    subject_signals: dict[str, str] | None = None,
    charged_points: dict[str, float] | None = None,
    is_synthetic: bool = False,
    cfg: BenchmarkingConfig | None = None,
    max_drivers: int = 5,
) -> ExpectationGapReport:
    """`Posture − E[Posture | cohort]`, with the observations that account for it.

    `charged_points` is what each signal cost the SUBJECT **in posture points** — that is,
    `effective_penalty / penalty_divisor`, converted by the caller because this package must not
    read `scoring.yaml`. A signal absent from it contributes nothing and is not guessed at.

    Every refusal rule the placement applies applies here too, for the same reasons, and they are
    checked in the same order.
    """
    cfg = cfg or get_benchmarking_config()
    subject_signals = subject_signals or {}
    charged_points = charged_points or {}
    n = len(peers)

    def refuse(reason: str) -> ExpectationGapReport:
        return ExpectationGapReport(
            supplier_ref=supplier_ref, posture=posture, expected_posture=None, gap=None,
            n=n, published=False, reason=reason,
        )

    # The hard gate first, before anything is computed — Decision 3, and the same order `place`
    # uses. An expectation derived from invented peers is a screenshottable fake, and the caption
    # under it does not travel with the screenshot.
    if is_synthetic:
        return refuse(
            "Reference points only, not assessed suppliers — no expectation is computed from "
            "synthetic peers at any sample size."
        )
    if posture is None:
        return refuse("No published posture to compare (blocked, gated, or insufficient evidence).")
    floor = cfg.min_quartile_n()
    if n < floor:
        return refuse(
            f"Insufficient peer data: {n} comparable supplier(s) assessed, minimum {floor}. "
            f"A gap against a median of {n} is a comparison with a handful of companies, and "
            f"naming it a peer expectation would give it a confidence it has not earned."
        )

    postures = sorted(p.posture for p in peers if p.posture is not None)
    expected = _percentile_value(postures, 50)
    if expected is None:
        return refuse(f"None of the {n} cohort members has a published posture to form a median.")

    gap = posture - expected
    direction = "at" if gap == 0 else ("above" if gap > 0 else "below")

    # Which signals cannot rank anybody here, so they can be named rather than quietly dropped.
    #
    # RUN OVER THE PEERS **PLUS THE SUBJECT**, and the difference is not academic. The cohort
    # statistics elsewhere exclude the subject on purpose — an "n=30" that counts the subject is 29
    # peers, and the percentile rule would be wrong by one. But a DISCRIMINATION verdict asks
    # whether a signal separates the companies being compared, and the subject is one of them.
    #
    # Excluding it inverts the test on precisely the case that matters most: fourteen peers all
    # publishing DMARC is 14/14 in one band, which the modal-share test calls flat — so a vendor
    # who is the ONLY ONE in the cohort without DMARC would have had their single clearest driver
    # suppressed for being unanimous among everyone except them. Including the subject makes it
    # 14/15, which is the discriminating signal it obviously is. A signal is only suppressed when
    # the subject AND its peers all sit in the same band, which is the case the suppression is for.
    with_subject = peers + [PeerRecord(supplier_ref=supplier_ref, posture=posture,
                                       signals=subject_signals)]
    flat = {v.key for v in discrimination_report(with_subject, cfg)
            if v.kind == "signal" and v.verdict == "non_discriminating"}

    drivers: list[GapDriver] = []
    suppressed: list[str] = []
    for signal, band in sorted(subject_signals.items()):
        cost = float(charged_points.get(signal, 0.0))
        if cost <= 0:
            continue                       # cost nothing, so it explains none of the gap
        observed = [p.signals[signal] for p in peers if p.signals.get(signal)]
        if not observed:
            continue                       # no peer was checked — a rate we cannot form
        if signal in flat:
            suppressed.append(signal)
            continue
        sharing = Counter(observed)[band]
        attribution = cost * (1 - sharing / len(observed))
        if attribution <= 0:
            continue                       # every peer is in the same band; nothing to explain
        drivers.append(GapDriver(
            signal=signal, subject_band=band, peers_observed=len(observed),
            peers_sharing_band=sharing, charged_posture_points=round(cost, 2),
            attribution=round(attribution, 2),
        ))

    drivers.sort(key=lambda d: -d.attribution)

    caveats = [
        "The drivers are RANKED, NOT A DECOMPOSITION. Since the diminishing-returns rule (E7a), "
        "what a finding costs depends on what else was charged alongside it, so per-signal "
        "attributions do not sum to the gap and cannot be made to.",
        f"The expectation is the {_ESTIMATOR}, over n={n} peers excluding this "
        f"supplier. The median rather than the mean because one extreme member is a large share of "
        f"a cohort this size.",
    ]
    if suppressed:
        caveats.append(
            f"Suppressed from the drivers because they do not vary across this cohort: "
            f"{', '.join(sorted(suppressed))}. This supplier is charged for them and so are its "
            f"peers, so they explain none of its POSITION — but 'every supplier in your cohort "
            f"fails this' is a finding in its own right and is reported separately."
        )
    if gap > 0:
        caveats.append(
            "This supplier is ABOVE its peer median. The drivers below are still what it is "
            "charged for; they are not evidence of being behind."
        )

    return ExpectationGapReport(
        supplier_ref=supplier_ref, posture=posture, expected_posture=expected, gap=gap,
        n=n, published=True, direction=direction,
        drivers=drivers[:max_drivers], suppressed_signals=sorted(suppressed), caveats=caveats,
    )
