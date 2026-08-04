# Should External Security Signals Be Interpreted Differently by Company Type?

### A research-backed evaluation of context-adjusted vendor cyber risk scoring, with a critique of the Posture/Confidence methodology and a proposed revision

**Prepared as:** third-party cyber risk research study
**Date:** July 2026
**Scope:** 35 external signals; company age, size, revenue, industry, regulatory status, geography, exposure, ownership structure

---

## 1. Executive Summary

### 1.1 The headline answer

**The importance of a security signal should almost never vary with a vendor's age, revenue, headcount, or market cap. It should vary with the vendor's measured exposure, and the consequences of its failure should vary with the buyer's engagement.** Those are three different adjustments, and conflating them is the central error the proposed context-adjustment would introduce.

Decomposed:

| Question | Correct home in the model | Should firmographics touch it? |
|---|---|---|
| How likely is this vendor to be compromised? | **Posture** | **No** — except exposure normalization |
| How much of my attack surface / data does the vendor hold? | **Impact / Vendor Tier** | Yes, but *my* firmographics and the engagement's, not the vendor's |
| How much do I trust the measurement? | **Confidence** | Weakly — coverage is partly a function of size |
| How well documented is the vendor's own assurance? | **Assurity** | Yes, and this is where audit-budget effects belong, quarantined |
| Is this normal for a company like this? | **Benchmarking** | **Yes — this is exactly what benchmarking is for** |
| What should I do about it? | **Recommendations / Tier** | Yes |

The intuition driving the research question — *"a $5 billion bank with no DMARC looks more negligent than a $500K startup with no DMARC"* — is correct, and it is a statement about **culpability**, not about **probability**. Negligence is a legal and commercial concept. Risk is a probabilistic one. A posture score that mixes them stops being a prediction of anything, becomes non-comparable across vendors, and cannot be validated against outcomes. The negligence signal is real and worth surfacing — but it belongs in the benchmark delta and the narrative, not in the arithmetic that produces the number.

### 1.2 The one adjustment that is mandatory, and it runs opposite to intuition

The current model — absolute penalties accumulated from a starting score of 100, with no denominator — contains a **severe, undocumented size bias that penalizes large vendors for being large**. This is the most consequential finding in this study.

Consider two vendors:

- **Vendor A:** 4 internet-facing hosts, 2 with expired certificates → **50% failure rate**
- **Vendor B:** 900 internet-facing hosts, 9 with expired certificates → **1% failure rate**

Under the current formula (Medium = 8 points each), Vendor A loses 16 points and Vendor B loses 72 points and is effectively floored on that category alone. Vendor B has a *fifty-times better* certificate management practice and scores dramatically worse. The model is measuring host count, not hygiene.

Both major ratings vendors solved this a decade ago, explicitly and publicly. Bitsight states that "large companies will typically have more findings than smaller companies," and that they normalize ratings by organization size specifically so that ratings do not "unfairly penalize large companies," comparing organizations "using applicable notions of size — e.g. employee count, magnitude of digital footprint, overall count of observations." SecurityScorecard's entire scoring model is a modified z-score in which "z = 1 when the number of findings equals the mean for organizations with the same size Digital Footprint," and its periodic recalibrations exist "to normalize scoring between organizations of different sizes, with differing digital footprints."

So the answer to *"should larger organizations receive larger penalties for basic security failures because they have more resources?"* is: **they already do, accidentally and massively, and the first priority is to stop that** — not to add more of it deliberately.

### 1.3 The taxonomy that resolves most of the question

Not all signals behave the same way under scaling. Sorting them into three classes answers most of the per-signal question mechanically:

**Class P — Prevalence signals** (count scales with asset inventory): certificate validity, TLS version, cipher suites, HSTS, CSP, X-Frame-Options, CVEs, KEVs, shadow assets, subdomain hygiene.
→ **Must be measured as a rate with an exposure denominator.** Size adjustment is mandatory, and its purpose is bias removal, not leniency.

**Class B — Binary policy signals** (one decision at org level, cost roughly independent of size): DMARC, SPF at apex, DKIM policy posture, DNSSEC, CAA, security.txt, VDP, published security contact.
→ **Identical treatment for every organization.** These cost engineering hours, not headcount. The empirical record refutes the "small companies can't afford it" defence and the "large companies have no excuse" framing equally.

**Class C — Consequence and assurance signals** (say more about impact or about the quality of evidence than about likelihood): breach history, exposed data types, ISO/SOC certifications, regulatory disclosures, adverse media, legal entity status, company continuity.
→ **These do not belong in posture at all.** They belong in Impact, Assurity, or Confidence.

### 1.4 What the empirical record actually supports

| Claim | Verdict | Evidence |
|---|---|---|
| Larger organizations experience more incidents | **Supported (frequency), and it is an exposure effect** | Cyentia IRIS 2025: adjusted for organization count, the largest corporations experience incidents at a rate 620× higher. IRIS 2022: firms >$100B revenue are 32× more likely to have multiple incidents in one year |
| Larger organizations remediate faster because they have resources | **Not supported** | Cyentia: "there's not much difference in fix speeds between small, medium, and large organizations (based on employee size)" — more resources, but proportionally more to patch |
| Larger organizations have better basic email hygiene | **Supported, and it undercuts the negligence argument** | EasyDMARC 2026: Fortune 500 at 95% DMARC adoption, >80% at enforcement, 62.7% at p=reject; Inc. 5000 at 15.2% p=reject with over half still at p=none |
| Industry base rates for hygiene differ materially | **Strongly supported** | RiskRecon: large banks average 0.5 critical-severity issues per 100 high-value internet-facing systems; universities average 6.3 — a 12× spread |
| Breach consequences differ by industry | **Strongly supported** | IBM/Ponemon 2025: healthcare $7.42M (14th consecutive year highest), financial $5.56M, industrial $5.00M, retail $3.54M, public sector $2.86M |
| Past incidents predict future incidents, with decay | **Supported** | Bitsight applies an incident adjustment scaled to severity and organization size that "decays over time, consistent with the empirical evidence that past incidents are predictive of future risk but with diminishing relevance as time passes" |
| Company *age* predicts security posture | **No published evidence found** | No authoritative source in this review scores or normalizes by founding date or domain age. Treat as unsupported |
| Exploit-likelihood beats severity for vulnerability weighting | **Strongly supported** | Jacobs et al.: a CVSS 7+ strategy requires remediating ~50.7% of CVEs for 74.6% coverage at ~6% efficiency; EPSS v4 reaches comparable coverage at ~6% effort and ~47% efficiency |

### 1.5 Top ten recommendations

1. **Add an exposure denominator to every prevalence-class signal.** Highest-impact change in this study. Removes an existing bias rather than adding a new one.
2. **Do not add firmographic penalty multipliers to Posture.** No revenue, headcount, market-cap, or company-age multiplier on severity or penalty.
3. **Replace linear penalty subtraction with bounded log-odds accumulation** run through a logistic transform. The current model floors at zero after roughly 2.5 criticals and loses all discriminating power in the bottom quartile.
4. **Make weights explicit.** "No category weights, categories emerge naturally" is not the absence of weighting — it is undocumented weighting determined by how many detectors you happen to have written per category.
5. **Move ISO/SOC/attestations out of Posture into Assurity.** Penalizing a missing SOC 2 report is a tax on audit budget with no demonstrated link to compromise likelihood, and it is the single most demographically biased element you could include.
6. **Introduce an Expectation Gap as an output, not an input:** `EG = Posture − E[Posture | peer group]`. This delivers everything the "$5B bank should look worse" intuition wants, without contaminating the score.
7. **Add a Compliance Contradiction finding class.** "Vendor asserts PCI DSS compliance and negotiates TLS 1.0" is not a more severe TLS finding — it is a distinct, high-signal finding about the reliability of the vendor's own attestations.
8. **Replace the hard 40% "Ghost" cutoff with coverage-scaled prediction intervals** plus a published, explicitly-labelled shrunk estimate. The current cliff is gameable: making attribution difficult is a way to disappear.
9. **Rebuild the mitigation multiplier.** A flat, human-granted ×0.6 with no evidence taxonomy is the most manipulable element in the current design.
10. **Never adjust by geography or nationality in Posture.** Weakly predictive, ethically fraught, and legally exposed. Surface jurisdiction as a disclosed attribute of the engagement instead.

### 1.6 Final answer to the deliverable-9 question

| Component | Should company age / size / revenue / maturity affect it? |
|---|---|
| **Posture** | **No.** Only *measured exposure* enters posture, as a denominator |
| **Severity** | **No.** Severity is a property of the technical condition |
| **Penalty multiplier** | **No** for firmographics; **Yes** for evidence-quality and exposure normalization |
| **Confidence** | **Marginally.** Coverage is easier to achieve for small footprints; disclose, don't adjust |
| **Assurity** | **Yes.** This is the correct quarantine for audit-budget and program-maturity effects |
| **Benchmarking** | **Yes — this is the primary and correct home** |
| **Vendor Tier** | **Yes**, driven mainly by the buyer's exposure to the vendor |
| **Risk recommendations** | **Yes.** Remediation advice should absolutely be size- and sector-aware |

---

## 2. Conceptual Foundation

### 2.1 Three quantities that must not be merged

Any vendor risk decision is an expected-loss judgment:

```
E[Loss] = P(vendor compromised) × P(compromise reaches me | vendor compromised) × Loss(me | reached)
```

- **Posture** is an estimator of the first term. It is a property of the vendor.
- **Vendor Tier / Impact** covers the second and third terms. These are properties of *the relationship*, not of the vendor. A hospital and a coffee shop using the same CRM face different consequences from an identical vendor compromise.
- **Confidence** is not part of the equation at all — it is a statement about the standard error of the first term.

The proposed context adjustments almost all belong to terms two and three, and the proposal is to apply them to term one. That is the structural error.

### 2.2 The negligence/probability distinction

The framing question — "does a 20-year-old company deserve a *larger penalty*" — uses the word *deserve*. Desert is a moral concept. Three distinct things get bundled:

1. **Probability** — is a compromise more likely here? (Empirical question, testable against outcomes.)
2. **Culpability** — should we judge this organization more harshly? (Normative question, not testable.)
3. **Expectation** — is this unusual for this kind of company? (Statistical question, answered by benchmarking.)

A rating that answers (1) can be validated: score cohorts, observe incident rates, measure lift. Bitsight publishes exactly this kind of validation — 27,458 companies over two years against 2,671 breach events, showing organizations rated 700+ at under 1% breach probability versus nearly 3% for those below 500. A rating that mixes (1) and (2) cannot be validated at all, because there is no outcome corresponding to "deservingness." Once you cannot validate, you cannot defend the score to a vendor who disputes it, and you cannot improve it.

**Recommendation:** answer (1) in Posture, answer (3) in Benchmarking, and let the human reading the report make judgment (2) with both numbers in front of them.

### 2.3 Why comparability is the whole point of a score

A vendor risk score exists to let a procurement team rank vendors and set thresholds. If a 72 means "72 for a startup" and a different 72 means "72 for a bank," then:

- The threshold "we do not onboard below 65" becomes meaningless.
- Portfolio aggregation becomes invalid — you cannot average scores computed on different scales.
- Trend analysis breaks when a vendor crosses a size or revenue band and its score moves without any change in its security.
- Dispute handling becomes impossible — the vendor cannot verify a score whose scale depends on their own financials.

This last point is not merely a design preference. The **U.S. Chamber of Commerce Principles for Fair and Accurate Security Ratings** (2017), explicitly modelled on the Fair Credit Reporting Act, require transparency into methodology, a dispute and appeal process, and that ratings be "empirical, data-driven, or notated as expert opinion." A revenue-scaled severity multiplier derived from third-party firmographic data that the vendor cannot see, verify, or correct fails all three.

### 2.4 The one place where regulators explicitly endorse size-based expectations

There is a genuine counter-argument, and it comes from law rather than data. **NIS2 Article 21(1)** requires "appropriate and proportionate" measures, and states that when assessing proportionality, "due account shall be taken of the degree of the entity's exposure to risks, the entity's size and the likelihood of occurrence of incidents and their severity, including their societal and economic impact." **DORA** applies requirements proportionately to entity size, nature, scale, complexity of ICT activities, and risk profile, with a simplified framework available to microenterprises under Article 16.

So European regulators do explicitly scale *obligations* by size. Two observations:

1. Note the ordering: **exposure first, size second.** Even the regulators put measured exposure ahead of headcount.
2. Note the direction: proportionality **reduces** obligations for small entities; it does not **increase** penalties for large ones. And it modifies the *required control set*, not the *risk assessment*.

This maps cleanly onto the recommendation: proportionality belongs in **expectations and recommendations** (what should this vendor be doing, what will regulators require of them) — the Compliance and Benchmarking dimensions — and not in the estimator of compromise likelihood.

### 2.5 The "aggregate confusion" warning

Berg, Kölbel and Rigobon's study of ESG ratings found average pairwise correlation across major providers of roughly 0.53 (updated to ~0.56 in later work), versus over 0.99 between Moody's and S&P credit ratings. The cause was not data scarcity — it was divergence in indicator selection, weighting, and scope decisions. Each provider's subjective weighting choices compounded into ratings that reached "not merely different but opposite conclusions" about the same firm.

Every subjective, unvalidated context multiplier added to a security rating moves it from the credit-rating end of that spectrum toward the ESG end. Each individual adjustment feels reasonable; the aggregate is noise. This is the strongest general argument for parsimony in context adjustment: **add only adjustments you can back-test.**

---

## 3. Empirical Evidence Review

### 3.1 Does organization size predict incidents?

**Yes, for frequency, and the mechanism is exposure.**

Cyentia's IRIS 2025, sponsored by CISA, finds that when adjusted for the number of organizations, the largest corporations experience cyber incidents at a rate 620× higher than the smallest. IRIS 2022 found organizations above $100B in annual revenue are 32× more likely to experience multiple security incidents in a single year. Crucially, the same research finds that while large organizations experience more incidents overall, **smaller organizations often face a greater relative impact when attacks occur** — the loss is smaller in absolute terms but larger relative to the firm.

The correct reading: incident *frequency* scales roughly with attack surface and target attractiveness, both of which are directly measurable from the outside. **Measure the surface, don't proxy it with revenue.** Revenue is a lagging, noisy, often-stale, and frequently unavailable proxy for something you can observe directly in DNS and certificate transparency logs.

### 3.2 Does organization size predict remediation performance?

**No, or only weakly — and this directly refutes the "they have more resources" premise.**

Cyentia's survival analysis of remediation velocity found "not much difference in fix speeds between small, medium, and large organizations (based on employee size)." Their explanation is the correct one: "Large orgs certainly have more resources to throw at the patching problem… but they also have a lot more stuff to patch."

They did find one size-dependent effect worth adopting: the gap between remediation velocity for vulnerabilities *with* known exploits versus those without is **widest for large organizations** — large firms triage harder because they must. This is a maturity signal, but note what it measures: differential prioritization, not raw speed. If you want to capture "operational maturity" from the outside, the measurable version is **whether the vendor's KEV/high-EPSS findings clear faster than its low-EPSS findings** — a within-vendor ratio, entirely free of firmographic input.

That is a genuinely better maturity metric than company age, and it is computable from data you already collect.

### 3.3 Does the "large companies have no excuse" argument survive contact with data?

**No, in the direction the argument assumes.** Large companies are already substantially better at the basic policy controls.

EasyDMARC's 2026 report: 95% of Fortune 500 companies have implemented DMARC, over 80% at enforcement policies, 62.7% at the strictest `p=reject`, with RUA reporting nearly universal at 97.9%. Inc. 5000 companies: 15.2% at `p=reject`, more than half still parked at `p=none`, and only 67.4% using RUA reporting. Globally, Red Sift's December 2025 analysis of 73.3 million domains found only 14.9% with any DMARC record at all and just 2.5% at `p=reject`.

This matters for scoring in two ways:

1. A Fortune 500 without DMARC at enforcement is already a ~4th-percentile outlier within its peer group. **The benchmark delta captures the "no excuse" intuition automatically, with no multiplier required.** This is the empirical demonstration that benchmarking is sufficient.
2. The implementation-difficulty argument runs backwards from the assumption. A Fortune 500 deploying `p=reject` must inventory hundreds of legitimate sending services accumulated over decades. A ten-person SaaS company has one or two. The large firm's task is *harder* and it does it *more often* — which means resource-based leniency for small vendors is not just unvalidated, it is contradicted.

### 3.4 Does industry predict hygiene? Yes — and it's the strongest firmographic effect in the literature

RiskRecon's methodology research is the cleanest published evidence. Analyzing issue rates in the context of both severity and asset value, they found **large banks average 0.5 critical-severity issues per 100 high-value internet-facing systems, while universities average 6.3** — a greater than 12× spread. RiskRecon built its entire rating scale around this, anchoring "good" risk management at the banking benchmark and "poor" at the university benchmark, distributing companies across the scale with a Rayleigh distribution.

Note what RiskRecon did *not* do: they did not apply a multiplier to a bank's findings. They used industry to **calibrate the scale**, then scored everyone on it identically. That is precisely the recommended architecture — industry informs the benchmark, not the arithmetic.

Complementing this on the consequence side, IBM/Ponemon's 2025 Cost of a Data Breach report (600 organizations, 17 industries) shows industry as one of the strongest predictors of breach *cost*: healthcare $7.42M for the fourteenth consecutive year, financial services $5.56M, industrial $5.00M, energy $4.83M, technology $4.79M, retail $3.54M, education $3.80M, public sector $2.86M. A third of breached organizations paid a regulatory fine.

**Interpretation:** industry belongs in two places — peer-group definition (RiskRecon's use) and the impact model (IBM's data). Not in severity.

### 3.5 Does breach history predict future breaches, and should it decay?

**Yes and yes.** Bitsight's published methodology applies a security-incident adjustment where "the overall rating is adjusted downward by an amount that reflects the severity of the incident and the size of the organization," and "this adjustment decays over time, consistent with the empirical evidence that past incidents are predictive of future risk but with diminishing relevance as time passes."

Note the size term. Bitsight scales incident impact by organization size — but in service of normalization (a breach of 200 records at a 200-person firm is a different event from a breach of 200 records at a firm with 200,000 employees), not culpability. The scaling is against the exposure base, consistent with everything else in their model.

This supports the current framework's existing age-decay design. The refinement needed is **recurrence handling**, addressed in §7.

### 3.6 Vulnerability signals: CVSS is a poor prioritizer, exploitability is a good one

Jacobs, Romanosky, Edwards, Adjerid and Roytman's EPSS work quantifies this precisely. A remediation strategy of "fix everything CVSS 7.0 and above" requires addressing roughly 50.7% of all published CVEs, achieves 74.6% coverage of vulnerabilities actually exploited in the following 30 days, and does so at approximately 6% efficiency. EPSS v4 achieves comparable coverage while prioritizing about 6% of vulnerabilities, at ~47% efficiency. Earlier work showed EPSS v3 at 90.4% coverage and 24.1% efficiency at equivalent effort to a CVSS-9.1+ strategy's 33.5% / 6.1%.

On KEV: Bitsight TRACE's analysis of 1.4 million organizations found over a third had at least one KEV-catalog vulnerability in 2023, nearly a quarter of those had five or more, and 60% of KEV vulnerabilities remained unremediated past CISA's deadlines. Verizon's 2025 DBIR found exploitation of vulnerabilities in 20% of breaches (up 34%), with edge devices and VPNs rising from 3% to 22% of exploitation targets — and only about 54% fully remediated over the year, at a median of 32 days.

**Implication for the framework:** the largest available accuracy gain in the vulnerability category is not contextual weighting by company type. It is replacing or supplementing CVSS-derived severity with KEV membership and EPSS probability. That is a bigger predictive improvement than any firmographic adjustment discussed in this study, and it is unambiguously evidence-backed.

### 3.7 The third-party risk context

Verizon's 2025 DBIR, covering over 22,000 incidents and 12,195 confirmed breaches, found third-party involvement in breaches **doubled from 15% to 30%** year over year. Median time to remediate leaked secrets discovered in GitHub repositories was 94 days. This is the case for the product existing; it is also a reminder that the model's job is predicting *whether this vendor becomes someone else's incident*, which is a likelihood question about the vendor's controls, not a fairness question about its size.

### 3.8 Where the evidence is weak or absent — stated plainly

The following are used in commercial scoring but have little or no published breach-correlation evidence at the signal level. This should be reflected in low weights and honest reporting:

- **CAA records** — no published correlation with compromise. Mis-issuance is rare; CAA's protective value is real but small and hard to measure.
- **security.txt / RFC 9116** — a discoverability convenience. No evidence it reduces compromise likelihood. Its value is as a weak positive indicator of program maturity, and it is trivially spoofable (a single static file).
- **X-Frame-Options** — largely superseded by CSP `frame-ancestors`. Flagging its absence alone, without checking CSP, generates false positives.
- **DNSSEC** — adoption is low enough that absence is uninformative. PowerDMARC's 2026 US analysis found 18.0% DNSSEC adoption; MTA-STS at 1.7%. A signal present in under a fifth of the population cannot carry meaningful penalty weight without effectively penalizing the norm.
- **Company age / domain age as maturity proxies** — no authoritative source in this review scores by founding date. Aged domains are purchasable commodities, which destroys the signal's integrity for scoring purposes.
- **Subdomain count in isolation** — a raw count is an exposure measure, not a risk measure. It belongs in the denominator, not the numerator.

I would rather state these as weak than manufacture justification for them.



---

## 4. Signal-by-Signal Analysis

**How to read each entry.** *Class* is P (prevalence — scales with assets, needs a denominator), B (binary policy — one org-level decision), or C (consequence/assurance — belongs outside Posture). *Verdict* is one of **Identical**, **Slightly adjusted**, or **Heavily adjusted**, followed by *where* the adjustment lives. *Evidence* is my honest read of how well-supported the signal's weighting is: Strong / Moderate / Weak / Speculative.

---

### 4.1 Cyber Hygiene

---

#### SPF

**Baseline importance:** Moderate. A prerequisite for DMARC; alone it stops very little, since SPF alignment failures are invisible to recipients without a DMARC policy. Presence is nearly universal — misconfiguration is the more informative finding. dmarcian's September 2025 survey of 713 US government email domains found 60% had SPF errors: missing records, invalid syntax, multiple records on one domain, or records exceeding the 10-DNS-lookup limit — and these were *mandated, audited, high-scrutiny* domains.

**Class:** B (policy at apex) with a P component (per-domain across a portfolio).

**Age:** Unchanged across all bands. A 20-year-old company is more likely to have accumulated a bloated `include:` chain that breaks the lookup limit — that is a *finding*, correctly detected, not a reason to weight the finding differently.

**Revenue / size:** Unchanged. A valid SPF record is one DNS TXT entry. Complexity scales with sender count, not revenue, and the *number of sending services* is directly observable from the record itself — use that, not headcount.

**Industry:** Unchanged for scoring. Finance, government, and healthcare have higher observed adoption; that shows up in the benchmark.

**Regulatory:** PCI DSS v4.0 addresses anti-phishing mechanisms; NIS2 Article 21 covers this under basic cyber hygiene. No framework distinguishes by firm size on this control.

**Attacker perspective:** A broken SPF record is functionally equivalent to no SPF for spoofing purposes; attackers do not check the target's revenue before spoofing it. High-value brands are more attractive spoofing targets, but that is a brand-attractiveness effect, not a control-quality effect.

**Business risk:** Procurement teams and email security vendors care uniformly. Insurers increasingly ask.

**Verdict: Identical.** Score the technical validity of the record. Report `+n sending services` as context.
**Evidence: Moderate.**

---

#### DKIM

**Baseline importance:** Moderate. Externally, DKIM is only partially observable — you can detect selectors via DNS if you know them, and confirm signing only by observing mail. Key length and rotation are the meaningful sub-findings (1024-bit keys still in use are a real weakness).

**Class:** B.

**Age:** Unchanged, with one nuance: legacy 1024-bit keys correlate with older deployments. That correlation is captured by measuring key length directly. Do not infer key length from company age.

**Revenue / size:** Unchanged.

**Industry:** Unchanged for scoring; high-volume senders (retail, marketing-heavy B2C, financial services) have more selectors and thus more surface for a weak key. Detect it, don't assume it.

**Regulatory:** Google and Yahoo bulk-sender requirements (2024) made DKIM effectively mandatory for anyone sending at volume — a market mandate that binds regardless of size.

**Attacker perspective:** Weak DKIM keys are an advanced attack; most spoofing does not require breaking DKIM when DMARC is at `p=none`.

**Business risk:** Low direct procurement salience; matters for deliverability.

**Verdict: Identical.** Low weight for absence (poor observability); moderate weight for confirmed weak keys.
**Evidence: Weak-to-Moderate.** Observability limits make this a Confidence problem as much as a Posture one.

---

#### DMARC

**Baseline importance:** High — the highest-value item in the email authentication cluster, because it is the only one that instructs recipients to act. This is the framework's flagship test case, so it gets extended treatment.

**Class:** B.

**Age:** Unchanged.

**Revenue / size:** **Unchanged in Posture — and this is a considered answer, not a default.** The proposed adjustment ("a $5B company missing DMARC is more negligent than a $500K startup") fails on three grounds:

1. *The empirical premise is inverted.* Large firms are already dramatically better at this: F500 at 95% adoption and >80% enforcement, versus Inc. 5000 at 15.2% `p=reject` with more than half at `p=none`. A large company without DMARC is a rare outlier *within its own peer group*, and the benchmark delta already says so, loudly, without any multiplier.
2. *The implementation-cost premise is inverted.* Reaching `p=reject` at a Fortune 500 means inventorying decades of accumulated sending services across dozens of business units. At a ten-person SaaS it means one afternoon. Charging the small firm less is subsidizing the easier task.
3. *The risk premise doesn't hold either.* Absence of DMARC increases the vendor's exposure to being impersonated *toward your employees*. If anything, a widely-recognized brand is a more effective phishing lure — but that argues for a **brand-recognition/exposure** term (measurable via domain popularity ranking), not a revenue term. If you want that effect, use Tranco rank or equivalent, and be honest that you are measuring impersonation attractiveness, not negligence.

**Industry:** Unchanged for scoring. Massive base-rate differences by sector — US federal at approximately 92% enforcement following BOD 18-01, versus most voluntary sectors far lower — go into the peer group.

**Regulatory:** Genuinely differentiated. PCI DSS v4.0 includes anti-phishing requirements; CISA BOD 18-01 mandates DMARC for US federal civilian agencies and BOD 25-01 extends secure-configuration baselines into M365 and Google Workspace. **This is where the "bank vs startup" intuition is legitimately correct — and the correct expression is a Compliance Gap finding, not a heavier DMARC penalty.**

**Attacker perspective:** Business email compromise is indifferent to victim size in technique. FBI IC3's 2025 report attributed $3.05B in losses to BEC within a total of $20.9B across more than one million complaints.

**Business risk:** Insurers ask about DMARC directly. Procurement teams check it. Brand-holders care most.

**Verdict: Identical in Posture. Heavily adjusted in Benchmarking and Compliance.** Score `p=reject` > `p=quarantine` > `p=none` > absent, with a separate RUA sub-check, identically for every organization.
**Evidence: Strong** on adoption base rates; **Moderate** on direct breach correlation.

---

#### DNSSEC

**Baseline importance:** Low-to-moderate, and this is where I would push back hardest on conventional scoring. DNSSEC protects against cache poisoning and spoofing, but adoption sits at roughly 18% of US domains. A signal absent in over 80% of the population cannot carry a meaningful penalty without penalizing the norm — and penalizing the norm produces a score that measures conformity to an aspirational standard rather than risk.

There is also a genuine dissent worth recording: several large operators have deliberately declined DNSSEC on availability grounds (misconfigured DNSSEC causes hard resolution failures; several major outages have been DNSSEC-related). Penalizing a considered operational decision as a security failing is exactly the kind of judgment a scoring system should be humble about.

**Class:** B.

**Age / revenue / size:** Unchanged. Registrar and DNS-provider support is the binding constraint, not budget.

**Industry:** Government and, in some jurisdictions, finance and telecom show materially higher adoption. Peer group only.

**Regulatory:** Required for US federal (OMB M-08-23 lineage); recommended in several EU national baselines. Not a general mandate.

**Attacker perspective:** DNS hijacking campaigns (e.g. the DNSpionage/Sea Turtle activity) have targeted government and telecom infrastructure specifically. Registrar-account compromise is the more common vector, and DNSSEC does not prevent it.

**Business risk:** Low procurement salience outside government supply chains.

**Verdict: Identical, at low weight — Informational or Low, never Medium.** Consider treating presence as a *positive* signal rather than absence as a penalty.
**Evidence: Weak.** State this in the report.

---

#### CAA

**Baseline importance:** Low. CAA constrains which CAs may issue for a domain. It reduces mis-issuance risk, which is a genuine but rare threat.

**Class:** B.

**Age / revenue / size / industry:** Unchanged throughout. One DNS record; cost is independent of every firmographic.

**Regulatory:** CA/Browser Forum baseline requirements obligate *CAs* to check CAA — not domain owners to publish it. No framework mandates publication.

**Attacker perspective:** Mis-issuance attacks are largely nation-state or CA-compromise scenarios. High-value targets face marginally more risk; the marginal is genuinely small.

**Business risk:** Very low salience.

**Verdict: Identical, Low or Informational weight.**
**Evidence: Weak.** No published breach correlation.

---

#### TLS Version

**Baseline importance:** High. This is the second flagship test case.

**Class:** **P — this is critical.** TLS version findings scale directly with host count. Without a denominator, this signal alone will produce the size bias described in §1.2.

**Age:** **Unchanged as a multiplier — but the question conceals a much better signal.** The proposal that a 20-year-old company deserves a larger penalty for TLS 1.0 than a startup rests on an intuition that is *almost* right, and the correct version is more useful:

- What actually distinguishes the two cases is not founding date but **internal consistency**. A vendor with 200 endpoints on TLS 1.3 and *one* on TLS 1.0 is showing you an unmanaged, forgotten, probably unmonitored asset — which is a genuinely worse risk indicator than a vendor whose entire (small) estate is uniformly on TLS 1.2, because the outlier host is likely outside the change-management process entirely.
- A startup with three hosts all on TLS 1.0 has a default-configuration problem: bad, but visible, uniform, and one config change from fixed.

So the informative variable is **posture dispersion** — the variance of configuration quality across a vendor's estate — not company age. This is computable from data you already collect, it is firmographic-free, it cannot be gamed by misreporting incorporation dates, and it captures precisely the "legacy debt in a mature enterprise" concern that motivated the original question. **I recommend adopting dispersion as a derived signal.** See §7.6.

**Revenue / size:** Unchanged as a multiplier; **mandatory as a denominator.**

**Industry:** Unchanged in severity. Base rates differ (RiskRecon's 12× bank/university spread); that is peer-group material.

**Regulatory:** Sharply differentiated, and this is legitimate context. RFC 8996 (2021) formally deprecated TLS 1.0 and 1.1 to Historic status and is part of BCP 195. PCI DSS required TLS 1.0 disabled by 30 June 2018 under v3.2; v4.0 maintains TLS 1.2 as the minimum and prohibits SSL and TLS 1.1. NIST SP 800-52 Rev. 2 binds US federal agencies and their contractors. **A PCI-attesting merchant negotiating TLS 1.0 is out of compliance with a named, dated requirement — record it as a Compliance Contradiction, not as a heavier TLS finding.**

**Attacker perspective:** Attackers do not select targets by TLS version; they exploit what is reachable. BEAST/POODLE-class attacks require an active network position and are rarely the primary vector. TLS 1.0's practical significance today is more as a *proxy for unmanaged infrastructure* than as a directly exploitable flaw — which reinforces the dispersion argument above.

**Business risk:** High salience. Fails PCI assessments, appears in every questionnaire, and is a common cyber-insurance exclusion trigger.

**Verdict: Identical severity; mandatory exposure normalization; add dispersion as a separate derived signal; route regulatory expectation to a Compliance Gap.**
**Evidence: Strong** on standards; **Moderate** on direct exploitation.

---

#### Cipher Suites

**Baseline importance:** Moderate. Highly variable: RC4, export-grade, NULL, and anonymous suites are serious; CBC-mode suites under TLS 1.2 are a much softer finding.

**Class:** P.

**Age / revenue / size:** Unchanged in severity; **denominator required.** Weak suites correlate with older middleboxes and load balancers, which correlates with organizational age — but again, measure the config, don't infer from the founding date.

**Industry:** Unchanged. Manufacturing, healthcare, and energy carry more embedded and appliance-based endpoints that lag; detect, don't assume.

**Regulatory:** PCI DSS and NIST SP 800-52r2 specify approved suites. FIPS 140-3 environments have stricter constraints.

**Attacker perspective:** Requires network position. Genuinely lower practical priority than the CVSS-style severity ratings usually assigned to it.

**Business risk:** Moderate; scanner-report driven.

**Verdict: Identical, normalized by exposure.** Consider splitting into two severities (broken vs. deprecated-but-not-broken); most scoring models over-penalize the latter.
**Evidence: Moderate.**

---

#### Certificate Validity

**Baseline importance:** High. Expired or invalid certificates on production endpoints are among the cleanest operational-hygiene indicators available externally — they represent a *process* failure with a hard deadline that the organization missed.

**Class:** **P — and the most size-biased signal in the whole model if left unnormalized.** A 1,000-host estate with 99.5% renewal reliability shows five expired certs; a 10-host estate with 80% reliability shows two. Absolute counting rates the disciplined enterprise as 2.5× worse.

**Age / revenue / size:** Unchanged in severity; **denominator mandatory.**

**Industry:** Unchanged. Meaningful base-rate variation — education notably poor, banking notably strong (RiskRecon).

**Regulatory:** Implied under NIS2 Article 21 cryptography-policy requirements, PCI DSS Requirement 4, and effectively all "appropriate technical measures" language.

**Attacker perspective:** Expired certs enable interception in narrow circumstances, but their real significance is what they reveal: nobody is watching that asset. That inference is *stronger* for a large, mature vendor — again a dispersion effect, not an age effect.

**Business risk:** Very high salience — visible to end users, causes outages, embarrasses procurement.

**Verdict: Identical severity, mandatory normalization.** Distinguish expired (high) from self-signed on an internal-purpose host (low) from hostname-mismatch (medium) — the current single "certificate validity" signal is too coarse.
**Evidence: Strong** as a hygiene proxy.

---

#### HSTS

**Baseline importance:** Moderate for sites handling authentication; low for static marketing sites.

**Class:** P.

**Age / revenue / size:** Unchanged in severity; denominator required. **Asset purpose matters far more than company demographics** — this is the RiskRecon asset-value insight applied directly. Missing HSTS on a login portal and missing HSTS on a brochure page are different findings that most models score identically. Fixing that is worth more accuracy than any firmographic adjustment.

**Industry:** Unchanged; relevance tracks the presence of authenticated web surfaces, which is a technology-stack property.

**Regulatory:** Recommended by OWASP, NIST SP 800-52r2 in a web context; not independently mandated.

**Attacker perspective:** Requires network position for SSL-stripping. Modern browser HTTPS-first behaviour has reduced practical exploitability, which argues against high weights.

**Business risk:** Low-moderate; appears in questionnaires.

**Verdict: Identical, normalized, and — more importantly — weighted by asset function.**
**Evidence: Weak-to-Moderate.**

---

#### CSP

**Baseline importance:** Moderate, with a large caveat: CSP quality varies enormously and presence/absence is a poor binary. A policy containing `unsafe-inline` and `unsafe-eval` provides close to no XSS protection while scoring as "present" in most models. Scoring presence rather than strength produces a signal vendors can satisfy in one line without improving security — a gaming vector you are handing them for free.

**Class:** P.

**Age / revenue / size:** Unchanged. Legacy applications are harder to retrofit with strict CSP, which correlates with age — but the retrofit difficulty is the vendor's problem, not a reason to score the risk lower.

**Industry:** Higher relevance for consumer-facing web (retail, media, SaaS) where XSS-driven skimming (Magecart-class attacks) is a live threat; lower for API-only vendors. **This is a technology-surface distinction, correctly detected by looking at what the vendor actually runs.**

**Regulatory:** PCI DSS v4.0 Requirements 6.4.3 and 11.6.1 target payment-page script integrity and change detection — the strongest regulatory hook for any header, and it applies to a *page type*, not a company size.

**Attacker perspective:** Card skimming targets checkout pages specifically. Attackers select by page function, exactly as the scoring model should.

**Business risk:** High for e-commerce; low elsewhere.

**Verdict: Identical, normalized, and scored on policy strength rather than presence.**
**Evidence: Moderate** for payment contexts; **Weak** generally.

---

#### X-Frame-Options

**Baseline importance:** Low. Superseded by CSP `frame-ancestors`. Flagging its absence without first checking for `frame-ancestors` produces false positives, which corrode vendor trust and generate disputes.

**Class:** P.

**Age / revenue / size / industry:** Unchanged throughout.

**Regulatory:** No specific mandate.

**Attacker perspective:** Clickjacking is a low-yield attack requiring user interaction.

**Business risk:** Very low; primarily a scanner-checklist item.

**Verdict: Identical, Low or Informational.** Suppress entirely when CSP `frame-ancestors` is present.
**Evidence: Weak.**

---

#### security.txt

**Baseline importance:** Low as a risk signal; moderate as a maturity indicator. RFC 9116 defines the format; CISA's 2026 joint coordinated-vulnerability-disclosure guidance recommends its use so researchers can find contact information without hunting.

**Class:** B.

**Age:** Slight genuine effect — this is one of the few places where organizational maturity is a defensible read, since publishing security.txt implies someone owns vulnerability intake. But the causal chain runs through *having a VDP*, which you should measure directly instead.

**Revenue / size:** Unchanged. A static file costs nothing.

**Industry:** Adoption is much higher among technology companies and much lower in manufacturing, retail, and education. **The proposal that "missing security.txt may matter more for technology companies than manufacturers" is directionally reasonable as an expectation — and the benchmark handles it. A software vendor without security.txt is at an unusual percentile for its peer group; a foundry without one is at the median.** No multiplier needed.

**Regulatory:** CISA BOD 20-01 requires VDPs for US federal civilian agencies. The EU Cyber Resilience Act extends vulnerability-disclosure obligations to suppliers operating in the EU — a genuine, size-independent legal hook that will bind broadly from 2026 onward.

**Attacker perspective:** Neutral to slightly negative for the defender — security.txt discloses contact points but does not increase attack surface meaningfully. Not a risk signal in either direction.

**Business risk:** Low, rising as CRA obligations bite.

**Verdict: Identical, Informational-to-Low weight, scored as a positive rather than a penalty.** Do not let it drift upward in weight just because it is easy to measure — ease of measurement is not evidence of importance, and that bias deserves explicit guarding against.
**Evidence: Speculative** as a risk predictor.

---

### 4.2 Digital Footprint

---

#### Number of Subdomains

**Baseline importance:** **This is not a risk signal. It is the denominator.** Treating subdomain count as a finding is the conceptual error that generates the size bias. More subdomains means more attack surface, yes — and it also means more legitimate business. A 2,000-subdomain enterprise is not 200× riskier than a 10-subdomain startup.

**Class:** Denominator (exposure), not P or B.

**All firmographics:** Subdomain count *is* the size measure. Using it as both a penalty and a size proxy would be double-counting in opposite directions.

**Industry:** Technology and media companies run far larger subdomain estates structurally. Any model that penalizes count will systematically rank tech vendors worse regardless of hygiene.

**Regulatory:** Asset inventory is required by NIS2 Article 21, ISO 27001 A.5.9, CIS Control 1, and essentially every framework — but the requirement is to *know* your assets, not to have few of them.

**Attacker perspective:** Attackers do enumerate subdomains, and larger estates offer more entry points per unit of effort — but they exploit *weak* subdomains, not numerous ones.

**Business risk:** Only meaningful in the ratio form (unmanaged/total).

**Verdict: Not a penalized signal. Use as exposure denominator `D`.** If you want a risk signal from the subdomain estate, use **dangling/takeover-vulnerable subdomains**, which is a real, exploitable, high-severity finding — and normalize *that* by total count.
**Evidence: Strong** that raw count is a poor risk signal.

---

#### Certificate Transparency History

**Baseline importance:** Moderate, primarily as a *discovery* mechanism rather than a scored signal. CT logs reveal assets the vendor may not have disclosed and may not be managing.

**Class:** Discovery input; feeds both the denominator and shadow-asset detection.

**Age:** Genuine effect on *interpretation*: a 20-year-old company has 20 years of CT and pre-CT history, including long-dead assets. Naively counting historical CT entries as current exposure massively over-states large/old vendors' surface. **Use CT for asset discovery with liveness validation, never as a raw historical count.**

**Revenue / size:** Larger estates generate more CT entries — again denominator, not numerator.

**Industry / regulatory / attacker:** CT is a public reconnaissance resource used identically by attackers and raters. Its use is symmetric.

**Business risk:** Indirect.

**Verdict: Not independently scored.** Use as discovery, always validated for liveness.
**Evidence: Strong** methodologically.

---

#### Shadow Assets

**Baseline importance:** **High — one of the most genuinely predictive external signals available**, because an unmanaged asset is by definition outside patching, monitoring, and certificate renewal.

**Class:** P, and the ratio form is essential.

**Age:** **Genuine, defensible sensitivity — the strongest case for age-related interpretation in this study.** Older organizations accumulate abandoned infrastructure through acquisitions, rebrands, discontinued products, and staff turnover. However: this manifests as *more detected shadow assets*, which the signal already captures directly. Age does not need to be a multiplier because age's effect flows through the observable. **Do not double-count it.**

**Revenue / size:** Same argument. Larger organizations have more shadow assets in absolute terms; the ratio is the fair comparison. The proposal that "shadow assets may scale with attack surface" is correct — and the response is normalization, not amplification.

**Industry:** Higher in sectors with M&A intensity (finance, healthcare, technology) and in federated-governance sectors (higher education, large public bodies — consistent with RiskRecon's university finding). Peer group.

**Regulatory:** Asset management is a named requirement in NIS2 Article 21, ISO 27001, CIS Control 1, and PCI DSS Requirement 12.5.

**Attacker perspective:** **This is the signal where attacker behaviour most strongly validates the metric.** Attackers actively hunt forgotten infrastructure; it is the standard initial-access path in large-enterprise compromises. DBIR 2025's finding that edge devices and VPNs rose from 3% to 22% of exploitation targets is the same phenomenon at the appliance layer.

**Business risk:** High, and rising.

**Verdict: Identical severity; normalize as a ratio (`shadow / total discovered`); do not additionally multiply by age or size.**
**Evidence: Strong** conceptually and by attacker behaviour; **Moderate** in direct published correlation.

---

### 4.3 Breach & Compromise

---

#### Public Breach History

**Baseline importance:** High and decaying. Bitsight's methodology confirms the empirical basis: past incidents are predictive of future risk with diminishing relevance over time.

**Class:** C, with a legitimate Posture component.

**Age of company:** **This is where the third framing question — "is an old breach less concerning for a company that has since built a mature security program?" — is answered.** Yes, but *maturity* is not the right variable, because you cannot observe it from outside. Three variables you *can* observe, all better:

1. **Recency** — already in the model via age decay. Correct.
2. **Recurrence** — repeated incidents are far more informative than a single old one. A vendor with incidents in 2019, 2022, and 2025 should not benefit from decay in the way a vendor with one 2019 incident does. **The current Frequency multiplier partially covers this; it needs a formal definition and a cap.**
3. **Root-cause recurrence** — two incidents from the same class (e.g. both credential-stuffing) are much stronger evidence of an unfixed systemic weakness than two incidents from different classes. This is genuinely high-signal and rarely implemented.

**Revenue / size:** Bitsight scales the incident adjustment by severity *and organization size* — as normalization. A 10,000-record breach at a 50-person vendor represents a far deeper compromise than the same count at a 100,000-employee firm. **Normalize breach magnitude by the vendor's data-holding scale, not by revenue as a wealth proxy.**

**Industry:** Affects consequence, not likelihood of recurrence. Healthcare's $7.42M average versus public sector's $2.86M belongs in the impact model.

**Regulatory:** A breach subject to active enforcement should not decay while enforcement is ongoing — a defensible, objective, non-firmographic rule.

**Attacker perspective:** Publicly breached organizations are re-targeted; leaked credentials retain value for years. DBIR's finding of a 94-day median remediation for leaked GitHub secrets illustrates the persistence.

**Business risk:** Highest salience of any signal to procurement, boards, and insurers.

**Verdict: Slightly adjusted — by recency, recurrence, root-cause repetition, and magnitude-relative-to-scale. Not by company age, revenue, or claimed maturity.**
**Evidence: Strong.**

---

#### Exposed Data Types

**Baseline importance:** High for impact, near-zero for likelihood.

**Class:** **C — pure impact. This should not touch Posture at all.**

**All vendor firmographics:** Irrelevant to the vendor's control quality. What matters is what the vendor holds *of yours*.

**Industry:** Highly relevant, and correctly so — this is the mechanism behind the IBM cost-by-industry data. Health records, payment data, and credentials carry different loss magnitudes.

**Regulatory:** Determines notification obligations, and thus a large share of realized cost — GDPR, HIPAA, PCI, and US state breach-notification laws all key off data type.

**Attacker perspective:** Data type is the primary driver of target selection for financially motivated actors.

**Business risk:** Central to procurement.

**Verdict: Heavily adjusted — but by data sensitivity and the buyer's engagement, in the Impact/Tier dimension. Zero effect on Posture.**
**Evidence: Strong.**

---

#### Known Exploited Vulnerabilities (KEV)

**Baseline importance:** **Very high — the single most defensible high-severity external signal available**, because KEV membership is empirical evidence of real-world exploitation rather than theoretical severity.

**Class:** P (normalize by exposed asset count) — though at low counts the absolute number matters more than the rate.

**Age / revenue / size:** **Identical, and this is the strongest "no adjustment" case in the study.** An unpatched, actively-exploited, internet-reachable vulnerability is being exploited by automated tooling that does not consult Crunchbase. Bitsight TRACE's 1.4-million-organization study found over a third of organizations had at least one KEV in 2023 and 60% remained unremediated past CISA deadlines — the problem is universal.

The one legitimate nuance is *velocity*: as noted in §3.2, the gap between KEV and non-KEV remediation speed is widest at large organizations, meaning large firms triage exploited vulnerabilities better. But that is an argument for measuring **time-to-remediate as a distinct signal**, not for softening the KEV penalty.

**Industry:** Unchanged. CISA BOD 22-01 binds federal agencies to KEV deadlines; those deadlines are a reasonable universal yardstick regardless of who is legally bound.

**Regulatory:** BOD 22-01 (federal), and increasingly referenced in FedRAMP, CMMC, and insurance underwriting.

**Attacker perspective:** By construction, this is the set attackers are demonstrably using.

**Business risk:** Maximum. A KEV on a vendor's perimeter is the clearest actionable finding a TPRM program can receive.

**Verdict: Identical for every organization, full severity, no leniency for anyone. Add days-past-CISA-deadline as a multiplier.**
**Evidence: Strong.**

---

#### CVEs

**Baseline importance:** Moderate, and easily over-weighted. Externally-observed CVEs are usually inferred from version banners, which produces both false positives (backported patches) and false negatives (hidden versions). This is a **Confidence** problem masquerading as a Posture problem.

**Class:** P.

**Age / revenue / size:** Identical in severity; normalization mandatory. Larger estates accumulate more CVEs mechanically. Also note the false-positive asymmetry: enterprises running vendor-backported packages (RHEL, Ubuntu LTS) generate systematically more banner-based false positives than startups running latest-version containers — **so unnormalized CVE counting penalizes enterprise-standard practice.** That is a real fairness defect, not a hypothetical one.

**Industry:** Unchanged; embedded-heavy sectors (manufacturing, energy, healthcare devices) show more legacy CVEs.

**Regulatory:** PCI DSS mandates CVSS-based remediation timelines, which is worth noting as a case where regulation lags the evidence — the research is clear that CVSS-only prioritization is inefficient.

**Attacker perspective:** Attackers do not work through the CVE list; they work through the exploitable subset. Weighting all CVEs comparably actively misrepresents risk.

**Business risk:** Moderate; frequently disputed by vendors, so evidence quality matters.

**Verdict: Identical, normalized, and heavily down-weighted relative to KEV/EPSS.** Consider not scoring banner-inferred CVEs at all except where confirmable.
**Evidence: Strong that raw CVE counts are weak predictors.**

---

#### CVSS

**Baseline importance:** Low as a *prioritizer*, moderate as a *descriptor*. CVSS measures intrinsic severity under worst-case conditions; it was never designed to predict exploitation and does not.

**Class:** Modifier on CVE findings.

**All firmographics:** Unchanged — and there is a subtlety worth flagging. CVSS *does* have environmental metrics designed for exactly the contextual adjustment being contemplated here. But environmental scoring requires internal knowledge (asset criticality, compensating controls) that an outside-in rater does not have. **Do not fabricate environmental scores from firmographics.** Guessing a bank's environmental modifiers from the fact that it is a bank is exactly the kind of unfounded subjective judgment the constraints in this brief rule out.

**Verdict: Identical. Use as a descriptor; do not use as the primary severity driver.**
**Evidence: Strong** on its limitations.

---

#### EPSS

**Baseline importance:** High as a weighting input — the best available exploitation-likelihood estimator for vulnerabilities not yet in KEV.

**Class:** Modifier.

**All firmographics:** **Identical, necessarily.** EPSS is a global model of exploitation probability for a CVE; it contains no organizational term and cannot be conditioned on one without invalidating it. Multiplying an EPSS probability by a firmographic factor produces a number that is no longer a probability of anything.

**Industry:** Unchanged — though a legitimate refinement exists: exploitation campaigns are sometimes sector-targeted. That is a *threat-intelligence* overlay, not an EPSS adjustment, and it should be sourced and dated if used.

**Regulatory:** Not yet mandated anywhere; increasingly accepted.

**Attacker perspective:** EPSS is a model *of* attacker behaviour. That is its whole value.

**Business risk:** Growing rapidly in underwriting.

**Verdict: Identical. Adopt as a primary severity input — this is the highest-value accuracy improvement available to the framework.**
**Evidence: Strong.**

---

### 4.4 Governance

---

#### Published Security Program

**Baseline importance:** Low as a risk predictor. A published security page is marketing collateral. Its correlation with actual control quality is unmeasured and plausibly weak.

**Class:** C — Assurity, not Posture.

**Age / revenue / size:** **This is the signal where firmographic bias is most likely to enter unnoticed.** Large, well-resourced, marketing-mature companies publish trust centres. Small, technically excellent companies often do not. Penalizing absence directly encodes a marketing-budget bias into a security score.

**Industry:** SaaS and technology companies publish these routinely (competitive necessity); manufacturers and non-profits rarely do. A raw penalty systematically disadvantages entire sectors for reasons unrelated to security.

**Regulatory:** NIS2 Article 20 requires management-body approval and oversight of cybersecurity measures — but *internal governance*, not public publication. No framework requires a public security page.

**Attacker perspective:** Neutral.

**Business risk:** Moderate procurement convenience; near-zero risk relevance.

**Verdict: Slightly adjusted, and moved out of Posture into Assurity, scored as a positive only.** Never penalize absence.
**Evidence: Speculative.**

---

#### Vulnerability Disclosure Policy

**Baseline importance:** Moderate, and the best of the three governance signals. A real VDP means someone is receiving, triaging, and fixing externally-reported vulnerabilities.

**Class:** B, Assurity-leaning.

**Age:** Slight legitimate effect — VDPs indicate program maturity. But absence in a young company is expected, not alarming, and the benchmark handles that.

**Revenue / size:** Unchanged in principle; a VDP is a policy document plus an intake process. Running a *bug bounty* costs money; running a VDP does not. **Do not conflate the two** — several models do, which penalizes small vendors for lacking a budget line rather than a process.

**Industry:** Strong differentiation. Technology, finance, and government lead. CISA BOD 20-01 requires US federal civilian agencies to publish VDPs, citing ISO/IEC 29147 and ISO/IEC 30111 as normative references. The EU Cyber Resilience Act extends disclosure obligations to suppliers operating in the EU.

**Regulatory:** Real and size-independent where it applies. NIST SP 800-216 provides federal guidance.

**Attacker perspective:** Slightly protective — a VDP raises the probability that a researcher reports rather than sells or drops a finding.

**Business risk:** Rising fast with CRA.

**Verdict: Identical, scored as a positive; route the regulatory expectation to Compliance Gap for entities actually in scope of BOD 20-01 or CRA.**
**Evidence: Moderate.**

---

#### Security Contact

**Baseline importance:** Low. Largely duplicative of security.txt and VDP.

**Class:** B.

**All firmographics:** Unchanged. Cost is one mailbox.

**Verdict: Identical, Informational.** Merge with security.txt to avoid triple-counting the same underlying fact across three signals — which the current flat-accumulation model would otherwise do, silently inflating the Governance category's effective weight.
**Evidence: Weak.**

---

### 4.5 Business

---

#### Domain Age

**Baseline importance:** **Near zero for established vendors; moderate only for fraud screening.**

**Class:** C — and arguably should not be in a security posture model at all.

**Age / revenue / size:** The proposal that "domain age may matter differently for startups" deserves a direct answer: **domain age is not a maturity signal, because aged domains are a purchasable commodity.** Expired-domain marketplaces sell 10- and 20-year-old domains for a few hundred dollars, and threat actors are among the most active buyers precisely because age defeats naive reputation scoring. Any weight you place on domain age is a weight an adversary can buy.

Its one legitimate use is **shell-entity screening**: a "vendor" whose domain was registered six weeks ago, with privacy-protected WHOIS, no legal entity record, and no corroborating footprint, is a plausible fraud rather than a security-posture problem. That is an **onboarding fraud check**, and it should be a gate with a human review path, not a scored penalty.

**Industry / regulatory / attacker / business:** Fraud-screening context only.

**Verdict: Not scored in Posture. Route to a separate Entity Verification gate.**
**Evidence: Weak** as a security signal; **Moderate** as a fraud signal.

---

#### Domain Registration Quality

**Baseline importance:** Low-to-moderate. Registrar lock, expiry buffer, and registrar security posture matter — domain hijacking via registrar-account compromise is a real and high-impact attack.

**Class:** B.

**Age / revenue / size:** Unchanged. Registrar lock is a checkbox.

**Industry:** Unchanged; high-value brands are targeted more, which again is brand attractiveness, not revenue.

**Regulatory:** Not specifically mandated.

**Attacker perspective:** Registrar-level attacks against high-value targets are real (multiple nation-state DNS-hijacking campaigns). But the control is free for everyone.

**Business risk:** Low salience, disproportionate impact when it fails.

**Verdict: Identical, Low-to-Medium.** Score lock status and expiry buffer; do not score privacy-protected WHOIS as a negative (it is now the default and often legally required under GDPR — penalizing it is a geographic bias in disguise).
**Evidence: Weak-to-Moderate.**

---

#### Legal Entity Status

**Baseline importance:** Moderate for counterparty risk; zero for security posture.

**Class:** C.

**Verdict: Not in Posture.** Route to Entity Verification / counterparty diligence.
**Evidence: N/A** for security.

---

#### Company Age

**Baseline importance:** **No demonstrated predictive value for security posture.** No authoritative source reviewed here — Bitsight, SecurityScorecard, RiskRecon, Cyentia, NIST, ENISA, CISA — scores or normalizes by company founding date.

**Class:** C — benchmarking covariate only.

**The core question, answered directly:** *Should a 20-year-old company receive a larger penalty than a one-year-old startup for the same finding?*

**No, for four reasons:**

1. **It is not more likely to cause a compromise.** The exploit does not know the incorporation date.
2. **The premise is contested by the data.** Older firms carry more legacy debt (arguing they are *worse*), and simultaneously have more mature programs (arguing they are *better*). Cyentia's finding of no meaningful size-based difference in remediation speed suggests these largely cancel. Adding a multiplier requires knowing the net direction, and nobody has demonstrated it.
3. **The effect, if real, is already observed directly.** Legacy debt manifests as detected legacy protocols, expired certificates, and shadow assets. Adding an age multiplier on top double-counts the same underlying cause.
4. **It destroys comparability and validatability**, per §2.2 and §2.3.

**Where it legitimately belongs:** as a **peer-group covariate** (compare 20-year-old enterprises to 20-year-old enterprises) and as an input to the **prior** when evidence coverage is low.

**Verdict: Not in Posture. Benchmarking and prior only.**
**Evidence: Absent** — and the absence should be stated, not filled with intuition.

---

#### Company Continuity

**Baseline importance:** Moderate for supply-chain resilience; low for security posture. Financial distress is genuinely associated with security degradation (security budgets get cut, staff leave, assets get orphaned), but the observable version of that is the resulting *technical decay*, which the model already catches.

**Class:** C.

**Age / revenue / size:** Relevant to continuity risk, which is a real third-party risk category but a different one from cyber posture.

**Industry / regulatory:** DORA and NIS2 both require supply-chain and continuity assessment — as a separate obligation from cybersecurity risk management.

**Verdict: Not in Posture. Separate Continuity dimension in the vendor profile.**
**Evidence: Weak** for direct security correlation.

---

### 4.6 Compliance

---

#### ISO Certifications

**Baseline importance:** Moderate as *assurance*, weak as *risk prediction*. ISO 27001 certification tells you an ISMS exists and was audited against a defined scope. It does not tell you the scope covered the systems you care about — scope statements are frequently narrow and are the single most under-examined document in vendor assurance.

**Class:** **C — Assurity. This should not be in Posture.**

**Age / revenue / size:** **The most firmographically biased signal in the entire catalogue.** ISO 27001 certification costs money and calendar time. A five-person startup with excellent engineering practices and no certificate is not more likely to be compromised than a certified 500-person firm with a narrow scope. Penalizing absence of certification is a direct tax on company size, dressed as a security measurement — and it is the exact form of bias this study exists to prevent.

**Industry:** Near-universal in enterprise SaaS and outsourcing; rare in manufacturing and non-profits. Penalizing absence would systematically mis-rank whole sectors.

**Regulatory:** ISO 27001 is a recognized route to demonstrating NIS2 Article 21 compliance, but is not itself mandated. Note the finding that ISO-certified organizations still typically show gaps around supply-chain security, management-body accountability, incident-reporting timelines, and explicit MFA requirements — certification is not equivalence.

**Attacker perspective:** Irrelevant. Certified organizations are breached routinely.

**Business risk:** High procurement salience — but that is a *procedural* requirement, not a risk finding, and the distinction matters.

**Verdict: Heavily adjusted, and quarantined in Assurity. Score presence positively, never score absence negatively in Posture. Record scope and expiry.**
**Evidence: Weak** for breach correlation; **Strong** for procurement relevance.

---

#### SOC Reports

**Baseline importance:** Same as ISO, with a sharper caveat: a SOC 2 Type II report's value lies almost entirely in the exceptions listed and the trust-services criteria in scope. A model that scores "has SOC 2: yes/no" is scoring a purchase, not a posture.

**Class:** C — Assurity.

**Age / revenue / size:** Same bias as ISO, with an additional wrinkle: SOC 2 Type II requires an observation period (typically 6–12 months), which makes it **structurally impossible** for a company under one year old. Penalizing its absence at a startup penalizes the passage of time.

**Industry:** US-centric; European vendors more often hold ISO. **Penalizing absence of SOC 2 is therefore a geographic bias in disguise** — precisely the class of adjustment that should be avoided.

**Verdict: Heavily adjusted, quarantined in Assurity, positive-only scoring.**
**Evidence: Weak** for breach correlation.

---

#### Regulatory Disclosures

**Baseline importance:** Moderate-to-high where present — SEC 8-K Item 1.05 material-incident disclosures, breach notifications to state AGs, and equivalent filings are high-quality, verified evidence.

**Class:** C feeding Posture via the breach-history mechanism.

**Age / revenue / size:** **Serious and under-appreciated availability bias.** Public companies must disclose; private companies often need not. Small companies below notification thresholds may have breaches that never surface. **A clean disclosure record at a private company is much weaker evidence of safety than a clean record at an SEC registrant** — a genuinely different quantity that the current model would treat identically.

This is a **Confidence** effect, not a Posture effect: public-company status increases evidence coverage for the breach signal. This is one of the few places where a firmographic legitimately and unambiguously belongs — in Confidence, exactly as the study's architecture predicts.

**Industry:** Healthcare (HHS OCR portal), finance (multiple regulators), and public companies have far higher disclosure rates than manufacturing or private services.

**Regulatory:** SEC cyber disclosure rules, GDPR Article 33, HIPAA Breach Notification Rule, NIS2 incident reporting (24-hour initial), DORA (4-hour initial).

**Verdict: Identical in Posture; adjust Confidence by disclosure regime.** Never treat "no disclosed breaches" as equivalent evidence across disclosure regimes.
**Evidence: Strong** for the bias; the correction is rarely implemented.

---

### 4.7 Reputation

---

#### Regulatory Enforcement

**Baseline importance:** High where present. An enforcement action is adjudicated, evidenced, and specific — far higher quality than media reporting.

**Class:** C with a legitimate Posture component when the action concerns security controls.

**Age / revenue / size:** **Enforcement probability is not uniform, and this is a significant fairness trap.** Regulators pursue large, visible, well-resourced targets disproportionately — greater harm, greater deterrent value, better cost recovery. A clean enforcement record at a small private vendor is much weaker evidence than at a large regulated entity. Treating them identically systematically favours small and unregulated vendors.

**Industry:** Finance, healthcare, and telecom face active supervisory regimes; most sectors do not.

**Regulatory:** Self-defining. Note NIS2's personal liability for management bodies and fines up to €10M or 2% of global turnover for essential entities — enforcement intensity is rising.

**Attacker perspective:** Neutral.

**Business risk:** Very high — often a contractual or insurance disqualifier.

**Verdict: Identical severity where the action is security-related. Adjust Confidence for enforcement-regime exposure. Score only adjudicated outcomes, never investigations-in-progress, in Posture.**
**Evidence: Moderate.**

---

#### Government Investigations

**Baseline importance:** Low for scoring. An open investigation is an allegation, not a finding.

**Class:** C.

**All firmographics:** The same selection bias as enforcement, amplified.

**Verdict: Do not score in Posture. Disclose as context.** Scoring unadjudicated investigations creates defamation exposure and is likely to fail the "empirical, data-driven" test in the Chamber Principles.
**Evidence: Weak.**

---

#### Verified Adverse Media

**Baseline importance:** Low and hazardous. Media coverage volume is a function of company visibility, not security quality.

**Class:** C.

**Age / revenue / size:** **The most size-confounded signal in the catalogue.** A large consumer brand generates orders of magnitude more coverage per incident than a private B2B vendor. Any adverse-media count penalizes fame. If used at all, it must be normalized by baseline media volume — and even then the residual is noisy.

**Industry:** B2C companies generate vastly more coverage than B2B for identical events.

**Attacker perspective:** Neutral.

**Business risk:** Real reputational-contagion concern for the buyer, which is a legitimate business input — but it is not a measure of the vendor's security.

**Verdict: Not in Posture.** Route to a separate Reputational Exposure view, normalized by media baseline, human-verified.
**Evidence: Weak.** Highest false-positive and dispute risk of any signal listed.