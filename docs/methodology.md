# Methodology — OSINT for Third-Party Risk

**Deliverables 1 & 3** (research methodology · v1 scoring model)
**Status:** v2 · scoring model **`scoring.yaml` v5.4.0 (penalty-based posture + Business Stability axis)**

> **This document is the product.** The code demonstrates it. If the PoC were deleted tomorrow,
> this file should be enough for someone else to rebuild it and get the same scores.

This document answers three questions that belong together, one per part:

| Part | Question |
|---|---|
| **1 · Research methodology** | What do we measure, and why that and not something else? |
| **2 · Legal & standards basis** | Once collected, does the score we build on it stand up? |
| **3 · Source assessment** | May we lawfully collect each source, and what is it worth? |

*Companion docs: [`scoring_model.md`](scoring_model.md) Part 1 (the model and every metric's arithmetic) ·
[`design_decisions.md`](design_decisions.md) (benchmarking, financial data, acceptance scenarios) ·
[`system_retrospective.md`](system_retrospective.md) (current, verified status).*

## Part 1 · Research methodology

**Deliverables 1 & 3** (research methodology · v1 scoring model)
**Status:** v2 · scoring model **`scoring.yaml` v5.3.0 (penalty-based posture + Business Stability axis)** · **Author:** *(intern)*
*Companion docs: [`scoring_model.md`](scoring_model.md) Part 1 (the model in brief) · Part 3 of this document (source methodology) · [`scoring_model.md`](scoring_model.md) Part 2 (per-metric arithmetic) · [`design_decisions.md`](design_decisions.md) Part 2 (Business Stability design).*

> **This document is the product.** The code demonstrates it. If the PoC were deleted tomorrow, this file should be enough for someone else to rebuild it and get the same scores. Execution sequencing is deliberately not here.

---

### 1. Objective

Take a vendor name or domain and return a **structured risk record and an overall score**, assembled automatically from lawfully-collected public information, where **every point of that score is traceable to stored evidence.**

Three constraints shape everything below, in this order:

1. **Defensibility before coverage.** A score we cannot reconstruct is worse than no score — see Part 2 of this document Finding A, which establishes that this is a legal standard in Australia, not a preference.
2. **Legality before coverage.** Per-source positions are settled in Part 3 of this document; model-level constraints in Part 2 of this document.
3. **Honesty before completeness.** OSINT is patchy. The model must say so in its own output, structurally, not in a footnote.

**What this is not.** It is not a replacement for a questionnaire framework. Taking the criteria list from an illustrative demo questionnaire template (**not authoritative** — see §5.6) merely as a rough inventory of ~27 plausible criteria: roughly **7 are observable** from public data, ~10 partially observable by proxy, and ~10 (access controls, security monitoring, data handling, insurance, change management, contract terms) are **invisible to any lawful external observer**. That is a property of the problem, not of our sourcing. OSINT **pre-fills the fraction it can evidence independently and flags contradictions** where a vendor's self-assessment disagrees with the public record. Contradiction-flagging, not replacement, is the product.

#### The thesis

> A regulator (the AFA) is on record warning against bought, black-box vendor scores, *"specifying that users must be able to determine their own rating system with regard to risk mapping."*

The brief's central instruction — propose and defend your own model — is independently confirmed by a regulator, and separately enforced by the Australian courts (Finding A). **Owning the model is not a differentiator. It is the only lawful way to sell a score.**

---

### 2. Scope

#### In scope for v1

| | |
|---|---|
| **Input** | Vendor name **or** domain |
| **Output** | Structured record + category postures + overall posture + grade + **confidence** + evidence trail |
| **Sources** | The 14 cleared collectors in Part 3 of this document |
| **Categories** | 5 scored + 2 context + gate (§5.2); 5 held |
| **Test vendors** | 5 real, named, deliberately varied (§2.3) |
| **Automation** | End-to-end collection → score → record, no manual steps except the adjudication gate (§5.5) |

#### Explicitly out of scope for v1 — with reasons

| Excluded | Why | Where it goes |
|---|---|---|
| Paid feeds (Shodan, Censys, VT commercial, HIBP Pro) | Brief: free/trial only | Roadmap |
| VirusTotal, SSL Labs | ToS prohibit our use case | Permanently excluded |
| AU sanctions (DFAT) | Licence unresolved | **Blocking** — see §4.4 |
| ESG / Modern Slavery | Licence unresolved | **Blocking** — category held (emits nothing) |
| FOCI / Provenance | Registry terms unresolved | Roadmap — §8.3 |
| Scoring natural persons | Legal bright line | **Never** — §4.2 |
| Financial quantification (FAIR $) | Inputs don't exist | §5.7 |

#### 2.3 Test vendors

The brief is explicit: *"Don't shortcut with 'test test', 'asdf' or 'Acme Corp'."* Each vendor below is chosen to break something specific.

| Vendor | Why chosen | What it tests (✓ = verified live via the collectors) |
|---|---|---|
| **Atlassian** | AU-founded, NASDAQ-listed (TEAM), mature trust centre, published subprocessors | Happy path; **GLEIF resolves (ACTIVE) ✓**; ships software → **KEV hits (Jira/Confluence) ✓**; full subprocessor extraction |
| **Snowflake** | **Data-warehouse SaaS — the quintessential data-processor third party**; NYSE-listed (SNOW); 2024 customer-data incident (credential-stuffing against *customer* accounts) | **GLEIF resolves (SNOWFLAKE INC., ACTIVE) ✓**; **HIBP returns a *clean receipt* ✓** — the incident was B2B and never entered HIBP, demonstrating the documented **"HIBP skews consumer-facing"** recall limit *live* (now scored as clean-receipt coverage, §5.4.2) |
| **Slack** | Salesforce-owned collaboration SaaS — a ubiquitous data-processor third party; private (subsidiary) | **GLEIF resolves (ACTIVE) ✓ AND Wikidata domain-verifies (P856 = slack.com) ✓** → business standing **corroborated** by two independent registers (conf 0.90 → 0.97, §5.4.3); **HIBP clean receipt ✓** (no breach under `slack.com`); the *single-source-fragility* archetype — its Digital-Footprint depends solely on CT, so a crt.sh outage tips it to `The Ghost` (v3.3) |
| **MYOB** | AU, PE-owned, private accounting/payroll SaaS | **GLEIF resolves (MYOB, LEI *LAPSED*) ✓** — a real per-vendor signal where EDGAR was blank; was refused at 0.27 under EDGAR, now scores at ~0.73 confidence |
| **OneTrust** | Privacy/GRC SaaS — a real compliance third party, and thematically apt: a governance tool assessed by a governance tool; private | **Strongest trust-centre result ✓** (ISO 27001 / PCI DSS / SOC 2 across four trust pages); **GLEIF resolves (ONETRUST LLC, ACTIVE) ✓ + Wikidata corroborates ✓**; clean sanctions screen ✓ — the *evidenced-clean* archetype |

**Snowflake demonstrates the HIBP recall limit live:** its 2024 B2B incident (credential-stuffing against *customer* accounts) **never entered HIBP**, so a domain search returns clean — scored honestly as a *clean receipt* (§5.4.2), not as proof of safety. This is precisely why *absence of a breach record is not evidence of security* (§3.1), shown on a real vendor rather than asserted.

> **Reference example — the HIBP visibility asymmetry (Canva ↔ Snowflake).** **Canva** was removed from the live rotation (v3.3, replaced by Slack) but is retained here as the contrasting half of a verifiable point: Canva's 2019 consumer breach **appears in HIBP** (`canva.com` → *Canva, 2019-05-24, verified*, checked live 21 Jul 2026) while Snowflake's B2B incident **does not** (`snowflake.com` → empty). Same reality — a real breach — opposite visibility, entirely down to whether the victims were consumers. The model must never read Snowflake's HIBP silence as safety; that is the whole purpose of the clean-receipt scoring (§5.4.2).

**The set is now all real TPRM targets.** Atlassian, Snowflake, Slack, MYOB and OneTrust are all suppliers a client actually onboards and whose failure hurts the client — spanning US-listed (Atlassian, Snowflake) and private (Slack, MYOB, OneTrust), software-shipping (Atlassian, Snowflake → KEV) and pure-SaaS, single-register (Snowflake, MYOB — GLEIF only) and two-register-corroborated (Atlassian, Slack, OneTrust — GLEIF + Wikidata, §5.4.3). The earlier non-archetypes (CSIRO, a gov research org; Medibank, a consumer insurer) and Canva (now a reference example, above) were removed from the live set. **Xero was trialled and correctly BLOCKED** — the ITA screen fuzzy-matched "CLOUD XERO MANAGEMENT PTE. LTD." on the SDN list and routed it to human adjudication (the sanctions gate working as designed, §5.5.1), so it is not a scored member of the set.

> **Live discovery — entity resolution is the hard problem, on cue (§3.1).** When **Vanta** was trialled as the GRC candidate, its 5-character name produced **two false positives**: EDGAR matched it to a *different* US-listed company (attributing a stranger's financials), and the ITA screen fuzzy-matched it to a CSL entry. The ITA hit is *working as intended* — the gate is recall-tuned to over-surface and route to human adjudication (§5.5.1). The EDGAR match is a **real defect** — silent wrong-company attribution — and is why the entity-resolution confidence gate (`< 0.5 → BLOCKED`) and a tighter name matcher are load-bearing, not optional. Logged as an entity-resolution hardening item for Phase 2. OneTrust was chosen partly *because* it resolves cleanly; Vanta earned its keep by breaking the matcher in the way the methodology predicted.

**Long-name layout test (was CSIRO's role).** The brief's *"very long company name"* requirement is a **UI robustness** check, not a vendor-selection one — it is exercised in Phase 4 with a long real vendor legal name (or a long input string), decoupled from needing a non-vendor in the assessment set.

**Still needed (open item):** a vendor with **almost no public footprint** and one with an **expired certificate**, both required by the brief. These must be found empirically from CT logs rather than assumed — expired certs are transient.

**Note on collecting about real companies.** These are real organisations and the record includes breach and adverse-media data. Per the brief: *"do not republish or expose it."* Records stay internal; the sample scorecard for Deliverable 4 uses a vendor whose findings are already a matter of public record.

---

### 3. OSINT Sources

Full assessment — signals, reliability, limits, ToS position, verification log — is in **Part 3 of this document** and is not duplicated here. Summary of what feeds the model:

| # | Source | Feeds category | Reliability | Killer limit |
|---|---|---|---|---|
| 1 | Certificate Transparency (crt.sh + certspotter fallback) | Cyber Hygiene / Digital Footprint | High | Certs *issued*, not hosts *live* |
| 2 | DNS (SPF/DKIM/**DMARC**/MX/CAA) | Cyber Hygiene | High | Mail path only |
| 3 | Self-run TLS + HTTP headers | Cyber Hygiene | High | Perimeter only |
| 4 | HIBP `/breaches` | Breach & Compromise | High | **Absence ≠ security** (clean receipt, §5.4.2) |
| 5 | ITA Consolidated Screening List | **Gate** | High | US scope only |
| 7 | **GLEIF (LEI register)** | Business Stability | High | Entity standing, not financials *(replaced EDGAR)* |
| 7b | **Wikidata** | Business Stability | Moderate | Domain-verified existence; corroborates GLEIF |
| 7c | **RDAP** | Business Stability | High | Domain standing — any registered domain, no auth |
| 8 | NVD + **EPSS** | Breach & Compromise | High | Vendor **products** only; EPSS adds exploit probability |
| 9 | CISA KEV | Breach & Compromise | High | Vendor **products** only |
| 10 | **Regulator RSS (FTC + cleared)** | Adverse Media | High (matched) | Recent-window; US-weighted |
| 11 | GDELT | Adverse Media *(candidates, held)* | **Moderate** | Noise; allegations ≠ findings |
| 12 | Trust pages / `security.txt` / DPAs | Transparency + Supply Chain | **Low–moderate** | **Self-reported** |
| 6 | DFAT (AU sanctions) | **Gate** | — | **HELD — no licence** |
| 12 | AU Modern Slavery Register | ESG | — | **HELD — no licence** |

**The selection principle, restated:** *prefer sources published in order to be read.* CT logs, sanctions lists and statutory registers exist so outsiders can audit them; their legal position is absent by design. This is why we run our own TLS client instead of SSL Labs, and use GDELT instead of scraping Google News — **in both cases we chose the source with the better legal position over the more familiar name**, and got the same signal.

#### 3.1 The three cross-cutting limits

These are properties of the register as a whole and drive model mechanics in §5.

**Entity resolution is the hard problem, not collection.** Proving a breach, sanction or news item belongs to *this* vendor — not a homonym, subsidiary or namesake — is where accuracy is won or lost. The AFA warns about *"the rate of homonymy"* and concludes automated tooling *"requires human analysis in order to adjust the assessment, particularly for the most high-risk third parties."*

**Absence of evidence is not evidence of absence.** No breach, no adverse media and no SEC filing is the **default state of a small clean vendor — and of a badly-run one nobody has written about yet.** → **Missing data reduces confidence, never risk** (§5.4). Any model where a vendor scores well by being invisible is broken. This is the most likely way a naive implementation fails, and §5.4 exists solely to prevent it.

**Public data is stale and patchy.** → NIST SP 1326's four variables (§5.3).

---

### 4. Legal Frameworks & Standards

Full analysis in **Part 2 of this document**. What the model must obey:

#### 4.1 The two findings

**Finding A — `ABN AMRO v Bathurst Regional Council` [2014] FCAFC 65.** Publishing a rating conveys an implied representation it was formed **on reasonable grounds with reasonable care and skill**; where it wasn't, it is misleading and deceptive conduct under **ACL s 18** (no intent required, honest mistake no defence). A duty of care was owed **without any contract**. → **The evidence store is a legal artefact. Every score reconstructible from retained records. Confidence published alongside every score.**

**Finding B — `Autonomous Sanctions Act 2011` (Cth) s 16.** Strict liability for bodies corporate; the **only** exit is s 16(7), which requires the company to **prove** reasonable precautions and due diligence, bearing a **legal burden**. → **Sanctions are a gate, not a weight. Tune for recall. Retain screening records including clean results.**

#### 4.2 Binding constraints

| Instrument | Rule it imposes on the model |
|---|---|
| **Privacy Act 1988** + *Clearview AI* [2021] AICmr 54 | "It's public" is **not** a defence. **APP 10:** personal info used must be accurate, up-to-date, complete, **relevant** |
| **Privacy tort** (from 10 Jun 2025) | Reaches non-APP entities; no small-business shield |
| **Copyright Act** + *IceTV* [2009] HCA 14 | Facts unprotected; **expression** protected; **no TDM exception** → store normalised facts, not verbatim text |
| **Defamation** (MDP 2021) | Large vendors **cannot** sue; **small vendors and named individuals can** → adverse media worded as *reported/alleged*, dated, attributed |
| **Criminal Code Pt 10.7** | Publication authorises retrieval — collection design already compliant |

> **The bright line, reached independently by three instruments** (APP 10, the privacy tort, and EU AI Act Art 6(3)): **score entities, not natural persons.** Sole traders are where the analysis changes. Three separate authorities converging on one design rule is a rule worth taking seriously.

#### 4.3 What the buyer must evidence (the demand-side spec)

| Instrument | Why it drives a feature |
|---|---|
| **APRA CPS 230 ¶47–48** | **Fourth-party risk is a regulated obligation.** Subprocessor concentration is not a clever extra — it is the regulated deliverable |
| **APRA CPS 234** | Demands **control effectiveness** assurance. OSINT cannot see it → **never claim discharge; claim subset + contradictions** |
| **SOCI Enhanced CIRMP Rules 2026** (reg. 9 Jun 2026) | **FOCI assessment of major suppliers mandatory**, phase-in ~mid-2028 → reframes our FOCI gap as a roadmap item with a deadline and a buyer |
| **Modern Slavery Act 2018** | Statutory register; **licence unstated** → held |

⚠ **The repo's CPS 230 PDF is superseded** — amended CPS 230/CPG 230 commenced **1 July 2026**. Re-check ¶ numbering before any client-facing use.

#### 4.4 Standards adopted — and why each

| Standard | What we take | Why it matters |
|---|---|---|
| **NIST SP 1326** | Five due-diligence categories; **four per-finding variables**; ITA CSL by name | **Borrowed authority for the decay model** (§5.3) |
| **NIST CSF 2.0 GV.SC** | Supplier criticality, **ongoing monitoring**, relationship conclusion | **Authority for agentic re-scoring** — it's a named C-SCRM outcome, not a flourish |
| **ISO 31000 / IEC 31010** | Process discipline; 41 techniques with stated limits | Method defence |
| **ISO/IEC 27001:2022 A.5.19–5.23** · **27036** | Supplier relationship controls | Dimension design |
| **Open FAIR (O-RT/O-RA)** | Frequency/magnitude **separation** | **Cited, not implemented** — §5.7 |

**"We adopted NIST's model" survives a client challenge. "We thought this was sensible" does not.** That is the entire purpose of this table.

---

### 5. Scoring Framework

> **Direction convention, stated once and never inverted: `100 = strongest posture, 0 = weakest`. A penalty is SUBTRACTED for each issue found.**

> **Model vocabulary — read once, resolves the rest of §5.**
> The shipped model is **`scoring.yaml` v5.2.0 — a penalty-based POSTURE model.** Every vendor starts at 100; each issue found subtracts a penalty sized by severity; a category's posture is 100 minus its own penalties, and the overall posture is **100 minus the total penalty divided by a fixed divisor**, published with a letter grade A–F and a plain-English reason for every deduction. It is inspired by UpGuard's subtractive method but is our own — our 0–100 scale, our categories, our differentiators (§5.10).
>
> **Why the model changed from a weighted-mean *risk* score to a penalty *posture* score.** The earlier design (d1–d3, a `category → subcategory → signal` weighted mean on a `0=low / 100=high` risk scale) needed a defensible *weight* for every category — *why is Cyber Hygiene 31%?* — a question with **no authoritative answer** (§5.6). The penalty model **deletes that problem**: a category's influence emerges from how many issues it has and how bad they are, so there are no weights to derive or defend — **open items 9, 10 and 13 disappear.** The weighted-mean lineage is retained in §5.6 for provenance and for the benchmark cross-check it still gives us; the current model is penalty-subtractive throughout, and any category-percentage figure elsewhere in this document is superseded d3 history.

#### 5.1 Architecture

Every score is a chain of traceable steps. Nothing is computed that cannot be walked backwards.

```
Vendor (name | domain)
   ↓  entity resolution → candidate set → resolved identity + confidence
Collectors (one per source, independent, failure-isolated)
   ↓  raw response  ────────────────────────────► EVIDENCE STORE (immutable, timestamped)
Normalizer → Finding{observation → severity → PENALTY}
   ↓  NIST SP 1326 modifiers: age × frequency × mitigation, applied to the penalty
   ↓  each (category, signal) group COLLAPSES to its worst instance (§5.3)
Penalties summed PER CATEGORY, each capped at 100
   ↓  GATE CHECK ── sanctions hit / ambiguous entity ──► BLOCKED (no score emitted)
Category posture = 100 − its own penalties           (for the breakdown)
   ↓  OVERALL posture = 100 − (total penalty ÷ a FIXED divisor, currently 2.86)
   ↓  CRITICAL CEILING ── directly-observed current critical ──► posture capped at 49
Grade (A–F) + confidence (coverage) + ASSURITY (§5.11), each reported separately
   ↓  the Ghost — below 40% coverage the grade is refused, not published
   ↓  + INHERENT (buyer-declared) → RESIDUAL, a 16-cell lookup (§5.12)
   ↓  + PEER PLACEMENT and EXPECTATION GAP, computed from the book (§5.13)
Explainability report — every penalty linked to evidence AND to a plain-English reason
```

**Order matters and is not negotiable:** gate → total → ceiling. The gate precedes everything because a blocked record has no score to cap. The ceiling comes **after** the division because it corrects that step's compensatory arithmetic — applying it earlier would let the spreading dilute it, which is the exact defect it exists to fix.

**Overall is `100 − total penalty ÷ a fixed divisor`, not a running sum and not an average of what answered.** Summing every penalty across categories would tank a merely-mediocre vendor to F (one −40 is 40% of the whole score). Averaging only the *covered* categories was worse in a subtler way: a clean category entered the mean as a 100 and pulled the score **up**, so publishing a trust page bought +23 posture and a source outage *lowered* a vendor's grade. That directly contradicted §5.4. Each category's damage is now capped at its own 100 and divided by a divisor **fixed by the model** (currently **2.86**), so a silent source contributes no penalty and cannot move the denominator. A genuine live critical is handled non-compensatorily by the ceiling, not the sum.

The divisor is calibrated, not assumed: a divisor equal to the category count is algebraically the plain mean of the category postures, but that scored **every** benchmark vendor A (86–92) — including one carrying 13 known-exploited product matches. The current value separates the evidenced-clean vendors from those with real findings against the frozen corpus in `backend/tests/fixtures`.

**The divisor is bound to the number of SCORING categories, and this is load-bearing.** Maximum damage is `scoring_categories × 100 ÷ divisor`. At seven categories and a divisor of 4 that was 175 posture points. The E5 restructure left **five** scoring categories and two context categories that can never penalise (§5.2) — so holding the divisor at 4 would have cut maximum damage to 125 and made the model **quietly more forgiving**, because a larger *fraction* of the model would have to fail before a vendor bottomed out. Nobody would have decided that. `test_divisor_preserves_maximum_damage` counts scoring categories only and asserts the relationship holds: 7→4.00, 6→3.43, **5→2.86**, 4→2.29, 3→1.71.

**Two properties are non-negotiable:** the evidence store is written **before** anything is scored, and every arrow is reversible. Finding A is the reason.

#### 5.2 Categories — organised by business risk, not by source

Categorising by source (`DNS → DNS`) is unexplainable to a client. Categories answer questions clients actually ask. **A penalty model has no category weights** — a category's influence emerges from the issues found in it.

**Five categories score. Two carry context and can never penalise.** The line between them is one question: a scoring category answers *how exposed is this vendor to compromise?*; a context category holds signals we still collect and still count toward coverage, but which answer a different question.

| Category | Engine key | The question it answers | Sources |
|---|---|---|---|
| **Breach & Compromise History** | `breach_compromise_history` | Has something already gone wrong? | HIBP, NVD, KEV, EPSS |
| **Attack Surface & Hygiene** | `attack_surface_hygiene` | Is the estate being kept? | CT, DNS, TLS, headers |
| **Identity & Email** | `identity_email` | Can this vendor be impersonated? | DNS |
| **Transparency** | `transparency` | Can this vendor be *told* about a vulnerability? | `security.txt`, trust pages |
| **Compliance & Regulatory** | `compliance_regulatory` | Do their certification claims check out — and has a regulator acted? | Trust pages, cert registries, regulator RSS |

| Context category | Engine key | The question it answers | Feeds |
|---|---|---|---|
| **Continuity Context** | `continuity_context` | Will this vendor still be trading? | the Continuity axis |
| **Assurance Context** | `assurance_context` | Has anyone independent checked? | **Assurity** (§5.11) |

#### 5.2.1 Business Stability — A Separate Scoring Axis (v5.3.0)

**Financial health is a SEPARATE 0-100 score from cybersecurity posture.** A bankrupt company can have excellent cybersecurity controls, and a secure startup can run out of cash. These are separate risk dimensions that must not be conflated.

The Business Stability axis answers: *Is this vendor financially viable?* It uses the same penalty-based approach but with different mechanics appropriate for financial data:

| Aspect | Cybersecurity Posture | Business Stability |
|---|---|---|
| **Starting point** | 100 (perfect security) | Age-based (70-100, by company age) |
| **Penalties** | Technical security issues | Financial distress signals |
| **Bonuses** | None | Survivorship bonuses for longevity |
| **Gate** | Sanctions (political/legal) | Active insolvency (financial) |
| **Coverage** | Evidence coverage | Registry coverage (jurisdiction-dependent) |

**Age-based base scores** reflect the well-documented failure rate curve:
- **Startup (<2 years):** Base 70 — highest failure rate (~3× established)
- **Young (2-5 years):** Base 85 — still establishing
- **Established (5-10 years):** Base 90 — proven model
- **Mature (10-20 years):** Base 95 — demonstrated staying power
- **Veteran (20+ years):** Base 100 — survivorship credit

**Financial penalties** include:
- Active insolvency proceedings → **BLOCK** (gate, not a score)
- Historical insolvency → −5 penalty
- Declining revenue (3+ quarters) → −15 penalty
- High debt-to-equity (>3x) → −10 penalty
- Negative cash flow (2+ years) → −10 penalty

**Survivorship bonuses** reward longevity:
- Mature (10-20 years): +5 bonus
- Veteran (20+ years): +10 bonus

**Confidence adjustments** by age band:
- Startup: −0.20 (harder to assess)
- Young: −0.10
- Established/Mature/Veteran: 0.00
- Unknown: −0.05

**Data sources** for Business Stability:
- OpenCorporates (global entity registry)
- Registry Lookup (national registries)
- EU Insolvency Register
- German Insolvency Register
- Canada Bankruptcy Database
- ASIC Insolvency Register (Australia)
- SEC EDGAR (US public companies, XBRL financials)

**API endpoints** (Phase 4):
- `GET /api/vendors/{ref}/stability` — Business Stability score
- `GET /api/vendors/{ref}/financial` — Raw financial profile data

**Why two categories stopped scoring.** Companies House maps liquidation, receivership and insolvency onto `entity_inactive`, which used to cost **20 points of technical security posture** — but a vendor entering administration does not thereby have worse TLS. And penalising the absence of an audit or a public security page is a tax on audit budget: it measures spend rather than risk, and falls hardest on exactly the small suppliers this product exists to assess fairly. Both facts are still collected and still published. Neither charges posture.

**Why the signals were not simply deleted.** `planned_signal_count` is the confidence denominator. Deleting nine signals would raise every vendor's confidence for no evidential reason — the check still ran; we merely stopped charging for it. Keeping them holds the denominator at **27** and keeps the receipt showing the check happened. `test_context_categories_never_penalise` asserts they carry no penalising band; the moment one gains a penalising band it has become a scoring category and the divisor must be re-derived.

**Identity & email is separated from general hygiene deliberately.** It is one decision at the apex, answered by three DNS records that stand or fall together, and — unlike TLS or certificate validity — a per-host *rate* has no meaning for it. Keeping it apart stops exposure normalisation being applied where it does not belong.

**Signals are unique across categories.** The engine keys penalties on `(category, signal)`, so a signal appearing in two categories would be charged twice. Asserted by `test_no_signal_appears_in_two_categories`.

**Sanctions is not a category.** It is a **gate** (§5.5.1). Five further categories (Supply Chain, Data Privacy, Geopolitical/FOCI, ESG, Emerging-Tech/AI) are **designed but held** — no free lawful source feeds them yet (§5.9).

#### 5.3 Severity penalties and the four NIST variables

Every signal is a **pass** (no penalty) or a fail at one of four severities. These four fixed penalties are the **only points table** — no per-signal tuning, no weights.

| Severity | Penalty | Assign when… |
|---|---|---|
| **Critical** | **−40** | Actively dangerous & confirmable — expired production cert, unpatched KEV CVE, breach exposing passwords/cards, CVSS 9–10 |
| **High** | **−20** | Serious weakness — no DMARC, TLS 1.0/1.1, confirmed breach of personal data, CVSS 7–8.9 |
| **Medium** | **−8** | Meaningful gap — weak TLS, `p=none`, missing SPF, CVSS 4–6.9 |
| **Low** | **−3** | Minor hygiene — a missing security header, no DNSSEC, CVSS 0.1–3.9 |
| **Informational** | **0** | Recorded, not scored — unverifiable (unproven open port, unconfirmed media) |

Each finding's penalty is then adjusted by the **NIST SP 1326** variables before it is subtracted — a decay-and-context model handed to us by a US federal publication. **Adopt it and cite it:** the hardest thing to defend is *why a 2013 breach counts less than last month's*, and "NIST says so" beats any curve we invent.

```
effective_penalty = severity_penalty × age × frequency × mitigation
```

| Variable | Implementation | Defence |
|---|---|---|
| **Age** | `max(0.15, 0.5 ^ (months / 36))` — 3-year half-life, **floor 0.15** | Decays but **never reaches zero** — a breach never becomes irrelevant |
| **Frequency** | `1 + 0.25 × (n − 1)`, capped 2.0 — **recurrence only** | Three breaches are a pattern, not one breach ×3 |
| **Mitigation** | ×0.6 where remediation is **evidenced**, not claimed | Claims don't count; corroboration does |

**Frequency replaces summing — it never stacks on top of it.** Every `(category, signal)` group
contributes **one** penalty: its **worst instance after decay**. Recurrence is then expressed once,
by the frequency factor. Three `personal_info` breaches are `20 × 1.5 = 30`, *not* `20+20+20 = 60` —
otherwise recurrence would be counted twice, in both the sum and the multiplier, and two breaches
would already outweigh a −40 critical. Because the representative is the worst *after* decay, a
fresh High can legitimately outrank a long-decayed Critical: the finding named is the one actually
driving the score.

**Keyword-matched CVE bags are frequency-exempt** (`modifiers.frequency.exempt_signals`). Forty
name-matched CVEs are match *volume*, not forty distinct events; they collapse to their worst
representative with **no** amplification, so coarse-match noise cannot tank a clean estate. Realized
events — breaches, regulator actions — are **not** exempt: recurrence there is a real pattern.

**Mitigation is never inferred from severity.** It travels on `Finding.remediation_evidenced`, set
only where a source positively corroborates a fix. It is deliberately **not** encoded in the severity
bands: doing both would discount a fix twice. This variable is **live in the engine but dormant in
practice** — no free source we lawfully collect evidences that a given vendor has remediated a given
issue, so nothing sets it today. It is honest to describe the rule; it would not be honest to imply
vendors are currently receiving this discount. (This corrected a real defect: NVD previously banded
every sub-HIGH CVE as `remediated`, which asserted a fix that NVD never observed. Bands now state
CVSS severity only — `cvss_critical` / `cvss_high` / `cvss_medium_or_low`.)

##### 5.3.1 Every deduction carries a sentence

A score a client cannot have explained to them is precisely what this methodology exists to prevent, so the model stores the explanation next to the band that triggers it:

```yaml
reasons:
  dmarc:
    absent: "Anyone can send email pretending to be this company. There is no published rule
             telling mail servers to stop it, which is the standard opening move in invoice
             fraud and staff impersonation."
```

Written **consequence first**: the lead clause is what a procurement lead understands, the technical fact sits underneath. All **54** penalising bands are covered, and the loader **refuses to start** if a penalising band has no reason — or if a reason survives for a band that no longer exists. The explanation cannot drift from the model, in either direction, which is the same class of guard as §5.3.2.

The receipts also explain any **adjustment**, which is where the NIST variables become legible rather than merely defensible: *"This is historic, so it counts for less than a recent finding would — at full weight it would have been −40."* For a frequency-exempt bag: *"13 matches found — only the most serious one is counted, so a long list of name matches cannot inflate the score."* The wording distinguishes the two treatments deliberately, because describing a coarse CVE bag as a "repeated pattern" would assert a calculation that never ran.

##### 5.3.2 Config that scores nothing must not look like config that scores something

The model is the deliverable, so a key sitting in `scoring.yaml` reads as a **claim**. An unread key is a claim the code does not honour — and this model accumulated four of them before they were caught in one review: two NIST variables (frequency, mitigation) sat inert behind hardcoded identity values while the docs and the UI advertised them as applied; a KEV band `patch_evidenced` that no collector ever emitted; and an NVD band named `remediated` that only ever meant "below CVSS HIGH", asserting a fix that NVD never observed.

Every top-level key must therefore be declared as either **read by the engine** or **documentation-only**, with a stated reason for the latter. Anything else fails at load. Adding config is now a conscious choice rather than a hope, and the failure mode that produced all four defects is closed structurally rather than fixed four times.

**The severity ladder is graduated, not binary.** DMARC is the clearest example — the band *is* the explanation, and a vendor with `p=none` is not penalised the same as one with no DMARC at all:

| Observed | Severity | Penalty | Reasoning |
|---|---|---|---|
| No DMARC record | **High** | −20 | No BEC protection at all |
| `p=none` | **Medium** | −8 | Monitoring only — no enforcement |
| `p=quarantine` | **Low** | −3 | Partial enforcement |
| `p=reject` | **pass** | 0 | Full enforcement |

This graduation is exactly what a naive subtractive model throws away (§5.10). Other representative bands live in `scoring.yaml`: TLS 1.0/1.1 → High · cert expiring <14d → High · expired production cert → **Critical** · no HSTS/CSP → Low · HIBP breach exposing passwords/cards → **Critical**, email-only → Medium · KEV-listed product CVE unpatched → **Critical** · NVD critical unpatched → Critical.

**All bands live in config, not code.** Changing the model must not require a deploy — it is the deliverable and must be arguable with a client in a room.

#### 5.4 The rule that keeps the model honest

> **Missing data reduces *confidence*. It never changes *posture*.**

Mechanically:

- A signal that returns nothing is **dropped from its category's coverage** — never scored as a comfortable pass, never as a penalty. Because the overall divisor is **fixed by the model** rather than set by how many categories answered, an absent category contributes no penalty and cannot move the denominator: it genuinely neither helps nor hurts the posture. This is now enforced arithmetically and guarded by a regression test — identical findings with varying silent sources must produce an identical posture. It was *not* true before the fixed divisor, when averaging the covered categories let a clean receipt enter as a 100 and lift the score.
- **Confidence is pure evidence coverage:** of the signals we planned to collect, how many returned data. `coverage = covered / planned`; **High ≥ 0.90 · Medium ≥ 0.70 · Low < 0.70.**
- **Below `coverage < 0.4` the product refuses to publish a posture** and returns **`Insufficient evidence`** with the coverage gaps enumerated — *the Ghost*.

**That refusal is a feature and the strongest single expression of Finding A.** A model that always produces a number is a model that lies when it has nothing. MYOB (§2.3) exists to prove this branch fires: a thin entity record must yield *low confidence*, **not low posture** — and **a vendor cannot look strong simply by being invisible**, nor be punished for silence; silence is a confidence problem, surfaced as such.

> **Why confidence is coverage, and nothing more.** An earlier design multiplied coverage by source-reliability and freshness, and combined agreeing registers with a noisy-OR. That was defensible but hard to explain in a room and easy to contest number-by-number. The shipped model makes confidence **exactly one thing a client can verify** — *what fraction of the planned evidence came back* — and folds all the "how much do we trust this source" nuance into whether a signal is collected at all, and into the clean-receipt discount (§5.4.2). One axis, one sentence.

##### 5.4.1 Reading posture against confidence — the Ghost

Posture and confidence are **two axes, never one number**. Collapsing them is the failure this whole section exists to prevent, so the scorecard shows the confidence band **beside** the grade, never the grade alone.

| | **Confidence High / Medium** | **Confidence Low** |
|---|---|---|
| **Strong posture** | **Evidenced-strong** — corroborated. The only place a good grade truly means low risk. | **The Ghost** — *looks* clean only because we found little. **Not a strong vendor; an unassessed one.** → questionnaire |
| **Weak posture** | **Verified exposure** — act on it. | **Uncorroborated signal** — something is there we can't stand behind. → review, don't report |

**The Ghost is the quadrant that matters.** It is the visible form of *"absence of evidence is not evidence of absence"* (§3.1) and the reason §5.4 exists. A small clean vendor and a badly-run obscure one **both** land here, and the model cannot distinguish them — so it says so, by name, rather than quietly rewarding invisibility. Below 40% coverage the Ghost hardens into an outright refusal; a directly-observed current critical (§5.5.2) is the one thing certain even on thin coverage, so a fired ceiling **bypasses** the Ghost refusal.

Two consequences for the build: the scorecard shows the confidence band **beside** the grade, never the grade alone; and `Uncorroborated signal` must never be presented to a client as a finding — an uncorroborated adverse-media hit against a small vendor is precisely the defamation exposure in Part 2 of this document §4.2.

##### 5.4.2 The clean receipt — "checked and clean" ≠ "never checked"

Confidence being coverage still leaves **two** kinds of "missing", and conflating them is what would make every clean vendor read as a Ghost:

- **Never checked** — the source did not run, or ran and errored. No coverage. Correctly costs confidence.
- **Checked and clean** — the source was *successfully queried* and came back empty: HIBP has no breach, CISA KEV no product match, NVD no recent critical CVE. This is a real, citable observation — *"we queried the largest public breach corpus on `<date>` and this domain is absent"* — and it **counts toward coverage** as a benign **pass** (no penalty), not silence.

This is what lifts a genuinely-clean vendor out of the Ghost without claiming false certainty: the claim is never "secure", only "**no KNOWN event, per this named source, on this date**". The residual uncertainty rides on the fact that a clean receipt is a *pass*, not a definitive all-clear — an authoritative register is the exception, because a GLEIF "active / good standing" is an *exhaustive* positive fact (the entity either is or isn't on the register), not a hedged absence.

##### 5.4.3 Calibration is evidence, not assertion — the frozen corpus

A model that is never re-measured drifts. So the five benchmark vendors (§2.3) have their collector output **captured once and frozen** in `backend/tests/fixtures`, replayed through the real engine against a pinned clock, and asserted down to per-category penalties. Any change that moves a number fails the build and the diff names the vendor and the category that moved — an intended re-grade and a regression no longer look the same.

This is what makes the numbers in this document defensible rather than plausible. Three claims here are corpus-measured, not assumed:

- **The divisor.** A divisor equal to the category count — the plain mean of the category postures — scored **every** benchmark vendor A (86–92), including one carrying 13 known-exploited product matches. The current value was chosen from a sweep because it separates the evidenced-clean vendors from those with real findings, and it moves with the number of scoring categories (§5.1).
- **The confidence bands.** Real vendors return **0.96–1.00** coverage and band **High**, so the ladder discriminates. A test fails if a signal is ever added with no collector to feed it — which would grow the denominator, make `High` unreachable, and quietly turn every vendor into a Ghost.
- **The invariant.** Silencing every clean source across all five vendors drops confidence (1.000 → 0.692) with **zero** posture movement.

An honest note on method: the corpus **falsified** a prior claim during this work. The assertion that the Ghost fires on nearly every vendor came from a three-source synthetic probe; real fourteen-collector runs disproved it, and the planned "fix" would have made confidence *worse* by weighting a one-signal category equally with an eleven-signal one. It was dropped. That is the corpus doing its job.

#### 5.5 Gates and the ceiling — where subtraction stops

Spreading the total across a fixed divisor is *compensatory* — strengths dilute weaknesses — which is correct for hygiene signals that genuinely trade off, and **wrong** for the three cases below. Two mechanisms override normal subtraction.

##### 5.5.1 Gates — the model emits nothing

| Signal | Behaviour | Authority |
|---|---|---|
| **Sanctions hit** | **BLOCK** → adjudication queue. **No score emitted.** | `Autonomous Sanctions Act` s 16(7) |
| **Entity resolution ambiguous** (confidence < 0.5) | **BLOCK** → manual confirmation. **No score emitted.** | §3.1 — never silently score the wrong company |

**Why a sanctions hit blocks rather than scores badly — or grades F.** A defence under s 16(7) is **not partially available**, so a weighted contribution is meaningless — but grading it F is no better, because a fuzzy name match would then have a machine silently make a **criminal accusation against a real company**, and a number in a field discharges no legal burden. An adjudication record does. **Surface generously, adjudicate manually, never auto-conclude.** Matching is whole-word (so *asana* can't trip on *villaSANA*) and recall-tuned; the clearing is itself the evidence. **This is the one place recall beats precision** — an inversion of the default everywhere else, stated wherever it appears. Xero (§2.3) was correctly BLOCKED here in live testing.

##### 5.5.2 The critical ceiling — non-compensatory (our knockout)

> **A vendor with a directly-observed current critical cannot be graded well because its DMARC is good.**

Left uncorrected, spreading the total across a divisor launders a critical finding into a comfortable grade — exactly the black-box number the AFA warns about. So a **directly-observed current critical caps the posture at the top of Grade D (49)**, so one severe live issue can't be diluted by good hygiene elsewhere.

```
if any Critical finding is DIRECTLY OBSERVED AS CURRENT and confidently attributed:
    posture = min(posture, ceiling_score)   # caps DOWN; never sets, never floors up
```

**The auto-ceiling is narrow by design.** It fires only on criticals we can directly observe as *current* — an **expired production certificate seen live** (`scoring.yaml` `critical_ceiling.auto_signals`). A **KEV name-match** establishes *"this product line has had a known-exploited CVE"*, not *"currently unpatched here"* — so it **penalises** (Critical, via worst-of) and flags for review, but does **not** auto-ceiling. Capping every software vendor on a historical Jira/Confluence CVE would not be defensible.

| Auto-ceilings (directly observed, current) | Critical penalty + review flag (can't confirm current) | Not Critical (scores normally) |
|---|---|---|
| **Expired certificate** serving production — seen live | **KEV-listed CVE** name-matched to a product | High CVSS, no exploitation evidence |
| | **Breach** not evidenced as remediated | Cert expiring in 20 days · historical remediated breach |

**Three constraints, each doing real work:**

1. **Confident attribution is a precondition.** An unattributed critical caps the *wrong company*. The ceiling requires entity-resolution confidence ≥ 0.7 — otherwise the finding routes to `Uncorroborated signal` (§5.4.1).
2. **The ceiling must name its cause.** `"Posture capped at Grade D — expired production certificate on <host>, observed live."` An unexplained cap is an unexplainable score, a Finding A liability. **A ceiling that cannot state its cause must not fire.**
3. **It caps, it does not set.** A vendor already below 49 stays where it is; the ceiling establishes a maximum, never a verdict — otherwise it becomes the gate it deliberately is not.

*Provenance: re-expressed from the earlier "knockout floor" — which floored **risk up** on a `0=low` scale to `band.moderate_lower` — into a posture **ceiling** that caps the score **down** to the top of Grade D on the `100=strong` scale. Same non-compensatory intent (correctly identified by the reviewed "CRO Trapdoor" proposal), correct direction for the new scale, and with the old open item 10 — pinning the exact band boundary — dissolved, because 49/Grade D is a plain grade cut-point, not a magic number.*

#### 5.6 Why there are no category weights (and what the benchmark still gives us)

> **This section is retained for two reasons: the record of *why* category weights were abandoned, and the commercial-platform benchmark that still cross-checks our *severity ordering*. The weight tables below (d1/d2/d3) are superseded lineage — the shipped v4 model has no weights. §5.9 is the current catalogue.**

The single hardest thing the earlier weighted-mean design had to defend was a **weight** for every category — *why is Cyber Hygiene 31% and Business Stability 7%?* **No authority publishes vendor-risk category weights.** NIST, APRA and ISO publish *categories*; none says Cyber is worth 24%. Relative weighting is a **risk-appetite judgement**, and the AFA (§1 thesis) is explicit it must be the user's: *"users must be able to determine their own rating system with regard to risk mapping."*

**The penalty model dissolves the problem rather than defending an answer.** A category's influence **emerges** from how many issues it has and how bad they are — there is nothing to weight, so **open items 9, 10 and 13 (intra-weights, band boundaries, the weight sensitivity analysis) disappear.** This is the core reason the model was rebased: not that the old weights were provably wrong, but that *any* set of weights was a standing liability with no authoritative anchor, and a penalty model needs none.

**What the benchmark still gives us — severity ordering, not weights.** Bitsight and UpGuard publish their weightings; a client with either subscription can check ours in an afternoon, so the comparison below (verified 17 Jul 2026 from vendor documentation, quoted not summarised) was done. It no longer sets any *weight*, but it cross-checks the **relative severity** we assign signals: TLS and email-auth sit high in our Critical/High tiers (both platforms rank them top); a missing **DMARC** is a deliberate **High** despite Bitsight's low weighting, because its primary harm is business email compromise — a fraud loss structurally invisible to a breach-trained model (FBI IC3 2024 ranks BEC **2nd by dollar loss, US$2.77bn**; ACSC 2024–25 at **>A$55k/incident**); and HTTP **headers rank last** (**Low**), which is where Bitsight rates them (*informational — zero rating impact*), because a header is a mitigation, not a vulnerability. **They weight by breach correlation; we penalise by departure from a governance standard** — where our severity departs from their ordering we owe a stated reason (DMARC) or we are simply wrong. The retained lineage tables below are the paper trail for that reasoning; they are **not** a live derivation.

**The honest starting point: no authority publishes vendor-risk category weights.** NIST, APRA and ISO publish *categories*; none of them says Cyber is worth 24% and Financial 5%. Relative weighting is a **risk-appetite judgement** — and the AFA (§1 thesis) is explicit it must be the user's to make: *"users must be able to determine their own rating system with regard to risk mapping."* There is no "correct" weighting to derive. The goal is a **transparent, reasoned, tunable default** defended *procedurally*: we defend **how** it was formed and **prove the exact values are low-stakes**, even where reasonable people would choose differently. That is the defensibility Finding A actually requires — and, unlike an inherited-authority claim, it rests on nothing a reviewer can falsify.

**Four anchors, strongest to weakest — each carries the load the layer below cannot:**

| Layer | Anchored to | Nature |
|---|---|---|
| **Which categories exist** | NIST SP 1326 five due-diligence areas · CSF 2.0 GV.SC · ISO 27036 | **Authoritative** — a published standard names them |
| **What must dominate / never compensate** | Australian law — sanctions gate (Autonomous Sanctions Act, Finding B), critical ceiling (observed exploitation, §5.5.2), fourth-party priority (CPS 230 ¶48) | **Legal** — a structural rule with a statutory basis |
| **Relative ordering of the weights** | Cross-checked against Bitsight / UpGuard / SecurityScorecard published weights (§5.6.2) | **Benchmarked** — three commercial platforms; diverge only with a stated reason |
| **The exact percentages** | A documented default — **client-tunable in `scoring.yaml`** and **sensitivity-bounded** (open item 13) | **Procedural** — defended by transparency + proof of low sensitivity, not authority |

**Observability is NOT in the weight — this is the second correction.** The retired formula multiplied importance by observability. That contradicts this model's central rule (§5.4): *missing data reduces confidence, never risk.* Down-weighting a category because we observe it poorly is that exact forbidden move, one level up — it lets invisibility shrink a category's contribution to **risk**. Unobservable categories are already handled correctly by **renormalisation over present signals + reduced confidence** (§5.4). **Observability therefore lives only on the confidence axis.** It may *inform* the default ordering as one input alongside structure and benchmark, but it is never a multiplier that manufactures a "derived" number.

**The sentence that survives a CRO checking it:**

> *No standard publishes category weights; weighting is a risk-appetite decision a regulator says must be yours. So we ship a transparent default — structure NIST-anchored, non-compensatory rules legally anchored, ordering cross-checked against three commercial platforms, exact values shown by sensitivity analysis to sit inside a band that does not change the risk rating — and every one is yours to change, in a config file, without a redeploy.*

This makes the **sensitivity analysis (open item 13) load-bearing, not optional**: it is the step that converts "these values are judgement" into "these values are judgement *and provably low-stakes*." Without it the procedural defence is incomplete.

**Retired lineage (kept for honesty, not authority).** The original six-category derivation used `client_category_weight × observability`. Both inputs are now rejected — the client-weight anchor was arbitrary, and observability belongs in confidence. The table below is retained **only to show the lineage the current numbers came through; it is not a live derivation.** Current weights are §5.9's.

| Our category | ~~Client category (weight)~~ *(anchor rejected)* | ~~Observability~~ *(→ confidence)* | Note | ~~Raw~~ | **d1 weight** |
|---|---|---|---|---|---|
| Cyber Hygiene | Information Security (1.5) | 1.0 | Direct observation | 1.50 | 32% |
| Incident History | Information Security (1.5) | 0.9 | High precision; GDELT noise | 1.35 | 29% |
| Supplier Transparency | Compliance (1.2) | 0.7 | Self-reported | 0.84 | 18% |
| Supply Chain | Operational Risk (1.2) | 0.5 | Only what DPAs disclose | 0.60 | 13% |
| Business Stability | Financial (0.8) | 0.5 | US-listed skew | 0.40 | 8% |
| ESG | ESG (0.8) | 0.3 → 0 | Licence held | 0.24 | 0% |
| Regulatory & Legal | — | — | **Gate, not weighted** | — | **—** |

##### 5.6.1 Intra-category weights — the same discipline, one level down

The table above sets weights **between** categories. Weights **within** a category are a second, separate problem, and the temptation is to split evenly — `DNS 25% / TLS 25% / Headers 25% / CT 25%`. **An even split is not neutral; it is an unstated claim that four signals carry equal risk, which is false and indefensible on exactly the grounds §5.6 is built to survive.**

Same four-anchor discipline applies one tier down. Within a category, order signals by **directness of the risk each evidences** (a claim we document per source in Part 3 of this document), **cross-check the ordering against the equivalent commercial-platform vector where one exists** (§5.6.2), and treat the exact split as a tunable, sensitivity-bounded default. **Observability does not enter here either** — a signal we read poorly lowers confidence in that signal, it does not lower its risk weight.

Cyber Hygiene, worked (the only category resolved at d1; the full nine-category subcategory split is §5.9):

| Signal | Weight | Derivation |
|---|---|---|
| **DNS / DMARC** | **35%** | Highest — *"the sharpest cheap signal available"*, gradeable on a real scale (§5.3), ties directly to BEC |
| **TLS** | **30%** | Direct observation; protocol/cipher facts, not inference |
| **Headers** | **20%** | Direct, but weaker risk linkage — a header is a mitigation, not a vulnerability |
| **CT** | **15%** | Lowest — shows certs *issued*, **not hosts live**; infers sprawl rather than evidencing it |

**CT is weighted lowest despite being our most reliable source**, and that is the derivation working correctly: **reliability of the source and directness of the risk are different things.** CT tells us something true (a cert exists) that only weakly implies risk. DMARC tells us something true that directly implies exposure. Conflating the two is how models get accused of arbitrariness.

> ⚠ **The table above is superseded — see §5.6.2.** Benchmarking against Bitsight's and UpGuard's published weights broke two of these four numbers. The *derivation method* survives; two of its outputs did not. The table is retained here because §5.6.2's argument is unreadable without it.

**The other four categories' intra-weights are unresolved — open item 9.** They are not asserted here rather than guessed and quietly shipped.

##### 5.6.2 Benchmark — where the commercial platforms disagree with us

**Bitsight and UpGuard publish their weights. A client with either subscription can check ours against theirs in an afternoon — so we do it first, and we lose some of it.**

Verified 17 Jul 2026 from Bitsight and SecurityScorecard vendor documentation, retrieved and quoted directly (including SecurityScorecard's *A Deep Dive in Scoring Methodology*, 2025). Not from a secondary summary — an earlier internal summary of these same vendors carried four material errors, which is itself the argument for this rule.

| Signal | **Bitsight** | **UpGuard** | **Ours (d1)** |
|---|---|---|---|
| Email auth (SPF/DKIM/DMARC) | **3%** (1+1+1) | ~9% (Email 7 + DNS 2) | **11.2%** (dns 35 × 32) |
| TLS | **25%** (certs 10 + configs 15) | 17% (Encryption) | **9.6%** (tls 30 × 32) |
| HTTP headers | **0%** — informational, no rating impact | *(within Website 19%)* | **6.4%** (headers 20 × 32) |
| Certificate estate / attack surface | *no equivalent vector* | 11% (Attack Surface) | **4.8%** (ct 15 × 32) |
| Critical vulnerability management | 20% | 13% | *(Incident History)* |
| Open ports | 10% | *(within Network 8%)* | *(not collected — Shodan is roadmap)* |

*Bitsight percentages are of the total rating and reconcile exactly: Compromised Systems 26 + Diligence 71.5 + User Behavior 2.5 = 100, and Diligence's twelve rated vectors sum to precisely 71.5. UpGuard's are of the scan-derived component — where a questionnaire is used the scan is 50% of the final rating, so the figure shown is the OSINT-comparable one.*

**Our ordering is close to inverted.** Bitsight weights TLS **8× above** email authentication; we weight email authentication above TLS. And Bitsight states the ordering is empirical: *"the higher the weighting, the higher the correlation to breach."*

###### The fork: breach-correlation vs governance-departure

**They weight by breach correlation. We weight by departure from a governance standard — a risk-appetite default, cross-checked against them. These answer two different questions, and the difference is why we may lawfully diverge from their numbers.**

| | Commercial platforms | This model |
|---|---|---|
| **Weight basis** | Correlation to publicly disclosed breach | Reasoned default; **structure** from NIST/CPS 230, **ordering cross-checked against these platforms** (§5.6), **values sensitivity-bounded** |
| **Target variable** | *Will this vendor be breached?* | *Where does this vendor's observable posture depart from the governance standard a CPS 230 buyer holds it to?* |
| **Evidence** | 15,000 breaches / 4 years (SecurityScorecard); ML-tuned per issue type | Published standards (structure) + these platforms (ordering) + sensitivity analysis (values) |
| **Fails when** | The harm doesn't produce a disclosed breach | Our default ordering departs from real risk **without a stated reason** |

§2 already commits to this: we are **not a breach predictor**. *"Contradiction-flagging, not replacement, is the product."* A breach-likelihood model and a governance-departure model should not have identical weights, and it would be suspicious if they did.

**So the benchmark is an anchor, not an authority — and the burden is on us at every divergence.** Because we no longer claim an inherited weighting (that anchor was arbitrary, §5.6), we cannot wave the benchmark away by saying "different question." The platforms *do* have data about risk; where our ordering departs from theirs, **we owe a stated, testable reason or we are simply wrong.** The benchmark is layer 3 of the anchor stack precisely so those divergences are visible and accountable, not hidden.

There are three divergences in Cyber Hygiene. **We have a reason for one, and the other two were errors we corrected.**

###### Signal by signal

**DMARC — the divergence survives, on a stated and now-evidenced ground.** Bitsight's target variable is *publicly disclosed data breach*. DMARC's primary harm is **business email compromise**, which is a fraud loss, not a data breach — it typically triggers no disclosure obligation and so cannot appear in the training data. **A model tuned to predict disclosed breaches will systematically under-weight a signal whose main harm never produces one.** CPS 230 is an *operational risk* standard, not a data-breach standard; BEC sits inside our client's risk perimeter and outside Bitsight's target variable.

The loss-magnitude evidence (both government sources, verified 19 Jul 2026):

- **FBI IC3 2024 Annual Report:** BEC losses of **US$2.77 billion** across 21,442 complaints — the **second-highest category by dollar loss**, ~17% of all reported cybercrime loss, and **US$8.5 billion cumulatively 2022–2024**.
- **ASD/ACSC Annual Cyber Threat Report 2024–25:** BEC accounted for **15% of reported attacks**; in FY2023–24 self-reported BEC losses to ReportCyber averaged **over A$55,000 per confirmed incident**.

**The point is not merely that the losses are large — it is that they are large *and structurally invisible to a breach-trained model*.** IC3 ranks BEC second by dollar loss, yet BEC rarely appears in breach-disclosure datasets because it produces no disclosable breach. That is the precise mechanism by which Bitsight's 3% under-weights it, and it is why an *operational-risk* buyer (CPS 230) should not inherit a *breach-likelihood* platform's weight for this signal.

> **Open item 11 — advanced from *unevidenced* to *cited*.** The divergence is now *defended*, not merely *explained*, on two official government sources. Remaining: confirm the exact IC3/ACSC page references against the primary PDFs before client-facing use (search-derived figures, not yet read from source).

**Headers — we were wrong, and our own reasoning says so.** Bitsight rates web application headers **informational: zero impact on the rating.** §5.6.1 argues, correctly, that *"a header is a mitigation, not a vulnerability."* We reached Bitsight's conclusion and then weighted the signal at 20% anyway. There is no rescue argument. The reasoning and the external evidence converge, and against our own number.

**TLS — we under-weight our best-evidenced signal.** Bitsight 25%, UpGuard 17%; both rank it top-3. §5.6.1 calls TLS *"direct observation; protocol/cipher facts, not inference"* — the strongest evidentiary standing anything in the category has. 30% of Cyber Hygiene understates it on both our reasoning and theirs simultaneously, which is the one combination with no defence.

**CT — no external comparator exists.** Bitsight has no certificate-transparency vector. The closest analogue is UpGuard's **Attack Surface (11%)**, and CT is our only attack-surface signal — the only one that finds assets *we did not know to look for*. That argues its 15% is low, but the analogue is loose and this remains the least-anchored number in the table.

###### Revised Cyber Hygiene intra-weights

| Signal | d1 | **d2 (adopted)** | Basis for the change |
|---|---|---|---|
| **TLS** | 30% | **40%** | Two independent platforms rank it top-3; strongest evidentiary standing of any signal we collect |
| **DNS / DMARC** | 35% | **30%** | Stays far above Bitsight's 3% on the BEC/target-variable argument — but no longer *first*, which that argument cannot support |
| **CT** | 15% | **20%** | Absorbs part of the headers reduction; sole attack-surface signal, cf. UpGuard 11% |
| **Headers** | 20% | **10%** | Bitsight rates it zero; §5.6.1's own reasoning agrees |

**The ordering is the defensible claim; the exact values are not.** Per §5.6's sensitivity property — the same self-damping renormalisation applies here — a ±5 shift in any of these moves the overall score by roughly a point and crosses no band. **What must be defended is that TLS now outranks DMARC and that headers ranks last.** Arguing the precise numbers is arguing inside the noise; we will change them on request and show the client the score barely moves.

###### What this benchmark is not

**Three limits, stated so they are not discovered later.**

1. **The taxonomies do not map cleanly.** Bitsight's *Diligence* spans our Cyber Hygiene *and* part of our Incident History. Our `dns` bucket spans their SPF, DKIM and DMARC vectors. Every row above is an approximate alignment, not an identity.
2. **Their "empirical" is weaker than the word implies.** SecurityScorecard concedes in its own methodology that *"statistical power is limited by the amount of breach data that is publicly available"* and that **"as many as 60-89% of breaches go unreported."** Their weights are correlated against a partial, disclosure-biased sample — which skews to regulated and consumer-facing sectors, i.e. **exactly the bias we name in §7.3.** Better grounded than ours. Not authoritative over ours.
3. **A benchmark is not a validation.** Matching Bitsight would not make us right, and diverging does not make us wrong. This section exists so that every divergence is *deliberate and stated* rather than discovered by a client. That is the whole of the claim.

#### 5.7 Two deliberate refusals

**No FAIR quantification.** FAIR quantifies risk in **financial terms** from frequency and magnitude distributions. OSINT gives us **neither** loss magnitude nor per-vendor event frequency. Attempting it would manufacture exactly the false precision that Finding A punishes. **We cite FAIR for the taxonomy discipline — keeping frequency and magnitude from collapsing into one number — and state plainly that v1 lacks the inputs.** Declining to use FAIR, with a reason, is a stronger methodological statement than using it badly.

**No score without confidence.** They are emitted together or not at all. There is no API path that returns a bare number.

#### 5.8 Where AI is used — and where it is fenced

Three designated moments — the first two from the brief, the third an opt-in read layer built in v3.4:

| Moment | Task | Fence |
|---|---|---|
| **Adverse media** | Summarise which GDELT hits **actually matter** — the work a human would otherwise do by hand | Output is a **ranked candidate list with evidence links**, not a score |
| **Trust pages** | Classify unstructured pages into structured certifications + expiry | Output is a **claim record**, flagged self-reported |
| **Whole-record digest** (opt-in) | Summarise *what the sources actually found* — the hash-stamped observations + the published score roll-up — into a plain-English brief for a reviewer | **Read layer only:** describes the evidence, never computes or alters a score, never writes to the evidence store; returned **marked AI-generated**, **cites the `content_hash`es** it was built from, and is fed **only the already-collected, entity-level OSINT the system holds** (bounded per-receipt) |

> **`"the model said so"` is not reasonable grounds.** Under Finding A, the reasonable-grounds representation attaches to the **published score**. So: **AI output is evidence-linked and human-adjudicable, and never silently moves a score.** Conveniently, that is the architecture the evidence store already requires.

> **The digest is provider-agnostic and off by default.** It speaks the OpenAI-compatible `chat/completions` shape, so the operator points it at any provider they trust (OpenRouter, Groq, Google's OpenAI-compat surface) via three env vars — no provider SDK, no lock-in. With none set, the endpoint returns 503 and the feature is inert. This is the system's **single documented data-egress point**; what crosses it is bounded to the already-collected, entity-level OSINT the system holds — the hash-stamped observations + the score roll-up, capped per receipt (Part 3 of this document → *Data egress*) — so the collectors' PII-minimisation is preserved at the boundary and nothing new is exposed. Because it reads the *record* rather than re-deriving it, it cannot become a shadow scorer — the number it describes was already fixed, upstream, by the deterministic engine.

#### 5.9 The category catalogue — signals and their severities

The shipped catalogue is **`scoring.yaml` v5.2.0**. Each signal maps an observation to a severity (pass / low / medium / high / critical) — and therefore a fixed penalty (§5.3) — and every penalising band additionally carries the plain-English sentence shown to the client (§5.3.1). **There are no weights.** Five categories score today and two carry context without ever penalising; five are held; twelve categories exist in structure only as a design record. This section is the catalogue and the defence.

**The expansion carries three non-negotiable corrections, applied at build time and visible in the config**, because without them the wider taxonomy stops being sellable:

1. **Sanctions is a gate, never a subcategory weight.** The proposed taxonomy scored "Sanctions & Watchlists" and "PEP/Sanction Links." Refused — §5.5.1 and Finding B: a weighted sanctions contribution is legally meaningless and a fuzzy match must not silently move a score.
2. **No natural persons.** Executive/brand risk, PEP screening, person-level beneficial ownership, and diversity/inclusion profiling are **excluded at the §4.2 bright line** — and logged in `scoring.yaml`'s `excluded_signals` block with the reason, not silently dropped.
3. **Uncleared *or unfed* categories are held — they emit nothing.** Any category whose source is paid, excluded, unresolved, or unobservable is present in the design record but scores nothing until cleared — the same treatment ESG already gets. In a penalty model this is clean: a held category simply contributes no signals, so it neither penalises nor pretends to be clean; it is disclosed as a coverage boundary. **Adverse Media** was re-promoted to scored once a lawful hard-fact feed was built, and **Business Stability** was re-sourced off EDGAR — traced below.

**Structure over weights.** The commercial platforms nest issue types under factors and weight them by correlation with disclosed breach, learned from tens of thousands of breaches (§5.6). We adopt their *taxonomy instinct* — categories that answer a client's questions — but not their weights: we have neither the breach data nor a path to it, and a penalty model needs no weights. What we keep from the benchmark is the **severity ordering** cross-check (§5.6).

**Seven SCORED categories.** A category is scored only if a working free-data collector actually produces data for it. The re-tier that got here: a reviewer asked the decisive OSINT question — *"how much public data can you actually get for your markers?"* — and categories returning nothing for any vendor were demoted to held. Two were then made real rather than left held: **Business Stability** was re-sourced EDGAR → **GLEIF / Wikidata / RDAP** (EDGAR fed no AU/private vendor; the register trio resolves globally), and **Adverse Media** was promoted to scored on a hard-fact **regulator-RSS** feed (not GDELT sentiment).

| Category | Signals (observation → severity) | Notes |
|---|---|---|
| **Cyber Hygiene & Technical** | TLS version, cert validity, DMARC/SPF/DKIM, HSTS/CSP/X-Frame, `security.txt`, DNSSEC/CAA | Richly fed (CT/DNS/TLS/headers). Graduated severity bands (§5.3) |
| **Breach & Compromise History** | breach by data class · KEV-listed CVE · NVD CVE (+EPSS) | **Directness ladder**: realized breach > exploited (KEV) > theoretical (NVD). Clean receipts count toward coverage (§5.4.2); CVEs are worst-of |
| **Digital Footprint & Assets** | subdomain estate · stale/shadow hosts · weak issuance | Estate *breadth*; counts bucketed into bands (not a log curve). **Single-source caveat:** CT is the only feed — a full CT outage zeros the category and reads as the Ghost (argues for a second footprint source, roadmap) |
| **Vendor Transparency & Governance** | program disclosure · contactability · vuln-disclosure program | Self-reported; a published disclosure path is less gameable than a logo |
| **Business & Financial Stability** | entity status (GLEIF) · entity existence (Wikidata, domain-verified) · domain standing (RDAP) | Authoritative entity standing; **RDAP** makes it universal (any registered domain, no auth). Distress/litigation/ownership-change stay **held** (no free source / need history) |
| **Compliance & Regulatory** | certifications/attestations · disclosure & reporting | Sanctions routes to the **gate**, not here; audit history held |
| **Adverse Media & Reputation** | regulator enforcement / investigation | Hard-fact named actions from official feeds (FTC + cleared), **not** GDELT sentiment. Honest limit: recent-window, US-weighted. Raw GDELT stays `ai_adjudicated`/held |

**Five HELD categories** (designed, emit nothing until a free lawful source clears): **Supply Chain & Dependency** (4th-party enumeration buildable from dns/ct/trust — roadmap), **Data Privacy & Leakage** (no lawful free collector; HIBP paste/domain is paid), **Geopolitical & FOCI** (registry terms + DFAT licence; SOCI 2028), **ESG & Ethical** (Modern Slavery licence), **Emerging Tech & AI** (no lawfully observable source). Plus the **sanctions gate** (ITA active, DFAT held). The held categories are the honest coverage boundary — disclosed on the scorecard, never hidden in a depressed score. The achievable free-OSINT model is, correctly, **cyber-and-breach-heavy** — that is where lawful free public data concentrates.

**Five EXCLUDED signals**, logged in `scoring.yaml`: executive/brand risk, PEP links, person-level beneficial ownership, diversity/inclusion signals (all **natural persons, §4.2**), and shadow-AI usage (**unobservable**).

**Six differentiators — the "advanced and unique" layer.** None requires breach data; each is stated so a client can see the choice:

1. **Two axes, never collapsed.** They emit one number + a letter. We refuse to (§5.4.1) — one number cannot separate *evidenced-clean* from *the Ghost*. Confidence is now computed at the subcategory tier too, then rolled up.
2. **Gate → mean → ceiling.** Non-compensatory corrections they lack: a sanctions gate that emits nothing, and a critical ceiling for observed exploitation. Their closest analog (SSC's -10% breach penalty) is a *weight*; ours is a *ceiling*, because a critical finding must not be averaged away (§5.5.2).
3. **Surgical size normalization** *(the interesting one)*. They normalize broadly because their signals are **counts** that scale with size. **Most of ours are policies** — a giant and a startup each have exactly one DMARC record and one TLS config, so normalizing those would be a *bug*. We normalize **only count-type signals**: Attack Surface (CT subdomains), Adverse Media (GDELT volume), Fourth-Party count. Marked `size_normalized: true` in the config, with the reason.
4. **Size bias handled on both axes.** Log-damping on the *risk* axis for counts, **and** confidence reduction for thin coverage (§7.3). They only do the former. And we are honest about the limit: true peer-relative z-scoring needs a reference population of millions (SSC's own figure) that we do not have — so the PoC log-damps, and peer-relative is a stated roadmap item, not a claimed capability.
5. **Decay lives in risk, per finding.** NIST SP 1326's four variables (§5.3) applied before roll-up — a 2013 breach counts less than last month's, with a US federal citation instead of an invented curve.
6. **Every score reconstructible** from stored evidence (Finding A).

**The honest seams**, stated here so they are not discovered later:

- **A missing DMARC is a deliberate High**, above where a breach-correlation platform would rank email auth, on the BEC/target-variable argument — evidenced by FBI IC3 (US$2.77bn, 2nd by dollar loss) and ACSC (>A$55k/incident); see §5.6. Remaining: verify page refs against the primary PDFs.
- **Concentration Risk is portfolio-scoped** — it needs multiple vendors to compute, so single-vendor scoring can't surface it. A real capability boundary and a roadmap item, not a bug.
- **Business Stability is now an authoritative signal, not absence.** Re-sourced EDGAR → **GLEIF / Wikidata / RDAP**: the register trio resolves globally (e.g. MYOB's LEI shows a *lapsed* registration — a mild governance signal, not silence). Financial-distress/litigation/ownership-change remain **held** — no free authoritative source, and change-detection needs history a snapshot can't give. The MYOB test (§2.3) now fires on a genuine *empty* only for a vendor with **no entity record at all**.
- **Vendor Transparency and Compliance overlap by design.** Both touch ISO/SOC 2 claims. The boundary drawn: Vendor Transparency = *program disclosure + contactability* (governance maturity); Compliance = *specific framework attestations*. A thin seam a client may reasonably want merged — kept separate because the taxonomy named both.
- **There are no weights to defend.** The penalty model replaced the weighted mean precisely so no category-weight derivation has to be argued (§5.6); a category's influence emerges from its issues. The two categories with no benchmark comparator (Digital Footprint, Adverse Media) are also the two whose *severities* lean hardest on our own judgement rather than the platform cross-check — flagged, not hidden.

#### 5.10 Relationship to the subtractive-penalty (UpGuard-style) benchmark

The shipped model **is** a subtractive-penalty model — start at the maximum, subtract fixed severity penalties, letter grades, weakest-link across assets — inspired by UpGuard's method. It is deliberately **not a copy**: we kept the measurement quality a naive subtractive spec throws away, and kept our own differentiators.

**What we took:** the subtractive posture scale (start at 100, subtract per issue), letter grades, and **multi-asset weakest-link** (`scoring.yaml` `aggregation`) — a vendor's posture is its worst scoped asset's, so a rotten `legacy.vendor.com` is not diluted by a clean primary. *(Aggregation is designed; multi-domain collection is a Phase 3 pipeline task — v1 scores the primary asset.)*

**What we deliberately did NOT copy:**

- **Our scale is 0–100, not 950** — a plain percentage a client reads without a decoder ring.
- **Graduated severity bands, not binary pass/fail** — a vendor with `p=none` and one with no DMARC at all must not receive the same penalty (§5.3); collapsing them is a real error, not a simplification.
- **Temporal decay** (NIST SP 1326) — a naive subtractive spec penalises a 2013 breach like last month's.
- **Sanctions is a BLOCK, not a Grade F** (§5.5.1) — a legal requirement, not a scoring preference.
- **A confidence axis with an outright refusal** (the Ghost) — a subtractive score alone still can't tell *strong* from *unassessed*.
- **An immutable evidence store** behind every published number (Finding A).

**The dispute path (open item 12) is the one adopted item still outstanding.** OSINT cannot see internal compensating controls, so the model systematically over-penalises well-run vendors with thin footprints — a Finding A exposure. A vendor should be able to submit verifiable, redacted evidence (SOC 2 Type II, a patched-CVE log) to refute a specific finding; on human adjudication an accepted refute applies the mitigation factor or nullifies the finding, logged immutably. Designed in `scoring.yaml`; the reviewer-facing queue is roadmap.

**Answering the one fair critique** — that a ceiling is a "design smell", a compensatory problem we create with a mean and then patch. It is not a patch; it is a deliberate, named non-compensatory mechanism with three guard rails (attribution ≥ 0.7, named cause, caps-never-sets — §5.5.2). The subtractive alternative avoids the ceiling only by giving up graduated bands, decay and a bounded scale — a worse trade. We keep the mean *and* the ceiling, and say why.

> **Legality veto — recorded because the benchmark advice tripped over the project's own foundation.** The reviewed advice proposed closing the active-exposure gap with **Shodan/Censys free tiers** and OTI feeds (URLScan, OpenPhish, AlienVault OTX, AbuseIPDB, GreyNoise). **Rejected as written:** Censys's free tier ToS (verified live) *expressly prohibits commercial use of any kind* — the VirusTotal trap, and this is a commercial-platform candidate; the OTI feeds each carry an **unverified** commercial-use claim, and the rule is *verify the live ToS before clearing a source*. Logged as candidates requiring verification (Part 3 of this document), not cleared. The gap is real; the shortcut is not lawful.

#### 5.11 Assurity — the third axis, and the compliance gap

*Implemented in `backend/app/assurity.py` and `backend/app/compliance_gap.py`; configured under `assurity:` in `scoring.yaml`. Full derivation in [`scoring_model.md`](scoring_model.md) Part 1 §8.*

Posture cannot answer *"has anyone independent actually checked?"*. **"Their TLS is current and they have no known breaches"** and **"an auditor has examined their controls"** are different claims and a buyer needs both. In the corpus, `synthetic_smallco` sits at **posture 97, assurity 13** — precisely the vendor a single grade misdescribes.

```
Assurity = 100 × sigmoid( A₀ + Σ creditⱼ − Σ γ · ComplianceGapₖ )
```

**Absence never subtracts, and this is enforced rather than intended:** `_validate` rejects a negative credit at load. A vendor with nothing observable sits at a **low intercept (≈23), not zero** — unevidenced is not disproved, and a 0 would read as *audited and failed*. Below `min_observed_signals: 3` nothing is published at all, the same refusal the target-maturity baseline applies at `min_controls`.

This is the half of the E2 argument that was always missing. E2 removed `cert_posture.none_claimed`, an 8-point charge that fired on **five of five** corpus vendors — a tax on audit budget rather than a measure of risk. E2 could say *"not doing what almost nobody does is not a failing"* but could not say *"and doing it **is** a distinction"*, because `penalty_for` returns zero or positive and the engine had no bonus path. This axis is that path, kept separate so that **credit for a trust page can never buy back points lost to an expired certificate**.

**The only thing that subtracts here is a compliance gap**, and a gap is not an absence: it is a vendor **asserting a framework** and being **observed failing one of its controls**. That is a statement about the reliability of their own claims, which is exactly what this axis measures.

The compliance gap is also where §5.6's deleted sector expectation landed, correctly. The superseded `industry_profiles` promoted a finding's *severity* by one step when a sector cited a named instrument — the same evidence scoring differently because of a label **we** assigned, which destroys the cross-vendor comparability the whole model rests on. The obligation was never the problem; the expression of it was:

> *"This DMARC finding is worth more points."* ← an opinion wearing a number
>
> *"Vendor is APRA-regulated and publishes no DMARC record; CPS 234 requires controls commensurate with the threat."* ← disputable, citable, actionable, and changes no arithmetic

Four disciplines the implementation holds: **bound-by** (client-supplied sector, never inferred) is kept apart from **asserted-by-vendor**; a framework may only match on a certification the collector actually read off the trust page, never on the band alone, because otherwise we put a claim in the vendor's mouth and then find them short against it; **distinct observations are counted once** on the axis so publishing more certifications can never cost a vendor more, while every affected framework is still reported; and **posture is untouched**, because the underlying finding already charged whatever it charges.

#### 5.12 Inherent and residual risk — the layer the buyer owns

*Implemented in `backend/app/residual_risk.py`. Full matrix in [`scoring_model.md`](scoring_model.md) Part 1 §9.*

A posture score answers *"how strong is this vendor?"*. It cannot answer *"how much do **we** stand to lose if they fail?"* — that depends on what this buyer has given them, which no amount of outside-in collection can observe. So it is **declared, not inferred**, and the two combine into a deterministic 16-cell lookup.

Three properties are deliberate and each has a failure mode behind it:

- **`max(criticality, data_access_scope)`, never an average.** A low-criticality vendor with production-data access is not a medium-risk vendor. Averaging is how a real exposure gets diluted by an unrelated judgement.
- **Undeclared is not Low.** An unclassified relationship routes to the **deepest** assessment, not the shallowest. The vendors nobody has got round to classifying are disproportionately the ones nobody has looked at, and treating silence as *low* rewards exactly that.
- **A strong posture never reaches Low at high inherent exposure.** An A-grade vendor holding production data lands at Medium. They are still holding it, and the day their posture moves you find out how much was riding on it.

**Residual is recomputed on read and stored nowhere**, so it cannot drift from the two inputs it is derived from — both of which *are* stored. It is advisory: it states what the evidence and the declared exposure together support, and the client decides.

#### 5.13 Peer benchmarking and the expectation gap

*Implemented in `backend/app/benchmarking/`, configured under `benchmarking:` in `benchmarks.yaml`, served under `/api/v2/suppliers/{ref}/…`. Full treatment in [`scoring_model.md`](scoring_model.md) Part 1 §10.*

**`n` travels with every figure, and the refusal is the figure.** A percentile requires **n ≥ 30**, a quartile **n ≥ 8**, and below that the response states *insufficient peer data* with the actual `n`. Both floors are enforced **in code**, not only in YAML — a config edit may raise them and may not lower them. That is not paranoia: the superseded v1 module shipped `min_cohort_n: 1`, and *"make it 3 for the demo"* is exactly how a demo setting survives into production, where it is indistinguishable from a decision nobody made.

The cohort is a **widening ladder** — `sector + size + delivery model`, then `sector + size`, then `sector` — and **every rung it tried is published with that rung's `n`**, because "which peers?" is the only question anyone actually asks about a benchmark. **There is deliberately no rung meaning "every supplier ever assessed"**: a comparison against everything is not a peer group. When the ladder widens, the card says so on its face, because a comparison against a wider population is a weaker claim.

Two further honesty mechanisms. **Comparison reliability is published separately from confidence** — a well-evidenced supplier can sit in a poorly-supported peer group, and those are different facts. And **per-domain discrimination is stated on every row**: a domain where every peer scores 100 cannot rank anybody, so presenting a rank among identical values would manufacture signal from a constant.

**The expectation gap** (`Posture − E[Posture ∣ cohort]`) is the sentence this subsystem exists to produce:

> *"Posture 68. Cohort median (n=14): 87. This vendor sits 19 points below its peer group. The gap is driven by dmarc (absent) — 12 of 14 peers are not in this band."*

A buyer handed `−19` has a fact. A buyer handed `−19, driven by DMARC, which 12 of 14 of their own peers publish` has a **remediation**, and one they can put to the vendor with a count from the vendor's own peer group attached rather than an opinion of ours. The drivers are **ranked, not a decomposition**, and the response says so: since E7a what a finding costs depends on what else was charged alongside it, so per-signal attributions do not sum to the gap and no arrangement of them can be made to.

**The cohort is disputable; the placement is not.** Cohort, snapshot and placement are deterministic lookups over the inputs and carry no independent judgement. Dispute an *input*. Snapshots are frozen when published — recomputing history against today's population would attribute the cohort's movement to the supplier — and are member-bearing only internally; every tenant-facing path calls `.public()`, which structurally cannot carry peer refs.

---

### 6. System Flow

```
                     ┌─────────────────────────────────────────┐
   vendor name ─────►│ ENTITY RESOLUTION                       │
   or domain         │ candidates → resolved identity + conf.  │◄── the hard problem
                     └──────────────────┬──────────────────────┘
                                        │
                     ┌──────────────────▼──────────────────────┐
                     │ COLLECTORS  (parallel, failure-isolated)│
                     │ dns · tls · headers · ct · hibp · kev   │
                     │ nvd+epss · gleif · wikidata · rdap ·     │
                     │ regulatory · trust · ita (gate)         │
                     │ each: timeout, retry, polite rate limit │
                     └──────────────────┬──────────────────────┘
                                        │ raw + fetched_at + source_version
                     ┌──────────────────▼──────────────────────┐
                     │ ★ EVIDENCE STORE (immutable, append)    │  ← written BEFORE scoring
                     │   the legal artefact — Finding A        │
                     └──────────────────┬──────────────────────┘
                                        │
                     ┌──────────────────▼──────────────────────┐
                     │ NORMALIZER → Finding{severity,date,src} │
                     └──────────────────┬──────────────────────┘
                                        │
                     ┌──────────────────▼──────────────────────┐
                     │ SCORING ENGINE (config-driven)          │
                     │ SP1326 decay → penalty → 100−pen → mean  │
                     └──────────────────┬──────────────────────┘
                                        │
                          ┌─────────────▼─────────────┐
                          │  GATE: sanctions hit?     │
                          └───┬───────────────────┬───┘
                         yes  │                   │  no
                    ┌─────────▼────────┐   ┌──────▼──────────────────┐
                    │ BLOCKED          │   │ OVERALL + CONFIDENCE    │
                    │ adjudication     │   │ conf < 0.4 →            │
                    │ queue — NO SCORE │   │ "Insufficient evidence" │
                    └─────────┬────────┘   └──────┬──────────────────┘
                              │ human clears      │
                              └────────►──────────┤
                                                  ▼
                                    ┌─────────────────────────────┐
                                    │ RISK RECORD + SCORECARD     │
                                    │ every deduction → evidence  │
                                    └─────────────┬───────────────┘
                                                  │
                                    ┌─────────────▼───────────────┐
                                    │ ⟳ SCHEDULED RE-SCORE        │
                                    │   delta → flag on movement  │
                                    │   NIST CSF 2.0 GV.SC        │
                                    └─────────────────────────────┘
```

**Speed to answer.** The brief asks how few steps from vendor name to scorecard. The answer is **one**: a name in a field, and the record renders — collectors run in parallel, partial results stream in, and the score resolves as coverage lands. There is no wizard, no source-selection screen, no configuration step. Every extra screen is friction against the user's actual goal.

---

### 7. Limitations

Stated here so they cannot be discovered later. Per the brief: *"Say what a signal does and does not tell you."*

#### 7.1 Structural — these do not close with more sources

1. **~10 of 27 criteria are unobservable to any lawful external observer.** Access controls, security monitoring, data handling, insurance, change management, contract terms. **No source register closes this.**
2. **Absence of evidence is the default state of a clean small vendor and of a badly-run obscure one.** We cannot distinguish them. We can only report low confidence honestly.
3. **Perimeter ≠ posture.** A perfect header score is fully compatible with a catastrophic internal posture. Cyber Hygiene & Technical — the most richly-fed category, and so the one carrying the most signals — measures **what a stranger can see**, which is a proxy, and is labelled as one.
4. **Self-reported is self-reported.** Trust pages are the vendor talking about itself — the exact input the brief is trying to move away from. Included at 0.7 observability for the **fourth-party data**, not for the certification claims.

#### 7.2 Known weaknesses (current model, v4)

| Weakness | Impact | Status |
|---|---|---|
| **No AU sanctions (DFAT)** | Gate runs on US list only | **Blocking — licence query pending** |
| **No ESG** | Category held (emits nothing) | Blocking — Modern Slavery licence pending |
| **FOCI / Provenance absent** | NIST SP 1326 category uncovered | Roadmap — has a **2028 regulatory deadline** |
| **Business Stability = standing, not financials** | Entity standing only (GLEIF/Wikidata/RDAP resolve globally); no distress/litigation data | Structural — no free source for the financial half |
| **Entity resolution** | The accuracy ceiling of the whole system | Mitigated by gates + confidence, not solved |
| **GDELT noise** | Coverage tracks **newsworthiness, not risk** | Held / AI-adjudicated, not scored |
| **crt.sh unstated ToS** | Low residual risk | Accepted, logged; Cert Spotter fallback |

#### 7.3 The bias that must be named

**Coverage tracks company size, not company risk.** A large consumer brand generates more breach records, more adverse media and more filings than a smaller, riskier vendor. Naively, **the model would score big vendors as riskier because more is known about them.**

The confidence mechanism (§5.4) is the mitigation — but it is a mitigation, not a cure, and any client reading a scorecard should be told this in plain language on the scorecard itself.

---

### 8. Deliverables

| # | Deliverable | Artefact | Status |
|---|---|---|---|
| **1** | Research methodology | Part 3 of this document + this §3 + Part 2 of this document | **Complete** |
| **2** | Working PoC | React + FastAPI app, named vendors, SSE, evidence store | **Built** |
| **3** | v1 scoring model | This §5 + `scoring.yaml` (**v5.4.0 — penalty posture + Business Stability axis**) + `scoring_model.md` Part 1 | **Implemented + tested** (~1,334 backend tests, incl. a frozen regression corpus) |
| **4** | Sample output | Client-ready scorecard (the app's Scorecard view), every deduction carrying a plain-English reason | **Built** |
| **5** | Roadmap | §8.3 below | **Complete** |

#### 8.3 Roadmap headline

**FOCI is the highest-value next item** — not an apology. The SOCI Enhanced CIRMP Rules 2026 (registered 9 Jun 2026) make FOCI assessment of major suppliers **legally mandatory** for critical infrastructure operators with a **~mid-2028 deadline**. That is a named buyer with a regulatory clock. Blocked only on registry terms.

**Fourth-party concentration is the sharpest commercial wedge.** CPS 230 ¶48 makes it a regulated obligation; DORA's dry run found **only 6.5% of ~1,000 EU firms passed all 116 data-quality checks**, most commonly failing on **missing subcontractor information** — a documented, quantified market failure in exactly the data we extract for free from public DPAs. Discovering that six vendors share one subprocessor is a finding a client **cannot obtain any other way**.

---

### 9. Open items

Carried from Part 3 of this document and Part 2 of this document, re-prioritised by this design:

| # | Item | Blocks |
|---|---|---|
| 1 | **DFAT licence query** → Australian Sanctions Office | The gate — **product viability, not coverage** (Finding B.4) |
| 2 | **Modern Slavery licence query** → Attorney-General's Department | ESG category |
| 3 | **Re-obtain current CPS 230/CPG 230** (in force 1 Jul 2026) | Every ¶ citation |
| 4 | **Read SP 1326 Pre-Checks + four variables in the repo PDF** | **§5.3 decay model rests on exact wording** |
| 5 | Counsel review: *"trades in personal information"* exception | Commercialisation |
| 6 | Find test vendors: no-footprint + expired cert | §2.3 |
| 7 | Registry terms (ASIC / Companies House / OpenCorporates) | FOCI + Business Stability recall |
| 8 | Per-vendor `robots.txt` check | Trust-page collection |
| 9 | ~~Intra-category weights for the unresolved categories~~ | **DISSOLVED** — the penalty model has no weights (§5.6) |
| 10 | ~~Set the five-band boundaries as a deliberate default~~ | **DISSOLVED** — no risk bands; grades are A–F cut-points and the ceiling is a plain grade boundary (49) (§5.5.2) |
| 11 | ~~Cite a BEC loss-magnitude source~~ **DONE** — FBI IC3 2024 (US$2.77bn, 2nd by dollar loss) + ACSC 2024–25 (>A$55k/incident) now in §5.6. Remaining: confirm exact page refs vs primary PDFs | §5.6 — the DMARC=High severity now *defended*, not just explained |
| 12 | **No vendor dispute path.** Both benchmarked platforms accept evidenced refutes (SecurityScorecard: ~48h decision) precisely because outside-in **cannot see compensating controls and so scores too harshly.** We inherit that bias and offer no correction route | **Finding A** — publishing a score with no contest mechanism, knowing the method systematically over-penalises. §5.5.1's adjudication queue covers gates only. Designed in `scoring.yaml`; queue is roadmap (§5.10) |
| 13 | ~~Run the weight sensitivity analysis~~ | **DISSOLVED** — no weights to sweep (§5.6). What remains is *severity*-tier defence, cross-checked against the commercial benchmark (§5.6), not a weight-sensitivity sweep |

---

### 10. Attribution obligations carried into the product

**These are UI requirements, not footnotes to add later.**

- **NVD** — must display prominently, verbatim: *"This product uses the NVD API but is not endorsed or certified by the NVD."*
- **HIBP** — CC BY 4.0 attribution + link to `haveibeenpwned.com` where the data appears.
- **GDELT** — citation + link to `gdeltproject.org`.

---

### References

- Part 3 of this document — per-source legality, reliability, limits
- Part 2 of this document — model-level legal basis
- `scoring_model.md` Part 2 — the per-metric arithmetic, every constant read from code

**Competitor methodologies — primary sources for §5.6.2** (vendor documentation, retrieved 17 Jul 2026; quoted, not summarised). These are external publications, not files in this repository:

- Bitsight technical documentation — risk category & vector weights, rating scale, normalization, decay
- SecurityScorecard, *A Deep Dive in Scoring Methodology* (2025) — Scoring 3.0 changeover, breach-likelihood table, size normalization. **Limitations p.33; Validation p.32 — source of the 60-89% unreported-breach figure**
- NIST SP 1326 — the four-variable decay model adopted in §5
- APRA CPS 230 — ⚠ superseded since July 2025, see §4.3 — https://www.apra.gov.au/prudential-standard-cps-230-operational-risk-management
- ISO/IEC 27001:2022 — https://www.iso.org/standard/27001
- French Compliance Society, *From Third Party Assessment to Third Party Risk Management*

**BEC loss-magnitude — §5.6.2 open item 11** (verified 19 Jul 2026; confirm page refs against primary PDFs before client use)
- FBI IC3 *2024 Internet Crime Report* — BEC US$2.77bn / 21,442 complaints — https://www.ic3.gov/AnnualReport/Reports/2024_IC3Report.pdf
- ASD/ACSC *Annual Cyber Threat Report 2024–25* — BEC 15% of attacks; >A$55k avg/incident — https://www.cyber.gov.au/about-us/view-all-content/reports-and-statistics/annual-cyber-threat-report-2024-2025

---

## Part 2 · Legal & standards basis

*Model-level legal basis — the rationale layer behind Deliverable 3. Where Part 3 asks whether we may lawfully **collect** a source, this part asks whether the **score** built on top of it stands up.*

**Supports Deliverable 3** (v1 scoring model — the rationale layer)
**Status:** v0.1 draft · **Verified:** 17 July 2026 · **Author:** *(intern)*

---

### Purpose — and how this differs from Part 3 of this document

Part 3 of this document answers one legal question: **may we lawfully collect this?** It answers it well, per source, and that work is not repeated here.

This document answers the *other* legal question, which is not the same one and is currently unanswered anywhere in the project:

> **Once collected, does the score we build on top of it stand up?**

A source register can be flawless and the model built on it still indefensible. The two questions have different answers, different authorities, and — as the first finding below shows — different consequences for getting them wrong.

**Structure.** Four tiers, in descending order of how much they bind us:

| Tier | What it is | Why it matters | Optional? |
|---|---|---|---|
| **1** | Binding law that constrains the model itself | Non-compliance is unlawful | **No** |
| **2** | Regulatory instruments defining what a score must cover | Determines what the client must be able to evidence | **No** — this is the buyer's demand |
| **3** | Standards supplying defensible structure | Borrowed authority; "we follow X" beats "we decided" | Strongly recommended |
| **4** | AI governance instruments | Engages once AI touches the score | Conditional |

**Caveat, stated once and meant.** I am not a lawyer and this is not legal advice. Everything below is a documented, cited position for review by someone qualified — which is exactly the treatment the brief asks for ("ask before you collect, not after"). Claims verified verbatim against primary sources are marked **[verbatim]**; claims resting on secondary summaries are marked **[secondary — verify]** and should not be relied on until confirmed.

---

### The two findings that reframe the project

Everything else in this document is supporting detail. These two are load-bearing, and neither appears anywhere in the existing docs.

#### Finding A — "Defensible" is a legal standard in Australia, not a client preference

The brief says *"any score you produce, you should be able to justify"* and reads as a quality bar. **It is not. It is a restatement of Australian law**, and there is a decided Full Federal Court authority directly on point.

In **`ABN AMRO Bank NV v Bathurst Regional Council` [2014] FCAFC 65**, Standard & Poor's was held liable for assigning a AAA rating to CPDO notes. The Full Federal Court's reasoning transfers to this project almost without modification:

- Publishing a rating conveys an **implied representation that the rating was formed on reasonable grounds and as the result of an exercise of reasonable care and skill**. Where it was not, the rating is **misleading and deceptive conduct**.
- The rating agency **owed a duty of care to investors** — a class of people it had **no contract with** — because the rating was procured for the purpose of being communicated to an ascertainable class who would rely on it.
- It is the **only common law case in which a ratings agency has been held liable** to compensate for losses on a rated product. It is Australian, it is appellate, and it is directly analogous.

**Why this lands on us specifically.** Wahid AI would publish a vendor risk score to clients who rely on it to make procurement decisions, exactly as investors relied on the AAA rating. Under **ACL s 18**, misleading or deceptive conduct requires **no intent** — *"it is no defence to say that the misleading conduct was an honest mistake."*

**Design consequences — these are requirements, not suggestions:**

1. **Every score must be reconstructible from stored evidence.** Not explainable in principle — reconstructible in fact, later, from what we retained. "Reasonable grounds" is proved with records or not at all.
2. **The evidence store is a legal artefact, not an engineering convenience.** Earlier design notes proposed it as good architecture. It is better than that: it is the discharge of the reasonable-grounds representation. Build it first.
3. **Publish the model's limits alongside the score.** A score presented as more certain than its inputs warrant is the *precise* defect in the AAA rating. This is why "confidence" is not a nice-to-have.
4. **Disclaimers help but do not cure.** S&P had disclaimers. Reasonable grounds is about how the opinion was actually formed.

> **This finding, not the brief, is the strongest argument for the whole methodology-first approach.** It also independently confirms the AFA regulator warning already quoted in Part 3 of this document — a black-box score is not merely unpersuasive, it is a liability.

#### Finding B — Sanctions screening is evidence for a client's statutory defence, not a scoring dimension

Part 3 of this document correctly notes sanctions breaches carry up to 10 years' imprisonment. The more consequential provision is the **defence**.

Under the **Autonomous Sanctions Act 2011 (Cth) s 16**: **[verbatim]**

- *"An offence against subsection (5) or (6) is an offence of strict liability"* — for a body corporate, **no fault element** is required.
- s 16(7): the subsection *"does not apply if the body corporate proves that it took reasonable precautions, and exercised due diligence, to avoid contravening that subsection."*
- *"The body corporate bears a legal burden in relation to the matter in subsection (7): see section 13.4 of the Criminal Code."*

Penalties: up to **$555,000** (individual), or **$2.2 million or 3× the transaction value, whichever is greater** (body corporate), and/or **up to 10 years' imprisonment**. **[secondary — verify quantum]**

**Read those together and the product changes shape.** Liability is strict — the client is guilty on the fact of dealing alone. The only exit is s 16(7), and the client carries a **legal burden** (balance of probabilities, not merely raising a doubt) to prove reasonable precautions and due diligence. **A screening record is what discharges that burden.** The output is not a risk input; it is the evidence in a criminal defence.

**Design consequences:**

1. **Sanctions must never be a weighted contributor.** The category structure already reaches this ("gate") by intuition. The Act supplies the reason: a defence is not partially available. Gate is correct — this is *why*.
2. **False negatives are the catastrophic direction, false positives merely expensive.** A missed hit destroys the defence; a false positive costs an analyst an hour. **Tune recall over precision here and nowhere else in the model.** This inverts the default and must be stated explicitly, since Part 3 of this document's (correct) warning about false-positive accusations pushes the opposite way. Both are right: surface generously, adjudicate manually, never auto-conclude.
3. **Screening records are retention-critical.** A defence needs the evidence as it stood **at the time of dealing**. Retain what was checked, against which list version, on what date, with what result — including clean results. A clean screen with no record is worth nothing in court.
4. **This is the commercial argument for resolving the DFAT open item.** Australian sanctions are the list an Australian client's defence turns on. ITA is a competent substitute for *risk*; it is not a substitute for *the defence*. That reframes DFAT from a coverage gap to a product-viability gap.

---

### Tier 1 — Binding law that constrains the model

#### 1.1 Privacy Act 1988 (Cth) — engaged, and more than expected

**Publicly available does not mean exempt.** In `Commissioner initiated investigation into Clearview AI, Inc.` **[2021] AICmr 54**, the OAIC held that indiscriminately collecting **publicly available** images was still collection of personal information and breached the APPs, expressly rejecting the argument that public availability removes Privacy Act protection. The OAIC's stated global position: *"personal information that is 'publicly available'... on the internet, is subject to data protection and privacy laws. Individuals and companies that scrape such personal information are therefore responsible for ensuring that they comply."* **[verbatim]**

**The entire OSINT premise of this project is that the data is public. That premise does not carry the privacy analysis.**

**Where personal information enters a vendor risk record** — this is not hypothetical:

- Sanctions lists name **individuals**, not only entities. DFAT's list covers *"individuals, entities and vessels"* (per Part 3 of this document).
- Sole traders and partnerships are vendors, and their business details are personal information.
- Adverse media names directors and officers.
- `security.txt` and DPA pages publish named DPO contacts.
- SEC EDGAR filings name officers and beneficial owners.

**APP 10 is the sharp one for a scoring product:** an entity must take reasonable steps to ensure personal information it uses or discloses is *"accurate, up-to-date, complete and relevant"* having regard to the purpose. **A stale or misattributed adverse-media hit against a named director is an APP 10 problem on top of everything else** — and entity resolution, already flagged in Part 3 of this document as the hard problem, is where this bites.

**Small business exemption — still in force, verified directly with OAIC 17 Jul 2026.** The **$3 million** annual turnover threshold has **not** been repealed; widely-reported "removal in 2026" claims are **incorrect as of today** and belong to an unlegislated reform tranche. **Do not design to a repeal that has not happened.**

**But the exemption has exceptions, and one is aimed straight at us.** It does not apply to a business that **trades in personal information**. **[verbatim, OAIC]** A product that collects personal information about vendor personnel and provides it to paying clients requires analysis against that exception — and if it applies, **turnover is irrelevant and the APPs bind in full**. This is a question for counsel before commercialisation, not after.

**Statutory tort of serious invasion of privacy — commenced 10 June 2025.** Introduced by the *Privacy and Other Legislation Amendment Act 2024*. Elements: serious invasion by intrusion upon seclusion **or misuse of information**; reasonable expectation of privacy; **intentional or reckless** conduct; public interest in privacy outweighing countervailing public interest. It is **broader than the Privacy Act — it reaches entities that are not APP entities**, so the small business exemption is no shield against it. Exemptions exist for journalism; **we are not journalists.** The intent/recklessness element is our friend here, and is another reason deliberate scoping and documented restraint have legal value.

**Design consequences:**
1. **Collect information about the vendor as an organisation; avoid personal information unless the signal requires it.** HIBP `/breaches`-not-domain-search (already decided) is exactly this instinct, correctly applied — generalise it into a stated principle.
2. **Named individuals in the record need APP 10 handling:** dated, sourced, adjudicated, and correctable.
3. **A "public data" justification is not available.** Clearview forecloses it.

#### 1.2 Copyright Act 1968 (Cth) — ingesting lists is fine; republishing them is not

Two rules, pulling in opposite directions, and the gap between them is the design.

**No text and data mining exception exists.** The Government **explicitly ruled out** a TDM exception in **October 2025**, stating it has *"no plans to weaken copyright protections when it comes to AI"*, referring the question to the Copyright and AI Reference Group instead. **Australia has no TDM safe harbour and is not getting one.** **[secondary — verify]**

**But facts are not protected.** `IceTV Pty Ltd v Nine Network Australia Pty Ltd` **[2009] HCA 14**: copyright does **not** subsist in the underlying data of a compilation, only in *"the particular form of expression"*. Australia has **no sui generis database right** and rejects "sweat of the brow" — the High Court called the resulting lack of database protection a gap in the law.

**Design consequence — and it is a clean one.** Extracting *facts* from a sanctions list, a KEV feed, or a filing is not an infringement, because the facts are not protected. Reproducing a source's *particular expression* — its prose, its arrangement, verbatim article text — is where infringement lives. **So: store normalised facts and pointers; do not warehouse verbatim third-party text.** This is why GDELT's redistribution licence matters more for adverse media (where we would otherwise hold expressive text) than for KEV (where we hold CVE identifiers, which are facts).

#### 1.3 Defamation — the exposure is inverted from intuition

Under the uniform **Model Defamation Provisions** (2021 amendments, enacted state by state):

- A corporation **has no cause of action unless it is an "excluded corporation"** — broadly, not-for-profit, or employing **fewer than 10 persons**. **Large vendors cannot sue us. Small ones can.** **[secondary — verify against the applicable state Act, s 9; search summaries on this point were internally contradictory and must not be relied on as written]**
- **Serious harm is an element** the plaintiff must prove (s 10A, 2021 reform, shifting the burden from defendant to plaintiff). For an excluded corporation, harm is not serious unless it caused or is likely to cause **serious financial loss**.
- **Individuals — directors, officers named in adverse media — face no such restriction.**

**Design consequences:**
1. **Adverse media risk concentrates on small vendors and named individuals** — precisely the segment where, per Part 3 of this document, *"absence of adverse media is close to meaningless"* and coverage is thinnest. The category with the worst signal quality carries the highest legal exposure. That is an argument for adjudication, not for dropping it.
2. **Media reports allegations, not findings** (already correctly stated). Carrying that distinction into the *output wording* — "reported", "alleged", dated, attributed — is what preserves the defences.
3. **ACL s 18 has no serious-harm threshold and no excluded-corporation limit.** A large vendor who cannot sue in defamation is not without remedy. **Do not treat "they're too big to sue in defamation" as safety.**

#### 1.4 Criminal Code Act 1995 (Cth) Part 10.7

Already correctly analysed in Part 3 of this document §3. Carried forward unchanged: retrieving a page published to the world is authorised by the act of publication. No further work needed.

---

### Tier 2 — Instruments that define what the score must cover

These are not constraints on us. **They are the client's obligations — and therefore the product's demand-side specification.** A dimension that maps to a client's statutory duty sells itself; one that doesn't is a hobby.

#### 2.1 APRA CPS 230 Operational Risk Management — *and it has changed since the PDF in this repo*

**⚠ Any locally-held copy is likely out of date.** The version this analysis was written against is the **July 2025** one. APRA **finalised targeted amendments in April/May 2026**, and the **updated CPS 230 and CPG 230 commence 1 July 2026** — i.e. **already in force as of today (17 July 2026)**. Any paragraph number cited from that version, including the ¶48 reference in Part 3 of this document, must be re-checked against the current instrument before it goes in a client-facing document. **This is open item 1.**

Key structure (subject to that re-check):
- **¶47–48:** the policy must cover how the entity identifies material service providers, manages material risks, **and manages risks from fourth parties that material service providers rely on** to deliver critical operations.
- A material service provider may be a third party, **related party or connected entity**.
- Pre-existing contracts: requirements apply from the earlier of next renewal or **1 July 2026**.

**Why this is the single most commercially valuable mapping in the project.** ¶48 makes **fourth-party risk a regulated obligation** for APRA-regulated entities. Part 3 of this document already identified that public DPAs and subprocessor lists yield fourth-party data for free, and correctly called it *"the one thing questionnaires are worst at surfacing."* **CPS 230 ¶48 converts that observation into a compliance requirement the client must satisfy anyway.** Concentration findings — six vendors, one subprocessor — are not a clever extra. They are the regulated deliverable.

#### 2.2 APRA CPS 234 Information Security

Requires regulated entities to assess third parties' information security capability, evaluate control **design and operating effectiveness**, assess testing frequency, and take reasonable steps regarding **sub-contractor** controls.

**Design consequence — a boundary, honestly drawn.** CPS 234 demands assurance about **control effectiveness**. OSINT cannot see control effectiveness; it sees perimeter artefacts. Part 3 of this document already concedes ~10 of 27 criteria are invisible to any lawful external observer. **CPS 234 is where that concession must be loudest.** The correct claim is that OSINT **evidences a subset and flags contradictions** — never that it discharges CPS 234. Overclaiming here is both a sales lie and, per Finding A, an ACL s 18 exposure.

#### 2.3 SOCI Act 2018 (Cth) + Enhanced CIRMP Rules 2026 — *this closes the FOCI gap argument*

The **Security of Critical Infrastructure (Enhanced Critical Infrastructure Risk Management Program) Rules 2026** were **registered 9 June 2026** under s 61 of the SOCI Act. Applies to critical broadcasting, DNS, electricity, energy market operator, freight infrastructure, freight services, gas, liquid fuel and water assets.

Responsible entities must **map supply chains for major suppliers and critical components**, identify maximum acceptable outages, and assess risks for existing or proposed major suppliers — **and the risks that must be assessed expressly include FOCI-related risks** and risks of access, influence and control exercised by suppliers.

Phase-in: ~mid-2027 for material-risk and patching measures; **~mid-2028 for supply chain and physical/natural hazards**.

**Why this matters to the model.** Part 3 of this document lists **FOCI / Provenance as the "honest gap in v1"** and treats it as a sourcing shortfall to apologise for. Reframe it: **an Australian instrument registered five weeks ago makes FOCI assessment of major suppliers legally mandatory for critical infrastructure operators, with a mid-2028 deadline.** The gap is not an embarrassment — it is the highest-value item on the roadmap, with a regulatory deadline attached and a named buyer. That is a far stronger thing to say at handover than "we couldn't resolve the registry terms."

#### 2.4 Modern Slavery Act 2018 (Cth)

Reporting entities (revenue ≥ AU$100m) must publish annual statements addressing supply-chain risks and remediation. Already correctly identified in Part 3 of this document as mapping onto the *Modern Slavery & Human Rights* criterion, and correctly **held pending a licence answer**.

**Note the asymmetry:** the *Act* creates a public statutory register. The *register's licence* is unstated. Statutory publication compels disclosure; it does not grant reuse rights. The existing hold is the right call.

---

### Tier 3 — Standards supplying defensible structure

The purpose of this tier is **borrowed authority**. "We adopted NIST's model" survives a client challenge; "we thought this was sensible" does not.

| Standard | What to take from it | Status |
|---|---|---|
| **NIST SP 1326** | Five due-diligence categories; **four per-finding variables: age, frequency, severity, mitigations**; ITA CSL recommended by name | **Primary — already in repo** |
| **NIST SP 800-161r1** | C-SCRM depth; supplier criticality tiering | Recommended |
| **NIST CSF 2.0 — GV.SC** | GV.SC-01…10: supplier **prioritisation by criticality**, **due diligence + ongoing monitoring**, relationship conclusion | **Adopt — maps to agentic monitoring** |
| **ISO/IEC 27001:2022 A.5.19–5.23** | Supplier relationship controls | In repo |
| **ISO/IEC 27036** (4 parts; Pt 1 rev. 2021) | Pt 2 = requirements; **Pt 3 = ICT supply chain**; Pt 4 = cloud | Recommended |
| **ISO 31000:2018 / IEC 31010:2019** | Risk process discipline; **31010 Annex = 41 assessment techniques with stated strengths and limitations** | **Adopt for method defence** |
| **Open FAIR (O-RT / O-RA)** | Frequency × magnitude decomposition; *"consistent and defensible risk statements"* | **Cite, don't implement** |

**Three notes that matter more than the table:**

**NIST SP 1326's four variables are the decay model, handed over by a US federal publication.** Part 3 of this document spotted this. It is worth being blunt about the value: the hardest thing to defend in any scoring model is *why a 2013 breach counts less than last month's*. **SP 1326 answers it with borrowed authority.** Age, frequency, severity, mitigations — adopt the four verbatim as the per-finding modifier set, and the decay curve stops being arbitrary.

**CSF 2.0 GV.SC is the authority for the agentic-AI requirement.** The brief asks where the system could act on the user's behalf — *"re-checking a vendor on a schedule."* GV.SC includes **ongoing monitoring** and **planning for supplier relationship conclusions** as governance outcomes. Scheduled re-scoring is therefore not a product flourish; it is a named C-SCRM outcome. **This is how the roadmap's agentic feature gets justified rather than assumed.**

**Open FAIR should be cited and not built.** FAIR quantifies risk in **financial terms** from frequency and magnitude distributions. OSINT gives us neither loss magnitude nor event frequency for a specific vendor. **Attempting FAIR quantification on OSINT inputs would manufacture exactly the false precision Finding A punishes.** Cite FAIR for the *taxonomy* discipline — separating frequency from magnitude, keeping them from collapsing into one number — and state plainly that v1 does not have the inputs to quantify. **Declining to use FAIR, with a reason, is a stronger methodological statement than using it badly.**

---

### Tier 4 — AI governance (engages the moment AI touches the score)

Part 3 of this document designates two AI moments: adverse-media summarisation and trust-page classification. Both are inside the scoring path, so this tier engages.

**EU AI Act — high-risk classification almost certainly does not bite, and the reason is worth knowing.** Annex III(5)(b) makes creditworthiness evaluation and credit scoring **of natural persons** high-risk. **Vendor risk scoring assesses legal entities, which falls outside that provision.** However: the **Art 6(3) exception never applies where the system performs profiling of natural persons**. **Design consequence — a bright line:** the moment the model scores a **sole trader** or attaches risk to a **named individual**, the analysis changes. **Keep the model scoring entities, not people.** That is the same line APP 10 and the privacy tort draw, arrived at independently — three separate instruments converging on one design rule is a rule worth taking seriously.

**Australia — Voluntary AI Safety Standard (10 guardrails).** Voluntary. Mandatory guardrails for high-risk settings were **accepted in principle but paused**; the Department published **Guidance for AI Adoption (6 essential practices) on 21 October 2025**, evolving VAISS. An **Australian AI Safety Institute** was slated to be operational in early 2026. **[secondary — verify current status; this area moves fast and the file's verification date will go stale first here]**

**ISO/IEC 42001:2023** (AI management system, certifiable, Stage 1/2 audit, 3-year cycle) and **ISO/IEC 23894:2023** (AI risk management, extends ISO 31000 to AI). **Roadmap, not v1** — 42001 certification runs ~$20–60k and 4–9 months. Worth naming in the roadmap because **Wahid AI is an AI platform**, and a third-party module that already documents its AI risk position is a cheaper input to a future 42001 scope than one that doesn't.

**The AI-specific exposure, stated plainly.** Under Finding A, the reasonable-grounds representation attaches to the **published score**. If an LLM summarises adverse media and that summary moves the score, **"the model said so" is not reasonable grounds.** Design consequence: **AI output must be evidence-linked and human-adjudicable, and must not silently move a score.** This is the same architecture the evidence store already requires — which is convenient, and not a coincidence.

---

### Tier 5 — Roadmap / non-binding today

**EU DORA** — applies since **17 January 2025**; ICT third-party risk management, mandatory **Register of Information** (2026 cycle, reference date 31 Dec 2025), oversight of designated **Critical ICT Third-Party Providers** (ESAs published the list **18 Nov 2025**). Art 28 governs third-party ICT arrangements.

**Why it earns a mention despite being EU law:** in the ESAs' 2024 dry run, **only 6.5% of ~1,000 firms passed all 116 data-quality checks**, with the most common failures being **incomplete contract data and missing subcontractor information**. That is a documented, quantified market failure in **exactly the fourth-party data this project extracts for free from public DPAs.** DORA is not our regulator, but it is evidence that the fourth-party angle has a buyer well beyond one Australian client. **Roadmap material, with a number attached.**

---

### Design consequences — consolidated

The point of the document. Each rule below is traceable to an instrument, which is what makes the model defensible rather than opinionated.

| # | Rule in the model | Authority |
|---|---|---|
| 1 | Every score reconstructible from stored evidence; evidence store built first | ABN AMRO v Bathurst; ACL s 18 |
| 2 | Confidence published alongside every score; never presented as more certain than inputs allow | ABN AMRO v Bathurst |
| 3 | Sanctions = gate, never a weighted term | Autonomous Sanctions Act s 16(7) |
| 4 | Sanctions tuned for **recall**; surface generously, adjudicate manually, never auto-conclude | s 16(7) legal burden |
| 5 | Screening records retained with list version + date + result, **including clean results** | s 16(7) evidentiary need |
| 6 | Missing data reduces **confidence**, never **risk** | Already in Part 3 of this document; reinforced by APP 10 "complete" |
| 7 | Per-finding modifiers = **age, frequency, severity, mitigations** | NIST SP 1326 |
| 8 | Score **entities, not natural persons**; sole traders are a bright line | APP 10 + privacy tort + EU AI Act Art 6(3) |
| 9 | Store normalised **facts**, not verbatim third-party expression | IceTV; no TDM exception |
| 10 | Adverse media output worded as **reported/alleged**, dated, attributed | Defamation (small vendors + individuals) |
| 11 | AI output evidence-linked, human-adjudicable, never silently score-moving | ABN AMRO + reasonable grounds |
| 12 | Fourth-party / subprocessor concentration = **headline feature**, not extra | CPS 230 ¶48; DORA Art 28 |
| 13 | Scheduled re-scoring justified as a C-SCRM outcome | NIST CSF 2.0 GV.SC |
| 14 | FOCI positioned as **roadmap item with a 2028 regulatory deadline**, not as an apology | SOCI Enhanced CIRMP Rules 2026 |
| 15 | Never claim OSINT discharges CPS 234; claim subset + contradiction-flagging | CPS 234; ACL s 18 |
| 16 | FAIR cited for taxonomy discipline; quantification explicitly declined with reason | Open FAIR O-RT/O-RA |

---

### What not to rely on

Recording these matters as much as the inclusions — an unexamined authority is worse than none.

- **The early brainstorm source table.** Already contradicted twice by Part 3 of this document (VirusTotal, SSL Labs). It is a useful brainstorm and **not** an authority. Nothing in it should reach a client document unverified.
- **"It's publicly available."** Foreclosed by Clearview for anything touching personal information.
- **"Australian Government material is usually CC BY 4.0."** Part 3 of this document already refuses this inference for DFAT. Correct. Do not let it back in elsewhere.
- **The repo's CPS 230 PDF.** Superseded — see §2.1.
- **Claims that the Privacy Act small business exemption has been removed.** Widely repeated in secondary commentary; **false as of 17 Jul 2026** per OAIC direct.
- **Commercial vendors' methodologies** (SecurityScorecard, Bitsight, Black Kite). Useful for dimension design. **Not authority** — and the AFA is on record warning against exactly these. Cite the regulator, study the vendors.

---

### Open items

| # | Item | Blocks | Priority |
|---|---|---|---|
| 1 | **Re-obtain current CPS 230 + CPG 230** (in force 1 Jul 2026); re-check ¶47–48 numbering | Every CPS 230 citation, incl. Part 3 of this document | **High** |
| 2 | **Counsel review of the "trades in personal information" exception** against the product model | Commercialisation | **High** |
| 3 | Verify **defamation excluded-corporation test** against applicable state Act s 9 | Adverse media wording | Medium |
| 4 | Confirm **Autonomous Sanctions Act penalty quantum** from primary source (austlii returned 403) | Methodology accuracy | Medium |
| 5 | Read **SP 1326 §Pre-Checks** and the four variables **in the repo PDF** — decay model depends on the exact wording | Scoring model | **High** |
| 6 | Confirm **VAISS / mandatory guardrail** status closer to handover | AI section currency | Low |
| 7 | Obtain **ISO/IEC 27036-2 and -3** (paywalled — note as future option per brief) | Tier 3 depth | Low |

**Carried from Part 3 of this document and now re-prioritised by this analysis:** the **DFAT** query (open item 1 there) is upgraded from a coverage gap to a **product-viability question** — see Finding B.4.

---

### Verification log

| Claim | Method | Result | Date |
|---|---|---|---|
| Privacy Act small business exemption | **direct fetch, oaic.gov.au** | **$3m threshold in force**; exceptions incl. trades-in-personal-information | 17 Jul 2026 |
| Autonomous Sanctions Act s 16(7)/(8) | search → austlii text | Strict liability + due diligence defence, legal burden | 17 Jul 2026 |
| Autonomous Sanctions Act s 16 (primary) | **direct fetch → 403 / wrong Act returned** | **Unverified — open item 4** | 17 Jul 2026 |
| ABN AMRO v Bathurst [2014] FCAFC 65 | search, multiple firm notes concurring | Reasonable grounds + duty without contract confirmed | 17 Jul 2026 |
| Clearview AI [2021] AICmr 54 | search, OAIC statements | Public availability ≠ exempt | 17 Jul 2026 |
| Privacy tort commencement | search | **10 June 2025**; broader than APP entities | 17 Jul 2026 |
| CPS 230 amendments | search, APRA + firm notes | **Updated CPS 230/CPG 230 in force 1 Jul 2026** | 17 Jul 2026 |
| SOCI Enhanced CIRMP Rules 2026 | search, Federal Register listing | **Registered 9 Jun 2026**; FOCI mandatory for major suppliers | 17 Jul 2026 |
| TDM exception ruled out | search, multiple firm notes | Oct 2025, no TDM exception | 17 Jul 2026 |
| IceTV | search | Facts unprotected; no database right | 17 Jul 2026 |
| Defamation excluded corporation | search | **Summaries self-contradictory — open item 3** | 17 Jul 2026 |
| EU AI Act Annex III(5)(b) | search | Natural persons only; Art 6(3) profiling carve-out | 17 Jul 2026 |
| DORA dry-run 6.5% pass rate | search | Confirmed; 116 checks, ~1,000 firms | 17 Jul 2026 |

**Method note.** Only the OAIC small business position was confirmed by direct fetch of a primary source. Everything else rests on search results and law-firm commentary, which is adequate for a v0.1 position paper and **not** adequate for a client-facing document. Items 1, 4 and 5 close that gap.

---

### References

**Legislation & instruments**
- *Autonomous Sanctions Act 2011* (Cth) s 16 — http://www.austlii.edu.au/au/legis/cth/consol_act/asa2011270/s16.html
- *Autonomous Sanctions Regulations 2011* (Cth) reg 14–15
- *Privacy Act 1988* (Cth); *Privacy and Other Legislation Amendment Act 2024* (Cth)
- *Copyright Act 1968* (Cth)
- *Criminal Code Act 1995* (Cth) Part 10.7
- *Modern Slavery Act 2018* (Cth)
- *Security of Critical Infrastructure Act 2018* (Cth); Enhanced CIRMP Rules 2026 — https://www.legislation.gov.au/F2026L00701/asmade
- *Competition and Consumer Act 2010* (Cth) Sch 2 (ACL) s 18, s 236
- Model Defamation Provisions (2021), ss 9, 10A — as enacted per state

**Cases**
- *ABN AMRO Bank NV v Bathurst Regional Council* [2014] FCAFC 65
- *Commissioner initiated investigation into Clearview AI, Inc.* [2021] AICmr 54 — https://www.oaic.gov.au/__data/assets/pdf_file/0016/11284/Commissioner-initiated-investigation-into-Clearview-AI,-Inc.-Privacy-2021-AICmr-54-14-October-2021.pdf
- *IceTV Pty Ltd v Nine Network Australia Pty Ltd* [2009] HCA 14

**Regulatory**
- APRA CPS 230 — https://www.apra.gov.au/standards/cps-230 · CPG 230 — https://www.apra.gov.au/practice-guides/cpg-230
- APRA final targeted amendments to CPS 230 — https://www.apra.gov.au/final-targeted-amendments-to-cps-230-operational-risk-management
- APRA CPS 234 — https://www.apra.gov.au/standards/cps-234
- OAIC APP Guidelines ch 10 (APP 10) — https://www.oaic.gov.au/privacy/australian-privacy-principles/australian-privacy-principles-guidelines/chapter-10-app-10-quality-of-personal-information
- OAIC small business — https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/organisations/small-business
- OAIC statutory tort — https://www.oaic.gov.au/privacy/your-privacy-rights/more-privacy-rights/statutory-tort-for-serious-invasions-of-privacy
- EU DORA (EIOPA) — https://www.eiopa.europa.eu/digital-operational-resilience-act-dora_en
- EU AI Act Annex III — https://artificialintelligenceact.eu/annex/3/ · Art 6 — https://artificialintelligenceact.eu/article/6/
- DISR Voluntary AI Safety Standard — https://www.industry.gov.au/publications/voluntary-ai-safety-standard/10-guardrails

**Standards**
- NIST SP 1326 — https://csrc.nist.gov/pubs/sp/1326/ipd
- NIST CSF 2.0 — https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf · GV.SC — https://csf.tools/reference/nist-cybersecurity-framework/v2-0/gv/gv-sc/
- NIST SP 800-161r1 — C-SCRM Practices for Systems and Organizations
- ISO/IEC 27001:2022 — https://www.iso.org/standard/27001
- ISO/IEC 27036-1:2021 — https://www.iso.org/standard/82905.html
- ISO 31000:2018 — https://www.iso.org/standard/65694.html · IEC 31010:2019 — https://www.iso.org/standard/72140.html
- Open FAIR (O-RT, O-RA) — https://www.opengroup.org/open-fair
- ISO/IEC 42001:2023 — https://www.iso.org/standard/42001 · ISO/IEC 23894:2023

**Internal**
- Part 3 of this document — source-level legality (the other legal question)
- Part 1 of this document — the model's derivation and category structure
ISO/IEC 42001

EU AI Act

O NIST AI RMF

G DTA Policy v2.0

Al Ethics Principles

4ts APRA CPS 230

APRA CPS 234

& Privacy Act 1988

To design a third-party risk scoring model that will stand up to a grilling by a client’s Chief Risk Officer (CRO) or General Counsel, we have to ground our methodology in established industry frameworks and clear legal safe harbors.

If a client asks, *"Why are you measuring this, and are you sure this data was collected legally?"* we should point directly to these exact standards.

---

### 1. The Regulatory & Security Frameworks (Why We Measure)

Our scoring model shouldn’t invent risk categories. Instead, it should map its dimensions directly to globally recognized standards. This ensures that any "Perimeter Defense" or "Reputational Risk" score we produce aligns with what risk teams are already auditing.

| Framework / Law | Specific Sections to Rely Upon | How It Directs Our Scoring Model |
| --- | --- | --- |
| **NIST SP 800-161 Rev. 1** <br>

<br>*(Cybersecurity Supply Chain Risk Management)* | **Control RA-3** (Risk Assessment) & **PM-31** (Continuous Monitoring) | Mandates that organizations continuously monitor the security posture of their supply chain. This justifies our automated, real-time "Pulse" scanning instead of static annual questionnaires. |
| **EU DORA** <br>

<br>*(Digital Operational Resilience Act)* | **Articles 28–30** (ICT Third-Party Risk Management) | Requires financial entities to conduct proactive, proportionate due diligence *prior* to contracting. Article 28(5) specifically demands assessing the vendor's information security standards, justifying our **Perimeter Defense** dimension. |
| **ISO/IEC 27001:2022** <br>

<br>*(Information Security Management)* | **Annex A.5.19** (Supplier Relationships) & **A.5.22** (Monitoring Supplier Services) | Establishes the requirement to regularly monitor, review, and audit third-party compliance and technical posture. |
| **US Banking Guidance** <br>

<br>*(OCC / FRB / FDIC Interagency Guidance)* | **Section on Due Diligence & Ongoing Monitoring** (June 2023) | Stresses that a bank's use of third parties does not diminish its responsibility. It explicitly outlines that due diligence must review the vendor’s technological and operational resilience. |

---

### 2. The Legal & Collection Safe Harbors (How We Collect Safely)

Our data collection must be entirely "passive"—we must never actively scan or probe a vendor’s network (which can look like a cyberattack). We also need to defend our use of automated public data collection.

#### A. The "Gates Up" Doctrine (U.S. CFAA)

To defend our right to pull public infrastructure data (like SSL/TLS status and DNS records), we rely on:

* **The Computer Fraud and Abuse Act (CFAA) - 18 U.S.C. § 1030**
* **hiQ Labs v. LinkedIn (9th Cir. 2022)**
* **Van Buren v. United States (U.S. Supreme Court, 2021)**

> **The Defensible Position:** Under the Supreme Court's "gates-up-or-down" inquiry, if a website or service is publicly accessible without a password or login barrier, accessing or indexing it via automated means is not a violation of the CFAA. Because our OSINT PoC only queries public DNS, certificate transparency logs (`crt.sh`), and public Shodan indexes, we remain firmly "gates-up". We do not bypass any technical access controls.

#### B. GDPR Legitimate Interest (European Privacy)

To justify collecting and scoring threat intelligence data that might occasionally touch personal data (like public emails associated with a breached domain), we rely on:

* **GDPR Article 6(1)(f) (Legitimate Interest)**
* **GDPR Recital 49**

> **The Defensible Position:** Recital 49 explicitly states that processing personal data to the extent *strictly necessary and proportionate* for the purpose of ensuring network and information security constitutes a "legitimate interest." Aggregating threat data (like AlienVault OTX alerts) to score a vendor's cybersecurity risk falls squarely under this protection.

#### C. Fair Use & Generative AI Summarization (Adverse Media)

When using an LLM to read, categorize, and summarize adverse media (news of breaches, lawsuits, or regulatory fines), we must protect against copyright claims:

* **U.S. Copyright Act - 17 U.S.C. § 107 (Fair Use)**

> **The Defensible Position:** Our PoC uses LLMs to perform **transformative summarization**. We are not redistributing full articles or creative prose; we are programmatically extracting and indexing raw, factual risk points (e.g., "Company X fined $2M for GDPR breach on [Date]"). Factual information itself is not copyrightable, and utilizing snippets for analysis is protected under the Fair Use doctrine.

---

### 3. How This Shapes Our Scoring Rules

To turn these laws and frameworks into our product's scoring engine, we will establish three rule-based guidelines:

1. **Rule of Passive-Only Sourcing:** Our engine is restricted to third-party databases (like Shodan or crt.sh) or standardized protocol queries (like DNS lookups). We never execute active pinging, port scanning, or web scraping of the target's direct servers.
2. **Rule of Strict Fact Attribution:** Every deduction in our scoring model must link to an authenticated public record (e.g., "`-10 points`: Expired TLS Certificate detected via Certificate Serial # [XYZ] on crt.sh"). This satisfies DORA’s requirement for auditability.
3. **Rule of the "Confidence Score" Offset:** In compliance with NIST SP 800-161's focus on data integrity, if a source is stale (e.g., an adverse media article from five years ago) or if data is missing, we must degrade the **Confidence Score** of the assessment rather than artificially lowering the vendor’s **Risk Score**.

---

## Part 3 · Source assessment

*The per-source register: what each source signals, how reliable it is, what it does not tell us, and its legal / terms-of-service position.*

**Deliverable 1 of 5** (research methodology document — source register)
**Status:** v0.1 draft · **Terms verified:** 17 July 2026 (register); GLEIF, Cert Spotter, FTC RSS added & verified 20 July 2026 · **Author:** *(intern)*

---

### Purpose and method

The brief sets two non-negotiables above coverage: *legality first*, and *free or trial data only*. This document records, per source, what it signals, how it is collected, how reliable it is, what it does **not** tell us, and its legal / terms-of-service position.

**Selection principle — prefer sources published in order to be read.**
Certificate Transparency logs, sanctions lists and statutory registers exist specifically so outsiders can audit them. Their legal position is not a risk to be managed; it is absent by design. Sources requiring scraping, or whose terms say "non-commercial", cost a paragraph of justification each and can collapse later. Because this work is a candidate for a commercial platform (Wahid AI third-party module), **any source restricted to non-commercial use is excluded now, not at handover.**

**Every position below was verified by reading the live terms on 17 July 2026**, not from memory or secondary summaries. Quotes are verbatim. Where a source states no licence, that is recorded as an open question rather than assumed to be permission.

**Scoring direction convention (used throughout):** `0 = lowest risk, 100 = highest risk`. Stated once here and never inverted.

---

### Summary register

| # | Source | Signals | Position | Verdict |
|---|--------|---------|----------|---------|
| 1 | Certificate Transparency (crt.sh + certspotter fallback) | Subdomains, cert history, expiry | Public by RFC 6962; crt.sh no ToS, certspotter ToS bars no commercial/automated use | **Use** (see caveat) |
| 2 | DNS (direct query) | SPF, DKIM, DMARC, MX, NS | Protocol operating as designed | **Use** |
| 3 | Self-run TLS + HTTP headers | TLS version, cipher, HSTS, CSP | Own client; one GET of a public page | **Use** |
| 4 | Have I Been Pwned `/breaches` | Confirmed breaches, dates, data classes | CC BY 4.0 — commercial OK w/ attribution | **Use** |
| 5 | ITA Consolidated Screening List | US sanctions / export exclusions | US Gov, free API, no restriction stated | **Use** (gate) |
| 6 | DFAT Consolidated List | Australian sanctions | **No licence stated — query required** | **Ask first** |
| 7 | **GLEIF (LEI register)** | Entity standing, registration currency, jurisdiction | **CC0 / public domain; commercial OK, no auth** | **Use** (replaces EDGAR) |
| 7b | **Wikidata (structured data)** | Entity existence / dissolution — *domain-verified* corroboration of GLEIF | **CC0 / public domain; commercial + automated OK; only a contact-bearing UA required** | **Use** (2nd register) |
| 8 | NVD API | CVEs against vendor products | Commercial OK; attribution notice required | **Use** (scoped) |
| 9 | CISA KEV | Known *exploited* vulnerabilities | US Gov work; no licence field in feed | **Use** (scoped) |
| 10 | **Regulator RSS (FTC + cleared feeds)** | Named enforcement actions / investigations | Gov open data / statutory publications | **Use** (adverse media) |
| 11 | GDELT | Adverse-media *candidates* (ai_adjudicated) | "unlimited and unrestricted... commercial" | **Use** (held, Phase 5) |
| 12 | Vendor trust pages / security.txt / DPAs | Certifications, fourth parties | Vendor's own publication; robots.txt applies | **Use** |
| 13 | AU Modern Slavery Register | Statutory statements | **No licence stated — query required** | **Ask first** |
| 14 | **ABN Lookup (AU)** | AU entity status (Active / Cancelled), entity type, trading names | Web Services Agreement permits third-party extracts, **no commercial bar, no bulk-harvest bar**; free registration GUID; must not imply Commonwealth endorsement | **Use** (built; `empty` without a GUID) |
| 15 | **Wikidata firmographics (P452/P1128/P2139/P414/P17/P571/P749)** | Industry, employees, revenue, listing, country, inception, corporate parent — **profile context only, emits no findings** | **CC0 / public domain**; contact-bearing UA required | **Use** (never scored) |
| 18 | **SEC EDGAR (US)** | 8-K Item 1.03 (bankruptcy), 10-K `goingConcern` | US public only. Free, no key | **Use** (built, narrow scope) |
| — | VirusTotal | Reputation | *"must not be used in commercial products"* | **EXCLUDED** |
| — | Qualys SSL Labs | TLS grade | Commercial + permission + publication bars | **EXCLUDED** |
| — | **Google Safe Browsing API** | Domain/URL reputation — malware & phishing flags | **Commercial use prohibited**; revenue-generating use is directed to the paid Web Risk API (verified 24 Jul 2026) | **EXCLUDED** — the VirusTotal pattern |
| — | Shadowserver Foundation | Exposure reports | Reports are issued to **the network owner / national CERT**, not to third parties assessing them | **Not applicable** |
| — | Shodan / Censys | Exposed services | Free tier too thin; paid = out of scope | **Roadmap** |
| — | Companies House | UK registry — entity status | OGL, commercial OK, free key, 600/5min | **Cleared (roadmap)** |
| 16 | **AlienVault OTX (passive DNS)** | Subdomain enumeration — **CT redundancy** for Digital Footprint | Free API key; cleared as CT redundancy | **Use** (built; `empty` without a key) |
| 17 | **Companies House (UK)** | UK entity status (active / dissolved / liquidation) | **OGL, commercial-OK, free key, 600/5min** | **Use** (built; `empty` without a key) |
| — | ~~ABN Lookup (AU)~~ | *promoted to #14 — BUILT* | — | **Built** |
| — | ~~Companies House~~ | *promoted to #17 — BUILT* | — | **Built** |
| — | ABN Lookup — **ANZSIC industry code** | Industry classification per ABN | **Non-public ABR data: released to eligible government agencies only** — absent from the public JSON services (verified 24 Jul 2026) | **Unavailable to us** — sector falls back to Wikidata |
| — | Google News (scraped) | Adverse media | Against ToS; no free API | **EXCLUDED** — use GDELT |
| 19 | **The Gazette (UK)** | Winding-up petitions, liquidator/administrator appointments | Free, Crown copyright/OGL, no ToS trap | **Use** (built) |
| 20 | **CourtListener (RECAP)** | US federal bankruptcy case dockets | Free, documented API | **Use** (built, narrow scope) |
| — | **OpenCorporates** | Dissolution/liquidation status codes across jurisdictions | Free tier; bulk data is paid | **Held pending ToS** |
| — | **Financial Modeling Prep**| Delisting notices, sustained price decline | Free tier usable; terms need confirmation | **Held pending ToS** |

---

### Proposed-source review — v3.4 (2026-07-21)

A batch of candidate sources was proposed to harden the weak categories. Each was vetted against
the same bar the rest of the register uses: **free, commercial + automated use permitted, no ToS
trap, and reachable/parseable**. Verdicts below; the two cleared ones are IMPLEMENTED and live-verified.

#### ✅ Implemented (cleared + verified live)

| Source | Category | What it adds | Licence | Verified |
|---|---|---|---|---|
| **FIRST EPSS** | Breach & Compromise | Exploitation *probability* per CVE — enriches NVD; a CVE ≥ 0.5 becomes `probable_exploit`, scored between theoretical CVSS and confirmed KEV | **CC0 / open, no auth** | 200 JSON; Snowflake 25/25 CVEs enriched; Atlassian's known criticals score EPSS 0.95–1.00 |
| **Regulator feeds — global** | Adverse Media | FTC + **SEC + DOJ** (US), **CMA + ICO** via gov.uk Atom (UK, incl. the data-protection regulator), **CNIL** (EU/GDPR). Added to the existing regulator collector, polled in parallel | US public domain / UK OGL / FR Licence Ouverte | All six 200 with items; reached live on the 5-vendor run |
| **RDAP** (domain registration) | Business Stability | The **universal** business-standing signal. RFC 9082/9083, the IETF successor to WHOIS, served by the registries themselves — free, **no auth**, answers for essentially ANY registered domain worldwide. Reads domain STANDING (registry hold / imminent expiry / age), NOT financials (entity-level, §4.2). Feeds the new `domain_standing` subcategory (30% of Business Stability); this is what pulls Business Stability out of The Ghost for the many private/global vendors GLEIF and Wikidata don't cover | **Public registry data, no auth** | Live-verified across 20 vendors in 17 countries (.com via Verisign RDAP, plus .co.jp/.de/.nz/.br/… authoritative servers via the rdap.org bootstrap) — every registered domain returned a standing record |

#### ⏳ Cleared but needs a free key (ready-to-wire; can't self-provision the key here)

| Source | Category | Why held | Path |
|---|---|---|---|
| **AlienVault OTX** passive DNS | Digital Footprint | Second subdomain source (CT redundancy — the real single-point-of-failure). Free API **key required**; endpoint also timed out on probe | Add `TPRM_OTX_API_KEY` collector (roadmap) |
| **CourtListener** (RECAP) | Business Stability | US federal litigation. Free key; but name-matching dockets is noisy → review-candidate only | Optional-key collector (roadmap) |
| **Companies House / ABN / SEDAR+ / NZ** | Business Stability | Authoritative registries, but each needs a registered key/GUID. Would corroborate GLEIF+Wikidata for UK/AU/CA/NZ | Roadmap (keyed) |

#### ⛔ Rejected — ToS / auth / anti-bot / no clean feed

| Source | Reason |
|---|---|
| **OpenCorporates API** | Free tier is **non-commercial**; commercial API is paid. Fails the free-commercial bar (same trap as the excluded feeds). Bulk data is ODbL but not the live API. |
| **Shodan / Censys free** | Free tiers are **non-commercial** — excluded for a commercial PoC (already on the register). |
| **GreyNoise / URLScan** | Community/free tiers are non-commercial or commercial-murky; needs a key. Held pending explicit ToS clearance. |
| **RapidDNS / BufferOver** | RapidDNS is a scrape target (anti-bot, unclear ToS); BufferOver is now key/Cloudflare-gated. |
| **CSA STAR / IAF CertSearch / UKAS / JAS-ANZ / ANAB / BSI / DNV** | Cert-verification directories with **no clean public API** — web search + anti-bot; scraping is fragile and ToS-uncertain. Real value, but not a lawful *free-API* path today. |
| **GDELT — scored (event-code filtered)** | Deliberately **kept held/ai-adjudicated (Phase 5)**. It reports allegations (defamation exposure, §5.4.1) and its free API 429s hard; it was just removed from the on-demand path for that reason. Event-code filtering doesn't change the licence/defamation posture. |
| **Mozilla Observatory / internet.nl** | Observatory's public API endpoints 404/502'd (service migrated); internet.nl needs a granted account. Both only *corroborate* our own scanner anyway (lower marginal value). |
| **GitHub Security Advisories / CISA Vulnrichment** | Work no-auth but largely **overlap NVD**; deferred as lower-value once EPSS is in. |
| **HHS OCR / FCC / ACCC / ASIC / OAIC / EDPB** | No reachable/stable public RSS found (403 or 404 on probe, 2026-07-21). AU regulators specifically publish no clean feed — an honest coverage gap, not silently dropped. |

---

### Cleared sources

#### 1. Certificate Transparency — crt.sh (primary) + Cert Spotter (fallback)

- **Signals:** subdomain estate, certificate issuance history, expiry, weak/deprecated issuance, infrastructure sprawl (forgotten dev/staging hosts).
- **Collection:** HTTPS query to `crt.sh`; on failure, fall back to **SSLMate's Cert Spotter API** (`api.certspotter.com/v1/issuances`). Both index the same public CT logs (RFC 6962).
- **Reliability:** **High.** Every publicly trusted certificate is logged by design (RFC 6962). Not self-reported; cryptographically anchored.
- **Limits:** Shows certificates *issued*, not hosts *live*. A logged subdomain may be dead. Wildcard certs hide subdomain detail. Says nothing about whether the host is well configured — only that a cert exists.
- **Legal / ToS position:** Verified 17 Jul 2026 — **crt.sh publishes no terms of service, acceptable use policy, or stated rate limit**; operated by Sectigo Limited. **Cert Spotter added 20 Jul 2026** because crt.sh is operationally flaky (verified live: multi-minute `ReadTimeout` outages that zeroed Digital Footprint for all five vendors). SSLMate's ToS (`sslmate.com/policies/tos`, fetched live) **bars no commercial use, automated access, scraping, or redistribution** — only "illegal or unauthorized purpose." The free no-key tier is documented "for personal or evaluation purposes" (our PoC = evaluation); a free SSLMate account (Small plan) is the production path.
- **Caveat — honest reading:** absence of stated terms (crt.sh) is *not* an explicit grant, and Cert Spotter's free tier is **CLEAR-CONDITIONAL** — evaluation-cleared for the PoC, production needs a (free) SSLMate account per their tiering (**open item**). The underlying CT data is public by design either way; both are convenience indexes we could replace with direct CT-log queries. **Mitigation:** rate-limit both, identify our agent honestly, prefer crt.sh, fall back only on failure. Residual (low) risk logged, not a claimed clean grant.

#### 2. DNS records

- **Signals:** SPF, DKIM, **DMARC policy**, MX, NS, CAA.
- **Collection:** standard DNS resolution.
- **Reliability:** **High**, authoritative, real-time.
- **Limits:** email-security posture only. A vendor with `p=reject` can still be catastrophically insecure elsewhere. No inference beyond the mail path.
- **Legal / ToS position:** **Clean.** A DNS query is the protocol performing its designed function against records published for public resolution. No scraping, no ToS, no access control circumvented.
- **Why it earns its place:** DMARC is the sharpest cheap signal available and is *gradeable on a real scale* — absent → `p=none` (monitoring only, no enforcement) → `p=quarantine` → `p=reject`. It ties directly to business email compromise, a risk clients understand immediately.

#### 3. Self-run TLS handshake + HTTP security headers

- **Signals:** TLS protocol versions, cipher suites, certificate expiry/chain, HSTS, CSP, X-Frame-Options, `security.txt` (RFC 9116) presence.
- **Collection:** our own TLS client (`sslyze` / `testssl.sh`) plus **one HTTP GET** of the vendor's public homepage.
- **Reliability:** **High** — direct observation, no intermediary.
- **Limits:** Perimeter only. Says nothing about encryption at rest, internal segmentation, or key management. A perfect header score is compatible with a terrible internal posture.
- **Legal / ToS position:** **Clean, and deliberately so.** This is a single request identical to what any browser issues when a member of the public visits the site — no authentication bypassed, no rate abuse, no non-public endpoint touched. Under the Criminal Code Act 1995 (Cth) Part 10.7, unauthorised *access* turns on access being unauthorised; retrieving a page the vendor publishes to the world for the purpose of being read is authorised by the act of publication.
- **Design note — this replaces SSL Labs deliberately.** Same signal, no ToS to breach (see exclusions). Running our own client is the *cheaper* legal position, not just the cheaper commercial one.

#### 4. Have I Been Pwned — `/breaches` endpoint only

- **Signals:** confirmed breach events, breach date, records affected, data classes exposed (`Passwords`, `Credit cards`, …), verified/unverified flag.
- **Collection:** `GET /api/v3/breaches` — **no API key, no authentication.**
- **Reliability:** **High** for what it asserts; breaches are curated and flagged verified/unverified.
- **Limits:** **Significant, and must be stated on the scorecard.** Absence of a breach record is *not* evidence of security — it is evidence of *no publicly known breach*. Undisclosed and undetected breaches are invisible. Coverage skews to consumer-facing services; a B2B vendor may be breached without ever appearing.
- **Legal / ToS position:** **Verified clean, and better than expected.** Licensed **Creative Commons Attribution 4.0 International** — commercial use is expressly permitted with attribution to Have I Been Pwned and a link to `haveibeenpwned.com` displayed where the data appears. AUP prohibits querying to harm breach victims, DoS, misidentifying user agents, and misrepresenting the data source — none of which we do.
- **Scope decision — one endpoint, not the other.** The **domain search** endpoint requires (1) adding the domain to a dashboard, (2) **verifying control of it via DNS or email**, (3) an API key, and (4) a Pro subscription. We will never control a vendor's domain, and the subscription is a paid feed. **Domain search is therefore excluded on both legality and the free-data rule.** We learn *that a company was breached* — never *which of its users were*. This distinction is deliberate and worth defending: it is also the privacy-respecting choice.

#### 5. ITA Consolidated Screening List (US)

- **Signals:** US export restrictions, denied/debarred parties, entity exclusions across Commerce, State and Treasury lists.
- **Collection:** free API at `developer.trade.gov`; CSV / TSV / JSON downloads.
- **Reliability:** **High** — official US Government publication.
- **Limits:** US-scope only. Name matching is the hard part, not retrieval (see *Entity resolution* below).
- **Legal / ToS position:** **Clean.** US Government work; page states the tools "may be used as an aid to industry in conducting electronic screens of potential parties to regulated transactions," with no stated licence restriction. ITA notes "additional due diligence should be conducted before proceeding" and that the Federal Register is the official publication — which we mirror as a confidence caveat rather than treating a hit as dispositive.
- **Standing:** **Recommended by name in NIST SP 1326** (Pre-Checks, p.5). Citing NIST's recommendation is itself part of the defence.

#### 7. GLEIF — the Global LEI register (replaces SEC EDGAR)

- **Signals:** legal-entity standing (ACTIVE / INACTIVE), LEI registration currency (ISSUED / LAPSED / RETIRED / ANNULLED), legal jurisdiction, entity legal name, parent/child structure (Level 2, entity-level only).
- **Collection:** `api.gleif.org/api/v1/lei-records` filtered by legal name. Free, **no auth**. Entity resolution is name-based (no domain index) and therefore coarse — the collector ranks candidates and records the count so an ambiguous pick is visible, never silent.
- **Reliability:** **High** — the LEI register is authoritative; issuance is regulated and periodically revalidated. Because it is *exhaustive* for the fact it asserts (an entity either is or isn't on the register in a given state), a clean "active / good standing" is a **full-reliability positive observation**, not a discounted clean receipt (methodology §5.4.2).
- **Limits:** entity STANDING, not financials. It does **not** carry going-concern, bankruptcy, litigation, or ownership-*change* data — those subcategories stay `held` (no free authoritative source; change-detection needs history a snapshot can't give). A `LAPSED` LEI is a mild governance signal (the entity stopped renewing), not proof of distress. Some small vendors have no LEI at all → genuine per-vendor `empty` (lowers confidence, not risk — the MYOB principle).
- **Legal / ToS position:** **Verified clean 20 Jul 2026 (best on the register).** GLEIF Level-1 data is published under **CC0 1.0 — public domain**: freely accessible, copyable, and usable **for any lawful purpose including commercial, without permission, payment, or attribution** (`gleif.org/en/about/open-data`, `/meta/lei-data-terms-of-use`, fetched live). The only ToU constraints are not misrepresenting the data as GLEIF-provided/endorsed and not implying affiliation — trivially honored.
- **Why it replaced EDGAR:** EDGAR covered **US-listed firms only** — it fed *none* of the five test vendors reliably (2 listed, 3 private/AU) and required a contact-bearing UA on pain of a 403 IP ban. GLEIF resolves **all five**. EDGAR removed from the collector registry.
- **Coverage verified live 20 Jul 2026:** Atlassian, Snowflake, Canva, OneTrust, MYOB all resolve to an LEI record (MYOB's shows a `LAPSED` registration — a real, if mild, signal).

#### 7b. Wikidata — the second, domain-verified register (corroborates GLEIF)

- **Why a second source (lever 2).** Confidence should reward *corroboration*: two independent public registers agreeing that an entity is live is stronger evidence than one. GLEIF is register #1; Wikidata is register #2. When both land on `legal_entity_status` and agree, the engine combines their reliabilities (noisy-OR, methodology §5.4.3) and the category reads at higher confidence than either alone — **earned**, not tuned.
- **Why Wikidata and not ABN Lookup / Companies House.** ABN Lookup and Companies House both require a **registered API key** (auth-gated), which breaks the free/no-auth PoC rule. Wikidata is **CC0 / public domain, no key**, *and* it carries the official-website property (P856) that GLEIF lacks — so it resolves by **domain**, fixing GLEIF's name-only blind spot. ABN/Companies House remain roadmap enrichments for a keyed build.
- **Collection:** `wbsearchentities` (name → candidates), then `Special:EntityData/{QID}.json` per candidate. Resolution keeps **only** a candidate whose P856 official-website registrable domain **equals the vendor's domain**; no domain match → emit **nothing** (`empty`). Corroborating the *wrong* entity is worse than not corroborating — so honest silence is the default.
- **Signals:** entity existence + dissolution (P576). Domain-verified & no P576 → benign "active_confirmed"; P576 present → "dissolved" (distress). Entity-level only (§4.2 — no natural persons).
- **Reliability:** **0.7** — community-edited, but every emission is domain-anchored to a hard identifier, so a false attribution is very unlikely.
- **Legal / ToS position:** **Verified clean 21 Jul 2026.** Wikidata structured data is **CC0 1.0** (`wikidata.org/wiki/Wikidata:Licensing`, fetched live): no restriction on automated access or commercial use, no attribution required. Wikimedia's **one** hard condition is a descriptive, contact-bearing **User-Agent** (a generic/library UA is 403'd by their robot policy) — honored by the shared client's UA.
- **Coverage verified live 21 Jul 2026:** Canva, Atlassian, Xero, Slack all domain-verify (Xero resolves to *Xero Limited* — a bare name search returns a film); **Cochlear** returns no domain match in the candidate set → correctly emits no corroboration (GLEIF alone stands).

#### 8. NVD API

- **Signals:** CVEs, CVSS severity, affected version ranges.
- **Collection:** NVD REST API (API key recommended for rate).
- **Reliability:** **High** for CVE facts.
- **Limits — the important one.** Mapping CVEs to a vendor requires knowing their internal stack, which OSINT barely reveals. **Therefore scope narrowly:** use NVD to score vendors who *make software* (their product's CVE and end-of-life history), **not** as a proxy for infrastructure they merely run. Inferring "vendor is vulnerable" from a banner is speculation, and we will not do it.
- **Legal / ToS position:** **Clean with obligations.** Commercial use permitted. Without an API key, limited to posted public rate limits; higher volume requires a free registered key, which "should not be used by, or shared with, individuals or organizations other than the original requestor." **Mandatory attribution — the product must display prominently:** *"This product uses the NVD API but is not endorsed or certified by the NVD."* NIST's name may not be used to imply endorsement. **Action:** this notice is a UI requirement on the scorecard, not a footnote to add later.

#### 9. CISA Known Exploited Vulnerabilities (KEV)

- **Signals:** vulnerabilities **known to be actively exploited in the wild** — a sharper signal than CVSS severity, which measures theoretical badness.
- **Collection:** public JSON feed. **Verified live 17 Jul 2026** — `catalogVersion 2026.07.16`, 1,647 vulnerabilities.
- **Reliability:** **High**, and high-signal: KEV membership means *observed exploitation*, not hypothesis.
- **Limits:** same stack-mapping limit as NVD — scope to vendor products.
- **Legal / ToS position:** feed carries **no licence field**. As a US Government work, CISA material is generally not subject to domestic copyright. **Open item:** confirm CISA's published data-licence statement rather than relying on the general rule.

#### 10. GDELT

- **Signals:** adverse media, incident reporting, tone/sentiment, event coding across global news.
- **Collection:** free API / bulk files.
- **Reliability:** **Moderate.** Media reports allegations, not findings. Coverage volume tracks newsworthiness, not risk — a large consumer brand generates more coverage than a riskier obscure vendor.
- **Limits:** noisy; severe entity-resolution burden; **absence of adverse media is close to meaningless** for a small vendor. Media tone must never drive score directly without human or AI adjudication.
- **Legal / ToS position:** **The strongest licence on this list.** Verbatim: *"all datasets released by the GDELT Project are available for unlimited and unrestricted use for any academic, commercial, or governmental use of any kind without fee."* Redistribution and rehosting expressly permitted with citation to the GDELT Project and a link to `gdeltproject.org`.
- **Why this instead of Google News:** Google News has no free official API and scraping it breaches Google's terms. GDELT delivers the same signal class with an unimpeachable licence. **This is the selection principle working as intended** — we chose the source with the better legal position, not the more familiar name.
- **Designated AI moment:** summarising which adverse-media hits *actually matter* is precisely the work a human would otherwise do by hand — the brief's own example.
- **v3.2 status change:** GDELT is now **held / `ai_adjudicated`** — it gathers candidates into the evidence store but does **not** score. The *scored* adverse-media signal moved to hard-fact regulator feeds (§10a), which report findings, not allegations, and carry no defamation exposure.

#### 10a. Regulator enforcement feeds (FTC + cleared feeds) — the scored adverse-media source

- **Signals:** named enforcement actions, settlements, orders, and investigations that mention the vendor — hard facts, dated and attributed.
- **Collection:** polite `GET` of official RSS/Atom feeds; parse entries; match the vendor name/domain as a **word** (so "canva" does not fire on "canvas"). A matched item is a **review candidate** (§5.4.1 defamation control), never an auto-published verdict; no match → a clean receipt.
- **Reliability:** **High when matched** (a regulator's own publication is a fact). **Low for a clean receipt (0.4):** a feed only exposes its recent window, not a searchable history, so "no action found" is weak evidence of absence.
- **Limits — stated, not hidden:** v1 is **US-weighted**. The FTC press feed (`ftc.gov/feeds/press-release.xml`) is reachable and clean (verified live 20 Jul 2026, valid RSS with real enforcement entries). **CISA hard-blocks automated access** (Akamai anti-bot — 403 even with a browser UA; excluded on ToS grounds, and its advisories are product-vuln already covered by KEV/NVD). **OAIC and ICO publish no stable public RSS** (verified 20 Jul 2026) — AU/UK regulator feeds are a roadmap gap. The collector polls whatever cleared feeds are listed and degrades gracefully.
- **Legal / ToS position:** **Clean.** Government open data / statutory publications, published to be read and syndicated via RSS. Honour rate limits, identify our agent.

#### 11. Vendor trust pages, `security.txt`, public DPAs and subprocessor lists

- **Signals:** ISO 27001 / SOC 2 claims and expiry, pen-test attestations, DPO contact, **subprocessor lists → fourth-party dependencies**, status pages, published SLAs.
- **Collection:** polite fetch of the vendor's own published pages; honour `robots.txt`.
- **Reliability:** **Low to moderate — self-reported.** This is the vendor talking about itself, i.e. the exact input the brief is trying to move away from. Treat as *claim*, not *evidence*, unless independently corroborated (e.g. certificate registry lookup).
- **Limits:** unverified claims; stale pages; absence of a trust page correlates with company size, not risk.
- **Legal / ToS position:** publicly published by the vendor for the purpose of being read. Honour `robots.txt`, identify our agent, rate-limit. Per-vendor terms must be checked for any vendor placed under recurring monitoring.
- **Why it still earns its place — the fourth-party angle.** Public DPAs list subprocessors, which yields fourth-party dependency data **for free**. This directly serves **CPS 230 ¶48** (managing risks from fourth parties a material service provider relies on) and is the one thing questionnaires are worst at surfacing. Discovering that six vendors share one subprocessor is a concentration finding a client cannot obtain any other way.
- **Designated AI moment:** classifying an unstructured trust page into structured certifications with expiry dates — the brief's other stated example.

---

### Sources requiring a decision before collection

The brief says: *"If you are unsure, ask before you collect — not after."* These two are that case. Both are Australian, both are the most locally relevant sources on the list, and **neither states a licence.**

#### 6. DFAT Consolidated List (Australian sanctions)

- **Signals:** individuals, entities and vessels under Australian sanctions — targeted financial sanctions, travel bans, arms embargos.
- **Collection:** XLSX at `dfat.gov.au/sites/default/files/Australian_Sanctions_Consolidated_List.xlsx` — verified present, last updated 10 July 2026.
- **Status:** **No licence or terms of use located on the DFAT sanctions pages.** Australian Government material is *often* released under CC BY 4.0 per the Open Access and Licensing framework, **but DFAT has not stated this for this file and we will not assume it.**
- **Why it matters commercially:** dealing with a listed entity is a criminal offence (up to 10 years). The list exists to be screened against, so a use-restriction would be perverse — but "would be perverse" is not a legal position.
- **→ ACTION:** written query to the Australian Sanctions Office confirming licence terms for automated ingestion and use within a commercial screening product. **Until answered, use the ITA Consolidated Screening List as the sanctions gate and record Australian sanctions coverage as a known gap on the scorecard.**

#### 12. Australian Modern Slavery Statements Register

- **Signals:** statutory modern-slavery statements under the *Modern Slavery Act 2018* (Cth) — supply-chain diligence, remediation, governance.
- **Status:** register confirmed live. Only legal statement located: **"Copyright Attorney-General's Department © 2026"** — no licence, no stated API, no stated bulk-download terms.
- **Why it matters:** free, statutory (its importance grounded in the *Modern Slavery Act 2018*, not in any demo framework), locally relevant, and an obvious *Modern Slavery & Human Rights* signal — and it is very unlikely anyone else on this project will think of it.
- **→ ACTION:** written query to the Attorney-General's Department on licence and automated access. **Held out of v1 pending reply.**

---

### Excluded sources

#### VirusTotal — EXCLUDED (commercial use prohibited)

Public API terms state: **"The Public API must not be used in commercial products or services."** Also barred from use "in business workflows that do not contribute new files." Enforcement is stated as "immediate permanent ban." Free tier is 500 requests/day at 4/minute.

Since the strongest work here is a candidate for the Wahid AI platform, this is disqualifying **now**. Excluding it at the start is cheaper than discovering it at handover. Commercial licensing exists and is a paid feed — out of scope per the brief. *Note: the early brainstorm source table listed VirusTotal without flagging this.*

#### Qualys SSL Labs — EXCLUDED (four independent blockers)

The most instructive exclusion on the list. Verbatim from the Terms of Use, **"You are not allowed, without our express permission, to:"**

- *"(i) use the API for commercial purposes;"*
- *"(ii) use the API on a public web site;"*
- *"(iii) publish any information received from us via the APIs without the owner's express permission;"*
- *"(iv) distribute, proxy, or otherwise make the API available for access or use by any person or entity other than your authorized employees, including but not limited to acting as a service bureau or developing a competing product or service offering."*

And the permitted-use clause is fatal on its own: **"use the API only to inspect only sites and servers whose owners have given you permission to do so."** We are assessing vendors precisely *because* we have no relationship with them — we will never have that permission. Separately: *"Using automation to request site assessments and/or extract assessment results from HTML pages ('scraping') is expressly forbidden."*

**Any of the four kills it. The permission clause alone makes SSL Labs structurally incompatible with third-party OSINT assessment — the product's own terms forbid the use case.** We obtain the same signal by running our own TLS handshake (source 3), which is why that choice was made on legal grounds first. *Note: the early brainstorm source table listed SSL Labs as a recommended source.*

#### Shodan / Censys — ROADMAP

Free tier limits results and query types; meaningful assessment volume pushes into paid, which the brief rules out. Shodan's terms permit product integration with attribution, but academic/research access is expressly non-commercial — meaning the *free* route and the *commercial* route are not the same route. Most estate-visibility value is already obtained from Certificate Transparency at zero cost and zero ToS risk. **Documented as a future paid option per the brief's instruction to note paywalled sources and move on.**

#### Google News (scraped) — EXCLUDED

No free official API; scraping breaches Google's terms. **Superseded by GDELT**, which is licensed for exactly this.

#### Corporate registries — ABN Lookup (AU) CLEAR-CONDITIONAL · Companies House (UK) CLEARED · OpenCorporates UNRESOLVED

**These directly address Business & Financial Stability's recall gap** — EDGAR is US-listed only (the MYOB test). Reviewed 20 Jul 2026 against each source's *actual* terms, fetched live, not a secondary summary.

- **ABN Lookup (AU) — CLEAR-CONDITIONAL, adopt (roadmap collector).** The Web Services Agreement (`abr.business.gov.au/Tools/WebServicesAgreement`, fetched live) permits *"provide relevant extracts of the ABN Lookup Web Services to third parties"* at your own risk, sets **no commercial bar** and **no bulk-harvest bar** (we do targeted per-vendor lookups, not bulk extraction), and requires only that you **not imply Commonwealth endorsement**. Free; needs a free registration **GUID** (same identify-yourself posture as EDGAR). Authoritative for AU status (Active / Cancelled / Deregistered) — **this is the source that actually solves the MYOB test.**
- **Companies House (UK) — CLEARED, adopt (roadmap collector).** Confirmed live: data is under the **Open Government Licence** with **no commercial restriction** (*"use the data in commercial applications without licensing fees"*), free API key, **600 requests / 5 min**, attribution required. Authoritative for UK status (Active / Dissolved / Liquidation / Administration / insolvency). **Resolves the earlier "auth wall — unresolved" finding.**
- **USPTO trademarks — HELD (weak proxy).** Public-domain US-gov data (legally clean), but *"dead trademark ⇒ business closure"* is a weak inference and the named TESS interface was retired in 2023 (now Trademark Search / TSDR API). Roadmap at most; not built first.
- **OpenCorporates — UNRESOLVED.** Terms URL still 404s; not cleared, not used.

**PII discipline (all of the above):** take **entity status only** — never director/officer personal data — holding the §4.2 bright line (score entities, not natural persons). **Status (v3.2):** Business & Financial Stability is now wired to **GLEIF** (§7) — global, CC0, no auth, resolves all five test vendors. ABN Lookup + Companies House remain **roadmap enrichments** that would add a *second* authoritative source for AU/UK entities (corroboration raises confidence); they are no longer the *only* path off EDGAR.

#### Data-availability re-feed candidates (v3.1 gap-closers)

The v3.1 re-tier (§5.9) held three categories for having no live collector. Reviewed 20 Jul 2026 — two have a **legally clean re-feed path**, one needing *no new external API*:

- **Supply Chain & Dependency — re-feed from ALREADY-CLEARED collectors (strongest).** Fourth-party dependency is inferable from data `dns`, `ct` and `trust` *already* retrieve: third-party infra suffixes in DNS/MX/CNAME (`amazonses.com`, `okta.com`, `cloudflare.net`), CT SAN/CNAME dependencies (`herokuapp.com`, `azurewebsites.net`), and published `/subprocessors` · `/dpa` lists. **No new clearance** — DNS/CT are facts (*IceTV*, RFC 6962), trust pages are published to be read. Build = a normalizer enhancement + a "critical third-party" dictionary. **Caveat:** gives per-vendor *enumeration*; `concentration_risk` (shared dependencies across the portfolio) still needs the portfolio view (roadmap).
- **Adverse Media — BUILT in v3.2 (regulator RSS).** The factual half of adverse media now scores via the regulator-feed collector (§10a): FTC enforcement RSS is reachable and clean (verified live 20 Jul 2026); a matched named action is a hard fact. On probing, **CISA blocks automated access** and **OAIC/ICO have no stable RSS**, so v1 is honestly US-weighted with a configurable feed list (documented, not hidden). Raw GDELT sentiment stays `ai_adjudicated`/held. Adverse Media was **promoted held → scored (6%)**. Wikidata `legal case`/`fine` (CC0) remains a patchy roadmap supplement.

**Supply Chain** remains a **roadmap build** (re-feed from already-cleared dns/ct/trust — no new clearance). **Adverse Media is done** (above). **Data Privacy & Leakage** has **no** clean free re-feed found yet (HIBP paste/domain is paid). Business & Financial Stability was **re-sourced EDGAR → GLEIF (§7)** and, in v3.3, **corroborated by a second register — Wikidata (§7b)** — domain-verified, which lifts confidence where both agree (4 of 5 test vendors); ABN Lookup + Companies House stay roadmap (both key-gated).

---

### Cross-cutting limits

These apply to the register as a whole and belong in the methodology, not in any single source row.

**Entity resolution is the hard problem, not collection.** Proving a breach, sanction or news item belongs to *this* vendor — not a homonym, subsidiary, or unrelated namesake — is where accuracy is actually won or lost. The French Compliance Society white paper flags this directly, warning about "the rate of homonymy" and false positives, and the AFA concludes that automated tooling "requires human analysis in order to adjust the assessment, particularly for the most high-risk third parties." Sanctions screening is the acute case: a false positive on a sanctions gate is a serious accusation against a real company. **Design consequence:** sanctions hits must surface as *review items with evidence*, never as silent automated score changes.

**Absence of evidence is not evidence of absence.** No breach record, no adverse media and no SEC filing are the *default* state of a small private vendor with a clean public footprint — and also of a badly-run one nobody has written about yet. **Design consequence:** missing data must reduce *confidence*, never reduce *risk*. Any model where a vendor scores well by being invisible is broken, and this is the most likely way a naive implementation fails.

**Public data is stale and patchy.** NIST SP 1326 gives us the four variables to weigh per finding — **age of the information, frequency of occurrence, severity, and mitigations in place** — which is effectively a decay-and-context model handed over by a US federal publication. Adopt it, and cite it.

**Regulator warning against bought scores — the argument for this project.** The AFA "warns about the automatic rating systems provided by digital solutions, specifying that users must be able to determine their own rating system with regard to risk mapping." A regulator is on record saying black-box vendor scores are not defensible and that you must own your model. **This is the brief's thesis, independently confirmed by a regulator, and it belongs in the methodology's opening argument.**

**Data egress — the optional LLM summariser.** The only component that sends data to a third party *not* on the source register is the opt-in evidence summariser (`app/summariser.py`, methodology "the AI moment"). It is off by default (no `TPRM_LLM_*` env → the endpoint returns 503) and, when on, is provider-agnostic over any OpenAI-compatible `chat/completions` host the operator chooses (OpenRouter, Groq, Google's OpenAI-compat surface). What leaves the system is the finished **record** — the score roll-up **plus the actual hash-stamped observations each source returned** (so the digest is about *what was found*, not a restatement of the numbers). This is deliberately **bounded** (per-receipt and total caps, test-enforced: `test_context_is_bounded_per_receipt`) and it is **only the already-collected, lawfully-public OSINT the system already holds** — PII is minimised at *collection* (entity-level / role addresses only), so the summariser exposes nothing the collectors did not already lawfully retain. The summary is a read layer: it never computes or alters a score, never writes to the immutable evidence store, is returned marked AI-generated, and cites the `content_hash`es it was built from so a reviewer can verify it against the receipts. **Design consequence:** an operator turning this on chooses their own LLM provider and inherits *that* provider's data-handling terms for the entity-level evidence described above — a deliberate, documented, single egress point, not a hidden dependency.

---

### Coverage against the scoring model

Mapping the cleared sources against NIST SP 1326's five due-diligence categories shows where v1 is strong and where it is honestly thin:

| NIST SP 1326 category | Covered by | Strength |
|---|---|---|
| Foundational Cyber Practices (supplier) | CT, DNS, TLS/headers, HIBP | **Strong** |
| Foundational Cyber Practices (product) | NVD, KEV | Moderate — vendor-products only |
| Resilience | GLEIF (entity standing), regulator RSS, HIBP | Moderate — standing not financials |
| Supply Chain Tiers (fourth party) | Subprocessor lists | Moderate — self-reported |
| FOCI / Provenance | *(registries — unresolved)* | **Weak — v1 gap** |

**FOCI and Provenance are the honest gap in v1**, pending resolution of ASIC / Companies House / OpenCorporates. This is stated rather than papered over, per the brief's instruction to be honest about confidence.

**Note on what OSINT cannot reach.** Taking the ~27 criteria from an illustrative demo questionnaire template (**not authoritative** — used here only as a rough criteria inventory) as a checklist: roughly 7 are observable from public data, ~10 are partially observable via proxy, and ~10 (access controls, security monitoring, data handling, insurance, change management, contract terms) are invisible to any lawful external observer. **No source register can close that gap** — it is a property of the problem, not of the sourcing. The product implication: OSINT does not replace the questionnaire framework; it pre-fills the fraction it can evidence independently and **flags contradictions** where a vendor's self-assessment disagrees with the public record.

---

### Open items

1. **DFAT** — written query to the Australian Sanctions Office on licence terms. *(blocking AU sanctions coverage)*
2. **Modern Slavery Register** — written query to the Attorney-General's Department. *(blocking ESG dimension)*
3. **CISA KEV** — confirm published data-licence statement rather than relying on the general US Gov rule.
4. **ASIC / OpenCorporates** — resolve terms. *(blocking FOCI + Provenance)* — **Companies House RESOLVED (cleared, OGL) and ABN Lookup CLEAR-CONDITIONAL (both 20 Jul 2026); build as Business-Stability collectors, roadmap.**
5. **crt.sh** — accept the low residual risk of an unstated-terms index. **Cert Spotter fallback added (20 Jul 2026)** for crt.sh's frequent outages; production use of Cert Spotter should move to a free SSLMate account per their tiering (evaluation-cleared for the PoC).
6. **Per-vendor `robots.txt`** — must be checked per test vendor before trust-page collection.
7. **Active-exposure / reputation candidates — VERIFY BEFORE CLEARING.** To close the "no live blocklist / open-port" gap (methodology §5.10 Roadmap #1) *without* the Shodan/Censys free tier — whose commercial-use bar disqualifies it for a commercial-platform candidate (Censys ToS verified 20 Jul 2026: *"Censys Free Customers… are expressly prohibited from using the Service and Censys Data for commercial purposes of any kind"* — the VirusTotal trap). Candidates proposed with **unverified** commercial-use claims, each needing the live-ToS treatment before use: **URLScan.io**, **OpenPhish**, **PhishStats**, **AlienVault OTX**, **AbuseIPDB**, **GreyNoise Community** (community tiers of the latter two are often non-commercial — check). **None cleared. Do not integrate on a secondary claim.**

### Verification log

| Source | Method | Result | Date |
|---|---|---|---|
| crt.sh | live fetch | No ToS/AUP found; Sectigo operates | 17 Jul 2026 |
| HIBP | live fetch of `/API/v3` | CC BY 4.0; `/breaches` unauthenticated | 17 Jul 2026 |
| GDELT | live fetch of `/about.html` | Unrestricted commercial use confirmed | 17 Jul 2026 |
| NVD | live fetch of ToS page | Commercial OK; attribution notice mandatory | 17 Jul 2026 |
| CISA KEV | live fetch of JSON feed | v2026.07.16, 1,647 CVEs, no licence field | 17 Jul 2026 |
| ITA CSL | live fetch | Free API; no restriction stated | 17 Jul 2026 |
| SEC EDGAR | live fetch → **403** | UA + 10 req/s enforcement confirmed → **REMOVED (→ GLEIF)** | 17 Jul 2026 |
| **GLEIF (LEI)** | live API + terms fetch | **CC0/public domain, commercial OK, no auth; all 5 vendors resolve** | 20 Jul 2026 |
| **Cert Spotter (SSLMate)** | live API + ToS fetch | 200 in ~2s; ToS bars no commercial/automated use; free tier = eval | 20 Jul 2026 |
| **FTC enforcement RSS** | live fetch | Valid RSS, real enforcement entries; gov open data | 20 Jul 2026 |
| CISA feeds | live fetch (browser UA) | **403 — anti-bot; excluded** for automated adverse-media | 20 Jul 2026 |
| OAIC / ICO RSS | search + probe | **No stable public RSS found** — AU/UK feed gap | 20 Jul 2026 |
| DFAT | live fetch + search | XLSX confirmed; **no licence found** | 17 Jul 2026 |
| Modern Slavery Register | live fetch | Copyright notice only; **no licence** | 17 Jul 2026 |
| VirusTotal | ToS lookup | Commercial use prohibited | 17 Jul 2026 |
| SSL Labs | ToS PDF, extracted | 4 blocking clauses quoted | 17 Jul 2026 |
| Shodan | ToS lookup | Free tier limited; non-commercial research tier | 17 Jul 2026 |
| OpenCorporates | live fetch → 404 | Unresolved | 17 Jul 2026 |
| Companies House | OGL confirmed — commercial OK, free key, 600/5min | **Cleared** | 20 Jul 2026 |
| ABN Lookup (AU) | Web Services Agreement fetched — 3rd-party extracts OK, GUID required | **Clear-conditional** | 20 Jul 2026 |

---

### References

- NIST SP 1326, *C-SCRM Due Diligence Assessment Quick-Start Guide* (July 2026) — https://csrc.nist.gov/pubs/sp/1326/ipd
- APRA *Prudential Standard CPS 230 Operational Risk Management* — https://www.apra.gov.au/prudential-standard-cps-230-operational-risk-management
- French Compliance Society, *From Third Party Assessment to Third Party Risk Management*
- ISO/IEC 27001:2022, Annex A controls 5.19–5.23 (supplier relationships) — https://www.iso.org/standard/27001
- Have I Been Pwned API v3 — https://haveibeenpwned.com/API/v3
- GDELT Project — https://www.gdeltproject.org/about.html
- NVD API Terms of Use — https://nvd.nist.gov/developers/terms-of-use
- CISA KEV Catalog — https://www.cisa.gov/known-exploited-vulnerabilities-catalog
- ITA Consolidated Screening List — https://www.trade.gov/consolidated-screening-list
- DFAT Consolidated List — https://www.dfat.gov.au/international-relations/security/sanctions/consolidated-list
- GLEIF Open Data / LEI Data Terms of Use (CC0) — https://www.gleif.org/en/about/open-data · https://www.gleif.org/en/meta/lei-data-terms-of-use
- SSLMate Cert Spotter CT Search API + ToS — https://sslmate.com/ct_search_api/ · https://sslmate.com/policies/tos
- FTC press-release RSS — https://www.ftc.gov/feeds/press-release.xml
- SEC EDGAR access policy *(source removed v3.2 — retained for provenance)* — https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
- Qualys SSL Labs Terms of Use — https://www.ssllabs.com/downloads/Qualys_SSL_Labs_Terms_of_Use.pdf
- VirusTotal API — https://docs.virustotal.com/reference/public-vs-premium-api
- Shodan Terms of Service — https://static.shodan.io/legal/terms.html

*Attribution obligations carried into the product: HIBP (CC BY 4.0 + link), GDELT (citation + link), NVD (verbatim non-endorsement notice).*
