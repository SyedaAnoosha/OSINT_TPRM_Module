# Critical Comparison: Your Model vs. UpGuard-Style Spec

A brutally honest, dimension-by-dimension comparison. Neither model is "right" — but each has structural gaps the other doesn't, and this document names them.

---

## Executive Summary

Your model is **architecturally more sophisticated** than the UpGuard spec in almost every dimension that matters for defensibility, epistemic honesty, and legal compliance. The UpGuard spec is **operationally simpler** and **more implementable in a weekend**, which is its explicit goal. But "simpler" and "better" are different claims, and on several concrete points your model has genuine gaps the UpGuard spec handles that you don't, and vice versa.

---

## 1. Scale & Direction — A Fundamental Fork

| Dimension | Your Model | UpGuard Spec |
|---|---|---|
| **Scale** | 0–100 (risk) | 0–950 (score/health) |
| **Direction** | 0 = lowest risk, 100 = highest risk | 950 = best, 0 = worst |
| **Grade system** | No letter grades — quadrant labels instead | A/B/C/D/F letter grades |

### Critique of yours
- Your refusal to use letter grades is **philosophically principled but commercially punishing**. Every competitor (UpGuard, Bitsight, SecurityScorecard) uses letter grades. A procurement officer who gets a quadrant label ("The Ghost") instead of a letter grade has to *learn your system* before they can act on it. You've traded usability for epistemic honesty, and you should know that trade-off exists.
- The quadrant system ("Evidenced clean" / "The Ghost" / "Verified exposure" / "Uncorroborated signal") is **genuinely better at communicating uncertainty** than a letter grade. But it only works if the consumer is trained. For a PoC, this may be over-engineered.

### Critique of theirs
- The 0–950 scale is **arbitrary ceiling theatre**. Why 950 and not 1000? UpGuard chose 950 so "no vendor is perfect," which is a design aesthetic, not a measurement principle. Your 0–100 is at least a conventional, interpretable range.
- Letter grades create a **false equivalence with academic grading** that masks huge differences within a band. An 801 and a 950 are both "A" — a 149-point gap hidden behind one letter.

### Verdict
**Neither wins cleanly.** Your model is more honest; theirs is more usable. You should consider offering letter grades *as a presentation layer on top of your quadrant system* — not replacing the quadrant, but supplementing it. The UpGuard spec should worry about the false precision of "Grade A" when evidence is thin.

---

## 2. Scoring Mechanics — Subtractive vs. Additive Weighted Mean

| Dimension | Your Model | UpGuard Spec |
|---|---|---|
| **Approach** | Weighted mean of signal scores (additive/aggregative) | Start at 950, subtract penalties (subtractive) |
| **Signal scoring** | Per-signal bands (e.g. DMARC absent → 100) | Binary pass/fail at a severity tier |
| **Granularity** | Continuous signal-level scores (0–100 each) | Four fixed penalties (-10, -30, -70, -150) |

### Critique of yours
- Your weighted-mean approach is **academically sounder** but creates a **compensatory problem you then have to fix with a knockout floor**. The UpGuard spec avoids this: penalties simply stack, and a critical finding always costs -150 regardless of what else is good. Your architecture *creates* a problem (weighted mean diluting severity) and then *patches* it (knockout floor). The UpGuard spec never has the problem in the first place.
- Your signal bands (DMARC: absent → 100, p=none → 70, p=quarantine → 35, p=reject → 0) are **far more granular and defensible** than UpGuard's binary pass/fail. Real security postures are gradients, not binaries. This is a genuine strength.

### Critique of theirs
- Four fixed penalties (-10/-30/-70/-150) are **deliberately blunt**. UpGuard admits this: "four fixed severity penalties instead of UpGuard's continuous, calibrated deductions — easier to defend and tune, slightly blunter." But "slightly" is generous — a vendor with DMARC `p=none` (monitoring only) and a vendor with no DMARC at all get the same penalty under this model. **That is a real measurement error, not a simplification.**
- Binary pass/fail **cannot represent partial compliance**, which is the reality of most security controls. Your graduated bands are superior here and the UpGuard spec sacrifices real information for implementation speed.

### Verdict
**Your signal-level granularity is better.** Their subtractive simplicity is easier to implement but loses real information. However, your need for a knockout floor to fix compensatory averaging is a **design smell** — the UpGuard approach's stacking penalties naturally prevent the problem your floor exists to solve.

---

## 3. Confidence — Where You Genuinely Win

| Dimension | Your Model | UpGuard Spec |
|---|---|---|
| **Confidence** | Computed: `coverage × source_reliability × freshness`, per-subcategory, rolled up by weight | Simple: High/Medium/Low based on % of signals returning data |
| **Score refusal** | Refuses below confidence 0.4 | Never refuses — always emits a score |
| **Quadrant labelling** | Yes — "The Ghost" labels low-confidence-low-risk explicitly | No — a vendor with thin evidence just has "Low" confidence noted beside the score |

### Critique of yours
- Your **three-factor confidence formula** (coverage × reliability × freshness) is **genuinely superior**. The UpGuard spec counts how many of N planned signals returned data and calls that confidence. Yours also accounts for *how reliable* each source is and *how recent* the data is. A vendor whose only data is a 2-year-old GDELT hit and a current DNS check should have lower confidence than one with 10 fresh, high-reliability signals — your model captures this, theirs cannot.
- **Score refusal below 0.4 is the single strongest design choice in your entire model.** The UpGuard spec will always produce a number. A model that always produces a number *lies when it has nothing*. You say this explicitly, and you're right.
- **"The Ghost" quadrant** is a genuinely novel contribution. It names the exact failure mode that every other vendor-scoring platform silently permits: a vendor looks "low risk" because nobody has written about it.

### Critique of theirs
- Their confidence layer is **thinner but more implementable**. `signals_returned / signals_planned` is a number anyone can compute. Your `coverage × reliability × freshness` requires per-source reliability assignments and freshness calculations that add real complexity.
- They do publish which sources didn't respond — that's honest and practical. But they don't *structurally prevent* a thin-evidence score from being read as authoritative.

### Verdict
**You win this dimension decisively.** Their confidence is a footnote; yours is a load-bearing structural element. The UpGuard spec's §7 admits: "the first [confidence] is better than UpGuard's (it publishes evidence coverage rather than silently dropping unverifiable findings)." They're right about your advantage here.

---

## 4. Categories & Coverage — Where They Have Something You Don't

| Dimension | Your Model | UpGuard Spec |
|---|---|---|
| **Categories** | 9 scored + 3 held + 1 gate | 6 categories |
| **Category weighting** | Explicit percentage weights summing to 100 | No explicit weights — "emerges from signal count and severity" |
| **Open ports / Network scanning** | **Not collected** — Shodan/Censys on roadmap | Included: "Attack surface / network — Open ports, exposed services (databases, RDP, SMB)" |
| **IP/blocklist reputation** | Held — "no cleared source" | Included: "Reputation & exposure — Domain/IP on malware or phishing blocklists" |

### Critique of yours — the real gaps

> [!WARNING]
> **You are missing active network/attack-surface scanning entirely.** UpGuard's categories include "Attack surface / network" with open ports, exposed databases, exposed RDP/SMB. Your model has *no equivalent scored capability*. Your "Digital Footprint & Assets" category looks at Certificate Transparency data (certs issued, not hosts live — you say this yourself). **CT tells you a certificate was issued for `staging.vendor.com`. It does not tell you that port 3389 (RDP) is open on that host.** These are fundamentally different signals, and the UpGuard spec scores the one you can't see.

> [!WARNING]
> **You have no blocklist/reputation check.** UpGuard scores whether a vendor's domain/IP appears on malware or phishing blocklists. Your `ip_reputation` subcategory is `status: held` with "no cleared source." **A vendor whose domain is actively on a phishing blocklist is a critical finding that your model cannot detect.** This is not a theoretical gap — it is a real, actionable signal that goes unscored.

These two gaps mean that the UpGuard spec covers a category of **actively dangerous, confirmable, right-now findings** (exposed RDP, blocklisted IP, open database ports) that your model structurally cannot see. Your CT-based "Digital Footprint" is a pale proxy for what they call "Attack Surface."

### Critique of theirs
- "Weighting emerges from how many signals sit in each category" is **an abdication of explicit weighting, not a feature.** If you put 8 signals in TLS and 2 in DNS, TLS implicitly gets 4× the weight — but you never stated or defended that ratio. Your explicit weights with a stated derivation are far more defensible.
- Six categories is too few for a TPRM model. They have no "Supply Chain & Dependency" (your strongest unique category), no "Vendor Transparency & Governance," and no "Business & Financial Stability." **Their model has zero visibility into fourth-party risk, which is a CPS 230 regulated obligation.**

### Verdict
**Mixed.** They beat you on real-time attack surface (ports, blocklists). You beat them on breadth, explicit weighting, supply chain, and governance. Your gaps are *operationally dangerous* (missing a blocklisted domain is a real risk); their gaps are *strategically dangerous* (missing fourth-party concentration is a regulatory risk).

---

## 5. Overrides — Both Have Them, Yours Are Better Designed

| Dimension | Your Model | UpGuard Spec |
|---|---|---|
| **Sanctions** | Gate — blocks score entirely, adjudication queue, no number emitted | Override — forces grade to F |
| **Critical findings** | Knockout floor — `max(risk, moderate_lower)`, requires attribution confidence ≥ 0.7, must name cause | No equivalent — stacking penalties handle this implicitly |
| **Multi-asset** | Not addressed explicitly | Weakest-link `min()` across assets |

### Critique of yours
- Your sanctions gate is **legally superior**. The UpGuard spec sets sanctions to "Grade F." Yours emits *nothing* and routes to adjudication. Under the Autonomous Sanctions Act, the difference matters: their approach has a machine making a criminal accusation (grade F = "do not engage"); yours has a machine surfacing a possible match for human review. **Your design is correct for strict-liability regimes.**
- Your knockout floor has **three constraints** (attribution confidence, named cause, floors-not-sets) that prevent it from firing incorrectly. The UpGuard spec's equivalent is simpler but has no guard rails: "A direct sanctions / watchlist match, or a confirmed active breach or ransomware event, forces the grade to F regardless of the number." How do they confirm a breach is "active"? How do they attribute it to the right entity? These questions are unaddressed.

> [!IMPORTANT]
> **You have no multi-asset weakest-link rule.** UpGuard's §4 point 6: "If a vendor has several domains or IPs, the vendor score is the lowest asset score, not the average." Your model does not address the case where a vendor has multiple domains. If vendor X has `main.com` (clean) and `legacy.vendor.com` (terrible), your model has no stated rule for aggregation. **This is a real gap** — vendors typically have many domains, and averaging across them would hide a weak subsidiary.

### Critique of theirs
- "Forces the grade to F" for a sanctions match is **too aggressive if the match is fuzzy.** Their spec says "confirmed" but offers no mechanism for confirmation or false-positive handling. Your recall-tuned gate with adjudication queue is more operationally realistic.
- Their "confirmed active breach" override assumes the system can *know* a breach is active and confirmed. With OSINT sources alone, this is often unknowable. Your model's requirement for "confident attribution (entity-confidence ≥ 0.7)" is the right guard rail that their spec lacks.

### Verdict
**Your sanctions gate and knockout floor are better designed.** Their multi-asset weakest-link rule is something you need and don't have.

---

## 6. Temporal Decay — You Have It, They Don't

| Dimension | Your Model | UpGuard Spec |
|---|---|---|
| **Finding age** | NIST SP 1326: `max(0.15, 0.5^(months/36))` — 3-year half-life, floors at 0.15 | **No decay model** |
| **Frequency** | `1 + 0.25 × (n-1)`, capped at 2.0 | No frequency adjustment |
| **Mitigation credit** | ×0.6 where remediation is evidenced | No mitigation credit |

### Critique of yours
- Your NIST-anchored decay model is a **genuine, material advantage**. A 2015 breach and a 2026 breach should not count equally. The UpGuard spec penalises both identically: if an HIBP breach is found, the penalty is fixed by severity regardless of when it happened. **That is objectively wrong for risk assessment** — a remediated, 10-year-old breach is not the same risk as one disclosed last month.
- The floor at 0.15 (never fully irrelevant) is a good design choice. A breach never reaches zero — it always leaves some residual signal.
- Frequency scaling (three breaches = pattern, not 3× one breach) is **thoughtful and defensible**.

### Critique of theirs
- **No decay is a serious omission.** In a worked example: if a vendor had a breach in 2013 (fully remediated, company restructured, new CISO, new architecture), the UpGuard spec penalises it at full severity. **That is not risk assessment; that is record-keeping.**
- No mitigation credit means a vendor who *fixes* a vulnerability gets no score improvement until the next scan detects the fix. Your 0.6 multiplier for evidenced remediation is more operationally realistic.

### Verdict
**You win this dimension completely.** The UpGuard spec's lack of temporal decay is its single biggest methodological weakness.

---

## 7. Size Normalization — Your Surgical Approach vs. Their Silence

| Dimension | Your Model | UpGuard Spec |
|---|---|---|
| **Approach** | Log-damped, applied *only* to count-type signals; policy signals excluded | **Not addressed** |

### Critique of yours
- Your distinction between count-type signals (subdomains, GDELT volume) and policy-type signals (DMARC, TLS config) is **genuinely insightful**. A 50,000-employee company has more subdomains than a 10-person startup, but both have exactly one DMARC record. Normalizing the DMARC check by company size would be a measurement error. The UpGuard spec doesn't address this at all.

### Critique of theirs
- Silence on size normalization means **large vendors will systematically score worse** under the UpGuard spec, simply because they have more infrastructure to scan and more signals to fail on. This is the exact bias your §7.3 names.

### Verdict
**You win.** They don't even attempt it.

---

## 8. Transparency & Defensibility

| Dimension | Your Model | UpGuard Spec |
|---|---|---|
| **Evidence traceability** | Every score reconstructible from stored evidence (legal requirement — Finding A) | No evidence store mentioned |
| **Legal basis** | Australian law citations (ABN AMRO, Autonomous Sanctions Act, Privacy Act, CPS 230) | None |
| **Weight derivation** | Four-anchor stack: NIST structure → legal non-compensatory rules → benchmark cross-check → sensitivity-bounded default | "No per-signal point tuning" — four fixed numbers |
| **Self-critique** | §7 Limitations, §9 Open Items, explicit bias disclosure | §7 "Be honest about what this simplifies" (2 paragraphs) |

### Critique of yours
- Your legal grounding is **appropriate for an Australian context** but may be over-engineered for a PoC. The UpGuard spec is explicitly "built to implement in a PoC, not to replicate the full platform." If the goal is a working demo, your 690-line methodology document may be producing diminishing returns.
- Your self-critique (§7, §9) is **remarkably honest** — 13 open items, named biases, structural limits. This is a strength for credibility but a weakness for confidence: a reader might wonder if the model is ready to ship.

### Critique of theirs
- **No evidence store is a serious gap for any production use.** If a vendor disputes a score, the UpGuard spec has no mechanism to show *why* the score is what it is beyond "here are the findings." Your immutable evidence store, written before scoring, is the correct architecture for any system that publishes ratings about real companies.
- Their self-critique is **too brief**. "Four fixed severity penalties instead of UpGuard's continuous, calibrated deductions" and "weakest-link min() instead of Gaussian mean" are honest simplifications, but they don't address the deeper problems: no decay, no size normalization, no evidence retention, no multi-source reliability weighting.

### Verdict
**You win on defensibility.** They win on "shippability." These are different goals.

---

## 9. What You Should Take From the UpGuard Spec

> [!IMPORTANT]
> These are concrete gaps in your model that the UpGuard spec handles and you currently don't.

| Gap | UpGuard Has | Your Status | Recommended Action |
|---|---|---|---|
| **Active network scanning** (open ports, exposed RDP/SMB/DB) | Yes — "Attack surface / network" category | `ip_reputation: held` — "no cleared source" | **Prioritize clearing Shodan/Censys or an equivalent.** Without this, your "Digital Footprint" category is measuring certificate issuance, not actual exposure. |
| **Blocklist/reputation checks** | Yes — "Domain/IP on malware or phishing blocklists" | `ip_reputation: held` | Same — this is a critical-severity signal (actively dangerous, confirmable) that you cannot detect. |
| **Multi-asset aggregation** | Weakest-link `min()` across domains/IPs | **Not addressed** | **Add a stated rule.** Most vendors have multiple domains. Your model needs to say what happens when `vendor-main.com` scores 25 and `vendor-legacy.io` scores 78. |
| **Informational tier** (cannot verify → record, don't score) | Explicit `Informational: 0 penalty` tier | Implicit via confidence ("missing data reduces confidence") | Consider making this explicit in your signal taxonomy — some findings are worth recording but genuinely unscorable, and an explicit "Informational" status would make that clearer. |
| **Simplicity of implementation** | Pseudocode fits on one page | Requires ~285 lines of YAML + ~690 lines of methodology + ~254 lines of framework doc | Not a model gap, but a real concern: **can a PoC team implement your model in the time available?** |

---

## 10. What They Should Take From You (Your Genuine Advantages)

| Your Advantage | UpGuard Spec Lacks | Why It Matters |
|---|---|---|
| **Two-axis scoring** (risk + confidence, never collapsed) | One number + a footnoted confidence band | A score without confidence is a lie when evidence is thin |
| **Score refusal** below confidence 0.4 | Always emits a score | Prevents the model from lying about vendors it knows nothing about |
| **"The Ghost" quadrant** | No equivalent | Names the exact failure mode: "looks clean because we found nothing" |
| **Temporal decay** (NIST SP 1326) | No decay at all | A 2013 breach ≠ a 2026 breach |
| **Frequency scaling** | Not addressed | Three breaches = pattern signal |
| **Mitigation credit** | Not addressed | Fixing a vulnerability should improve the score |
| **Sanctions as gate, not grade** | Forces "Grade F" | Correct for strict-liability regimes; prevents machine-made criminal accusations |
| **Knockout floor with attribution guard** | No guard rails on override | Prevents flooring the wrong company on a fuzzy match |
| **Supply chain / fourth-party** category | Not present | CPS 230 ¶48 regulatory obligation |
| **Business & Financial Stability** | Not present | Viability risk is real TPRM |
| **Vendor Transparency & Governance** | Not present | Self-reported but still informative |
| **Size normalization** (surgical, count-type only) | Not addressed | Prevents large-vendor bias |
| **Evidence store** (immutable, pre-scoring) | Not mentioned | Required for score disputes and legal defensibility |
| **Explicit weight derivation** | Emergent from signal count | Transparent and challengeable |
| **NIST/legal anchoring** | None cited | "NIST says so" beats "we thought so" |

---

## 11. Bottom Line — The Honest Assessment

**Your model is a research-grade, legally-grounded, epistemically honest scoring framework that would survive a regulatory review.** It handles uncertainty better than any commercial platform's published methodology, and it's self-aware about its limitations in ways that build credibility.

**The UpGuard spec is a pragmatic, implementable simplification designed to get a PoC running.** It sacrifices real measurement quality (no decay, binary pass/fail, no confidence refusal) for speed-to-demo.

**Where you need to worry:**
1. **You cannot see active exposure** (open ports, blocklisted IPs). The UpGuard spec can. This is not a philosophical gap — it's a blind spot for the most dangerous, most actionable findings.
2. **You have no multi-asset rule.** Add one.
3. **Your model may be too complex to implement in a PoC timeframe.** The UpGuard spec's pseudocode is 20 lines. Yours requires implementing a 285-line YAML configuration engine, multi-factor confidence, knockout floors with attribution guards, and size-selective normalization. Be honest about whether the team can ship this.
4. **You have no vendor dispute mechanism.** Open item 12 in your own document. The UpGuard spec doesn't have one either, but you *know* you need one and haven't built it.

**Where you should be confident:**
Your confidence model, your temporal decay, your sanctions gate, your supply-chain category, and your evidence store are all *genuinely better* than the UpGuard spec's equivalents — and better than what most commercial platforms publish. These aren't marginal improvements; they're structural advantages that make your scores more honest and more defensible.

> [!TIP]
> The ask was to "align with" the UpGuard spec. The three concrete alignment actions are: **(1)** add a multi-asset weakest-link rule, **(2)** prioritize clearing a source for active network/port scanning and blocklist checks, and **(3)** consider adding an explicit "Informational" signal status for findings you record but don't score. Everything else is a case where your model is already more sophisticated — alignment would be regression.
