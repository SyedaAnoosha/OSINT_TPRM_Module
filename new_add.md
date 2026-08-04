Here is a concise, sectioned summary of the research report and migration plan, tailored to your requested structure.

---

### 1. What Our Current Scoring Model Includes (and its Flaws)
* **Current State:** `scoring.yaml` v4.2.0 uses a penalty-subtractive posture model. It correctly keeps Posture and Confidence separate, does not decay ongoing issues, and requires plain-English reasons for penalties.
* **Critical Flaws:** 
  - **The "Size Penalty" Bug:** It accumulates absolute penalties with *no denominator*, accidentally measuring host count rather than hygiene (e.g., penalizing a large vendor more for 9 expired certs out of 900 than a small vendor with 2 out of 4).
  - **Implicit Weighting:** "No category weights" is a fallacy. Weighting is dictated by the detection inventory, causing a dozen missing hygiene headers to mathematically outrank a single actively exploited vulnerability (KEV).
  - **Score Saturation:** Penalties saturate at the *category* level — roughly 2.5 criticals exhaust a category's 100-point cap. With `penalty_divisor: 4.0`, one saturated category costs 25 posture points, so ~4 saturated categories floor the overall score. Discrimination is destroyed among the highest-risk vendors, exactly where triage matters most.
  - **Invalid Severity Promotions:** The `industry_profiles` file incorrectly promotes technical severity based on industry, contradicting both commercial best practices and our own `benchmarks.yaml`.
  - **Going-Concern Signals Sit Inside Posture:** `business_financial_stability` is a *Posture* category holding continuity signals. Companies House `liquidation`, `receivership`, `administration` and `insolvency-proceedings` all map to `entity_inactive` — **costing 20 points of technical security posture**. `entity_maturity` penalises companies under 10 years old by 3 points, i.e. scores by founding date. `rdap_collector` already tags `domain_registration` with `subcategory="business_continuity"`. A vendor entering administration has a business-continuity problem, not worse TLS.

### 2. The Answer to Our Research Question
> **"Should external security signals be interpreted differently by company type (age, revenue, headcount, market cap)?"**

**No.** The importance of a technical security signal should almost *never* vary with vendor firmographics. It should vary with **measured exposure** (as a denominator), and the consequences of failure should vary with the **buyer’s specific engagement**. 

The intuition that *"a $5B bank with no DMARC is more negligent than a $500K startup"* is a statement about **culpability**, not probability. Mixing culpability into the arithmetic destroys cross-vendor comparability. Firmographics belong exclusively in benchmarking, assurance, and buyer-side impact—*never* as multipliers in the core Posture score.

This is the mainstream TPRM design, not a contrarian position. The standard architecture separates an **Inherent Risk** layer (who the vendor is — type, size, data sensitivity, criticality) from a **Control/Posture** layer (how well they manage risk), then combines them into **Residual Risk** at the end. Our Impact/Tier axis *is* that Inherent Risk layer (§6.4). Any proposal that instead multiplies posture penalties by firmographic bands — *"−10 base, ×1.5 for a large mature vendor, ×0.6 for a young startup"* — has collapsed the two layers back into one and reintroduced the bias the separation exists to prevent. See §7.

The same rule governs **financial markers**. An unpatched KEV is equally dangerous whether the vendor turns over $10M or $10B. Financial health is nonetheless a major driver of *vendor* risk — abrupt service loss, security-team layoffs, inability to fund audits — so it is **routed, never multiplied**. Every proposed financial marker passes a three-question test:

1. Does it change the technical probability of compromise? → **Continuity axis**
2. Does it change how much we trust our external data? → **Confidence multiplier**
3. Does it help compare the vendor to fair peers? → **Expectation Gap (cohorting)**
4. None of the above? → **Discard.** It is firmographic bias seeking a side door.

### 3. Which Signals We Need to Work On
* **Class-P (Prevalence) Signals:** Must be converted to rates with exposure denominators (e.g., `expired certs / total certs`). Includes TLS version, cipher suites, certificate validity, HSTS, CSP, CVEs, KEV, and shadow assets.
* **Low-Base-Rate Signals:** Reclassify from *penalty* to *bonus*. Penalizing the absence of DNSSEC, CAA, or `security.txt` penalizes the norm and adds noise.
* **Governance/Compliance Signals:** Move ISO 27001, SOC reports, and published security programs *entirely out of Posture*. Penalizing their absence is a "tax on audit budget" that disproportionately hurts small vendors.
* **Digital Footprint:** Subdomain count and CT history must be used strictly as denominators or discovery inputs, *never* scored as numerators.
* **Class-C (Continuity) Signals:** `entity_status`, `entity_existence`, `entity_maturity`, `domain_registration`. **Relocate out of Posture entirely.** These are going-concern facts, not security observations. `entity_maturity` and `domain_registration` also belong on the low-base-rate reclassification list — both are company-age proxies, and no major rating provider scores by founding date.

### 4. How We Can Move Forward (The Migration Plan)
We must follow one rule: **Relocate before you re-weight, and re-weight before you re-shape.**
* **Phase 0 (2–3 wks):** Instrument and baseline. Run a "firmographics-only" ablation test to prove the current model's bias. *(Requires building an outcome-label set first — none exists today.)*
* **Phase 1 (2–3 wks):** Structural relocations. Delete `industry_profiles` severity promotions and stop penalising low-base-rate signals. 
* **Phase 2A (1 wk):** `stale_hosts ÷ subdomain_estate` — the one exposure denominator that already exists in the collected data. Free, and it moves the largest penalty line item for every corpus vendor.
* **Phase 2B (6–10 wks):** Collector fan-out. The TLS and headers collectors currently probe a **single host**, so 9 of 10 Class-P signals have no denominator to recover yet. Multi-tenant SaaS detection lands here. *(The highest-impact change.)*
* **Phase 3 (2–3 wks):** Aggregation. Implement λ=0.7 diminishing returns within categories so trivia no longer outranks active exploitation. Ships together with the widened ladder — separately, neither reaches the target ordering.
* **Phases 4–7:** Add hard gates, context outputs, real peer cohorts, and eventually bounded log-odds to fix score saturation.

### 5. What We Need to Include
* **Exposure Denominators:** Mandatory for all count-based signals to remove the existing size bias.
* **Root-Cause Deduplication:** "One remediation ticket, one penalty." (e.g., KEV supersedes EPSS/CVSS; CSP `frame-ancestors` satisfies X-Frame-Options).
* **Platform-Provisioning Discounts:** Do not credit small vendors for HSTS/TLS 1.3 defaults auto-provisioned by Cloudflare or Vercel.
* **Explicit, Versioned Weights & Widened Ladder:** Publish the weights. Widen the severity ladder (Critical: 50, High: 20, Medium: 6, Low: 1.5) to restore correct risk ordering.
* **Hard Gates:** Findings that bypass arithmetic entirely and trigger an automatic block/manual review (e.g., overdue KEV on an internet-facing asset, dissolved legal entity).
* **Continuity Relocation:** Move `business_financial_stability` out of Posture into the Continuity axis. This is a *relocation*, not a new build — the signals and collectors already exist. Cheap, reversible, and it removes a live distortion.
* **Held-Source Discipline for Financial Data:** Only markers with a lawful free source ship. The rest go to `held_roadmap` rather than being asserted.

### 6. What New Scores/Axes We Are Adding
To satisfy the business need for context without corrupting the math, we add dimensions *alongside* Posture. **Only one of them is a new 0–100 score.** The distinction is load-bearing — calling a flag set or a lookup table a "score" implies a measurement that was never made.

| Output | Type | Status |
|---|---|---|
| **Posture** | 0–100 score | Existing, unchanged |
| **Confidence** | 0–1 + band | Existing, unchanged |
| **Assurity** | **0–100 score** | **New** |
| **Expectation Gap** | Signed delta + cohort narrative | New — an output, not a score |
| **Impact / Inherent Risk Tier** | Tier (Low → Critical) | New — buyer-side |
| **Compliance Gap** | Finding class | New — findings, not a number |
| **Continuity** | **Registry-cited flags only** | New — deliberately *not* 0–100 |
| **Residual Risk** | Derived matrix view | New — a decision aid, not a measurement |

1. **Assurity (0–100):** A positive-only score for audit-budget effects (ISO, SOC, VDP). *Absence never subtracts.* A vendor with no certifications has low Assurity, not bad Posture. **Note the dependency:** the engine has no bonus mechanism today, so Assurity must ship *before* the Phase 1 signals can be credited — those signals park at `informational` in the interim.
2. **Expectation Gap (Output):** `EG = Posture − E[Posture | cohort]`. This is the legitimate home for firmographics. It outputs narratives like: *"Posture 68. Median for Enterprise Financial is 87. This vendor sits 19 points below its peer group."*
3. **Compliance Gap (Finding Class):** A distinct, high-signal finding emitted when a vendor asserts compliance (e.g., PCI DSS) but is observed failing a corresponding technical control (e.g., negotiating TLS 1.0).
4. **Impact / Inherent Risk Tier:** A buyer-side dimension based on data held, integration depth, service criticality and substitutability. This is the **Inherent Risk** layer — *who the vendor is and what we have exposed to them* — assessed before looking at a single control. It updates rarely (only when the relationship or the vendor's fundamentals change), whereas Posture refreshes continuously. Keeping the two on different clocks is half the reason for separating them.

   **Residual Risk** is the published combination — and a **derived view, not a dimension**. It is a lookup over two already-published inputs, so it is a procurement decision aid rather than an independent measurement: a vendor disputes its Posture or its Tier, never the cell it lands in. Use a matrix, not a formula, so both inputs stay separately disputable:

   | Posture ↓ / Inherent → | Low | Medium | High | Critical |
   |---|---|---|---|---|
   | **Strong (80–100)** | Low | Low-Med | Medium | Med-High |
   | **Moderate (60–79)** | Low-Med | Medium | High | High |
   | **Weak (40–59)** | Medium | High | High | Critical |
   | **Poor (<40)** | Med-High | High | Critical | Critical |

   Note that a High-Inherent vendor with Strong Posture still lands at Medium — inherent exposure does not disappear because the controls look good. **This is the smallest gap between what we already collect and what we publish:** `criticality` is client-supplied and already reaches `recommend.py`; it simply never becomes a tier.
5. **Continuity (structured flags — deliberately NOT a 0–100 score):** Going-concern status, carrying every financial marker that is not a cohort input. **Registry-cited facts only**, e.g. *"In administration — Companies House company status, retrieved 2026-07-29."*

   **Why flags and not a number.** (a) The research establishes that these signals must *leave* Posture; it does not specify an arithmetic to replace them — a score here would be invention wearing the report's authority. (b) Four registry bands cannot support hundred-point precision. (c) A cited register fact carries the same legal footing as any other published observation, whereas a *derived* distress index is closer to credit-rating territory and defamation-adjacent when wrong. Publish the fact and its retrieval date; do not publish an inference about solvency.
   * **Available now:** entity status and insolvency proceedings (GLEIF, Companies House, ABN — all already collected); corporate parent / M&A state (Wikidata).
   * **Routed to Confidence, not Continuity:** public-vs-private status (Wikidata `listed_on`, **already collected and currently unused**). A public company is bound by SEC Item 1.05 four-day breach disclosure; a private one is not — so "no breach news" is materially weaker evidence for a private firm. Multiplier ≈ 0.6.
   * **Routed to Cohort:** revenue band, employee band (already wired).
   * **HELD — no lawful free source:** funding runway, cash burn, down-rounds, Altman Z-score, market share, layoffs. GLEIF's own collector already records this finding: *"Financial-distress (going concern), litigation, and ownership-CHANGE remain HELD."* Roughly four of ten candidate markers are actually obtainable today.

> **Legal caution on Continuity.** This axis carries different exposure than Posture. A cited registry fact — *"Companies House records administration proceedings, retrieved 2026-07-29"* — sits on the same footing as everything else we publish. A **derived** distress score (inferred runway, a bankruptcy-risk index) is closer to credit-rating territory and is defamation-adjacent when wrong. Ship Continuity as cited registry facts only until advice has been taken on the inferred layer.

### 7. Financial-Marker Anti-Patterns
1. **Ability-to-pay bias.** Do not penalise Posture for absent ISO 27001 or SOC 2. *Currently violated:* `cert_posture.none_claimed` costs 8 points and fires on 5 of 5 corpus vendors. Fixed by Phase 1.
2. **Revenue-weighted severity / context multipliers on penalties.** A missing DMARC record is not worth more at a bank. The concrete form this proposal usually takes — *"−10 base, ×1.3–1.6 for Large+Mature, ×0.5–0.75 for Small+Early"* — is rejected on five independent grounds in `report.md`. It is also self-defeating: the same design note that proposes it lists its own cons as *"harder to explain, easier to create hidden bias, less flexible."* The anomaly it is reaching for is real and is captured by the **Expectation Gap**, never by the arithmetic.
3. **Suspending penalties after M&A.** "Inherited infrastructure" is an *explanation*, not a risk reduction — and it is dynamic severity adjustment (mechanism #10, rejected) wearing a different hat. It is also trivially gameable.
4. **Reweighting absence-of-evidence for regulated firms.** Making absence cost more for a bank is a sector severity promotion entering through the confidence door. Confidence bounds what we *assert*; it never reweights a penalty.
5. **Financial distress as a cyber proxy.** Negative cash flow does not imply bad TLS. Separate vectors, separate axes.
6. **Category weights.** A proposed split — *"Cyber 30–35%, Financial 15–20%, Reputational 10%…"* — reintroduces exactly what §5.6 deleted. A penalty model has no category weights; weighting emerges from the detection inventory, which is why Phase 3 fixes **aggregation** rather than adding percentages. Percentages look principled and are unfalsifiable, which is the problem.
7. **Natural-person signals.** Employee sentiment (Glassdoor, Blind), key-person dependency, leadership controversies and diversity data are barred by §4.2 — `excluded_signals` already names `executive_brand_risk`, `beneficial_ownership_person` and `diversity_inclusion_signals`. They are additionally observability-biased: large employers generate more reviews.

### 8. Signal Coverage — Gaps Worth Building, Lines We Do Not Cross
A full OSINT signal catalogue maps onto our collectors in three buckets. Recording all three matters: the barred list exists so the same proposals are not re-litigated every quarter.

**Already covered.** Breach history (`hibp`) · infrastructure hygiene (`dns`, `tls`, `headers`, `ct`) · CVE and KEV exposure (`nvd`, `kev`) · email authentication (`dns`) · certification claims (`trust`) · regulator actions (`regulatory`) · sanctions (gate) · adverse media (`gdelt`) · attack surface and shadow assets (`ct`) · fourth-party enumeration (`fourth_party.py`) · entity standing and insolvency (`gleif`, `companies_house`, `abn`).

**Real gaps, worth scoping.**
* **Service outage / status-page history** — no collector. The clearest operational-resilience signal we do not read, and it is genuinely public. Best home is the **Continuity** axis, not Posture.
* **End-of-life technology** — we read CVEs but not version currency, which is the earlier and more actionable signal.
* **Public code and secret leakage** — GitHub org scanning for exposed credentials and keys.
* **Litigation** — court records. Already noted as HELD in `gleif_collector`: *"litigation… remain HELD: no free authoritative source."*
* **Credential / dark-web exposure** — already HELD: `data_privacy_leakage: "no lawful free collector (HIBP domain paid)"`. Worth revisiting only with a licence, not a scrape.

**Barred, with the reason recorded.**
* **Employee sentiment, key-person dependency, leadership controversies, diversity data** — natural persons, §4.2. See anti-pattern 7.
* **Customer review corpora (Trustpilot, G2, BBB, Reddit).** A reputation axis built on review volume is a size classifier wearing a halo: large firms generate more reviews, more press and more scrutiny. This is precisely the observability bias the model exists to remove, arriving through a door that sounds like quality rather than size. The legitimate, observable form of *"do they do what they say"* is the **Compliance Gap** (§6.3).
* **Country / geopolitical risk inside Posture** — weakly predictive, ethically fraught, legally exposed. Jurisdiction is surfaced as a disclosed attribute instead. Sanctions remain a gate, which is a different mechanism.
* **ESG** — HELD pending a Modern Slavery data licence (`held_roadmap.esg_ethical`).

**Design principles we already satisfy.** Recency weighting (NIST SP 1326 age decay), severity × frequency (the NIST modifier set), source reliability (per-collector `reliability`), dynamic monitoring (`monitor.py`), and explainability (the loader *refuses to start* if any penalising band lacks a plain-English reason, an action and a recheck date). These are worth stating because they are commonly listed as gaps in generic scoring-model checklists and are, here, already enforced in code.
