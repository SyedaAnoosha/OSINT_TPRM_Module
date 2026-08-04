# Does Company Information Change the Score? — signal by signal

**A brief.** Condensed from `context-aware-vendor-risk-scoring-study.md` (Part I, §4) and
`new_research_meth.md` (Part II, §6). One question asked of all 35 signals:

> *Should this signal's contribution to the score change because of the vendor's age, revenue,
> headcount, market cap, industry, or regulatory status?*

---

## The answer in five lines

**For 35 of 35 signals, the answer in Posture is no.** Not one signal in the catalogue justifies a
company-age, revenue, headcount, or market-cap multiplier on its penalty.

**What does legitimately change the arithmetic is measured exposure** — the vendor's observed
internet-facing footprint, used as a *denominator* on the 10 signals whose finding-count scales with
asset inventory. That is size-sensitivity in the direction that *removes* an existing bias, not one
that adds a new one.

**Everything else the firmographics want to say gets said elsewhere** — in Benchmarking, Compliance
Gap, Confidence, Assurity, or Impact — where it is visible, disputable, and does not destroy
score comparability.

---

## The rule that decides each row

Sort every signal into one of four classes and the answer falls out mechanically:

| Class | Meaning | Does company info change the score? |
|---|---|---|
| **P — Prevalence** | Finding count scales with asset inventory (certs, TLS, headers, CVEs, KEV, shadow assets) | **Exposure denominator: mandatory.** Firmographics: no |
| **B — Binary policy** | One org-level decision, cost ~independent of size (DMARC, SPF, DNSSEC, CAA, VDP) | **No. Identical for every organization** |
| **C — Consequence / assurance** | Says more about impact or evidence quality than about likelihood (breaches, ISO/SOC, media, entity data) | **Mostly leaves Posture entirely** |
| **D — Denominator / discovery** | Subdomain count, CT history | **Not scored at all.** It *is* the size measure |

---

## Master table — all 35 signals

Legend for *Changes the score?*: **No** · **No — exposure only** (denominator, not firmographic) ·
**Leaves Posture** (routed to another dimension) · **Yes**

The last column carries a **concrete real-world anchor** — the incident, measurement, or named
instrument the verdict rests on — followed by the honest strength of that support.

### Cyber Hygiene

| Signal | Class | Changes the score? | What *does* drive it | Where company context goes instead | Real-world anchor (evidence) |
|---|---|---|---|---|---|
| **SPF** | B | **No** | Record validity and syntax | Benchmark (sector adoption); report sending-service count as context | dmarcian's Sept 2025 survey of **713 US government email domains found 60% with SPF errors** — missing records, invalid syntax, duplicates, or breaching the 10-lookup limit — on *mandated, audited, high-scrutiny* domains. Budget was never the binding constraint. *(Moderate)* |
| **DKIM** | B | **No** | Key length, confirmed signing | Observability gap → **Confidence** | **Google and Yahoo's Feb 2024 bulk-sender rules** made DKIM effectively mandatory above 5,000 messages/day — a market mandate that binds a ten-person startup and a bank identically. *(Weak–Moderate)* |
| **DMARC** | B | **No** | Policy band: reject > quarantine > none > absent | **Benchmark + Compliance Gap** — this is where "$5B bank has no excuse" is expressed | **EasyDMARC 2026: Fortune 500 at 95% adoption and 62.7% `p=reject`; Inc. 5000 at 15.2% `p=reject`.** The large firm is already the better performer, so a big vendor without DMARC is a ~4th-percentile outlier *in its own cohort* — the benchmark says this without a multiplier. FBI IC3 2025 puts BEC losses at **$3.05B**. *(Strong on adoption, Moderate on breach link)* |
| **DNSSEC** | B | **No** | Presence / validity — at Low or Informational weight only | Benchmark. Adoption is ~18%; penalising absence penalises the norm | **PowerDMARC's 2026 US analysis: 18.0% DNSSEC adoption (MTA-STS 1.7%).** A control absent in four-fifths of the population cannot carry real weight without scoring conformity rather than risk — and several large operators decline it deliberately, because misconfigured DNSSEC fails *closed* and takes the domain offline. *(Weak — say so in the report)* |
| **CAA** | B | **No** | Presence | Benchmark. No published breach correlation | The threat is real but rare: **Symantec's 2015 issuance of unauthorised test certificates for google.com**, which ultimately cost the CA Chrome's trust, is the class of event CAA constrains. CA/B Forum obliges **CAs** to honour CAA — no framework obliges domain owners to publish it. *(Weak — no published breach correlation)* |
| **TLS version** | **P** | **No — exposure only** | Share of hosts non-conforming, + **dispersion** across the estate | Regulatory expectation → **Compliance Gap** (PCI, RFC 8996, SP 800-52r2) | **PCI DSS v3.2 required TLS 1.0 disabled by 30 June 2018; RFC 8996 (2021) moved TLS 1.0/1.1 to Historic; NIST SP 800-52r2 binds federal agencies and contractors.** These are dated, named obligations — which is exactly why a PCI-attesting merchant still negotiating TLS 1.0 is a *Compliance Contradiction*, not a heavier TLS penalty. *(Strong on standards, Moderate on exploitation)* |
| **Cipher suites** | P | **No — exposure only** | Broken (RC4/EXPORT/NULL) vs merely deprecated | Benchmark | **FREAK and Logjam (2015)** showed export-grade suites were directly breakable; **POODLE (2014)** did the same for SSLv3 CBC. Nothing comparable exists for TLS 1.2 CBC suites — which is why collapsing "broken" and "deprecated" into one severity overstates the second. *(Moderate)* |
| **Certificate validity** | **P** | **No — exposure only** | Renewal failure *rate*. **Highest-priority normalization in the model** | Benchmark | **Equifax, 2017: an expired certificate on a traffic-inspection device left encrypted traffic uninspected for ~19 months**, which is why the intrusion ran undetected for 76 days. **Ericsson, Dec 2018: one expired certificate took O2 UK offline for ~32M subscribers.** Expiry is a *process* failure with a hard deadline the organisation missed — the cleanest external hygiene proxy there is. *(Strong)* |
| **HSTS** | P | **No — exposure only** | Asset *function* (auth/payment endpoint ≫ static page) | Benchmark | HSTS exists because of **Moxie Marlinspike's sslstrip (2009)**, which needs an active network position. Browser HTTPS-first defaults have since absorbed most of that risk — arguing for low weight, and for weighting a login portal far above a brochure page. *(Weak–Moderate)* |
| **CSP** | P | **No — exposure only** | Policy *strength*, not presence (`unsafe-inline` ≈ worthless) | Higher relevance for e-commerce → Compliance Gap (PCI 4.0 scripts) | **British Airways, 2018: a Magecart skimming script on the payment page compromised ~380,000 card transactions; the ICO fined BA £20M.** PCI DSS v4.0 requirements 6.4.3 and 11.6.1 exist because of this attack class — and they key off *page type*, not company size. *(Moderate for payment contexts, Weak generally)* |
| **X-Frame-Options** | P | **No** | Absence — suppressed entirely when CSP `frame-ancestors` present | — | The header was **superseded by CSP `frame-ancestors` in CSP Level 2 (2014)**; W3C and MDN both direct implementers there. Flagging its absence without checking CSP manufactures a false positive — and false positives are what vendors dispute. *(Weak)* |
| **security.txt** | B | **No** | Presence, positive-only, Informational–Low | Benchmark (tech/SaaS adopt more); BOD 20-01 / EU CRA scope → Compliance Gap | **RFC 9116 (2022)** defines it and CISA's coordinated-disclosure guidance recommends it — but it is a static text file, trivially published and trivially spoofed. No study links its presence to lower compromise likelihood. It is cheap to *measure*, which is precisely why its weight tends to drift upward unguarded. *(Speculative)* |

### Digital Footprint

| Signal | Class | Changes the score? | What *does* drive it | Where company context goes instead | Real-world anchor (evidence) |
|---|---|---|---|---|---|
| **Number of subdomains** | **D** | **Not scored** | Nothing — it *is* the exposure denominator `D` | Score *dangling/takeover-vulnerable* subdomains instead, normalized | **SecurityScorecard scores every issue as a modified z-score where "z = 1 when the number of findings equals the mean for organizations with the same size Digital Footprint."** The industry's largest rater treats footprint as the denominator, never the numerator — because a 2,000-subdomain enterprise is not 200× riskier than a 10-subdomain startup, it is 200× larger. *(Strong)* |
| **CT history** | **D** | **Not scored** | Discovery input only, always liveness-validated | Old firms have decades of dead CT entries — never count history as current surface | **Chrome has required all publicly-trusted certificates to be CT-logged since April 2018**, which is what makes CT a near-complete discovery source — and also why a 20-year-old company's log history is thick with long-dead hosts. Counting history as current surface systematically inflates old and large vendors. *(Strong, methodologically)* |
| **Shadow assets** | P | **No — exposure only** | Ratio `shadow / total discovered` | Age and M&A intensity flow through the *observable* — do not double-count with a multiplier | **Verizon DBIR 2025: edge devices and VPNs rose from 3% to 22% of exploitation targets in one year**, with only ~54% fully remediated (median 32 days). **MOVEit (2023)** was one forgotten internet-facing file-transfer appliance repeated across 2,700+ organisations. Attackers hunt forgotten infrastructure — this is the signal their behaviour validates most directly. *(Strong conceptually, Moderate in published correlation)* |

### Breach & Compromise

| Signal | Class | Changes the score? | What *does* drive it | Where company context goes instead | Real-world anchor (evidence) |
|---|---|---|---|---|---|
| **Public breach history** | C (+Posture) | **Slightly** — but not by firmographics | Event **recency**, **recurrence**, **root-cause repetition**, magnitude relative to scale | Disclosure regime → **Confidence**; sector cost → **Impact** | **T-Mobile US disclosed breaches in 2018, 2019, 2020, 2021 and 2023** — the canonical case for recurrence outweighing recency. Bitsight's published methodology applies an incident adjustment that "decays over time, consistent with the empirical evidence that past incidents are predictive of future risk but with diminishing relevance as time passes." *(Strong)* |
| **Exposed data types** | **C** | **Leaves Posture** | Nothing in Posture — zero effect | **Impact / Vendor Tier**, by data sensitivity and *your* engagement | **IBM/Ponemon 2025: healthcare $7.42M per breach — highest for the fourteenth consecutive year — against public sector at $2.86M.** That spread is entirely about what data was held, not about how well the organisation was defended. It is an impact fact, so it belongs in the impact model. *(Strong)* |
| **KEV** | P | **No — for anyone** | KEV membership + days past CISA deadline | Nowhere. **The strongest "no adjustment" case in the study** — automated exploitation does not consult Crunchbase | **Bitsight TRACE, across 1.4M organisations: over a third had at least one KEV-catalogue vulnerability in 2023, and 60% of KEVs remained unremediated past CISA's BOD 22-01 deadlines.** The failure is universal across every size band, and mass-exploitation campaigns (Log4Shell, MOVEit) scan indiscriminately. *(Strong)* |
| **CVEs** | P | **No — exposure only** | Confirmability; heavily down-weighted vs KEV/EPSS | Note the bias: banner-inference penalises enterprise backporting (RHEL/LTS) | **Jacobs et al.: remediating everything at CVSS 7+ means addressing ~50.7% of all published CVEs to catch 74.6% of what is actually exploited — roughly 6% efficiency.** Worse for fairness: enterprises on backported distributions (RHEL, Ubuntu LTS) show patched software behind old version banners, so unnormalised banner-inferred counting penalises the *enterprise-standard* practice. *(Strong — that raw counts predict poorly)* |
| **CVSS** | Modifier | **No** | Intrinsic severity as a *descriptor* | Environmental metrics need internal knowledge — **do not fabricate them from firmographics** | **FIRST's own specification** defines Base metrics as intrinsic and constant across environments, and puts context in the *Environmental* group — which requires asset criticality and compensating-control knowledge an outside-in rater does not have. Inferring a bank's environmental modifiers from the fact that it is a bank is the exact unfounded judgement this study rules out. *(Strong, on its limitations)* |
| **EPSS** | Modifier | **No — structurally cannot** | Global exploitation probability | Multiplying a probability by a firmographic yields a probability of nothing | **EPSS v4 reaches coverage comparable to a CVSS 7+ strategy while prioritising ~6% of vulnerabilities, at ~47% efficiency versus ~6%** (Cyentia/FIRST). It is a calibrated probability with no organisational term in it — scaling it by revenue produces a number that is no longer a probability of anything. *(Strong)* |

### Governance

| Signal | Class | Changes the score? | What *does* drive it | Where company context goes instead | Real-world anchor (evidence) |
|---|---|---|---|---|---|
| **Published security program** | C | **Leaves Posture** | Positive-only, never a penalty | **Assurity.** Penalising absence encodes a marketing-budget bias | **NIS2 Article 20 requires management-body approval and oversight of security measures — internal governance, not a public page.** No framework anywhere requires publishing one. What a trust centre reliably measures is marketing maturity: SaaS vendors publish them as competitive necessity, manufacturers and non-profits rarely do. *(Speculative)* |
| **Vulnerability disclosure policy** | B | **No** | Presence of a real intake process (≠ funded bug bounty) | BOD 20-01 / EU CRA scope → **Compliance Gap** | **CISA BOD 20-01 (2020) requires every US federal civilian agency to publish a VDP**, citing ISO/IEC 29147 and 30111; the **EU Cyber Resilience Act** extends disclosure duties to suppliers in the EU from 2026. Note the cost asymmetry the model must not blur: a *VDP* is a policy plus an inbox; a *bug bounty* is a budget line. *(Moderate)* |
| **Security contact** | B | **No** | Presence — **merge with security.txt** | Three signals for one fact silently triple-weights Governance | RFC 9116's `Contact:` field, a VDP page, and a published security address are usually **the same fact observed three ways**. Under flat penalty accumulation that fact is charged three times, quietly making Governance heavier than any deliberate weighting decision would have made it. *(Weak)* |

### Business

| Signal | Class | Changes the score? | What *does* drive it | Where company context goes instead | Real-world anchor (evidence) |
|---|---|---|---|---|---|
| **Domain age** | C | **Leaves Posture** | — | **Entity Verification gate.** Aged domains are purchasable — any weight here is a weight an adversary can buy | **Expired-domain marketplaces sell 10- and 20-year-old domains for a few hundred dollars, and threat actors are among the most active buyers** — precisely because age defeats naive reputation scoring. Its one honest use is shell-entity screening: a six-week-old domain, privacy-protected WHOIS, no entity record, no corroborating footprint. That is a fraud gate with human review, not a penalty. *(Weak for security, Moderate for fraud)* |
| **Domain registration quality** | B | **No** | Registrar lock, expiry buffer | Do **not** penalise privacy-protected WHOIS — GDPR-era default; that is geographic bias in disguise | **The DNSpionage and Sea Turtle campaigns (2018–19) hijacked government and telecom domains at the registrar and registry layer** — serious enough that CISA issued **Emergency Directive 19-01**. Registrar lock is free and a checkbox; WHOIS privacy, by contrast, is the GDPR-era default, so scoring it as a negative penalises European registration. *(Weak–Moderate)* |
| **Legal entity status** | C | **Leaves Posture** | — | Counterparty diligence | No security framework — NIST, ISO 27001, CIS, NIS2 — treats company registration standing as a security control. It is a genuine counterparty-risk fact and a non-fact about compromise likelihood. *(N/A for security)* |
| **Company age** | C | **Leaves Posture** | — | **Benchmark covariate + Bayesian prior only.** No authoritative source scores by founding date | **The evidence here is an absence, and it is worth stating as one: not one of Bitsight, SecurityScorecard, RiskRecon, Cyentia, NIST, ENISA or CISA scores or normalises by founding date.** Corroborating it, Cyentia's survival analysis finds "not much difference in fix speeds between small, medium, and large organizations" — legacy debt and program maturity largely cancel. *(Absent — do not fill the gap with intuition)* |
| **Company continuity** | C | **Leaves Posture** | — | Separate **Continuity** dimension | **DORA and NIS2 both require supply-chain and continuity assessment as an obligation distinct from cybersecurity risk management** — the regulators themselves keep the two apart. Financial distress does degrade security, but it surfaces as observable technical decay the model already catches. *(Weak for direct security correlation)* |

### Compliance

| Signal | Class | Changes the score? | What *does* drive it | Where company context goes instead | Real-world anchor (evidence) |
|---|---|---|---|---|---|
| **ISO certifications** | C | **Leaves Posture** | Positive presence only; record scope + expiry | **Assurity.** Penalising absence is a tax on audit budget — the most demographically biased element available | **Certified organisations are breached routinely, because an ISO 27001 certificate attests that an ISMS was audited against a declared scope — and Statements of Applicability are frequently narrow.** A certificate whose SoA excludes the product you are buying is not evidence about that product. Certification is a purchase with a calendar cost; a five-person team with excellent engineering and no certificate is not measurably likelier to be compromised. *(Weak for breach correlation, Strong for procurement relevance)* |
| **SOC reports** | C | **Leaves Posture** | Positive-only | **Assurity.** Type II needs a 6–12 month window — structurally impossible under 1 year old. US-centric → geographic bias | **A SOC 2 Type II requires a 6–12 month observation window, so it is *structurally impossible* for a company under a year old** — penalising its absence at a startup penalises the passage of time. And because SOC 2 is US-centric while European vendors hold ISO, penalising absence is also a geographic bias in disguise. The value is in the exceptions listed, not the yes/no. *(Weak for breach correlation)* |
| **Regulatory disclosures** | C→Posture | **No in Posture — Yes in Confidence** | The disclosed event itself | **Confidence, adjusted by disclosure regime.** A clean record at a private firm is weaker evidence than at an SEC registrant | **SEC Item 1.05 8-K material-incident disclosure (effective Dec 2023) binds registrants only; private companies below notification thresholds may have breaches that never surface at all.** So "no disclosed breaches" at a private vendor and at an SEC registrant are *different quantities* — a coverage fact, which is why the correction belongs in Confidence and not in the score. *(Strong for the bias; the correction is rarely implemented anywhere)* |

### Reputation

| Signal | Class | Changes the score? | What *does* drive it | Where company context goes instead | Real-world anchor (evidence) |
|---|---|---|---|---|---|
| **Regulatory enforcement** | C (+Posture) | **No in Posture — Yes in Confidence** | Adjudicated, security-related actions only | **Confidence**, for enforcement-regime exposure — regulators pursue large visible targets | **The ICO's security fines land on large, visible names — British Airways £20M, Marriott £18.4M** — because regulators pursue greater harm, greater deterrent value and better cost recovery. A clean enforcement record at a small private vendor is therefore *much weaker evidence* than the same record at a supervised entity; treating them alike silently favours small and unregulated vendors. *(Moderate)* |
| **Government investigations** | C | **Leaves Posture** | — | Disclose as context. Scoring allegations invites defamation exposure | An open investigation is an **allegation, not a finding**, and carries the same large-target selection bias as enforcement, amplified. The **US Chamber's Principles for Fair and Accurate Security Ratings** require ratings be "empirical, data-driven, or notated as expert opinion" — scoring an unadjudicated allegation fails that test and creates defamation exposure. *(Weak)* |
| **Verified adverse media** | C | **Leaves Posture** | — | Separate **Reputational Exposure** view, normalized by baseline media volume. **Most size-confounded signal in the catalogue** — any raw count penalises fame | **A consumer brand and a private B2B vendor suffering identical incidents generate coverage differing by orders of magnitude** — media volume tracks visibility, not security quality. Any raw article count is therefore a fame penalty wearing a risk label, and it carries the highest false-positive and dispute risk of the 35. *(Weak)* |

---

## Tally

| | Count |
|---|---|
| Signals where **company age** changes the score | **0 of 35** |
| Signals where **revenue / headcount / market cap** changes the score | **0 of 35** |
| Signals where **measured exposure** changes the score (mandatory denominator) | **10 of 35** |
| Signals where **industry** matters — all into benchmark, Compliance Gap, or Impact, never severity | **12 of 35** |
| Signals where a firmographic legitimately moves **Confidence** | **3** (regulatory disclosures, enforcement, DKIM observability) |
| Signals that should **leave Posture entirely** | **11** |

Revenue appears four times across the whole catalogue: three times as a **bias to correct**
(ISO/SOC audit budget, enforcement selection, adverse-media volume) and once as *magnitude relative
to scale* inside breach history — which is a ratio, not a multiplier.

---

## The three flagship questions, answered

**"Should a 20-year-old company be penalised more than a 1-year-old startup for TLS 1.0?"**
No. The exploit does not know the incorporation date, and the premise is contested in both
directions — older firms carry more legacy debt *and* more mature programs, and Cyentia finds no
meaningful size difference in remediation speed. The better variable is **dispersion**: a vendor with
200 hosts on TLS 1.3 and one on TLS 1.0 is showing you an unmanaged, forgotten asset — a genuinely
worse indicator than a small estate uniformly on TLS 1.2. Dispersion is computable, firmographic-free,
and cannot be gamed by misreporting a founding date.

**"Should a $5B bank be penalised more than a 10-person SaaS for missing DMARC?"**
No, and the premise inverts twice. Empirically, Fortune 500 sits at 95% DMARC adoption and 62.7% at
`p=reject` versus Inc. 5000 at 15.2% — so a large firm without DMARC is *already* a ~4th-percentile
outlier in its own peer group, and the **benchmark delta says so without any multiplier**. On cost,
reaching `p=reject` at a Fortune 500 means inventorying decades of sending services across dozens of
business units; at a ten-person SaaS it is one afternoon. The large firm's task is harder and it does
it more often. The intuition is about **culpability**, not probability — real, worth surfacing, and
belonging in the benchmark and the narrative, not the arithmetic.

**"Is an old breach less concerning for a company that has since matured?"**
Yes — but *maturity* is not observable from outside, so do not proxy it with company age. Three
observable variables are all better: **recency** (already handled by age decay), **recurrence**
(incidents in 2019, 2022 and 2025 should not decay like one 2019 incident), and **root-cause
repetition** (two credential-stuffing incidents are far stronger evidence of an unfixed systemic
weakness than two unrelated ones). Prefer the direct measurement to the proxy.

---

## The one change that is mandatory, and it runs opposite to intuition

The current model accumulates absolute penalties with no denominator, which means it **already
penalises large vendors severely — by accident**:

| | Hosts | Expired certs | Failure rate | Current penalty (Medium = 8) |
|---|---|---|---|---|
| Vendor A | 4 | 2 | **50%** | −16 |
| Vendor B | 900 | 9 | **1%** | **−72** (category floored) |

Vendor B has fifty-times better certificate management and scores dramatically worse. The model is
measuring host count, not hygiene. Both major raters solved this publicly a decade ago — Bitsight
normalizes by "employee count, magnitude of digital footprint, overall count of observations"
explicitly so ratings do not "unfairly penalize large companies"; SecurityScorecard's entire model is
a modified z-score where "z = 1 when the number of findings equals the mean for organizations with the
same size Digital Footprint."

So: *should larger organizations receive larger penalties because they have more resources?* **They
already do, accidentally and massively. The first priority is to stop that** — not to add more of it
deliberately.

---

## Why the answer is "no" so consistently

Three reasons, each sufficient on its own:

1. **Probability ≠ culpability.** A posture score that mixes "how likely is compromise" with "how
   harshly should we judge this" can never be validated against outcomes, because there is no outcome
   corresponding to deservingness. Once unvalidatable, it is also undefendable to a vendor who disputes
   it.
2. **Comparability is the whole point.** If 72 means one thing for a startup and another for a bank,
   the threshold "we don't onboard below 65" is meaningless, portfolio aggregation is invalid, and a
   vendor's score moves when it crosses a revenue band without any change in its security.
3. **The effect is usually already observed directly.** Legacy debt manifests as detected legacy
   protocols, expired certs, and shadow assets. Adding an age multiplier on top double-counts the same
   underlying cause.

---

## A note on the anchors

Each anchor is the strongest published thing found for that signal — and where nothing strong exists,
the cell says so rather than manufacturing support. **Six signals rest on weak or absent evidence and
are marked as such**: DNSSEC, CAA, X-Frame-Options, security.txt, published security program, and
company age. That is a finding in its own right, not a gap to be papered over — those six should carry
low weight, or none, precisely because the evidence for them is thin.

Figures quoted from vendor reports (EasyDMARC, Bitsight TRACE, PowerDMARC, IBM/Ponemon, dmarcian,
Cyentia) restate the source's own published claims and are proprietary datasets that cannot be
independently reproduced. Verify each against the current edition before any of this reaches a client
deliverable — several of these reports recalibrate annually.

---

**Full reasoning, citations, and the revised model:** `context-aware-vendor-risk-scoring-study.md`
(evidence review and per-signal analysis) and `new_research_meth.md` (§6 matrix, §7 critique,
§9 revised model, §10 tiered recommendations, §11 migration plan).
