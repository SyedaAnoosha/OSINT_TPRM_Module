"""E13 — bounded log-odds. BUILT, TESTED, AND DELIBERATELY NOT SWITCHED ON.

THE DEFECT IT FIXES. The published posture is `100 − Σpenalty/divisor`, clamped at 0. A vendor with
three Criticals and one with fifteen both publish **0**. At the bottom of the scale, where triage
matters most and where a procurement team most needs an ordering, the model has none. E7 made this
worse before it makes it better: diminishing returns moved `synthetic_floor` from 16 to 39, which
is the compression arriving from the other end.

    L̃ = c^τ · L + (1 − c^τ) · L_peer          Posture = 100 · (1 − σ(L̃))

`L` is this vendor's own penalty expressed as log-odds. `L_peer` is their cohort's. `c` is
confidence, and `c^τ` is how far we trust the vendor's own evidence over their peer group's.

WHAT THE SHAPE BUYS, in order of how much it matters:

  * NEVER FLOORS, NEVER SATURATES. σ is asymptotic at both ends, so a fifteen-Critical vendor and a
    three-Critical vendor always separate. The ordering survives at the extremes, which is the
    whole point.
  * IT MAKES THE GHOST CLIFF UNNECESSARY. An unmeasurable vendor shrinks toward their cohort
    median rather than toward a flattering 100, so **hiding stops being better than being
    average** — which is the strongest structural argument in the entire plan, because it removes
    the incentive rather than penalising the response to it.
  * Confidence enters as a SHRINKAGE WEIGHT, not as a penalty. Thin evidence pulls a vendor toward
    what is typical rather than toward a number we invented.

WHY IT IS OFF, AND WHY IT IS HERE ANYWAY

`shrink()` requires `L_peer`. The peer pool is not seeded (E11), so today `L_peer` would come from
`_synthetic_baseline_peers` — six invented postures. **Shrinking every under-evidenced vendor
toward six numbers somebody typed would be materially worse than not shrinking at all**: it would
take the system's most defensible property (we refuse to publish what we cannot evidence) and
replace it with a confident number derived from fiction, applied hardest to exactly the vendors we
know least about.

The plan lists that as a precondition to *verify, not assume*. `preconditions()` verifies it in
code, `enabled()` refuses without it, and `test_log_odds.py` asserts the refusal — so this cannot
be switched on by an `enabled: true` in YAML while the pool is still synthetic.

It is built now rather than at E11 because the transform is the part that can be reasoned about,
tested and reviewed WITHOUT the pool, and having it reviewed in advance is what turns E13 from a
three-week unknown into a switch-on. Nothing here is imported by the engine.

THIS IS A SECOND RELEASE WHEN IT LANDS. It changes what the number means — same evidence, different
published figure — so it needs a version bump, a notice period and side-by-side publication. A
model change that arrives without those is indistinguishable to a client from a vendor's posture
having moved.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

#: Numerical guard. A vendor with zero penalty has infinite log-odds of being clean, and a vendor
#: at the cap has negative infinity; both are real limits of the transform and neither is
#: representable. Clamping the PROBABILITY before taking logs keeps the published range at roughly
#: 0.5-99.5 rather than 0-100 — which is the honest shape anyway, since neither "certainly
#: compromised" nor "certainly clean" is a claim external observation can support.
_EPS = 1e-4


@dataclass(frozen=True)
class ShrinkageInput:
    """One vendor's own evidence, and the cohort it is read against."""

    penalty_fraction: float          # 0-1: capped penalty / (max_score × divisor)
    confidence: float                # 0-1: evidence coverage
    peer_penalty_fraction: float | None = None
    n_peers: int = 0
    peers_are_synthetic: bool = True


@dataclass(frozen=True)
class PeerContext:
    """`L_peer`'s inputs, assembled from a cohort — or an explicit refusal to assemble them.

    THIS TYPE IS THE PART E13 WAS MISSING. Every exit criterion but the switch-on was met, and the
    phase note said *"switching on is one argument, demonstrated rather than promised"* — but the
    engine passed `peer_penalty_fraction=None, n_peers=0, peers_are_synthetic=True` as literals and
    **no code anywhere computed a peer penalty rate**. The argument did not exist to be changed. A
    promise that the last step is one line is worth exactly as much as the line being there.
    """

    penalty_fraction: float | None
    n_peers: int
    is_synthetic: bool
    median_posture: float | None = None
    capped_peers: int = 0
    basis: str = ""

    def as_shrinkage(self, *, penalty_fraction: float, confidence: float) -> ShrinkageInput:
        return ShrinkageInput(
            penalty_fraction=penalty_fraction, confidence=confidence,
            peer_penalty_fraction=self.penalty_fraction,
            n_peers=self.n_peers, peers_are_synthetic=self.is_synthetic,
        )


#: What the engine passes when it has no cohort to offer. Identical in every respect to the literals
#: the engine used to inline, so the default path's behaviour and its refusal text are unchanged.
NO_PEERS = PeerContext(
    penalty_fraction=None, n_peers=0, is_synthetic=True,
    basis="no cohort was supplied to the engine for this vendor",
)


def penalty_fraction_from_posture(posture: float, *, max_score: float = 100.0) -> float:
    """Invert the published posture back to the penalty fraction `L` is taken over.

    `posture = max_score − Σcapped/divisor` and `penalty_fraction = Σcapped/(max_score·divisor)`,
    so the two are related by `penalty_fraction = (max_score − posture)/max_score` exactly — no
    divisor needed, and no dependence on the tuning constant.

    EXACT EXCEPT AT THE CLAMPS, which is why the cohort statistic below is a MEDIAN. A peer at the
    0 floor inverts to 1.0 when their true fraction is higher, and a peer capped by the critical or
    confidence ceiling inverts to a fraction far larger than the one they actually earned. Both are
    real distortions and they point in opposite directions, so neither can be corrected by an
    adjustment — but neither moves a median in a cohort of eight or more, and the count of capped
    peers is disclosed so a reader can see whether the median is standing on distorted values.
    """
    return min(1.0, max(0.0, (max_score - posture) / max_score))


def peer_context(
    postures: list[float],
    *,
    is_synthetic: bool,
    capped_peers: int = 0,
    cohort_label: str | None = None,
) -> PeerContext:
    """Build `L_peer` from a cohort's published postures. Empty is a refusal, not a zero.

    THE MEDIAN, NOT THE MEAN — see `penalty_fraction_from_posture`. The mean is moved by exactly the
    peers whose posture hit a clamp, and those are the ones whose inverted penalty fraction is
    least trustworthy.

    THE EXACT COHORT, NEVER A WIDENED ONE. The benchmark's ladder widens — sector+size+delivery,
    then sector+size, then sector — because *"where does this supplier rank"* is still worth
    answering against a looser group, with the widening disclosed. Shrinking is different: it moves
    a vendor's published number toward the group, and pulling a supplier toward a sector-wide median
    while the label still says "peer group" is a claim about a population we did not compare them
    to. If the exact cohort cannot hold eight, the answer is to refuse, which is what
    `preconditions()` does.
    """
    clean = sorted(p for p in postures if p is not None)
    if not clean:
        return PeerContext(
            penalty_fraction=None, n_peers=0, is_synthetic=is_synthetic,
            basis=f"cohort {cohort_label or '(unnamed)'} holds no scored peer",
        )
    mid, odd = divmod(len(clean), 2)
    median = clean[mid] if odd else (clean[mid - 1] + clean[mid]) / 2.0
    return PeerContext(
        penalty_fraction=penalty_fraction_from_posture(median),
        n_peers=len(clean),
        is_synthetic=is_synthetic,
        median_posture=median,
        capped_peers=capped_peers,
        basis=(f"median posture {median:g} over {len(clean)} peer(s) in cohort "
               f"{cohort_label or '(unnamed)'}"
               + (f"; {capped_peers} of them published a CAPPED posture, whose inverted penalty "
                  f"rate overstates what they actually earned" if capped_peers else "")),
    )


@dataclass
class ShrinkageResult:
    posture: float | None
    own_log_odds: float
    peer_log_odds: float | None
    weight: float                    # c^τ — how much of the vendor's own evidence was used
    shrunk_log_odds: float | None
    published: bool
    reason: str | None = None
    caveats: list[str] = field(default_factory=list)


def logit(p: float) -> float:
    """Log-odds of a probability, clamped away from the asymptotes. See `_EPS`."""
    p = min(1.0 - _EPS, max(_EPS, p))
    return math.log(p / (1.0 - p))


def sigmoid(x: float) -> float:
    # Written this way rather than 1/(1+exp(-x)) so a large negative x cannot overflow exp().
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def posture_from_log_odds(log_odds: float) -> float:
    """`100 · (1 − σ(L))`. High log-odds of trouble means low posture."""
    return 100.0 * (1.0 - sigmoid(log_odds))


def preconditions(inp: ShrinkageInput, *, min_peers: int = 8) -> list[str]:
    """Every reason this vendor may NOT be shrunk. Empty means it may.

    Returned as a list rather than a bool because each entry is a different piece of work, and a
    single `False` would collapse "the pool is not seeded yet" into "this vendor has no cohort" —
    which are a programme task and a per-vendor fact respectively.
    """
    failures: list[str] = []
    if inp.peer_penalty_fraction is None:
        failures.append("no cohort penalty rate available — nothing to shrink toward")
    if inp.peers_are_synthetic:
        failures.append(
            "the peer pool is SYNTHETIC. Shrinking an under-evidenced vendor toward invented "
            "numbers would be materially worse than not shrinking: it replaces a refusal to "
            "publish with a confident figure derived from fiction, applied hardest to exactly the "
            "vendors we know least about. This is E11's seeded pool, and it is not optional."
        )
    if inp.n_peers < min_peers:
        failures.append(f"cohort holds {inp.n_peers} peers, below the floor of {min_peers}")
    return failures


def enabled(inp: ShrinkageInput, *, min_peers: int = 8) -> bool:
    """Whether the transform may run for this vendor. There is no config flag that overrides this.

    Deliberately not readable from YAML. A precondition that can be waived by an `enabled: true` is
    not a precondition, and `min_cohort_n: 1` is the standing evidence in this codebase that a
    setting which CAN be lowered eventually is.
    """
    return not preconditions(inp, min_peers=min_peers)


def shrink(inp: ShrinkageInput, *, tau: float = 1.0, min_peers: int = 8) -> ShrinkageResult:
    """`L̃ = c^τ·L + (1 − c^τ)·L_peer`, or a stated refusal.

    `tau` shapes how fast trust in a vendor's own evidence falls away as coverage thins. τ=1 is
    linear in confidence; τ>1 keeps trusting the vendor's own evidence further down. It is a
    parameter rather than a constant because it is the one knob here that is genuinely a judgement
    call, and it should be argued over with a real pool in front of the people arguing.
    """
    own = logit(inp.penalty_fraction)
    weight = inp.confidence ** tau
    failures = preconditions(inp, min_peers=min_peers)
    peer = None if inp.peer_penalty_fraction is None else logit(inp.peer_penalty_fraction)

    if failures:
        return ShrinkageResult(
            posture=None, own_log_odds=own, peer_log_odds=peer, weight=weight,
            shrunk_log_odds=None, published=False, reason=" · ".join(failures),
        )

    assert peer is not None
    shrunk = weight * own + (1.0 - weight) * peer
    return ShrinkageResult(
        posture=posture_from_log_odds(shrunk),
        own_log_odds=own, peer_log_odds=peer, weight=weight,
        shrunk_log_odds=shrunk, published=True,
        caveats=[
            f"{round(weight * 100)}% of this figure comes from this vendor's own evidence and "
            f"{round((1 - weight) * 100)}% from their peer group's typical position. Thin evidence "
            f"pulls a vendor toward what is normal for their cohort, not toward a flattering "
            f"number — which is why hiding stops being better than being average.",
            "This transform never reaches 0 or 100. Neither 'certainly compromised' nor 'certainly "
            "clean' is a claim external observation can support.",
        ],
    )
