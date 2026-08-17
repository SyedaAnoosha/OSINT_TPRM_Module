# Methodology — OSINT for Third-Party Risk

**Deliverables 1 & 3** (research methodology · v1 scoring model)
**Status:** v2 · scoring model **`scoring.yaml` v5.3.0 (penalty-based posture + Business Stability axis)** · **Author:** *(intern)*
*Companion docs: [`scoring_model.md`](scoring_model.md) (the model in brief) · [`research_doc.md`](research_doc.md) (source methodology) · [`roadmap.md`](roadmap.md) · [`financial_integration_design.md`](financial_integration_design.md) (Business Stability design).*

> **This document is the product.** The code demonstrates it. If the PoC were deleted tomorrow, this file should be enough for someone else to rebuild it and get the same scores. Execution sequencing lives in `project_plan.md`; it is deliberately not here.

---

## 1. Objective

Take a vendor name or domain and return a **structured risk record and an overall score**, assembled automatically from lawfully-collected public information, where **every point of that score is traceable to stored evidence.**

Three constraints shape everything below, in this order:

1. **Defensibility before coverage.** A score we cannot reconstruct is worse than no score — see `legal_and_standards_basis.md` Finding A, which establishes that this is a legal standard in Australia, not a preference.
2. **Legality before coverage.** Per-source positions are settled in `source_assessment.md`; model-level constraints in `legal_and_standards_basis.md`.
3. **Honesty before completeness.** OSINT is patchy. The model must say so in its own output, structurally, not in a footnote.

**What this is not.** It is not a replacement for a questionnaire framework. Taking the criteria list in `an_example_risk_scoring_System.md` (an illustrative demo template, **not authoritative** — see §5.6) merely as a rough inventory of ~27 plausible criteria: roughly **7 are observable** from public data, ~10 partially observable by proxy, and ~10 (access controls, security monitoring, data handling, insurance, change management, contract terms) are **invisible to any lawful external observer**. That is a property of the problem, not of our sourcing. OSINT **pre-fills the fraction it can evidence independently and flags contradictions** where a vendor's self-assessment disagrees with the public record. Contradiction-flagging, not replacement, is the product.

### The thesis

> A regulator (the AFA) is on record warning against bought, black-box vendor scores, *"specifying that users must be able to determine their own rating system with regard to risk mapping."*

The brief's central instruction — propose and defend your own model — is independently confirmed by a regulator, and separately enforced by the Australian courts (Finding A). **Owning the model is not a differentiator. It is the only lawful way to sell a score.**

---

## 2. Scope

### In scope for v1

| | |
|---|---|
| **Input** | Vendor name **or** domain |
| **Output** | Structured record + category postures + overall posture + grade + **confidence** + evidence trail |
| **Sources** | The 14 cleared collectors in `source_assessment.md` |
| **Categories** | 5 scored + 2 context + gate (§5.2); 5 held |
| **Test vendors** | 5 real, named, deliberately varied (§2.3) |
| **Automation** | End-to-end collection → score → record, no manual steps except the adjudication gate (§5.5) |

### Explicitly out of scope for v1 — with reasons

| Excluded | Why | Where it goes |
|---|---|---|
| Paid feeds (Shodan, Censys, VT commercial, HIBP Pro) | Brief: free/trial only | Roadmap |
| VirusTotal, SSL Labs | ToS prohibit our use case | Permanently excluded |
| AU sanctions (DFAT) | Licence unresolved | **Blocking** — see §4.4 |
| ESG / Modern Slavery | Licence unresolved | **Blocking** — category held (emits nothing) |
| FOCI / Provenance | Registry terms unresolved | Roadmap — §8.3 |
| Scoring natural persons | Legal bright line | **Never** — §4.2 |
| Financial quantification (FAIR $) | Inputs don't exist | §5.7 |

### 2.3 Test vendors

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

**Still needed (open item):** a vendor with **almost no public footprint** and one with an **expired certificate**, both required by the brief. These must be found empirically from CT logs rather than assumed — expired certs are transient. See `project_plan.md` Phase 1.

**Note on collecting about real companies.** These are real organisations and the record includes breach and adverse-media data. Per the brief: *"do not republish or expose it."* Records stay internal; the sample scorecard for Deliverable 4 uses a vendor whose findings are already a matter of public record.

---

## 3. OSINT Sources

Full assessment — signals, reliability, limits, ToS position, verification log — is in **`source_assessment.md`** and is not duplicated here. Summary of what feeds the model:

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

### 3.1 The three cross-cutting limits

These are properties of the register as a whole and drive model mechanics in §5.

**Entity resolution is the hard problem, not collection.** Proving a breach, sanction or news item belongs to *this* vendor — not a homonym, subsidiary or namesake — is where accuracy is won or lost. The AFA warns about *"the rate of homonymy"* and concludes automated tooling *"requires human analysis in order to adjust the assessment, particularly for the most high-risk third parties."*

**Absence of evidence is not evidence of absence.** No breach, no adverse media and no SEC filing is the **default state of a small clean vendor — and of a badly-run one nobody has written about yet.** → **Missing data reduces confidence, never risk** (§5.4). Any model where a vendor scores well by being invisible is broken. This is the most likely way a naive implementation fails, and §5.4 exists solely to prevent it.

**Public data is stale and patchy.** → NIST SP 1326's four variables (§5.3).

---

## 4. Legal Frameworks & Standards

Full analysis in **`legal_and_standards_basis.md`**. What the model must obey:

### 4.1 The two findings

**Finding A — `ABN AMRO v Bathurst Regional Council` [2014] FCAFC 65.** Publishing a rating conveys an implied representation it was formed **on reasonable grounds with reasonable care and skill**; where it wasn't, it is misleading and deceptive conduct under **ACL s 18** (no intent required, honest mistake no defence). A duty of care was owed **without any contract**. → **The evidence store is a legal artefact. Every score reconstructible from retained records. Confidence published alongside every score.**

**Finding B — `Autonomous Sanctions Act 2011` (Cth) s 16.** Strict liability for bodies corporate; the **only** exit is s 16(7), which requires the company to **prove** reasonable precautions and due diligence, bearing a **legal burden**. → **Sanctions are a gate, not a weight. Tune for recall. Retain screening records including clean results.**

### 4.2 Binding constraints

| Instrument | Rule it imposes on the model |
|---|---|
| **Privacy Act 1988** + *Clearview AI* [2021] AICmr 54 | "It's public" is **not** a defence. **APP 10:** personal info used must be accurate, up-to-date, complete, **relevant** |
| **Privacy tort** (from 10 Jun 2025) | Reaches non-APP entities; no small-business shield |
| **Copyright Act** + *IceTV* [2009] HCA 14 | Facts unprotected; **expression** protected; **no TDM exception** → store normalised facts, not verbatim text |
| **Defamation** (MDP 2021) | Large vendors **cannot** sue; **small vendors and named individuals can** → adverse media worded as *reported/alleged*, dated, attributed |
| **Criminal Code Pt 10.7** | Publication authorises retrieval — collection design already compliant |

> **The bright line, reached independently by three instruments** (APP 10, the privacy tort, and EU AI Act Art 6(3)): **score entities, not natural persons.** Sole traders are where the analysis changes. Three separate authorities converging on one design rule is a rule worth taking seriously.

### 4.3 What the buyer must evidence (the demand-side spec)

| Instrument | Why it drives a feature |
|---|---|
| **APRA CPS 230 ¶47–48** | **Fourth-party risk is a regulated obligation.** Subprocessor concentration is not a clever extra — it is the regulated deliverable |
| **APRA CPS 234** | Demands **control effectiveness** assurance. OSINT cannot see it → **never claim discharge; claim subset + contradictions** |
| **SOCI Enhanced CIRMP Rules 2026** (reg. 9 Jun 2026) | **FOCI assessment of major suppliers mandatory**, phase-in ~mid-2028 → reframes our FOCI gap as a roadmap item with a deadline and a buyer |
| **Modern Slavery Act 2018** | Statutory register; **licence unstated** → held |

⚠ **The repo's CPS 230 PDF is superseded** — amended CPS 230/CPG 230 commenced **1 July 2026**. Re-check ¶ numbering before any client-facing use.

### 4.4 Standards adopted — and why each

| Standard | What we take | Why it matters |
|---|---|---|
| **NIST SP 1326** | Five due-diligence categories; **four per-finding variables**; ITA CSL by name | **Borrowed authority for the decay model** (§5.3) |
| **NIST CSF 2.0 GV.SC** | Supplier criticality, **ongoing monitoring**, relationship conclusion | **Authority for agentic re-scoring** — it's a named C-SCRM outcome, not a flourish |
| **ISO 31000 / IEC 31010** | Process discipline; 41 techniques with stated limits | Method defence |
| **ISO/IEC 27001:2022 A.5.19–5.23** · **27036** | Supplier relationship controls | Dimension design |
| **Open FAIR (O-RT/O-RA)** | Frequency/magnitude **separation** | **Cited, not implemented** — §5.7 |

**"We adopted NIST's model" survives a client challenge. "We thought this was sensible" does not.** That is the entire purpose of this table.

---

## 5. Scoring Framework

> **Direction convention, stated once and never inverted: `100 = strongest posture, 0 = weakest`. A penalty is SUBTRACTED for each issue found.**

> **Model vocabulary — read once, resolves the rest of §5.**
> The shipped model is **`scoring.yaml` v5.2.0 — a penalty-based POSTURE model.** Every vendor starts at 100; each issue found subtracts a penalty sized by severity; a category's posture is 100 minus its own penalties, and the overall posture is **100 minus the total penalty divided by a fixed divisor**, published with a letter grade A–F and a plain-English reason for every deduction. It is inspired by UpGuard's subtractive method but is our own — our 0–100 scale, our categories, our differentiators (§5.10).
>
> **Why the model changed from a weighted-mean *risk* score to a penalty *posture* score.** The earlier design (d1–d3, a `category → subcategory → signal` weighted mean on a `0=low / 100=high` risk scale) needed a defensible *weight* for every category — *why is Cyber Hygiene 31%?* — a question with **no authoritative answer** (§5.6). The penalty model **deletes that problem**: a category's influence emerges from how many issues it has and how bad they are, so there are no weights to derive or defend — **open items 9, 10 and 13 disappear.** The weighted-mean lineage is retained in §5.6 for provenance and for the benchmark cross-check it still gives us; the current model is penalty-subtractive throughout, and any category-percentage figure elsewhere in this document is superseded d3 history.

### 5.1 Architecture

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

### 5.2 Categories — organised by business risk, not by source

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

### 5.2.1 Business Stability — A Separate Scoring Axis (v5.3.0)

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

### 5.3 Severity penalties and the four NIST variables

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

#### 5.3.1 Every deduction carries a sentence

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

#### 5.3.2 Config that scores nothing must not look like config that scores something

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

### 5.4 The rule that keeps the model honest

> **Missing data reduces *confidence*. It never changes *posture*.**

Mechanically:

- A signal that returns nothing is **dropped from its category's coverage** — never scored as a comfortable pass, never as a penalty. Because the overall divisor is **fixed by the model** rather than set by how many categories answered, an absent category contributes no penalty and cannot move the denominator: it genuinely neither helps nor hurts the posture. This is now enforced arithmetically and guarded by a regression test — identical findings with varying silent sources must produce an identical posture. It was *not* true before the fixed divisor, when averaging the covered categories let a clean receipt enter as a 100 and lift the score.
- **Confidence is pure evidence coverage:** of the signals we planned to collect, how many returned data. `coverage = covered / planned`; **High ≥ 0.90 · Medium ≥ 0.70 · Low < 0.70.**
- **Below `coverage < 0.4` the product refuses to publish a posture** and returns **`Insufficient evidence`** with the coverage gaps enumerated — *the Ghost*.

**That refusal is a feature and the strongest single expression of Finding A.** A model that always produces a number is a model that lies when it has nothing. MYOB (§2.3) exists to prove this branch fires: a thin entity record must yield *low confidence*, **not low posture** — and **a vendor cannot look strong simply by being invisible**, nor be punished for silence; silence is a confidence problem, surfaced as such.

> **Why confidence is coverage, and nothing more.** An earlier design multiplied coverage by source-reliability and freshness, and combined agreeing registers with a noisy-OR. That was defensible but hard to explain in a room and easy to contest number-by-number. The shipped model makes confidence **exactly one thing a client can verify** — *what fraction of the planned evidence came back* — and folds all the "how much do we trust this source" nuance into whether a signal is collected at all, and into the clean-receipt discount (§5.4.2). One axis, one sentence.

#### 5.4.1 Reading posture against confidence — the Ghost

Posture and confidence are **two axes, never one number**. Collapsing them is the failure this whole section exists to prevent, so the scorecard shows the confidence band **beside** the grade, never the grade alone.

| | **Confidence High / Medium** | **Confidence Low** |
|---|---|---|
| **Strong posture** | **Evidenced-strong** — corroborated. The only place a good grade truly means low risk. | **The Ghost** — *looks* clean only because we found little. **Not a strong vendor; an unassessed one.** → questionnaire |
| **Weak posture** | **Verified exposure** — act on it. | **Uncorroborated signal** — something is there we can't stand behind. → review, don't report |

**The Ghost is the quadrant that matters.** It is the visible form of *"absence of evidence is not evidence of absence"* (§3.1) and the reason §5.4 exists. A small clean vendor and a badly-run obscure one **both** land here, and the model cannot distinguish them — so it says so, by name, rather than quietly rewarding invisibility. Below 40% coverage the Ghost hardens into an outright refusal; a directly-observed current critical (§5.5.2) is the one thing certain even on thin coverage, so a fired ceiling **bypasses** the Ghost refusal.

Two consequences for the build: the scorecard shows the confidence band **beside** the grade, never the grade alone; and `Uncorroborated signal` must never be presented to a client as a finding — an uncorroborated adverse-media hit against a small vendor is precisely the defamation exposure in `legal_and_standards_basis.md` §4.2.

#### 5.4.2 The clean receipt — "checked and clean" ≠ "never checked"

Confidence being coverage still leaves **two** kinds of "missing", and conflating them is what would make every clean vendor read as a Ghost:

- **Never checked** — the source did not run, or ran and errored. No coverage. Correctly costs confidence.
- **Checked and clean** — the source was *successfully queried* and came back empty: HIBP has no breach, CISA KEV no product match, NVD no recent critical CVE. This is a real, citable observation — *"we queried the largest public breach corpus on `<date>` and this domain is absent"* — and it **counts toward coverage** as a benign **pass** (no penalty), not silence.

This is what lifts a genuinely-clean vendor out of the Ghost without claiming false certainty: the claim is never "secure", only "**no KNOWN event, per this named source, on this date**". The residual uncertainty rides on the fact that a clean receipt is a *pass*, not a definitive all-clear — an authoritative register is the exception, because a GLEIF "active / good standing" is an *exhaustive* positive fact (the entity either is or isn't on the register), not a hedged absence.

#### 5.4.3 Calibration is evidence, not assertion — the frozen corpus

A model that is never re-measured drifts. So the five benchmark vendors (§2.3) have their collector output **captured once and frozen** in `backend/tests/fixtures`, replayed through the real engine against a pinned clock, and asserted down to per-category penalties. Any change that moves a number fails the build and the diff names the vendor and the category that moved — an intended re-grade and a regression no longer look the same.

This is what makes the numbers in this document defensible rather than plausible. Three claims here are corpus-measured, not assumed:

- **The divisor.** A divisor equal to the category count — the plain mean of the category postures — scored **every** benchmark vendor A (86–92), including one carrying 13 known-exploited product matches. The current value was chosen from a sweep because it separates the evidenced-clean vendors from those with real findings, and it moves with the number of scoring categories (§5.1).
- **The confidence bands.** Real vendors return **0.96–1.00** coverage and band **High**, so the ladder discriminates. A test fails if a signal is ever added with no collector to feed it — which would grow the denominator, make `High` unreachable, and quietly turn every vendor into a Ghost.
- **The invariant.** Silencing every clean source across all five vendors drops confidence (1.000 → 0.692) with **zero** posture movement.

An honest note on method: the corpus **falsified** a prior claim during this work. The assertion that the Ghost fires on nearly every vendor came from a three-source synthetic probe; real fourteen-collector runs disproved it, and the planned "fix" would have made confidence *worse* by weighting a one-signal category equally with an eleven-signal one. It was dropped. That is the corpus doing its job.

### 5.5 Gates and the ceiling — where subtraction stops

Spreading the total across a fixed divisor is *compensatory* — strengths dilute weaknesses — which is correct for hygiene signals that genuinely trade off, and **wrong** for the three cases below. Two mechanisms override normal subtraction.

#### 5.5.1 Gates — the model emits nothing

| Signal | Behaviour | Authority |
|---|---|---|
| **Sanctions hit** | **BLOCK** → adjudication queue. **No score emitted.** | `Autonomous Sanctions Act` s 16(7) |
| **Entity resolution ambiguous** (confidence < 0.5) | **BLOCK** → manual confirmation. **No score emitted.** | §3.1 — never silently score the wrong company |

**Why a sanctions hit blocks rather than scores badly — or grades F.** A defence under s 16(7) is **not partially available**, so a weighted contribution is meaningless — but grading it F is no better, because a fuzzy name match would then have a machine silently make a **criminal accusation against a real company**, and a number in a field discharges no legal burden. An adjudication record does. **Surface generously, adjudicate manually, never auto-conclude.** Matching is whole-word (so *asana* can't trip on *villaSANA*) and recall-tuned; the clearing is itself the evidence. **This is the one place recall beats precision** — an inversion of the default everywhere else, stated wherever it appears. Xero (§2.3) was correctly BLOCKED here in live testing.

#### 5.5.2 The critical ceiling — non-compensatory (our knockout)

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

### 5.6 Why there are no category weights (and what the benchmark still gives us)

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

#### 5.6.1 Intra-category weights — the same discipline, one level down

The table above sets weights **between** categories. Weights **within** a category are a second, separate problem, and the temptation is to split evenly — `DNS 25% / TLS 25% / Headers 25% / CT 25%`. **An even split is not neutral; it is an unstated claim that four signals carry equal risk, which is false and indefensible on exactly the grounds §5.6 is built to survive.**

Same four-anchor discipline applies one tier down. Within a category, order signals by **directness of the risk each evidences** (a claim we document per source in `source_assessment.md`), **cross-check the ordering against the equivalent commercial-platform vector where one exists** (§5.6.2), and treat the exact split as a tunable, sensitivity-bounded default. **Observability does not enter here either** — a signal we read poorly lowers confidence in that signal, it does not lower its risk weight.

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

#### 5.6.2 Benchmark — where the commercial platforms disagree with us

**Bitsight and UpGuard publish their weights. A client with either subscription can check ours against theirs in an afternoon — so we do it first, and we lose some of it.**

Verified 17 Jul 2026 from vendor documentation retrieved and quoted in `bitsight.md`, `securityscorecard.md`, and `MethodologyDeepDive-3.0-Ebook_102325_SD.pdf`. Not from a secondary summary — an earlier internal summary of these same vendors carried four material errors, which is itself the argument for this rule.

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

##### The fork: breach-correlation vs governance-departure

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

##### Signal by signal

**DMARC — the divergence survives, on a stated and now-evidenced ground.** Bitsight's target variable is *publicly disclosed data breach*. DMARC's primary harm is **business email compromise**, which is a fraud loss, not a data breach — it typically triggers no disclosure obligation and so cannot appear in the training data. **A model tuned to predict disclosed breaches will systematically under-weight a signal whose main harm never produces one.** CPS 230 is an *operational risk* standard, not a data-breach standard; BEC sits inside our client's risk perimeter and outside Bitsight's target variable.

The loss-magnitude evidence (both government sources, verified 19 Jul 2026):

- **FBI IC3 2024 Annual Report:** BEC losses of **US$2.77 billion** across 21,442 complaints — the **second-highest category by dollar loss**, ~17% of all reported cybercrime loss, and **US$8.5 billion cumulatively 2022–2024**.
- **ASD/ACSC Annual Cyber Threat Report 2024–25:** BEC accounted for **15% of reported attacks**; in FY2023–24 self-reported BEC losses to ReportCyber averaged **over A$55,000 per confirmed incident**.

**The point is not merely that the losses are large — it is that they are large *and structurally invisible to a breach-trained model*.** IC3 ranks BEC second by dollar loss, yet BEC rarely appears in breach-disclosure datasets because it produces no disclosable breach. That is the precise mechanism by which Bitsight's 3% under-weights it, and it is why an *operational-risk* buyer (CPS 230) should not inherit a *breach-likelihood* platform's weight for this signal.

> **Open item 11 — advanced from *unevidenced* to *cited*.** The divergence is now *defended*, not merely *explained*, on two official government sources. Remaining: confirm the exact IC3/ACSC page references against the primary PDFs before client-facing use (search-derived figures, not yet read from source).

**Headers — we were wrong, and our own reasoning says so.** Bitsight rates web application headers **informational: zero impact on the rating.** §5.6.1 argues, correctly, that *"a header is a mitigation, not a vulnerability."* We reached Bitsight's conclusion and then weighted the signal at 20% anyway. There is no rescue argument. The reasoning and the external evidence converge, and against our own number.

**TLS — we under-weight our best-evidenced signal.** Bitsight 25%, UpGuard 17%; both rank it top-3. §5.6.1 calls TLS *"direct observation; protocol/cipher facts, not inference"* — the strongest evidentiary standing anything in the category has. 30% of Cyber Hygiene understates it on both our reasoning and theirs simultaneously, which is the one combination with no defence.

**CT — no external comparator exists.** Bitsight has no certificate-transparency vector. The closest analogue is UpGuard's **Attack Surface (11%)**, and CT is our only attack-surface signal — the only one that finds assets *we did not know to look for*. That argues its 15% is low, but the analogue is loose and this remains the least-anchored number in the table.

##### Revised Cyber Hygiene intra-weights

| Signal | d1 | **d2 (adopted)** | Basis for the change |
|---|---|---|---|
| **TLS** | 30% | **40%** | Two independent platforms rank it top-3; strongest evidentiary standing of any signal we collect |
| **DNS / DMARC** | 35% | **30%** | Stays far above Bitsight's 3% on the BEC/target-variable argument — but no longer *first*, which that argument cannot support |
| **CT** | 15% | **20%** | Absorbs part of the headers reduction; sole attack-surface signal, cf. UpGuard 11% |
| **Headers** | 20% | **10%** | Bitsight rates it zero; §5.6.1's own reasoning agrees |

**The ordering is the defensible claim; the exact values are not.** Per §5.6's sensitivity property — the same self-damping renormalisation applies here — a ±5 shift in any of these moves the overall score by roughly a point and crosses no band. **What must be defended is that TLS now outranks DMARC and that headers ranks last.** Arguing the precise numbers is arguing inside the noise; we will change them on request and show the client the score barely moves.

##### What this benchmark is not

**Three limits, stated so they are not discovered later.**

1. **The taxonomies do not map cleanly.** Bitsight's *Diligence* spans our Cyber Hygiene *and* part of our Incident History. Our `dns` bucket spans their SPF, DKIM and DMARC vectors. Every row above is an approximate alignment, not an identity.
2. **Their "empirical" is weaker than the word implies.** SecurityScorecard concedes in its own methodology that *"statistical power is limited by the amount of breach data that is publicly available"* and that **"as many as 60-89% of breaches go unreported."** Their weights are correlated against a partial, disclosure-biased sample — which skews to regulated and consumer-facing sectors, i.e. **exactly the bias we name in §7.3.** Better grounded than ours. Not authoritative over ours.
3. **A benchmark is not a validation.** Matching Bitsight would not make us right, and diverging does not make us wrong. This section exists so that every divergence is *deliberate and stated* rather than discovered by a client. That is the whole of the claim.

### 5.7 Two deliberate refusals

**No FAIR quantification.** FAIR quantifies risk in **financial terms** from frequency and magnitude distributions. OSINT gives us **neither** loss magnitude nor per-vendor event frequency. Attempting it would manufacture exactly the false precision that Finding A punishes. **We cite FAIR for the taxonomy discipline — keeping frequency and magnitude from collapsing into one number — and state plainly that v1 lacks the inputs.** Declining to use FAIR, with a reason, is a stronger methodological statement than using it badly.

**No score without confidence.** They are emitted together or not at all. There is no API path that returns a bare number.

### 5.8 Where AI is used — and where it is fenced

Three designated moments — the first two from the brief, the third an opt-in read layer built in v3.4:

| Moment | Task | Fence |
|---|---|---|
| **Adverse media** | Summarise which GDELT hits **actually matter** — the work a human would otherwise do by hand | Output is a **ranked candidate list with evidence links**, not a score |
| **Trust pages** | Classify unstructured pages into structured certifications + expiry | Output is a **claim record**, flagged self-reported |
| **Whole-record digest** (opt-in) | Summarise *what the sources actually found* — the hash-stamped observations + the published score roll-up — into a plain-English brief for a reviewer | **Read layer only:** describes the evidence, never computes or alters a score, never writes to the evidence store; returned **marked AI-generated**, **cites the `content_hash`es** it was built from, and is fed **only the already-collected, entity-level OSINT the system holds** (bounded per-receipt) |

> **`"the model said so"` is not reasonable grounds.** Under Finding A, the reasonable-grounds representation attaches to the **published score**. So: **AI output is evidence-linked and human-adjudicable, and never silently moves a score.** Conveniently, that is the architecture the evidence store already requires.

> **The digest is provider-agnostic and off by default.** It speaks the OpenAI-compatible `chat/completions` shape, so the operator points it at any provider they trust (OpenRouter, Groq, Google's OpenAI-compat surface) via three env vars — no provider SDK, no lock-in. With none set, the endpoint returns 503 and the feature is inert. This is the system's **single documented data-egress point**; what crosses it is bounded to the already-collected, entity-level OSINT the system holds — the hash-stamped observations + the score roll-up, capped per receipt (`source_assessment.md` → *Data egress*) — so the collectors' PII-minimisation is preserved at the boundary and nothing new is exposed. Because it reads the *record* rather than re-deriving it, it cannot become a shadow scorer — the number it describes was already fixed, upstream, by the deterministic engine.

### 5.9 The category catalogue — signals and their severities

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

### 5.10 Relationship to the subtractive-penalty (UpGuard-style) benchmark

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

> **Legality veto — recorded because the benchmark advice tripped over the project's own foundation.** The reviewed advice proposed closing the active-exposure gap with **Shodan/Censys free tiers** and OTI feeds (URLScan, OpenPhish, AlienVault OTX, AbuseIPDB, GreyNoise). **Rejected as written:** Censys's free tier ToS (verified live) *expressly prohibits commercial use of any kind* — the VirusTotal trap, and this is a commercial-platform candidate; the OTI feeds each carry an **unverified** commercial-use claim, and the rule is *verify the live ToS before clearing a source*. Logged as candidates requiring verification (`source_assessment.md`), not cleared. The gap is real; the shortcut is not lawful.

### 5.11 Assurity — the third axis, and the compliance gap

*Implemented in `backend/app/assurity.py` and `backend/app/compliance_gap.py`; configured under `assurity:` in `scoring.yaml`. Full derivation in [`scoring_model.md`](scoring_model.md) §8.*

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

### 5.12 Inherent and residual risk — the layer the buyer owns

*Implemented in `backend/app/residual_risk.py`. Full matrix in [`scoring_model.md`](scoring_model.md) §9.*

A posture score answers *"how strong is this vendor?"*. It cannot answer *"how much do **we** stand to lose if they fail?"* — that depends on what this buyer has given them, which no amount of outside-in collection can observe. So it is **declared, not inferred**, and the two combine into a deterministic 16-cell lookup.

Three properties are deliberate and each has a failure mode behind it:

- **`max(criticality, data_access_scope)`, never an average.** A low-criticality vendor with production-data access is not a medium-risk vendor. Averaging is how a real exposure gets diluted by an unrelated judgement.
- **Undeclared is not Low.** An unclassified relationship routes to the **deepest** assessment, not the shallowest. The vendors nobody has got round to classifying are disproportionately the ones nobody has looked at, and treating silence as *low* rewards exactly that.
- **A strong posture never reaches Low at high inherent exposure.** An A-grade vendor holding production data lands at Medium. They are still holding it, and the day their posture moves you find out how much was riding on it.

**Residual is recomputed on read and stored nowhere**, so it cannot drift from the two inputs it is derived from — both of which *are* stored. It is advisory: it states what the evidence and the declared exposure together support, and the client decides.

### 5.13 Peer benchmarking and the expectation gap

*Implemented in `backend/app/benchmarking/`, configured under `benchmarking:` in `benchmarks.yaml`, served under `/api/v2/suppliers/{ref}/…`. Full treatment in [`scoring_model.md`](scoring_model.md) §10.*

**`n` travels with every figure, and the refusal is the figure.** A percentile requires **n ≥ 30**, a quartile **n ≥ 8**, and below that the response states *insufficient peer data* with the actual `n`. Both floors are enforced **in code**, not only in YAML — a config edit may raise them and may not lower them. That is not paranoia: the superseded v1 module shipped `min_cohort_n: 1`, and *"make it 3 for the demo"* is exactly how a demo setting survives into production, where it is indistinguishable from a decision nobody made.

The cohort is a **widening ladder** — `sector + size + delivery model`, then `sector + size`, then `sector` — and **every rung it tried is published with that rung's `n`**, because "which peers?" is the only question anyone actually asks about a benchmark. **There is deliberately no rung meaning "every supplier ever assessed"**: a comparison against everything is not a peer group. When the ladder widens, the card says so on its face, because a comparison against a wider population is a weaker claim.

Two further honesty mechanisms. **Comparison reliability is published separately from confidence** — a well-evidenced supplier can sit in a poorly-supported peer group, and those are different facts. And **per-domain discrimination is stated on every row**: a domain where every peer scores 100 cannot rank anybody, so presenting a rank among identical values would manufacture signal from a constant.

**The expectation gap** (`Posture − E[Posture ∣ cohort]`) is the sentence this subsystem exists to produce:

> *"Posture 68. Cohort median (n=14): 87. This vendor sits 19 points below its peer group. The gap is driven by dmarc (absent) — 12 of 14 peers are not in this band."*

A buyer handed `−19` has a fact. A buyer handed `−19, driven by DMARC, which 12 of 14 of their own peers publish` has a **remediation**, and one they can put to the vendor with a count from the vendor's own peer group attached rather than an opinion of ours. The drivers are **ranked, not a decomposition**, and the response says so: since E7a what a finding costs depends on what else was charged alongside it, so per-signal attributions do not sum to the gap and no arrangement of them can be made to.

**The cohort is disputable; the placement is not.** Cohort, snapshot and placement are deterministic lookups over the inputs and carry no independent judgement. Dispute an *input*. Snapshots are frozen when published — recomputing history against today's population would attribute the cohort's movement to the supplier — and are member-bearing only internally; every tenant-facing path calls `.public()`, which structurally cannot carry peer refs.

---

## 6. System Flow

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

## 7. Limitations

Stated here so they cannot be discovered later. Per the brief: *"Say what a signal does and does not tell you."*

### 7.1 Structural — these do not close with more sources

1. **~10 of 27 criteria are unobservable to any lawful external observer.** Access controls, security monitoring, data handling, insurance, change management, contract terms. **No source register closes this.**
2. **Absence of evidence is the default state of a clean small vendor and of a badly-run obscure one.** We cannot distinguish them. We can only report low confidence honestly.
3. **Perimeter ≠ posture.** A perfect header score is fully compatible with a catastrophic internal posture. Cyber Hygiene & Technical — the most richly-fed category, and so the one carrying the most signals — measures **what a stranger can see**, which is a proxy, and is labelled as one.
4. **Self-reported is self-reported.** Trust pages are the vendor talking about itself — the exact input the brief is trying to move away from. Included at 0.7 observability for the **fourth-party data**, not for the certification claims.

### 7.2 Known weaknesses (current model, v4)

| Weakness | Impact | Status |
|---|---|---|
| **No AU sanctions (DFAT)** | Gate runs on US list only | **Blocking — licence query pending** |
| **No ESG** | Category held (emits nothing) | Blocking — Modern Slavery licence pending |
| **FOCI / Provenance absent** | NIST SP 1326 category uncovered | Roadmap — has a **2028 regulatory deadline** |
| **Business Stability = standing, not financials** | Entity standing only (GLEIF/Wikidata/RDAP resolve globally); no distress/litigation data | Structural — no free source for the financial half |
| **Entity resolution** | The accuracy ceiling of the whole system | Mitigated by gates + confidence, not solved |
| **GDELT noise** | Coverage tracks **newsworthiness, not risk** | Held / AI-adjudicated, not scored |
| **crt.sh unstated ToS** | Low residual risk | Accepted, logged; Cert Spotter fallback |

### 7.3 The bias that must be named

**Coverage tracks company size, not company risk.** A large consumer brand generates more breach records, more adverse media and more filings than a smaller, riskier vendor. Naively, **the model would score big vendors as riskier because more is known about them.**

The confidence mechanism (§5.4) is the mitigation — but it is a mitigation, not a cure, and any client reading a scorecard should be told this in plain language on the scorecard itself.

---

## 8. Deliverables

| # | Deliverable | Artefact | Status |
|---|---|---|---|
| **1** | Research methodology | `research_doc.md` + `source_assessment.md` + this §3 + `legal_and_standards_basis.md` | **Complete** |
| **2** | Working PoC | React + FastAPI app, named vendors, SSE, evidence store | **Built** |
| **3** | v1 scoring model | This §5 + `scoring.yaml` (**v5.2.0 — penalty posture, 5 scored + 2 context + 5 held**) + `scoring_model.md` | **Implemented + tested** (~1,120 backend tests, incl. a frozen regression corpus) |
| **4** | Sample output | Client-ready scorecard (the app's Scorecard view), every deduction carrying a plain-English reason | **Built** |
| **5** | Roadmap | `roadmap.md` | **Complete** |

### 8.3 Roadmap headline

**FOCI is the highest-value next item** — not an apology. The SOCI Enhanced CIRMP Rules 2026 (registered 9 Jun 2026) make FOCI assessment of major suppliers **legally mandatory** for critical infrastructure operators with a **~mid-2028 deadline**. That is a named buyer with a regulatory clock. Blocked only on registry terms.

**Fourth-party concentration is the sharpest commercial wedge.** CPS 230 ¶48 makes it a regulated obligation; DORA's dry run found **only 6.5% of ~1,000 EU firms passed all 116 data-quality checks**, most commonly failing on **missing subcontractor information** — a documented, quantified market failure in exactly the data we extract for free from public DPAs. Discovering that six vendors share one subprocessor is a finding a client **cannot obtain any other way**.

---

## 9. Open items

Carried from `source_assessment.md` and `legal_and_standards_basis.md`, re-prioritised by this design:

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

## 10. Attribution obligations carried into the product

**These are UI requirements, not footnotes to add later.**

- **NVD** — must display prominently, verbatim: *"This product uses the NVD API but is not endorsed or certified by the NVD."*
- **HIBP** — CC BY 4.0 attribution + link to `haveibeenpwned.com` where the data appears.
- **GDELT** — citation + link to `gdeltproject.org`.

---

## References

- `docs/source_assessment.md` — per-source legality, reliability, limits
- `docs/legal_and_standards_basis.md` — model-level legal basis
- `docs/an_example_risk_scoring_System.md` — ⚠ **a demo product's editable placeholder, NOT authoritative** (opens *"Not sure how genuine it is"* / *"Adjust weights…"*). Earlier mistakenly used as the weight anchor; that claim is withdrawn (§5.6). Usable only as a rough inventory of *plausible criteria*, never as a source of weights
- `docs/source_mappping.md` — category structure origin
- `docs/OSINT_TPRM_Intern_Brief.md` — the brief

**Competitor methodologies — primary sources for §5.6.2** (vendor documentation, retrieved 17 Jul 2026; quoted, not summarised):

- `docs/bitsight.md` — risk category & vector weights, rating scale, normalization, decay
- `docs/securityscorecard.md` — Scoring 3.0 changeover, breach-likelihood table, size normalization
- `docs/MethodologyDeepDive-3.0-Ebook_102325_SD.pdf` — SecurityScorecard, *A Deep Dive in Scoring Methodology* (2025). **Limitations p.33; Validation p.32 — source of the 60-89% unreported-breach figure**
- NIST SP 1326 — `docs/NIST.SP.1326.pdf`
- APRA CPS 230 — ⚠ repo PDF superseded, see §4.3
- ISO/IEC 27001:2022 — `docs/ISO_IEC-270012022-ed.3.pdf`
- French Compliance Society TPRM — `docs/TPRM_digital_version_anglaise.pdf`

**BEC loss-magnitude — §5.6.2 open item 11** (verified 19 Jul 2026; confirm page refs against primary PDFs before client use)
- FBI IC3 *2024 Internet Crime Report* — BEC US$2.77bn / 21,442 complaints — https://www.ic3.gov/AnnualReport/Reports/2024_IC3Report.pdf
- ASD/ACSC *Annual Cyber Threat Report 2024–25* — BEC 15% of attacks; >A$55k avg/incident — https://www.cyber.gov.au/about-us/view-all-content/reports-and-statistics/annual-cyber-threat-report-2024-2025
