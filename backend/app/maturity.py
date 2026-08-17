"""Operating history — years on the record turned into a number the model can use.

THE PROBLEM THIS MODULE EXISTS TO FIX. Age used to be five step-bands, and the top one opened at
ten years. A forty-year-old vendor and an eleven-year-old vendor produced byte-identical output;
a two-year-old and a forty-year-old differed by a single `low` (3 penalty points, 0.75 posture
after the divisor) — inside the noise of a grade band. Domain age was worse: `domain_established`
begins at 730 days, so a two-year-old domain and a forty-year-old domain were the same
observation. The model *represented* operating history without ever *resolving* it.

THE CURVE, AND WHY IT SATURATES. `maturity_index` is logarithmic, reaching 1.0 at
`SATURATION_YEARS`:

    index(y) = min(1, ln(1 + y) / ln(1 + SATURATION_YEARS))

    1y -> 0.21   2y -> 0.34   5y -> 0.55   10y -> 0.74   20y -> 0.93   25y+ -> 1.00

Steep where the difference is real and flat where it is not. The gap between year one and year
five is a genuine difference in demonstrated continuity; the gap between year twenty-five and
year forty is not, and a linear-in-years term would have quietly made "old" the single largest
term in the model. Diminishing returns on operating history is the claim, and it is the one the
curve makes.

WHAT THIS IS NOT ALLOWED TO DO. It does not touch posture arithmetic. `context-aware-vendor-risk-
scoring-study.md` §1.4 records that no authoritative source scores or normalises by founding date
— the finding is "no published evidence", not "weak evidence" — so age driving a risk PREDICTION
would be an assertion wearing a decimal point, and §1.6 puts it out of Posture explicitly. Age
therefore reaches exactly two places: a bounded CONFIDENCE multiplier (how much operating record
stands behind the measurement) and the BENCHMARK cohort (who this vendor is fairly compared with).
Two vendors with identical findings still get an identical posture. That is deliberate.

AGE IS PURCHASABLE, WHICH IS WHY EVIDENCE STRENGTH IS SEPARATE. An aged domain costs a few hundred
dollars on an expiry auction; a company inception date in a national register does not. Weighting
every source the same would have made "buy an old domain" the cheapest posture uplift in the
product. `assurance_index` therefore discounts by source, and discounts in ONE direction only — a
weak source can never buy assurance, and can never manufacture youth that isn't there either. The
engine independently takes the most conservative multiplier when sources disagree.
"""

from __future__ import annotations

import math

# The age at which more history stops telling us anything new. A vendor trading 25 years has
# demonstrated continuity across at least two full economic cycles; one trading 40 has not
# demonstrated meaningfully more, and treating it as though it had would let age dominate.
SATURATION_YEARS = 25.0

# How far a source is trusted to speak about OPERATING history, as a fraction of full credit.
# A national register records the legal entity's inception; RDAP records when somebody paid for a
# domain name. Those are different claims, and only the first is what "operating history" means.
EVIDENCE_STRENGTH: dict[str, float] = {
    "gleif": 1.0,               # LEI registration — authoritative entity record
    "companies_house": 1.0,     # UK register
    "abn": 1.0,                 # Australian Business Register
    "wikidata": 0.9,            # curated inception date; corroborated but community-maintained
    "firmographics": 0.8,       # aggregated founding year
    "pdl": 0.8,
    "rdap": 0.6,                # domain creation date — a proxy, and a buyable one
}
# An unrecognised source is treated as the weakest named one rather than as full credit: a new
# collector must earn its weight in this table, not inherit it by being absent from it.
DEFAULT_EVIDENCE_STRENGTH = 0.6

# Band edges, in years. UNCHANGED from the step model they replace — scoring.yaml maps these keys
# to severities, reasons and actions, and moving them would silently re-score every stored vendor.
# The bands are now a LABEL for the narrative; the index above is what the model computes with.
_BANDS: tuple[tuple[float, str], ...] = (
    (10.0, "mature_gt_10"),
    (5.0, "established_5_10"),
    (2.0, "young_2_5"),
    (1.0, "startup_lt_2"),
)
_YOUNGEST_BAND = "new_lt_1"


def years_between(earlier: object, later: object) -> float | None:
    """Whole-and-fractional years between two datetimes, or None if either is missing.

    Kept here so every caller measures age the same way — 365.25 days, floored at zero. A future
    inception date is a source error, not a negative age, and must not produce a negative index.
    """
    from datetime import datetime

    if not isinstance(earlier, datetime) or not isinstance(later, datetime):
        return None
    return max(0.0, (later - earlier).days / 365.25)


def maturity_index(years: float | None) -> float | None:
    """Operating history as a saturating 0-1 index. None in, None out — an unknown age is unknown,
    never a zero, which would read as "founded today" and is a different claim entirely."""
    if years is None:
        return None
    years = max(0.0, float(years))
    return min(1.0, math.log1p(years) / math.log1p(SATURATION_YEARS))


def maturity_band(years: float | None) -> str | None:
    """The band key for narrative and severity lookup. The index is what we compute with; this is
    what a reader is shown and what scoring.yaml maps to a sentence."""
    if years is None:
        return None
    for edge, key in _BANDS:
        if years >= edge:
            return key
    return _YOUNGEST_BAND


def evidence_strength(source: str | None) -> float:
    """How far this source is trusted to speak about operating history (see EVIDENCE_STRENGTH)."""
    if not source:
        return DEFAULT_EVIDENCE_STRENGTH
    return EVIDENCE_STRENGTH.get(str(source).lower(), DEFAULT_EVIDENCE_STRENGTH)


def assurance_index(years: float | None, source: str | None = None) -> float | None:
    """The index used for the CONFIDENCE multiplier: operating history, discounted by how well the
    claim is evidenced.

    The discount is deliberately one-directional. It scales the index DOWN, so a weakly-evidenced
    forty-year-old domain earns roughly what a well-evidenced seven-year-old company earns — which
    is the intended answer, because an aged domain is a thing you can buy and a seven-year trading
    record is not. It can never scale UP, so no source combination invents assurance the evidence
    does not support.
    """
    index = maturity_index(years)
    if index is None:
        return None
    # Clamped to the raw index, not merely multiplied by a weight <= 1. Rounding alone would let a
    # full-credit source round UP past the honest curve by a hair, and "a discount can only
    # discount" is an invariant worth holding exactly rather than to four decimal places.
    return min(index, round(index * evidence_strength(source), 4))


def multiplier_from(index: float | None, floor: float, ceiling: float) -> float:
    """Interpolate a bounded confidence multiplier across the index.

    Linear between `floor` (no operating history) and `ceiling` (saturated). Linear is correct
    HERE even though the index itself is logarithmic: the curve has already done the compression,
    and compressing twice would flatten the top of the range back into the single bucket this
    whole module exists to remove.
    """
    if index is None:
        return 1.0
    lo, hi = (floor, ceiling) if floor <= ceiling else (ceiling, floor)
    return round(lo + (hi - lo) * max(0.0, min(1.0, index)), 4)


def age_adjusted_assurance(
    years: float | None,
    source: str | None = None,
    age_band: str | None = None,
) -> float | None:
    """Age-adjusted assurance index that considers data richness by vendor age.

    Mature vendors (10+ years) with rich OSINT corpus get higher confidence weighting.
    Young vendors (<5 years) with sparse data have individual findings carry higher relative weight.

    Args:
        years: Operating years since incorporation
        source: Data source for age claim (for evidence strength)
        age_band: Vendor age band (startup, young, established, mature, veteran, unknown)

    Returns:
        Adjusted assurance index (0-1) or None if years is None

    Rationale:
    - 20-year vendor: Multi-year trends can be weighed; rich corpus supports higher confidence
    - 2-year vendor: Sparse data means single red flags are more significant; absence of history
      is itself elevated risk, not neutral
    """
    base_assurance = assurance_index(years, source)
    if base_assurance is None:
        return None

    # No age band provided - return base assurance
    if age_band is None:
        return base_assurance

    # Age-specific adjustments
    # Young vendors: discount assurance further due to sparse data
    if age_band in ("startup", "young"):
        # Sparse data means we have less confidence in our assessment
        # Apply additional discount beyond evidence strength
        age_discount = 0.85 if age_band == "startup" else 0.90
        return round(base_assurance * age_discount, 4)

    # Mature vendors: can weight multi-year patterns more heavily
    # No additional discount - the base assurance already reflects their long history
    if age_band in ("mature", "veteran"):
        return base_assurance

    # Established and unknown: no age-specific adjustment
    return base_assurance
