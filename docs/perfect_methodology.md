# Perfect Methodology — the enterprise-grade design, and what money actually buys

**Status:** design document · target state · **v2.1 — evidence lifecycle + operational closures**
**Date:** 26 July 2026
**Companions:** [`methodology.md`](methodology.md) (what is built) · [`doable_methodology.md`](doable_methodology.md) (the free-tier work plan) · [`review_response.md`](review_response.md) · [`roadmap.md`](roadmap.md) · [`scoring.yaml`](../scoring.yaml)

---

> **The question this answers.** *"If money wasn't a limitation, what would the ideal methodology look
> like?"*
>
> **The answer in one line.** Eleven stages in the **lifecycle of a piece of evidence** — resolve,
> collect, validate, enrich, interpret, weigh, score, benchmark, decide, monitor, explain — into which
> any source, free or commercial, plugs without changing a single stage.
>
> **The rule that governs every purchase.** **Buy observations, never verdicts.** A commercial feed
> enters as evidence with our severities under our published bands. It never enters as a score.
>
> **What does not change with budget.** The two axes, the sanctions gate, the no-natural-persons bright
> line, the immutable evidence store, the refusal to let machine learning determine a score, and the rule
> that **firmographics — including size — never enter the arithmetic**. Those are not cost-saving
> compromises. They are the methodology.

---

## What changed in v2, and why

**v1 of this document was organised by security domain** — *Vendor Profiling → Attack Surface →
Technical Security → Threat Intelligence → Business → Supply Chain*. That is how a security team
thinks, and it is the wrong spine for a methodology, for one specific reason:

> **A source-shaped pipeline appears to change every time you add a source.** If "Attack Surface" is a
> *stage*, then buying Censys looks like a pipeline change. If it is an *evidence bucket*, buying Censys
> is one more collector emitting observations into a pipeline that does not move.

**The decisive argument is that the shipped code was already built the second way, and v1 of this
document was misdescribing it.** From `models.py`, quoted verbatim:

```
Pipeline order (scoring.yaml PIPELINE ORDER; not negotiable):
    entity-resolution -> collect -> EVIDENCE STORE (first) -> normalize
    -> finding modifiers -> signal -> subcategory mean -> category mean
    -> GATE -> overall mean -> KNOCKOUT FLOOR -> confidence + quadrant
```

And from `collectors/base.py`: *"Every collector returns the same `CollectorResult` envelope, so the
scoring engine never knows or cares where data came from."* That envelope **is** the source-independence
the restructure is asking for, and it already exists.

**Three amendments made to the proposed structure**, each for a reason the linear diagram hides:

1. **The pipeline is a cycle, not a line.** Entity resolution runs **twice** — once before collection to
   pick the subject, once *after* collection to derive confidence from what the registries actually said
   (`pipeline.py`: *"ENTITY RESOLUTION, second pass. Confidence can only be derived once the registries
   have answered"*). Monitoring and dispute both loop **backwards** into evidence. Drawing them as
   forward steps 10 and 11 loses the most important structural fact about the system.
2. **Gates are cross-cutting, not a step inside scoring.** `entity_ambiguous` fires at Stage 1/4;
   `sanctions` fires between Stage 5 and Stage 7. Both **emit nothing**. A gate is not a stage in a
   pipeline — it is a stop condition on several of them.
3. **Evidence buckets organise the source register, not the model.** *"Attack Surface"* and
   *"Vulnerabilities"* are still source-shaped one level up, and real sources span them — Censys supplies
   attack surface **and** TLS **and** certificates. The stable taxonomy is the **category/signal** in
   `scoring.yaml`; the buckets are shelving for the register in Stage 2.

Nothing from v1 was deleted. The mapping is in the appendix.

## What changed in v2.1

v2 restructured the document around the evidence lifecycle. v2.1 closes the operational gaps v2 left
implicit — each now built or specified rather than an open thread:

1. **Size is collected *after* the score exists, never on the scoring form.** It only ever picks a
   cohort, so a box beside the Score button would wrongly imply it moves the grade. When public sources
   publish no size, the benchmark card offers to add one — and says plainly it buys a comparison, not a
   different number (§1, §8). *Built.*
2. **Benchmarking gains a stability state and role-aware depth.** A cohort that has only just cleared the
   minimum is published as **provisional**, not treated as settled; and the peer strip's depth follows the
   reader's role (§8, Presentation). *Built (minimal provisional signal; the full time-window state
   machine below is the target).*
3. **The projection layer is specified with its live flags and its action surface** — decision recording,
   dispute, export — not just the five questions (Presentation). *Built.*
4. **Commercial data is framed as increasing the *frequency* of contested findings**, which makes the
   dispute loop a prerequisite, not a later addition (§9).
5. **Language tightened** so firmographics — size especially — can never be misread as score inputs (Rule
   12, §1, §8, §17).

The arithmetic, the gates, the two-axis model and *buy observations, never verdicts* are untouched.

---

## Contents

| Part | Sections |
|---|---|
| **Cross-cutting rules** | The twelve that apply at every stage, plus the gates |
| **The lifecycle** | §1–§11 — the stages, with free vs commercial sourcing at each |
| **Presentation** | The projection layer — outputs, not a stage |
| **The money** | §12 — costs, budget scenarios, what to buy first |
| **The constraints** | §13 what stays fixed · §14 what money cannot buy · §15 legal traps in paid data |
| **The plan** | §16 maturity ladder · §17 design principles · Appendix: v1 → v2 stage mapping |

---

# Cross-cutting rules

**These are not a closing summary. They are preconditions on every stage below**, and a stage that
breaks one is wrong regardless of how well it performs.

| # | Rule | Enforced by |
|---|---|---|
| 1 | **Evidence before scoring.** The store is written before any normalisation | `pipeline.py` — `store.put()` precedes the engine |
| 2 | **Every observation is traceable** — source, timestamp, collector, raw payload, hash | `models.py` → `Evidence` |
| 3 | **Observations are immutable.** Nothing is edited; corrections are new rows | DB triggers reject UPDATE/DELETE |
| 4 | **Confidence is separate from posture**, always, with no API path returning a bare number | `models.py` → `Score` |
| 5 | **Missing evidence lowers confidence, never posture** | `empty` is a first-class status |
| 6 | **Scores are deterministic.** Same evidence, same clock, same score | Frozen 5-vendor regression corpus |
| 7 | **Commercial platforms provide observations, never verdicts** | Ingestion contract, §12 |
| 8 | **Natural persons are excluded** — entity-level only | `scoring.yaml` → `excluded_signals` |
| 9 | **AI never determines a score** | Read-layer fence, §11 |
| 10 | **Every published result is reconstructible** | Finding A — `ABN AMRO v Bathurst` |
| 11 | **Every deduction has a plain-language explanation** | Loader refuses to start without one |
| 12 | **Firmographics — industry, size, region, ownership — are context only.** They never enter the penalty arithmetic | `ScoringEngine.score()` never receives them; `_derive_cohort` is the only consumer |

**Gates — the thirteenth rule, which behaves differently from the others.** A gate does not adjust a
score; it **stops the pipeline and emits nothing**, routing to human adjudication.

| Gate | Fires at | Behaviour |
|---|---|---|
| `entity_ambiguous` | Stage 1 (pre) and Stage 4 (post-collection re-derivation) | Confidence < 0.5 → BLOCK. Never silently score the wrong company |
| `sanctions` | Between Stage 5 and Stage 7 | Any match → BLOCK, tuned for **recall**. Never a grade (Autonomous Sanctions Act s 16(7)) |

---

# The lifecycle

```
                          ┌──────────────────────────────┐
                          │        VENDOR (name/domain)   │
                          └───────────────┬──────────────┘
                                          ▼
                        ╔═════════════════════════════════╗
                        ║  1. ENTITY RESOLUTION (pre)     ║◀──────────┐
                        ╚═════════════════┬═══════════════╝           │
                                          ▼                            │
                        ╔═════════════════════════════════╗           │
                        ║  2. EVIDENCE COLLECTION         ║           │
                        ║     (n collectors, isolated)    ║           │
                        ╚═════════════════┬═══════════════╝           │
                                          ▼                            │
                        ╔═════════════════════════════════╗           │
                        ║  3. EVIDENCE VALIDATION         ║           │
                        ║     hash · store · immutable    ║           │
                        ╚═════════════════┬═══════════════╝           │
                                          ▼                            │
                        ╔═════════════════════════════════╗           │
                        ║  4. EVIDENCE ENRICHMENT         ║───────────┘
                        ║     re-resolve · corroborate    ║  entity confidence
                        ╚═════════════════┬═══════════════╝  re-derived here
                                          ▼
                        ╔═════════════════════════════════╗
                        ║  5. FINDING GENERATION          ║
                        ╚═════════════════┬═══════════════╝
                                          │
                        ┌─────────────────┴─────────────────┐
                        ▼                                   ▼
            ╔═══════════════════════╗          ╔═══════════════════════╗
            ║ 6. CONFIDENCE         ║          ║ 7. PENALTY SCORING    ║
            ║    ANALYSIS           ║          ║    (+ GATES, CEILING) ║
            ╚═══════════┬═══════════╝          ╚═══════════┬═══════════╝
                        │        never mixed               │
                        └─────────────────┬────────────────┘
                                          ▼
                        ╔═════════════════════════════════╗
                        ║  8. BENCHMARKING                ║
                        ║     interpretation, not maths   ║
                        ╚═════════════════┬═══════════════╝
                                          ▼
                        ╔═════════════════════════════════╗
                        ║  9. DECISION ENGINE             ║
                        ╚═══════┬═════════════════┬═══════╝
                                │                 │
                    ┌───────────┘                 └────────────┐
                    ▼                                          ▼
      ╔═════════════════════════╗              ╔═════════════════════════╗
      ║ 10. MONITORING          ║              ║  DISPUTE / REFUTE       ║
      ║     re-score on cadence ║              ║  vendor evidence in     ║
      ╚═══════════┬═════════════╝              ╚═══════════┬═════════════╝
                  │                                        │
                  └────────────► back to Stage 2 ◄─────────┘
                                          │
                                          ▼
                        ╔═════════════════════════════════╗
                        ║ 11. AI READ LAYER (fenced)      ║
                        ╚═════════════════════════════════╝
                                          ▼
                              PRESENTATION — 5 projections
```

**The two loops are the point.** Monitoring re-enters at collection on a cadence; a dispute re-enters
with vendor-supplied evidence. Both produce a **new immutable score** — neither ever edits the old one.

---

## Stage 1 — Entity Resolution

**Purpose.** Ensure every observation belongs to the correct organisation, **before** any assessment
begins. This is the accuracy ceiling of the whole system, and the AFA says so: automated tooling
*"requires human analysis in order to adjust the assessment, particularly for the most high-risk third
parties."*

### What resolution produces

| Field | Free source | Commercial | Note |
|---|---|---|---|
| Legal entity name | GLEIF, Wikidata | D&B | |
| LEI / ABN / ACN / CRN / DUNS | GLEIF · ABN Lookup · ASIC · Companies House | D&B DUNS | Hard identifiers — the cure for homonymy |
| Jurisdiction, countries of operation | GLEIF legal address | D&B, Moody's | Selects the registry adapter and industry profile |
| Industry (ANZSIC / SIC / NAICS) | ABN Lookup, Companies House, Wikidata P452 | D&B, S&P | Sets the peer cohort **and** the severity profile |
| Size — employees, revenue | Wikidata P1128/P2139; EDGAR/ASX if listed | **D&B, Moody's, S&P — the only real answer for private companies** | **Optional, and never required to score** — picks the cohort only; may be client-supplied *after* the score (§8) |
| Ownership / ultimate parent | Companies House PSC, ASIC | D&B linkage, Moody's Orbis | **FOCI** — mandatory under SOCI from ~mid-2028 |
| Public / private / PE-backed | Wikidata P414 + GLEIF | S&P Capital IQ | |
| **Criticality to the client** | **Client input — never inferred** | — | Not observable from outside. Ever |

### Three rules

1. **Firmographics are context, never score inputs.** They set the peer cohort and the industry profile.
   The moment revenue moves a penalty, the size bias returns through the front door — *coverage tracks
   company size, not company risk* ([`methodology.md`](methodology.md) §7.3).
2. **Entity-level only.** Ownership chains stop at corporate entities. **Paid feeds will happily sell
   you director and beneficial-owner data. The line does not move because a vendor will sell across it.**
3. **Resolution is derived, not asserted.** A caller-supplied confidence is an explicit override for
   testing or for recording an adjudicator's decision — never the normal path.

> **Size is deliberately not required here.** It is an optional, client-supplied fact used only to form
> the peer cohort (§8), so it never appears on the scoring form. Public sources often lack it, and the
> buyer frequently knows the *contracting entity* better than Wikidata does — the 40-person local
> subsidiary they sign with, not the 8,000-person global parent. When it is missing, the benchmark card
> offers to add it *after* the score, where it plainly buys a comparison and not a different grade.

**Gate:** `resolution_confidence < 0.5` → **BLOCKED**. The Vanta case is the warning: EDGAR matched a
*different* US-listed company and silently attributed a stranger's financials. **More sources make this
failure mode more likely, not less.**

**Output:** `VendorProfile` — every field carrying its own source and `fetched_at`.

---

## Stage 2 — Evidence Collection

**Purpose.** Run n independent collectors, each returning the **same envelope**. This is the stage where
budget changes what is knowable — and the only stage it changes.

### The contract that makes source-independence real

```python
class CollectorResult(BaseModel):
    source: str                 # collector id
    vendor_ref: str
    status: Literal["ok", "empty", "error", "timeout", "skipped_tos"]
    fetched_at: datetime        # timezone-aware, mandatory
    source_version: str | None  # KEV catalogVersion, ETag, list date — for reconstruction
    raw: dict | None            # verbatim payload → evidence store
    findings: list[Finding]
    reliability: float          # from the source assessment, never invented
```

Every collector — free or a A$300k feed — returns this. **Failure isolation lives in the base class:** a
timeout becomes `status="timeout"`, an exception becomes `error`, nothing-found becomes `empty`. One dead
source cannot sink an assessment.

**`empty` is a first-class result, not a failure.** The source was reached and had nothing for this
vendor. It is **stored**, and it lowers *confidence*, never *risk*.

### The evidence register

Buckets are **shelving for sources, not model structure**. A source may sit in several.

#### Internet / perimeter

| Free ✅ | Commercial 💰 |
|---|---|
| Certificate Transparency (crt.sh + Cert Spotter) · DNS (SPF/DKIM/DMARC/MX/CAA/DNSSEC) · own TLS handshake · HTTP security headers · `security.txt` · RDAP | SecurityTrails (historical DNS, passive DNS, WHOIS history) |

**Honest limit:** CT shows certificates **issued**, not hosts **live**. And CT is a genuine single point
of failure — a crt.sh outage zeroes Digital Footprint and tips a clean vendor to *The Ghost*.

#### Attack surface — **the largest gap between free and paid**

| Free ✅ | Commercial 💰 | What money buys |
|---|---|---|
| Subdomain names via CT; netblocks via RIR RDAP | **Censys** · **Shodan Enterprise** · **BinaryEdge** · **RiskIQ / Defender EASM** | Open ports · exposed services · **service versions** · IP-level estate · cloud attribution |

> **The legal point most people get backwards.** v1 performs no active scanning — deliberately, to stay
> clear of unauthorised-access exposure (Criminal Code Act 1995 (Cth) Part 10.7) and the ToS traps that
> permanently excluded SSL Labs and VirusTotal. **Buying Censys or Shodan data is *legally safer* than
> scanning yourself:** they scan under their own legal posture and licence you the observations. You get
> open-port visibility without ever sending a packet at a vendor you have no relationship with.
>
> **Highest value per dollar, lowest cost to defensibility.** Buy this first.

#### Vulnerability

| Free ✅ | Commercial 💰 |
|---|---|
| CISA KEV · NVD · EPSS | **VulnCheck** — KEV enrichment, exploit availability, **version-level matching** |

**Honest limit:** KEV and NVD are **product-line name matches**. They prove *"this product line had a
CVE"*, not *"this vendor is unpatched"* — which is exactly why v1 penalises them but correctly refuses
to apply the critical ceiling. Version-level matching is what makes them ceiling-eligible.

#### Threat & credential

| Free ✅ | Commercial 💰 |
|---|---|
| HIBP `/breaches` | **SpyCloud** · **Constella** (credential recapture) · **KELA** (initial-access brokers, extortion listings) · **Recorded Future** · **Mandiant** · **CrowdStrike** · **Microsoft Defender TI** |

**Honest limit:** HIBP **skews consumer-facing**. Snowflake's 2024 B2B incident never entered it — a real
breach at a real vendor returns clean on the free stack. v1 handles that honestly (a clean receipt lowers
confidence, never signals safety), but honesty about a blind spot is not the same as seeing.

> **The dark-web fence — the most important ingestion rule in this document.** Credential dumps and
> infostealer logs are **personal information about a vendor's employees**. APP 3 (collection) and APP 10
> (quality) apply, and the §4.2 bright line already excludes natural persons. **Buying a feed does not
> create a lawful basis to hold that data.**
>
> **Aggregate at ingestion, not at display.** *"47 credentials associated with `@vendor.com` recaptured
> in the last 90 days, 12 with session cookies"* is an organisational hygiene finding. An individual's
> credential record is a privacy liability you have paid money to acquire. This is a hard architectural
> boundary in the collector, not a UI filter.

#### Governance & compliance

| Free ✅ | Commercial 💰 |
|---|---|
| Trust pages · `security.txt` · published DPAs · subprocessor lists | Certification-register APIs, GRC platforms (OneTrust, AuditBoard) |

**Honest limit:** self-reported is self-reported. Paid verification promotes a claim from
`claimed_unverified` to `registry_corroborated` — **a band change with evidence**, not a relabelling.

#### Business & financial

| Free ✅ | Commercial 💰 | What money buys |
|---|---|---|
| GLEIF · Wikidata · RDAP · ABN Lookup · ASIC · **Companies House (free filed accounts)** · EDGAR / ASX for listed | **D&B · Moody's Orbis · S&P Capital IQ** | **Private-company financials, credit deterioration, distress, litigation** — the half [`methodology.md`](methodology.md) §7.2 openly admits is missing |

#### Regulatory & sanctions

| Free ✅ | Commercial 💰 |
|---|---|
| ITA CSL (the gate) · **DFAT (held — licence pending)** · FTC RSS · OAIC · ACCC · ASIC | Dow Jones, Refinitiv screening |

**Better screening reduces false positives. It does not turn a hit into a grade.** The gate stays a gate.

#### Supply chain / fourth party

| Free ✅ | Commercial 💰 |
|---|---|
| MX · SPF `include:` · NS · CNAME · CT SANs · `/subprocessors` · response-header fingerprints | Interos · Panorays · Prevalent |

**This bucket is nearly free.** The vendor's own published DPA is the *authoritative* list; a paid graph
is inferring what the vendor already tells you. **Buy last, or not at all** — a bought graph is
unreconstructible, which collides with Finding A and dissolves the concentration finding
[`roadmap.md`](roadmap.md) §2.2 says a client cannot obtain any other way.

> **Adding a source never changes the pipeline.** It registers a collector, declares a bucket, and emits
> `CollectorResult`. Stages 3–11 do not know it happened.

---

## Stage 3 — Evidence Validation

**Purpose.** Persist every observation immutably before anything interprets it. **This is the legal
defence, and it does not change with budget** — it matters *more* with paid data, which you may not be
able to re-query tomorrow.

### The record

| Field | Why |
|---|---|
| `source` + `source_version` | Reconstruct the screen **as it stood at the time** (Finding B) |
| `collector` | Attribution and failure isolation |
| `fetched_at` (tz-aware, mandatory) | Same |
| `raw` payload | The unprocessed observation |
| `reliability` | From the source assessment, never invented |
| `content_hash` (sha256, canonical JSON) | Byte-identical read-back, verified by test |
| **`licence`** | **New in v2** — which licence this observation was collected under |
| **`retention_until`** | **New in v2** — the contractual retention boundary |
| **`redistributable`** | **New in v2** — may this be shown to a client, or is it internal-only? |

**Why the three new fields.** With free sources, licence is a property of the *register* and can live in
a document. With commercial feeds it becomes a property of **each record** — different feeds carry
different retention and redistribution terms, and a mixed-provenance evidence pack must know which rows
it may print. Without these, §15's traps are discovered at audit rather than at ingestion.

### Validation is a write, not a filter

**Nothing is rejected here.** An `empty`, an `error` and a `timeout` are all stored. Discarding an
observation because it looked unhelpful would itself be an unrecorded scoring judgement — the precise
move Finding A punishes. Validation means *"stamped, hashed and made immutable"*, not *"checked for
worthiness"*.

The store is **append-only** — database triggers reject UPDATE and DELETE. Under Finding A
(`ABN AMRO v Bathurst Regional Council` [2014] FCAFC 65), publishing a rating carries an implied
representation it was formed on reasonable grounds, and a duty of care is owed **without any contract**.
The evidence store is the artefact that discharges it.

---

## Stage 4 — Evidence Enrichment

**Purpose.** Improve evidence without creating findings. **This is where most commercial value actually
lands, and naming it as its own stage is the sharpest structural improvement in v2** — enrichment was
previously scattered across five domain stages where nobody could see it was one activity.

| Enrichment | What it does | Free | Commercial |
|---|---|---|---|
| **Entity re-resolution** | Re-derive resolution confidence **from what the registries actually answered** — the second pass | GLEIF match quality, Wikidata P856 domain verification | D&B linkage |
| **Cross-source corroboration** | Two independent registers agreeing → higher confidence (noisy-OR) | GLEIF + Wikidata + RDAP | + ABN, Companies House, D&B |
| **Asset attribution** | Which observed hosts are *actually this vendor's* | CT SAN + DNS | **Censys/RiskIQ attribution — and audit it, because the liability transfers to you** |
| **Version matching** | Product name → running version | — | **VulnCheck, Censys banners** |
| **CVE enrichment** | CVSS, EPSS, exploit availability, KEV status | NVD + EPSS + KEV | VulnCheck, Recorded Future |
| **Historical context** | Was this misconfigured last quarter too? | Wayback CDX, CT issuance history | SecurityTrails |
| **Dependency graph assembly** | Provider fingerprints → fourth-party map | DNS/CT/trust fingerprint dictionary | Interos (cross-check only) |
| **Freshness weighting** | How stale is this observation | `fetched_at` + `event_date` | — |

**The pipeline loop lives here.** Entity confidence is re-derived *after* collection and *before* the
gate reads it, because it cannot be known earlier. If it falls below 0.5, the record is blocked despite
having collected successfully — **a late gate on an early question.**

**One variable a paid feed *could* finally make real.** The NIST mitigation factor (×0.6) is wired
end-to-end but **dormant**: nothing free evidences that a vendor *fixed* a given issue. Version-level
detection is the first plausible source of remediation evidence — *the vulnerable version was observed on
1 June and the patched version on 15 June.* But it is not automatic: it earns the factor **only when the
collector can reliably map the later banner to the exact product instance that produced the earlier
finding** — same host, same service, same component. A banner change on a *different* asset is not a fix.
Where that mapping holds, a currently correct-but-inert variable becomes live; where it does not, the
finding stands and the dispute path (§9) is how a real fix is credited instead.

---

## Stage 5 — Finding Generation

**Purpose.** Convert observations into findings — the first stage where judgement is applied, and every
piece of it is declared in `scoring.yaml` rather than in code.

```
Observation:  "no DMARC record at _dmarc.vendor.com"        [collector: dns, hash: 3f9a…]
                              ↓  band lookup
Band:         dmarc.absent
                              ↓  severity map
Severity:     high  →  −20
                              ↓  reason lookup (loader-enforced)
Reason:       "Anyone can send email pretending to be this company. There is no published rule
               telling mail servers to stop it, which is the standard opening move in invoice
               fraud and staff impersonation."
                              ↓
Action:       "Ask the vendor to publish a DMARC record, starting at p=none, moving to p=reject"
Re-check:     30d
Refutable by: "A published DMARC record at p=quarantine or p=reject"
```

**Every finding carries:** signal · category · band · severity · penalty · **plain-English reason** ·
evidence hash · `event_date` · occurrences · confidence contribution.

**The loader refuses to start if a penalising band has no reason.** A score a client cannot have
explained to them is the thing this model exists not to produce.

### The bands commercial evidence unlocks

```yaml
# Attack surface — from Censys/Shodan observations (Stage 2), attributed in Stage 4
exposed_admin_service:
  none: pass
  ssh_exposed: low                    # expected on many estates; note, don't punish hard
  rdp_or_smb_exposed: critical        # the ransomware front door
exposed_datastore:
  none: pass
  auth_required: medium
  unauthenticated: critical           # open Elasticsearch/MongoDB/Redis
service_version_currency:
  supported: pass
  end_of_life_component: high
  known_vulnerable_version: critical  # version match, not name match — ceiling-eligible

# Threat & credential — entity-level counts only (the dark-web fence, Stage 2)
credential_exposure:
  none: pass
  historic_only: low                  # >12 months, no recent recapture
  recent_recaptured: high             # <90 days
  active_session_tokens: critical     # session cookies = MFA bypass
initial_access_listing:
  none: pass
  claimed_unverified: high
  corroborated: critical              # ceiling-eligible
ransomware_leak_site:
  not_listed: pass
  historic_listing: high
  active_listing: critical            # ceiling-eligible — a live extortion listing
```

**Why `rdp_or_smb_exposed` is ceiling-eligible and a KEV name-match is not.** An observed open RDP port
on an attributed host is a **direct current-state observation of this vendor's own estate**. A product-line
KEV match is a statement about a product line. The ceiling exists for the first kind of fact only.

---

## Stage 6 — Confidence Analysis

**Purpose.** Say how much of the planned evidence actually arrived — **in a dedicated engine, never
mixed into posture**.

| Input | Effect |
|---|---|
| **Coverage** — planned signals that returned data | Primary driver |
| **Corroboration** — independent sources agreeing (noisy-OR) | Raises confidence where two registers concur |
| **Freshness** | Stale observations count for less |
| **Source reliability** | From the source assessment, per collector; a *clean receipt* is stamped lower than a positive detection |
| **Entity certainty** | Below 0.5 this stops being a confidence input and becomes a **block** |

**Bands:** ≥0.90 High · ≥0.70 Medium · else Low · **<0.40 → refuse to publish.**

| | High confidence | Low confidence |
|---|---|---|
| **Strong posture** | Evidenced clean | **The Ghost** — *unassessed, not safe* |
| **Weak posture** | Verified exposure | Uncorroborated signal |

> **What budget actually does to this stage.** More sources raise **confidence** far more than they
> change **posture**. That is the model working correctly. A vendor that reads as *The Ghost* on the free
> stack and **stays a Ghost after A$200k of feeds** is telling you something real — that is a finding,
> not a failure.

---

## Stage 7 — Penalty Scoring

**Purpose.** One defensible number. **Unchanged by budget. Deliberately.**

```
Start at 100
   ↓  subtract a penalty per issue, sized by severity  (critical 40 · high 20 · medium 8 · low 3)
   ↓  × age decay        0.5^(months/36), floor 0.15; current-state signals never decay
   ↓  × frequency        1 + 0.25×(n−1), cap 2.0 — a pattern, not a re-count
   ↓  × mitigation       ×0.6 where remediation is EVIDENCED
   ↓  collapse each (category, signal) group to its worst member
   ↓  sum per category (each capped at 100)
   ↓  ╔═ SANCTIONS GATE ═╗ → BLOCK, emit nothing, human adjudication
   ↓  overall = 100 − (total penalty / divisor)
   ↓  CRITICAL CEILING — a directly-observed current critical caps the grade at 49
   ↓  grade A–F + confidence, published together or not at all
```

**No machine learning determines the score.** ML may rank, cluster or triage; it never sets a penalty.

**What commercial data changes here: the inputs, never the arithmetic.** New signals, new bands, new
severities — the same one points table, the same four NIST modifiers, the same gates. **That is what
makes the whole upgrade path additive rather than a rewrite.**

---

## Stage 8 — Benchmarking

**Purpose.** A clean score means different things in different industries. **Separating this from scoring
is the correct call** — the arithmetic is untouched, only the reading changes.

```
peer_cohort = industry × size_band × region [ × ownership ]
```

| Dimension | Bands |
|---|---|
| Industry | ANZSIC division → ~12 working sectors |
| Size | Micro <20 · Small 20–199 · Medium 200–999 · Large 1k–10k · Mega 10k+ |
| Region | ANZ · North America · UK/EU · APAC · Other — *regulatory regime, not geography* |
| Ownership | Listed · Private · PE/VC · Government · Not-for-profit |

### Two levers, and the one that is refused

| Lever | Effect | Status |
|---|---|---|
| **Expected-posture band** | Same score, industry-relative reading: *"78 against a cohort expectation of 88 — below par for a regulated financial vendor"* | **Adopted.** Arithmetic untouched; the regression corpus still holds |
| **Industry severity profile** | Promotion-only, capped at one step, each line citing a named instrument (CPS 234 · SOCI · APP 11 · PCI DSS), declared on the card, client-switchable | **Adopted.** One lever, itemised, contestable per line |
| 🚫 **Per-industry category weights** | — | **Refused.** No authority publishes vendor-risk category weights; the AFA says the rating system must be the *user's*. §5.6 deleted weights for that reason and three open items dissolved with them |

**Where the expected band comes from,** in order of preference: observed cohort medians (needs a
portfolio) → regulator-published sector evidence (OAIC NDB sector breakdown) → client-set risk appetite.
**Never a number invented and printed.** Until one is populated the field reads *"no cohort baseline."*

### Size is context, and it is collected here — not at scoring

Size never touches the posture (Rule 12). It has exactly one job — picking the cohort — so it is resolved
where that job is done, not on the scoring form:

- **Observed.** When public sources publish a size, it is used and labelled *observed*.
- **Client-supplied, added after the score.** When they do not, the vendor has no cohort, and the card
  says so and offers a fix: *"Public sources did not publish a reliable size. Know the correct size — or
  the entity you actually contract with? [Add size band]."* Supplying it re-derives the cohort
  (`refresh_cohort`) and **writes a new profile row; the posture is byte-identical.** The band is labelled
  **client-supplied** so a reader — and an auditor — can see the comparison rests on a supplied figure,
  not an observed one. A supplied band overrides the observed one, because the buyer may be describing the
  local subsidiary they contract with rather than the global parent a register describes.

### The widening ladder, and the convenience-sample caveat

An exact `industry × revenue × headcount × region` cohort almost never fills at real portfolio sizes, so
the ladder **steps out one dimension at a time** — drop region, then revenue, then headcount — and never
past **industry**. The rung actually used is named on the card (*"wider peer group used: industry +
region"*); there is deliberately no rung comparing a bank to every vendor ever scored. Every benchmark
also carries the standing caveat that peers are **vendors this deployment happened to score** — a
convenience sample, not an industry norm.

### The stability window — a published percentile should not flip overnight

`n = 8` is defensible **because** the percentile is rounded to the step the sample can express
(`ceil(100/n)`, printed beside it) and the system refuses below the threshold. Pair it with a stability
state so a cohort does not swing from *insufficient* to a confident percentile the moment an eighth peer
lands:

| State | Condition | Publication |
|---|---|---|
| **Insufficient** | n < 8 at every rung | Refusal message + how close the best rung came |
| **Provisional** | n ≥ 8 but the window is not yet satisfied | Quartile + variance + a **provisional** badge; percentile shown with its step |
| **Stable** | n ≥ 8 held across the full window (target: 14 consecutive days) | Full percentile (resolution-aware), quartile, IQR spread, per-category variance |

A grace period on drop (target: 3 days) stops a single peer leaving from instantly retracting a published
comparison. *(Shipped today: the minimal provisional signal — a cohort within a peer or two of the gate
is badged provisional. The time-window state machine above is the target-state elaboration.)*

### Role-aware depth

The peer strip is gated and sized by the reader's role, over the **same** benchmark object — never a
different computation:

| Role | Benchmark | Shows |
|---|---|---|
| Procurement | simple | quartile · median · one sentence — the decision read |
| Security analyst / Risk | full | percentile + step · quartile · widening path · per-category variance · charts |
| Executive / CISO | minimal | one line — quartile / traffic-light |
| Auditor | off by default | the absolute record; peers are interpretation, one switch away |

**Rules:** absolute grade always published · minimum **n = 8** before any percentile, with the step
(`ceil(100/n)`) printed beside it · a **quartile** rides alongside because it survives one peer joining or
leaving · outliers by an IQR fence, not stdev · the ceiling and the gate never relax for a cohort · the
cohort, its **n**, its widening rung and its stability state are all disclosed on the card.

---

## Stage 9 — Decision Engine

**Purpose.** Answer *"Now what?"* — where a score becomes a decision.

**Consumes:** score · confidence band · criticality (client input) · industry profile · gate state.

| Grade | Confidence | Criticality | Recommendation |
|---|---|---|---|
| A–B | High | any | **Approve.** Re-check at 90 days |
| A–B | Low (*Ghost*) | High | **Approve pending questionnaire.** Thin evidence ≠ good security |
| C | High | Low | **Approve with conditions.** Named remediations, re-check at 30 days |
| C | High | High | **Request remediation before signing.** Send the evidence, re-scan in 7 days |
| D | High | any | **Full due diligence + executive risk acceptance** with compensating controls |
| F | High | any | **Reject**, or accept with executive sign-off, a named owner and an expiry date |
| any | any | any | **BLOCKED** → human adjudication. No score, ever |

**Produces:** recommendation · required action · `ask_of_vendor` (copy-pasteable) · `accepts_as_refute` ·
`recheck_after` · evidence pack · owner + expiry for accepted risks.

**Deterministic and reconstructible** — a rule table over published fields, **never LLM-generated**. It is
**advisory and labelled as such**; the client decides.

### The dispute loop

Outside-in scoring **systematically over-penalises**, because it cannot see compensating controls. Both
benchmarked commercial platforms accept evidenced refutes for exactly that reason. v1 has none —
**open item 12, a live Finding A exposure.**

A vendor submits verifiable, redacted evidence (SOC 2 Type II, a patch log, a WAF rule proving the CVE is
unexploitable, *"that IP is our CDN, not us"*) → a human adjudicates → an accepted refute applies the
`mitigation` modifier or nullifies the finding → **a new immutable Score is written**, with the dispute,
the evidence and the resolution in its chain. **Nothing is ever edited.**

> **Paid data makes this a prerequisite, not a follow-up.** Commercial sources *raise the frequency* of
> contested findings: attack-surface attribution errors and dark-web false positives are more common than
> DNS misreads, and every extra source is extra findings, some of them wrong. When Censys says an IP
> belongs to a vendor and it does not, **your** score is wrong and **your** client relied on it. The
> dispute path scales with spend — the more you buy, the more you need it.

---

## Stage 10 — Continuous Monitoring

**Purpose.** A point-in-time assessment is true on the day it is signed. Risk is not. **This stage loops
back to Stage 2**, producing a new score rather than amending the old one.

| Cadence | For | Watching |
|---|---|---|
| **Daily** | Critical vendors | Sanctions, ransomware leak sites, active exploitation, credential dumps |
| **Weekly** | Medium | New CVEs, certificate expiry, DNS/provider changes, new breaches |
| **Monthly** | Low | Full re-score, entity standing, financial signals |
| **Event-driven** | All | A new KEV entry matching a known product; a fourth party's incident |

**Drift alerts.** Because every run is hash-stamped, a posture move raises a flag **with before/after
receipts attached**. Drift is *provable*, not asserted.

**Portfolio concentration monitoring** — a *shared* fourth-party dependency emerging across many vendors —
is the systemic signal no single-vendor questionnaire can ever see.

---

## Stage 11 — AI Read Layer

**Purpose.** Support the analyst. **Never the scorer.**

| ✅ Suitable | 🚫 Never |
|---|---|
| Summarise findings into a plain-English brief | Calculate or adjust a score |
| Generate executive reports | Modify or create evidence |
| Explain technical issues to non-technical readers | Override a penalty or a band |
| Draft remediation requests | Make an approval decision |
| Adjudicate adverse-media candidates → **review items with evidence** | Auto-publish a verdict |
| Classify trust pages into structured certifications | Resolve an ambiguous entity unsupervised |
| Answer questions about the evidence | Become a shadow scorer |

**The fence, as built:** the summariser reads the published score plus the hash-stamped receipt index,
never computes or alters a score, never writes to the store, is returned **marked AI-generated**, and
**cites the hashes it was built from**. Raw collector payloads never reach the model. It is the system's
**single documented egress point**, off by default, provider-agnostic.

> **`"the model said so"` is not reasonable grounds.** Under Finding A the representation attaches to the
> **published score**. AI output is evidence-linked and human-adjudicable, or it does not ship.

**Placing it last is deliberate.** It reads the finished record, so it **cannot** become a shadow scorer —
the number it describes was already fixed, upstream, by the deterministic engine.

---

## Presentation — projections, not a stage

Deliberately **not** numbered. It is an output layer over Stage 9's record, and treating it as a pipeline
step invites the failure it exists to prevent: an executive number computed differently from the analyst
detail.

| Role | Leads with | Reads first | Behaviours (the live flags) | Action |
|---|---|---|---|---|
| **Procurement** | recommendation | grade · confidence · recommendation · deal-breakers | `materialOnly`, simple benchmark, no receipts | **record decision** (approve / conditional / reject) |
| **Security analyst** | score | every finding, expanded to the receipt | full benchmark, receipts, clean passes shown | **dispute a finding** with evidence |
| **Risk manager** | score | categories · trend · peer comparison | `materialOnly`, full benchmark, portfolio context | dispute · set tier |
| **Executive / CISO** | recommendation | top-3 findings · minimal benchmark | `topFindingsOnly`, disclosures one click away | record decision · share pack |
| **Auditor** | score | score → finding → receipt → source → timestamp → hash | `showHashes`, benchmark off, stability history | verify · export evidence pack |

**One record, five projections — not five scores.** Every view renders from the same API response and
**the same immutable score object** — the one source of truth for every projection *and* for any later
benchmark refresh. A role changes only what is shown first and how much is expanded; it never changes what
is true, and the analyst can always reach the receipt behind the executive's number.

**Actions write *alongside* the score, never inside it.** Recording a decision, submitting a dispute,
setting a tier, exporting a pack — each is an append-only fact beside the immutable record, emitting no
finding and moving no penalty. A decision is even stamped with the posture *as at* the moment it was made,
so *"approved at 72 (C)"* stays true after a later re-score.

---

# Part II — The Money

## §12. What it costs, and what to buy first

### Indicative annual cost

| Capability | Typical sources | Approx. annual (AUD) | Value per dollar **for TPRM** | Enters at |
|---|---|---|---|---|
| **Attack surface** | Censys, Shodan Enterprise, SecurityTrails, RiskIQ | **$30k – $80k** | ★★★★★ | Stage 2 + 4 |
| **Business intelligence** | D&B, Moody's, S&P Capital IQ | **$20k – $100k** | ★★★★☆ | Stage 1 + 2 |
| **Dark web / credential** | SpyCloud, Constella, KELA | **$50k – $200k** | ★★★★☆ | Stage 2 (fenced) |
| **Threat intelligence** | Recorded Future, CrowdStrike, Mandiant, Defender TI | **$100k – $300k+** | ★★☆☆☆ | Stage 4 |
| **Supply chain graph** | Interos, Panorays, Prevalent | **$80k – $250k+** | ★☆☆☆☆ | Stage 4 (cross-check) |
| **Compliance / GRC** | OneTrust, AuditBoard | **$20k – $100k** | *(adjacent — the other half of the platform)* | — |

> **Indicative list-price bands, not quotes.** Enterprise pricing is negotiated and rarely published;
> actual cost varies with data volume, seats, term and API limits. A fully featured deployment lands in
> the **high six figures to low seven figures AUD annually**.

**Why the star ratings invert the price order.** Threat intelligence and supply-chain graphs are the most
expensive and the *least* aligned with this use case — built for SOCs and for buying the answer,
respectively. Attack surface is cheap, factual, and closes the largest genuine blind spot.

**On supply-chain graphs specifically: usually do not buy.** The vendor's own published DPA and
subprocessor list is the *authoritative* fourth-party map, and it is free; a bought graph infers what the
vendor already tells you, is unreconstructible (colliding with Finding A), and dissolves the very
concentration finding it is sold on. Treat it, at most, as a cross-check on the free graph — never as the
source of record.

### Budget scenarios

| Budget | Buy | Closes |
|---|---|---|
| **A$0** | Nothing. Register free keys — Cert Spotter, ABN Lookup GUID, Companies House, OTX, NVD. Chase the DFAT and Modern Slavery licence replies | CT single point of failure · AU/UK entity standing · **AU sanctions** — blocked on a letter, not a cheque |
| **~A$50k** | **Censys or Shodan** + **SecurityTrails** | The attack-surface gap. **Can begin to evidence remediation** — where a later banner maps to the finding's own asset (§4). Biggest single jump available |
| **~A$150k** | Add **D&B or Moody's** + **VulnCheck** | Private-company financials. KEV name-match → version-match, making it ceiling-eligible |
| **~A$400k** | Add **SpyCloud or Constella** (entity-level only) + **KELA** | The HIBP recall gap. *"Access to this vendor is for sale"* |
| **A$1M+** | Add **Recorded Future / Mandiant** as displayed third-party opinions; **Interos** as a cross-check on our own graph | Targeting context, n-th tier depth — **least value per dollar, bought last for a reason** |

### The ingestion contract

> ### Buy observations, never verdicts.
>
> A commercial feed enters as **evidence** — a hash-stamped observation with a source, a timestamp, a
> licence, and a severity **we** assign under **our** published bands. It never enters as a score, a
> weight, or a black-box grade we resell.

**Legal.** Finding A: publishing a rating carries an implied representation it was formed on reasonable
grounds. *"Recorded Future said 62"* is not reasonable grounds — you cannot reconstruct it, explain it,
or defend it in a dispute.

**Regulatory.** The AFA is on record warning against bought, black-box vendor scores, *"specifying that
users must be able to determine their own rating system with regard to risk mapping."*

**The commercial corollary:** import their score and you are a reseller with a markup. Import their
observations and apply your own transparent model and you are a methodology — auditable, tunable, and
defensible to *the client's* regulator. **The second one is the product.**

---

# Part III — The Constraints

## §13. What does not change, at any budget

| Principle | Why budget does not touch it |
|---|---|
| **Two axes, never collapsed** | Posture and confidence answer different questions. More data raises confidence; that is not lower risk |
| **Sanctions is a gate, not a weight** | Strict liability. A block routed to adjudication *is* the s 16(7) defence; a grade is not |
| **No natural persons** | Paid feeds will sell you director data and credential dumps. The line does not move because a vendor will sell across it |
| **Evidence before scoring** | With paid data this is *more* critical — you may not be able to re-query it later |
| **Every deduction has a sentence** | An expensive score you cannot explain is worse than a free one you can |
| **No ML determines the score** | ML may rank, cluster or triage. It never sets a penalty |
| **Missing data reduces confidence, never posture** | The one rule that stops invisibility reading as safety |
| **Absence of evidence ≠ evidence of absence** | Snowflake's HIBP silence, demonstrated live on a real vendor |

## §14. What money cannot buy

1. **~10 of ~27 due-diligence criteria are invisible to any lawful external observer** — access controls,
   security monitoring, data handling, insurance, change management, contract terms. **No spend closes
   this.** It is why the honest pitch is contradiction-flagging and pre-fill, never replacement.
2. **Perimeter ≠ posture.** More external sources make the perimeter reading better, not deeper.
3. **Entity resolution is the accuracy ceiling.** More sources create **more** chances to attribute a
   stranger's data to your vendor. Budget makes this failure mode *more* likely, not less.
4. **Self-reported stays self-reported.** Verification promotes the band; it does not change what the
   claim is.
5. **Coverage tracks company size, not company risk** — and paid feeds **amplify** it, having deeper
   coverage of large enterprises.
6. **You cannot buy your way out of a dispute path.** More data → more findings → more contested findings.

## §15. Legal and contractual traps in paid data

Money removes the cost barrier, **not the legality bar** — the same bar that permanently excluded
VirusTotal and SSL Labs. Every feed must clear these **before** ingestion, and the answers belong in
Stage 3's `licence` / `retention_until` / `redistributable` fields, per record.

| Question | Why it is a deal-breaker if unanswered |
|---|---|
| **May we use this in a commercial derived product?** | Many licences permit internal use only. A score sold to a client is a derived product |
| **May we retain the raw observation for 7 years?** | Finding B requires reconstruction. Many licences require deletion on termination — **directly incompatible** |
| **May we display the observation to our client?** | Redistribution is often separately licensed → `redistributable` |
| **What is the provenance of this record?** | Critical for dark-web data. *"We cannot say"* means it cannot penalise a vendor |
| **Is there a right of correction?** | Feeds the dispute loop |
| **Does ingestion create a Privacy Act obligation?** | Credential dumps are personal information |
| **Are we permitted to score with it?** | Some TI licences prohibit using their data to rate third parties — *precisely* our use case |

### The three sharpest traps

**1. Dark-web data is personal information.** Buying a feed does not create a lawful basis to hold it.
Aggregate at ingestion (Stage 2), never at display.

**2. Retention clauses vs Finding B.** A licence requiring deletion on termination is incompatible with an
evidence store that must reconstruct historical scores. **Negotiate a retention carve-out for the derived,
hash-stamped finding before signing** — or the feed is limited to display-only context and may never enter
the scoring path.

**3. Attribution liability transfers to you.** Under Finding A the reasonable-grounds representation
attaches to what *you* publish. This is why the dispute loop is a **prerequisite** for commercial
attack-surface data.

---

# Part IV — The Plan

## §16. Maturity ladder

| Tier | Cost | What runs | Who for |
|---|---|---|---|
| **Tier 0 — shipped** | ~A$0 | 14 collectors · 26 signals · 7 categories · evidence store · penalty model · two axes | SMEs, research, startups, budget-free procurement |
| **Tier 1 — free keys** | ~A$0 + registrations | + ABN Lookup, Companies House, DFAT, Modern Slavery, OTX, Cert Spotter · **AU sanctions in the gate** · ESG and FOCI unlocked | Australian mid-market |
| **Tier 2 — mid-market** | ~A$50k–150k | + attack surface + business intelligence + VulnCheck · **open ports, exposed services, private financials, version-level matching** | Regulated buyers under CPS 230 |
| **Tier 3 — enterprise** | A$400k–1M+ | + dark web, threat intelligence, n-th party cross-check, daily monitoring, full portfolio benchmarking | Banks, insurers, critical infrastructure under SOCI |

**Each tier is additive and none changes the model.** Same arithmetic, same gates, same two axes. **That
is the design claim of this document** — and the restructure in v2 is what makes it visibly true: every
tier adds sources at **Stage 2** and enrichment at **Stage 4**. Stages 3, 5, 6, 7, 9, 10 and 11 never move.

## §17. Design principles

1. **Organise by the lifecycle of evidence, not by security domain.** A new source is a new collector, not
   a new stage.
2. **Collect observations, not proprietary scores.** Commercial ratings are third-party opinions to display
   beside ours, never inputs to merge into ours.
3. **Separate posture from confidence, always.** No API path returns a bare number.
4. **Keep every finding traceable.** Source, timestamp, raw payload, licence, hash. If it cannot be
   reconstructed, it cannot be published.
5. **Compare like with like.** Benchmark within industry × size × region × regime, and disclose the
   cohort, its **n**, its widening rung and its stability state. Never publish a percentile finer than the
   sample can express.
6. **Turn findings into decisions.** Every finding carries an action, an ask, and a re-check date; every
   decision is recorded beside the score, stamped with the posture it was made on.
7. **Explain every deduction in a sentence a procurement lead understands.** Loader-enforced.
8. **Close the loops.** Monitoring and dispute both re-enter at collection and write **new** scores.
   Nothing is ever edited.
9. **Firmographics are context — full stop.** Industry, region and ownership select the cohort and the
   severity profile; size is collected only when needed for interpretation, added after the score if
   public sources lack it, and never a scoring input.

---

## Appendix — v1 → v2 stage mapping

Nothing was dropped. The domain content was redistributed to the lifecycle stage that owns it.

| v1 (domain-driven) | v2 (evidence-driven) |
|---|---|
| 1. Vendor Profiling | **§1 Entity Resolution** |
| 2. Attack Surface Discovery | **§2** (evidence register — attack surface bucket) + **§4** (attribution) + **§5** (bands) |
| 3. Technical Security Assessment | **§2** (internet/perimeter bucket) + **§5** (bands) |
| 4. Threat Intelligence | **§2** (threat & credential bucket) + **§4** (CVE/version enrichment) + **§5** (bands) |
| 5. Business & Governance | **§2** (business, governance, regulatory buckets) |
| 6. Fourth-Party Mapping | **§2** (supply-chain bucket) + **§4** (graph assembly) |
| 7. Evidence Validation | **§3** (+ licence / retention / redistributable fields, new) |
| 8. Confidence Engine | **§6 Confidence Analysis** |
| 9. Risk Scoring | **§7 Penalty Scoring** |
| 10. Industry Benchmarking | **§8 Benchmarking** |
| 11. Decision Engine | **§9 Decision Engine** (+ the dispute loop, made explicit) |
| 12. Role-Based Views | **Presentation** — a projection layer, deliberately not a stage |
| 13. Continuous Monitoring | **§10 Monitoring** (now drawn as a loop back to §2) |
| 14. AI Assistance | **§11 AI Read Layer** |
| *(scattered through v1)* | **Cross-cutting rules** — hoisted to the front, where they govern every stage |
| *(inside v1 stage 9)* | **Gates** — promoted to cross-cutting; they stop the pipeline, they are not a step in it |

---

### See also

- [`methodology.md`](methodology.md) — the shipped methodology · §4 (legal frame) · §5.6 (why no weights) · §7 (limitations)
- [`doable_methodology.md`](doable_methodology.md) — the same lifecycle on a free tier, with the build backlog
- [`review_response.md`](review_response.md) — the nine reviewer points
- [`roadmap.md`](roadmap.md) — the sequenced path from Tier 0 to Tier 1
- [`source_assessment.md`](source_assessment.md) — the clearance bar every paid feed must also pass
- [`scoring.yaml`](../scoring.yaml) — the model all of this lands in, unchanged
