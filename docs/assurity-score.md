# Why "No Gaps" Doesn't Mean Equal Assurity Scores

## The Short Answer
**"No gaps observed" only means the vendor didn't contradict their own claims. It does NOT mean they have maximum positive assurance.**

Assurity is driven by the **positive credits** a vendor *actually has*, not just the absence of contradictions.

## The Math Behind the Score

Your Assurity formula (from `assurity.py`):
```
Assurity = 100 * sigmoid( A0 + SUM(positive credits) - SUM(gap penalties) )
```

Where:
- **A0 (Intercept)**: `-1.2` (baseline - a vendor with zero observable assurance sits at ~23/100)
- **Gap Penalties**: `0` (since you noted "no gaps observed")
- **Positive Credits**: This is the ONLY variable left

### Score Breakdown
To get a score of **69/100**:
```
100 * sigmoid(-1.2 + 2.0) = 100 * sigmoid(0.8) ≈ 69
```
Required credit sum: **~2.0**

To get a score of **73/100**:
```
100 * sigmoid(-1.2 + 2.2) = 100 * sigmoid(1.0) ≈ 73
```
Required credit sum: **~2.2**

The 4-point difference is explained by a **0.2 credit difference** - as simple as one vendor having `security_txt: present` while the other doesn't.

## Available Credits (from scoring.yaml)

| Signal | Band | Credit Value |
|--------|------|-------------|
| cert_posture | registry_corroborated | 1.4 |
| cert_posture | claimed_unverified | 0.2 |
| reporting_posture | substantive | 0.9 |
| reporting_posture | partial | 0.3 |
| program_disclosure | detailed_policies | 0.6 |
| program_disclosure | marketing_only | 0.1 |
| vd_program | bug_bounty | 0.8 |
| vd_program | security_txt_only | 0.3 |
| contactability | dpo_and_security_contact | 0.4 |
| contactability | partial | 0.1 |
| security_txt | present | 0.2 |
| dnssec | valid | 0.3 |
| caa | present | 0.2 |

## Example Scenarios

### Vendor A (Score: 73)
- cert_posture = registry_corroborated (+1.4)
- program_disclosure = detailed_policies (+0.6)
- security_txt = present (+0.2)
- **Total Credits: 2.2** → Score: 73

### Vendor B (Score: 69)
- cert_posture = registry_corroborated (+1.4)
- program_disclosure = detailed_policies (+0.6)
- *(Missing security_txt)*
- **Total Credits: 2.0** → Score: 69

Both have "no gaps observed" but Vendor A has one additional positive credit.

## The Dental Checkup Analogy

Think of Assurity like a dental checkup:
- **"No gaps observed"** = You have no cavities. (Great! Nothing is subtracting from your score.)
- **"Positive credits"** = You also floss daily, use fluoride, and get regular cleanings.

A person with no cavities but who never brushes will still get a mediocre score. A person with no cavities *and* excellent hygiene gets a high score.

Similarly:
- A vendor with no compliance gaps but no independent certifications: lower Assurity
- A vendor with no gaps *and* a SOC 2 report: higher Assurity

## How to Verify This in Your System

The `AssurityReport` object contains an `inputs` array that shows exactly which signals contributed credits. Each input shows:
- `signal`: The assurance signal (e.g., "security_txt")
- `band_key`: The observed value (e.g., "present")
- `credit`: The credit value (e.g., 0.2)
- `evidence_id`: Link to the source evidence

### Check the API Response
Look at the assurity endpoint response for both vendors:

```json
{
  "score": 73,
  "observed_signals": 4,
  "inputs": [
    {
      "signal": "cert_posture",
      "band_key": "registry_corroborated", 
      "credit": 1.4,
      "evidence_id": "abc123"
    },
    {
      "signal": "program_disclosure",
      "band_key": "detailed_policies",
      "credit": 0.6,
      "evidence_id": "def456"
    },
    {
      "signal": "security_txt",
      "band_key": "present",
      "credit": 0.2,
      "evidence_id": "ghi789"
    }
  ],
  "gap_count": 0,
  "gap_penalty": 0.0
}
```

## How We Independently Check Assurity

The system has multiple layers of independent verification to distinguish between vendor claims and verified facts:

### 1. Self-Reported Claims (Trust Collector)
**Source**: `trust_collector.py`  
**Reliability**: 0.5 (self-reported, claim not evidence)

The trust collector scans vendor websites for security/trust pages and extracts:
- **Certifications claimed**: ISO 27001, SOC 2, PCI DSS, etc. (regex pattern matching)
- **Program disclosure**: Detailed policies vs marketing-only content
- **Contactability**: Role-based security contacts (security@, dpo@, etc.)
- **Reporting posture**: Substantive reports vs partial disclosure

**Key features**:
- Honors robots.txt before fetching any pages
- PII minimization: only role addresses kept, named-person emails stripped
- Explicitly marked as "SELF-REPORTED claim — corroborate against cert registry where possible"
- Lower reliability score (0.5) reflects this is a claim, not verified fact

### 2. Registry Verification (Registry Lookup Collector)
**Source**: `registry_lookup_collector.py`  
**Reliability**: 0.80 (backup source with varying data quality)

Provides independent verification of:
- **Incorporation dates**: Cross-checks vendor claims against official registry data
- **Company status**: Active, dissolved, in administration, etc.
- **Jurisdiction**: Country and legal entity information
- **Company numbers**: Official registration identifiers

**Key features**:
- Access to 521M entities across 309 jurisdictions
- Backup when primary jurisdiction-specific collectors fail
- API key required (returns `empty` without key, lowering coverage)
- Higher reliability score (0.80) as it's from official registries

### 3. Multi-Source Corroboration
The system cross-references findings across multiple collectors:

**Example Certification Verification Flow**:
1. **Trust collector** finds vendor claims "SOC 2" on their website
2. **Companies House / OpenCorporates** confirms the legal entity exists
3. **Future collectors** could verify against official certification registries
4. **Assurity scoring** applies different credits:
   - `claimed_unverified`: +0.2 credit (self-reported only)
   - `registry_corroborated`: +1.4 credit (independently verified)

### 4. Evidence Chain Integrity
Every finding carries:
- **Source**: Which collector produced it (trust, registry_lookup, etc.)
- **Reliability score**: 0.0-1.0 indicating source trustworthiness
- **Evidence ID**: Link to raw receipt for audit trail
- **Locator**: URL or registry reference for verification
- **Notes**: Explicit caveats about data source limitations

### 5. Compliance Gap Detection
The system independently checks if vendors fail the controls of frameworks they claim:

**Example**: Vendor claims ISO 27001
- System checks for required security controls
- If missing controls found → **Compliance Gap** (penalty applied)
- This measures claim reliability, not security posture

## System Design Validation

This behavior is **exactly as designed**:

1. **Absence never subtracts** - enforced in code (negative credits rejected at load)
2. **Baseline is low (~23/100)** - because "unevidenced is not disproved"
3. **Only compliance gaps subtract** - when a vendor claims a framework but fails controls
4. **Positive evidence drives the score up** - independent certifications, bug bounties, etc.
5. **Multi-source verification** - claims are cross-checked against independent registries
6. **Reliability-weighted scoring** - self-reported claims get lower credit than verified facts

## UI Improvement Recommendation

Consider adding a "What earned this score" breakdown in the Assurity display to show users exactly which positive signals are driving the difference between vendors with equal gap counts, including source reliability indicators.

The system is working correctly - it's measuring the **presence of positive, independent evidence**, not just the absence of contradictions, with multiple layers of verification to distinguish claims from verified facts.