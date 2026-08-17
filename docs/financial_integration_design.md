# Financial Data Integration Design (Phase 1.3)

## Overview
This document defines the integration points for financial data collectors into the existing TPRM pipeline, including collector mapping, priority chains, API endpoints, and database schema considerations.

## Collector Mapping: Domain → Registry Number

### Existing Collectors for Entity Resolution
The following existing collectors already provide registry numbers that financial collectors can leverage:

| Existing Collector | Provides | Target Financial Collectors |
|-------------------|----------|----------------------------|
| `gleif_collector` | LEI, registration numbers | OpenCorporates, SEC EDGAR |
| `abn_collector` | Australian Business Number (ABN) | ASIC insolvency |
| `companies_house_collector` | UK company number | Companies House insolvency |
| `wikidata_collector` | Various registry IDs | Regional registries |

### New Financial Collectors and Their Inputs

| Collector | Primary Input | Fallback Input | Priority |
|-----------|--------------|----------------|----------|
| `companies_house_collector` | UK company number | Company name + domain | 1 (UK) |
| `sec_edgar_collector` | CIK (from LEI or ticker) | Company name + domain | 1 (US public) |
| `open_corporates_collector` | Company name + domain | LEI | 2 (global) |
| `registry_lookup_collector` | Company name + domain | Registry number | 3 (global backup) |
| `eu_insolvency_collector` | Company name + jurisdiction | Registry number | 1 (EU) |
| `german_insolvency_collector` | Company name + HRB | Registry number | 1 (Germany) |
| `canada_bankruptcy_collector` | Company name | Business number | 1 (Canada) |
| `asic_insolvency_collector` | ACN/ABN | Company name | 1 (Australia) |

## Collector Priority and Fallback Chain

### Primary Strategy: Jurisdiction-Based Routing
1. Determine vendor jurisdiction from existing `VendorProfile.country`
2. Route to primary collector for that jurisdiction
3. If primary fails, fall back to global collectors
4. If all fail, return `empty` (lowers confidence, never posture)

### Fallback Chain by Jurisdiction

#### United Kingdom
1. `companies_house_collector` (authoritative UK registry)
2. `open_corporates_collector` (global aggregator)
3. `registry_lookup_collector` (backup global)

#### United States (Public Companies)
1. `sec_edgar_collector` (SEC EDGAR - authoritative for public companies)
2. `open_corporates_collector` (for private company data)
3. `registry_lookup_collector` (backup)

#### European Union
1. `eu_insolvency_collector` (official EU insolvency register)
2. National registry collector (if available for specific country)
3. `open_corporates_collector` (global aggregator)

#### Germany
1. `german_insolvency_collector` (official German insolvency register)
2. `open_corporates_collector` (global aggregator)

#### Canada
1. `canada_bankruptcy_collector` (OSB official bankruptcy records)
2. `open_corporates_collector` (global aggregator)

#### Australia
1. `asic_insolvency_collector` (ASIC official records)
2. `open_corporates_collector` (global aggregator)

#### Global/Unknown Jurisdiction
1. `open_corporates_collector` (primary global source)
2. `registry_lookup_collector` (backup global)

### Collector Configuration
Add to `config.py`:

```python
# Financial collector configuration
financial_collector_priority: dict[str, list[str]] = {
    "uk": ["companies_house", "open_corporates", "registry_lookup"],
    "us": ["sec_edgar", "open_corporates", "registry_lookup"],
    "eu": ["eu_insolvency", "open_corporates", "registry_lookup"],
    "de": ["german_insolvency", "open_corporates", "registry_lookup"],
    "ca": ["canada_bankruptcy", "open_corporates", "registry_lookup"],
    "au": ["asic_insolvency", "open_corporates", "registry_lookup"],
    "global": ["open_corporates", "registry_lookup"],
}
```

## API Endpoints Design

### New Endpoints

#### GET /api/vendors/{ref}/financial
Retrieve the financial profile for a vendor.

**Response Schema:**
```json
{
  "vendor_ref": "atlassian",
  "incorporation_date": {
    "value": "2002-06-27",
    "source": "open_corporates",
    "locator": "https://opencorporates.com/companies/au/...",
    "fetched_at": "2026-08-05T14:00:00Z",
    "as_of": "2002-06-27"
  },
  "company_status": {
    "value": "active",
    "source": "companies_house",
    "locator": "https://find-and-update.company-information.service.gov.uk/company/...",
    "fetched_at": "2026-08-05T14:00:00Z"
  },
  "registry_number": {
    "value": "123456789",
    "source": "companies_house",
    "locator": "https://find-and-update.company-information.service.gov.uk/company/123456789",
    "fetched_at": "2026-08-05T14:00:00Z"
  },
  "insolvency_status": {
    "value": "none",
    "source": "companies_house",
    "fetched_at": "2026-08-05T14:00:00Z"
  },
  "insolvency_records": [],
  "financial_metrics": [
    {
      "period_end": "2024-06-30",
      "period_type": "annual",
      "revenue": 4000000000,
      "revenue_currency": "USD",
      "net_income": 800000000,
      "total_assets": 10000000000,
      "total_liabilities": 3000000000,
      "long_term_debt": 1000000000,
      "cash_and_equivalents": 2000000000,
      "equity": 7000000000,
      "source": "sec_edgar",
      "source_version": "0001193125-24-123456",
      "locator": "https://www.sec.gov/Archives/edgar/data/...",
      "fetched_at": "2026-08-05T14:00:00Z"
    }
  ],
  "operating_years": 24.1,
  "age_band": "veteran",
  "debt_to_equity": 0.14,
  "revenue_trend": "growing",
  "cash_flow_trend": "positive",
  "insolvency_gate": false,
  "insolvency_gate_reason": null,
  "computed_at": "2026-08-05T14:00:00Z"
}
```

#### GET /api/vendors/{ref}/stability
Retrieve the Business Stability score for a vendor.

**Response Schema:**
```json
{
  "vendor_ref": "atlassian",
  "score": 95,
  "base_score": 100,
  "age_band": "veteran",
  "penalties": {},
  "bonuses": {
    "survivorship": 10.0
  },
  "gate_triggered": false,
  "gate_reason": null,
  "confidence_adjusted": 0.95,
  "contingency_plan_required": false,
  "computed_at": "2026-08-05T14:00:00Z"
}
```

**Gate Response (if insolvency active):**
```json
{
  "vendor_ref": "blocked-vendor",
  "score": null,
  "base_score": null,
  "age_band": "mature",
  "penalties": {},
  "bonuses": {},
  "gate_triggered": true,
  "gate_reason": "Active insolvency proceeding: liquidation (CASE-12345) in United Kingdom",
  "confidence_adjusted": null,
  "contingency_plan_required": true,
  "computed_at": "2026-08-05T14:00:00Z"
}
```

### Extended Existing Endpoints

#### GET /api/vendors/{ref}
Add `business_stability` field to existing vendor response:

```json
{
  "vendor_ref": "atlassian",
  "name": "Atlassian",
  "domain": "atlassian.com",
  "score": {
    "posture": 88,
    "grade": "A",
    "overall_confidence": 0.92,
    "confidence_band": "High",
    "blocked": false,
    "refused": false
  },
  "business_stability": {
    "score": 95,
    "age_band": "veteran",
    "gate_triggered": false,
    "confidence_adjusted": 0.95
  },
  // ... existing fields
}
```

## Database Schema Changes

### New Tables

#### financial_profiles
Stores the financial profile for each vendor (similar to vendor_profiles).

```sql
CREATE TABLE financial_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_ref VARCHAR(255) NOT NULL,
    incorporation_date JSONB,
    company_status JSONB,
    registry_number JSONB,
    registry_jurisdiction JSONB,
    insolvency_status JSONB,
    insolvency_records JSONB,
    financial_metrics JSONB,
    operating_years FLOAT,
    age_band VARCHAR(50),
    debt_to_equity FLOAT,
    revenue_trend VARCHAR(50),
    cash_flow_trend VARCHAR(50),
    insolvency_gate BOOLEAN DEFAULT FALSE,
    insolvency_gate_reason TEXT,
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (vendor_ref)
);

CREATE INDEX idx_financial_profiles_vendor_ref ON financial_profiles(vendor_ref);
CREATE INDEX idx_financial_profiles_computed_at ON financial_profiles(computed_at DESC);
```

#### business_stability_scores
Stores the Business Stability score history (similar to scores table).

```sql
CREATE TABLE business_stability_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_ref VARCHAR(255) NOT NULL,
    score INTEGER,
    base_score INTEGER,
    age_band VARCHAR(50),
    penalties JSONB,
    bonuses JSONB,
    gate_triggered BOOLEAN DEFAULT FALSE,
    gate_reason TEXT,
    confidence_adjusted FLOAT,
    contingency_plan_required BOOLEAN DEFAULT FALSE,
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_business_stability_scores_vendor_ref ON business_stability_scores(vendor_ref);
CREATE INDEX idx_business_stability_scores_computed_at ON business_stability_scores(computed_at DESC);
```

### No Changes to Existing Tables
The existing tables (scores, vendor_profiles, evidence, findings) remain unchanged to maintain backward compatibility. Business Stability is a separate axis that does not modify the cybersecurity scoring data.

## Pipeline Integration

### Pipeline Order Extension
Add financial collection phase after existing collectors but before scoring:

```
entity-resolution → collect (existing + financial) → EVIDENCE STORE
→ normalize → score (cybersecurity) → business_stability_score
→ persist Score → persist BusinessStabilityScore
```

### Progress Events
Add SSE progress events for financial collectors:

```python
await _emit(progress, "financial_collecting", {
    "total": len(financial_collectors),
    "sources": [c.source for c in financial_collectors]
})

await _emit(progress, "financial_collector_done", {
    "source": result.source,
    "status": result.status,
    "evidence_id": evidence.id,
})

await _emit(progress, "business_stability_scoring", {})

await _emit(progress, "business_stability_done", {
    "score": result.score,
    "gate_triggered": result.gate_triggered,
})
```

## Error Handling

### Collector Failure Strategy
- Individual collector failure: Log warning, continue to next in fallback chain
- All collectors in chain fail: Return `empty` status, lower confidence
- Gate triggered: Return early with gate status, do not compute score

### Data Quality Validation
- Validate required fields (e.g., incorporation_date must be valid date)
- Handle missing data gracefully (set to None, don't fail)
- Validate financial metrics (e.g., revenue must be positive number)
- Log data quality issues for monitoring

## Rate Limiting

### Per-Collector Rate Limits
Add to `config.py`:

```python
# Financial collector rate limits (requests per minute)
financial_rate_limits: dict[str, int] = {
    "companies_house": 600,  # Companies House API limit
    "sec_edgar": 10,  # SEC EDGAR fair access rule
    "open_corporates": 300,  # OpenCorporates free tier
    "registry_lookup": 60,  # Registry Lookup free tier
    "eu_insolvency": 60,  # EU e-Justice Portal
    "german_insolvency": 60,  # German insolvency register
    "canada_bankruptcy": 30,  # OSB search limit
    "asic_insolvency": 60,  # ASIC registry
}
```

### Global Rate Limiting
Use existing `RateLimiter` class with per-collector limits.

## Monitoring

### Collector Success Metrics
Track per-collector success rates and latency:

```python
financial_collector_metrics = {
    "companies_house": {"success_rate": 0.95, "avg_latency_ms": 250},
    "sec_edgar": {"success_rate": 0.98, "avg_latency_ms": 500},
    # ...
}
```

### Gate Trigger Monitoring
Alert on gate triggers (active insolvency):

```python
if gate_triggered:
    log.warning("Insolvency gate triggered for %s: %s", vendor_ref, gate_reason)
    # Send alert to procurement team
```

## Backward Compatibility

### Existing API Behavior
- Existing endpoints unchanged by default
- Business Stability data only added when explicitly requested via new endpoints
- Cybersecurity scoring logic completely unaffected
- Existing tests continue to pass without modification

### Feature Flag
Add feature flag to enable/disable Business Stability:

```python
business_stability_enabled: bool = True
```

When disabled, financial collectors are skipped and Business Stability endpoints return 503.

---

## Implementation record (v5.3.0 — shipped)

This design was implemented as specified above. What follows is the as-built detail this design
doc doesn't otherwise cover — scoring mechanics are documented in
[`methodology.md`](methodology.md) §5.2.1 and [`scoring_model.md`](scoring_model.md) §6.1; this is
the wiring.

**Scoring/longevity logic:** `app/business_stability.py` (`compute_business_stability`),
`app/longevity.py` (`age_band_from_years`, `base_age_score`, `confidence_adjustment`,
`survivorship_bonus`, `contingency_plan_required`).

**Frontend:**
- `BusinessStabilityCard.jsx` — financial health score, gate status, age band, metrics, contingency flags, registry facts
- `BusinessStabilityPair` (in `primitives.jsx`) — Business Stability as a second axis alongside posture, same confidence-pairing rule
- `FinancialDetailModal.jsx` — drill-down tabs: Overview, Trends, Ratios, Insolvency

**Tests:**
- `test_business_stability.py` — age bands, base/confidence/bonus scoring, gate logic, penalties
- `test_financial_integration.py` — collector fallback chains, SSE streaming, API structure, missing-key/timeout handling, rate limits
- `test_regression_cybersecurity.py` — confirms cybersecurity scoring and collector separation are unaffected
- `tests/fixtures/financial_validation_corpus.py` — five fixtures (active insolvency block, 2-year startup, 40-year veteran, declining mature company, historical insolvency)

**Deployment:** no schema changes beyond §"Database Schema Changes" above; findings land in the
existing evidence store under category `business_financial_stability`. Required env vars:
`OPENCORPORATES_KEY`, `REGISTRY_LOOKUP_KEY`, `CANADA_BANKRUPTCY_KEY` (see `backend/.env.example`).
