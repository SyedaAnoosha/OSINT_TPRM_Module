# Vendor Age Differentiation in OSINT TPRM Module

## Overview

The OSINT-based Third-Party Risk Management (TPRM) module implements a sophisticated vendor age differentiation system that distinguishes between vendors of different ages (e.g., 2 years vs 20 years) through multiple complementary mechanisms. This system recognizes that vendor age is a contextual factor for business stability assessment rather than a direct cybersecurity penalty.

**Key Principle:** A 2-year-old startup can have excellent cybersecurity controls, and a 40-year-old company can have poor security. Age affects BUSINESS STABILITY only, not cybersecurity posture.

## Architecture

The age differentiation system consists of three main modules:

1. **`longevity.py`** - Discrete age band classification with base scores and confidence adjustments
2. **`maturity.py`** - Continuous logarithmic maturity index with evidence strength weighting  
3. **`business_stability.py`** - Integration of age into Business Stability scoring

## Module 1: longevity.py - Age Band Classification

### Age Bands

The system classifies vendors into six age bands based on operating years:

| Age Band | Operating Years | Description |
|----------|----------------|-------------|
| `startup` | < 2 years | Highest risk, 3× failure rate (liability of newness) |
| `young` | 2-5 years | Moderate risk, some track record |
| `established` | 5-10 years | Lower risk, proven business model |
| `mature` | 10-20 years | Low risk, demonstrated staying power |
| `veteran` | 20+ years | Lowest risk, survivorship bonus |
| `unknown` | Age not determinable | Conservative middle ground |

### Base Business Stability Scores by Age Band

Each age band has a starting base score for Business Stability assessment:

```python
base_scores = {
    "startup": 70,      # Must prove viability
    "young": 85,        # Some track record
    "established": 90,  # Proven business
    "mature": 95,       # Demonstrated staying power
    "veteran": 100,     # Maximum survivorship credit
    "unknown": 85,      # Conservative middle ground
}
```

**Rationale:** Younger vendors start with lower base scores because they lack a track record. They must EARN their way up through demonstrated financial health.

### Confidence Adjustments by Age Band

Young vendors receive confidence penalties due to limited operating history:

```python
confidence_adjustments = {
    "startup": -0.20,   # 20% reduction (high uncertainty)
    "young": -0.10,     # 10% reduction (moderate uncertainty)
    "established": 0.00, # No adjustment
    "mature": 0.00,     # No adjustment
    "veteran": 0.00,    # No adjustment
    "unknown": -0.05,   # 5% reduction (age uncertainty)
}
```

**Rationale:** This is a COVERAGE adjustment, not a risk penalty — it reflects uncertainty in our assessment, not poor performance by the vendor.

### Survivorship Bonuses

Vendors that demonstrate staying power receive bonus points:

```python
survivorship_bonuses = {
    "startup": 0,        # No survivorship yet
    "young": 0,          # Too early for credit
    "established": 0,    # Not yet demonstrated long-term survival
    "mature": 5,         # Survived 10+ years
    "veteran": 10,       # Survived 20+ years
    "unknown": 0,         # Cannot determine survivorship
}
```

**Additional Bonus:** +5 points for surviving known economic downturns (2008, 2020) if the vendor was in business during those periods.

### Age-Specific Risk Factors

Different risk factors are assessed based on age band:

**Startup (<2 years):**
- Funding runway remaining
- Customer concentration risk
- Founder dependency (key person risk)

**Young (2-5 years):**
- Growth sustainability
- Market validation (product-market fit)
- Team completeness and hiring ability

**Established (5-10 years):**
- Market position in industry
- Operational efficiency and margin pressure
- Scalability without breaking operations

**Mature (10-20 years):**
- Decline signals (revenue/market share trends)
- Acquisition risk (leadership changes, PE ownership)
- Innovation stagnation (R&D investment, product pipeline)

**Veteran (20+ years):**
- Institutional health (governance, succession planning)
- Adaptability to market changes
- Legacy risk (technical debt, outdated systems)

## Module 2: maturity.py - Continuous Age Index

### Logarithmic Maturity Index

The system uses a continuous logarithmic index that saturates at 25 years:

```python
def maturity_index(years: float | None) -> float | None:
    """Operating history as a saturating 0-1 index."""
    if years is None:
        return None
    years = max(0.0, float(years))
    return min(1.0, math.log1p(years) / math.log1p(SATURATION_YEARS))
```

**Formula:** `index(y) = min(1, ln(1 + y) / ln(1 + 25))`

**Values:**
- 1 year → 0.21
- 2 years → 0.34
- 5 years → 0.55
- 10 years → 0.74
- 20 years → 0.93
- 25+ years → 1.00

**Rationale for Saturation at 25 Years:**
A vendor trading 25 years has demonstrated continuity across at least two full economic cycles; one trading 40 years has not demonstrated meaningfully more. Treating 40 years as significantly higher would let "old" dominate the scoring model.

### Evidence Strength Weighting

Different data sources receive different weights for age claims:

```python
EVIDENCE_STRENGTH: dict[str, float] = {
    "gleif": 1.0,               # LEI registration — authoritative entity record
    "companies_house": 1.0,     # UK register
    "abn": 1.0,                 # Australian Business Register
    "wikidata": 0.9,            # Curated inception date; community-maintained
    "firmographics": 0.8,       # Aggregated founding year
    "pdl": 0.8,
    "rdap": 0.6,                # Domain creation date — proxy, and buyable
}
```

**Rationale:** A national register records the legal entity's inception; RDAP records when somebody paid for a domain name. These are different claims, and only the first is what "operating history" means.

### Assurance Index

The confidence multiplier combines maturity index with evidence strength:

```python
def assurance_index(years: float | None, source: str | None = None) -> float | None:
    """The index used for the CONFIDENCE multiplier: operating history, discounted by evidence."""
    index = maturity_index(years)
    if index is None:
        return None
    # Discount is one-directional only - can scale down, never up
    return min(index, round(index * evidence_strength(source), 4))
```

**Key Principle:** The discount is deliberately one-directional. It scales the index DOWN, so a weakly-evidenced forty-year-old domain earns roughly what a well-evidenced seven-year-old company earns — which is the intended answer, because an aged domain is a thing you can buy and a seven-year trading record is not.

## Module 3: business_stability.py - Integration

### Age-Based Base Score Calculation

The Business Stability score starts with an age-based base score:

```python
def _compute_age_base(self) -> None:
    """Compute base score from vendor age."""
    # Priority order for age sources:
    # 1. incorporation_date from entity registers
    # 2. entity_maturity from Wikidata (P571 - legal inception date)
    # 3. entity_maturity from RDAP (domain creation date - discounted)
    # 4. Fallback to "unknown" if no source available
    
    if self.profile.incorporation_date:
        self.profile.operating_years = operating_years(self.profile.incorporation_date.value)
    else:
        # Fallback to Wikidata or RDAP maturity data
        wikidata_years = getattr(self.profile, 'wikidata_years', None)
        rdap_years = getattr(self.profile, 'rdap_years', None)
        
        if wikidata_years is not None:
            self.profile.operating_years = wikidata_years
        elif rdap_years is not None:
            self.profile.operating_years = rdap_years
        else:
            self.profile.operating_years = None
    
    # Determine age band and base score
    self.profile.age_band = age_band_from_years(self.profile.operating_years)
    self._base_score = base_age_score(self.profile.age_band or "unknown")
```

### Complete Age Modifier Application

```python
def apply_age_modifiers(
    profile: FinancialProfile,
    base_confidence: float,
) -> tuple[int, float]:
    """Apply all age-based modifiers to Business Stability score and confidence."""
    # Calculate operating years if not already computed
    if profile.operating_years is None and profile.incorporation_date:
        profile.operating_years = operating_years(profile.incorporation_date.value)
    
    # Determine age band if not already computed
    if profile.age_band is None:
        profile.age_band = age_band_from_years(profile.operating_years)
    
    # Get base score from age band
    age_score = base_age_score(profile.age_band or "unknown")
    
    # Apply confidence adjustment
    conf_adj = confidence_adjustment(profile.age_band or "unknown")
    adjusted_confidence = max(0.0, min(1.0, base_confidence + conf_adj))
    
    return age_score, adjusted_confidence
```

## Concrete Examples: 2-Year vs 20-Year Vendor

### Example 1: 2-Year-Old Vendor

**Vendor Profile:**
- Operating years: 2.0
- Age band: "young"
- Base Business Stability score: 85/100
- Confidence adjustment: -10%
- Maturity index: 0.34

**Scoring Impact:**
```python
# Base score calculation
base_score = base_age_score("young")  # Returns 85

# Confidence calculation
base_confidence = 0.90  # From evidence coverage
adjusted_confidence = 0.90 + confidence_adjustment("young")  # 0.90 - 0.10 = 0.80

# Risk factors assessed
risk_factors = age_risk_factors("young")
# Returns: growth_sustainability, market_validation, team_completeness

# Benchmarking cohort
benchmark_cohort = age_appropriate_benchmarking("young")
# "Benchmark against other young vendors (2-5 years) with similar funding stages"
```

**Final Assessment:**
- Business Stability starts at 85/100
- Must prove financial health to increase score
- 10% confidence penalty due to limited track record
- Compared against other young vendors
- Focus on growth sustainability and market validation

### Example 2: 20-Year-Old Vendor

**Vendor Profile:**
- Operating years: 20.0
- Age band: "mature"
- Base Business Stability score: 95/100
- Confidence adjustment: 0%
- Maturity index: 0.93
- Survivorship bonus: +5 points

**Scoring Impact:**
```python
# Base score calculation
base_score = base_age_score("mature")  # Returns 95

# Confidence calculation
base_confidence = 0.90  # From evidence coverage
adjusted_confidence = 0.90 + confidence_adjustment("mature")  # 0.90 + 0.00 = 0.90

# Survivorship bonus
bonus = survivorship_bonus("mature")  # Returns 5

# Risk factors assessed
risk_factors = age_risk_factors("mature")
# Returns: decline_signals, acquisition_risk, innovation_stagnation

# Benchmarking cohort
benchmark_cohort = age_appropriate_benchmarking("mature")
# "Benchmark against other mature vendors (10-20 years) in the same industry"
```

**Final Assessment:**
- Business Stability starts at 95/100 (higher baseline)
- +5 survivorship bonus for demonstrated staying power
- No confidence penalty (extensive track record)
- Compared against other mature vendors
- Focus on decline signals and innovation stagnation

### Key Differences Summary

| Aspect | 2-Year-Old Vendor | 20-Year-Old Vendor |
|--------|------------------|-------------------|
| **Age Band** | young | mature |
| **Base Score** | 85/100 | 95/100 |
| **Confidence Penalty** | -10% | 0% |
| **Maturity Index** | 0.34 | 0.93 |
| **Survivorship Bonus** | 0 | +5 |
| **Risk Focus** | Growth, market fit | Decline, stagnation |
| **Benchmarking** | Young vendors (2-5yr) | Mature vendors (10-20yr) |

## Data Model Integration

### FinancialProfile Model

The `FinancialProfile` model in `models.py` includes age-related fields:

```python
class FinancialProfile(BaseModel):
    vendor_ref: str
    
    # Primary age source
    incorporation_date: ProfileField | None  # Date company was legally incorporated
    
    # Fallback age sources when entity registers unavailable
    wikidata_years: float | None  # Years from Wikidata (P571) - free fallback
    rdap_years: float | None  # Years from domain registration - discounted fallback
    
    # Computed age fields
    operating_years: float | None  # Years since incorporation (computed)
    age_band: Literal["startup", "young", "established", "mature", "veteran", "unknown"] | None
```

## Design Principles

### 1. Age as Context, Not Penalty

Age affects BUSINESS STABILITY only, not cybersecurity posture. A bankrupt company can have excellent security, and a secure startup can run out of cash. These are separate risk dimensions.

### 2. Survivorship Recognition

The system rewards demonstrated staying power through survivorship bonuses. Companies that weather economic downturns or survive for decades have proven business models.

### 3. Evidence Quality Matters

Not all age sources are equal. Entity registers (GLEIF, Companies House) receive full credit, while domain age (RDAP) is discounted because domains can be purchased on expiry auctions.

### 4. Age-Appropriate Benchmarking

Young vendors are benchmarked against peers of similar age, not against established companies. This prevents unfair comparisons and ensures relevant risk assessment.

### 5. Diminishing Returns on Age

The logarithmic maturity index recognizes that the difference between 1 and 5 years is meaningful, but the difference between 25 and 40 years is not. The curve saturates at 25 years.

### 6. Confidence vs. Risk

Confidence adjustments reflect uncertainty in our assessment, not poor vendor performance. A young vendor with limited public information receives a confidence penalty, not a risk penalty.

## Usage Examples

### Basic Age Assessment

```python
from datetime import datetime, UTC
from app.longevity import operating_years, age_band_from_years, base_age_score
from app.maturity import maturity_index, assurance_index

# Calculate operating years
incorporation_date = datetime(2024, 1, 1, tzinfo=UTC)
years = operating_years(incorporation_date)  # Returns ~2.0

# Determine age band
age_band = age_band_from_years(years)  # Returns "young"

# Get base score
score = base_age_score(age_band)  # Returns 85

# Calculate maturity index
maturity = maturity_index(years)  # Returns ~0.34

# Calculate assurance with evidence strength
assurance = assurance_index(years, source="companies_house")  # Returns ~0.34
assurance_rdap = assurance_index(years, source="rdap")  # Returns ~0.20 (discounted)
```

### Full Business Stability Calculation

```python
from app.business_stability import BusinessStabilityScore
from app.models import FinancialProfile

# Create financial profile
profile = FinancialProfile(
    vendor_ref="example_vendor",
    incorporation_date=ProfileField(
        value=datetime(2024, 1, 1, tzinfo=UTC),
        source="companies_house"
    )
)

# Calculate Business Stability score
scorer = BusinessStabilityScore(profile)
result = scorer.compute()

# Result includes:
# - score: final Business Stability score (age-adjusted)
# - base_score: starting score from age band
# - age_band: vendor's age classification
# - penalties: financial distress penalties
# - bonuses: survivorship bonuses
```

## Integration with Benchmarking

The age differentiation system integrates with the benchmarking module to ensure age-appropriate comparisons:

```python
def age_appropriate_benchmarking(age_band: AgeBand) -> str:
    """Return benchmarking guidance based on vendor age."""
    guidance = {
        "startup": "Benchmark against other startups (<2 years) with similar funding stages",
        "young": "Benchmark against other young vendors (2-5 years) with similar growth trajectories",
        "established": "Benchmark against established vendors (5-10 years) in same industry",
        "mature": "Benchmark against mature vendors (10-20 years) in same industry",
        "veteran": "Benchmark against veteran vendors (20+ years) with similar market positions",
        "unknown": "Benchmark against industry averages (age unknown)",
    }
    return guidance.get(age_band, "Benchmark against industry averages")
```

## References

- **Research Basis:** "Liability of newness" (Stinchcombe, 1965) - established research on higher failure rates for young organizations
- **Vendor Risk Best Practices:** Industry standard treating age as business stability factor, not security factor
- **Regulatory Alignment:** Approach aligns with Australian regulatory guidance on transparent, defensible scoring
- **Related Documentation:** 
  - `methodology.md` - Overall OSINT TPRM methodology
  - `financial_integration_design.md` - Business Stability axis design
  - `scoring_model.md` - Complete scoring model documentation

## Gaps and Enhancement Opportunities

Based on comprehensive vendor risk management best practices, the current implementation has several enhancement opportunities to fully leverage vendor age as a material risk differentiator:

### 1. Inherent Risk Baseline Adjustment

**Current State:** Inherent risk is calculated solely from `criticality` and `data_access_scope` (see `residual_risk.py`). Age does not factor into inherent risk calculation.

**Recommended Enhancement:** Apply age-based modifier to inherent risk baseline:
- Young vendors (<3-5 years): Apply upward adjustment to inherent risk due to limited track record and elevated failure risk
- Mature vendors (≥10-15 years): Apply downward adjustment or neutral baseline; focus on long-term patterns

**Implementation Location:** `residual_risk.py` - `inherent_tier()` function

### 2. Monitoring Cadence by Age

**Current State:** Monitoring cadence is determined by inherent tier (T1-T4) via `assessment_depth.py`. Age does not influence monitoring frequency.

**Recommended Enhancement:** Implement age-adjusted monitoring cadence:
- Young vendors: Higher-frequency continuous monitoring, tighter alert thresholds, shorter reassessment cycles
- Mature vendors: Risk-based cadence scaled to tier + recent signal strength; historical stability can justify relaxed intervals

**Implementation Location:** `assessment_depth.py` - Assessment plan lookup table, `monitor.py` - scheduling logic

### 3. Evidence Weighting by Vendor Age

**Current State:** Evidence strength is based on source reliability (GLEIF=1.0, RDAP=0.6) but not on vendor age. (see `maturity.py`)

**Recommended Enhancement:** Apply age-specific evidence weighting:
- 20-year vendor: Weight multi-year trends more heavily; rich OSINT corpus gets higher confidence
- 2-year vendor: Sparse data means single red flags carry higher relative weight; require stronger corroboration

**Implementation Location:** `maturity.py` - Evidence strength calculation, confidence scoring

### 4. Age-Specific Residual Risk Thresholds

**Current State:** Residual risk matrix uses posture bands vs inherent tiers uniformly. No age-based adjustments to residual risk thresholds.

**Recommended Enhancement:** Implement age-adjusted residual risk thresholds:
- Young vendors: Lower residual-risk acceptance bars (same posture → higher residual risk classification)
- Mature vendors: Standard thresholds; long history supports current posture assessment

**Implementation Location:** `residual_risk.py` - `_RESIDUAL` matrix lookup

### 5. Incident & Reputation Pattern Analysis by Age

**Current State:** Incident scoring applies uniformly regardless of vendor age. No age-specific incident weight or pattern analysis.

**Recommended Enhancement:** Age-specific incident analysis:
- Mature vendors: Look for recurring themes, severity trends, remediation evidence over time
- Young vendors: Treat any material incident as higher-impact (little positive counter-history); scrutinize founder/key-personnel OSINT more aggressively

**Implementation Location:** Scoring configuration (`scoring.yaml`), incident collectors

### 6. Change & Continuity Monitoring by Age

**Current State:** Change monitoring applies uniformly. No age-specific change focus areas.

**Recommended Enhancement:** Age-specific change indicators:
- Mature vendors: Monitor for late-stage risks (ownership changes, divestitures, key-person departures, declining sentiment)
- Young vendors: Monitor for rapid scaling signals (headcount jumps, geographic expansion, new product lines) and acquisition/wind-down probability

**Implementation Location:** `monitor.py` - change detection logic, alert thresholds

### 7. Financial Signal Focus by Age

**Current State:** Financial signals apply uniformly via `business_stability.py`. Some age-specific risk factors exist but financial focus is not age-differentiated.

**Recommended Enhancement:** Age-specific financial focus:
- Mature vendors: Emphasize multi-year financial health, credit history, bankruptcy/lien records, consistent growth patterns
- Young vendors: Prioritize recent funding rounds, burn-rate proxies, founder/background checks, early customer traction; treat limited transparency as elevated risk

**Implementation Location:** `business_stability.py` - financial penalty application

## Implementation Priority Matrix

| Enhancement | Impact | Complexity | Priority |
|-------------|--------|------------|----------|
| Inherent Risk Baseline Adjustment | High | Medium | High |
| Monitoring Cadence by Age | High | Low | High |
| Evidence Weighting by Age | Medium | Medium | Medium |
| Age-Specific Residual Risk Thresholds | High | Low | High |
| Incident Pattern Analysis by Age | Medium | High | Medium |
| Change Monitoring by Age | Medium | Medium | Medium |
| Financial Signal Focus by Age | Low | Low | Low |

## Conclusion

The current vendor age differentiation system provides a solid foundation through Business Stability scoring, maturity indexing, and evidence strength weighting. However, it does not fully leverage vendor age as a material risk differentiator across all risk dimensions as recommended by best practices.

The key enhancement opportunities are:
1. **Integrate age into inherent risk calculation** - Young vendors should have higher inherent risk baselines
2. **Implement age-based monitoring cadence** - Young vendors need more frequent monitoring
3. **Apply age-specific evidence weighting** - Sparse data for young vendors should elevate individual findings
4. **Adjust residual risk thresholds by age** - Lower acceptance bars for young vendors

These enhancements would align the system with the principle that "a clean OSINT profile on a 2-year-old vendor is inherently less reassuring than the same profile on a 20-year-old vendor with a long, observable history."