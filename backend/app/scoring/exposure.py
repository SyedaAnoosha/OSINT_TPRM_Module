"""Exposure — turn a raw failure COUNT into a rate the size of the estate cannot distort (E6).

THE DEFECT THIS FIXES. `stale_hosts` was banded on a raw count: 0 is `none`, 1-5 is `some`, more
is `many`. So a vendor with 4 public hosts and 2 abandoned ones — half their estate rotting —
scored `some` and paid 8, while a vendor with 900 hosts and 9 abandoned ones scored `many` and
paid 20. The second is running a tidier estate by a factor of fifty and paid two and a half times
more. The model was measuring how BIG a vendor is and calling the answer risk.

`docs/discrimination-analysis.md` shows this is not hypothetical: `stale_hosts`,
`subdomain_estate` and `weak_issuance` charge **every** real corpus vendor. Three of the four
remaining flat taxes are footprint signals, and a penalty nobody escapes ranks nobody.

THE ARITHMETIC, AND WHY IT IS NOT JUST f/D

    r̂ = (f + α) / (D + α + β)                 beta-binomial posterior mean
    g = λ·r̂ + (1 − λ)·min(1, f/κ)             the rate, blended with an absolute floor

Two corrections, each answering a way the naive ratio fails:

  * **α, β — the prior.** One stale host out of one observed host is not a 100% failure rate; it
    is one observation. `f/D` cannot tell the difference between 1-of-1 and 900-of-900, and would
    hand the smallest vendors the worst possible score on the thinnest possible evidence. The
    prior shrinks a small sample toward the population base rate, and its strength (α+β) is
    exactly "how many observations before we believe the vendor's own rate".

  * **κ — the absolute floor.** A pure rate lets scale buy forgiveness: 60 abandoned hosts out of
    900 is 6.6%, which reads fine, and 60 abandoned hosts is 60 ways in. λ decides how much of the
    verdict is proportional and how much is absolute. Without it the rate correction would simply
    invert the original defect in favour of large vendors.

f = 0 SHORT-CIRCUITS TO `none`, ALWAYS. With a prior, zero observed failures still yields a small
positive r̂ — for a 4-host vendor, 0.5/14 = 3.6% — which would band a vendor with a *perfectly
clean* estate as having a problem. The prior exists to temper a rate we have observed, never to
manufacture one we have not. Nothing is more corrosive to trust in a score than being charged for
a finding of zero.

PURE FUNCTIONS, NO CONFIG READS — the same discipline as `modifiers.py`. Every parameter arrives
as an argument so the arithmetic can be reasoned about, tested and disputed on its own, and so
`scoring.yaml` stays the single place the numbers live.
"""

from __future__ import annotations

from dataclasses import dataclass

# Defaults, used only when a caller supplies nothing. The SHIPPED values live in
# `scoring.yaml` -> `exposure:`; these exist so the functions are callable in isolation.
DEFAULT_ALPHA = 0.5
DEFAULT_BETA = 9.5      # alpha+beta = 10 -> "believe the vendor's own rate after ~10 hosts"
DEFAULT_LAMBDA = 0.7    # 70% proportional, 30% absolute
DEFAULT_KAPPA = 50.0    # the count at which the absolute term saturates


@dataclass(frozen=True)
class ExposureResult:
    """The rate, and everything needed to publish and dispute it.

    `denominator` is carried deliberately. E6's exit criterion is *publish the denominator*, and
    attribution — *"you counted 340 hosts, we operate 40"* — is a top-two dispute category. A rate
    whose denominator is not shown cannot be argued with, and a finding that cannot be argued with
    does not belong in a report we ask vendors to accept.
    """

    failures: int
    denominator: int
    posterior_rate: float     # r̂ — what share of the estate is affected, prior-corrected
    absolute_term: float      # min(1, f/κ) — how bad it is regardless of estate size
    index: float              # g — the blend, in [0, 1]
    band: str

    def cited(self) -> str:
        """The published sentence. Always names both numbers, never just the rate."""
        return (f"{self.failures} of {self.denominator} observed hosts "
                f"({self.posterior_rate:.1%} adjusted)")


def posterior_rate(failures: int, denominator: int, *,
                   alpha: float = DEFAULT_ALPHA, beta: float = DEFAULT_BETA) -> float:
    """Beta-binomial posterior mean. Never 1.0 for a small sample, never 0.0 for a large one."""
    if denominator < failures:
        # A denominator smaller than the numerator means the two came from different observations
        # — the safe reading is that the estate is at least as large as the failures we counted.
        denominator = failures
    return (failures + alpha) / (denominator + alpha + beta)


def absolute_term(failures: int, *, kappa: float = DEFAULT_KAPPA) -> float:
    """The scale-independent half: how bad `failures` is on its own terms, saturating at κ."""
    if kappa <= 0:
        return 0.0
    return min(1.0, failures / kappa)


def exposure_index(failures: int, denominator: int, *,
                   alpha: float = DEFAULT_ALPHA, beta: float = DEFAULT_BETA,
                   lam: float = DEFAULT_LAMBDA, kappa: float = DEFAULT_KAPPA) -> float:
    """`g` — the blended exposure index in [0, 1]. Zero failures is zero exposure, always."""
    if failures <= 0:
        return 0.0
    r = posterior_rate(failures, denominator, alpha=alpha, beta=beta)
    return lam * r + (1.0 - lam) * absolute_term(failures, kappa=kappa)


def band_for(index: float, thresholds: dict[str, float], *, zero_band: str) -> str:
    """Map `g` onto a band key, given `{band: lower_bound}` from config.

    Bands are kept because everything downstream depends on them: `reasons` and `actions` are
    keyed by band and loader-enforced, and `_apply_dispute` matches on `(signal, band_key)`. A
    continuous penalty would have nothing to attach a sentence to, so the rate decides the BAND
    and the band decides the penalty — the model's existing shape, fed a better input.
    """
    if index <= 0.0:
        return zero_band
    chosen, best = zero_band, -1.0
    for band, lower in thresholds.items():
        if index >= lower and lower >= best:
            chosen, best = band, lower
    return chosen


def evaluate(failures: int, denominator: int, spec: dict) -> ExposureResult:
    """One signal's raw counts + its `exposure:` spec -> a banded, publishable result."""
    alpha = float(spec.get("alpha", DEFAULT_ALPHA))
    beta = float(spec.get("beta", DEFAULT_BETA))
    lam = float(spec.get("lambda", DEFAULT_LAMBDA))
    kappa = float(spec.get("kappa", DEFAULT_KAPPA))
    thresholds = {str(k): float(v) for k, v in (spec.get("bands") or {}).items()}
    zero_band = str(spec.get("zero_band", "none"))

    index = exposure_index(failures, denominator, alpha=alpha, beta=beta, lam=lam, kappa=kappa)
    return ExposureResult(
        failures=failures,
        denominator=denominator,
        posterior_rate=posterior_rate(failures, denominator, alpha=alpha, beta=beta),
        absolute_term=absolute_term(failures, kappa=kappa),
        index=index,
        band=band_for(index, thresholds, zero_band=zero_band),
    )
