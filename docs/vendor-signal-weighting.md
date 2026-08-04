# Should External Security Signals Be Weighted Differently by Vendor Type?

**A research-backed design analysis for third-party cyber risk scoring**

---

## 1. The short answer

**Yes — but almost certainly not in the way your framing implies.**

Your question is phrased as "should a 20-year-old company get a *larger penalty* for TLS 1.0 than a startup?" That framing bundles together three things that a defensible model must keep separate:

| | What it measures | Does it vary by firmographics? |
|---|---|---|
| **Severity** | How technically broken the finding is | **No.** TLS 1.0 is equally broken everywhere. |
| **Diagnosticity** | How much observing this finding updates your belief about the vendor's *unobserved* security competence | **Yes, strongly** — it is a function of the peer-group base rate. |
| **Consequence** | How much loss *you* absorb if this weakness is exploited | **Yes, strongly** — but driven by the relationship, not the vendor's age. |

Treating every signal identically is wrong because it ignores diagnosticity and consequence. But applying a blanket "older/bigger company = bigger penalty" multiplier is *also* wrong, and it is wrong in a way that will quietly destroy your model's predictive power: it turns your scoring system into a company-size detector wearing a security costume.

The correct architecture is:

> **Firmographics enter as priors, denominators, and expectations — never as penalties.**

Concretely, four legitimate modifier channels, and one illegitimate one:

- **D — Diagnosticity (peer base rate).** A missing control is informative in proportion to how *unusual* it is within the vendor's cohort. Missing DMARC among the Fortune 500 (95% adoption, >80% at enforcement) is a 1-in-20 anomaly. Missing DMARC across the general domain population (14.9% have any record) is the overwhelming norm. Same finding, ~35x difference in information content.
- **N — Exposure normalization (denominators).** Count-based signals (subdomains, CVEs, findings, shadow assets) must be divided by footprint or they measure size. This is not optional and it is what every mature commercial rating engine already does.
- **O — Obligation.** Regulatory and contractual duty genuinely differs. PCI DSS banned early TLS in June 2018; DORA imposes prescriptive ICT third-party requirements on EU financial entities; NIS2 covers 18 sectors; BOD 18-01 pushed US federal DMARC enforcement to ~92%. A finding that violates a binding obligation is a different artifact from the same finding at an unregulated vendor.
- **C — Consequence.** What the vendor holds, touches, and connects to *in your environment*. This should dominate everything else, and it is a property of the relationship, not of the vendor's founding date.
- **✗ Moral expectation ("they should know better").** Not a modifier. It is intuition dressed as analysis, it doesn't survive backtesting, and it is the channel through which unfairness and disputes enter.

The rest of this document derives that position from the evidence, applies it signal-by-signal to all 30 signals in your list, and gives you implementable math plus a validation protocol.

---

## 2. Why "treat everything equally" fails

### 2.1 The base-rate / diagnosticity argument

For a binary finding, the amount your belief should move is governed by the likelihood ratio:

```
LR = P(finding observed | vendor is weak) / P(finding observed | vendor is strong)
```

Both terms are population-dependent. If a control is adopted by 95% of a cohort, its absence is a screaming outlier. If it is adopted by 8%, its absence is background noise — you are penalizing nearly everyone, which adds variance and no discrimination.

The published adoption data makes this concrete and is not a close call:

| Signal | Adoption base rate | Implication for "absent" |
|---|---|---|
| DMARC — Fortune 500 | <cite index="40-1">95% adoption, over 80% at enforcement</cite> | Absence = strong negative signal |
| DMARC — Inc. 5000 | <cite index="40-1">more than half remain at monitoring-only</cite> | Absence = weak signal |
| DMARC — all domains | <cite index="42-1">14.9% of 73.3M domains have any record; 2.5% enforce p=reject</cite> | Absence ≈ uninformative |
| DMARC — US federal | <cite index="42-1">92% enforcement due to BOD 18-01</cite> | Absence = severe outlier |
| DNSSEC | <cite index="47-1">secure delegation ~7% in 2025</cite>; <cite index="50-1">5.93% across 171M domains, with enormous registrar variance — GoDaddy 0.29% vs Squarespace 28.12%</cite> | Absence ≈ uninformative |
| security.txt | <cite index="119-1">below 0.25% of all domains, and most adoption is platform auto-provisioning rather than a deliberate security decision</cite> | Absence ≈ uninformative |
| CAA (early measurement) | <cite index="54-1">~1.6% of Alexa top-million</cite> | Absence ≈ uninformative |

If you assign the same penalty to "missing DNSSEC" as to "missing DMARC," you have made a claim that the evidence contradicts: one of those observations distinguishes vendors and the other does not.

A practical, immediately implementable proxy for diagnosticity when you lack labelled incident outcomes is **surprisal**:

```
D_i(cohort) = -log2( P(finding | cohort) )
```

- Missing DMARC in an F500 cohort: P ≈ 0.05 → **4.3 bits**
- Missing DNSSEC globally: P ≈ 0.92 → **0.12 bits**

That is a ~35x ratio derived entirely from public adoption data, with no incident labels required. Surprisal measures anomaly, not harm — so cap it and multiply it by an expert-assigned severity rather than letting it float free.

### 2.2 The exposure-normalization argument

Raw counts are size measurements. The evidence is unambiguous:

- <cite index="83-1">Larger companies have a much broader risk surface but nearly 2x fewer vulnerabilities per system than SMBs</cite>.
- <cite index="133-1">54% of SMEs (1–250 employees) had at least one attack surface exposure in 12 months versus 70% of midmarket (251–5,000); organizations with 1,000–5,000 employees manage 748 assets on average, more than five times as many as organizations with 251–1,000</cite>.
- Bitsight normalizes explicitly: <cite index="165-1">large companies typically have more findings than smaller companies, so ratings are normalized based on organization size, using employee count, magnitude of digital footprint, and overall count of observations to quantify attack surface</cite>, with <cite index="161-1">size factored into the impact calculation on a logarithmic basis, bounded at 100 employees at the low end and 100,000 at the high end, then converted to a percentile ranked against all rated organizations</cite>.
- The concern is explicitly acknowledged in the ratings patent literature: <cite index="137-1">intuition suggests risk scales linearly in network size because each endpoint is a new penetration vector, but such an approach is clearly naïve — a large organization with excellent practices may maintain large numbers of secure endpoints managed uniformly by a single central administrator, in which case additional endpoints do not imply increased breach risk</cite>.

So: **subdomain count, CVE count, and finding count are not risk signals in raw form.** Density, severity-weighted density, and dwell time are.

### 2.3 The base-rate-of-outcome argument

Vendor characteristics genuinely shift the prior probability and magnitude of loss:

- <cite index="2-1">Healthcare and Finance have the most incidents, with 76x more events than the least-breached industries of Mining and Agriculture; organizations above $100B in annual revenue are 32x more likely to have multiple security incidents in a single year than smaller firms</cite>.
- <cite index="5-1">Over 60% of the Fortune 1000 had at least one public breach over the last decade, and roughly one in four Fortune 1000 firms will suffer a cyber loss event annually</cite>.
- Loss magnitude scales the opposite way in relative terms: <cite index="1-1">a $100B enterprise experiencing a typical cyber event faces a cost representing 0.000003% of annual revenue, while a shop bringing in $100K per year will likely lose a quarter of its earnings or more</cite>.
- Ransomware breaks the pattern: <cite index="4-1">companies from $100M to $100B are pretty much all equally likely to be hit, with the smallest and largest exhibiting surprisingly similar elevated probabilities, attributed to ransomware gangs tailoring demands to the victim's pocketbook</cite> — a useful reminder that firmographic effects are threat-specific, not global.

### 2.4 The detection-and-disclosure-bias argument (the one most models get wrong)

Several of your signals — public breach history, regulatory enforcement, government investigations, adverse media, regulatory disclosures — are not observed directly. They are observed through a filter whose transmissivity is itself a function of firmographics.

A public company in a mandatory-notification jurisdiction is enormously more likely to have any given incident become visible than a 10-person private vendor in a jurisdiction with weak disclosure law. Consequently:

> **"No public breach history" is strong positive evidence for a Fortune 500 and near-zero evidence for a private SMB.**

If you score absence-of-evidence symmetrically, you systematically reward opacity — you give your best scores to the vendors you can see least. Correct for this explicitly by weighting absence-signals by `P(we would have observed it | it happened)`, estimated from listing status, jurisdiction, sector disclosure regime, and size.

### 2.5 But: firmographics must be bounded

The counterweight, from the same research base:

- <cite index="89-1">Single demographic factors such as industry, size, and region aren't enough to assess the risk posed by third parties; choosing a partner with a poor security posture can mean your organization is 360 times more likely to be exposed to security findings</cite>.

Observed posture dominates demographics by a wide margin. Firmographics should therefore be **bounded modifiers on observed findings**, never independent score drivers. My recommendation: cap the combined firmographic effect so it can move any individual signal's weight by no more than ~2.5x, and cap total firmographic influence on the composite posture score at ~20–25%.

---

## 3. The correct treatment of company age (your headline question)

Company age is the weakest and most confounded of the modifiers you listed, and it is the one most likely to get your model into trouble. Here is what the evidence actually supports.

### 3.1 The intuition is half right — for code, not for configuration

Veracode's longitudinal data supports "older accumulates debt" *for application code*: <cite index="90-1">security debt is not uniformly distributed and tends to concentrate in applications that are older and have grown larger over time</cite>, and the trend is worsening — <cite index="96-1">security debt now affects 82% of organizations (up 11% year-over-year), critical security debt affects 60% (a 20% relative increase), and high-risk vulnerabilities are up 36% year-over-year</cite>.

But that finding is about *application age and codebase size*, which you can often measure directly. It does not license a general "old company = worse" multiplier applied to DNS records and TLS configuration.

### 3.2 The right axis is remediation cost and latency, not age

Sort your signals by **how much time and organizational capital remediation actually requires.** That, not age, determines whether leniency is defensible.

**Tier 1 — Zero-cost, minutes-to-hours (no age leniency, ever):**
TLS version, cipher suite selection, HSTS header, X-Frame-Options, SPF record, CAA record, certificate renewal, security.txt

**Tier 2 — Real engineering or process cost, weeks-to-quarters (modest leniency for genuinely young/small vendors):**
DMARC at enforcement with a complex sender ecosystem, CSP retrofit on a legacy app, DNSSEC operations, shadow-asset cleanup

**Tier 3 — Organizational maturity, quarters-to-years (legitimate leniency; age is a real input):**
ISO 27001, SOC 2 Type II, published security program, formal VDP, governance documentation

### 3.3 Applying this to your TLS 1.0 example — the answer inverts your intuition

TLS 1.0 is Tier 1. <cite index="102-1">RFC 8996 formally deprecated TLS 1.0 and 1.1 in March 2021, moving both to Historic status, noting that TLS 1.2 became the recommended version in 2008 — providing sufficient time to transition</cite>. <cite index="101-1">PCI DSS required disabling early TLS by 30 June 2018</cite>, and <cite index="98-1">TLS 1.0 and 1.1 are blocked by all major browsers, and banned outright by PCI DSS, NIST SP 800-52 Rev. 2, and HIPAA guidelines</cite>.

Now decompose:

| Channel | 20-year-old firm | 1-year-old startup |
|---|---|---|
| **Severity** | Identical | Identical |
| **Diagnosticity** | High — but there is a *plausible mechanism* (legacy client compatibility, appliance debt) | **Higher.** Every modern stack ships TLS 1.2/1.3 by default. A 2025-founded company running TLS 1.0 had to actively regress or deploy something ancient. There is no legacy story. The finding is *more anomalous*, therefore *more informative*. |
| **Obligation** | Higher if regulated (PCI, HIPAA, DORA/NIS2 scope) | Lower unless payment-adjacent |
| **Consequence** | Typically higher — more data, more users, more regulatory exposure | Typically lower |

**Net:** the 20-year-old bank usually scores worse — but through the **obligation and consequence** channels, not through an age penalty. And on the pure "does this tell me the vendor is careless?" question, the startup's TLS 1.0 is arguably the *louder* signal.

This distinction is not academic. If you implement it as an age penalty, a startup with TLS 1.0 gets a discount it does not deserve, and your model will underperform on exactly the segment where SMB risk is concentrated — <cite index="76-1">96% of ransomware victims where organizational size was known were SMBs, and third parties were involved in 55% of SMB breaches</cite>.

### 3.4 What to use instead of company age

**Measure defect dwell time directly.** You can usually reconstruct it from Certificate Transparency logs, passive DNS, and your own scan history. "This TLS 1.0 endpoint has been in this state for 41 months" is:

- more accurate than an age proxy,
- directly interpretable as remediation tempo,
- defensible under a vendor dispute,
- and correlated with the thing that actually predicts incidents — <cite index="18-1">Marsh McLennan found that an organization's patching cadence, as measured by BitSight, was correlated to the likelihood of experiencing a cybersecurity incident</cite>.

**Design principle: prefer measured behavioural tempo over firmographic proxies wherever both are available.** Age is what you use when you cannot measure dwell time; it should never override it.

### 3.5 Where company age *is* legitimately used

1. **Cohort assignment** for peer-relative base rates.
2. **Denominator for history-length-dependent signals.** CT history depth, breach-record length, and adverse-media history all scale with observation window. A 1-year-old company has a short clean record because it is young, not because it is safe. Rate-normalize or these become age detectors.
3. **Expectation modifier for Tier 3 controls only.**

---

## 4. Signal-by-signal analysis

Notation for each signal:

- **Equal?** — Should this be weighted identically for every vendor?
- **Modifiers** — Which characteristics legitimately change the interpretation
- **Direction** — `PENALTY` (absence/presence costs points), `BONUS` (presence-only credit, never penalize absence), `GATE` (pass/fail, not scored), `NORMALIZER` (an input to other signals, not scored itself)

### 4.1 Cyber Hygiene

---

#### SPF
**Equal?** Near-equal. **Direction:** PENALTY (low-moderate) **Modifiers:** Email-sending behaviour, B2C exposure — *not* age or size.

Adoption is now high and rising fast (<cite index="45-1">SPF had the biggest single-year improvement of any protocol, a 5.97 point jump in twelve months, driven by Google and Yahoo bulk sender enforcement</cite>), and the fix is a single DNS record. High base rate + zero remediation cost = absence is diagnostic across every cohort. No age leniency.

**Design note:** score *correctness*, not presence. <cite index="42-1">A 2025 survey of 713 US .gov domains found 60% had SPF errors — missing records, invalid syntax, or the 10-DNS-lookup problem — silently breaking DMARC</cite>. A `+all` record or a lookup-limit overflow is worse than a thoughtful absence.

---

#### DKIM
**Equal?** Yes in principle, but **observability is the binding constraint.** **Direction:** PENALTY (low), with a strong "unknown" state.

You cannot reliably enumerate selectors externally. Treat unobserved DKIM as *unknown*, not *failing*. Downweight accordingly and do not let it contribute to a cohort comparison it cannot support. Modifier: if you observe mail from the vendor (bounce headers, DMARC aggregate reports you receive), you can score it properly; otherwise abstain.

---

#### DMARC
**Equal?** **No — this is the clearest case in your entire list for cohort normalization.** **Direction:** PENALTY, ordinal (none < quarantine < reject), cohort-scaled.
**Modifiers:** employee count, revenue, industry, B2C/brand exposure, regulatory obligation, public/private, geography.

The base rates above give you a ~4x to ~35x spread in diagnostic content depending on cohort. Beyond diagnosticity, consequence differs sharply: impersonating a bank monetizes directly, impersonating a 10-person B2B tool usually does not. <cite index="43-1">In 2024, 48% of healthcare organizations and 73% of financial institutions reported phishing attacks</cite>.

**Direct answer to your question 2:** Missing DMARC should cost the Fortune 500 financial institution substantially more than the 10-person startup — but for *two independently modelled reasons* (anomaly within cohort + impersonation consequence), not one fudge factor. And it should still be recorded for the startup as a low-weight hygiene item, because the fix costs nothing.

**Design note:** score the policy level and alignment, not record presence. <cite index="41-1">More than half a million domains with DMARC records remain at p=none, the monitoring-only policy that offers zero protection against spoofing</cite>, and <cite index="39-1">more than 70% of DMARC-enabled domains lack reporting (RUA) tags</cite>. A `p=none` record is close to a null result; treating it as compliance is the single most common scoring error in this signal.

---

#### DNSSEC
**Equal?** No. **Direction:** **BONUS — do not penalize absence for general commercial vendors.**
**Modifiers:** industry (DNS/hosting/registry/CDN operators, government), geography, critical-infrastructure status.

At <cite index="47-1">~7% secure delegation</cite> globally, penalizing absence penalizes ~93% of the population — pure noise. Adoption is also strongly regional: <cite index="48-1">.cz (59%), .se (55%), .nl (51%), and .sk (48%) lead among EU ccTLDs, where registry operators provide price incentives and technical support</cite>. A German or Swedish vendor without DNSSEC sits in a cohort where adoption is normal; a US vendor without it sits in a cohort where it is exotic. Geography is a legitimate modifier here in a way it rarely is elsewhere.

Two forward-looking caveats worth building for: <cite index="52-1">end-to-end DNSSEC validation grew 45% year-over-year from Q1 2025 to Q1 2026, with signing moving from 7.28% to 8.11%</cite>, and <cite index="177-1">CA/Browser Forum ballot SC-085v2, effective March 15 2026, requires certificate authorities to validate DNSSEC when issuing certificates</cite>. Expect the base rate to move; re-estimate annually.

---

#### CAA
**Equal?** No. **Direction:** BONUS. **Modifiers:** cohort maturity, certificate issuance volume.

Same structural logic as DNSSEC: low cost but low awareness means presence is a strong positive indicator of deliberate hygiene, while absence carries almost no information. Score asymmetrically. Slightly higher weight for vendors with large CT footprints (many certs, many CAs) where CAA meaningfully constrains mis-issuance.

---

#### TLS version
**Equal?** Severity yes; total weight no. **Direction:** PENALTY (high). **Modifiers:** obligation (PCI/HIPAA/NIST scope), endpoint criticality, consequence. **Not age.**

See §3.3 for the full argument. Two additional design points:

1. **Endpoint criticality must dominate firmographics.** TLS 1.0 on `blog.vendor.com` and TLS 1.0 on `api.vendor.com` handling your customer data are different findings. Weight by what the endpoint does, which you can often infer (auth forms, API paths, cert SANs, CT-derived naming).
2. Grade the full ladder: TLS 1.3 preferred / 1.2 minimum / 1.1 or 1.0 offered / SSLv3 or below. <cite index="98-1">75.3% of the top 150,000 websites supported TLS 1.3 as of June 2025</cite>, so the "no TLS 1.3" cohort is now a minority and modestly diagnostic in its own right.

---

#### Cipher suites
**Equal?** Severity yes, graded. **Direction:** PENALTY (graded). **Modifiers:** endpoint criticality, regulatory profile, legacy-integration industry (as a routing signal, not a discount).

Tier the findings rather than scoring "weak ciphers" as one item: NULL/EXPORT/anon-DH/RC4/3DES are severe and invariant; missing forward secrecy or missing AEAD is moderate; suboptimal preference ordering is cosmetic. RFC 8996 notes the structural problem directly — <cite index="104-1">TLS 1.0 and 1.1 require older cipher suites no longer desirable for cryptographic reasons, lack AEAD support, and depend on SHA-1 for handshake integrity and peer authentication</cite>, so cipher findings and version findings are correlated. **Do not double-count them** (see §6.4).

For healthcare-device or banking-terminal vendors, a legacy cipher requirement may have a real explanation. That should route the finding to manual review with an exception workflow — not silently discount it.

---

#### Certificate validity
**Equal?** Near-equal, but **must be density-normalized.** **Direction:** PENALTY (moderate-high). **Modifiers:** certificate portfolio size (denominator), endpoint criticality.

An expired or hostname-mismatched cert on a production endpoint is one of the highest-value *diagnostic* signals available externally: it indicates absent automation and absent monitoring, which generalizes. But 2 expired certs out of 4,000 is a rounding error; 2 out of 3 is a program failure. Always score `expired / total observed`.

This signal's weight should **rise** over the next three years. <cite index="172-1">CA/Browser Forum Ballot SC-081v3, approved April 2025, sets maximum certificate lifespan at 200 days from March 15 2026, 100 days from March 15 2027, and 47 days from March 15 2029, with domain validation reuse dropping to 10 days</cite>. <cite index="174-1">200-day certificates are manageable with disciplined manual processes; 100-day certificates will strain most manual workflows; by 2029 manual management becomes a recipe for outages</cite>. As lifetimes compress, an expired cert stops meaning "someone forgot" and starts meaning "this vendor has no certificate lifecycle automation" — a much stronger inference. Plan to increase this weight on the 2027 and 2029 boundaries.

---

#### HSTS
**Equal?** Near-equal. **Direction:** PENALTY (low). **Modifiers:** whether the vendor serves authenticated web sessions to your users or customers.

Mostly diagnostic rather than causal (HTTPS redirection is usually present regardless). Cheap to deploy, so no age leniency. Score `max-age`, `includeSubDomains`, and preload status as an ordinal; preload is a reasonable BONUS.

---

#### CSP
**Equal?** **No — and this is the one signal where genuine maturity leniency runs in the direction you expected, reversed.** **Direction:** PENALTY (low by default, high for payment-adjacent). **Modifiers:** application age/complexity, payment adjacency, whether the vendor's scripts execute in your users' browsers.

Retrofitting a strict CSP onto a large legacy application is genuinely expensive; deploying one on a greenfield SPA is nearly free. So a 20-year-old firm with no CSP has a real engineering explanation, and a young cloud-native vendor without one has less of one. This is Tier 2 work, unlike TLS.

Two caveats that matter more than the age adjustment:

1. **Score quality, not presence.** A policy with `unsafe-inline`, `unsafe-eval`, or wildcard sources provides close to no protection. Presence-scoring rewards theatre.
2. **Payment adjacency changes the weight class entirely.** PCI DSS v4.0 requirements 6.4.3 and 11.6.1 impose script management and change-detection obligations on payment pages. For a payments vendor, weak CSP is an obligation finding, not a hygiene nicety.

---

#### X-Frame-Options
**Equal?** Yes. **Direction:** PENALTY (very low). **Modifiers:** only whether the vendor serves authenticated UI.

Largely superseded by CSP `frame-ancestors`. Keep it, weight it near the floor, and make sure your scoring accepts `frame-ancestors` as satisfying the control — otherwise you penalize vendors for being *more* modern.

---

#### security.txt
**Equal?** No. **Direction:** **BONUS only. Never penalize absence.** **Modifiers:** footprint size, whether the file is self-provisioned or platform-provisioned.

Two findings make this signal near-useless as a penalty and modest as a bonus:

- <cite index="119-1">Adoption remains below 0.25% of all domains, and the majority appears driven by platform automation rather than deliberate security decisions; when a file exists there is a 60% chance it points to a platform's generic security contact rather than someone who can remediate</cite>.
- <cite index="117-1">Only 44% of domains with a security.txt file meet RFC standards</cite>.

**This raises a general design warning worth applying across your whole framework:**

> **Attribute each signal to the party that actually controls it.**

Cloud, PaaS, and website-builder defaults hand small vendors free credit for HSTS, TLS 1.3, security.txt, and modern ciphers that reflect Vercel's or Cloudflare's competence, not the vendor's. This systematically inflates small-vendor hygiene scores and *deflates the diagnostic value of the entire hygiene category for cloud-native cohorts*. Detect platform provisioning (header fingerprints, ASN, default file contents) and discount accordingly, or your hygiene score will mostly measure hosting choice.

### 4.2 Digital Footprint

---

#### Number of subdomains
**Equal?** **No — and in raw form this is not a risk signal at all.** **Direction:** NORMALIZER + PENALTY on derived density. **Modifiers:** employee count, revenue, architecture, M&A history.

Raw subdomain count is a size proxy (§2.2). Derive instead:
- severity-weighted findings per host
- high-severity findings per *high-value* host
- ratio of unmanaged/orphaned to managed names
- growth rate and volatility of the footprint

**Critical architectural exception:** multi-tenant SaaS vendors legitimately provision per-customer subdomains and will show tens of thousands of names. That is architecture, not sprawl. Detect the pattern (naming regularity, shared wildcard certs, uniform infrastructure) and exclude it, or every SaaS vendor in your portfolio scores in the basement.

---

#### Certificate Transparency history
**Equal?** No — **must be observation-window normalized.** **Direction:** mixed. **Modifiers:** company age and domain age (as denominators), CA relationships.

CT depth is mechanically a function of how long the entity has existed and when CT enforcement began. A 1-year-old company has a short, clean CT history *because it is young*. Never treat that as evidence of discipline.

Useful derivations, all rate-based:
- issuance velocity and its variance
- CA diversity and churn (frequent unexplained CA switching is a process signal)
- wildcard reliance (broad blast radius on key compromise)
- certificate lifetime discipline relative to the SC-081v3 schedule
- **appearance of internal/dev/staging hostnames in public logs** — a genuine information-disclosure finding and a strong process signal
- names still in CT that no longer resolve or resolve to third-party infrastructure (dangling-record precursor)

---

#### Shadow assets
**Equal?** No — normalize, and weight by severity and dwell time. **Direction:** PENALTY (high on severity-weighted density). **Modifiers:** employee count, M&A activity, cloud footprint, organizational decentralization.

This is the highest-value footprint signal, and the data supports expecting *some* shadow assets from any organization above trivial size: <cite index="133-1">exposed databases take the top two spots, with more than a quarter of organizations exposing MySQL; among SMEs 26% exposed risky ports and services and 20% exposed HTTP panels, rising to 45% and 39% for midmarket</cite>.

The discriminating metrics are severity-weighted density and **mean time to removal** — and the tempo data is counterintuitive in a way that should shape your weighting: <cite index="133-1">small organizations remove exposures fastest, taking 14–18 days on average, with remediation slowing as companies grow into the midmarket and peaking at 56 days for organizations with 5,000+ employees</cite>, before improving again at large enterprise scale.

That non-monotonic curve is exactly why a linear "bigger = penalize more" or "smaller = penalize more" rule fails. Use the measured tempo.

**M&A activity is a legitimate, measurable, and rarely-used modifier here.** Acquisitive companies inherit unmanaged infrastructure. If you can detect acquisitions (press, CT, ASN changes), you can predict and contextualize footprint sprawl instead of just punishing it.

### 4.3 Breach & Compromise

---

#### Public breach history
**Equal?** **Emphatically no**, for two independent reasons. **Direction:** PENALTY with decay and observability weighting. **Modifiers:** public/private, revenue, size, sector disclosure regime, jurisdiction, elapsed time, evidence of remediation.

**Reason 1 — observability asymmetry (§2.4).** Absence of public breach history means fundamentally different things across cohorts. Weight the *absence* by observability; never treat a clean record as positive evidence for a low-observability vendor.

**Reason 2 — recidivism is real but decays.** Among public companies, <cite index="64-1">of 1,014 data breaches disclosed before the end of 2021, 334 (about 33%) were repeat breaches</cite>, and <cite index="64-1">second-time breaches hurt firm value more than the first, with the damage most severe for financial-data breaches</cite>.

**Direct answer to your question 3:** Yes — an old breach followed by demonstrated program maturation should carry materially less weight than a recent cluster at a young firm. But three conditions:

1. **The discount must be earned by evidence, not granted by the calendar.** The literature is explicit that form ≠ substance: <cite index="65-1">merely increasing IT security usage does not necessarily reduce breaches, as effective integration of IT security into processes is essential, whereas symbolic adoption diminishes IT security effectiveness and increases breach risks</cite>. Accept post-incident leadership change, published remediation with specifics, a subsequent clean external posture trend, or an attestation obtained *after* the incident. Do not accept a press release.
2. **Apply exponential decay** — a 24-month half-life is a defensible starting prior, to be recalibrated against your own portfolio outcomes.
3. **Weight patterns superlinearly.** Two incidents in three years should cost considerably more than 2× one incident, because a cluster evidences systemic rather than episodic failure. Commercial precedent exists: Bitsight applies a <cite index="162-1">security incident adjustment</cite> on top of the vector-derived rating.

---

#### Exposed data types
**Equal?** No — but this is a **consequence** signal, not a posture signal. **Direction:** feeds loss magnitude, not the hygiene score. **Modifiers:** whether the vendor holds the same data classes *for you*, B2C consumer-PII volume, sector regulatory multipliers, jurisdiction.

Keep this out of your posture score entirely. A vendor that once leaked email addresses and a vendor that once leaked health records have similar posture implications and wildly different loss implications. Conflating them corrupts both numbers.

---

#### Known Exploited Vulnerabilities (KEV)
**Equal?** **Yes — this is the one signal that should be near-invariant across all firmographics.** **Direction:** PENALTY (highest weight in the framework) and a candidate GATE. **Modifiers:** dwell time since KEV listing, endpoint exposure/criticality, attribution confidence. **Not age, size, sector, or revenue.**

KEV denotes confirmed in-the-wild exploitation. There is no firmographic story that makes an actively-exploited internet-facing vulnerability acceptable. Do not discount it for anyone.

The urgency case has strengthened materially: <cite index="79-1">vulnerability exploitation is now the top breach entry point at 31% of breaches, the first time in 19 years it has surpassed stolen credentials</cite>, and <cite index="74-1">AI is compressing exploitation timelines, with the rapid weaponization of known vulnerabilities creating a capacity crisis for security teams</cite>.

**The single most useful thing you can do with KEV is measure dwell time.** Days-since-KEV-listing on an unremediated internet-facing asset is a direct, defensible, firmographic-free measure of remediation tempo — and it is a far better maturity proxy than company age, size, or revenue. Where you have it, it should *override* firmographic priors, not be blended with them.

Recommended treatment: KEV on an internet-facing authenticated or data-bearing asset, unremediated beyond the CISA due date, should be a **gate** (blocks onboarding pending remediation) rather than a score component that can be averaged away by good hygiene elsewhere.

---

#### CVEs (raw counts)
**Equal?** No — near-useless raw. **Direction:** PENALTY (low), heavily normalized. **Modifiers:** footprint size (denominator), technology stack, cloud vs on-prem, attribution confidence.

Two problems compound:
1. **Count is footprint.** Must be density-normalized like every other count.
2. **External CVE attribution is unreliable.** Banner-based version inference cannot see vendor backports, produces high false-positive rates, and misattributes shared and CDN infrastructure. Attribution error is the dominant source of vendor disputes with external ratings — which you are obliged to handle (§7).

Also: a WordPress-based vendor will always show more CVEs than a Go-monolith vendor at identical competence. That is a stack effect. Either control for it or accept that you are partly scoring technology choice.

---

#### CVSS
**Equal?** Yes, but **weight it low and use it only for impact characterization.** **Direction:** modifier on other signals, not a standalone score.

The evidence against CVSS-driven prioritization is decisive: <cite index="28-1">CVSS 7+ prioritization requires patching 50% of known CVEs to achieve 74.6% exploit coverage, with only 6% efficiency, whereas EPSS v4 achieves similar coverage by patching just 6% of vulnerabilities, increasing efficiency to 47%</cite>. <cite index="29-1">Effort is reduced by more than 8 times over — from 50.7% down to 6% effort — for roughly the same security outcome</cite>.

Use CVSS base metrics for what they are good at (characterizing scope and confidentiality/integrity/availability impact *once exploitability is established*), and never as the primary ordering.

---

#### EPSS
**Equal?** **Yes — fully invariant.** It is a property of the vulnerability, not of the organization. **Direction:** continuous modifier on vulnerability findings.

Use EPSS in place of CVSS as the exploitability prior. Three implementation notes:

1. Be consistent about probability vs percentile. <cite index="30-1">EPSS estimates the probability that a vulnerability will be attempted to be exploited within the next 30 days, and also provides percentile rankings — a score of 0.15 at the 89th percentile means 89% of all scored CVEs sit at or below it</cite>. Mixing the two silently across your model is a common and hard-to-debug error.
2. **KEV supersedes EPSS.** EPSS is a pre-threat-intelligence estimate; when confirmed exploitation exists, that observation dominates the prediction.
3. Weight the KEV ∩ high-EPSS intersection highest, and re-pull EPSS daily — it is a moving score, unlike CVSS.

<cite index="29-1">EPSS v4, released March 2025, ingests exploitation activity including malware activity and endpoint detections, collecting activity for 12K vulnerabilities a month</cite>.

### 4.4 Governance

All three governance signals share a structure: **near-zero causal weight, moderate diagnostic weight, and heavy confounding by sales motion and business model.** All three should be BONUS-weighted, with penalties applied only where absence is anomalous within a well-defined cohort.

---

#### Published security program / trust page
**Equal?** No. **Direction:** BONUS; small penalty only for enterprise-selling B2B SaaS above ~50 employees. **Modifiers:** B2B vs B2C, industry, size, whether the vendor sells to regulated buyers.

Enterprise-selling B2B SaaS publishes trust pages because procurement demands them. A B2C app, a logistics firm, or a specialist manufacturer may run an excellent program with no public page. Penalizing absence here largely measures *go-to-market motion*.

---

#### Vulnerability disclosure policy
**Equal?** No — **weight should scale with internet-facing footprint, not with age or revenue.** **Direction:** BONUS, with a real penalty for large-footprint vendors. **Modifiers:** internet-facing footprint size, industry (software/infrastructure), critical-infrastructure status, government contracting.

This is the one governance signal with a genuine causal mechanism: a vendor with a large public attack surface and no reporting channel *cannot be told* about externally discovered flaws, which measurably lengthens time-to-fix. So weight it by footprint. A 5-person vendor with three hosts and no VDP is unremarkable; a vendor with 4,000 internet-facing hosts and no way to report a bug has an operational gap. CISA BOD 20-01 mandates VDPs for US federal civilian agencies, establishing a cohort where absence is a hard outlier.

---

#### Security contact
**Equal?** No. **Direction:** BONUS (lowest weight of the three).

Subject to the same platform-provisioning caveat as security.txt. A contact address that resolves to a hosting provider's generic inbox is not evidence about the vendor.

### 4.5 Business

---

#### Domain age
**Equal?** **Do not use it as a security-competence signal at all.** **Direction:** GATE (fraud screening) + NORMALIZER. **Modifiers:** n/a.

Domain age has real evidentiary value, but in a different domain than yours: fraud, impersonation, and shell-entity screening. <cite index="156-1">More than 70% of newly registered domains are malicious, suspicious, or not safe for work — almost ten times the ratio observed in the top 10,000 domains</cite>.

But "old domain = safe" is equally false, and this is the part most frameworks miss: <cite index="158-1">strategically aged domains show a malicious rate more than three times higher than newly registered domains, with 22.27% malicious, suspicious, or not safe for work</cite> — actors register domains years in advance specifically to evade reputation-based detection.

Correct uses:
1. **Consistency gate** — does domain age match claimed company age and corporate registry records? A mismatch is a verification trigger.
2. **Fraud screen** — recent registration + redacted WHOIS + no corporate records + payment instructions = a different workflow entirely.
3. **Denominator** for history-length-dependent signals (§3.5).

---

#### Domain registration quality
**Equal?** Severity yes; expectation no. **Direction:** PENALTY (moderate), cohort-scaled expectation. **Modifiers:** consequence (do you federate identity with this vendor?), brand value, footprint, cohort norms.

This is an underrated, genuinely causal signal. Domain hijack is a catastrophic single point of failure: it yields email interception, certificate issuance, and often SSO/OAuth takeover simultaneously. Score: registrar lock, transfer lock, **registry lock**, expiry runway, WHOIS/RDAP consistency, corporate vs consumer registrar, DNS provider redundancy, auto-renew status.

Cohort-scale the *expectation*: registry lock is a large-enterprise practice with real cost and friction. Expecting it from a 5-person vendor is unrealistic; expecting it from a bank is entirely reasonable. Expiry runway and auto-renew, by contrast, are free and should be expected of everyone.

Weight by consequence: if you SSO into this vendor or they send transactional mail to your customers, domain control is your risk, not just theirs.

---

#### Legal entity status
**Equal?** Yes. **Direction:** GATE, not a score. **Modifiers:** geography (observability only).

Active / good standing / dissolved / struck off is binary and should gate onboarding, not contribute points. The one firmographic adjustment needed is **observability**: registry data quality varies enormously by jurisdiction, and some registries are opaque or paywalled. Route unverifiable to manual review; never penalize a vendor for its jurisdiction's registry practices.

---

#### Company age
**Equal?** **Should not be a direct scoring input.** **Direction:** NORMALIZER + cohort assignment + Tier-3 expectation modifier only.

Full treatment in §3. Summary: use it for cohort assignment, as a denominator for history-window signals, and as an expectation modifier for high-latency governance and compliance controls. Never let it modify the severity of a configuration finding. Where dwell time is measurable, dwell time wins.

---

#### Company continuity
**Equal?** No — **and this deserves its own sub-score, separate from confidentiality risk.** **Direction:** PENALTY on a distinct continuity/availability dimension. **Modifiers:** revenue, funding stage, public/private, your dependence concentration, switching cost.

Going-concern signals — layoffs, funding gaps, auditor going-concern qualifications, distressed M&A, mass security-team departures, product sunset notices, unpaid-invoice signals — predict two distinct failures: (a) abrupt service loss, and (b) control decay as the security function is cut first.

Asymmetrically important for small and private vendors (thin reserves) and for vendors you cannot exit quickly. This is real third-party risk that pure security scanning entirely misses, and it is one of the few places where revenue and funding stage are *directly* relevant rather than proxies.

### 4.6 Compliance

---

#### ISO 27001 certification
**Equal?** No — **strong, legitimate size/age leniency here** (Tier 3, real cost). **Direction:** BONUS, with penalty only where absence is cohort-anomalous. **Modifiers:** employee count, revenue, industry, B2B/B2C, buyer regulatory profile, geography.

Cost is a genuine input: <cite index="126-1">depending on scope, ISO 27001 can initially cost 50–60% more than SOC, although pricing varies widely across industries</cite>. A 5-person vendor without ISO 27001 is normal. A 500-person enterprise-selling SaaS vendor without either ISO 27001 or SOC 2 is an outlier worth a real penalty.

**Score scope, not presence.** The Statement of Applicability can legitimately be scoped to a single product line or office. A certificate that excludes the system you are actually buying is worth nothing. Parse the scope statement, or at minimum flag unparsed scope as an unknown rather than a pass.

Geography is a legitimate modifier: ISO 27001 is the expected credential in EU and APAC markets; SOC 2 in the US. Penalizing a European vendor for lacking SOC 2 measures nationality.

---

#### SOC reports
**Equal?** No — same structure as ISO. **Direction:** BONUS. **Modifiers:** as above.

**Score type and period, not presence.** A SOC 2 Type II covering 12 months with no qualified opinions is substantially stronger evidence than a Type I point-in-time snapshot; treating them as equivalent is a common scoring error. Also check currency — expired reports are extremely common in vendor portals — and check for qualified opinions and carve-outs, which are where the real information is.

**Ceiling caveat for both certifications:** the empirical literature is clear that certification is not immunity, and that symbolic adoption can be actively counterproductive (see the Angst et al. finding cited under breach history). Cap the maximum credit any certification can contribute, and never let a certification offset a KEV or an active exposure. Certification evidence and observed-posture evidence answer different questions.

---

#### Regulatory disclosures
**Equal?** **Structurally unequal by observability.** **Direction:** BONUS channel only — never a penalty for absence. **Modifiers:** public/private, jurisdiction, sector.

SEC 10-K Item 1C risk-management disclosures and 8-K Item 1.05 material-incident filings are rich evidence — for the tiny fraction of vendors subject to them. Private SMBs *cannot* produce this signal. If absence costs points, you have built a public-company preference, not a risk model.

Use it as an additive information source where it exists: quality and specificity of the Item 1C description, board-level oversight structure, and whether disclosed incidents match what you found independently (a disclosure/observation mismatch is itself a strong signal).

### 4.7 Reputation

This whole category is the noisiest and most size-biased in your framework. Weight it conservatively, require corroboration, and be strict about relevance filtering.

---

#### Regulatory enforcement
**Equal?** No. **Direction:** PENALTY (high where present, decayed). **Modifiers:** industry regulation intensity, geography, public/private, size, recency, subject-matter relevance.

Enforcement actions (FTC consent orders, ICO/DPA fines, OCC/FCA actions, HHS OCR settlements) are the highest-quality reputation signal available: they represent *adjudicated* findings of substantiated failure, not allegations. Weight them well above adverse media.

But apply the observability correction hard: regulated sectors and large firms are structurally far more exposed to enforcement. Absence is weak evidence for an unregulated small vendor.

**Be strict about relevance.** An environmental fine, an employment dispute, or an antitrust action is not a cybersecurity signal. Importing general "regulatory trouble" into a cyber score adds noise and invites disputes you will lose.

---

#### Government investigations
**Equal?** No. **Direction:** flag for manual review; low or zero automatic score. **Modifiers:** as above, plus corroboration requirement.

Open investigations are not findings. This signal has the worst precision-to-defamation-risk ratio in your framework. Recommendation: surface it to a human analyst, require a second independent source, and do not let it move a score automatically. Under the fair-ratings principles (§7) you must operate a dispute process, and this is the signal class that will generate them.

---

#### Verified adverse media
**Equal?** **No — and this is the most size-biased signal in the entire framework.** **Direction:** PENALTY (low), heavily normalized. **Modifiers:** total media volume (denominator), public/private, sector, language/geographic coverage.

Media coverage volume is a function of company prominence, not risk. A Fortune 500 firm will always generate more adverse-media hits than a 10-person vendor at any level of actual security performance.

> **If you score raw adverse-media count, you have built a company-fame detector.**

Required corrections:
1. **Normalize to adverse *share*, not adverse count** (adverse mentions / total mentions).
2. **Entity resolution confidence threshold** — name collisions are rampant and are a leading cause of false findings against small vendors with generic names.
3. **Category filtering** — security, privacy, fraud, and insider-threat categories only.
4. **Source tiering** — weight established outlets and regulatory press releases above aggregators and content farms.
5. **Recency decay.**
6. **Language coverage awareness** — non-English markets are systematically under-covered. Low adverse media for a vendor in an under-covered market is an artifact, not a clean record. Do not reward it.

---

## 5. Summary matrix

| Signal | Equal for all? | Primary modifiers | Direction | Weight class |
|---|---|---|---|---|
| SPF | ~Yes | email behaviour, B2C | Penalty | Low-Med |
| DKIM | Yes (observability-limited) | — | Penalty / Unknown | Low |
| DMARC | **No** | size, industry, B2C, regulation | Penalty (ordinal, cohort-scaled) | Med-High |
| DNSSEC | **No** | industry, geography, infra role | **Bonus** | Low |
| CAA | **No** | cohort maturity, cert volume | **Bonus** | Low |
| TLS version | Severity yes | obligation, endpoint criticality | Penalty | High |
| Cipher suites | Severity yes (graded) | endpoint criticality, regulation | Penalty | Med-High |
| Certificate validity | ~Yes, density-normalized | cert portfolio size | Penalty | Med-High ↑ |
| HSTS | ~Yes | authenticated sessions | Penalty | Low |
| CSP | **No** | app age/complexity, payment adjacency | Penalty | Low (High if payments) |
| X-Frame-Options | Yes | authenticated UI | Penalty | Very low |
| security.txt | **No** | footprint, self vs platform-provisioned | **Bonus** | Very low |
| Subdomain count | **No** | size, architecture, M&A | **Normalizer** | n/a raw |
| CT history | **No** | age/domain age as denominator | Mixed | Med |
| Shadow assets | **No** | size, M&A, decentralization | Penalty (density + dwell) | High |
| Public breach history | **No** | observability, recency, remediation | Penalty (decayed) | High |
| Exposed data types | **No** | your data overlap, sector | **Consequence, not posture** | High (loss side) |
| KEV | **Yes** | dwell time, exposure only | Penalty / **Gate** | **Highest** |
| CVEs | **No** | footprint, stack, attribution | Penalty (normalized) | Low |
| CVSS | Yes | — | Modifier only | Very low |
| EPSS | **Yes (invariant)** | — | Modifier | Med-High |
| Published security program | **No** | B2B/B2C, size, sales motion | **Bonus** | Low |
| VDP | **No** | **footprint size**, industry | Bonus + footprint-scaled penalty | Low-Med |
| Security contact | **No** | provisioning source | **Bonus** | Very low |
| Domain age | Not a security signal | — | **Gate + Normalizer** | n/a |
| Domain registration quality | Expectation varies | consequence, cohort norms | Penalty | Med |
| Legal entity status | Yes | geography (observability) | **Gate** | n/a |
| Company age | Not a scoring input | — | **Normalizer / cohort** | n/a |
| Company continuity | **No** | revenue, funding, dependence | Penalty (**separate dimension**) | Med-High |
| ISO 27001 | **No** | size, geography, buyer profile | **Bonus** | Med |
| SOC reports | **No** | size, geography, type/period | **Bonus** | Med |
| Regulatory disclosures | **Structurally unequal** | public/private, jurisdiction | **Bonus only** | Low-Med |
| Regulatory enforcement | **No** | regulation intensity, recency | Penalty | Med-High |
| Government investigations | **No** | corroboration | **Manual review** | ~0 automatic |
| Verified adverse media | **No** | **media volume denominator** | Penalty (normalized) | Low |

---

## 6. Implementation architecture

### 6.1 Decompose the score into three independent quantities

Do not produce a single number until the last step. The risk you actually care about factors as:

```
VendorRisk = P(vendor compromised)
           × P(compromise reaches you | vendor compromised)
           × Loss(you)
```

Map that to three separately computed sub-scores:

1. **Posture score** — observed control state. *This is where cohort/diagnosticity normalization lives.*
2. **Exposure score** — footprint, shadow assets, KEV/EPSS-weighted vulnerability load. *This is where denominators live.*
3. **Consequence multiplier** — data classes held, integration depth, OAuth/SSO scopes granted, network access, business criticality, substitutability. *This should not be firmographic at all — it is a property of your relationship with the vendor.*

Keeping these apart is what lets you answer "why did this vendor score badly?" with a sentence a procurement lead can act on. It is also what prevents the classic failure where a huge, well-run vendor and a tiny, sloppy one land on the same composite number for opposite reasons.

### 6.2 Per-signal weight formula

```
w_i(vendor) = w_i^base
            × D_i(cohort)        # diagnosticity: peer base-rate adjustment
            × O_i(obligation)    # regulatory / contractual duty
            × C_i(consequence)   # blast-radius relevance to you
            ÷ N_i(exposure)      # footprint normalizer for count-based signals
```

With these constraints:

- **`D_i` from surprisal** where you lack labels: `D_i = clamp(-log2(P(finding | cohort)) / k, 0.5, 2.5)`. Re-estimate cohort base rates **from your own vendor portfolio**, not from global domain studies — global studies measure the population of registered domains, which is not the population of companies you buy from, and your own portfolio is both easier to measure and far more accurate.
- **`D_i` from likelihood ratios** once you have outcome labels: `D_i = clamp(log(LR_cohort), bounds)`.
- **Bound the product.** `D × O × C ∈ [0.5, 2.5]` per signal, and total firmographic influence on the composite posture score ≤ ~20–25%, per §2.5.
- **Log-scale all count normalizers**, following the established precedent of logarithmic size normalization bounded at the tails.
- **Percentile-rank within cohort** for the final presentation layer, so scores are interpretable as "worse than 80% of comparable vendors" rather than as an absolute that drifts with the population.

### 6.3 Three distinct scoring mechanics

- **Gates** (block or escalate; not averaged): dissolved legal entity; KEV past due date on an internet-facing authenticated asset; no valid TLS at all; unresolvable ownership/attribution.
- **Penalties** (cohort-scaled): KEV, cert validity, TLS/cipher, missing SPF/DMARC, shadow assets, recent breach, enforcement actions.
- **Bonuses** (presence-only, never penalize absence): DNSSEC, CAA, security.txt, VDP, trust page, registry lock, ISO/SOC, positive regulatory disclosure quality.

Getting the bonus/penalty split right is the highest-leverage single change you can make. Roughly a third of your signal list has base rates low enough that penalizing absence adds only noise.

### 6.4 Avoid double-counting (this will otherwise silently break your model)

Four clusters in your list describe overlapping underlying facts:

| Cluster | Overlap | Resolution |
|---|---|---|
| KEV / CVE / CVSS / EPSS | All describe the same vulnerabilities | Pick one primary in precedence order **KEV > EPSS > CVSS**; use the others as modifiers on the primary, not as additive items |
| TLS version / cipher suites | TLS 1.0 mechanically forces weak ciphers | Score the protocol finding; treat ciphers as an increment only where they add information beyond the version |
| CSP / X-Frame-Options | `frame-ancestors` subsumes XFO | Accept either; do not penalize twice |
| Subdomains / shadow assets / CT history | All footprint views | One footprint model, several views into it |

Additionally, resist correlated-signal stacking within the hygiene category: SPF, DKIM, DMARC, HSTS, CAA and security.txt all partly measure "does this org have someone who reads RFCs." Six correlated low-information signals summed together can outweigh one KEV, which is exactly backwards. Consider a diminishing-returns transform (e.g. score the hygiene category on a concave function of the count of failures) rather than a linear sum.

### 6.5 Cohort design

Define cohorts from variables that are cheap and reliable to obtain:

```
cohort = employee_band × sector_family × public_private × primary_jurisdiction
```

**Beware sparsity.** Four employee bands × six sector families × two × three regions = 144 cells; you will not have enough vendors to estimate base rates in most of them. The established approach in the loss-modelling literature is to model these as regularized main effects rather than as independent cells — Cyentia's own methodology <cite index="8-1">fits log-normal models with random effects that account for various slices like industry and revenue bands</cite>. Do the same: hierarchical/partial pooling, not lookup tables.

---

## 7. Validation, governance, and the tests that will catch your mistakes

### 7.1 The single most important test

> **Ablate all posture signals and score vendors using firmographics alone. Compare AUC to your full model.**

If firmographics-only gets close to the full model, you have not built a security rating — you have built a firmographic classifier with security-themed features. This test takes an afternoon and will tell you more about your design than any amount of expert review.

Run the mirror test too: posture-only versus full model. If firmographics add nothing, drop them and simplify.

### 7.2 Backtest properly

- Label against forward-window public incidents. This is achievable in principle: Liu et al. demonstrated that <cite index="20-1">cyber security incidents can be predicted from externally observable properties of an organization's network, using 258 externally measurable features across two categories — mismanagement symptoms such as misconfigured DNS or BGP, and malicious activity time series including spam, phishing, and scanning</cite>, with <cite index="26-1">mismanagement features ranking as the most important feature class, and dynamic features outperforming static ones</cite>.
- **Report discrimination metrics within cohort, never pooled.** Pooled AUC will be inflated by your model's ability to detect company size, which correlates with disclosure probability — you will be measuring your own selection bias and calling it accuracy.
- **Report calibration, not just discrimination.** EPSS publishes calibration plots for exactly this reason. A model that ranks well but is badly calibrated will produce risk-acceptance decisions that are systematically wrong in magnitude.
- **Monotonicity and stability tests.** A vendor that fixes a finding must never lose points. Re-cohorting must not silently move thousands of scores. Both failures are common and both destroy trust instantly.

### 7.3 Expect a hard ceiling on external signals

Be honest in your documentation about what this class of model cannot see. The current threat data is blunt about it: <cite index="78-1">83% of privilege escalation incidents involved no CVE exploitation at all, and the high-profile cloud third-party campaigns were not CVE stories — they were OAuth token stories and missing-MFA stories</cite>. <cite index="75-1">Only 23% of third-party organizations fully remediated missing or improperly secured MFA on cloud accounts, and weak password and permission misconfigurations took a median of 8 months to resolve 50% of findings</cite>.

Meanwhile the stakes keep rising: <cite index="74-1">third-party involvement in breaches is up 60% year over year, now accounting for 48% of all breaches</cite> — <cite index="77-1">up from 30% the prior year and 15% the year before that</cite>.

Practical implication: cap how much confidence the external score carries for high-criticality vendors, and pair it with attestation, questionnaire, or contractual evidence above a criticality threshold. Identity hygiene — MFA coverage, OAuth scope discipline, credential rotation — is where the third-party losses actually are, and it is nearly invisible to external scanning. If your framework has a strategic gap, that is it, not signal weighting.

### 7.4 Fairness and governance obligations

If you contextualize by firmographics, you take on governance duties. The relevant industry baseline is the U.S. Chamber of Commerce framework, which was <cite index="62-1">modelled on the Fair Credit Reporting Act, which helped increase confidence in the credit process by ensuring both the usability of ratings for legitimate purposes and recognizing the interests of rated parties to ensure the underlying data is sound</cite>. It comprises <cite index="59-1">transparency; dispute resolution; accuracy and validation; methodology model governance; independence; and confidentiality</cite>, and specifies that <cite index="58-1">rating companies should have an appeal and dispute resolution process, disputed ratings should be notated as such until resolved, and ratings should be empirical, data-driven, or notated as expert opinion</cite>.

Applied to a cohort-normalized design specifically:

- **Publish your cohort definitions and modifier ranges.** A vendor must be able to see which cohort it was placed in and why.
- **Make cohort assignment disputable.** Misclassification (wrong sector, wrong size band, wrong jurisdiction) will be one of your top two dispute categories.
- **Make attribution disputable.** It will be the other one. Shared hosting, CDN address space, subsidiaries, and acquired brands generate most external-rating false positives.
- **Give notice before weight or cohort changes.** A cohort redefinition can move thousands of scores overnight with no change in any vendor's actual behaviour.
- **Label expert-set weights as expert judgment** until you have backtested them. Most of your initial weights will be expert judgment; that is fine and normal, but it must be declared.

### 7.5 Anti-patterns to design against explicitly

1. **Ability-to-pay bias.** Do not let revenue and headcount become a proxy for "can afford compliance." Small firms lose on certifications but **win on tempo** (14–18 day remediation versus 56 days at midmarket). Make sure your framework has channels where a small vendor can legitimately score well; otherwise your score is a size league table.
2. **"Old company = bad."** The evidence supports old *code* accumulating debt, not old *companies* having worse DNS records.
3. **"Big company = bad."** Large firms have more incidents but <cite index="83-1">nearly 2x fewer vulnerabilities per system than SMBs</cite>. And for third-party risk, what usually matters is `P(their incident reaches you)`, which is driven by your integration depth, not their headcount.
4. **Platform-provisioned credit.** Discount hygiene signals the vendor didn't configure (§4.1, security.txt).
5. **Multi-tenant subdomain inflation.** Detect per-tenant naming or every SaaS vendor fails.
6. **Fame-weighted reputation.** Normalize adverse media by total coverage.
7. **Certification as absolution.** Never let ISO/SOC offset a KEV.

---

## 8. What the research does *not* support

Stated plainly, so you can calibrate confidence in the recommendations above:

1. **There is no published, peer-reviewed table of per-signal likelihood ratios by firmographic cohort.** The strongest validation work is vendor-sponsored: the Marsh McLennan analysis <cite index="14-1">compared Bitsight security performance data across 365,000 organizations against Marsh McLennan's proprietary incident and claims database from 2018–2021</cite> and found <cite index="17-1">fourteen analytics — the rating plus thirteen risk vectors — correlated with incidents across endpoint management, vulnerability management, secure communications, and user training</cite>. That is meaningful evidence that external signals carry information. It is not a published weighting scheme, effect sizes are not independently reproducible, and the models are closed. Treat my recommended weight *classes* as informed priors to be calibrated on your own data, not as findings.

2. **Correlation is not uplift.** A low rating correlates with breach in part because both are caused by low security investment. That is entirely adequate for prediction — which is what you are building — but do not let it become a claim that adding an HSTS header reduces breach probability by some amount. Effect estimates like <cite index="19-1">organizations with ratings between 300 and 500 being 7.9x more likely to be targeted by ransomware</cite> are associational.

3. **Published adoption base rates measure domains, not your vendors.** Every base rate in §2.1 comes from internet-wide domain scans. Your vendor portfolio is a biased sample of that population — probably skewed toward B2B SaaS and toward companies that survived your procurement process. **Re-estimate every base rate on your own portfolio.** It is cheap, it is more accurate, and it makes your cohort adjustments defensible under dispute.

4. **Breach datasets carry survivorship and disclosure bias throughout.** The Cyentia/Advisen-derived figures are explicitly limited to incidents that <cite index="4-1">make their way into the public record, through outward signs or impacts, mandatory reporting, voluntary disclosure</cite>. Every firmographic effect derived from them is partly an observability effect. That is the core of §2.4 and it deserves a permanent caveat in your model documentation.

5. **The external-signal paradigm has a demonstrated ceiling** (§7.3). Several major recent third-party compromises occurred at organizations with unremarkable external posture.

---

## 9. Recommended next steps

1. **Split your model into posture / exposure / consequence** before touching weights (§6.1). Most of the value is in this one change.
2. **Reclassify the ~10 low-base-rate signals from penalty to bonus** — DNSSEC, CAA, security.txt, VDP, trust page, security contact, ISO, SOC, regulatory disclosures, registry lock. This alone will materially reduce noise.
3. **Add denominators** to every count-based signal (§2.2).
4. **Implement dwell-time measurement** for KEV, expired certs, and TLS findings — and let it override age-based reasoning wherever available (§3.4).
5. **Re-estimate all cohort base rates on your own portfolio** (§8.3).
6. **Run the firmographics-only ablation test** (§7.1) before you ship.
7. **Add an observability weight** to every absence-of-evidence signal (§2.4).
8. **Write the dispute and cohort-transparency process** now, not after your first angry vendor (§7.4).

---

## Sources

**Loss and frequency base rates**
- Cyentia Institute, *Information Risk Insights Study* (IRIS 20/20, 2022, 2025) and *IRIS Ransomware* — cyentia.com/iris
- Cyentia risk data methodology — cyentia.com/risk-data

**External-signal predictive validity**
- Liu, Sarabi, Zhang, Naghizadeh, Karir, Bailey & Liu, "Cloudy with a Chance of Breach: Forecasting Cyber Security Incidents," USENIX Security 2015
- Marsh McLennan Cyber Risk Analytics Center × Bitsight correlation study (2022), 365,000 organizations
- RiskRecon/Cyentia, *Internet Risk Surface* series and *Navigating the Internet Risk Surface*

**Vulnerability prioritization**
- Jacobs, Romanosky, Edwards, Adjerid & Roytman, "Exploit Prediction Scoring System (EPSS)," *Digital Threats: Research and Practice* 2(3), 2021
- EPSS v4 release analysis, Empirical Security / FIRST, March 2025
- CISA Known Exploited Vulnerabilities Catalog

**Adoption base rates**
- EasyDMARC *DMARC Adoption & Enforcement Report* 2025 and 2026; Red Sift global DMARC analysis (73.3M domains, Dec 2025); Valimail sector data
- APNIC/Cloudflare DNSSEC measurement 2025–2026; Wotschofsky DNSSEC survey (171M domains)
- URIports and IoTDef security.txt adoption studies (2024–2026); Hierlmeier & Sperl, "security.txt Revisited," DTRAP 2023
- Qualys SSL Pulse TLS version statistics

**Standards and obligations**
- RFC 8996, *Deprecating TLS 1.0 and TLS 1.1* (BCP 195, March 2021); RFC 9116 (security.txt)
- PCI DSS v4.0; NIST SP 800-52 Rev. 2
- CA/Browser Forum Ballots SC-081v3 (certificate lifetime schedule) and SC-085v2 (CA DNSSEC validation)
- EU DORA and NIS2 third-party ICT provisions; CISA BOD 18-01, BOD 20-01

**Threat landscape**
- Verizon *Data Breach Investigations Report* 2026 (22,000+ confirmed breaches, 145 countries)
- Veracode *State of Software Security* 2025 and 2026
- Palo Alto Networks Unit 42, newly registered and strategically aged domain research
- Intruder *Attack Surface Management Index* 2026

**Governance**
- U.S. Chamber of Commerce, *Principles for Fair and Accurate Security Ratings* (2017)
- Angst, Block, D'Arcy & Kelley, on symbolic vs. substantive IT security adoption, *MIS Quarterly* (2017)
- Bitsight published normalization methodology
