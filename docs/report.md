# Context-Aware Vendor Risk Scoring — Consolidated Research Report

**Should external security signals be interpreted differently by company type?**
Evidence review, per-signal analysis, critique of the current model, and a revised specification.

**Assessed system:** `scoring.yaml` v4.2.0 (penalty-subtractive posture) · `benchmarks.yaml` v1.0.0 · `docs/methodology.md` §5
**Date:** July 2026
**Status:** research recommendation. **Nothing in Parts VI–X is in the engine.** Where the shipped code already differs, this report says so.

---

## Part 0 · What this report consolidates

This merges five source documents. A sixth file, `vendor-signal-weighting(1).md`, is **byte-identical** to `vendor-signal-weighting.md` and contributed nothing additional.

| Source | Lines | Distinctive contribution retained here |
|---|--:|---|
| `context-aware-vendor-risk-scoring-study.md` | 973 | The P/B/C signal taxonomy; the three-quantities decomposition; the empirical evidence table |
| `new_research_meth.md` | 1,236 | Commercial-platform comparison; the twelve-mechanism scoring; the full revised mathematics (log-odds, shrinkage, Assurity, Compliance Gap, Expectation Gap); five-phase migration |
| `vendor-signal-weighting.md` | 786 | The **diagnosticity / surprisal** framing and the `D·O·C ÷ N` weight formula; the remediation-cost tiering of signals |
| `signal_affect.md` | 222 | **Real-world anchors** per signal and honest **evidence-strength ratings**, including six signals marked as weakly evidenced |
| `methodology-evaluation-and-redesign.md` | 621 | **Concrete per-cohort severity values**; the λ=0.7 diminishing-returns aggregation; the ranked unintended-consequences table |
| *(duplicate file)* | 786 | — none — |

**Total source material: 3,838 distinct lines.** Consolidated here with overlap removed.

**One thing this report adds that no source contains: [Part VIII](#part-viii--where-the-sources-disagree).** The five documents do not agree with each other on three substantive design questions. Earlier drafts of a merged document would have silently adopted whichever source was read last. Those disagreements are surfaced explicitly instead, because two of them change what you would build.

---

## Part I · Executive summary

### The headline answer

> **The importance of a security signal should almost never vary with a vendor's age, revenue, headcount, or market cap. It should vary with the vendor's measured exposure, and the consequences of its failure should vary with the buyer's engagement.**

Those are three different adjustments, and conflating them is the central error the proposed context-adjustment would introduce.

| Question | Correct home | Should firmographics touch it? |
|---|---|---|
| How likely is this vendor to be compromised? | **Posture** | **No** — except exposure normalization |
| How much of my attack surface / data does the vendor hold? | **Impact / Vendor Tier** | Yes, but *my* firmographics and the engagement's |
| How much do I trust the measurement? | **Confidence** | Weakly — coverage is partly a function of size |
| How well documented is the vendor's own assurance? | **Assurity** | Yes — this is where audit-budget effects belong, quarantined |
| Is this normal for a company like this? | **Benchmarking** | **Yes — this is exactly what benchmarking is for** |
| What should I do about it? | **Recommendations / Tier** | Yes |

The intuition driving the research question — *"a $5 billion bank with no DMARC looks more negligent than a $500K startup with no DMARC"* — is correct, and it is a statement about **culpability**, not **probability**. Negligence is a legal and commercial concept; risk is a probabilistic one. A posture score that mixes them stops predicting anything, becomes non-comparable across vendors, and cannot be validated against outcomes. The negligence signal is real and worth surfacing — in the benchmark delta and the narrative, not in the arithmetic.

### The one adjustment that is mandatory, and it runs opposite to intuition

The current model accumulates absolute penalties with **no denominator**, which means it already penalises large vendors severely — by accident.

| | Hosts | Expired certs | Failure rate | Current penalty (Medium = 8) |
|---|--:|--:|--:|--:|
| Vendor A | 4 | 2 | **50%** | −16 |
| Vendor B | 900 | 9 | **1%** | **−72** (category floored) |

Vendor B has *fifty times better* certificate management and scores dramatically worse. **The model is measuring host count, not hygiene.**

Both major raters solved this publicly a decade ago. Bitsight normalizes by "employee count, magnitude of digital footprint, overall count of observations" explicitly so ratings do not "unfairly penalize large companies." SecurityScorecard's entire model is a modified z-score in which "z = 1 when the number of findings equals the mean for organizations with the same size Digital Footprint."

So: *should larger organizations receive larger penalties because they have more resources?* **They already do, accidentally and massively. The first priority is to stop that** — not to add more of it deliberately.

### The taxonomy that resolves most of the question

| Class | Signals | Treatment |
|---|---|---|
| **P — Prevalence** | cert validity, TLS version, ciphers, HSTS, CSP, XFO, CVEs, KEV, shadow assets, subdomain hygiene | **Must be measured as a rate with an exposure denominator.** Size adjustment is mandatory — its purpose is bias removal, not leniency |
| **B — Binary policy** | DMARC, SPF, DKIM, DNSSEC, CAA, security.txt, VDP, security contact | **Identical treatment for every organization.** These cost engineering hours, not headcount |
| **C — Consequence / assurance** | breach history, exposed data types, ISO/SOC, regulatory disclosures, adverse media, entity status, company age/continuity | **Do not belong in posture at all.** They belong in Impact, Assurity, or Confidence |
| **D — Denominator** | subdomain count, CT history | **Not scored.** They *are* the size measure |

### The tally

| | Count |
|---|--:|
| Signals where **company age** changes the score | **0 of 35** |
| Signals where **revenue / headcount / market cap** changes the score | **0 of 35** |
| Signals where **measured exposure** changes the score (mandatory denominator) | **10 of 35** |
| Signals where **industry** matters — into benchmark, Compliance Gap, or Impact, never severity | **12 of 35** |
| Signals where a firmographic legitimately moves **Confidence** | **3** |
| Signals that should **leave Posture entirely** | **11** |

Revenue appears four times across the whole catalogue: three times as a **bias to correct** (ISO/SOC audit budget, enforcement selection, adverse-media volume) and once as *magnitude relative to scale* inside breach history — which is a ratio, not a multiplier.

### The three flagship questions, answered

**"Should a 20-year-old company be penalised more than a 1-year-old startup for TLS 1.0?"**
No — and the intuition inverts. The exploit does not know the incorporation date. Decomposed: severity is identical; **diagnosticity is *higher* for the startup**, because every modern stack ships TLS 1.2/1.3 by default and a 2025-founded company had to actively regress, whereas the 20-year-old has a plausible legacy-appliance story; obligation and consequence are usually higher for the older firm. Net, the older firm often scores worse — but through **obligation and consequence**, never an age multiplier. The better variable is **dispersion**: 200 hosts on TLS 1.3 and one on TLS 1.0 reveals a forgotten asset, which is worse than a small estate uniformly on TLS 1.2.

**"Should a $5B bank be penalised more than a 10-person SaaS for missing DMARC?"**
No, and the premise inverts twice. Fortune 500 sits at **95% adoption and 62.7% at `p=reject`** against Inc. 5000 at **15.2%** — so a large firm without DMARC is *already* a ~4th-percentile outlier in its own cohort, and **the benchmark delta says so without any multiplier**. On cost, reaching `p=reject` at a Fortune 500 means inventorying decades of sending services across dozens of business units; at a ten-person SaaS it is one afternoon. The large firm's task is harder and it does it more often.

**"Is an old breach less concerning for a company that has since matured?"**
Yes — but *maturity is not observable from outside*, so do not proxy it with company age. Three observable variables are all better: **recency** (age decay), **recurrence** (incidents in 2019, 2022 and 2025 must not decay like one 2019 incident), and **root-cause repetition** (two credential-stuffing incidents evidence an unfixed systemic weakness far more than two unrelated ones). And the discount must be **earned by evidence, not granted by the calendar** — the literature is explicit that symbolic adoption diminishes security effectiveness.

### Top ten recommendations

1. **Add an exposure denominator to every prevalence-class signal.** Highest-impact change in this report. Removes an existing bias rather than adding a new one.
2. **Do not add firmographic penalty multipliers to Posture.** No revenue, headcount, market-cap, or company-age multiplier on severity or penalty.
3. **Replace linear penalty subtraction with bounded log-odds accumulation** through a logistic transform. The current model floors at zero after roughly 2.5 criticals and loses all discriminating power in the bottom quartile.
4. **Make weights explicit.** "No category weights, categories emerge naturally" is not the absence of weighting — it is undocumented weighting determined by how many detectors you happen to have written per category.
5. **Move ISO / SOC / attestations out of Posture into Assurity.** Penalizing a missing SOC 2 is a tax on audit budget with no demonstrated link to compromise likelihood, and it is the single most demographically biased element you could include.
6. **Introduce an Expectation Gap as an output, not an input:** `EG = Posture − E[Posture | peer group]`. This delivers everything the "$5B bank should look worse" intuition wants without contaminating the score.
7. **Add a Compliance Contradiction finding class.** "Vendor asserts PCI DSS compliance and negotiates TLS 1.0" is not a more severe TLS finding — it is a distinct, high-signal finding about the reliability of the vendor's own attestations.
8. **Replace the hard 40% Ghost cutoff** with coverage-scaled prediction intervals plus an explicitly labelled shrunk estimate. The current cliff is gameable: making attribution difficult is a way to disappear.
9. **Rebuild the mitigation multiplier.** A flat, human-granted ×0.6 with no evidence taxonomy is the most manipulable element in the current design.
10. **Never adjust by geography or nationality in Posture.** Weakly predictive, ethically fraught, legally exposed. Surface jurisdiction as a disclosed attribute of the engagement instead.

---

## Part II · Conceptual foundation

### II.1 Three quantities that must not be merged

```
VendorRisk = P(vendor compromised)
           × P(compromise reaches you | vendor compromised)
           × Loss(you)
```

The current model computes a proxy for the **first term only**. Two vendors at 72 might be a payroll processor holding your entire employee PII set with SSO federation, and a stock-photo service. Map the factorisation to three separately computed sub-scores:

1. **Posture** — observed control state. *This is where cohort/diagnosticity normalization lives.*
2. **Exposure** — footprint, shadow assets, KEV/EPSS-weighted vulnerability load. *This is where denominators live.*
3. **Consequence multiplier** — data classes held, integration depth, OAuth/SSO scopes, network access, business criticality, substitutability. *Not firmographic at all — a property of your relationship with the vendor.*

Keeping these apart is what lets you answer "why did this vendor score badly?" in one sentence a procurement lead can act on. It also prevents the classic failure where a huge well-run vendor and a tiny sloppy one land on the same composite number for opposite reasons.

### II.2 The four legitimate modifier channels, and the one illegitimate one

> **Firmographics enter as priors, denominators, and expectations — never as penalties.**

- **D — Diagnosticity (peer base rate).** A missing control is informative in proportion to how *unusual* it is within the vendor's cohort.
- **N — Exposure normalization (denominators).** Count-based signals must be divided by footprint or they measure size.
- **O — Obligation.** Regulatory and contractual duty genuinely differs. A finding that violates a binding obligation is a different artifact from the same finding at an unregulated vendor.
- **C — Consequence.** What the vendor holds, touches, and connects to *in your environment*. Should dominate everything else; a property of the relationship, not the founding date.
- **✗ Moral expectation ("they should know better").** Not a modifier. Intuition dressed as analysis. It does not survive backtesting, and it is the channel through which unfairness and disputes enter.

### II.3 Diagnosticity, formally

For a binary finding, belief should move in proportion to the likelihood ratio:

```
LR = P(finding observed | vendor is weak) / P(finding observed | vendor is strong)
```

Both terms are population-dependent. A control adopted by 95% of a cohort makes its absence a screaming outlier; a control adopted by 8% makes absence background noise — you penalise nearly everyone, adding variance and no discrimination.

A practical proxy where you lack labelled outcomes is **surprisal**:

```
D_i(cohort) = −log₂( P(finding | cohort) )
```

- Missing DMARC in an F500 cohort: P ≈ 0.05 → **4.3 bits**
- Missing DNSSEC globally: P ≈ 0.92 → **0.12 bits**

A ~35× ratio derived entirely from public adoption data, with no incident labels required. Surprisal measures **anomaly, not harm** — so cap it and multiply by an expert-assigned severity rather than letting it float free.

### II.4 The negligence / probability distinction

The "$5B bank has no excuse" intuition is about **culpability**. A model that mixes culpability into probability:

1. cannot be validated against outcomes, because there is no outcome corresponding to deservingness;
2. destroys comparability — if 72 means one thing for a startup and another for a bank, the threshold "we don't onboard below 65" is meaningless and portfolio aggregation is invalid;
3. double-counts, because the effect is usually already observed directly. Legacy debt manifests as detected legacy protocols, expired certs and shadow assets. An age multiplier on top counts the same underlying cause twice.

### II.5 The detection-and-disclosure bias — the one most models get wrong

Several signals — public breach history, regulatory enforcement, government investigations, adverse media, regulatory disclosures — are not observed directly. They are observed through a filter whose transmissivity is itself a function of firmographics.

> **"No public breach history" is strong positive evidence for a Fortune 500 and near-zero evidence for a private SMB.**

If you score absence-of-evidence symmetrically, you **systematically reward opacity** — your best scores go to the vendors you can see least. Correct explicitly by weighting absence-signals by `P(we would have observed it | it happened)`, estimated from listing status, jurisdiction, sector disclosure regime and size. The Posture/Confidence split is what makes this fixable here and unfixable in single-axis models.

### II.6 But firmographics must be bounded

Observed posture dominates demographics by a wide margin: *"single demographic factors such as industry, size, and region aren't enough to assess the risk posed by third parties; choosing a partner with a poor security posture can mean your organization is 360 times more likely to be exposed to security findings."*

Firmographics should therefore be **bounded modifiers on observed findings**, never independent score drivers. Recommended caps: any individual signal's weight moved by no more than **~2.5×**, and total firmographic influence on composite posture capped at **~20–25%**.

### II.7 Where regulators genuinely do scale by size — and why it is not a counter-argument

NIS2 Article 21(1) requires "appropriate and proportionate" measures with due account of "the degree of the entity's exposure to risks, the entity's size and the likelihood of occurrence of incidents." DORA scales by size, nature, scale and complexity, with a simplified framework for microenterprises under Article 16.

Three observations settle it:

1. **Ordering.** Exposure first, size second. Even the regulators put measured exposure ahead of headcount.
2. **Direction.** Proportionality *reduces* obligations for small entities. It does not *increase* penalties for large ones. The research question asks for the second; the regulation supports only the first.
3. **Object.** It modifies the **required control set**, not the **risk assessment**. A microenterprise running TLS 1.0 has exactly the same technical exposure as a bank running TLS 1.0. What differs is what the law demands of each.

Proportionality therefore belongs in **Compliance Gap and Recommendations**, not in the estimator of compromise likelihood.

---

## Part III · Empirical evidence review

| Claim | Verdict | Evidence |
|---|---|---|
| Larger organizations experience more incidents | **Supported (frequency) — and it is an exposure effect** | Cyentia IRIS 2025: adjusted for organization count, the largest corporations experience incidents at a rate 620× higher. IRIS 2022: firms >$100B revenue are 32× more likely to have multiple incidents in one year |
| Larger organizations remediate faster because they have resources | **Not supported** | Cyentia: "there's not much difference in fix speeds between small, medium, and large organizations (based on employee size)" — more resources, but proportionally more to patch |
| Larger organizations have better basic email hygiene | **Supported — and it undercuts the negligence argument** | EasyDMARC 2026: Fortune 500 at 95% DMARC adoption, >80% at enforcement, 62.7% at `p=reject`; Inc. 5000 at 15.2% `p=reject` with over half still at `p=none` |
| Industry base rates for hygiene differ materially | **Strongly supported** | RiskRecon: large banks average 0.5 critical-severity issues per 100 high-value internet-facing systems; universities average 6.3 — a 12× spread |
| Breach consequences differ by industry | **Strongly supported** | IBM/Ponemon 2025: healthcare $7.42M (14th consecutive year highest), financial $5.56M, industrial $5.00M, retail $3.54M, public sector $2.86M |
| Past incidents predict future incidents, with decay | **Supported** | Bitsight applies an incident adjustment scaled to severity and organization size that "decays over time, consistent with the empirical evidence that past incidents are predictive of future risk but with diminishing relevance as time passes." Among public companies, 334 of 1,014 breaches disclosed before end-2021 (~33%) were repeat breaches |
| Company **age** predicts security posture | **No published evidence found** | Not one of Bitsight, SecurityScorecard, RiskRecon, Cyentia, NIST, ENISA or CISA scores or normalises by founding date. **Treat as unsupported** |
| Exploit-likelihood beats severity for vulnerability weighting | **Strongly supported** | Jacobs et al.: a CVSS 7+ strategy requires remediating ~50.7% of CVEs for 74.6% coverage at ~6% efficiency; EPSS v4 reaches comparable coverage at ~6% effort and ~47% efficiency |
| Small firms are slower to remediate | **Contradicted — the curve is non-monotonic** | Small organizations remove exposures fastest (14–18 days), slowing to a peak of **56 days at 5,000+ employees**, improving again at large-enterprise scale |
| Old *code* accumulates security debt | **Supported — but this is application age, not company age** | Veracode: security debt concentrates in applications that are older and have grown larger; affects 82% of organizations, critical debt 60% |

### III.1 A conflict between the sources, unresolved

**DNSSEC adoption is cited at two materially different rates:**

| Source | Figure | Implication |
|---|---|---|
| `vendor-signal-weighting.md` | **~7%** secure delegation globally (APNIC/Cloudflare 2025); 5.93% across 171M domains | Penalising absence penalises ~93% — pure noise |
| `signal_affect.md` | **18.0%** US adoption (PowerDMARC 2026) | Still a minority, but 2.5× the other figure |

Both cannot be the operative number. They are probably measuring different populations (global registered domains vs US business domains), which is itself the point made in [Part XII.3](#part-xii--what-the-research-does-not-support): **published base rates measure domains, not your vendors.** The practical resolution is the same under either figure — DNSSEC stays a bonus, never a penalty — but the gap should be closed before either number reaches a client deliverable.

### III.2 The signals whose evidence is weak, stated plainly

Six signals rest on weak or absent evidence and are marked as such throughout. **This is a finding in its own right, not a gap to be papered over** — those six should carry low weight, or none, precisely because the evidence for them is thin:

**DNSSEC · CAA · X-Frame-Options · security.txt · published security program · company age**

---

## Part IV · What the commercial platforms actually do

**Every platform that publishes a technical rating normalizes by measured digital footprint, and none applies a revenue, headcount, or company-age multiplier to a technical finding's severity.** Firmographics appear in exactly two places across the whole market — peer-group definition, and loss-magnitude estimation.

| Practice | Bitsight | SSC | RiskRecon | Black Kite | UpGuard | Panorays | OneTrust | ProcessUnity |
|---|---|---|---|---|---|---|---|---|
| Normalizes findings by measured footprint | ✅ | ✅✅ | ✅ | ✅ | ~ | ? | n/a | n/a |
| **Revenue/headcount multiplier on technical severity** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Industry used to define peer group | ✅ | ✅ | ✅✅ | ✅ | ✅ | ~ | ~ | ~ |
| **Industry used to change severity arithmetic** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Firmographics drive loss magnitude | ~ | ~ | ✅ | ✅✅ | ❌ | ✅ | ✅ | ✅ |
| Buyer-side context drives tier/depth | ~ | ~ | ~ | ~ | ~ | ✅✅ | ✅✅ | ✅✅ |
| Incident history decays over time | ✅ | ✅ | ✅ | ✅ | ✅ | ? | n/a | n/a |
| Published breach-outcome validation | ✅✅ | ✅ | ~ | ~ | ~ | ❌ | n/a | n/a |

*✅✅ central design feature · ✅ present and disclosed · ~ partial/undisclosed · ❌ absent · ? not publicly documented*

**Two rows carry the whole argument.** Row 1 is unanimous and row 2 is unanimously empty. Eight competing platforms, with access to outcome data none of them share, all normalize by footprint and none applies a firmographic multiplier to technical severity. **The current model does the opposite on both counts:** it has no denominator, and it *does* promote severity by industry via `industry_profiles`.

Two further Bitsight design choices worth copying: risk vectors are **weighted by demonstrated correlation to breach**, not expert opinion — which is why HTTP security headers carry near-zero rating impact in their model while the current model scores them Low. And their validation artefact is what makes a rating defensible: 27,458 companies over two years against 2,671 breach events, showing organizations rated 700+ at under 1% breach probability against nearly 3% below 500. **Note what that requires — an absolute, comparable scale.** A score whose scale varies with the subject's revenue cannot produce that chart.

**The caveat these platforms carry, and you should too.** Berg, Kölbel and Rigobon found average pairwise correlation across major ESG rating providers of roughly 0.53–0.56, versus over 0.99 between Moody's and S&P credit ratings — driven not by data scarcity but by divergence in indicator selection, weighting and scope. Security ratings sit somewhere between those poles and nobody knows exactly where. **Each unvalidated context adjustment you add moves you toward the ESG end.**

---

## Part V · Signal-by-signal analysis — all 35

**Legend.** *Class*: P prevalence · B binary policy · C consequence/assurance · D denominator.
*Direction*: PENALTY · BONUS (presence-only, never penalise absence) · GATE (pass/fail, not scored) · NORMALIZER.
*Evidence*: strength of the real-world anchor supporting the verdict.

### V.1 Cyber hygiene

| Signal | Class | Firmographics change the score? | Direction | Anchor · evidence |
|---|:--:|---|---|---|
| **SPF** | B | **No** | PENALTY (low-med) | dmarcian Sept 2025: **60% of 713 US .gov domains had SPF errors** — on mandated, audited, high-scrutiny domains. Budget was never the binding constraint. Score *correctness*, not presence: `+all` or a 10-lookup overflow is worse than a thoughtful absence. *(Moderate)* |
| **DKIM** | B | **No** | PENALTY (low) + strong *unknown* state | Selectors cannot be reliably enumerated externally — treat unobserved as **unknown, never failing**, and route the gap to Confidence. Google/Yahoo Feb 2024 bulk-sender rules bind a ten-person startup and a bank identically. *(Weak–Moderate)* |
| **DMARC** | B | **No** *(strongest cohort case in the catalogue — see Part VIII)* | PENALTY, ordinal: reject > quarantine > none > absent | F500 **95% adoption / 62.7% `p=reject`** vs Inc. 5000 **15.2%**. Score the *policy level*, not record presence: >500k domains sit at `p=none`, which offers zero protection; >70% lack RUA tags. FBI IC3 2025 puts BEC losses at **$3.05B**. *(Strong on adoption, Moderate on breach link)* |
| **DNSSEC** | B | **No** | **BONUS** | ~7–18% adoption depending on population measured (see [III.1](#iii1-a-conflict-between-the-sources-unresolved)). Penalising absence penalises the norm. Large operators decline it deliberately — misconfigured DNSSEC fails *closed* and takes the domain offline. Geography is a real modifier here: .cz 59%, .se 55%, .nl 51%, .sk 48%. *(Weak — say so in the report)* |
| **CAA** | B | **No** | **BONUS** | Symantec's 2015 unauthorised google.com test certificates — which ultimately cost the CA Chrome's trust — is the class of event CAA constrains. CA/B Forum obliges **CAs** to honour CAA; nothing obliges domain owners to publish it. *(Weak — no published breach correlation)* |
| **TLS version** | **P** | **No — exposure only** | PENALTY (high) | PCI DSS v3.2 required TLS 1.0 disabled by **30 June 2018**; RFC 8996 (2021) moved 1.0/1.1 to Historic; NIST SP 800-52r2 binds federal agencies. Dated, named obligations — which is why a PCI-attesting merchant negotiating TLS 1.0 is a **Compliance Contradiction**, not a heavier TLS penalty. Weight by **endpoint criticality** and **dispersion**. *(Strong on standards, Moderate on exploitation)* |
| **Cipher suites** | P | **No — exposure only** | PENALTY (graded) | **FREAK and Logjam (2015)** showed export-grade suites directly breakable; **POODLE (2014)** the same for SSLv3 CBC. Nothing comparable for TLS 1.2 CBC — collapsing "broken" and "deprecated" into one severity overstates the second. Correlated with TLS version: **do not double-count**. *(Moderate)* |
| **Certificate validity** | **P** | **No — exposure only. Highest-priority normalization** | PENALTY (med-high, **rising**) | **Equifax 2017: an expired certificate on a traffic-inspection device left encrypted traffic uninspected for ~19 months**, which is why the intrusion ran undetected for 76 days. **Ericsson Dec 2018: one expired certificate took O2 UK offline for ~32M subscribers.** Always score `expired / total observed`. *(Strong)* |
| **HSTS** | P | **No — exposure only** | PENALTY (low) | Exists because of Marlinspike's **sslstrip (2009)**, which needs an active network position. Browser HTTPS-first defaults have absorbed most of that risk — low weight, and weight a login portal far above a brochure page. *(Weak–Moderate)* |
| **CSP** | P | **No — exposure only** | PENALTY (low; **high if payment-adjacent**) | **British Airways 2018: a Magecart script on the payment page compromised ~380,000 card transactions; ICO fined £20M.** PCI DSS v4.0 req. 6.4.3 and 11.6.1 key off *page type*, not company size. Score policy **strength** — `unsafe-inline` ≈ worthless. *(Moderate for payments, Weak generally)* |
| **X-Frame-Options** | P | **No** | PENALTY (very low) | **Superseded by CSP `frame-ancestors` in CSP Level 2 (2014).** Flagging absence without checking CSP manufactures a false positive — and false positives are what vendors dispute. Accept either mechanism. *(Weak)* |
| **security.txt** | B | **No** | **BONUS only** | Below **0.25%** of domains, majority platform-provisioned; when present there is a **60% chance** it points to a platform's generic contact; only **44%** are RFC-conformant. Cheap to *measure*, which is precisely why its weight drifts upward unguarded. *(Speculative)* |

> **Platform-provisioning discount — apply across this whole category.** Cloud, PaaS and site-builder defaults hand small vendors free credit for HSTS, TLS 1.3, modern ciphers and security.txt that reflect Vercel's or Cloudflare's competence, not the vendor's. Detect provisioning (header fingerprints, ASN, default file contents) and discount accordingly. Without this, the hygiene score substantially measures **hosting choice**, and small cloud-native vendors will systematically outscore banks.

### V.2 Digital footprint

| Signal | Class | Firmographics change the score? | Direction | Anchor · evidence |
|---|:--:|---|---|---|
| **Subdomain count** | **D** | **Not scored** | NORMALIZER | SecurityScorecard scores every issue as a modified z-score where *"z = 1 when the number of findings equals the mean for organizations with the same size Digital Footprint."* The industry's largest rater treats footprint as the **denominator, never the numerator** — a 2,000-subdomain enterprise is not 200× riskier than a 10-subdomain startup, it is 200× larger. *(Strong)* |
| **CT history** | **D** | **Not scored** | Discovery input, always liveness-validated | Chrome has required all publicly-trusted certificates to be CT-logged since **April 2018** — which makes CT near-complete for discovery, and also why a 20-year-old company's log history is thick with long-dead hosts. Counting history as current surface systematically inflates old and large vendors. *(Strong, methodologically)* |
| **Shadow assets** | P | **No — exposure only** | PENALTY (high, on density + dwell) | **Verizon DBIR 2025: edge devices and VPNs rose from 3% to 22% of exploitation targets in one year**, only ~54% fully remediated (median 32 days). **MOVEit (2023)** was one forgotten internet-facing appliance repeated across 2,700+ organisations. Score `shadow / total discovered` and **mean time to removal**. *(Strong conceptually, Moderate in published correlation)* |

> **Two architectural exceptions that will otherwise sink real vendors.** **Multi-tenant SaaS** legitimately provisions per-customer subdomains and will show tens of thousands of names — that is architecture, not sprawl. Detect the pattern (naming regularity, shared wildcard certs, uniform infrastructure) and exclude it, or every SaaS vendor scores in the basement. **M&A activity** is a legitimate, measurable and rarely-used modifier: acquisitive companies inherit unmanaged infrastructure, and detecting acquisitions lets you contextualise sprawl instead of blindly punishing it.

### V.3 Breach and compromise

| Signal | Class | Firmographics change the score? | Direction | Anchor · evidence |
|---|:--:|---|---|---|
| **Public breach history** | C (+Posture) | **Slightly — but not by firmographics** | PENALTY, decayed + observability-weighted | **T-Mobile US disclosed breaches in 2018, 2019, 2020, 2021 and 2023** — the canonical case for recurrence outweighing recency. Drivers are recency, **recurrence**, root-cause repetition, and magnitude relative to scale. Disclosure regime → Confidence; sector cost → Impact. *(Strong)* |
| **Exposed data types** | **C** | **Leaves Posture entirely** | Impact / Vendor Tier | **IBM/Ponemon 2025: healthcare $7.42M per breach — highest for the 14th consecutive year — against public sector $2.86M.** That spread is entirely about what data was held, not how well the organisation was defended. *(Strong)* |
| **KEV** | P | **No — for anyone.** The strongest "no adjustment" case in the study | PENALTY (**highest**) + **GATE** candidate | **Bitsight TRACE across 1.4M organisations: over a third had at least one KEV in 2023, and 60% of KEVs remained unremediated past CISA deadlines.** Universal across every size band; mass-exploitation campaigns (Log4Shell, MOVEit) scan indiscriminately. **Automated exploitation does not consult Crunchbase.** Measure **days past due** — a firmographic-free maturity proxy far better than company age. *(Strong)* |
| **CVEs (raw)** | P | **No — exposure only** | PENALTY (low), heavily normalized | Two compounding problems: count *is* footprint, and external attribution is unreliable. Banner inference cannot see backports, so unnormalised counting **penalises the enterprise-standard practice** (RHEL/Ubuntu LTS). A WordPress vendor always shows more CVEs than a Go-monolith vendor at identical competence — that is a stack effect. *(Strong — that raw counts predict poorly)* |
| **CVSS** | Modifier | **No** | Modifier only, never standalone | FIRST's own specification defines Base metrics as intrinsic and constant across environments, putting context in the *Environmental* group — which requires asset criticality an outside-in rater does not have. **Inferring a bank's environmental modifiers from the fact that it is a bank is the exact unfounded judgement this report rules out.** *(Strong, on its limitations)* |
| **EPSS** | Modifier | **No — structurally cannot** | Continuous modifier | A calibrated probability with **no organisational term in it** — scaling it by revenue produces a number that is no longer a probability of anything. **KEV supersedes EPSS** (confirmed exploitation dominates a pre-threat-intel estimate). Be consistent about probability vs percentile, and re-pull daily. *(Strong)* |

### V.4 Governance

*All three share a structure: near-zero causal weight, moderate diagnostic weight, heavy confounding by sales motion and business model.*

| Signal | Class | Firmographics change the score? | Direction | Anchor · evidence |
|---|:--:|---|---|---|
| **Published security program** | C | **Leaves Posture** | BONUS → **Assurity** | **NIS2 Article 20 requires management-body approval and oversight — internal governance, not a public page.** No framework anywhere requires publishing one. What a trust centre reliably measures is *marketing maturity*: SaaS vendors publish them as competitive necessity; manufacturers and non-profits rarely do. *(Speculative)* |
| **Vulnerability disclosure policy** | B | **No — but weight scales with footprint** | BONUS + footprint-scaled PENALTY | The one governance signal with a genuine causal mechanism: a vendor with a large public attack surface and no reporting channel **cannot be told** about externally discovered flaws. **CISA BOD 20-01 (2020)** requires every US federal civilian agency to publish a VDP; the **EU Cyber Resilience Act** extends disclosure duties to suppliers from 2026. Do not blur the cost asymmetry: a VDP is a policy plus an inbox; a bug bounty is a budget line. *(Moderate)* |
| **Security contact** | B | **No** | BONUS (lowest) — **merge with security.txt** | RFC 9116's `Contact:` field, a VDP page, and a published security address are usually **the same fact observed three ways**. Under flat penalty accumulation that fact is charged three times, quietly making Governance heavier than any deliberate weighting decision would have made it. *(Weak)* |

### V.5 Business

| Signal | Class | Firmographics change the score? | Direction | Anchor · evidence |
|---|:--:|---|---|---|
| **Domain age** | C | **Leaves Posture** | **GATE** (fraud) + NORMALIZER | **Aged domains are purchasable — any weight here is a weight an adversary can buy.** >70% of newly registered domains are malicious/suspicious, but **strategically aged domains show a malicious rate more than 3× higher than newly registered ones (22.27%)** — actors register years in advance specifically to evade reputation scoring. Honest uses: consistency gate, fraud screen, denominator. *(Weak for security, Moderate for fraud)* |
| **Domain registration quality** | B | **No** *(expectation may be cohort-scaled)* | PENALTY (moderate) | **DNSpionage and Sea Turtle (2018–19) hijacked government and telecom domains at the registrar and registry layer** — serious enough that CISA issued **Emergency Directive 19-01**. Hijack yields email interception, certificate issuance and often SSO takeover simultaneously. **Do not penalise privacy-protected WHOIS** — GDPR-era default; that is geographic bias in disguise. *(Weak–Moderate)* |
| **Legal entity status** | C | **Leaves Posture** | **GATE** | No security framework — NIST, ISO 27001, CIS, NIS2 — treats company registration standing as a security control. A genuine counterparty-risk fact and a non-fact about compromise likelihood. Route unverifiable jurisdictions to manual review; **never penalise a vendor for its registry's practices.** *(N/A for security)* |
| **Company age** | C | **Leaves Posture** | **NORMALIZER + cohort assignment only** | **The evidence here is an absence, and it is worth stating as one: not one of Bitsight, SecurityScorecard, RiskRecon, Cyentia, NIST, ENISA or CISA scores or normalises by founding date.** Cyentia corroborates: "not much difference in fix speeds between small, medium, and large organizations" — legacy debt and program maturity largely cancel. *(Absent — do not fill the gap with intuition)* |
| **Company continuity** | C | **Leaves Posture — deserves its own dimension** | PENALTY on a separate **Continuity** axis | **DORA and NIS2 both require supply-chain and continuity assessment as an obligation distinct from cybersecurity risk management** — the regulators keep the two apart. Going-concern signals predict two distinct failures: abrupt service loss, and control decay as security is cut first. One of the few places revenue and funding stage are *directly* relevant. *(Weak for direct security correlation)* |

### V.6 Compliance

| Signal | Class | Firmographics change the score? | Direction | Anchor · evidence |
|---|:--:|---|---|---|
| **ISO 27001** | C | **Leaves Posture** | BONUS → **Assurity** | **Certified organisations are breached routinely, because a certificate attests that an ISMS was audited against a declared scope — and Statements of Applicability are frequently narrow.** A certificate whose SoA excludes the product you are buying is not evidence about that product. **Score scope, not presence.** Penalising absence is a tax on audit budget — the most demographically biased element available. Geography matters: ISO in EU/APAC, SOC 2 in the US. *(Weak for breach correlation, Strong for procurement relevance)* |
| **SOC reports** | C | **Leaves Posture** | BONUS → **Assurity** | **A SOC 2 Type II requires a 6–12 month observation window, so it is *structurally impossible* for a company under a year old** — penalising its absence at a startup penalises the passage of time. **Score type and period, not presence:** Type II with no qualified opinions ≫ Type I snapshot. The value is in the exceptions and carve-outs, not the yes/no. *(Weak for breach correlation)* |
| **Regulatory disclosures** | C→Confidence | **No in Posture — Yes in Confidence** | BONUS only, never penalty | **SEC Item 1.05 8-K material-incident disclosure (Dec 2023) binds registrants only**; private companies below notification thresholds may have breaches that never surface. "No disclosed breaches" at a private vendor and at an SEC registrant are **different quantities** — a coverage fact, so the correction belongs in Confidence. If absence costs points, you have built a public-company preference, not a risk model. *(Strong for the bias; the correction is rarely implemented anywhere)* |

> **Ceiling caveat for both certifications.** The empirical literature is clear that certification is not immunity, and that symbolic adoption can be actively counterproductive. **Cap the maximum credit any certification can contribute, and never let a certification offset a KEV or an active exposure.** Certification evidence and observed-posture evidence answer different questions.

### V.7 Reputation

*The noisiest and most size-biased category. Weight conservatively, require corroboration, be strict about relevance.*

| Signal | Class | Firmographics change the score? | Direction | Anchor · evidence |
|---|:--:|---|---|---|
| **Regulatory enforcement** | C (+Posture) | **No in Posture — Yes in Confidence** | PENALTY (high, decayed) | **The ICO's security fines land on large, visible names — British Airways £20M, Marriott £18.4M** — because regulators pursue greater harm, deterrent value and cost recovery. A clean enforcement record at a small private vendor is *much weaker evidence* than at a supervised entity. **Be strict on relevance:** an environmental fine or antitrust action is not a cyber signal. *(Moderate)* |
| **Government investigations** | C | **Leaves Posture** | **Manual review; ~0 automatic** | An open investigation is an **allegation, not a finding**, carrying the same large-target selection bias as enforcement, amplified. The **US Chamber Principles** require ratings be "empirical, data-driven, or notated as expert opinion" — scoring an unadjudicated allegation fails that test and creates defamation exposure. **Worst precision-to-defamation ratio in the framework.** *(Weak)* |
| **Verified adverse media** | C | **Leaves Posture. Most size-confounded signal in the catalogue** | PENALTY (low), heavily normalized | **A consumer brand and a private B2B vendor suffering identical incidents generate coverage differing by orders of magnitude.** Media volume tracks visibility, not security quality. **If you score raw adverse-media count, you have built a company-fame detector.** Required: normalize to adverse *share*; entity-resolution confidence threshold; category filtering; source tiering; recency decay; and treat low coverage in under-covered non-English markets as an **artifact, not a clean record**. *(Weak)* |

---

## Part VI · Critique of the current model

### VI.0 What is genuinely right and must survive the migration

The system under review is unusually honest for its class. It refuses to publish a score it cannot evidence, it stores evidence before it scores, it fails the loader if a penalising band has no plain-English reason, it refuses to score natural persons, and it keeps a frozen regression corpus that has already falsified one of its own claims. **The defects below are the defects of a careful model, not a careless one.**

| Decision | Verdict |
|---|---|
| Posture and Confidence as orthogonal axes | **Keep — best decision in the model.** Structurally solves the observability bias that corrupts most ratings |
| Confidence never changes posture | **Keep, with one amendment** — it should gate *publication*, not arithmetic (already accepted via the Ghost) |
| The Ghost (suppress below 40% coverage) | **Keep the principle, fix the cliff** |
| Ongoing issues never decay | **Keep — correct and rare.** If live misconfigurations decayed, vendors could wait out findings rather than fix them |
| Subtractive transparency | **Keep the mechanic, fix the prior and the floor** |
| Benchmarking affects interpretation only | **Keep the principle** — peer-relative scoring is non-stationary and non-reproducible |

### VI.1 The defects, ranked by how likely they are to be biting today

| # | Defect | Mechanism | Fix |
|--:|---|---|---|
| 1 | **Hygiene trivia outranks active exploitation** | No category weights + linear summation of correlated findings | [VII.3](#vii3-aggregation--two-competing-proposals) |
| 2 | **Large vendors penalised for being large** | No exposure denominator; linear frequency multiplier | [VII.1](#vii1-exposure-normalization--the-mandatory-change) |
| 3 | **Multi-tenant SaaS vendors bottom out** | Per-tenant subdomains × linear frequency | Tenant-pattern detection before computing the denominator |
| 4 | **Opacity is rewarded** | The Ghost suppresses scores that would otherwise be bad | [VII.4](#vii4-confidence-and-the-ghost) |
| 5 | **Ungoverned reweighting on every release** | Emergent category weight = detection inventory | Explicit versioned weights |
| 6 | **No discrimination among the worst vendors** | Floor at 0; three Criticals saturate | Bounded log-odds; retain unclamped raw score |
| 7 | **Small cloud-hosted vendors outscore banks** | Platform-provisioned hygiene credited to the vendor | Provisioning discount ([V.1](#v1-cyber-hygiene)) |
| 8 | **Mitigation becomes score laundering** | ×0.6 with no TTL, no artifact requirement, no audit trail | [VII.5](#vii5-mitigation--a-taxonomy-not-a-constant) |
| 9 | **Scores start tracking vendor sales capacity** | "Human-approved" discretion favours vendors with account teams | Artifact-based evidence requirement |
| 10 | **Risk acceptance corrupts the instrument** | Your appetite modifies their measured posture | Acceptance ×1.0, tracked separately |
| 11 | **One root cause counted four times** | TLS 1.0 → ciphers → PFS → AEAD; KEV → CVE → CVSS → EPSS | [VII.6](#vii6-root-cause-deduplication) |
| 12 | **Tiny vendors publish as 100** | No denominator; no evidence-volume component in Confidence | Ceiling ramp / shrinkage |
| — | *Waiting out findings* | **Not present** — the no-decay-on-ongoing rule closes this | **Keep as-is** |

### VI.2 "No category weights" does not remove weighting — it hides it

**The claim:** categories emerge naturally from accumulated penalties, so no weights are needed.

**The reality:** if categories emerge from accumulated penalties, each category's effective weight equals *the number of distinct findings the scanner can generate in it, times their severities.* Weighting has not been eliminated — it has been **delegated to the detection inventory.**

Work the arithmetic. Cyber Hygiene contains twelve signals. A vendor failing four at Medium and eight at Low:

```
4 × 8 = 32
8 × 3 = 24
        ──
        56 points
```

A different vendor with a single actively-exploited vulnerability on an internet-facing authenticated endpoint:

```
1 × 40 = 40 points
```

**The vendor missing a dozen headers and DNS records scores worse than the vendor being actively exploited.** Not an edge case — the modal outcome, because hygiene findings are numerous, cheap to detect, and highly correlated, while KEV findings are singular. The evidence says this ordering is exactly backwards: vulnerability exploitation is now the top breach entry point at **31% of breaches**, the first time in 19 years it has surpassed stolen credentials.

Three compounding sub-problems:

- **(a) Correlated stacking.** SPF, DKIM, DMARC, DNSSEC, CAA, HSTS, CSP, XFO and security.txt all partly measure one latent variable: *"does this organisation have someone who reads RFCs."* Summing nine correlated measurements of one thing gives that thing nine times the weight of an uncorrelated, higher-precision signal.
- **(b) Root-cause double counting.** One TLS 1.0 endpoint can produce a protocol finding, a weak-cipher finding, a no-forward-secrecy finding and a no-AEAD finding. Four penalties, one root cause, **one remediation action**.
- **(c) Ungoverned model drift.** Every new detection silently reweights the entire model. Add three header checks and web hygiene gains weight against vulnerability management — with no decision, no review, and no notice. Under the model-governance principle this is a material methodology change disguised as a feature release.

### VI.3 The scale saturates at both ends

**Bottom.** Three Criticals reach 120 points against a 100-point scale. A vendor with three Criticals and one with fifteen both publish as 0. **You lose all discrimination precisely where your highest-risk vendors sit** — and where triage decisions are most consequential.

**Top.** A vendor with no findings scores 100 regardless of whether it is a hardened bank or a three-page brochure site with nothing to find. **Absence of findings scales with absence of attack surface.** With no denominator anywhere, the model cannot distinguish "clean because well-run" from "clean because tiny."

A subtle interaction with Confidence: a three-host vendor can achieve *very high check coverage* while resting on a *very thin evidence base*. Coverage ratio and evidence volume are different quantities, and Confidence currently measures only the first.

### VI.4 Starting at 100 encodes an unjustified prior

"Innocent until proven guilty" is the right ethical posture and the wrong statistical one. Roughly **one in four Fortune 1000 firms suffers a cyber loss event annually**; security debt affects **82% of organizations**; only **23% of third-party organizations** fully remediated missing or improperly secured MFA on cloud accounts. A vendor at 45% coverage with zero findings publishing as 100 is almost certainly wrong.

### VI.5 `industry_profiles` contradicts `benchmarks.yaml` — and the whole market

The shipped model promotes severity by industry. This is mechanism #10 in [Part VII.7](#vii7-the-twelve-candidate-mechanisms-scored) — *dynamic severity adjustment* — and it is the one every commercial platform declines to implement. It also contradicts the project's own `benchmarks.yaml`, which states that interpretation lives in benchmarking and never in the arithmetic. **These two files currently disagree with each other.**

---

## Part VII · The revised model

### VII.1 Exposure normalization — the mandatory change

For each Class-P signal, replace the raw count with a smoothed rate:

```
r̂_s = (f_s + α_s) / (D_s + α_s + β_s)          # beta-binomial posterior mean
g_s = λ_s·r̂_s + (1 − λ_s)·min(1, f_s/κ_s)      # blend rate with an absolute floor
```

where `f_s` is findings, `D_s` the observed denominator (hosts, certs, endpoints), and the `α/β` priors prevent a 1-of-1 failure reading as 100%. The `κ_s` term preserves an absolute component so a large vendor cannot dilute a genuinely severe finding to nothing.

**Multi-tenant detection is mandatory before computing `D_s`.** Detect per-tenant provisioning (naming regularity, shared wildcard certificates, uniform infrastructure fingerprints) and exclude those names from both the denominator and the finding counts.

Worked comparison, ten expired certificates:

| Vendor | Certs | Expired | Current model | Revised |
|---|--:|--:|--:|--:|
| A | 4,000 | 10 | ×10 | ×1.0 (at or below expectation) |
| B | 3 | 2 | ×2 | ×2.4 (far above expectation) |

**The current model ranks these backwards by a factor of five.**

### VII.2 Per-signal weight

```
w_i(vendor) = w_i^base
            × D_i(cohort)        # diagnosticity: peer base-rate adjustment
            × O_i(obligation)    # regulatory / contractual duty
            × C_i(consequence)   # blast-radius relevance to you
            ÷ N_i(exposure)      # footprint normalizer for count-based signals
```

Constraints:

- **`D_i` from surprisal** where labels are unavailable: `D_i = clamp(−log₂(P(finding|cohort)) / k, 0.5, 2.5)`
- **`D_i` from likelihood ratios** once outcome labels exist: `D_i = clamp(log(LR_cohort), bounds)`
- **Bound the product:** `D × O × C ∈ [0.5, 2.5]` per signal; total firmographic influence on composite posture ≤ **20–25%**
- **Log-scale all count normalizers**, bounded at the tails
- **Percentile-rank within cohort** for presentation only

### VII.3 Aggregation — two competing proposals

The sources offer two different fixes for defect #1. **They are not compatible; pick one.**

**Proposal A — diminishing returns within category** *(`methodology-evaluation-and-redesign.md`)*

```
CategoryPenalty(c) = Σᵢ pᵢ · λ^(rankᵢ − 1)      λ = 0.7, rank by descending pᵢ
RawPosture         = 100 − Σ_c CategoryPenalty(c) + min(DiligenceCredit, 10)
Posture            = clamp(RawPosture, 0, Ceiling(confidence))
```

Twelve hygiene failures (four Medium, eight Low) now total **≈15.9** against one Critical KEV at 50 — the vulnerability dominates by better than 3:1. **Correct ordering restored without introducing category weights**, which preserves the emergence principle while killing the correlated-stacking bug. Also widens the ladder to **50 / 20 / 6 / 1.5** (Critical:Low becomes 33:1, from 13:1) and routes Informational findings into Confidence.

**Proposal B — bounded log-odds accumulation** *(`new_research_meth.md`)*

```
z_s = w_sev(s) · a(s) · φ(s) · m(s) · g_s · κ_cat(s)
L   = L₀ + Σ_s z_s
L̃   = c^τ·L + (1 − c^τ)·L_peer                  # shrinkage toward cohort prior
Posture = 100 · (1 − σ(L̃))
```

Never floors, never saturates, keeps discrimination in the bottom quartile, and makes the Ghost cliff unnecessary by shrinking toward the cohort prior instead of refusing.

**Recommendation:** Proposal A is a smaller change and preserves more of the current model's explainability — every point still traces to a finding. Proposal B is statistically better and solves saturation, which A only partially addresses via the unclamped raw score. **Take A first as a two-week fix, and treat B as the destination.**

### VII.4 Confidence and the Ghost

Three problems with a hard 40% gate: it is a **discontinuity** (39.9% → no score; 40.1% → potentially 100); **coverage is not uniform in value** (40% that includes KEV assessment is worth vastly more than 40% of HTTP headers); and **it creates an incentive to be unscannable**.

Again two proposals:

**Ceiling ramp** *(evaluation doc)* — posture arithmetic untouched; confidence bounds only what you are willing to assert:

```
< 40%    → no publish; "Insufficient Evidence" (explicitly ADVERSE); manual review required
40–60%   → publish, ceiling 80
60–75%   → publish, ceiling 90
75–90%   → publish, ceiling 97
≥ 90%    → publish, ceiling 100
```

**Shrinkage** *(research-meth doc)* — at `c = 0.3`, roughly 84% of the estimate is the cohort prior, and the report says so. **A vendor who becomes unmeasurable gets their cohort's median, not a free pass** — which removes the gaming vector entirely, because hiding no longer produces a better outcome than being average. Retain outright refusal only below `c ≈ 0.15`.

Both proposals agree on the critical governance point: **publish "Insufficient Evidence" as an explicitly adverse state, not a neutral absence**, and route it mandatorily to manual assessment. Procurement must not be able to read a Ghost as a pass.

**Two narrow, legitimate firmographic corrections to Confidence** — the only place in the model where public/private status touches the arithmetic:

```
c_breach       *= δ_disclosure     1.0 SEC registrant / HHS-covered / GDPR Art.33; 0.6 private, no mandatory regime
c_enforcement  *= δ_supervision    1.0 actively supervised sector; 0.7 unsupervised
```

The effect is that "no breaches found" at a small private vendor produces *lower confidence*, not *equal posture*.

### VII.5 Mitigation — a taxonomy, not a constant

| Class | Meaning | Factor | Expiry |
|---|---|--:|---|
| Vendor claim, uncorroborated | "We've handled it" with no artifact | **1.00** | n/a — no credit |
| Vendor claim + plausible documentation | | **0.85** | 90 days |
| Independent re-observation of a partial fix | | **0.60** | 180 days |
| Independent re-observation: condition absent | | **0.25** | 365 days, then re-verify |
| Condition absent + root cause evidenced | | **0.10** | 365 days |
| **Risk accepted by your business owner** | Your appetite, not their security | **×1.0 — must not change posture** | — |

That last row matters most. **Risk acceptance is a property of your risk appetite, not of the vendor's security posture.** If accepting a risk improves the vendor's score, you have corrupted the measurement instrument with your own tolerance, and next quarter you will read your own acceptance back as evidence of vendor quality.

Three further requirements: **TTLs are not optional** (an unexpiring mitigation is a permanent discount for a one-time claim); every grant carries analyst identity, evidence reference, timestamp and expiry in the receipt; and Tier 3–4 grants should eventually be **automatic rather than human** — a re-scan showing the cert is now valid is machine-verifiable, and machine grants cannot be socially pressured.

### VII.6 Root-cause deduplication

| Cluster | Rule |
|---|---|
| KEV / CVE / CVSS / EPSS | Precedence **KEV > EPSS > CVSS**. One penalty; others become modifiers, never additive items |
| TLS version / cipher suites | Score the protocol finding. Ciphers add an increment only where they carry information beyond the version |
| CSP / X-Frame-Options | `frame-ancestors` satisfies XFO. Accept either. Never penalize twice |
| Subdomains / shadow assets / CT anomalies | One footprint model, several views. One penalty per distinct asset defect |

> **Rule of thumb: one remediation ticket, one penalty.** If fixing one thing clears four findings, it was one finding.

### VII.7 The twelve candidate mechanisms, scored

| # | Approach | Predictive | Fairness | Explainability | Gaming resistance | Soundness | **Verdict** |
|--:|---|---|---|---|---|---|---|
| 1 | Firmographic multipliers (revenue/headcount × severity) | ✗ | ✗ | ~ | ✗ | ✗ | **Reject** |
| 2 | **Exposure normalization** (rate with denominator) | ✅ | ✅ | ✅ | ✅ | ✅ | **Adopt — mandatory** |
| 3 | Bayesian priors (cohort prior, evidence updates) | ✅ | ✅ | ~ | ✅ | ✅✅ | **Adopt for Confidence/shrinkage** |
| 4 | Logistic scaling (bounded log-odds → score) | ✅ | ✅ | ~ | ✅ | ✅✅ | **Adopt** |
| 5 | **Expectation Gap as an output** | ~ | ✅✅ | ✅✅ | ✅ | ✅ | **Adopt — this is the answer to the research question** |
| 6 | Industry-specific baselines (calibrate scale, score identically) | ✅ | ✅ | ✅ | ✅ | ✅ | **Adopt in benchmarking** |
| 7 | Compliance-gap findings | ~ | ✅ | ✅✅ | ✅✅ | ✅ | **Adopt** |
| 8 | Signal-specific weighting (explicit, published, tunable) | ✅ | ✅ | ✅ | ~ | ~ | **Adopt — implicit weights already exist** |
| 9 | Confidence adjustments (disclosure regime, coverage) | ~ | ✅ | ✅ | ✅ | ✅ | **Adopt, narrowly** |
| 10 | Dynamic severity adjustment | ✗ | ✗ | ✗ | ✗ | ✗ | **Reject — this is what `industry_profiles` does today** |
| 11 | Baseline maturity curves (expected posture as f(age)) | ✗ | ✗ | ~ | ✗ | ✗ | **Reject** |
| 12 | **Hybrid (2+3+4+5+6+7+8+9)** | ✅✅ | ✅✅ | ✅ | ✅✅ | ✅✅ | **The recommendation** |

**Why mechanism 1 fails, on five independent grounds:** no published evidence links revenue to compromise likelihood independent of attack surface; the premise is contradicted (no size difference in fix speeds); the direction is contradicted (large firms already have better DMARC); it fails the US Chamber Principles on transparency, dispute and empirical basis; and it destroys comparability.

### VII.8 The new dimensions

**Assurity** — the quarantine for audit-budget effects. Positive-only accumulation, 0–100, reported beside Posture and never merged with it:

```
Assurity = 100 · σ( A₀ + Σ_j v_j · valid_j · scope_j − Σ_k γ_k · ComplianceGap_k )
```

| Component | Weight | Notes |
|---|--:|---|
| ISO 27001 certificate | 1.0 | × `scope_j` — an SoA excluding the assessed product scores near zero |
| SOC 2 Type II | 1.2 | Type II > Type I; report-period recency matters |
| PCI DSS AoC | 0.8 | Only where payment handling is in scope |
| Published security program / trust page | 0.4 | |
| VDP | 0.5 | |
| Named security contact / security.txt | 0.2 | Merged — one fact, one score |
| Public pentest summary or bug bounty | 0.6 | |
| **Compliance Gap** | **−γ ≈ 1.5** | **A contradicted claim is worse than no claim** |

**Absence never subtracts.** A vendor with no certifications has low Assurity, not bad Posture. This is the single most important structural fix for demographic fairness in the model.

**Compliance Gap** — a new finding class. Where a vendor asserts (or is bound by) framework `F` and is observed failing a control `c ∈ C(F)`, emit a cited finding. *"Vendor asserts PCI DSS compliance and negotiates TLS 1.0"* is not a more severe TLS finding — it is a distinct, high-signal finding about the reliability of the vendor's own attestations. Gaming it means dropping the claim, which is itself informative.

**Expectation Gap** — where every firmographic legitimately lives:

```
EG = Posture − E[Posture | cohort]
```

Publish the absolute posture (always), `E[Posture | cohort]` with `n` and the widening rung reached, `EG` with its sign and a plain-English reading, and the self-selection caveat verbatim. This delivers the research question's entire intuition with more force than a multiplier and none of the cost:

> *"Posture 68. Median for financial services, 1,000–10,000 staff, ANZ (n=14): 87. **This vendor sits 19 points below its peer group and in the bottom decile of it.** The gap is driven by absent DMARC (95% of Fortune 500 peers have it, 62.7% at `p=reject`) and by TLS 1.0 on 8 of 340 checked hosts."*

**Impact / Tier** — the buyer's side. Compute a Criticality Tier per *relationship* from data classes held, integration depth, OAuth scopes, network access, business criticality and substitutability. Drive action from the matrix, never a blended number:

| | T1 Critical | T2 Important | T3 Standard | T4 Low |
|---|---|---|---|---|
| **Posture ≥ 85** | Annual review | Annual | Biennial | Passive |
| **70–84** | Quarterly + remediation plan | Semi-annual | Annual | Passive |
| **50–69** | Remediation plan, contractual milestones | Quarterly | Annual | Passive |
| **< 50** | Escalate; do not onboard without exception | Remediation plan | Monitor | Monitor |
| **Insufficient Evidence** | **Mandatory manual assessment** | Manual assessment | Questionnaire | Monitor |
| **Gate triggered** | **Block** | Block | Escalate | Escalate |

**Continuity — structured flags, deliberately not a score.** Class-C signals leave Posture (§VII.7) and need a destination. That destination is a set of **registry-cited going-concern flags**, not a 0–100 axis:

> *"In administration — Companies House company status, retrieved 2026-07-29."*

Three reasons this stays flags rather than becoming a fifth number:

1. **The sources do not specify a scored continuity axis.** They establish that entity status and company age must leave Posture; they do not establish an arithmetic for what replaces them. A number here would be invention wearing the report's authority.
2. **Four registry bands cannot support 0–100 precision.** `entity_status` has four bands, `entity_existence` two. Compressing them onto a hundred-point scale asserts a resolution the underlying registers do not have.
3. **Legal exposure differs in kind from Posture.** A cited register fact sits on the same footing as every other published observation. A *derived* distress index — inferred runway, a bankruptcy-risk score — is closer to credit-rating territory and is defamation-adjacent when wrong. Publish the fact and its retrieval date; do not publish an inference about solvency.

Financial markers route by the same discipline: **going-concern facts → Continuity flags · public-vs-private status → Confidence multiplier · revenue and headcount bands → cohort assignment · everything else → discard.** Markers with no lawful free source (funding runway, cash burn, Altman Z-score, market share) stay in `held_roadmap` rather than being asserted — the position `gleif_collector` already records: *"Financial-distress (going concern), litigation, and ownership-CHANGE remain HELD."*

**Residual Risk — a derived view, not a dimension.** The Posture × Tier matrix above is a lookup over two published inputs, and it must be presented as one. It is a procurement decision aid, not an independent measurement: a vendor disputes its Posture or its Tier, never the cell they land in. Treating it as a peer of Posture would imply a third thing was measured when nothing was.

### VII.9 Gates — findings that bypass arithmetic entirely

Everything in the current model is arithmetic, so everything is fungible. A vendor at 100 with one actively-exploited internet-facing vulnerability publishes at 60 and clears a "≥50" procurement threshold.

- KEV past its remediation due date on an internet-facing authenticated or data-bearing asset
- Legal entity dissolved, struck off, or not in good standing
- No valid TLS on a data-bearing endpoint
- Ownership or attribution unresolvable
- *(existing)* Sanctions hit → adjudication queue
- *(existing)* Entity confidence < 0.5 → manual confirmation

### VII.10 The complete model, one page

```
── GATES ──────────────────────────────────────────────────────────────
   sanctions hit → BLOCK, adjudication queue, no score
   entity confidence < 0.5 → BLOCK, manual confirmation
   KEV past due on internet-facing auth/data asset → BLOCK
   dissolved entity · no TLS on data-bearing endpoint → BLOCK

── POSTURE ────────────────────────────────────────────────────────────
   Class-P signal s:   r̂_s = (f_s + α_s) / (D_s + α_s + β_s)
                       g_s = λ_s·r̂_s + (1−λ_s)·min(1, f_s/κ_s)
   Class-B signal s:   g_s = 1 if failing band met else 0

   z_s = w_sev(s) · a(s) · φ(s) · m(s) · g_s · κ_cat(s)
   L   = L₀ + Σ_s z_s
   L̃   = c^τ·L + (1−c^τ)·L_peer
   Posture = 100 · (1 − σ(L̃))

   if directly-observed current critical AND attribution ≥ 0.7 AND cause nameable:
       Posture = min(Posture, 49)          # caps down, never floors up

── CONFIDENCE ─────────────────────────────────────────────────────────
   c = Σ(covered signals) / Σ(planned signals)
   c_breach *= δ_disclosure ; c_enforcement *= δ_supervision
   interval width ∝ 1/√(effective observations)
   refuse only below c ≈ 0.15

── ASSURITY ───────────────────────────────────────────────────────────
   Assurity = 100·σ( A₀ + Σ_j v_j·valid_j·scope_j − Σ_k γ_k·ComplianceGap_k )
   absence never subtracts

── COMPLIANCE GAP ─────────────────────────────────────────────────────
   asserted/mandatory framework F, observed failure of c ∈ C(F)
   → cited finding; reduces Assurity; never touches Posture

── EXPECTATION GAP ────────────────────────────────────────────────────
   EG = Posture − E[Posture | cohort]
   cohort from the widening ladder; n and rung always disclosed
   ── every firmographic the research question asked about lives here ──

── IMPACT / TIER ──────────────────────────────────────────────────────
   Impact   = h(buyer-side engagement properties)
   Priority = Impact × (1 − Posture/100)
```

---

## Part VIII · Where the sources disagree

**No source document contains this section.** These three disagreements are substantive, and two of them change what you would build.

### VIII.1 May severity be cohort-scaled? — the sources split 3–2

| Position | Sources | Argument |
|---|---|---|
| **Never.** Severity is a property of the technical condition | `context-aware-...`, `new_research_meth`, `signal_affect` | Cohort-scaled severity is mechanism #10, *dynamic severity adjustment*, rejected on comparability grounds. "0 of 35 signals" justify a firmographic multiplier. Every commercial platform declines it |
| **Yes, via a versioned lookup table** | `vendor-signal-weighting`, `methodology-evaluation-...` | `Severity = SeverityTable[finding_type][cohort]` is still a **fixed constant at scoring time** — reproducible, auditable, disputable, explainable ("in your cohort, 95% of comparable organisations enforce DMARC; you do not"). It is empirically calibrated priors, not live ranking. And the evidence for diagnosticity is real: missing DMARC in an F500 cohort is 4.3 bits, missing DNSSEC globally is 0.12 bits — a 35× difference the current model expresses as one number |

The evaluation doc goes furthest, proposing concrete per-cohort values: **DMARC absent = 1.5 (micro) / 6 (mid) / 20 (enterprise-regulated)**.

**This is a genuine, unresolved design fork.** The versioned-table position is stronger than the "never" position acknowledges — a table fixed at scoring time really does preserve reproducibility, and the surprisal argument is mathematically sound. But the "never" position holds the decisive practical card: **a cohort-scaled severity means the same technical condition produces different numbers for different vendors, so the threshold "we don't onboard below 65" stops meaning one thing**, and Bitsight's outcome-validation chart becomes unproducible.

**Recommendation: take the Expectation Gap route (mechanism 5) rather than cohort-scaled severity (mechanism 10).** Both express the same diagnosticity insight, but only one keeps the score comparable. The DMARC example is decisive on its own — a large firm without DMARC is *already* a ~4th-percentile outlier in its cohort, so the benchmark delta communicates the anomaly at full strength with no arithmetic change at all. If you later find the Expectation Gap insufficient, the versioned table is the correct second choice; a bare multiplier never is.

### VIII.2 Aggregation — diminishing returns or log-odds?

See [VII.3](#vii3-aggregation--two-competing-proposals). Both fix defect #1; they are not compatible. **Recommendation: λ=0.7 diminishing returns first (small, preserves explainability), log-odds as the destination (solves saturation, which the former only partially addresses).**

### VIII.3 The Ghost — ceiling ramp or shrinkage?

See [VII.4](#vii4-confidence-and-the-ghost). The ceiling ramp preserves the current axiom exactly and is a smaller change. Shrinkage is stronger against gaming, because it removes the incentive entirely rather than softening it. **Recommendation: ceiling ramp now; shrinkage when the cohort medians are dense enough to be a trustworthy prior** — which they are not today.

### VIII.4 A numeric conflict

DNSSEC adoption is cited at ~7% and 18.0% in different sources. See [III.1](#iii1-a-conflict-between-the-sources-unresolved). The practical conclusion (bonus, never penalty) is unchanged under either figure, but the discrepancy should be resolved before either number is quoted to a client.

---

## Part IX · Recommendations, tiered

### IX.1 Strongly recommended

1. **Exposure denominators on all Class-P signals.** Removes an existing bias. Highest impact.
2. **No firmographic multipliers in Posture.** No revenue, headcount, market-cap or age multiplier on severity or penalty.
3. **Fix the aggregation** — diminishing returns within category, then bounded log-odds.
4. **Make weights explicit and versioned.** You already have implicit weights; publish them.
5. **Delete `industry_profiles` severity promotions; replace with Compliance Gap.**
6. **Move ISO / SOC / published program out of Posture into Assurity.**
7. **Reclassify the ~10 low-base-rate signals from penalty to bonus** — DNSSEC, CAA, security.txt, VDP, trust page, security contact, ISO, SOC, regulatory disclosures, registry lock. *Roughly a third of the signal list.* Highest-leverage single change for noise reduction.
8. **Add gates** (VII.9).
9. **Expectation Gap as a published output.**
10. **Root-cause deduplication** (VII.6).
11. **Class the mitigation multiplier**, add TTLs and artifact requirements, separate risk acceptance out of posture entirely.
12. **Observability weight on every absence-of-evidence signal.**
13. **Measure dwell time** for KEV, expired certs and TLS findings — and let it **override** age-based reasoning wherever available.

### IX.2 Reasonable but optional

- Continuous Confidence with prediction intervals
- Separate Continuity dimension for going-concern signals
- Impact / Tier dimension and the action matrix
- Scheduled certificate-weight increases at the **March 2027 and March 2029** CA/B Forum boundaries — recorded now as a planned model-governance change rather than discovered later as drift

### IX.3 Not recommended

- Firmographic severity multipliers *(mechanism 1)*
- Dynamic severity adjustment *(mechanism 10 — what `industry_profiles` does today)*
- Baseline maturity curves as a function of company age *(mechanism 11)*
- **Any geography or nationality adjustment in Posture.** Weakly predictive, ethically fraught, legally exposed

---

## Part X · Migration plan

Ordered by impact-to-effort. **Items 1–4 change rankings.**

| Phase | Work | Duration |
|---|---|---|
| **0 — Instrument** | Baseline everything before changing anything. Run the firmographics-only ablation now, so you have a baseline to demonstrate improvement against | 1–2 weeks |
| **1 — Structural relocations** | Move ISO/SOC/program to Assurity; reclassify low-base-rate signals to bonus; add gates. *No arithmetic change to what remains* | 2–3 weeks |
| **2 — Exposure normalization** | Denominators on all Class-P signals; multi-tenant detection. **The big one** | 3–4 weeks |
| **3 — Aggregation** | λ=0.7 diminishing returns; widened ladder; Informational → Confidence | 2–3 weeks |
| **4 — Context outputs** | Expectation Gap, Compliance Gap, Impact/Tier | 3–4 weeks |
| **5 — Validation** | Ongoing, starts at Phase 2 | — |

**What must not change:** the Posture/Confidence split; evidence stored before scoring; the loader refusing a penalising band with no plain-English reason; no natural-person data; the frozen regression corpus; and the no-decay-on-ongoing-findings rule.

---

## Part XI · Validation protocol

### XI.1 The single most important test

> **Ablate all posture signals. Score vendors using firmographics alone. Compare AUC against the full model.**

If firmographics-only performs close to the full model, you have not built a security rating — you have built a firmographic classifier with security-themed features. **Given the linear frequency multiplier in the current design, expect this test to be uncomfortable today.** That is precisely why it is worth running *before* any changes, so there is a baseline to demonstrate improvement against.

Run the mirror test too: posture-only versus full model. If firmographics add nothing measurable, drop them and keep the simpler system.

### XI.2 Backtest properly

External signals do carry real predictive information — Liu et al. predicted incidents from **258 externally measurable features** across mismanagement symptoms and malicious-activity time series, with **mismanagement features ranking as the most important class** and **dynamic features outperforming static ones**. That last finding directly endorses both the no-decay-on-ongoing rule and dwell-time measurement over static snapshots.

Requirements:

- **Report discrimination within cohort, never pooled.** Pooled AUC is inflated by the model's ability to detect size, which correlates with disclosure probability — you would be measuring your own selection bias and reporting it as accuracy.
- **Report calibration, not just ranking.** A model that orders well but is badly calibrated produces risk-acceptance decisions systematically wrong in magnitude.
- **Monotonicity test.** A vendor that remediates a finding must **never** lose points. Verify this survives the diminishing-returns transform — a common place to introduce a violation.
- **Stability test.** Re-cohorting must not silently move published scores. Version and diff.

### XI.3 Re-estimate base rates on your own portfolio

Every adoption figure in this report comes from internet-wide domain scans. Your vendor portfolio is a biased sample — skewed toward B2B SaaS and toward companies that survived your procurement filter. Re-estimating on your own data is cheap, more accurate, and far more defensible when a vendor disputes a cohort-adjusted severity.

### XI.4 Governance obligations you take on

Publishing scores about other companies carries duties. The relevant baseline is the U.S. Chamber framework, modelled on the Fair Credit Reporting Act, comprising **transparency; dispute resolution; accuracy and validation; methodology model governance; independence; confidentiality**.

| Principle | What it requires here |
|---|---|
| **Transparency** | Publish the severity table, cohort definitions, decay half-lives, frequency function, credit list, gate conditions |
| **Dispute and appeal** | **Cohort misassignment and attribution error will be your top two categories.** Disputed ratings must be notated as such until resolved |
| **Accuracy and validation** | Publish backtests. **Label expert-set severities as expert judgment until calibrated** — most of yours are, and that is fine if declared |
| **Model governance** | Notice before severity-table or cohort changes. Version everything |
| **Independence** | The mitigation-approval channel is where commercial pressure enters. Artifact requirements and audit trails are the control |
| **Confidentiality** | Do not publish exploitable detail in vendor-facing reports |

### XI.5 The explicit gaming surface

Assume vendors will read the methodology, because under the transparency principle you must publish it.

| | Profitable strategy today | Profitable strategy after revision |
|---|---|---|
| | Reduce scannable surface | Remediate high-severity findings fast |
| | Contest coverage to fall below 40% | Increase scannable transparency to lift the confidence ceiling |
| | Deploy cheap hygiene items with the best points-per-hour regardless of risk | Earn diligence credits |
| | Lobby for mitigation approvals | Provide artifacts |

**That is the correct incentive gradient, and getting it right is arguably worth more than the accuracy improvement.**

### XI.6 Anti-patterns to design against explicitly

1. **Ability-to-pay bias.** Small firms lose on certifications but **win on tempo** (14–18 days vs 56 at midmarket). Ensure a fifteen-person vendor can legitimately score well, or the score is a revenue league table with extra steps.
2. **"Old company = bad."** The evidence supports old *code* accumulating debt, not old *companies* having worse DNS records.
3. **"Big company = bad."** Large firms have more incidents but nearly **2× fewer vulnerabilities per system** than SMBs.
4. **Platform-provisioned credit.** Discount hygiene the vendor did not configure.
5. **Multi-tenant subdomain inflation.** Detect per-tenant naming or every SaaS vendor fails.
6. **Fame-weighted reputation.** Normalize adverse media by total coverage.
7. **Certification as absolution.** Never let ISO/SOC offset a KEV.

---

## Part XII · What the research does not support

Stated plainly, so confidence in everything above can be calibrated.

1. **There is no published, peer-reviewed table of per-signal likelihood ratios by firmographic cohort.** The strongest validation work is vendor-sponsored: Marsh McLennan compared Bitsight data across **365,000 organizations** against a proprietary incident and claims database (2018–2021), finding fourteen analytics correlated with incidents. Meaningful evidence that external signals carry information; **not a published weighting scheme, not independently reproducible, models closed.** Treat every severity value here as an **informed prior to be calibrated on your own outcomes, not as a finding.**

2. **Correlation is not uplift.** A low rating correlates with breach partly because both are caused by low security investment. Adequate for prediction — which is what you are building — but never a claim that adding an HSTS header reduces breach probability by some amount. Figures like *"organizations rated 300–500 are 7.9× more likely to be targeted by ransomware"* are associational.

3. **Published adoption base rates measure domains, not your vendors.** Every base rate in Part III comes from internet-wide scans. **Re-estimate on your own portfolio.**

4. **Breach datasets carry survivorship and disclosure bias throughout.** Cyentia's figures are explicitly limited to incidents that *"make their way into the public record."* Every firmographic effect derived from them is partly an observability effect. **This deserves a permanent caveat in the model documentation.**

5. **The external-signal paradigm has a demonstrated ceiling.** **83% of privilege escalation incidents involved no CVE exploitation at all** — the high-profile cloud third-party campaigns were OAuth-token stories and missing-MFA stories. Only **23% of third-party organizations** fully remediated missing or improperly secured MFA; weak password and permission misconfigurations took a median of **8 months** to resolve half of findings. Meanwhile third-party involvement in breaches is up **60% year over year, now 48% of all breaches** (from 30% and 15% in the two prior years).

   **Practical implication:** cap how much confidence the external score carries for high-criticality vendors and pair it with attestation or contractual evidence. **Identity hygiene — MFA coverage, OAuth scope discipline, credential rotation — is where the third-party losses actually are, and it is nearly invisible to external scanning. If this programme has a strategic gap, that is it, not signal weighting.**

6. **Figures from vendor reports** (EasyDMARC, Bitsight TRACE, PowerDMARC, IBM/Ponemon, dmarcian, Cyentia) restate the source's own published claims from proprietary datasets that cannot be independently reproduced. **Verify each against the current edition before any of this reaches a client deliverable** — several recalibrate annually.

---

## Part XIII · Final answer to the deliverable question

| Component | Should company age / size / revenue / maturity affect it? |
|---|---|
| **Posture** | **No.** Only *measured exposure* enters, as a denominator |
| **Severity** | **No.** Severity is a property of the technical condition *(contested — see [VIII.1](#viii1-may-severity-be-cohort-scaled--the-sources-split-32))* |
| **Penalty multiplier** | **No** for firmographics; **Yes** for evidence-quality and exposure normalization |
| **Confidence** | **Marginally** — disclosure-regime and supervision corrections only |
| **Assurity** | **Yes.** The correct quarantine for audit-budget and program-maturity effects |
| **Benchmarking** | **Yes — the primary and correct home** |
| **Vendor Tier** | **Yes**, driven mainly by the buyer's exposure to the vendor |
| **Risk recommendations** | **Yes.** Remediation advice should absolutely be size- and sector-aware |

---

## Part XIV · Consolidated references

**Loss and frequency base rates**
Cyentia Institute, *Information Risk Insights Study* (IRIS 20/20, 2022, 2025) and *IRIS Ransomware* · Cyentia risk-data methodology

**External-signal predictive validity**
Liu, Sarabi, Zhang, Naghizadeh, Karir, Bailey & Liu, *"Cloudy with a Chance of Breach: Forecasting Cyber Security Incidents,"* USENIX Security 2015 · Marsh McLennan Cyber Risk Analytics Center × Bitsight correlation study (2022), 365,000 organizations · RiskRecon/Cyentia *Internet Risk Surface* series and *Navigating the Internet Risk Surface* · Bitsight published normalization methodology · Bitsight TRACE (1.4M organisations)

**Vulnerability prioritization**
Jacobs, Romanosky, Edwards, Adjerid & Roytman, *"Exploit Prediction Scoring System (EPSS),"* Digital Threats: Research and Practice 2(3), 2021 · EPSS v4 release analysis, Empirical Security / FIRST, March 2025 · CISA Known Exploited Vulnerabilities Catalog · FIRST CVSS specification

**Adoption base rates**
EasyDMARC *DMARC Adoption & Enforcement Report* 2025 and 2026 · Red Sift global DMARC analysis (73.3M domains, Dec 2025) · Valimail sector data · dmarcian US .gov SPF survey, Sept 2025 · PowerDMARC US DNSSEC/MTA-STS analysis 2026 · APNIC/Cloudflare DNSSEC measurement 2025–2026 · Wotschofsky DNSSEC survey (171M domains) · URIports and IoTDef security.txt studies · Hierlmeier & Sperl, *"security.txt Revisited,"* DTRAP 2023 · Qualys SSL Pulse

**Standards and obligations**
RFC 8996 *Deprecating TLS 1.0 and TLS 1.1* (BCP 195, March 2021) · RFC 9116 (security.txt) · PCI DSS v3.2 and v4.0 · NIST SP 800-52 Rev. 2 · ISO/IEC 27001, 29147, 30111 · CA/Browser Forum Ballots SC-081v3 (certificate lifetimes) and SC-085v2 (CA DNSSEC validation) · EU DORA and NIS2 third-party ICT provisions · EU Cyber Resilience Act · CISA BOD 18-01, BOD 20-01, BOD 22-01, Emergency Directive 19-01 · SEC 10-K Item 1C and 8-K Item 1.05

**Threat landscape and incidents**
Verizon *Data Breach Investigations Report* 2025 and 2026 · Veracode *State of Software Security* 2025 and 2026 · IBM/Ponemon *Cost of a Data Breach* 2025 · FBI IC3 2025 · Palo Alto Networks Unit 42, newly-registered and strategically-aged domain research · Intruder *Attack Surface Management Index* 2026 · Equifax (2017), Ericsson/O2 UK (2018), British Airways/Magecart (2018), MOVEit (2023), T-Mobile US (2018–2023), DNSpionage and Sea Turtle (2018–19), Symantec mis-issuance (2015), FREAK/Logjam/POODLE (2014–15)

**Governance and organizational research**
U.S. Chamber of Commerce, *Principles for Fair and Accurate Security Ratings* (2017) · Angst, Block, D'Arcy & Kelley on symbolic vs. substantive IT security adoption, *MIS Quarterly* (2017) · Berg, Kölbel & Rigobon on ESG rating divergence · Liu & Babar, systematic review of corporate cybersecurity risk and data breaches (2026)

---

*Consolidated from five source documents, July 2026. Where the sources disagree, [Part VIII](#part-viii--where-the-sources-disagree) says so rather than choosing silently.*
