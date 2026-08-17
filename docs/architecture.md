# Complete System Explanation: OSINT TPRM Module

## Overview

This system is a comprehensive Third-Party Risk Management (TPRM) solution that uses Open Source Intelligence (OSINT) to assess vendor risk across multiple independent axes. It follows a penalty-based scoring model with strict architectural boundaries between different risk dimensions.

## Core Principles

### 1. Separation of Concerns
The system maintains strict boundaries between different risk dimensions:
- **Cybersecurity Posture**: Technical security controls and vulnerabilities
- **Confidence**: How much evidence we actually have (coverage)
- **Assurity**: Independent assurance and certifications
- **Business Stability**: Financial health and viability
- **Continuity**: Going-concern status and registry facts

### 2. Evidence-Based Scoring
- Every number must be backed by retrievable evidence
- Absence of data never subtracts from scores
- Missing data lowers confidence, never posture
- Ghost refusal when evidence is insufficient (<40% coverage)

### 3. Architectural Invariants
- Age and finance never affect cybersecurity posture
- Compliance gaps never affect technical posture
- "Unevidenced is not disproved" - baseline scores reflect uncertainty
- Natural persons are excluded (PII minimization)

## The Three Main Axes

### Axis 1: Cybersecurity Posture (0-100)

**Question**: How strong are this vendor's technical security controls?

**Calculation**:
```
Posture = 100 - (Total Penalties / Fixed Divisor)
```

**Components**:
- **Base score**: Every vendor starts at 100
- **Penalties**: Subtracted for each security issue found
- **Severity levels**: Critical (-40), High (-25), Medium (-8), Low (-3)
- **Categories**: 5 scoring categories covering different security domains
- **Ceiling**: Critical issues cap the maximum possible score

**Categories**:
1. **Breach & Compromise History** (3 signals)
   - Breach by data class
   - KEV-listed CVEs
   - NVD CVEs

2. **Attack Surface & Hygiene** (9 signals)
   - TLS version, certificate validity, HSTS, CSP, X-Frame-Options
   - DNSSEC, CAA, subdomain estate, stale hosts, weak issuance

3. **Identity & Email Security** (3 signals)
   - DMARC, SPF, DKIM

4. **Regulatory & Compliance** (2 signals)
   - Sanctions list (gate), regulator actions

**Key Features**:
- Diminishing returns on multiple similar issues (aggregation decay)
- One-ticket-one-penalty for root cause suppression
- Non-compensatory critical ceiling
- Age/frequency mitigation for old findings

### Axis 2: Confidence (Coverage)

**Question**: How much of the planned evidence did we actually collect?

**Calculation**:
```
Coverage = (Signals with findings) / (Planned signals)
Confidence Band: High (≥90%), Medium (≥70%), Low (<70%)
```

**Ghost Refusal**:
- Threshold: 40% coverage
- Below threshold: Score not published (Ghost refusal)
- Rationale: "Insufficient evidence" is adverse, not neutral

**Ceiling Ramp**:
- 90%+ coverage: No cap (can reach 100)
- 75%+ coverage: Max 97
- 60%+ coverage: Max 90
- 40%+ coverage: Max 80
- <40%: Not published

**Planned Signals**: 27 total
- 17 scoring signals (drive posture)
- 10 context signals (coverage only, no posture impact)

**Age Adjustment**:
- Assurance multiplier can adjust confidence based on operational history
- Young vendors get slight confidence reduction
- Old vendors get slight confidence boost
- Applied via multiplier, not threshold shifts

### Axis 3: Assurity (0-100)

**Question**: How much independent assurance does this vendor actually have?

**Calculation**:
```
Assurity = 100 * sigmoid(Intercept + Credits - Gap Penalties)
```

**Parameters**:
- Intercept: -1.2 (baseline ~23/100 with no observable assurance)
- Scale: 1.0 (sigmoid steepness)
- Gamma: 0.8 (compliance gap penalty multiplier)

**Credit Sources** (positive evidence):
- Registry-corroborated certifications: +1.4
- Substantive security reports: +0.9
- Bug bounty programs: +0.8
- Detailed policy disclosure: +0.6
- DPO and security contact: +0.4
- Valid DNSSEC: +0.3
- Security.txt present: +0.2
- CAA present: +0.2
- Claimed-unverified certifications: +0.2

**Gap Penalties** (only thing that subtracts):
- Compliance gaps: -0.8 each
- Applied when vendor claims framework but fails controls

**Independent Verification**:
1. **Trust Collector** (reliability 0.5): Self-reported claims from vendor websites
2. **Registry Lookup** (reliability 0.8): Official registry verification
3. **Multi-source corroboration**: Cross-check claims against independent data
4. **Evidence chain**: Every finding carries source, reliability, and audit trail

**Key Principle**: Absence never subtracts. A vendor with no observable assurance sits at baseline because they're unevidenced, not because they failed.

## Additional Axes

### Business Stability (0-100)

**Question**: How financially healthy and viable is this vendor?

**Calculation**:
```
Business Stability = Base Score (Age) - Financial Penalties + Survivorship Bonuses
```

**Age Base Scores**:
- Startup (<2 years): 92
- Young (2-5 years): 94
- Established (5-10 years): 96
- Mature (10-20 years): 98
- Veteran (20+ years): 100
- Unknown: 95

**Financial Penalties**:
- Historical insolvency: -5 to -20 (depending on recency)
- Revenue decline: -15
- High debt-to-equity (>3x): -10
- Negative cash flow: -15

**Age Multipliers** (amplify penalties for young vendors):
- Startup: 1.5x penalties
- Young: 1.2x penalties
- Established: 1.0x (neutral)
- Mature: 0.9x (reduced)
- Veteran: 0.8x (proven stability)

**Gate Logic**: Active insolvency proceedings BLOCK scoring entirely

**OSINT Limitations**:
- Observable: Legal insolvency, operating history
- Not observable: Revenue trends, debt ratios, cash flow (require paid sources)
- UI must disclose these limitations honestly

### Continuity (Going-Concern Status)

**Question**: Is this vendor actively operating as a going concern?

**Standing Levels**:
- **Sound**: Active and in good standing
- **Watch**: Monitoring advised
- **Impaired**: Financial distress indicators
- **Ceased**: Dissolved, liquidated, or out of business
- **Unknown**: No registry coverage for jurisdiction

**Data Sources**:
- Entity registers (Companies House, SEC, etc.)
- Gazette notices (insolvency, winding-up)
- Court records (bankruptcy petitions)
- Official registry databases

**Key Principle**: Disclosed, never scored. Four registry bands cannot support hundred-point precision.

## The Scoring Pipeline

### 1. Data Collection (Collectors)

**Collector Types**:
- **Technical collectors**: TLS, DNS, headers, certificates
- **Vulnerability collectors**: NVD, KEV, HIBP breaches
- **Registry collectors**: Companies House, EDGAR, OpenCorporates
- **Financial collectors**: Insolvency notices, court records
- **Transparency collectors**: Trust pages, security.txt

**Reliability Scoring**:
- 1.0: Cryptographically anchored (CT logs, DNSSEC)
- 0.9: Official registries (government sources)
- 0.8: Commercial APIs with validation
- 0.5: Self-reported (vendor websites)
- Lower: Unverified or secondary sources

**Rate Limiting & Politeness**:
- Per-source rate limiters
- User-Agent identification
- robots.txt compliance
- Retry with backoff for transient failures

### 2. Evidence Processing

**Normalization**:
- All findings converted to `NormalizedFinding` format
- Standardized signal names and band keys
- Evidence IDs assigned for audit trail
- Source reliability preserved

**Deduplication**:
- Root cause suppression (one ticket, one penalty)
- Signal deduplication across collectors
- Most reliable source preferred

### 3. Score Calculation

**Engine Process**:
1. Calculate coverage (confidence)
2. Apply assurance multiplier if available
3. Calculate category penalties
4. Apply aggregation decay (diminishing returns)
5. Calculate overall posture
6. Apply ceiling if critical issues found
7. Determine grade and confidence band

**Posture Calculation**:
```
For each category:
  - Apply penalties for findings
  - Cap category damage at 100
  - Apply aggregation decay for multiple issues

Overall posture:
  - Sum capped category penalties
  - Divide by fixed divisor (2.86)
  - Subtract from 100
  - Apply ceiling if critical issue present
```

### 4. Quality Gates

**Ghost Refusal**:
- Coverage < 40%: Score not published
- Clear adverse messaging
- Prevents false sense of security

**Sanctions Gate**:
- Sanctions list match: Complete block
- No score published
- Requires human adjudication

**Insolvency Gate**:
- Active insolvency: Business Stability blocked
- Historical insolvency: Scored with penalty

## Grade System

**Grade Boundaries**:
- A: 85-100 (Strong posture)
- B: 70-84 (Good posture with minor issues)
- C: 50-69 (Moderate risk, multiple issues)
- D: 30-49 (High risk, serious issues)
- F: 0-29 (Critical risk, multiple severe issues)

**Critical Ceiling**:
- Any critical finding caps maximum score at 49
- Cannot grade better than F with critical issues
- Non-compensatory: one critical cannot be diluted away

## Configuration-Driven Design

**scoring.yaml Structure**:
- Version tracking (major changes break comparability)
- Severity penalties (configurable point values)
- Category definitions (signals and bands)
- Confidence thresholds (refuse_below, bands)
- Assurity credits (positive evidence values)
- Business stability parameters (age bands, penalties)
- Compliance frameworks (sector obligations)

**Key Invariants**:
- 100 = strongest posture, 0 = weakest (direction convention)
- Four severity penalties must be defined
- Sanctions must be a gate, not a grade
- Excluded signals documented (natural persons excluded)

## API Architecture

**Main Endpoints**:
- `POST /api/vendors/score` - Initiate scoring job
- `GET /api/vendors/{ref}` - Get full score record
- `GET /api/vendors/{ref}/findings` - Get detailed findings
- `GET /api/vendors/{ref}/evidence/{id}` - Get raw evidence receipt
- `GET /api/vendors/{ref}/stability` - Business Stability score
- `GET /api/vendors/{ref}/continuity` - Going-concern status
- `GET /api/vendors/{ref}/assurity` - Independent assurance
- `GET /api/portfolio` - All vendors overview

**Progress Streaming**:
- Server-Sent Events (SSE) for real-time progress
- Events: collecting, collector_done, scoring, done
- Client can show progress bar per collector

## Frontend Architecture

**Main Pages**:
- **Assess**: Vendor scoring interface
- **VendorPage**: Detailed vendor scorecard
- **UseCases**: Scenario-based validation (20 test scenarios)
- **Portfolio**: Multi-vendor overview

**Key Components**:
- **BusinessStabilityCard**: Financial health with OSINT caveats
- **AssurityDisplay**: Independent assurance breakdown
- **PostureDisplay**: Technical security posture
- **ConfidenceIndicator**: Evidence coverage visualization

**UI Principles**:
- Every number must be explainable
- Evidence IDs link to source data
- Caveats displayed where applicable
- OSINT limitations disclosed honestly

## Data Model

**Core Entities**:
- **Vendor**: name, domain, criticality, size band
- **Score**: posture, confidence, grade, blocked/refused
- **Finding**: signal, band, severity, evidence_id
- **Evidence**: raw source data, hash-stamped
- **Continuity**: going-concern status, registry flags
- **Assurity**: independent assurance score, inputs
- **BusinessStability**: financial health, age band, penalties

**Storage**:
- Postgres-only (no local file fallback)
- Evidence trail is reconstructible months later
- Hash-stamped receipts for auditability
- Connection pooling for performance

## Testing & Validation

**Test Coverage**:
- Collector tests (each source independently)
- Engine tests (scoring calculations)
- Integration tests (full pipeline)
- Scenario tests (vendor comparison cases)

**Validation Rules**:
- No signal appears in two categories
- Compliance gaps have proper framework assertions
- Age never affects posture
- Financial metrics never affect posture
- Ghost refusal thresholds enforced

## Operational Considerations

**API Keys Required**:
- NVD API Key (CVE data, rate limits)
- Cert Spotter Token (CT logs, backup)
- OTX API Key (passive DNS)
- Companies House Key (UK registry)
- Registry Lookup Key (global backup)

**Rate Limits**:
- Per-source limiters prevent abuse
- Backoff retry for transient failures
- Graceful degradation when keys missing

**Coverage Issues**:
- Missing API keys → empty findings → lower coverage
- Jurisdiction limitations → some signals unavailable
- Collector failures → specific gaps in evidence
- Fix: Add API keys, check logs, verify domain resolution

## Security & Privacy

**PII Minimization**:
- Natural persons excluded from scoring
- Named-person emails stripped
- Only role addresses kept (security@, dpo@)
- No individual credit checks

**Data Sources**:
- Only public or lawfully accessible data
- Respects robots.txt
- User-Agent identification
- Terms of service compliance

**Evidence Integrity**:
- Hash-stamped receipts
- Immutable evidence store
- Reconstructible audit trail
- Source attribution for every finding

## Summary

This system provides a comprehensive, evidence-based approach to third-party risk assessment by:

1. **Separating risk dimensions** - posture, confidence, assurity, financial health
2. **Using real evidence** - every number backed by retrievable data
3. **Applying consistent logic** - penalty-based model with clear rules
4. **Maintaining transparency** - evidence IDs, source reliability, caveats
5. **Respecting boundaries** - age/finance never affect technical posture
6. **Admitting limitations** - OSINT constraints disclosed honestly

The result is a defensible, auditable risk assessment that buyers can trust and vendors can verify.