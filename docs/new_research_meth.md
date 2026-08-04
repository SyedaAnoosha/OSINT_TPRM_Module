# The Revised Methodology — context-aware vendor risk scoring, specified

### Part II of *Should External Security Signals Be Interpreted Differently by Company Type?*

**Continues:** [context-aware-vendor-risk-scoring-study.md](context-aware-vendor-risk-scoring-study.md) §§1–4
**Assessed system:** `scoring.yaml` v4.2.0 (penalty-subtractive posture) · `benchmarks.yaml` v1.0.0 · [docs/methodology.md](docs/methodology.md) §5
**Date:** July 2026
**Status:** research recommendation, not a shipped model. Nothing here is in the engine yet.

---

## How to read this document

Part I answered the research question: *does the importance of a security signal change with the vendor's age, revenue, headcount, or industry?* The answer was **no for probability, yes for expectation, and yes for consequence** — three different adjustments that must live in three different places.

Part II is the engineering consequence of that answer. It contains the deliverables Part I did not reach:

| § | Deliverable (from `new_req.md`) | What it gives you |
|---|---|---|
| **5** | Commercial platform comparison | What the eight named platforms actually do about company context |
| **6** | Signal classification matrix | All 35 signals, one row each, fully populated |
| **7** | Critique of the current methodology | Strengths credited, then eleven defects, ranked |
| **8** | Comparison of adjustment approaches | Twelve candidate mechanisms scored on six axes |
| **9** | The revised model | Complete mathematics, every symbol defined |
| **10** | Tiered recommendations | Strongly recommended / optional / refused, with evidence, cost, bias and gaming for each |
| **11** | Migration plan | Five phases against your actual config files and frozen corpus |
| **12** | Final answer to deliverable 9 | Which component each firmographic is allowed to touch |
| **13** | References | |

**One framing note before the critique.** The system under review is unusually honest for its class. It refuses to publish a score it cannot evidence, it stores evidence before it scores, it fails the loader if a penalising band has no plain-English reason, it refuses to score natural persons, and it keeps a frozen regression corpus that has already falsified one of its own claims. Those are not common properties. The defects below are real and several are serious, but they are the defects of a careful model, not a careless one, and the critique should be read that way.

---

# 5. What the commercial platforms actually do

`new_req.md` asks, for each platform: do they change the interpretation of findings based on company characteristics; do they use peer benchmarking; do they normalize by company size; do they disclose context-aware scoring; and is benchmarking separate from scoring.

The honest summary first: **every platform that publishes a technical rating normalizes by measured digital footprint, and none of them applies a revenue, headcount, or company-age multiplier to a technical finding's severity.** Firmographics appear in exactly two places across the whole market — peer-group definition, and loss-magnitude estimation. That convergence is itself evidence, because these are competitors who solved the problem independently.

### 5.1 Platform-by-platform

#### Bitsight

| Question | Answer |
|---|---|
| Context-changes interpretation? | **By size of digital footprint, yes. By firmographics, no.** |
| Peer benchmarking? | Yes — industry and peer-group comparison is a headline feature |
| Normalizes by size? | **Yes, explicitly and by design** |
| Discloses it? | Yes, in public knowledge-base documentation |
| Benchmarking separate from scoring? | Yes — the rating is absolute; peer comparison is a view over it |

Bitsight states plainly that "large companies will typically have more findings than smaller companies" and that ratings are normalized by organization size so as not to "unfairly penalize large companies," comparing organizations "using applicable notions of size — e.g. employee count, magnitude of digital footprint, overall count of observations."

Two further design choices matter for your model. First, risk vectors are **weighted by demonstrated correlation to breach**, not by expert opinion — which is why HTTP security headers carry near-zero rating impact in their model while yours scores them Low. Second, security incidents produce a rating adjustment "that reflects the severity of the incident and the size of the organization," and that adjustment **decays over time** — the same shape as your NIST SP 1326 age decay, arrived at independently.

Their validation is the thing worth copying: 27,458 companies over two years against 2,671 breach events, showing organizations rated 700+ at under 1% breach probability against nearly 3% below 500. That is the artefact that makes a rating defensible. Note what it requires — an absolute, comparable scale. A score whose scale varies with the subject's revenue cannot produce that chart.

#### SecurityScorecard

| Question | Answer |
|---|---|
| Context-changes interpretation? | **Yes — footprint size is in the arithmetic, as a denominator** |
| Peer benchmarking? | Yes |
| Normalizes by size? | **Yes — it is the core of the scoring function** |
| Discloses it? | Yes, including recalibration notices in advance |
| Benchmarking separate from scoring? | Partly — the z-score is itself relative to a size-matched population |

SecurityScorecard's model is a modified z-score in which, in their words, "z = 1 when the number of findings equals the mean for organizations with the same size Digital Footprint." Periodic recalibrations exist explicitly "to normalize scoring between organizations of different sizes, with differing digital footprints," and the company publishes forward-dated recalibration notices (February 2026, May 2026, August 2026 in the current cycle) so customers can anticipate score movement.

This is the most aggressive normalization in the market and it comes with a cost you should note: because the reference population moves, a vendor's score can change without the vendor changing. That is the price of a relative scale, and it is a real argument for the **absolute posture + separate expectation gap** architecture recommended in §9 rather than a fully relative one.

#### RiskRecon (Mastercard)

| Question | Answer |
|---|---|
| Context-changes interpretation? | **Yes — by asset value, which is the most sophisticated approach in the market** |
| Peer benchmarking? | Yes, and industry benchmarks anchor the scale itself |
| Normalizes by size? | Yes — issue rates per high-value system |
| Discloses it? | Yes, including a published statement of compliance with the U.S. Chamber principles |
| Benchmarking separate from scoring? | **No — industry benchmarks calibrate the scale, then everyone is scored on it identically** |

RiskRecon's contribution is the **asset-value dimension**: an issue is rated in the context of both its severity and the value of the system it sits on, so a weak cipher on a marketing microsite and the same cipher on a system handling regulated data are not the same finding. This is a *measured* property of the asset, inferred from what the system does and what data it appears to handle — not a firmographic property of the company.

Their industry work is the cleanest published evidence in the whole study: large banks average 0.5 critical-severity issues per 100 high-value internet-facing systems; universities average 6.3 — a greater than 12× spread. RiskRecon used that spread to **anchor the scale** (banking as the "good" anchor, universities as the "poor" anchor, companies distributed across it with a Rayleigh distribution) and then scored every company on the same scale.

**That is precisely the architecture this study recommends.** Industry determined what the numbers mean. It did not multiply anyone's findings.

#### Black Kite

| Question | Answer |
|---|---|
| Context-changes interpretation? | **Split: no in the technical rating, heavily yes in the financial-impact rating** |
| Peer benchmarking? | Yes |
| Normalizes by size? | In the technical rating, by footprint; in the FAIR model, firmographics are primary inputs |
| Discloses it? | Yes — the FAIR methodology is openly named |
| Benchmarking separate from scoring? | Yes |

Black Kite is the most architecturally instructive platform for your purposes because it publishes **three separate ratings rather than one blended number**: a technical letter grade, a FAIR-based financial impact figure in dollars, and a compliance correlation showing how observed findings map to NIST, ISO 27001, PCI DSS and GDPR control expectations.

Look at where the firmographics go. Revenue, employee count and record volume drive the **FAIR loss-magnitude estimate** — the dollar figure — and they do not drive the technical grade. And the "your findings contradict your claimed compliance posture" question gets its own output rather than being folded into severity.

This is the same decomposition §9 recommends, shipped commercially. It is the strongest available evidence that a multi-output architecture is viable rather than merely tidy.

#### UpGuard

| Question | Answer |
|---|---|
| Context-changes interpretation? | Limited — severity weights are largely uniform |
| Peer benchmarking? | Yes, industry comparison |
| Normalizes by size? | Partially; less aggressively than Bitsight or SecurityScorecard |
| Discloses it? | Category weights and severity bands are published |
| Benchmarking separate from scoring? | Yes |

UpGuard is the closest published analogue to your current model — a subtractive score across weighted categories — and it is the reason your `docs/methodology.md` §5.10 cross-checks against it. The relevant lesson is the one your own §5.6 already records: a subtractive model with published weights invites the *"why is this category 31%?"* question, and there is no authoritative answer to it. Your penalty model dissolved that question, and §7.4 below explains why the dissolution was less complete than the documentation claims.

#### Panorays

| Question | Answer |
|---|---|
| Context-changes interpretation? | **Yes, via relationship context — buyer-side, not vendor-side** |
| Peer benchmarking? | Limited |
| Normalizes by size? | Not prominently disclosed |
| Discloses it? | Partially |
| Benchmarking separate from scoring? | Yes |

Panorays combines external attack-surface findings with questionnaire responses and — the relevant part — **business relationship context**: what the vendor does for *you*, what data they hold of *yours*, how deep the integration runs. That context drives assessment depth and the criticality rating, not the technical severity of a finding.

This is the Impact/Tier dimension of §9.6, and note whose firmographics it uses: **the buyer's and the engagement's, not the vendor's.** Panorays is also a signatory to the U.S. Chamber's Principles for Fair and Accurate Security Ratings.

#### OneTrust and ProcessUnity

| Question | Answer (both) |
|---|---|
| Context-changes interpretation? | **Yes, but at the tiering layer, not the signal layer** |
| Peer benchmarking? | Not a primary feature |
| Normalizes by size? | Not applicable — they do not generate the external technical rating |
| Discloses it? | Inherent-risk models are configurable and visible to the customer |
| Benchmarking separate from scoring? | Not applicable |

These are TPRM governance platforms rather than security-rating providers. They typically ingest a rating from Bitsight, SecurityScorecard or similar, and their own contribution is **inherent risk tiering**: a scoping questionnaire — data classes, criticality, spend, regulatory exposure, integration depth — that determines *how much diligence the vendor gets*, how often they are reassessed, and what contractual controls apply.

The pattern is important and it is unanimous across the two: **company context changes the depth of assessment and the required control set. It does not change what a given technical finding means.**

### 5.2 What the market convergence tells you

| Practice | Bitsight | SSC | RiskRecon | Black Kite | UpGuard | Panorays | OneTrust | ProcessUnity |
|---|---|---|---|---|---|---|---|---|
| Normalizes findings by measured footprint | ✅ | ✅✅ | ✅ | ✅ | ~ | ? | n/a | n/a |
| Revenue/headcount multiplier on technical severity | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Industry used to define peer group | ✅ | ✅ | ✅✅ | ✅ | ✅ | ~ | ~ | ~ |
| Industry used to change severity arithmetic | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Firmographics drive loss magnitude | ~ | ~ | ✅ | ✅✅ | ❌ | ✅ | ✅ | ✅ |
| Buyer-side context drives tier/depth | ~ | ~ | ~ | ~ | ~ | ✅✅ | ✅✅ | ✅✅ |
| Incident history decays over time | ✅ | ✅ | ✅ | ✅ | ✅ | ? | n/a | n/a |
| Published breach-outcome validation | ✅✅ | ✅ | ~ | ~ | ~ | ❌ | n/a | n/a |

*✅✅ = central design feature · ✅ = present and disclosed · ~ = partial or undisclosed · ❌ = absent · ? = not publicly documented*

**Two rows carry the whole argument.** Row 1 is unanimous and row 2 is unanimously empty. Eight platforms, competing, with access to outcome data none of them share, all normalize by footprint and none of them applies a firmographic multiplier to technical severity. Your current model does the opposite on both counts: it has no denominator (§7.1) and it does promote severity by industry (§7.5).

**The caveat these platforms carry, and you should too.** Berg, Kölbel and Rigobon found average pairwise correlation across major ESG rating providers of roughly 0.53–0.56, versus over 0.99 between Moody's and S&P credit ratings — driven not by data scarcity but by divergence in indicator selection, weighting and scope. Security ratings sit somewhere between those poles and nobody knows exactly where. Each unvalidated context adjustment you add moves you toward the ESG end.

---

# 6. Signal Classification Matrix

All 35 signals, one row each. Populated from the per-signal analysis in Part I §4.

**Column definitions**

- **Class** — P = prevalence (count scales with asset inventory) · B = binary org-level policy · C = consequence/assurance · D = denominator/discovery input
- **Age sens.** — should the *vendor's founding date or domain age* change how this finding is scored in Posture?
- **Rev/size sens.** — should revenue, headcount or market cap change it?
- **Exposure sens.** — should *measured internet-facing footprint* change it? (This is the column that is mostly ✅, and it is not a firmographic.)
- **Industry sens.** — should industry change it, and where?
- **Reg. sens.** — does regulatory status change the expectation?
- **Recommended context adjustment** — the operative instruction
- **Evidence** — strength of published support for that instruction

### 6.1 Cyber Hygiene

| Signal | Class | Age sens. | Rev/size sens. | Exposure sens. | Industry sens. | Reg. sens. | Recommended context adjustment | Evidence |
|---|---|---|---|---|---|---|---|---|
| **SPF** | B (+P across portfolio) | ❌ | ❌ | Per-domain only | Benchmark only | Moderate — PCI, sector email rules | **None in Posture.** Score record validity identically. Report sending-service count as context, not penalty | Moderate |
| **DKIM** | B | ❌ | ❌ | ❌ | Benchmark only | Low | **None.** Low weight for absence (poor external observability); moderate for confirmed weak keys. Treat observability gap as Confidence | Weak–Moderate |
| **DMARC** | B | ❌ | ❌ | ❌ | **Benchmark: strong** | **High** — the clearest Compliance Gap candidate | **None in Posture.** Graduated bands (reject > quarantine > none > absent) identically for all. Expectation gap and Compliance Gap carry the "$5B bank has no excuse" signal | Strong (adoption), Moderate (breach link) |
| **DNSSEC** | B | ❌ | ❌ | ❌ | Benchmark only | Low (gov/AU-fed contexts higher) | **None. Downgrade to Informational/Low; prefer scoring presence as a positive over absence as a penalty** | **Weak — state this in the report** |
| **CAA** | B | ❌ | ❌ | ❌ | Benchmark only | Very low | **None. Low or Informational.** No published breach correlation | **Weak** |
| **TLS version** | **P** | ❌ | ❌ | **✅ Mandatory** | Benchmark + Compliance Gap | **High** — PCI DSS deadline, NIST SP 800-52r2, RFC 8996 | **Exposure denominator required.** Identical severity. Add *dispersion* (share of hosts non-conforming) as a separate derived signal. Route regulatory expectation to Compliance Gap | Strong (standards), Moderate (exploitation) |
| **Cipher suites** | P | ❌ | ❌ | **✅ Mandatory** | Benchmark only | Moderate | **Normalize.** Split broken (RC4, EXPORT, NULL) from deprecated-but-unbroken — most models over-penalize the latter | Moderate |
| **Certificate validity** | **P** | ❌ | ❌ | **✅ Mandatory — highest priority** | Benchmark only | Moderate | **Normalize. This is the single most size-biased signal in the current model.** Split expired / hostname-mismatch / self-signed-on-internal — one coarse signal today | Strong (as hygiene proxy) |
| **HSTS** | P | ❌ | ❌ | ✅ | Benchmark only | Low–Moderate | **Normalize, and weight by asset function** (auth/payment endpoints ≫ static marketing hosts) | Weak–Moderate |
| **CSP** | P | ❌ | ❌ | ✅ | Higher for e-commerce (PCI 4.0 scripts) | Moderate in payment contexts | **Normalize; score policy strength, not mere presence.** A `unsafe-inline` CSP is near-worthless | Moderate (payment), Weak (general) |
| **X-Frame-Options** | P | ❌ | ❌ | ✅ | ❌ | ❌ | **Low/Informational. Suppress entirely when CSP `frame-ancestors` is present** — otherwise you double-count one control | **Weak** |
| **security.txt** | B | ❌ | ❌ | ❌ | Slightly higher for tech/SaaS | Moderate (BOD 20-01 scope, EU CRA) | **Informational-to-Low, positive-only.** Guard actively against weight drift: ease of measurement is not evidence of importance | **Speculative** |

### 6.2 Digital Footprint

| Signal | Class | Age sens. | Rev/size sens. | Exposure sens. | Industry sens. | Reg. sens. | Recommended context adjustment | Evidence |
|---|---|---|---|---|---|---|---|---|
| **Number of subdomains** | **D** | ❌ | ❌ | Is the denominator | ❌ | ❌ | **Not a penalised signal. Use as the exposure denominator `D`.** If you want risk from the estate, score *dangling/takeover-vulnerable* subdomains and normalize those | Strong (that raw count is a poor risk signal) |
| **CT history** | D | ❌ | ❌ | Discovery input | ❌ | ❌ | **Not independently scored.** Discovery only, always liveness-validated before entering `D` | Strong (methodologically) |
| **Shadow assets** | P | ❌ | ❌ | **✅ Ratio form essential** | ❌ | ❌ | **Score as ratio `shadow / total discovered`. Do not additionally multiply by size or age** — that would double-count the same effect | Strong (conceptual), Moderate (published correlation) |

### 6.3 Breach & Compromise

| Signal | Class | Age sens. | Rev/size sens. | Exposure sens. | Industry sens. | Reg. sens. | Recommended context adjustment | Evidence |
|---|---|---|---|---|---|---|---|---|
| **Public breach history** | C (legit Posture component) | ❌ (company age irrelevant; **event** age decays) | Magnitude-relative-to-scale only | ~ | Benchmark + Impact | Disclosure regime → **Confidence** | **Slightly adjusted** — by recency, recurrence, root-cause repetition, and magnitude relative to scale. **Not** by company age, revenue, or claimed maturity | Strong |
| **Exposed data types** | **C — pure impact** | ❌ | ❌ | ❌ | ✅ in Impact | ✅ in Impact | **Zero effect on Posture. Heavily adjusted in Impact/Tier** by data sensitivity and the buyer's engagement | Strong |
| **KEV** | P (absolute dominates at low counts) | ❌ | ❌ | ✅ blended with absolute count | ❌ | **High** — BOD 22-01 binds federal; CISA deadline is a public expectation | **Full severity for everyone, no leniency for anyone. Add days-past-CISA-deadline as a multiplier.** The one signal where uniformity is not a compromise but the correct answer | Strong |
| **CVEs** | P | ❌ | ❌ | ✅ | ❌ | ❌ | **Normalize and heavily down-weight relative to KEV/EPSS.** Consider not scoring banner-inferred CVEs at all unless confirmable | Strong (that raw counts predict poorly) |
| **CVSS** | Modifier | ❌ | ❌ | ❌ | ❌ | ❌ | **Descriptor, not primary severity driver.** A CVSS 7+ strategy needs ~50.7% of CVEs remediated for 74.6% coverage at ~6% efficiency | Strong (on its limitations) |
| **EPSS** | Modifier | ❌ | ❌ | ❌ | ❌ | ❌ | **Adopt as a primary severity input.** EPSS v4 reaches comparable coverage at ~6% effort and ~47% efficiency. **Highest-value accuracy improvement available to this framework** | Strong |

### 6.4 Governance

| Signal | Class | Age sens. | Rev/size sens. | Exposure sens. | Industry sens. | Reg. sens. | Recommended context adjustment | Evidence |
|---|---|---|---|---|---|---|---|---|
| **Published security program** | C → **Assurity** | Slight | Slight (audit budget) | ❌ | Higher for SaaS/tech | Moderate | **Move out of Posture into Assurity. Positive-only — never penalize absence** | **Speculative** |
| **Vulnerability disclosure policy** | B, Assurity-leaning | ❌ | ❌ | ❌ | Higher for tech/gov suppliers | **High for BOD 20-01 / EU CRA scope** | **Positive-only score; route the regulatory expectation to Compliance Gap for entities actually in scope** | Moderate |
| **Security contact** | B | ❌ | ❌ | ❌ | ❌ | Low | **Informational. Merge with security.txt** — three signals measuring one fact silently triple-weights Governance under flat accumulation | Weak |

### 6.5 Business

| Signal | Class | Age sens. | Rev/size sens. | Exposure sens. | Industry sens. | Reg. sens. | Recommended context adjustment | Evidence |
|---|---|---|---|---|---|---|---|---|
| **Domain age** | C | n/a (is the characteristic) | ❌ | ❌ | ❌ | ❌ | **Not scored in Posture. Route to Entity Verification gate** — it is a fraud/impersonation signal, not a security-posture signal | Weak (security), Moderate (fraud) |
| **Domain registration quality** | B | ❌ | ❌ | ❌ | ❌ | Low | **Identical, Low–Medium. Score registrar lock and expiry buffer. Do not score privacy-protected WHOIS as a negative** — it is the GDPR-era default, and penalizing it is geographic bias in disguise | Weak–Moderate |
| **Legal entity status** | C | ❌ | ❌ | ❌ | ❌ | ❌ | **Not in Posture.** Counterparty diligence / Entity Verification | N/A for security |
| **Company age** | C | n/a (is the characteristic) | ❌ | ❌ | ❌ | ❌ | **Not in Posture. Benchmarking covariate and Bayesian prior only.** No authoritative source scores by founding date — **state the absence rather than filling it with intuition** | **Absent** |
| **Company continuity** | C | ❌ | ❌ | ❌ | ❌ | ❌ | **Not in Posture.** Separate Continuity dimension on the vendor profile | Weak |

### 6.6 Compliance

| Signal | Class | Age sens. | Rev/size sens. | Exposure sens. | Industry sens. | Reg. sens. | Recommended context adjustment | Evidence |
|---|---|---|---|---|---|---|---|---|
| **ISO certifications** | **C → Assurity** | Slight | **Strong (audit budget)** | ❌ | Strong | Strong | **Quarantine in Assurity. Positive presence only; never penalize absence in Posture. Record scope and expiry** — an ISO 27001 certificate whose SoA excludes the assessed product is not evidence about that product | Weak (breach), Strong (procurement) |
| **SOC reports** | C → Assurity | Slight | **Strong (audit budget)** | ❌ | Strong | Strong | **Quarantine in Assurity, positive-only.** Penalizing absence is a tax on audit budget — the most demographically biased element you could include | Weak (breach) |
| **Regulatory disclosures** | C → Posture via breach mechanism | ❌ | **Availability bias — public vs private** | ❌ | Strong (HHS OCR, financial regulators) | Definitional | **Identical in Posture; adjust Confidence by disclosure regime. Never treat "no disclosed breaches" as equivalent evidence across regimes** | **Strong** for the bias; correction rarely implemented |

### 6.7 Reputation

| Signal | Class | Age sens. | Rev/size sens. | Exposure sens. | Industry sens. | Reg. sens. | Recommended context adjustment | Evidence |
|---|---|---|---|---|---|---|---|---|
| **Regulatory enforcement** | C (+ Posture where security-related) | ❌ | **Selection bias — regulators pursue large visible targets** | ❌ | Strong (finance, health, telecom supervised) | Definitional | **Identical severity where the action concerns security controls. Adjust Confidence for enforcement-regime exposure. Score adjudicated outcomes only** | Moderate |
| **Government investigations** | C | ❌ | Same bias, amplified | ❌ | Strong | Definitional | **Do not score in Posture. Disclose as context.** Scoring allegations creates defamation exposure and likely fails the Chamber Principles' "empirical, data-driven" test | **Weak** |
| **Verified adverse media** | C | ❌ | **The most size-confounded signal in the catalogue** | ❌ | B2C ≫ B2B for identical events | ❌ | **Not in Posture.** Separate Reputational Exposure view, normalized by baseline media volume, human-verified. Any raw count penalizes fame | **Weak — highest false-positive and dispute risk of any signal listed** |

### 6.8 Reading the matrix

Count the columns:

- **Age sensitive: 0 of 35.** Not one signal in the catalogue justifies a company-age adjustment in Posture. Company age and domain age appear only as the characteristics themselves, and both are routed out of Posture entirely.
- **Revenue/headcount sensitive in Posture: 0 of 35.** Revenue appears four times — three as a *bias to correct* (ISO/SOC audit budget, enforcement selection, adverse-media volume) and once as `magnitude relative to scale` within breach history, which is a ratio, not a multiplier.
- **Exposure sensitive: 10 of 35, and all 10 are mandatory.** Every Class-P signal. This is the real answer to "should size affect scoring" — measured exposure, as a denominator, in the direction that *removes* a bias rather than adding one.
- **Industry sensitive: 12 of 35, and in every case the destination is benchmarking, Compliance Gap, or Impact — never severity.**
- **Signals that should leave Posture altogether: 11.** Exposed data types, published security program, domain age, legal entity status, company age, company continuity, ISO, SOC, government investigations, adverse media, and raw subdomain count.

---

# 7. Critique of the current methodology

Against `scoring.yaml` v4.2.0 and `docs/methodology.md` §5.

## 7.0 What is genuinely right, and should survive the migration

State this first, because the list below is long and the reader should know what is not in dispute.

1. **Evidence store before scoring, every arrow reversible.** This is the property that makes disputes survivable. Most commercial platforms cannot reproduce a score from twelve months ago. Keep it exactly as is.
2. **The loader refuses to start if a penalising band has no plain-English reason — and refuses if a reason survives for a deleted band.** A bidirectional guard against explanation drift. This is better practice than any platform in §5 publicly documents.
3. **§5.3.2 — config that scores nothing must not look like config that scores something.** Four inert keys were found and closed structurally rather than individually. Keep this rule and apply it to everything §9 adds.
4. **The Ghost as a concept.** "A vendor cannot look strong simply by being invisible" is correct and rare. §7.6 attacks the *cliff*, not the concept.
5. **Gates over grades for sanctions.** Refusing to let a machine make a criminal accusation via a letter grade is right, and the recall-tuned matching with manual clearing is the correct inversion.
6. **The frozen corpus, which has already falsified one of your own claims** (the three-source synthetic probe on Ghost frequency). A calibration harness that can prove you wrong is worth more than one that confirms you.
7. **`excluded_signals` — refusals recorded, not silently dropped.** Executive brand risk, PEP links, inferred demographics. Correct on law and on ethics, and documenting the refusal is what makes it a position rather than an omission.
8. **`benchmarks.yaml` shipping `expected_posture: {}` empty rather than inventing sector targets.** The right answer, and the loader guard requiring a `basis:` for any number is the right enforcement.

Now the defects, ranked by how much they distort the output.

## 7.1 There is no exposure denominator — the model measures size, not hygiene

**Severity: critical. Fix first.**

Ten of the 35 signals are prevalence-class. All ten are counted absolutely.

Worked example against your actual configuration. Two vendors, certificate findings only, `cert_validity` never decays (`modifiers.age.never_decays`), and an expired production cert is Critical (−40) with `critical_ceiling.auto_signals: [cert_validity]`:

| | Vendor A | Vendor B |
|---|---|---|
| Hosts serving TLS | 4 | 900 |
| Expired production certs | 2 | 9 |
| **Failure rate** | **50%** | **1%** |
| Collapsed penalty (worst-of, per §5.3) | 40 | 40 |
| Ceiling fires | Yes | Yes |
| **Published posture** | **≤49** | **≤49** |

Two things are wrong here and they pull in opposite directions, which is why the defect is easy to miss.

The **worst-of collapse partially masks the absolute-counting bias** — both vendors collapse to one −40, so the 2-vs-9 difference never enters the arithmetic. That is accidental protection, not design, and it fails the moment a category holds signals that do not collapse together. It also throws away real information: 9 expired certs on 900 hosts and 1 expired cert on 900 hosts are genuinely different, and the model cannot tell them apart.

Meanwhile the **rate difference is invisible**. Vendor B manages certificates fifty times better than Vendor A and receives an identical published posture. Under `aggregation: weakest_link` (`vendor_posture = min(asset_posture)`) the position gets worse, because a 900-host vendor has 225× more chances to own the worst asset. **Absolute counting plus weakest-link aggregation is a double size penalty**, and neither is disclosed as one.

Both major raters solved this a decade ago and say so publicly (§5.1). The fix is §9.2, and note its direction: **it removes an existing undisclosed bias against large vendors. It is not leniency, and it is not the firmographic adjustment the research question asked about.**

## 7.2 Linear subtraction floors, and loses all resolution exactly where decisions are hardest

**Severity: high.**

`overall_posture = 100 − (Σ category penalties, each capped at 100) / 4`.

Posture reaches 0 at 400 total penalty. With Critical = −40, that is **ten criticals** across the estate — but each category caps at 100, so a category saturates at **2.5 criticals**. Consequences:

**Within a saturated category, further findings are free.** A vendor at 100 penalty in Cyber Hygiene can acquire unlimited additional hygiene failures at zero cost. That is a perverse incentive with the arrow pointing exactly the wrong way: the vendors with the worst hygiene have the least reason to fix any of it.

**Resolution collapses in the bottom quartile.** Vendors at 400 and 700 total penalty both publish as 0. Every vendor in the F band is indistinguishable, which is the band where a procurement team most needs to rank remediation and choose between two bad options.

**The divisor is doing weighting work it is not credited for.** `docs/methodology.md` §5.1 is admirably honest that 7 (the plain mean of seven categories) graded every benchmark vendor A, including one carrying 13 KEV matches, and that 4 was chosen from a sweep because it separated the corpus. That is calibration against a five-vendor convenience sample. It is also a **global severity multiplier of 1.75× relative to the algebraic mean**, applied to every vendor, tuned on five data points. Compare Bitsight's 27,458 companies against 2,671 breach events.

**And the divisor is coupled to the category count.** Add an eighth category — five are already designed and held in `held_roadmap` — and either the divisor changes and every historical score moves, or it does not and the model silently gets harsher. Neither is acceptable in a system that publishes trend lines.

The fix is §9.3: bounded log-odds accumulation through a logistic transform. Never floors, always discriminates, and the parameter that used to be a magic divisor becomes a calibration intercept with a stated meaning.

## 7.3 "No category weights" is not the absence of weighting

**Severity: high. This is the most consequential doc-versus-reality gap in the system.**

`docs/methodology.md` §5.6 argues — correctly, and with a good citation to the AFA on risk mapping being the user's choice — that no authority publishes vendor-risk category weights, and concludes that the penalty model "dissolves the problem." It does not. It relocates it.

A category's influence emerges from **how many detectors you happen to have written for it, multiplied by the severities you happen to have assigned them.** That is a weighting scheme. It is simply an implicit, undocumented, accidental one, determined by engineering history rather than by risk judgement.

Two demonstrations from your own config:

**Governance is triple-counted.** `security.txt`, published security contact, and VDP are three signals over substantially one underlying fact — *does this vendor publish a way to report a vulnerability?* A vendor that publishes nothing takes three penalties for one omission. Part I's verdict on Security Contact says exactly this: merge them.

**Whichever category gets the next collector silently gains weight.** No review, no decision, no changelog entry. The weight moved because someone shipped a detector.

The honest position is not "we have no weights." It is: **"weights are implicit in signal counts and severity assignments; here they are, computed and published, and here is the sensitivity analysis."** That is defensible, it preserves the AFA argument (the numbers remain client-tunable in config), and it costs one table. §9.4 makes them explicit.

## 7.4 The frequency/severity ladder double-counts recurrence in one specific place

**Severity: medium.**

§5.3's design is right and the reasoning is unusually careful — frequency *replaces* summing rather than stacking on it, and the CVE-bag exemption is correct. One residual: `frequency` is not exempt for `breach_by_data_class`, and Part I recommends adding **root-cause repetition** as a distinct signal. Three breaches from three unrelated root causes and three breaches from one unfixed root cause are very different facts, and `1 + 0.25×(n−1)` treats them identically. The second should weigh more; the first is closer to bad luck scaled by exposure.

Second-order: the `age` floor of 0.15 with a 36-month half-life means a breach from 2004 still carries 6 penalty points forever on a −40 finding. The stated defence — "a breach never becomes irrelevant" — is reasonable, but it interacts badly with §7.9's disclosure bias: the vendors whose 2004 breaches are discoverable are disproportionately public companies in disclosure-regime jurisdictions.

## 7.5 `industry_profiles` contradicts `benchmarks.yaml`, and contradicts the whole market

**Severity: high. This is the direct answer to the research question, and the current answer is the wrong one.**

`scoring.yaml` lines 645–667 promote severity by industry:

```yaml
financial_services:
  promote:
    dmarc.absent: critical        # High (-20) -> Critical (-40)
    spf.absent: high              # Medium (-8) -> High (-20)
    cert_posture.none_claimed: high
    contactability.none_published: high
healthcare:
  promote:
    breach_by_data_class.personal_info: critical
    dmarc.absent: critical
    reporting_posture.none: high
```

`benchmarks.yaml` line 6 states: *"THIS FILE CHANGES NO ARITHMETIC. The posture in scoring.yaml is computed the same way for every vendor on earth; a bank and a bakery with the same findings get the same number."*

**That statement is not true of the shipped system.** A bank and a bakery with identical DMARC absence get −40 and −20 respectively. The separation of interpretation from arithmetic that `benchmarks.yaml` describes as the design principle is breached in the other file.

The config even flags its own discomfort: `max_promotions: 6  # a bigger number is a weighting scheme wearing a hat`. The comment is correct, and it applies at six as well as at seven.

Three concrete harms:

1. **Comparability breaks.** "We do not onboard below 65" means different things for a bank and a bakery. Portfolio aggregation over mixed-sector vendors becomes arithmetically invalid.
2. **Industry classification becomes a scoring input**, and it is derived from free sources of uneven reliability. A vendor misclassified as `financial_services` gets silently harsher treatment, and misclassification is now a dispute vector with points attached.
3. **It is not what the underlying authority says.** APRA CPS 234 requires an information security capability *commensurate with the threat* — it is a statement about what the entity must **do**, not about how much more **likely** a compromise is. You are using an obligation to modify a probability estimate.

**The signal being captured is real.** A regulated financial entity without DMARC *is* a bigger problem than a bakery without DMARC. But the reason is regulatory non-conformance and consequence, not compromise likelihood — and both have proper homes. §9.5's **Compliance Gap** and §9.7's **Expectation Gap** deliver the same message with more force (a named regulation and a named clause beats an unexplained extra −20) and without contaminating the score.

This one has a migration subtlety: the promotions are currently the *only* mechanism carrying sector expectation, so they must not be deleted before the replacement lands. §11 sequences it.

## 7.6 The Ghost cliff at 0.4 is gameable, and the game is "be harder to measure"

**Severity: medium-high.**

`confidence.refuse_below: 0.4` → "Insufficient evidence," no posture published.

The concept is right (§7.0). The **cliff** creates a discontinuity a rational bad actor can exploit: at coverage 0.41 with terrible hygiene you publish an F; at 0.39 you publish nothing. **Reducing attributable evidence is a way to avoid a bad grade** — and it is achievable without improving anything: fragment the estate across unattributable registrants, move assets behind third-party infrastructure that breaks attribution, reduce CT-discoverable surface.

The critical-ceiling bypass (a fired ceiling escapes the Ghost refusal) closes the worst case but only for `cert_validity`.

The fix is §9.8: replace the cliff with continuous shrinkage toward the cohort prior plus a published prediction interval. A vendor you cannot measure gets the cohort median with wide intervals and an explicit label — **not a free pass, and not a false precision either.** Retain outright refusal only at extreme coverage (≲0.15) where even the prior is uninformative.

## 7.7 The mitigation multiplier is the most manipulable element in the model

**Severity: medium — currently latent.**

`mitigation: { evidenced_factor: 0.6 }`, applied on human approval.

A flat 30–40% penalty reduction, granted by a human, with no evidence taxonomy and no differentiation between *"the vendor emailed us saying it is fixed"* and *"we re-scanned and the cert is now valid."* Your documentation is admirably clear that this is **dormant** — no free source currently evidences remediation, so nothing sets it — which means the defect is latent rather than active. But the moment a commercial source or a vendor portal lands, this becomes the single highest-value target for pressure on your analysts, and it will arrive with no structure to defend.

Fix in §9.9: a four-tier evidence taxonomy with different factors, an auto-expiry, and an audit trail per grant.

## 7.8 The critical ceiling creates a cliff with a perverse gradient

**Severity: low-medium.**

`ceiling_score: 49` caps down and never floors up — the design is right and the three constraints (confident attribution, must name its cause, caps-not-sets) are all correct.

The residual is the gradient. An expired certificate costs a well-run vendor 51 points and a poorly-run vendor 0. Two effects: the marginal incentive to *avoid* the ceiling is enormous for good vendors and nil for bad ones; and because a fired ceiling bypasses the Ghost, the strongest published claim in the system rests on a single signal's liveness check being correct.

Not urgent. In §9 the ceiling survives unchanged in intent, applied after the logistic transform, but note that the logistic curve softens the gradient naturally — the distance from 100 to the ceiling is compressed when the underlying evidence is otherwise clean.

## 7.9 Availability bias is not corrected anywhere, and it favours small private vendors

**Severity: medium — structural, and largely invisible in the output.**

Three signals are systematically more discoverable for large, public, regulated vendors:

| Signal | Bias direction | Current handling |
|---|---|---|
| Breach history | SEC registrants and HHS-covered entities must disclose; private firms below thresholds need not | None |
| Regulatory enforcement | Regulators pursue large, visible, well-resourced targets | None |
| Adverse media | Coverage volume tracks fame, not security | None |

A clean record on all three at a small private vendor is **much weaker evidence** than a clean record at a listed bank. The model treats them identically, which systematically flatters small private vendors — the opposite of the bias the research question worried about, and evidence that intuition about direction is unreliable here.

This is a **Confidence** correction, not a Posture one (§9.8), and it is one of the few places a firmographic legitimately enters the arithmetic.

## 7.10 Calibration rests on five vendors, and there is no outcome validation

**Severity: high for defensibility; low for day-to-day operation.**

The frozen corpus is excellent engineering — it makes regressions and intended re-grades distinguishable, which most teams never achieve. But it is a **regression harness, not a validation study.** It proves the model does what it did yesterday. It cannot show the model predicts anything.

Every number in the model — the 40/20/8/3 ladder, the divisor of 4, the 0.4 Ghost threshold, the 49 ceiling, the 36-month half-life, the 0.6 mitigation factor — is currently defended by reasoning and by a five-vendor sweep. None is defended by outcome data.

That is an acceptable position for a PoC **if it is stated**, and §5.4.3 does state it honestly. But it caps what the model may claim. Bitsight can say "700+ correlates with under 1% breach probability." You cannot say anything of that form, and should not imply it. §11 Phase 5 sets out the minimum viable validation path.

## 7.11 Summary of gaming vectors

| # | Vector | Cost to vendor | Score gain | Detectability | Fix |
|---|---|---|---|---|---|
| 1 | Reduce attributable footprint below 40% coverage | Low–Medium | Escapes a bad grade entirely | Low | §9.8 shrinkage |
| 2 | Saturate a category at 100, then ignore it | Zero | Unlimited free findings in that category | Low | §9.3 log-odds |
| 3 | Claim remediation to obtain the ×0.6 | Zero | Up to 40% penalty reduction | Depends on analyst | §9.9 taxonomy |
| 4 | Concentrate the estate on one clean primary asset | Medium | Weakest-link picks the clean one | Medium | §9.2 denominator over full estate |
| 5 | Contest or obscure industry classification | Low | Escapes `industry_profiles` promotion | Medium | §7.5 — remove promotions |
| 6 | Publish `security.txt` + contact + trust page | **Very low** | Three Governance signals at once | n/a — legitimate but over-rewarded | §9.4 merge, cap Governance influence |
| 7 | Let a marketing microsite host the compliant TLS while legacy endpoints lag | Low | Dispersion invisible to worst-of collapse | Medium | §9.2 dispersion term |

Vector 6 deserves a note: it is not cheating. It is the model over-rewarding a cheap action, which is the same failure with better manners. Ease of measurement is not evidence of importance, and Part I flags this specifically for `security.txt`.

---

# 8. Comparison of adjustment mechanisms

The twelve approaches `new_req.md` lists, scored on the six axes it asks for. Ratings are relative to each other, not absolute.

| # | Approach | Predictive value | Fairness | Explainability | Gaming resistance | Statistical soundness | Complexity | **Verdict** |
|---|---|---|---|---|---|---|---|---|
| 1 | **Firmographic multipliers** (revenue/headcount × severity) | ✗ None demonstrated | ✗ Poor | ~ Easy to state, impossible to justify | ✗ Weak — firmographics are contestable and often stale | ✗ Unvalidatable | Low | **Reject** |
| 2 | **Exposure normalization** (rate with denominator) | ✅ Strong | ✅ Strong — removes an existing bias | ✅ "9 of 900 hosts" reads better than "9 hosts" | ✅ Strong — denominator is externally observable, and inflating it means adding real hosts | ✅ Beta-binomial, standard | Medium | **Adopt — mandatory** |
| 3 | **Bayesian priors** (cohort prior, evidence updates) | ✅ Strong at low coverage | ✅ Strong if the prior is disclosed | ~ Requires explanation, but the explanation is honest | ✅ Strong — kills the disappearing act | ✅✅ Principled | Medium-High | **Adopt for Confidence/shrinkage** |
| 4 | **Logistic scaling** (bounded log-odds → score) | ✅ Strong — never floors | ✅ Neutral | ~ Non-linear; needs a chart in the report | ✅ Strong — no saturation to exploit | ✅✅ Standard | Medium | **Adopt** |
| 5 | **Peer-adjusted expectation as an output** (`EG = Posture − E[Posture\|peers]`) | ~ Not predictive; interpretive | ✅✅ Excellent — the score stays absolute | ✅✅ Excellent | ✅ Strong — cohort membership is disclosed | ✅ Sound | Low-Medium | **Adopt — this is the answer to the research question** |
| 6 | **Industry-specific baselines** (calibrate the scale, score identically) | ✅ Moderate | ✅ Strong | ✅ Strong | ✅ Strong | ✅ Sound (RiskRecon precedent) | Medium | **Adopt in benchmarking** |
| 7 | **Compliance-gap findings** (asserted framework vs observed control) | ~ Not likelihood; high decision value | ✅ Strong — cites a clause | ✅✅ Excellent | ✅✅ Excellent — gaming means dropping the claim, which is itself informative | ✅ Deterministic | Medium | **Adopt** |
| 8 | **Signal-specific weighting** (explicit, published, tunable) | ✅ Moderate | ✅ Strong | ✅ Strong once published | ~ Neutral | ~ Sound if disclosed | Low | **Adopt — you already have implicit weights (§7.3)** |
| 9 | **Confidence adjustments** (disclosure-regime, coverage) | ~ Indirect | ✅ Strong — corrects a real bias | ✅ Strong | ✅ Strong | ✅ Sound | Medium | **Adopt, narrowly** |
| 10 | **Dynamic severity adjustment** (severity varies by context) | ✗ Unsupported | ✗ Poor | ✗ Poor — severity stops meaning one thing | ✗ Weak | ✗ Breaks comparability | Medium | **Reject — this is what `industry_profiles` does today** |
| 11 | **Baseline maturity curves** (expected posture as f(company age)) | ✗ No evidence found | ✗ Poor | ~ Intuitive but unfounded | ✗ Weak | ✗ No published base rates | High | **Reject** |
| 12 | **Hybrid** (2 + 3 + 4 + 5 + 6 + 7 + 8 + 9) | ✅✅ | ✅✅ | ✅ | ✅✅ | ✅✅ | High | **This is the §9 recommendation** |

### 8.1 Why approach 1 fails, stated once and precisely

A revenue multiplier on severity fails on five independent grounds, any one of which is sufficient:

1. **No published evidence** links revenue to compromise *likelihood* independent of attack surface. Cyentia's finding that the largest corporations experience incidents at a 620× higher rate is an **exposure** effect, and exposure is directly measurable in DNS and CT logs. Revenue is a lagging, noisy, often-stale proxy for something you can observe.
2. **The premise is contradicted.** Cyentia found "not much difference in fix speeds between small, medium, and large organizations." More resources, proportionally more to patch.
3. **The direction is contradicted.** Fortune 500 DMARC adoption sits at 95% with 62.7% at `p=reject`, against Inc. 5000 at 15.2% `p=reject`. Large firms are *already better* at exactly the controls the "no excuse" argument targets — and their implementation task is harder, not easier, because `p=reject` at a Fortune 500 means inventorying hundreds of legitimate senders accumulated over decades.
4. **It fails the U.S. Chamber Principles for Fair and Accurate Security Ratings** on all three of the relevant tests: transparency of methodology, a workable dispute process, and ratings being "empirical, data-driven, or notated as expert opinion." A multiplier derived from third-party firmographic data the vendor cannot see, verify or correct fails each.
5. **It destroys comparability**, which is the entire reason a score exists (§2.3 of Part I).

### 8.2 Why NIS2 and DORA proportionality is not a counter-argument

It is the strongest counter-argument available, and it does not survive inspection.

NIS2 Article 21(1) requires "appropriate and proportionate" measures, with due account taken of "the degree of the entity's exposure to risks, the entity's size and the likelihood of occurrence of incidents." DORA scales requirements by size, nature, scale and complexity, with a simplified framework for microenterprises under Article 16.

So European regulators do scale obligations by size. Three observations settle it:

1. **Ordering.** Exposure first, size second. Even the regulators put measured exposure ahead of headcount.
2. **Direction.** Proportionality *reduces* obligations for small entities. It does not *increase* penalties for large ones. The research question asks for the second, and the regulation supports only the first.
3. **Object.** It modifies the **required control set**, not the **risk assessment**. A microenterprise with a simplified framework that is nonetheless running TLS 1.0 has exactly the same technical exposure as a bank running TLS 1.0. What differs is what the law demands of each.

Proportionality therefore belongs in **Compliance Gap and Recommendations** — what should this vendor be doing, what will regulators require of them — and not in the estimator of compromise likelihood.

---

# 9. The revised model

Five published quantities, each answering exactly one question, none contaminating another.

```
                         ┌──────────────────────────────────────────┐
   Evidence store  ─────► │  Findings (severity, band, timestamps)   │
   (unchanged)            └────────────────┬─────────────────────────┘
                                           │
        ┌──────────────┬───────────────────┼──────────────┬──────────────┐
        ▼              ▼                   ▼              ▼              ▼
  ┌───────────┐  ┌───────────┐      ┌────────────┐ ┌───────────┐ ┌────────────┐
  │  POSTURE  │  │CONFIDENCE │      │  ASSURITY  │ │ COMPLIANCE│ │  IMPACT /  │
  │   0-100   │  │   0-1     │      │   0-100    │ │    GAP    │ │    TIER    │
  │           │  │           │      │            │ │           │ │            │
  │ likelihood│  │ how much  │      │ documented │ │ claimed   │ │ what THIS  │
  │ of        │  │ we know   │      │ assurance  │ │ vs        │ │ engagement │
  │ compromise│  │           │      │ (positive- │ │ observed  │ │ exposes ME │
  │           │  │           │      │  only)     │ │           │ │     to     │
  └─────┬─────┘  └─────┬─────┘      └────────────┘ └───────────┘ └─────┬──────┘
        │              │                                                │
        │   vendor's firmographics: FORBIDDEN in Posture                │
        │   measured exposure: REQUIRED (as denominator)                │
        │                                                                │
        └──────────────┴──────────► EXPECTATION GAP ◄────────────────────┘
                                    EG = Posture − E[Posture | cohort]
                                    ── every firmographic lives HERE ──
```

## 9.1 Notation

| Symbol | Meaning |
|---|---|
| `s` | a signal |
| `f_s` | count of failing observations for signal `s` |
| `D_s` | exposure denominator for `s` — count of assets **checked and eligible** for that signal |
| `r̂_s` | smoothed failure rate |
| `g_s` | normalized evidence strength for `s`, in [0,1] |
| `w_sev` | log-odds weight for the finding's severity band |
| `a, φ, m` | age-decay, frequency, mitigation modifiers (retained from NIST SP 1326) |
| `z_s` | log-odds contribution of signal `s` |
| `L` | accumulated log-odds |
| `L₀` | calibration intercept |
| `c` | evidence coverage in [0,1] |
| `L_peer` | cohort-median log-odds (the Bayesian prior) |
| `σ(x)` | logistic function `1 / (1 + e^(−x))` |

## 9.2 Exposure normalization — the mandatory change

For every Class-P signal, define a denominator of **assets actually checked and eligible**:

| Signal | `D_s` |
|---|---|
| TLS version, cipher suites | Hosts with a successful TLS handshake |
| Certificate validity | Distinct certificates observed on live hosts |
| HSTS, CSP, X-Frame-Options | Hosts returning HTTP 200 on 443 |
| CVEs, KEV | Distinct fingerprinted software instances |
| Shadow assets | Total discovered assets (validated live) |
| Dangling subdomains | Total DNS records resolved |

**`D_s` counts what was checked, not what exists.** This keeps §5.4's central rule intact — an unchecked asset is a Confidence problem, never a silent pass and never a silent failure. It also removes the obvious gaming path: you cannot inflate the denominator without exposing real, scannable hosts, and those hosts then carry their own findings.

Smooth with a Beta prior so small denominators do not produce false certainty:

```
r̂_s = (f_s + α_s) / (D_s + α_s + β_s)
```

`α_s, β_s` are fitted from the cohort failure distribution for that signal (method of moments over the scored population). Until a cohort exists, use a weak uniform prior `α = 1, β = 4` — documented as provisional in config, per §5.3.2's rule that an unread or unjustified key is a claim you cannot honour.

Why this matters concretely: a 3-host vendor with 1 expired cert has a raw rate of 33%, but the evidence for "this vendor manages certificates badly" is thin. Smoothing pulls it toward the population mean; a 900-host vendor's 1% is measured precisely and barely moves.

**Blend rate with absolute count, per signal.** Pure rate is wrong for KEV — one unpatched known-exploited vulnerability is serious on a 5,000-host estate:

```
g_s = λ_s · r̂_s  +  (1 − λ_s) · min(1, f_s / κ_s)
```

| Signal class | `λ_s` | `κ_s` | Rationale |
|---|---|---|---|
| Certificate validity, TLS, ciphers, headers | 1.0 | — | Pure hygiene rate. This is where the size bias lives |
| Shadow assets | 1.0 | — | Ratio is the meaningful form |
| CVEs (banner-inferred) | 0.8 | 10 | Mostly rate; a huge absolute count still says something |
| **KEV** | **0.0** | **3** | **Absolute. One is bad; three is saturated. No leniency for anyone** |
| Dangling subdomains | 0.3 | 5 | Each one is individually exploitable |

**Add dispersion as a separate derived signal.** Worst-of collapse hides the difference between one legacy endpoint and an estate-wide failure. Dispersion — the share of eligible hosts failing — is a genuine maturity signal, computed entirely from data you already collect, with no firmographic input:

```
Dispersion(s) = f_s / D_s      reported alongside the finding, banded:
                                isolated (<5%) · partial (5-25%) · systemic (>25%)
```

An estate-wide TLS 1.0 failure and a single forgotten host are different facts about the vendor's change management. This is a **better maturity metric than company age**, and unlike company age it has an evidentiary basis.

**Class B signals get no denominator.** DMARC, DNSSEC, CAA, security.txt, VDP are one organisational decision. `g_s = 1` when the failing band is met.

## 9.3 Bounded log-odds accumulation

Replace `100 − Σpenalty/4` with accumulation in log-odds space, transformed once at the end.

**Step 1 — severity to log-odds weight.** Preserve the existing ratio so this is a re-parameterization, not a re-derivation (the 40:20:8:3 ladder is retained; only the units change):

| Severity | Current penalty | `w_sev` | Derivation |
|---|---|---|---|
| Critical | 40 | **2.20** | 40 / 18.2 |
| High | 20 | **1.10** | 20 / 18.2 |
| Medium | 8 | **0.44** | 8 / 18.2 |
| Low | 3 | **0.165** | 3 / 18.2 |
| Informational | 0 | **0** | |

The scaling constant 18.2 is chosen so that a single Critical at full weight moves a median vendor by approximately the same distance the current model moves it — making Phase 2 of the migration a near-identity transform on clean vendors and a large improvement on dirty ones. It is a calibration parameter and must be recorded as such.

**Step 2 — per-signal contribution:**

```
z_s = w_sev(s) · a(s) · φ(s) · m(s) · g_s · κ_cat(s)
```

`a`, `φ`, `m` are the NIST SP 1326 modifiers, unchanged in form and unchanged in configuration. `κ_cat` is the explicit category weight from §9.4.

**Step 3 — accumulate and transform:**

```
L = L₀ + Σ_s z_s

Posture = 100 · (1 − σ(L))      where σ(L) = 1 / (1 + e^(−L))
```

**Step 4 — non-compensatory overrides, in the existing order:** gates → transform → ceiling. Gates still block before anything is computed. The critical ceiling still caps down to 49, still requires attribution ≥ 0.7, still must name its cause, still never floors up.

**Properties gained:**

| Property | Current | Revised |
|---|---|---|
| Floors at 0 | Yes, at 400 total penalty | **Never** — asymptotic |
| Resolution in the bottom quartile | None | **Full** |
| Free findings after category saturation | Yes | **No** |
| Divisor coupled to category count | Yes | **No** — `L₀` is independent |
| Adding a category shifts all scores | Yes | **No** |
| Marginal value of fixing one finding | Zero when saturated | **Always positive** |

**Calibration of `L₀`.** One parameter with one job: place the population median at a chosen posture. If you want the median scored vendor at 75, set `L₀ = −ln(75/25) − median(Σz) = −1.0986 − median(Σz)`. This is the honest replacement for the divisor of 4 — same role, but its meaning is stateable in one sentence and it is re-fittable as the population grows without changing what any score means relative to the others.

**Worked comparison** (illustrative; exact values depend on `L₀` and the fitted priors):

| Vendor | Findings | Current posture | Revised posture |
|---|---|---|---|
| Clean, well-evidenced | none | 100 | ~97 |
| 1 High (no DMARC) | 1 × 20 | 95 | ~91 |
| 2 High + 3 Medium | 64 | 84 | ~80 |
| 3 Critical + 4 High | 200 | 50 | ~24 |
| 8 Critical + 12 High | 560 (capped) | **0** | **~4** |
| 20 Critical + 30 High | 1400 (capped) | **0** | **~0.3** |

The last two rows are the point. The current model cannot tell those vendors apart. The revised model ranks them, and the ranking is the thing a procurement team acts on.

## 9.4 Explicit category weights

§7.3 established that weights exist implicitly. Publish them:

```
κ_cat  ∈ config, default 1.0, tunable per client, printed in every report
```

Defaults, with the reasoning stated so a client can argue with it:

| Category | `κ_cat` | Reasoning |
|---|---|---|
| Breach & Compromise | **1.0** | Realized events. Strongest published correlation to future incidents |
| Cyber Hygiene & Technical | **1.0** | The core observable, once exposure-normalized |
| Digital Footprint & Assets | **0.8** | Real but partly a denominator; avoid double-counting with Class-P rates |
| Vendor Transparency & Governance | **0.5** | Three signals over one underlying fact (§7.3); merged and down-weighted |
| Compliance & Regulatory | **0.0 in Posture** | Moves to Assurity (§9.5) |
| Business & Financial Stability | **0.0 in Posture** | Moves to Entity Verification / Continuity |
| Adverse Media & Reputation | **0.0 in Posture** | Moves to Reputational Exposure (§9.10) |

**This does not resurrect the problem §5.6 dissolved.** The AFA argument — weighting is a risk-appetite judgement that must be the user's — is fully preserved: every `κ` is in config, changeable without a deploy, printed in the report, and defaults to 1.0 with a stated reason for each departure. What changes is that the weights are now **visible and arguable** instead of emergent from detector count. That is strictly more defensible, not less, and it closes the "why is Governance worth three signals?" question that the current design cannot answer.

## 9.5 Compliance Gap — a new finding class

The mechanism that replaces `industry_profiles`.

```
For each framework F the vendor publicly asserts (ISO 27001, SOC 2 Type II,
PCI DSS, HIPAA, FedRAMP, NIS2/DORA scope, APRA CPS 234):
    C(F) = the externally observable control expectations of F
    For each c ∈ C(F) observed to fail:
        emit ComplianceGap{framework: F, clause: c.citation, observation: c.evidence}
```

Three properties make this strictly better than severity promotion:

1. **It is deterministic and citable.** "Vendor asserts PCI DSS compliance; TLS 1.0 negotiated on `checkout.example.com`; PCI DSS required TLS 1.0 migration by 30 June 2018" is a stronger statement than a silent extra −20, and it is verifiable by the vendor.
2. **It does not touch Posture.** The technical severity of TLS 1.0 is what it is. What changed is the reliability of the vendor's own attestation.
3. **It cannot be gamed without cost.** The only escape is to stop asserting the framework — which is itself a highly informative event, and one the buyer wants to know about.

**Where it lands:** Compliance Gaps **reduce Assurity** (§9.6), never Posture. An attestation you visibly contradict is worth less than no attestation at all, and Assurity is the quantity that measures the value of attestations.

**For entities in mandatory scope** (NIS2 essential entities, DORA financial entities, BOD 20-01 federal agencies, APRA-regulated), a Compliance Gap is emitted whether or not the vendor asserts the framework, because the obligation is not optional. This is where §8.2's proportionality analysis operationalizes: regulatory status changes the **required control set**, exactly as the regulation intends.

## 9.6 Assurity — the quarantine for audit-budget effects

Positive-only accumulation, 0–100, reported beside Posture and never merged with it:

```
Assurity = 100 · σ( A₀ + Σ_j v_j · valid_j · scope_j  −  Σ_k γ_k · ComplianceGap_k )
```

| Component | Weight `v_j` | Notes |
|---|---|---|
| ISO 27001 certificate | 1.0 | × `scope_j` — an SoA excluding the assessed product scores near zero |
| SOC 2 Type II | 1.2 | Type II > Type I; report period recency matters |
| PCI DSS AoC | 0.8 | Only where payment handling is in scope |
| Published security program / trust page | 0.4 | |
| VDP | 0.5 | |
| Named security contact / security.txt | 0.2 | Merged — one fact, one score |
| Public pentest summary or bug bounty | 0.6 | |
| **Compliance Gap** | **−γ, γ ≈ 1.5** | **A contradicted claim is worse than no claim** |

`valid_j ∈ {0,1}` for expiry. `scope_j ∈ [0,1]` for scope coverage of the assessed entity and product.

**Absence never subtracts.** A vendor with no certifications has low Assurity, not bad Posture. This is the single most important structural fix for demographic fairness in the model: penalizing a missing SOC 2 is a tax on audit budget, correlates strongly with revenue, and has no demonstrated link to compromise likelihood.

## 9.7 Expectation Gap — where every firmographic legitimately lives

```
EG = Posture − E[Posture | cohort]
```

`cohort` is resolved by the existing `benchmarks.yaml` widening ladder — the design there is sound and needs no change beyond one addition. Publish:

- the absolute Posture (always, never replaced by the percentile — `disclosure.always_show_absolute_grade` already requires this);
- `E[Posture | cohort]`, with `n` and the widening rung reached;
- `EG`, with its sign and a plain-English reading;
- the self-selection caveat, verbatim, as `benchmarks.yaml` already mandates.

**This delivers the entire research question's intuition, with more force than a multiplier and none of the cost:**

> *"Posture 68. Median for financial services, 1,000–10,000 staff, ANZ (n=14): 87. **This vendor sits 19 points below its peer group and in the bottom decile of it.** The gap is driven by absent DMARC (95% of Fortune 500 peers have it, 62.7% at `p=reject`) and by TLS 1.0 on 8 of 340 checked hosts."*

Compare that with the current mechanism, which silently turns a −20 into a −40 and tells the reader nothing about why.

**One addition to `benchmarks.yaml`:** allow `expected_posture` entries to be *computed and stored* from cohort medians with an auto-generated `basis:` string. The loader guard requiring a basis is correct and must stay; an observed median with a date and an `n` satisfies it honestly. This is the file's own stated Path 1 and it is currently unimplemented.

## 9.8 Confidence — continuous, with two legitimate firmographic corrections

**Replace the cliff with shrinkage.** Rather than refusing at `c < 0.4`, shrink the estimate toward the cohort prior:

```
L̃ = c^τ · L  +  (1 − c^τ) · L_peer        τ ≈ 1.5

Posture_published = 100 · (1 − σ(L̃))
```

At `c = 1.0` the vendor's own evidence fully determines the score. At `c = 0.3` roughly 84% of the estimate is the cohort prior, and the report says so. **A vendor who becomes unmeasurable gets their cohort's median, not a free pass** — which removes gaming vector 1 entirely, because hiding no longer produces a better outcome than being average.

Publish a prediction interval whose width scales with `1/√(effective observations)`, and retain outright refusal only below `c ≈ 0.15`, where even the prior is uninformative about *this* vendor.

**Keep the Ghost as a label.** The quadrant in §5.4.1 is good communication and should survive verbatim. What changes is that the bottom-left quadrant now carries a shrunk number with a wide interval and an explicit "this is mostly your cohort's median, not this vendor's evidence" statement, instead of a blank.

**Two disclosure-regime corrections** — the narrow, legitimate firmographic entry into Confidence (§7.9):

```
c_breach *= δ_disclosure     δ = 1.0  SEC registrant / HHS-covered / GDPR Art.33 jurisdiction
                             δ = 0.6  private, no mandatory notification regime

c_enforcement *= δ_supervision  δ = 1.0  actively supervised sector
                                δ = 0.7  unsupervised
```

The effect is that "no breaches found" at a small private vendor produces *lower confidence*, not *equal posture*. This is the only place in the model where public/private status or regulatory footprint touches the arithmetic, and it moves the honest axis.

## 9.9 Mitigation — a taxonomy, not a flat multiplier

Replace `evidenced_factor: 0.6`:

| Tier | Evidence | Factor | Expiry |
|---|---|---|---|
| 0 | Vendor claim, uncorroborated | **1.00** | n/a — no credit |
| 1 | Vendor claim + plausible documentation | **0.85** | 90 days |
| 2 | Independent re-observation of a partial fix | **0.60** | 180 days |
| 3 | Independent re-observation: condition no longer present | **0.25** | 365 days, then re-verify |
| 4 | Condition absent on re-scan and root cause evidenced | **0.10** | 365 days |

Every grant carries the analyst identity, the evidence reference, the grant timestamp and the expiry, and appears in the receipt. Expiry is not optional: an unexpiring mitigation is a permanent discount for a one-time claim.

Tier 3–4 grants should eventually be **automatic** rather than human — a re-scan showing the cert is now valid is machine-verifiable, and machine grants cannot be socially pressured. Note that Tier 0 exists specifically so that "the vendor says it is fixed" has somewhere to be recorded without being rewarded.

## 9.10 What leaves Posture

| Signal | New home | Reason |
|---|---|---|
| ISO certifications, SOC reports | **Assurity** | Audit-budget proxy; no breach correlation |
| Published security program | **Assurity** | Speculative as a risk predictor |
| Exposed data types | **Impact / Tier** | Pure consequence, and the consequence is the buyer's |
| Domain age, legal entity status | **Entity Verification** | Fraud signals, not security signals |
| Company age, company continuity | **Vendor Profile + benchmarking prior** | No published evidence of a security relationship |
| Government investigations | **Context disclosure only** | Allegation, not finding. Defamation exposure |
| Verified adverse media | **Reputational Exposure** | Measures fame; must be normalized by media baseline |
| Raw subdomain count | **Denominator `D`** | Not a risk signal; it is the thing risk is measured against |

Nothing is deleted. Everything is relocated to a dimension where it is measuring what it actually measures, and every relocation is recorded in config rather than silently dropped — the `excluded_signals` discipline, applied to relocations.

## 9.11 Impact and Tier — the buyer's side

Kept brief because it is largely outside the external-OSINT scope, but the architecture requires it to exist or the consequence signals have nowhere to go:

```
Impact = h( data_classes_held, access_type, integration_depth,
            volume_of_records, buyer_sector, substitutability, 4th-party reach )
```

Every input is a property of **the engagement**, sourced from the buyer, not inferred about the vendor. Then:

```
Priority = Impact × (1 − Posture/100)
```

This is the number that should drive remediation ordering and reassessment cadence, and it is the only place where a *hospital* using a CRM and a *coffee shop* using the same CRM correctly diverge.

## 9.12 The complete model, one page

```
── GATES (unchanged) ──────────────────────────────────────────────────
   sanctions hit → BLOCK, adjudication queue, no score
   entity confidence < 0.5 → BLOCK, manual confirmation

── POSTURE ────────────────────────────────────────────────────────────
   for each Class-P signal s:
       r̂_s = (f_s + α_s) / (D_s + α_s + β_s)
       g_s = λ_s·r̂_s + (1−λ_s)·min(1, f_s/κ_s)
   for each Class-B signal s:
       g_s = 1 if failing band met else 0

   z_s = w_sev(s) · a(s) · φ(s) · m(s) · g_s · κ_cat(s)
   L   = L₀ + Σ_s z_s
   L̃   = c^τ·L + (1−c^τ)·L_peer
   Posture = 100 · (1 − σ(L̃))

   if directly-observed current critical AND attribution ≥ 0.7 AND cause nameable:
       Posture = min(Posture, 49)          # caps down, never floors up

── CONFIDENCE ─────────────────────────────────────────────────────────
   c = Σ(covered signals) / Σ(planned signals)
   c_breach      *= δ_disclosure
   c_enforcement *= δ_supervision
   publish interval width ∝ 1/√(effective observations)
   refuse only below c ≈ 0.15

── ASSURITY ───────────────────────────────────────────────────────────
   Assurity = 100·σ( A₀ + Σ_j v_j·valid_j·scope_j − Σ_k γ_k·ComplianceGap_k )
   absence never subtracts

── COMPLIANCE GAP ─────────────────────────────────────────────────────
   asserted or mandatory framework F, observed failure of c ∈ C(F)
   → cited finding; reduces Assurity; never touches Posture

── EXPECTATION GAP ────────────────────────────────────────────────────
   EG = Posture − E[Posture | cohort]
   cohort from benchmarks.yaml widening ladder; n and rung always disclosed
   ── every firmographic the research question asked about lives here ──

── IMPACT / TIER ──────────────────────────────────────────────────────
   Impact   = h(buyer-side engagement properties)
   Priority = Impact × (1 − Posture/100)
```

---

# 10. Recommendations, tiered

Each carries evidence, implementation cost, bias risk, gaming risk, fairness effect, and effect on score consistency, as `new_req.md` requires.

## 10.1 Strongly recommended

### R1 — Exposure denominators on all Class-P signals

| | |
|---|---|
| **Evidence** | Bitsight and SecurityScorecard both do this explicitly and publicly; RiskRecon measures issues per 100 high-value systems. Unanimous market practice |
| **Complexity** | **Medium.** Requires per-signal denominator plumbing; you already collect the counts |
| **Bias risk** | **Negative — it removes a bias.** Current absolute counting penalizes large estates for being large |
| **Gaming risk** | **Low.** Inflating `D` means exposing real scannable hosts, which carry their own findings |
| **Fairness** | **Large improvement.** The current undisclosed size penalty is the model's biggest fairness defect |
| **Consistency** | Scores will move for large-footprint vendors, upward. Frozen corpus must be re-baselined with documented diffs |

### R2 — Logistic transform over bounded log-odds

| | |
|---|---|
| **Evidence** | Standard practice in credit and actuarial scoring; Bitsight's rating-to-breach-probability curve is logistic in shape |
| **Complexity** | **Medium.** Contained change to the aggregation step; modifiers and bands unchanged |
| **Bias risk** | Neutral |
| **Gaming risk** | **Reduces it** — removes the category-saturation free-findings exploit (vector 2) |
| **Fairness** | Improves — every remediation has positive marginal value at every score level |
| **Consistency** | Clean vendors barely move; bottom-quartile vendors re-rank substantially, which is the objective |

### R3 — Delete `industry_profiles` severity promotions; replace with Compliance Gap

| | |
|---|---|
| **Evidence** | No platform in §5 promotes technical severity by industry. Your own `benchmarks.yaml` line 6 states the principle this violates |
| **Complexity** | **Medium.** Deletion is trivial; the Compliance Gap replacement is the real work and must land first |
| **Bias risk** | **Removes one.** Industry classification is currently a scoring input derived from uneven free sources |
| **Gaming risk** | **Reduces it** — removes vector 5 (contest the classification) |
| **Fairness** | Large improvement; restores cross-sector comparability |
| **Consistency** | Financial-services and healthcare vendors will score higher. **Sequence the replacement first** or you lose the sector signal in the interim |

### R4 — Move ISO / SOC / published program out of Posture into Assurity

| | |
|---|---|
| **Evidence** | No published breach correlation for certification holding; strong correlation with audit budget, which correlates with revenue |
| **Complexity** | **Low.** Recategorization plus one new output |
| **Bias risk** | **Removes the model's most demographically biased element** |
| **Gaming risk** | Unchanged |
| **Fairness** | Large improvement for small and private vendors |
| **Consistency** | Vendors without certifications gain posture; the information is preserved and more prominent in Assurity |

### R5 — Adopt EPSS as a primary vulnerability severity input

| | |
|---|---|
| **Evidence** | **Strongest single accuracy result in this study.** A CVSS 7+ strategy needs ~50.7% of CVEs remediated for 74.6% coverage at ~6% efficiency; EPSS v4 reaches comparable coverage at ~6% effort and ~47% efficiency |
| **Complexity** | **Low.** Free API, already in your source register |
| **Bias risk** | None identified |
| **Gaming risk** | Very low — EPSS is externally computed |
| **Fairness** | Improves; the same threat model applies to everyone |
| **Consistency** | CVE-derived penalties re-rank significantly, in the direction of actual exploitation |

### R6 — Expectation Gap as a published output

| | |
|---|---|
| **Evidence** | Universal market practice; and Fortune 500 vs Inc. 5000 DMARC data shows the benchmark delta *already* captures the "no excuse" intuition without any multiplier |
| **Complexity** | **Low–Medium.** `benchmarks.yaml` machinery mostly exists; needs computed `expected_posture` with auto-generated basis |
| **Bias risk** | Low if cohorts are disclosed; the self-selection caveat is already mandated |
| **Gaming risk** | Low — cohort membership is externally observable |
| **Fairness** | Improves — this is *how* you deliver context fairly |
| **Consistency** | Zero effect on Posture, by construction |

### R7 — Replace the Ghost cliff with shrinkage plus intervals

| | |
|---|---|
| **Evidence** | Standard hierarchical Bayesian practice; closes a discontinuity that rewards being unmeasurable |
| **Complexity** | **Medium.** Needs cohort priors, which need a scored population |
| **Bias risk** | Low, provided the prior is disclosed |
| **Gaming risk** | **Removes vector 1, the most exploitable path in the current model** |
| **Fairness** | Improves — thin-evidence vendors get an honest estimate with honest uncertainty rather than a blank |
| **Consistency** | Vendors near the 0.4 boundary stop flipping between "F" and "no score" on collector noise |

### R8 — Publish explicit category weights

| | |
|---|---|
| **Evidence** | The weights already exist implicitly (§7.3). Publishing is strictly more transparent |
| **Complexity** | **Low.** A config table and a report line |
| **Bias risk** | Reduces — makes the existing implicit weighting arguable |
| **Gaming risk** | Neutral |
| **Fairness** | Improves — a vendor can now dispute a weighting, which the Chamber Principles require |
| **Consistency** | Small movements; defaults chosen to approximate current effective weights |

### R9 — Mitigation evidence taxonomy with expiry

| | |
|---|---|
| **Evidence** | Basic control design; the current flat human-granted 0.6 has no evidence standard |
| **Complexity** | **Low.** Config plus an audit field |
| **Bias risk** | Reduces — removes analyst discretion as an unpriced variable |
| **Gaming risk** | **Removes vector 3** |
| **Fairness** | Improves — the same evidence standard for every vendor |
| **Consistency** | No effect today (the multiplier is dormant); prevents a future inconsistency |

### R10 — Merge `security.txt`, security contact, and VDP into one Governance signal

| | |
|---|---|
| **Evidence** | Part I's Security Contact verdict states it directly: three signals over one fact |
| **Complexity** | **Low** |
| **Bias risk** | Reduces the ease-of-measurement bias Part I warns about explicitly |
| **Gaming risk** | **Removes vector 6** — publishing three cheap artefacts no longer buys three signals |
| **Fairness** | Improves |
| **Consistency** | Governance category shrinks in influence, correctly |

## 10.2 Reasonable but optional

### O1 — Asset-value weighting (the RiskRecon approach)

Weight findings by inferred asset function: authentication endpoints and payment paths above static marketing hosts. **Genuinely better risk measurement**, and it is a *measured* property, not a firmographic. Cost: high — requires reliable functional classification of hosts, and misclassification becomes a dispute vector. Defer until R1 lands, since it is a refinement of the same denominator machinery.

### O2 — Days-past-CISA-deadline multiplier on KEV

Bitsight's KEV analysis found more than 60% of known exploited vulnerabilities remain unmitigated past CISA deadlines. A deadline-overrun multiplier is well-evidenced and cheap. Optional only because it refines an already-correct signal.

### O3 — Root-cause repetition as a distinct breach signal

Three breaches from one unfixed root cause differ from three unrelated ones. Correct in principle; requires breach-cause data that free sources rarely provide reliably. Build the field, populate it when evidence allows, and leave it dormant with a documented reason — per §5.3.2's rule.

### O4 — KEV/EPSS differential remediation velocity as the maturity metric

Cyentia found the gap between remediation speed for exploited versus non-exploited vulnerabilities is widest for large organizations — large firms triage harder because they must. This is a **genuine, measurable maturity signal computed entirely within the vendor**, free of firmographic input, and it is a far better maturity proxy than company age. Requires longitudinal scanning, so it depends on scheduled re-scoring landing first.

### O5 — Computed `expected_posture` written back to `benchmarks.yaml`

The file documents this as Path 1 and ships empty. Implement it once cohorts populate. Optional only because R6 delivers most of the value without persistence.

## 10.3 Not recommended

### N1 — Revenue, headcount, or market-cap multipliers on severity

Five independent grounds for rejection (§8.1). **This is the direct answer to the framing question, and it is no.** The intuition behind it is correct and it is served by R6.

### N2 — Company-age or domain-age based expectation curves

**No published evidence exists.** No authoritative source in this review scores or normalizes by founding date or domain age. Building a maturity curve on intuition would introduce an unvalidatable adjustment that cannot be back-tested — precisely the ESG-divergence failure mode. If you want maturity, use O4, which is measurable.

### N3 — Geographic or nationality-based posture adjustment

Weakly predictive, ethically fraught, legally exposed under anti-discrimination and trade regimes. Surface jurisdiction as a disclosed attribute of the engagement. Note that the current model already has a latent version of this: penalizing privacy-protected WHOIS is a geographic bias in disguise, since it is the GDPR-era default (Part I, Domain Registration Quality).

### N4 — Scoring unadjudicated government investigations

Allegation, not finding. Defamation exposure, and it likely fails the Chamber Principles' "empirical, data-driven" requirement. `docs/legal_and_standards_basis.md` §1.3 already identifies this class of exposure — and note its finding that the exposure runs *opposite* to intuition: a large vendor barred from suing in defamation by the excluded-corporation test still has ACL s 18, which carries no serious-harm threshold and no size limit. "Too big to sue us" is not safety.

### N5 — Raw adverse-media counts in any scored dimension

The most size-confounded signal in the catalogue — it measures fame. If used at all, normalize by baseline media volume, require human verification, and keep it out of Posture entirely.

### N6 — Blending Posture and Confidence into one number

Already refused by the current design, and the refusal is correct. Restating it here because the shrinkage in R7 could be misread as a step toward blending. It is not: shrinkage changes the *estimate* using a disclosed prior; it does not fold *uncertainty* into the point value. Both numbers stay published, side by side.

---

# 11. Migration plan

Five phases. Every phase is independently shippable, independently reversible, and leaves the model coherent if the next phase never happens.

**Two invariants that hold throughout:** the evidence store contract is untouched, and every phase re-baselines the frozen corpus with a documented, reviewed diff — never a silent one. The corpus's whole value is that an intended re-grade and a regression look different, and that property must survive its own re-baselining.

## Phase 0 — Instrument before you change anything (1–2 weeks)

No scoring change ships. Build the measurement that tells you whether the later phases worked.

1. Record `D_s` for every Class-P signal on every scan — **without using it in scoring**. Two to four weeks of data gives you the failure-rate distributions that fit `α_s, β_s`.
2. Compute and publish the **implicit** category weights the current model produces (§7.3). Expect this to be the most uncomfortable artefact in the migration, and the most useful.
3. Add a shadow-scoring harness: run the revised model alongside the current one, log both, publish neither.
4. Reconcile the `industry_profiles` / `benchmarks.yaml` contradiction in the documentation *now*, before any code moves. It is currently a live inconsistency between two shipped files and it should not survive another release either way.

**Exit criterion:** denominators recorded for ≥ 30 vendors; implicit weights published; shadow harness green against the frozen corpus.

## Phase 1 — Structural relocations (2–3 weeks) · *no arithmetic change to what remains*

The cheapest phase and the largest fairness gain per unit of work.

1. **R4** — ISO, SOC, published program out of Posture; stand up **Assurity** as a positive-only output.
2. **R10** — merge `security.txt` + security contact + VDP into one Governance signal.
3. Relocate per §9.10: exposed data types → Impact; domain age, legal entity status → Entity Verification; adverse media, government investigations → Reputational Exposure (disclosure-only); raw subdomain count → denominator.
4. **R8** — publish explicit `κ_cat`, defaulted to reproduce Phase 0's measured implicit weights as closely as possible, so this phase is weight-neutral by construction.

**Expected movement:** vendors without certifications gain posture. Small private vendors gain most. Frozen corpus re-baselined; the diff should be explicable vendor by vendor in one sentence each.

**Rollback:** config-only. Revert `κ_cat` and the category assignments.

## Phase 2 — Exposure normalization (3–4 weeks) · *the big one*

1. **R1** — `D_s` live for all Class-P signals, with Beta smoothing fitted from Phase 0 data.
2. Add the dispersion signal (isolated / partial / systemic).
3. Split the coarse signals Part I flags: certificate validity → expired / hostname-mismatch / self-signed-internal; cipher suites → broken / deprecated.
4. **R5** — EPSS as a primary vulnerability severity input; down-weight raw CVE counts.

**Expected movement:** large-footprint vendors gain substantially. This is the phase where the undisclosed size bias comes out, and scores will move enough that **existing clients must be notified in advance** — SecurityScorecard's practice of publishing forward-dated recalibration notices is the right model to copy, and copying it also demonstrates good faith under the Chamber Principles.

**Rollback:** set every `λ_s = 0` and `κ_s = 1`, which reduces the blend to absolute counting.

## Phase 3 — Aggregation change (2–3 weeks)

1. **R2** — log-odds accumulation with the logistic transform. Fit `L₀` so the population median lands where the divisor of 4 currently puts it, making the change approximately neutral at the median and corrective in the tails.
2. Retire `overall.penalty_divisor` — and retire it *loudly*, with the reasoning recorded in the config comment, since the current comment block explaining the divisor is one of the better pieces of documentation in the system and its replacement should be equally well argued.
3. Reconsider `aggregation: weakest_link`. With denominators in place, weakest-link over assets double-counts exposure. Recommend: **weakest-link for the ceiling and gates** (one live critical anywhere still caps), **estate-wide rates for Posture**.

**Expected movement:** clean vendors barely move; bottom-quartile vendors re-rank and become distinguishable for the first time.

**Rollback:** the transform is a single function; keep the linear path behind a config flag for one release.

## Phase 4 — Context outputs (3–4 weeks)

1. **R3** — Compliance Gap finding class, mapped for ISO 27001, SOC 2, PCI DSS, HIPAA, NIS2/DORA scope, APRA CPS 234, BOD 20-01. **Then, and only then**, delete `industry_profiles.promote`.
2. **R6** — Expectation Gap published; computed `expected_posture` with auto-generated basis strings (**O5**).
3. **R7** — shrinkage and prediction intervals; the Ghost becomes a label over a shrunk estimate rather than a refusal, with hard refusal retained below `c ≈ 0.15`.
4. **R9** — mitigation taxonomy with expiry and audit trail.
5. Disclosure-regime confidence corrections (§9.8).

**Sequencing is load-bearing.** `industry_profiles` is currently the only mechanism carrying sector expectation. Deleting it before Compliance Gap ships would lose the signal, and the loss would show up as financial-services vendors quietly scoring better with no visible reason — the exact kind of unexplained movement that destroys trust in a score.

## Phase 5 — Validation (ongoing, starts at Phase 2)

The phase that converts the model from *defensible by reasoning* to *defensible by evidence*.

1. **Record predictions.** Every published Posture, timestamped and immutable. You cannot validate retrospectively.
2. **Collect outcomes.** Public breach disclosures, regulatory notifications, HIBP additions, OAIC NDB entries against previously-scored vendors. Slow, and there is no shortcut.
3. **Measure discrimination** once you have outcomes: AUC of Posture against subsequent incident, and a calibration plot of predicted versus observed rates by score band.
4. **Publish the curve.** This is what lets you eventually make a Bitsight-class claim. Until then, do not imply one — §5.4.3's honesty about the five-vendor corpus is the right register and should be extended, not quietly retired.
5. **Back-test every context adjustment.** §2.5's aggregate-confusion warning is the standing rule: **an adjustment you cannot back-test is an adjustment you should not ship.** That applies to everything in §9, including §9's own recommendations.

## Timeline and dependency

```
Phase 0  ████                                        instrument + shadow  (wks 1-2)
Phase 1      ██████                                  relocations          (wks 3-5)
Phase 2            ████████                          denominators + EPSS  (wks 6-9)
Phase 3                    ██████                    log-odds             (wks 10-12)
Phase 4                          ████████            context outputs      (wks 13-16)
Phase 5            ═══════════════════════════════►  validation, ongoing from wk 6
```

Phase 1 depends on nothing. Phase 2 depends on Phase 0's distributions. Phase 3 is independent of 1 and 2 but lands best after them. Phase 4's step 1 must complete before Phase 4's `industry_profiles` deletion.

## What must not change

| Property | Why |
|---|---|
| Evidence store written before scoring | The dispute-survival property. Non-negotiable |
| Every arrow reversible | Same |
| Loader refuses a penalising band with no reason | Prevents explanation drift, in both directions |
| Gates block, never grade | Sanctions must never be a letter grade |
| Critical ceiling caps down, names its cause | A ceiling that cannot state its cause must not fire |
| `excluded_signals` recorded, not dropped | A refusal is a position; document it |
| No natural-person signals | Law and ethics, both settled |
| Config, not code | The model is the deliverable and must be arguable in a room |
| Posture and Confidence never merge | The Ghost exists because of this |

---

# 12. Final recommendation

The answer to deliverable 9, stated as a permission table. Read the middle column as: *"is this input allowed to change this output?"*

| Component | Company age | Revenue | Headcount | Market cap | Industry | Regulatory status | Public/private | **Measured exposure** | Buyer engagement |
|---|---|---|---|---|---|---|---|---|---|
| **Severity** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Penalty modifiers** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | **✅ denominator** | ❌ |
| **Posture** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | **✅ via rates** | ❌ |
| **Confidence** | ❌ | ❌ | ❌ | ❌ | ~ | **✅ disclosure regime** | **✅** | ~ | ❌ |
| **Assurity** | ~ | **✅** | **✅** | ~ | **✅** | **✅** | **✅** | ❌ | ❌ |
| **Compliance Gap** | ❌ | ~ | ~ | ❌ | **✅** | **✅✅** | **✅** | ❌ | ~ |
| **Benchmarking** | **✅** | **✅** | **✅** | **✅** | **✅✅** | **✅** | **✅** | **✅** | ❌ |
| **Vendor Tier / Impact** | ❌ | ~ | ~ | ❌ | **✅** | **✅** | ❌ | ~ | **✅✅** |
| **Recommendations** | **✅** | **✅** | **✅** | ~ | **✅** | **✅** | **✅** | **✅** | **✅** |

*✅✅ = primary driver · ✅ = permitted and appropriate · ~ = weak or indirect · ❌ = forbidden*

### The three sentences that carry the whole study

> **Posture answers one question — how likely is this vendor to be compromised — and the only company characteristic allowed to touch it is measured exposure, entering as a denominator, in the direction that removes a size bias rather than adding one.**
>
> **Every other company characteristic the research question asked about — age, revenue, headcount, market cap, industry, regulatory status, ownership — belongs in Benchmarking, Assurity, Compliance Gap, Impact, or Recommendations, where it changes the reading of the number and the actions taken, and never the number itself.**
>
> **The intuition that started this research is correct: a $5 billion bank with no DMARC is a worse finding than a $500,000 startup with no DMARC. That intuition is about culpability and consequence, not probability, and the Expectation Gap says it louder, with a citation and a peer percentile, than any multiplier ever could.**

### What actually gets built, in priority order

1. **Exposure denominators** — removes an existing undisclosed bias. Highest impact.
2. **Move ISO/SOC to Assurity** — cheapest large fairness gain.
3. **EPSS as primary vulnerability input** — the single best accuracy improvement available.
4. **Log-odds and logistic transform** — restores resolution where decisions are hardest.
5. **Compliance Gap, then delete `industry_profiles`** — in that order.
6. **Expectation Gap** — the deliverable that answers the research question.
7. **Shrinkage over the Ghost cliff** — closes the most exploitable gaming path.
8. **Outcome validation** — the only thing that converts any of this from reasoning into evidence.

### The honest limitation of this document

Everything in §9 is derived from published methodology, empirical studies, and the internal logic of the decomposition. **None of it is validated against outcome data on your population, because that data does not exist yet.** Phase 5 exists to create it, and until it does, the revised model is *better-reasoned* than the current one but not *demonstrably more predictive*. That distinction should be stated to any client who asks, in the same register as `docs/methodology.md` §5.4.3 already states the five-vendor limitation.

The one thing this study can claim without qualification is narrower and firmer: **the current model contains a measurable, undisclosed bias against large-footprint vendors, and R1 removes it.** That claim needs no outcome data. The arithmetic is sufficient.

---

# 13. References

Grouped by the role each source plays in the argument. Where a source's methodology is publicly documented but its underlying data is proprietary, that is noted — the distinction matters for how much weight a claim can carry.

### Ratings-provider methodology (public documentation, proprietary data)

1. Bitsight — *The Definitive Guide to Bitsight Security Ratings*; *How Are Bitsight Security Ratings Calculated?*; *Bitsight Security Ratings Correlate to Breaches* (knowledge base and datasheet). Size normalization, breach correlation (27,458 companies / 2,671 events), incident-adjustment decay.
2. Bitsight — *More than 60 Percent of Known Exploited Vulnerabilities Remain Unmitigated Past Deadlines* (CISA KEV catalogue analysis).
3. SecurityScorecard — *How SecurityScorecard Calculates Your Scores*; *A Deep Dive in Scoring Methodology*; *A Closer Look at Scoring 3.0 Vocabulary and Breach Likelihood*; scoring recalibration notices (Oct 2025, Feb 2026, May 2026, Aug 2026). Digital-footprint z-score normalization.
4. RiskRecon (Mastercard) — *RiskRecon Ratings Explained*; *New RiskRecon Cybersecurity Risk Ratings Model: The Methodology*; *Asset Risk Valuation Algorithms*. Asset-value weighting; bank 0.5 vs university 6.3 critical issues per 100 high-value systems; Rayleigh distribution.
5. Black Kite — technical rating, FAIR-based financial impact, and compliance-correlation modules (vendor documentation).
6. UpGuard — published category weights and severity bands; comparison series covering Black Kite, Panorays, RiskRecon and SecurityScorecard.
7. Panorays — external attack surface combined with business relationship context; Chamber Principles signatory statement.

### Empirical research

8. Cyentia Institute — *Information Risk Insights Study (IRIS) 2022* and *IRIS 2025* (2025 edition sponsored by CISA). Incident frequency by organization size (620× adjusted rate; 32× multiple-incident likelihood above $100B revenue); relative impact on smaller firms.
9. Cyentia Institute / Kenna Security — *Prioritization to Prediction* series. Remediation velocity by organization size; the exploited-vs-non-exploited triage gap.
10. Jacobs, Romanosky, et al. — EPSS design and evaluation; *Enhancing Vulnerability Prioritization: Data-Driven Exploit Predictions with Community-Driven Insights* (arXiv). CVSS 7+ at ~50.7% effort / 74.6% coverage / ~6% efficiency; EPSS v4 at ~6% effort / ~47% efficiency.
11. FIRST — EPSS v4 model documentation and performance analysis.
12. Verizon — *2025 Data Breach Investigations Report*. Third-party involvement in confirmed breaches doubled to 30%; edge-device exploitation growth.
13. IBM Security / Ponemon Institute — *Cost of a Data Breach Report 2025* (600 organizations, 17 industries). Healthcare $7.42M (14th consecutive year highest), financial $5.56M, industrial $5.00M, energy $4.83M, technology $4.79M, education $3.80M, retail $3.54M, public sector $2.86M.
14. EasyDMARC — *2026 DMARC Adoption Report* and *DMARC Adoption Across Fortune 500 and Inc. 5000*. Fortune 500 at 95% adoption / 62.7% `p=reject` / 97.9% RUA; Inc. 5000 at 15.2% `p=reject`.
15. Red Sift — December 2025 global DMARC analysis, 73.3 million domains: 14.9% with any DMARC record, 2.5% at `p=reject`.
16. Berg, Kölbel and Rigobon — *Aggregate Confusion: The Divergence of ESG Ratings* (Review of Finance). Pairwise correlation ~0.53–0.56 across ESG providers vs >0.99 for Moody's/S&P credit ratings; divergence attributable to measurement, scope and weighting choices.
17. *Conflicting Scores, Confusing Signals: An Empirical Study of Vulnerability Scoring Systems* (arXiv). Divergence across vulnerability scoring systems.

### Standards, regulation and governance

18. NIST SP 1326 — third-party risk assessment variables (age, frequency, mitigation) as adopted in `scoring.yaml` `modifiers`.
19. NIST SP 800-52 Rev. 2 — TLS implementation guidelines.
20. IETF RFC 8996 — *Deprecating TLS 1.0 and TLS 1.1*.
21. IETF RFC 9116 — `security.txt`.
22. ISO/IEC 29147 (vulnerability disclosure), ISO/IEC 30111 (handling), ISO/IEC 27001, ISO/IEC 27036.
23. CISA BOD 20-01 — *Develop and Publish a Vulnerability Disclosure Policy*; BOD 22-01 — KEV remediation deadlines.
24. EU Directive 2022/2555 (NIS2), Article 21(1) — proportionality: "due account shall be taken of the degree of the entity's exposure to risks, the entity's size and the likelihood of occurrence of incidents."
25. EU Regulation 2022/2554 (DORA), including Article 16 simplified framework for microenterprises.
26. PCI DSS v4.0 — TLS migration deadline (30 June 2018) and client-side script requirements.
27. U.S. Chamber of Commerce — *Principles for Fair and Accurate Security Ratings* (2017), with compliance statements published by RiskRecon, Bitsight and Panorays.
28. APRA CPS 234 (Information Security) and CPS 230 (Operational Risk Management, in force 1 July 2026) — cited in `scoring.yaml` `industry_profiles.financial_services.basis`.
29. OAIC — *Notifiable Data Breaches* statistical reports; health providers 19% of CY2025 notifications.
30. FBI IC3 — *2024 Internet Crime Report*. BEC second by dollar loss, US$2.77bn — the basis for scoring DMARC above Bitsight's weighting.

### Internal

31. [context-aware-vendor-risk-scoring-study.md](context-aware-vendor-risk-scoring-study.md) — Part I, §§1–4. Conceptual foundation, empirical review, and the 35-signal analysis this document's §6 matrix summarises.
32. [docs/methodology.md](docs/methodology.md) §5 — the current scoring framework under review.
33. `scoring.yaml` v4.2.0 · `benchmarks.yaml` v1.0.0 — the shipped configuration.
34. [docs/legal_and_standards_basis.md](docs/legal_and_standards_basis.md) §1.3 (defamation, and ACL s 18 as the residual exposure against large vendors) and §1.1 (Privacy Act APP constraints behind `excluded_signals`). *Note: `docs/methodology.md` §5.4.1 cites this as "§4.2", which no longer resolves — worth fixing when that file is next touched.*

---

*Part II of a two-part study. Part I asked whether context should change the score; Part II specifies where context goes instead.*
