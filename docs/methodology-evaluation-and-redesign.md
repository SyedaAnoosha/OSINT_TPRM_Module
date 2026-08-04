# Evaluation and Redesign of the Vendor Posture Scoring Methodology

**Research-backed critique of the current model, with a revised specification**

---

## 0. Verdict

Your architecture is better than most commercial security ratings on the two hardest design questions, and worse than it needs to be on four mechanical ones. The good decisions are structural and should be preserved. The bad ones are arithmetic and are fixable without touching your philosophy.

**Design scorecard:**

| Decision | Verdict | Note |
|---|---|---|
| Posture and Confidence as orthogonal axes | **Keep — best decision in the model** | Structurally solves the observability bias that corrupts most ratings |
| Confidence never changes posture | **Keep, with one amendment** | Should gate *publication*, not arithmetic — you already accept this via the Ghost |
| The Ghost (suppress below 40% coverage) | **Keep the principle, fix the cliff** | Currently a step function and an incentive to be unscannable |
| Ongoing issues never decay | **Keep — correct and rare** | A live misconfiguration is a present-tense fact, not history |
| Subtractive scoring from 100 | **Keep the mechanic, fix the prior and the floor** | Transparent and disputable; but 100 is an unjustified starting belief and 0 saturates |
| Benchmarking affects interpretation only | **Keep the principle, reject the consequence** | You can get cohort calibration without live peer arithmetic |
| **No category weights** | **This is the critical flaw** | You have not removed weights — you have delegated them to your scanner's detection inventory |
| **Frequency as a linear multiplier** | **Second critical flaw** | Converts your posture score into a company-size detector |
| Severity ladder 40/20/8/3/0 | Too compressed | Critical:Low of 13:1 lets 14 trivia outrank one actively-exploited vulnerability |
| Mitigation × 0.6 flat | Too blunt, and a governance hazard | One constant for four very different evidence classes; no TTL; no audit trail |
| Age decay on historical events | Right idea, underspecified | No half-life, no event-class differentiation, and time alone shouldn't buy forgiveness |

The two flaws marked critical interact. Together they mean a large, competent vendor with broad surface area can score below a small, negligent one with an actively exploited vulnerability. That is a ranking inversion on the exact comparison the score exists to make.

---

## 1. What your model gets right, and why the research supports it

### 1.1 Separating posture from confidence

This is the single most important thing in your design, and most commercial products get it wrong.

Nearly every "reputation," "breach," and "compliance" signal is observed through a filter whose transmissivity depends on the vendor's size, listing status, jurisdiction, and sector. Public companies and regulated entities have their incidents surface; small private vendors often do not. Cyentia's data is explicitly bounded this way — their figures cover only incidents that <cite index="4-1">make their way into the public record, through outward signs or impacts, mandatory reporting, voluntary disclosure</cite>. Meanwhile <cite index="5-1">over 60% of the Fortune 1000 had at least one public breach over the last decade</cite>, which says as much about disclosure obligations as about security.

A single-axis score cannot distinguish "clean" from "opaque." Yours can. Protect that.

### 1.2 Refusing to publish under-evidenced scores

The Ghost is an explicit refusal to emit a number you can't support. That is rarer than it should be and aligns directly with the industry governance baseline, which specifies that <cite index="58-1">ratings should be empirical, data-driven, or notated as expert opinion</cite>. Keep the principle. §3.4 fixes the implementation.

### 1.3 Ongoing issues never decay

Correct, and it closes a loophole most models leave open. If live misconfigurations decayed, vendors could wait out findings rather than fix them. Your rule means the only way to clear an ongoing finding is to remediate it. That is the right incentive and it should be stated prominently in your published methodology, because it is a genuine differentiator.

### 1.4 Subtractive transparency

Every point of loss traces to a specific finding. This satisfies the transparency and dispute-resolution obligations you inherit the moment you publish scores about other companies — the governance framework built for this domain <cite index="62-1">was modelled on the Fair Credit Reporting Act, which helped increase confidence in the credit process by ensuring both the usability of ratings for legitimate purposes and recognizing the interests of rated parties to ensure the underlying data is sound</cite>, and comprises <cite index="59-1">transparency; dispute resolution; accuracy and validation; methodology model governance; independence; and confidentiality</cite>.

### 1.5 Refusing live peer-relative arithmetic

I want to steelman this before I complicate it, because the instinct is sound. Peer-relative scoring makes numbers non-stationary: a vendor's score changes when its cohort changes, with no change in its own behaviour. That makes disputes harder, makes historical comparison meaningless, and creates a model-governance problem where a cohort redefinition silently moves thousands of scores overnight.

Your instinct to keep arithmetic reproducible is correct. §3.3 shows how to capture the diagnostic value of peer base rates *without* live percentile ranking.

---

## 2. The two critical flaws

### 2.1 "No category weights" does not remove weighting — it hides it

**The claim:** categories emerge naturally from accumulated penalties, so no weights are needed.

**The reality:** if categories emerge from accumulated penalties, then each category's effective weight equals *the number of distinct findings your scanner can generate in it, times their severities.* You have not eliminated weighting. You have delegated it to your detection inventory.

Work the arithmetic on your own signal list. Cyber Hygiene contains twelve signals. Suppose a vendor fails four at Medium and eight at Low:

```
4 × 8  = 32
8 × 3  = 24
        ----
         56 points
```

Now a different vendor has a single actively-exploited vulnerability on an internet-facing authenticated endpoint — one Critical:

```
1 × 40 = 40 points
```

**The vendor missing a dozen headers and DNS records scores worse than the vendor being actively exploited.** That is not a hypothetical edge case; it is the modal outcome, because hygiene findings are numerous, cheap to detect, and highly correlated, while KEV findings are singular.

The evidence says this ordering is exactly backwards. <cite index="79-1">Vulnerability exploitation is now the top breach entry point at 31% of breaches, the first time in 19 years it has surpassed stolen credentials</cite>, and <cite index="74-1">AI is compressing exploitation timelines, with the rapid weaponization of known vulnerabilities creating a capacity crisis for security teams</cite>. Meanwhile several of those hygiene signals carry almost no information at all — <cite index="119-1">security.txt adoption remains below 0.25% of all domains, and the majority appears driven by platform automation rather than deliberate security decisions</cite>, and DNSSEC sits at <cite index="47-1">roughly 7% secure delegation</cite>.

**Three compounding sub-problems:**

**(a) Correlated stacking.** SPF, DKIM, DMARC, DNSSEC, CAA, HSTS, CSP, X-Frame-Options and security.txt all partly measure the same latent variable: "does this organisation have someone who reads RFCs." Summing nine correlated measurements of one thing gives that thing nine times the weight of an uncorrelated, higher-precision signal.

**(b) Root-cause double counting.** One misconfiguration frequently generates several findings. RFC 8996 notes that <cite index="104-1">TLS 1.0 and 1.1 require older cipher suites no longer desirable for cryptographic reasons, lack AEAD support, and depend on SHA-1 for handshake integrity and peer authentication</cite> — so a single TLS 1.0 endpoint can produce a protocol finding, a weak-cipher finding, a no-forward-secrecy finding and a no-AEAD finding. Four penalties, one root cause, one remediation action. Similarly, KEV / CVE / CVSS / EPSS are four views of the same vulnerabilities; if each generates a finding, you quadruple-count.

**(c) Ungoverned model drift.** Every new detection you ship silently reweights the entire model. Add three header checks and web hygiene gains weight against vulnerability management, with no decision, no review, and no notice. Under the model-governance principle this is a material methodology change disguised as a feature release.

### 2.2 Linear Frequency converts posture into a size measurement

Your formula multiplies severity by frequency. Ten expired certificates therefore cost ten times one expired certificate.

But raw counts are footprint measurements, not risk measurements. The evidence is consistent and unambiguous:

- <cite index="83-1">Larger companies have a much broader risk surface but nearly 2x fewer vulnerabilities per system than SMBs</cite>.
- <cite index="133-1">54% of SMEs (1–250 employees) had at least one attack surface exposure in twelve months versus 70% of midmarket (251–5,000); organizations with 1,000–5,000 employees manage 748 assets on average, more than five times as many as organizations with 251–1,000</cite>.
- The mature commercial engines normalize explicitly: <cite index="165-1">large companies typically have more findings than smaller companies, so ratings are normalized based on organization size, using employee count, magnitude of digital footprint, and overall count of observations to quantify attack surface</cite>, with <cite index="161-1">size factored into the impact calculation on a logarithmic basis, bounded at 100 employees at the low end and 100,000 at the high end</cite>.
- The problem is acknowledged directly in the ratings patent literature: <cite index="137-1">intuition suggests risk scales linearly in network size because each endpoint is a new penetration vector, but such an approach is clearly naïve — a large organization with excellent practices may maintain large numbers of secure endpoints managed uniformly by a single central administrator, in which case additional endpoints do not imply increased breach risk</cite>.

Two concrete failures in your current form:

**Two expired certs out of three is a program failure. Ten out of four thousand is a rounding error.** Linear frequency ranks the four-thousand-cert vendor five times worse.

**Multi-tenant SaaS vendors are catastrophically mis-scored.** A vendor provisioning per-customer subdomains will show tens of thousands of names. Under linear frequency, any finding class that touches those names produces an unbounded penalty. Your best-architected SaaS vendors will bottom out the scale.

---

## 3. The remaining structural problems

### 3.1 The scale saturates at both ends

**Bottom.** Three Criticals reach 120 points of penalty against a 100-point scale. A vendor with three Criticals and a vendor with fifteen both publish as 0. You lose all discrimination precisely where your highest-risk vendors sit — and where triage decisions are most consequential.

**Top.** A vendor with no findings scores 100 regardless of whether it is a hardened bank or a three-page brochure site with nothing to find. **Absence of findings scales with absence of attack surface.** Your model has no denominator anywhere, so it cannot distinguish "clean because well-run" from "clean because tiny."

There is a subtle interaction with Confidence here that is worth surfacing: a three-host vendor can achieve *very high check coverage* — you ran every check you have — while resting on a *very thin evidence base*. Coverage ratio and evidence volume are different quantities, and your Confidence dimension currently appears to measure only the first.

### 3.2 Starting at 100 encodes an empirically unjustified prior

"Innocent until proven guilty" is the right ethical posture and the wrong statistical one. The base rates say a perfect prior is not defensible:

- <cite index="5-1">Roughly one in four Fortune 1000 firms will suffer a cyber loss event annually</cite>.
- <cite index="96-1">Security debt now affects 82% of organizations, up 11% year-over-year, and critical security debt affects 60%, a 20% relative increase</cite>.
- <cite index="75-1">Only 23% of third-party organizations fully remediated missing or improperly secured MFA on cloud accounts, and weak password and permission misconfigurations took a median of 8 months to resolve 50% of findings</cite>.

A vendor at 45% coverage with zero findings publishing as 100 is almost certainly wrong. The fix is not to abandon your axiom — it is to generalise the mechanism you already believe in (§3.4).

### 3.3 Severity is carrying load that four other variables should carry

Your formula has exactly one channel for context: the severity enum assigned per finding type. That single global constant has to encode everything. It cannot.

**The problem, concretely.** "Missing DMARC" gets one severity. But the same observation carries wildly different information depending on cohort:

| Cohort | DMARC adoption | Information content of "absent" |
|---|---|---|
| Fortune 500 | <cite index="40-1">95% adoption, over 80% at enforcement</cite> | 1-in-20 anomaly — loud signal |
| Inc. 5000 | <cite index="40-1">more than half remain at monitoring-only</cite> | Modal — weak signal |
| All domains | <cite index="42-1">14.9% of 73.3M domains have any record; 2.5% enforce p=reject</cite> | Near-uninformative |
| US federal | <cite index="42-1">92% enforcement due to BOD 18-01</cite> | Severe outlier |

Formally, the amount your belief should move on observing a finding scales with its *surprisal*, `−log₂ P(finding | cohort)`. Missing DMARC in the F500 cohort is 4.3 bits. Missing DNSSEC globally is 0.12 bits. **That is a 35× ratio, derived entirely from public adoption data, and your model currently expresses it as a single number.**

**But — and this is the resolution — you do not need live peer arithmetic to capture it.**

Your principle is that benchmarking must not touch the arithmetic, because peer-relative scoring is non-stationary and non-reproducible. That principle survives intact if you make severity a function of *(finding type, cohort)* resolved against a **published, versioned lookup table** rather than against a live population percentile.

```
Severity = SeverityTable[finding_type][cohort]     # constant at scoring time
```

At scoring time this is still a fixed constant. Still fully reproducible. Still auditable. Still disputable. Still explainable to a vendor: "in your cohort, 95% of comparable organisations enforce DMARC; you do not." The table is versioned and changes only under model governance with notice — exactly as your philosophy demands. You are using empirically calibrated priors, not live ranking.

The same logic extends to the other three missing channels: **Obligation** (a finding that violates a binding regulatory duty is a different artifact — PCI DSS <cite index="101-1">required disabling early TLS by 30 June 2018</cite>, and DORA imposes prescriptive ICT third-party requirements on EU financial entities), and **Consequence** (which belongs in a separate dimension entirely — see §4.6).

### 3.4 The Ghost is a cliff, and it rewards opacity

Three problems with a hard 40% gate:

**(a) Discontinuity.** 39.9% → no score. 40.1% → full score, potentially 100. Vendors near the boundary will flip-flop as scan coverage fluctuates, which destroys trust in the number.

**(b) Coverage is not uniform in value.** 40% coverage that includes vulnerability and KEV assessment is worth vastly more than 40% that is all HTTP headers. Confidence should be **risk-weighted coverage** — weighted by the severity mass each check is capable of producing — not raw check-count coverage.

**(c) It creates an incentive to be unscannable.** If a vendor knows that low coverage suppresses a score that would otherwise be bad, opacity is rewarded. This is the detection-bias problem reappearing inside your own architecture. The fix has two parts:

1. **Publish "Insufficient Evidence" as an explicitly adverse state**, not a neutral absence, and route it mandatorily to manual assessment. Procurement must not be able to read a Ghost as a pass.
2. **Replace the cliff with a ceiling ramp.** This preserves your axiom precisely, because a ceiling governs *publishability*, not arithmetic — which is what the Ghost already does. You are generalising a mechanism you already accept from a step function to a curve.

```
confidence < 40%   → no publish; "Insufficient Evidence" (adverse); manual review required
40–60%             → publish, ceiling 80
60–75%             → publish, ceiling 90
75–90%             → publish, ceiling 97
≥ 90%              → publish, ceiling 100
```

Posture arithmetic is untouched. Confidence still never subtracts a point. It only bounds what you are willing to assert.

### 3.5 Mitigation × 0.6 is too blunt and is a governance hazard

Four distinct things are being collapsed into one constant:

| Mitigation class | What it actually means | Appropriate treatment |
|---|---|---|
| Verified compensating control removing exploitability | WAF virtual patch confirmed effective; asset network-isolated from data | Large reduction — ×0.25 |
| Verified partial mitigation | Control reduces but does not remove exploitability | ×0.6 (your current value, now correctly scoped) |
| Vendor-asserted, unverified | "We've handled it" with no artifact | ×0.85 at most |
| **Risk accepted by your business owner** | Your appetite, not their security | **×1.0 — must not change posture** |

That last row is the important one. **Risk acceptance is a property of your risk appetite, not of the vendor's security posture.** If accepting a risk improves the vendor's score, you have corrupted the measurement instrument with your own tolerance, and next quarter you will read your own acceptance back as evidence of vendor quality. Track accepted risk in your register, alongside the unmodified posture score.

Three further defects:

- **No TTL.** Mitigations without expiry become permanent score laundering. Attach expiry (suggest 180 days for verified, 90 for asserted) with mandatory re-verification.
- **No audit trail.** Under the governance principles you need who approved, on what evidence, when, and when it lapses.
- **Ability-to-pay bias through the back door.** "Human-approved mitigation" is a discretion channel, and discretion channels get lobbied. Large vendors have account teams and relationship managers to argue for mitigations; a fifteen-person vendor does not. Left unconstrained, this becomes the mechanism by which your scores start tracking vendor sales capacity. Require artifact-based evidence, not conversation.

### 3.6 Age decay is underspecified, and calendar time shouldn't buy absolution

Two gaps:

**No half-life, and no event-class differentiation.** A botnet observation and a regulatory enforcement action should not decay at the same rate. Suggested starting values (to be recalibrated against your own outcomes):

| Event class | Half-life | Rationale |
|---|---|---|
| Malware / C2 beacon observation | 1 month | Highly transient |
| Botnet / compromised-system observation | 3 months | Transient but indicative |
| Adverse media | 12 months | Noisy, prominence-driven |
| Public breach | 24 months | Recidivism is real but attenuates |
| Regulatory enforcement | 36 months | Adjudicated finding; durable |
| **Ongoing configuration finding** | **none** | Keep your existing rule |

**Time alone should not grant the discount.** Recidivism is genuinely predictive — among public companies, <cite index="64-1">of 1,014 data breaches disclosed before the end of 2021, 334 (about 33%) were repeat breaches</cite>, and <cite index="64-1">second-time breaches hurt firm value more than the first, with the damage most severe for financial-data breaches</cite>. But the literature is equally clear that form is not substance: <cite index="65-1">merely increasing IT security usage does not necessarily reduce breaches, as effective integration of IT security into processes is essential, whereas symbolic adoption diminishes IT security effectiveness and increases breach risks</cite>.

So gate the decay on evidence. Full decay requires at least one of: documented remediation with specifics, security leadership change, a post-incident attestation, or a demonstrably improved external posture trend. Absent any of those, apply a floor — decay to no less than 40% of original severity, not to zero.

And **weight patterns superlinearly.** Two incidents in 36 months should cost considerably more than twice one incident, because a cluster evidences systemic rather than episodic failure.

### 3.7 There are no gates

Everything in your model is arithmetic, so everything is fungible. A vendor at 100 with one actively-exploited internet-facing vulnerability publishes at 60 and clears a "≥50" procurement threshold.

Some findings should not be scoreable. Recommended hard gates that bypass arithmetic entirely:

- Actively exploited vulnerability (KEV) past its remediation due date on an internet-facing authenticated or data-bearing asset
- Legal entity dissolved, struck off, or not in good standing
- No valid TLS on a data-bearing endpoint
- Ownership or attribution unresolvable

### 3.8 There is no consequence dimension

Your posture score is vendor-intrinsic. But the risk you actually care about factors as:

```
VendorRisk = P(vendor compromised) × P(compromise reaches you) × Loss(you)
```

Your model computes a proxy for the first term only. Two vendors at 72 might be a payroll processor holding your entire employee PII set with SSO federation, and a stock-photo service. The urgency is not theoretical: <cite index="74-1">third-party involvement in breaches is up 60% year over year, now accounting for 48% of all breaches</cite>, <cite index="77-1">up from 30% the prior year and 15% the year before that</cite>.

This is **additive** to your design, not a rewrite — and it must never be multiplied into posture. See §4.6.

---

## 4. Revised specification

### 4.1 Revised penalty formula

```
EffectivePenalty(finding) =
      Severity[finding_type][cohort]        # versioned table; absorbs diagnosticity
    × Obligation(finding, vendor)           # 1.0 | 1.25 | 1.5, capped
    × FrequencyFactor(n, E[n])              # concave, density-based
    × Decay(age, event_class, remediation_evidence)
    × Mitigation(class, evidence, ttl)
```

Then aggregate with diminishing returns within category, sum across categories:

```
CategoryPenalty(c) = Σᵢ pᵢ · λ^(rankᵢ − 1)          where λ = 0.7, rank by descending pᵢ
RawPosture         = 100 − Σ_c CategoryPenalty(c) + min(DiligenceCredit, 10)
Posture            = clamp(RawPosture, 0, Ceiling(confidence))
```

Retain `RawPosture` unclamped internally for ranking the worst vendors.

### 4.2 Frequency: concave and density-based

Replace the linear multiplier:

```
FrequencyFactor(n, E[n]) = min( 1 + 0.6 · ln(1 + n / E[n]) , 3.0 )
```

where `E[n]` is the expected count for this finding type given the vendor's observed footprint, calibrated on your own portfolio. Cap at 3.0.

Worked comparison, ten expired certificates:

| Vendor | Certs | Expired | Current model | Revised |
|---|---|---|---|---|
| A | 4,000 | 10 | ×10 | ×1.0 (at or below expectation) |
| B | 3 | 2 | ×2 | ×2.4 (far above expectation) |

The revised model ranks these correctly. The current one ranks them backwards by a factor of five.

**Multi-tenant detection is mandatory.** Before computing `E[n]`, detect per-tenant subdomain provisioning (naming regularity, shared wildcard certificates, uniform infrastructure fingerprints) and exclude those names from the footprint denominator and from finding counts. Without this, your best SaaS vendors bottom out.

### 4.3 Revised severity ladder

Your current 40/20/8/3/0 gives Critical:Low ≈ 13:1, meaning fourteen trivia outrank one actively-exploited vulnerability. Widen it:

| Level | Current | Revised | Rationale |
|---|---|---|---|
| Critical | 40 | **50** | Should approach unrecoverable alone |
| High | 20 | **20** | Unchanged |
| Medium | 8 | **6** | Slight compression to reduce mid-band stacking |
| Low | 3 | **1.5** | Should be a nudge, not a lever |
| Informational | 0 | **0 → routes to Confidence** | See below |

Critical:Low becomes 33:1.

**Informational findings should feed Confidence, not posture.** Right now you compute and store findings that can never affect anything. But an informational observation *is* evidence — it demonstrates coverage. Route it to the Confidence numerator. This makes the level meaningful instead of decorative, and it strengthens the axis you most want to strengthen.

Re-run the §2.1 inversion under the revised model. Twelve hygiene failures (four Medium, eight Low), sorted descending with λ = 0.7:

```
6.0 + 4.2 + 2.94 + 2.06 + (1.5 × 0.24 + 1.5 × 0.17 + …)  ≈  15.9
```

Against one Critical KEV at 50. The vulnerability now dominates hygiene stacking by better than 3:1. Correct ordering restored, and note that you achieved it **without introducing category weights** — the diminishing-returns transform preserves your emergence principle while killing the correlated-stacking bug.

### 4.4 Root-cause deduplication

Before scoring, collapse findings that share a remediation action:

| Cluster | Rule |
|---|---|
| KEV / CVE / CVSS / EPSS | Precedence **KEV > EPSS > CVSS**. One penalty. Others become modifiers, never additive items. |
| TLS version / cipher suites | Score the protocol finding. Ciphers add an increment only where they carry information beyond the version. |
| CSP / X-Frame-Options | `frame-ancestors` satisfies XFO. Accept either. Never penalize twice. |
| Subdomains / shadow assets / CT anomalies | One footprint model, several views. One penalty per distinct asset defect. |

**Rule of thumb: one remediation ticket, one penalty.** If fixing one thing clears four findings, it was one finding.

### 4.5 Gates, penalties, credits

**Gates** (bypass arithmetic; block or escalate): §3.7 list.

**Diligence credits** (capped at +10 total; can offset penalties, never exceed 100). These are the signals whose base rates are so low that penalizing absence adds only variance:

| Credit | Points | Base-rate justification |
|---|---|---|
| DNSSEC signed | +2 | <cite index="47-1">~7% secure delegation</cite> |
| CAA record present | +1 | <cite index="54-1">~1.6% of top-million at early measurement</cite> |
| security.txt, self-provisioned, RFC-conformant, unexpired | +1 | <cite index="119-1">below 0.25% of domains, mostly platform-provisioned</cite>; <cite index="117-1">only 44% RFC-conformant</cite> |
| VDP with named security contact | +2 | Low base rate; genuine causal mechanism |
| Registry lock on primary domain | +2 | Rare; prevents a catastrophic single point of failure |
| ISO 27001, in-scope and current | +3 | <cite index="126-1">can initially cost 50–60% more than SOC</cite> — real investment |
| SOC 2 Type II, unqualified, current | +3 | 12-month period ≫ Type I snapshot |
| HSTS preload | +1 | Deliberate, verifiable |

**Roughly a third of your signal list should move from penalty to credit.** This is the highest-leverage single change available to you and it will measurably reduce noise.

### 4.6 The consequence dimension (separate, never multiplied in)

Compute a **Criticality Tier** per vendor relationship from: data classes held, integration depth, OAuth scopes granted, network access, business criticality, substitutability. Report alongside posture. Drive action from the matrix, not from a blended number:

| | T1 Critical | T2 Important | T3 Standard | T4 Low |
|---|---|---|---|---|
| **Posture ≥ 85** | Annual review | Annual | Biennial | Passive |
| **70–84** | Quarterly + remediation plan | Semi-annual | Annual | Passive |
| **50–69** | Remediation plan required, contractual milestones | Quarterly | Annual | Passive |
| **< 50** | Escalate; do not onboard without exception | Remediation plan | Monitor | Monitor |
| **Insufficient Evidence** | **Mandatory manual assessment** | Manual assessment | Questionnaire | Monitor |
| **Gate triggered** | **Block** | Block | Escalate | Escalate |

Keeping these axes separate is what lets you explain a score in one sentence to a procurement lead, and what prevents a huge well-run vendor and a tiny sloppy one from landing on the same composite number for opposite reasons.

---

## 5. Signal-by-signal severity assignment

Concrete values on the revised ladder. Cohort columns: **Micro** (<50 employees, unregulated), **Mid** (50–1,000), **Enterprise/Regulated** (>1,000 or in PCI/HIPAA/DORA/NIS2 scope).

### 5.1 Cyber Hygiene

| Signal | Micro | Mid | Ent/Reg | Notes |
|---|---|---|---|---|
| SPF absent or invalid | 6 | 6 | 6 | Score correctness, not presence. <cite index="42-1">A 2025 survey of 713 US .gov domains found 60% had SPF errors — missing records, invalid syntax, or the 10-DNS-lookup problem — silently breaking DMARC</cite>. `+all` or lookup overflow ≥ absence. Cost to fix ≈ 0 → no cohort leniency. |
| DKIM unobservable | 0 | 0 | 0 | Route to Confidence as reduced coverage. Selector enumeration is unreliable; treat as *unknown*, never *failing*. |
| DMARC absent | 1.5 | 6 | 20 | The clearest cohort case in your list (§3.3). |
| DMARC at `p=none` | 0.75 | 3 | 10 | Half of absent. <cite index="41-1">More than half a million domains with DMARC records remain at p=none, the monitoring-only policy that offers zero protection against spoofing</cite>. Treating a record as compliance is the most common error in this signal. |
| DNSSEC absent | 0 | 0 | 0 | Credit only. Exception: DNS/hosting/registry operators and government → 6. Geography matters: <cite index="48-1">.cz (59%), .se (55%), .nl (51%), .sk (48%) lead among EU ccTLDs</cite>, so absence is more anomalous for a Nordic vendor. |
| CAA absent | 0 | 0 | 0 | Credit only. |
| TLS 1.0/1.1 — auth or data endpoint | 20 | 20 | 20 × 1.5 obligation | See §5.5 for why the age intuition inverts. |
| TLS 1.0/1.1 — marketing only | 6 | 6 | 6 | Endpoint criticality dominates firmographics. |
| SSLv3 or below | 50 | 50 | 50 | Gate candidate. |
| Weak ciphers — NULL/EXPORT/anon/RC4 | 20 | 20 | 20 | Suppress if already counted via TLS version (§4.4). |
| Weak ciphers — 3DES | 6 | 6 | 6 | |
| No forward secrecy / no AEAD | 1.5 | 1.5 | 1.5 | |
| Certificate expired/mismatched — production auth | 20 | 20 | 20 | Density-normalized. **Weight should rise on schedule** — see §5.4. |
| Certificate expired — non-critical | 6 | 6 | 6 | |
| Self-signed on public production | 20 | 20 | 20 | |
| HSTS absent | 1.5 | 1.5 | 1.5 | Preload = credit. |
| CSP absent — general | 1.5 | 1.5 | 1.5 | Genuine Tier-3 retrofit cost on legacy apps; this is where maturity leniency is defensible. |
| CSP absent/weak — payment page | 20 | 20 | 20 | PCI DSS v4.0 req. 6.4.3 and 11.6.1 make this an obligation, not hygiene. |
| CSP present but `unsafe-inline`/wildcard | 1.5 | 1.5 | 1.5 | Score quality, not presence, or you reward theatre. |
| X-Frame-Options / frame-ancestors absent | 1.5 | 1.5 | 1.5 | Accept either mechanism. |
| security.txt absent | 0 | 0 | 0 | Credit only. |

**Platform-provisioning discount — apply across this whole category.** Cloud, PaaS and site-builder defaults hand small vendors free credit for HSTS, TLS 1.3, modern ciphers and security.txt that reflect their host's competence, not theirs. Detect provisioning (header fingerprints, ASN, default file contents) and discount credits accordingly. Without this, your hygiene score substantially measures hosting choice, and small cloud-native vendors will systematically outscore banks.

### 5.2 Digital Footprint

| Signal | All cohorts | Notes |
|---|---|---|
| Subdomain count (raw) | **0** | Not a risk signal. Feeds `E[n]`. |
| CT: internal/dev/staging hostnames in public logs | 6 | Genuine information disclosure and a strong process signal. |
| CT: CA churn, wildcard over-reliance | 1.5 | Rate-based, not volume-based. |
| CT: names in logs no longer resolving to vendor infrastructure | 6 | Dangling-record precursor. |
| Shadow asset: exposed database | 50 | <cite index="133-1">Exposed databases take the top two spots, with more than a quarter of organizations exposing MySQL</cite>. |
| Shadow asset: exposed admin panel / RDP | 20 | <cite index="133-1">Among SMEs 26% exposed risky ports and 20% exposed HTTP panels, rising to 45% and 39% for midmarket</cite>. |
| Shadow asset: orphaned/dangling DNS | 6 | Subdomain-takeover risk. |
| Shadow asset: stale marketing host | 1.5 | |

**Normalize by footprint and weight by dwell time.** The remediation-tempo data is non-monotonic in size and defeats any linear firmographic rule: <cite index="133-1">small organizations remove exposures fastest, taking 14–18 days on average, with remediation slowing as companies grow into the midmarket and peaking at 56 days for organizations with 5,000+ employees</cite>, improving again at large-enterprise scale. Measure the tempo; don't infer it from headcount.

**M&A is a legitimate and rarely-used modifier here.** Acquisitive vendors inherit unmanaged infrastructure. If you can detect acquisitions, you can contextualize sprawl instead of blindly penalizing it.

### 5.3 Breach & Compromise

| Signal | Severity | Notes |
|---|---|---|
| Public breach ≤ 12 months | 20 | × observability weight (§5.6) |
| Public breach 12–36 months | 6 | Decay gated on remediation evidence (§3.6) |
| Public breach > 36 months, remediation evidenced | 1.5 or 0 | |
| **Pattern: ≥2 incidents in 36 months** | **50** | Superlinear, not additive. Cluster = systemic. |
| Exposed data types | **0 in posture** | Feeds Criticality Tier only |
| **KEV past due date, internet-facing auth/data asset** | **GATE + 50** | |
| KEV within remediation window | 20 | |
| KEV on non-critical asset | 6 | |
| CVE, non-KEV, EPSS ≥ 0.5 | 20 | |
| CVE, non-KEV, EPSS 0.1–0.5 | 6 | |
| CVE, non-KEV, EPSS < 0.1 | 1.5 | Density-normalized, attribution-weighted |
| CVSS | **0 independent** | Modifier only |
| EPSS | **0 independent** | Modifier only |

**Use EPSS, not CVSS, as your exploitability prior.** The comparison is decisive: <cite index="28-1">CVSS 7+ prioritization requires patching 50% of known CVEs to achieve 74.6% exploit coverage, with only 6% efficiency, whereas EPSS v4 achieves similar coverage by patching just 6% of vulnerabilities, increasing efficiency to 47%</cite> — <cite index="29-1">effort reduced by more than 8 times over, from 50.7% down to 6%, for roughly the same security outcome</cite>.

Three implementation notes: be consistent about probability versus percentile (<cite index="30-1">EPSS estimates the probability of exploitation attempt within the next 30 days and also provides percentile rankings — a score of 0.15 at the 89th percentile means 89% of all scored CVEs sit at or below it</cite>); **KEV supersedes EPSS**, since EPSS is a pre-threat-intelligence estimate; and re-pull EPSS daily, unlike CVSS.

**Attribution confidence must gate CVE penalties.** Banner-based version inference cannot see vendor backports, produces high false positives, and misattributes shared and CDN infrastructure. Attribution error is the dominant source of vendor disputes with external ratings.

### 5.4 A signal whose weight should rise on a known schedule

Certificate validity deserves special mention because the environment is changing under it. <cite index="172-1">CA/Browser Forum Ballot SC-081v3, approved April 2025, sets maximum certificate lifespan at 200 days from March 15 2026, 100 days from March 15 2027, and 47 days from March 15 2029, with domain validation reuse dropping to 10 days</cite>. <cite index="174-1">200-day certificates are manageable with disciplined manual processes; 100-day certificates will strain most manual workflows; by 2029 manual management becomes a recipe for outages</cite>.

As lifetimes compress, an expired certificate stops meaning "someone forgot" and starts meaning "this vendor has no certificate lifecycle automation" — a materially stronger inference about the organisation. **Schedule a weight increase at the March 2027 and March 2029 boundaries, and record it as a planned model-governance change now** rather than discovering it as drift later.

(Related: <cite index="177-1">CA/Browser Forum ballot SC-085v2, effective March 15 2026, requires certificate authorities to validate DNSSEC when issuing certificates</cite>, and <cite index="52-1">end-to-end DNSSEC validation grew 45% year-over-year from Q1 2025 to Q1 2026, with signing moving from 7.28% to 8.11%</cite>. Re-estimate the DNSSEC base rate annually; the credit-only treatment is correct today but may not be in five years.)

### 5.5 Why the age intuition inverts on TLS

Worth stating explicitly since it drives the table above.

<cite index="102-1">RFC 8996 formally deprecated TLS 1.0 and 1.1 in March 2021, moving both to Historic status, noting that TLS 1.2 became the recommended version in 2008 — providing sufficient time to transition</cite>. <cite index="98-1">TLS 1.0 and 1.1 are blocked by all major browsers, and banned outright by PCI DSS, NIST SP 800-52 Rev. 2, and HIPAA guidelines</cite>. Remediation is a configuration change.

| Channel | 20-year-old firm | 1-year-old startup |
|---|---|---|
| Severity | Identical | Identical |
| Diagnosticity | High — but a plausible mechanism exists (legacy client compatibility, appliance debt) | **Higher.** Every modern stack ships TLS 1.2/1.3 by default. A 2025-founded company had to actively regress. No legacy story exists. |
| Obligation | Higher if in PCI/HIPAA/DORA scope | Lower unless payment-adjacent |
| Consequence | Typically higher | Typically lower |

The older firm usually ends up penalized more — but through **Obligation** and **Consequence**, not through an age multiplier. On the pure question "does this tell me the vendor is careless?", the startup's TLS 1.0 is the louder signal.

Getting this wrong matters commercially, because SMB risk is where the losses concentrate: <cite index="76-1">96% of ransomware victims where organizational size was known were SMBs, and third parties were involved in 55% of SMB breaches</cite>.

**Design principle worth adopting outright: prefer measured behavioural tempo over firmographic proxies wherever both are available.** Days-since-KEV-listing on an unremediated asset, or months a TLS endpoint has sat misconfigured, is reconstructable from CT logs, passive DNS and your own scan history. It is more accurate than any age proxy, directly interpretable, defensible under dispute, and correlated with what actually predicts incidents — <cite index="18-1">Marsh McLennan found that an organization's patching cadence, as measured by BitSight, was correlated to the likelihood of experiencing a cybersecurity incident</cite>. Where dwell time exists, it should override firmographic priors rather than blend with them.

### 5.6 Governance, Business, Compliance, Reputation

| Signal | Treatment | Notes |
|---|---|---|
| Published security program | Credit; 1.5 penalty only for B2B SaaS > 50 staff with none | Absence largely measures go-to-market motion, not security |
| Vulnerability disclosure policy | Credit; **penalty scaled by footprint**: 0 (<200 hosts), 1.5 (200–1,000), 6 (>1,000) | The one governance signal with a causal mechanism — no channel means externally-found flaws can't be reported |
| Security contact | Credit only | Platform-provisioning caveat applies |
| Domain age | **0 — gate and normalizer only** | See below |
| Domain registration quality | No registrar lock 1.5; expiry < 30 days 6; single DNS provider at high consequence 6 | Registry lock = credit. Hijack yields email, cert issuance and often SSO simultaneously |
| Legal entity dissolved/struck off | **GATE** | Observability varies by jurisdiction — route unverifiable to manual, never penalize the jurisdiction |
| Company age | **0 — cohort assignment and denominator only** | |
| Company continuity distress | 20 on a **separate continuity axis** | Going-concern qualification, security-team exodus, funding gap, sunset notice |
| ISO 27001 / SOC 2 absent | 0; 6 only if enterprise-selling, >100 staff, regulated data | **Score scope and type, not presence.** SoA can exclude the system you're buying; Type II ≫ Type I |
| Expired certification presented as current | 6 | An integrity signal, not a compliance one |
| Regulatory disclosures | **Credit only, never penalty** | Private SMBs cannot produce this signal; penalizing absence builds a public-company preference |
| Regulatory enforcement, security/privacy, ≤24mo | 20 | Adjudicated findings ≫ allegations. Be strict on relevance — an environmental fine is not a cyber signal |
| Regulatory enforcement 24–60mo | 6 | |
| Government investigation | **0 automatic; manual flag** | Open investigations are not findings. Worst precision-to-defamation ratio in the framework |
| Verified adverse media | 1.5 max, on normalized adverse **share** | See below |

**Domain age is not a security-competence signal.** Its evidentiary value lies in fraud and impersonation screening: <cite index="156-1">more than 70% of newly registered domains are malicious, suspicious, or not safe for work — almost ten times the ratio observed in the top 10,000 domains</cite>. But "old domain = safe" is equally false, and this is the part most frameworks miss: <cite index="158-1">strategically aged domains show a malicious rate more than three times higher than newly registered domains, with 22.27% malicious, suspicious, or not safe for work</cite>. Use it as a consistency gate (does domain age match claimed company age and registry records?) and as a denominator for history-length-dependent signals.

**Adverse media is the most size-biased signal in your framework.** Coverage volume is a function of prominence, not risk. A Fortune 500 will always generate more adverse hits than a fifteen-person vendor at any level of actual security performance. **If you score raw adverse-media count, you have built a company-fame detector.** Required corrections: normalize to adverse *share* (adverse mentions ÷ total mentions); enforce an entity-resolution confidence threshold (name collisions are the leading cause of false findings against small vendors); filter to security/privacy/fraud categories only; tier sources; require two independent sources; decay at 12 months; and treat low adverse media in under-covered non-English markets as an artifact, not a clean record.

**Observability weighting for all absence-of-evidence signals.** Breach history, enforcement, investigations, adverse media and regulatory disclosures are all filtered by size, listing status, jurisdiction and sector. Weight *absence* by `P(we would have observed it | it happened)`. Otherwise you systematically reward opacity — your best scores go to the vendors you can see least. Your Confidence axis is the natural home for this and is the reason your architecture can solve it and single-axis models cannot.

---

## 6. Unintended consequences of the current design

Ranked by how likely they are to be actively biting you today.

| # | Consequence | Mechanism | Fix |
|---|---|---|---|
| 1 | **Hygiene trivia outranks active exploitation** | No category weights + linear summation of correlated findings | §4.3 diminishing returns + widened ladder |
| 2 | **Large vendors penalized for being large** | Linear Frequency multiplier | §4.2 concave density-based frequency |
| 3 | **Multi-tenant SaaS vendors bottom out** | Per-tenant subdomains × linear frequency | §4.2 tenant-pattern detection |
| 4 | **Opacity is rewarded** | The Ghost suppresses scores that would be bad | §3.4 adverse "Insufficient Evidence" state |
| 5 | **Ungoverned reweighting on every release** | Emergent category weight = detection inventory | §4.3 explicit versioned severity table |
| 6 | **No discrimination among your worst vendors** | Floor at 0, three Criticals saturate | §4.1 retain unclamped raw score |
| 7 | **Small cloud-hosted vendors outscore banks** | Platform-provisioned hygiene credited to the vendor | §5.1 provisioning discount |
| 8 | **Mitigation becomes score laundering** | ×0.6 with no TTL, no artifact requirement, no audit trail | §3.5 classed mitigation with expiry |
| 9 | **Scores start tracking vendor sales capacity** | "Human-approved" discretion channel favours vendors with account teams | §3.5 artifact-based evidence requirement |
| 10 | **Risk acceptance corrupts the instrument** | Your appetite modifies their measured posture | §3.5 acceptance ×1.0, tracked separately |
| 11 | **One root cause counted four times** | TLS 1.0 → ciphers → PFS → AEAD; KEV → CVE → CVSS → EPSS | §4.4 deduplication rules |
| 12 | **Tiny vendors publish as 100** | No denominator; no evidence-volume component in Confidence | §3.1, §3.4 ceiling ramp |
| 13 | **Waiting out findings** | *Not present* — your no-decay-on-ongoing rule closes this | Keep as-is |

**Explicit gaming surface.** Assume vendors will read your methodology, because under the transparency principle you must publish it. Under the current design, the profitable strategies are: reduce scannable surface; contest coverage to fall below 40%; deploy the cheap hygiene items that carry the most points per hour of work regardless of risk; and lobby for mitigation approvals. Under the revised design, the profitable strategies become: remediate high-severity findings fast; increase scannable transparency to lift the confidence ceiling; and earn diligence credits. That is the correct incentive gradient, and getting it right is arguably worth more than the accuracy improvement.

---

## 7. Migration plan

Ordered by impact-to-effort. Items 1–4 are the ones that change rankings.

1. **Add diminishing-returns aggregation within category** (λ = 0.7). One function. Fixes the #1 inversion without abandoning your no-category-weights philosophy.
2. **Replace linear Frequency with the concave density form**, and add multi-tenant detection. Fixes the size bias.
3. **Move the ~10 low-base-rate signals from penalty to diligence credit** — DNSSEC, CAA, security.txt, VDP, trust page, security contact, ISO, SOC, regulatory disclosures, registry lock.
4. **Add gates.** KEV past due on internet-facing auth asset; dissolved entity; no TLS on data-bearing endpoint.
5. **Widen the severity ladder** to 50/20/6/1.5 and route Informational into Confidence.
6. **Build the versioned cohort severity table** for the handful of signals where it matters most: DMARC, TLS obligation, ISO/SOC expectation, VDP footprint scaling.
7. **Replace the Ghost cliff with the ceiling ramp**, and make Insufficient Evidence an explicitly adverse state.
8. **Class the mitigation multiplier**, add TTLs and artifact requirements, and separate risk acceptance out of posture entirely.
9. **Specify decay half-lives by event class**, and gate full decay on remediation evidence with a 40% floor.
10. **Add the Criticality Tier dimension** and the action matrix.
11. **Make Confidence risk-weighted**, and add an evidence-volume component so tiny footprints cannot reach maximum confidence on coverage ratio alone.
12. **Implement root-cause deduplication** (§4.4).

---

## 8. Validation protocol

### 8.1 The test that will tell you the most

> **Ablate all posture signals. Score your vendors using firmographics alone. Compare AUC against the full model.**

If firmographics-only performs close to the full model, you have built a size-and-sector classifier wearing a security costume. Given the linear Frequency multiplier in your current design, I would expect this test to be uncomfortable today — that is precisely why it is worth running before you change anything, so you have a baseline to demonstrate improvement against.

Run the mirror test too: posture-only versus full model. If cohort adjustment adds nothing measurable, drop it and keep the simpler system.

### 8.2 Backtesting

Externally observable signals do carry real predictive information — Liu et al. demonstrated that <cite index="20-1">cyber security incidents can be predicted from externally observable properties of an organization's network, using 258 externally measurable features across two categories — mismanagement symptoms such as misconfigured DNS or BGP, and malicious activity time series including spam, phishing, and scanning</cite>, with <cite index="26-1">mismanagement features ranking as the most important feature class, and dynamic features outperforming static ones</cite>. That last finding is a direct endorsement of your no-decay-on-ongoing rule and of dwell-time measurement over static snapshots.

Requirements:

- **Report discrimination within cohort, never pooled.** Pooled AUC is inflated by your model's ability to detect size, which correlates with disclosure probability. You would be measuring your own selection bias and reporting it as accuracy.
- **Report calibration, not just ranking.** A model that orders well but is badly calibrated produces risk-acceptance decisions that are systematically wrong in magnitude.
- **Monotonicity test.** A vendor that remediates a finding must never lose points. Verify this holds through the diminishing-returns transform, which is a common place to introduce a violation.
- **Stability test.** Re-cohorting must not silently move published scores. Version and diff.

### 8.3 Re-estimate base rates on your own portfolio

Every adoption figure in this document comes from internet-wide domain scans. Your vendor portfolio is a biased sample of that population — skewed toward B2B SaaS and toward companies that survived your procurement filter. Re-estimating cohort base rates on your own data is cheap, more accurate, and far more defensible when a vendor disputes a cohort-adjusted severity.

### 8.4 Accept the ceiling on external signals

Document it explicitly. <cite index="78-1">83% of privilege escalation incidents involved no CVE exploitation at all, and the high-profile cloud third-party campaigns were not CVE stories — they were OAuth token stories and missing-MFA stories</cite>. Several major recent third-party compromises occurred at organisations with unremarkable external posture.

Practical implication: for T1 vendors, cap how much confidence the external score carries and pair it with attestation or contractual evidence. Identity hygiene — MFA coverage, OAuth scope discipline, credential rotation — is where the third-party losses actually are, and it is nearly invisible to external scanning. If your programme has a strategic gap, that is it, not signal weighting.

---

## 9. Governance obligations you take on

Publishing scores about other companies carries duties. Mapped to your revised design:

| Principle | What it requires here |
|---|---|
| **Transparency** | Publish the severity table, cohort definitions, decay half-lives, frequency function, credit list, and gate conditions |
| **Dispute and appeal** | Cohort misassignment and attribution error will be your top two categories. <cite index="58-1">Disputed ratings should be notated as such until resolved</cite> |
| **Accuracy and validation** | Publish backtests. Label expert-set severities as expert judgment until calibrated — most of yours are, and that is fine if declared |
| **Model governance** | Notice before severity-table or cohort changes. Version everything. The March 2027 certificate weight increase (§5.4) should be announced in advance, not shipped silently |
| **Independence** | The mitigation-approval channel is where commercial pressure enters. Artifact requirements and audit trails are the control |
| **Confidentiality** | Do not publish exploitable detail in vendor-facing reports |

**One fairness note worth designing against deliberately.** Small vendors lose on certifications, governance documentation and formal programme evidence — all Tier-3 controls with real cost. But they **win on tempo**: <cite index="133-1">small organizations remove exposures fastest, taking 14–18 days on average</cite>, against 56 days at midmarket. Make sure your model has channels where a fifteen-person vendor can legitimately score well, or your posture score becomes a revenue league table with extra steps.

---

## 10. What this analysis cannot give you

1. **There is no published, peer-reviewed table of per-signal likelihood ratios by cohort.** The strongest validation work is vendor-sponsored: the Marsh McLennan analysis <cite index="14-1">compared Bitsight security performance data across 365,000 organizations against Marsh McLennan's proprietary incident and claims database from 2018–2021</cite> and found <cite index="17-1">fourteen analytics — the rating plus thirteen risk vectors — correlated with incidents across endpoint management, vulnerability management, secure communications, and user training</cite>. Meaningful evidence that external signals carry information; not a published weighting scheme; not independently reproducible. **Treat every severity value in §5 as an informed prior to be calibrated on your own outcomes, not as a finding.**

2. **Correlation is not uplift.** A low score correlates with breach partly because both are caused by low security investment. Adequate for prediction — which is what you are building — but do not let it become a claim that adding a header reduces breach probability. Figures like <cite index="19-1">organizations with ratings between 300 and 500 being 7.9x more likely to be targeted by ransomware</cite> are associational.

3. **Firmographics are weak individually and observed posture dominates.** <cite index="89-1">Single demographic factors such as industry, size, and region aren't enough to assess the risk posed by third parties; choosing a partner with a poor security posture can mean your organization is 360 times more likely to be exposed to security findings</cite>. This is the strongest argument *for* your instinct to keep benchmarking out of the arithmetic — and the reason I recommend bounding total cohort influence rather than making it a primary driver. Cap `Obligation × cohort-severity-uplift` at roughly 2.5× base, and total firmographic influence on posture at 20–25%.

4. **Breach data carries survivorship and disclosure bias throughout.** Every firmographic effect derived from it is partly an observability effect. That belongs as a permanent caveat in your model documentation, and it is exactly what your Confidence axis exists to handle.

---

## Sources

**Loss and frequency base rates**
Cyentia Institute, *Information Risk Insights Study* (IRIS 20/20, 2022, 2025) and *IRIS Ransomware*; Cyentia risk-data methodology

**External-signal predictive validity**
Liu, Sarabi, Zhang, Naghizadeh, Karir, Bailey & Liu, "Cloudy with a Chance of Breach: Forecasting Cyber Security Incidents," USENIX Security 2015 · Marsh McLennan Cyber Risk Analytics Center × Bitsight correlation study (2022), 365,000 organizations · RiskRecon/Cyentia *Internet Risk Surface* series · Bitsight published normalization methodology

**Vulnerability prioritization**
Jacobs, Romanosky, Edwards, Adjerid & Roytman, "Exploit Prediction Scoring System (EPSS)," *Digital Threats: Research and Practice* 2(3), 2021 · EPSS v4 release analysis, Empirical Security / FIRST, March 2025 · CISA Known Exploited Vulnerabilities Catalog

**Adoption base rates**
EasyDMARC *DMARC Adoption & Enforcement Report* 2025 and 2026 · Red Sift global DMARC analysis (73.3M domains, Dec 2025) · Valimail sector data · APNIC/Cloudflare DNSSEC measurement 2025–2026 · Wotschofsky DNSSEC survey (171M domains) · URIports and IoTDef security.txt studies · Hierlmeier & Sperl, "security.txt Revisited," DTRAP 2023 · Qualys SSL Pulse

**Standards and obligations**
RFC 8996 (BCP 195, March 2021) · RFC 9116 · PCI DSS v4.0 · NIST SP 800-52 Rev. 2 · CA/Browser Forum Ballots SC-081v3 and SC-085v2 · EU DORA and NIS2 · CISA BOD 18-01, BOD 20-01

**Threat landscape**
Verizon *DBIR* 2026 (22,000+ confirmed breaches, 145 countries) · Veracode *State of Software Security* 2025 and 2026 · Palo Alto Networks Unit 42 domain research · Intruder *Attack Surface Management Index* 2026

**Governance and organizational research**
U.S. Chamber of Commerce, *Principles for Fair and Accurate Security Ratings* (2017) · Angst, Block, D'Arcy & Kelley on symbolic vs. substantive IT security adoption, *MIS Quarterly* (2017) · Liu & Babar, systematic review of corporate cybersecurity risk and data breaches (2026)
