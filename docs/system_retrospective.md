# OSINT-Based Third-Party Risk Management Platform — System Retrospective

**Model:** `scoring.yaml` v5.4.0, `penalty_subtractive` · **Verified against the running system:** 2026-08-06
**Status:** 1,332 backend tests passing (2 documented `xfail`), frontend building clean.
**Companion:** `docs/metrics.md` — the per-metric arithmetic, every constant read from code.

---

## 1. Project Overview

The platform answers one procurement question from lawfully public data: *what can we establish
about this vendor without their cooperation, and how much of it can we stand behind?* A name or
domain goes in; an evidence-linked risk record comes out, every deduction traceable to a
hash-stamped receipt.

The problem is structural. Questionnaires measure what a vendor is willing to say about itself;
commercial ratings measure what a scanner sees but publish it as an opaque number. *ABN AMRO v
Bathurst Regional Council* established that publishing a rating conveys an implied representation
that it was formed on reasonable grounds — so a score that cannot be reconstructed is a legal
exposure, not merely a methodological weakness. Owning and defending the model is not a
differentiator; it is the only lawful way to publish a score.

Architecturally this is a **multi-attribute decision model with deliberately non-compensatory
aggregation across axes**. A weighted sum of everything lets a strong attribute buy back a weak one,
which is the wrong property here: a published trust page must never offset an expired production
certificate, and financial distress must never read as a security failing. Each axis aggregates
internally, with limits, and never across axes. Two rules follow, enforced in arithmetic rather than
convention: **missing data reduces Confidence, never Posture**, and **absence never subtracts on
Assurity**.

## 2. What I Built

**Evidence collection.** Twenty-eight collectors behind one uniform envelope, each failure-isolated
so a dead source cannot sink an assessment. `empty` is a first-class status distinct from `error`:
the source was reached and had nothing, so it reduces confidence and never touches risk. Raw
responses are written to an append-only, SHA-256-stamped store **before** scoring runs, because the
store is the legal artefact and must exist whether or not scoring succeeds. Entity resolution
refuses to guess a domain from a name, and confidence below 0.5 blocks rather than scoring low.

**Posture.** Severity is Critical 50, High 20, Medium 6, Low 1.5, Informational 0 — a Critical:Low
ratio of 33.3 : 1, widened deliberately. NIST SP 1326 modifiers apply per finding: age decay
(`0.5^(months/36)`, floor 0.15), frequency (`1 + 0.25(n−1)`, cap 2.0), evidenced mitigation (×0.6).
Within a category, penalties are ranked and discounted by `0.7^(rank−1)` — the tenth missing header
on a vendor already missing nine tells you almost nothing new, and charging it in full counts one
organisational fact ten times. Final posture is `100 − Σ min(category_penalty,100) / 2.86`, the
divisor **fixed by the model** rather than by how many categories answered:
`divisor(n) = n × (4/7)` holds maximum damage constant at 175 points regardless of category count.

**Independent axes.** Confidence (a conditional expectation ratio, §4); Business Stability
(age-anchored base plus evidenced adjustments); Assurity (`100 × σ(−1.2 + Σcredits − 0.8·gaps)`,
range 23–97); Continuity (five registry standings, disclosed and never scored — four registry bands
cannot support hundred-point precision); Longevity (a saturating maturity index); Lifecycle (Adizes
five-stage vocabulary, narrative only).

**Gates, not grades.** Sanctions, ambiguous entity, dissolution and active insolvency **block** — no
posture, routed to a human. A disqualified vendor publishing 60 clears a "≥ 50" procurement
threshold and gets onboarded by a rule nobody re-reads.

**Explainability enforced mechanically.** Every penalising band must carry a plain-English reason
and an action — what to do, what to ask, when to re-check, what would refute it. A band that deducts
points without a sentence **fails the configuration loader at startup**.

## 3. Research and Design Process

The design was corrected against research rather than fixed at the outset. Reviewing UpGuard,
SecurityScorecard, Black Kite, OneTrust and ProcessUnity surfaced one pattern: dimensions collapsed
into a number, weights defended by assertion, vendors penalised for evidence that does not exist
publicly. We took the subtractive method and rejected the opacity.

Theory did real work. NIST SP 1326 supplied decay-in-the-penalty. Stinchcombe's **liability of
newness** (1965) and US BLS establishment survival rates (~20% fail in year one, ~50% survive to
five years, ~33% to ten, declining hazard thereafter) set the *shape* of the Business Stability age
curve — a proxy for shape, explicitly not a prediction. Adizes supplied the lifecycle vocabulary.
The logistic function was chosen for Assurity because it is bounded without a cliff at either end:
the twentieth certification cannot buy what the second did, and no vendor is pinned at 0 or 100.

Source legality was checked against live terms, not summaries, excluding VirusTotal, SSL Labs and
Google Safe Browsing outright and leaving DFAT sanctions and the Modern Slavery Register held
pending written licence queries — held categories emit nothing rather than quietly scoring zero.
Where a source states no licence, that was recorded as an open question, not assumed permission.

The consequential rejections were subjective category weighting — deleted rather than asserted,
since no defensible weights could be derived from published evidence — and sector-based severity
promotion. `context-aware-vendor-risk-scoring-study.md` found signal importance should almost never
vary with a vendor's age, revenue or headcount; it should vary with measured exposure, and
consequences should vary with the buyer's engagement. Those are three different adjustments, and
conflating them is the central error context-adjustment introduces.

## 4. Technical Challenges Faced

**Hidden weighting.** "No category weights" was false: each category's effective weight equalled the
number of findings the scanner could generate times their severities, so twelve trivial signals
outranked one actively exploited vulnerability — a ranking inversion measured at 0.71 : 1. Widening
the ladder alone reached 1.39 : 1, rank decay alone 1.78 : 1; both together 3.06 : 1. Neither half
was sufficient, which is why they shipped together.

**Size bias and the flat tax.** Linear frequency turned posture into a footprint measurement: 900
hosts with 9 expired certificates (1% failure) scored worse than 4 hosts with 2 expired (50%).
Discrimination analysis then showed **19 of 26 signals could not order real vendors at all** — three
charged every vendor (~6.4 posture points before anything vendor-specific), sixteen charged none.
The three were footprint signals with no denominator, measuring estate size and calling it risk.
Both were fixed by exposure normalisation — penalties as rates against a measured, published
denominator.

**Separating posture from business risk.** Companies House maps liquidation, receivership and
administration onto `entity_inactive`, which was costing **20 points of technical security
posture**. A vendor entering administration does not thereby have worse TLS. Eleven penalising bands
moved to informational, the divisor was recalibrated 4.0 → 2.86, and Continuity became its own
disclosed-never-scored axis. The separation is now asserted end-to-end: each corpus vendor is scored
with and without financial evidence and the results must be identical.

**Confidence as a conditional expectation.** The naïve `found / all_possible` embeds a systematic
bias — a two-month-old startup has no five-year SOC 2 observation window and cannot acquire one by
trying harder. The implemented form is `Σw(expected ∧ found) / Σw(expected)`, so an unattainable
signal never enters the denominator. A veteran with only the 13 always-expected signals scores
108/211 = **51.2%**; a startup with the same 13 scores 100%. The differentiation comes from the
denominator, not a penalty table.

**Age escaping its bounds.** Age has two legitimate homes on the security side — Confidence and
attainability — because the context-aware study found no published evidence that founding date
predicts security posture. It escaped twice. A hard-coded table charged young vendors 6–15 posture
points in categories *where nothing had been observed*, breaking the requirement that stored
findings reconstruct the published penalty (receipts summing to zero while the card showed 88).
Separately, an **unknown** age band is mapped onto the *startup* threshold, so a vendor whose age we
cannot determine expects 108 weight rather than 211 — not knowing something makes the score easier
to earn. The first is removed; the second is open.

**Age is purchasable.** An aged domain costs a few hundred dollars at auction; a register inception
date does not. Evidence strength discounts operating history by source — registers 1.00, Wikidata
0.90, firmographics 0.80, RDAP 0.60 — one-directionally, so a weak source can never buy assurance.
The maturity index `ln(1+y)/ln(26)` saturates at 25 years: year two of trading is enormously
informative, year forty is not.

**The audit-budget tax.** Assurance was originally expressed by *subtracting* for its absence —
`cert_posture.none_claimed` cost 8 points and fired on five of five corpus vendors, a tax on audit
budget falling hardest on the small suppliers this product exists to assess fairly. Assurity
inverted it: absence never subtracts (rejected at load time), and the only subtraction is a
compliance gap — a vendor asserting a framework and observably failing a control inside its scope.

**OSINT reliability.** A corporate-suffix regex lacked a closing word boundary, so "Microsoft
Corporation" normalised to "microsoft oration". A status mapper matched the participle but not the
noun, classifying a company in *"Liquidation"* as a lapsed registration — a `watch` — rather than
`entity_inactive`, which drives a hard gate. When Vanta was trialled, EDGAR matched it to a
different US-listed company, attributing a stranger's financials. Confidence *search failures*
stayed in the denominator while leaving the numerator, so a collector outage scored identically to
the vendor lacking the control — the two-axis confusion reappearing inside the confidence axis.

**Configuration drift.** Age base scores existed in four inconsistent versions — model file,
hard-coded copy in `longevity.py`, tests, and `SYSTEM_EXPLANATION.md`. The YAML block was **inert**:
the runtime never loaded it, so `docs/methodology.md` documented values that never executed.
Confidence changed meaning without a version bump, moving every published confidence while postures
stayed put. The Business Stability signal set, duplicated across two modules for independence, grew
on one side only and acquired five signals the model declares nowhere.

**Tests that could not fail for the right reason**, and a system fragile to small edits. A
regression suite asserted a configuration API that has never existed; others asserted
`hasattr(x, '__annotations__')`, true of every Python class. Separately, an orphaned reason entry
made **the model file fail to load**, so nothing could score, and an endpoint pasted mid-function
orphaned that function's docstring into bare code, so **the API would not import**. Two further
endpoints were dead on arrival and the scheduled monitor crashed on every sweep.

## 5. What I Learned

**Legal defensibility is a standard, not a preference.** Every score must be *reconstructible* from
stored evidence, not explainable in principle. That single requirement drove the append-only store,
the hash-stamped receipts and the refusal to publish anything a reader cannot trace.

**Judgement must be labelled as judgement.** The severity ladder, aggregation decay and divisor are
expert judgement, not calibrated against outcomes — calibration needs outcome labels the project
does not have. A number presented as more certain than its inputs warrant is exactly the defect that
makes ratings legally vulnerable.

**One-size-fits-all scoring fails procurement.** Security needs control detail, procurement needs
viability, legal needs compliance. The answer is not a better single number but giving each
stakeholder the dimension their decision turns on.

**Public OSINT is materially less reliable than commercial datasets imply.** Of a typical
27-criterion questionnaire, roughly seven items are externally observable, about ten partly
observable by proxy, and the rest — access controls, monitoring, insurance, change management,
contract terms — invisible to any lawful external observer. Contradiction-flagging against a
vendor's own claims, not replacement of the questionnaire, is the realistic product.

**Peer comparison must never touch the number it interprets**, or a vendor improves their score by
choosing worse peers. Honest statistics beat flattering ones: percentiles rounded to the step the
sample can express, thin cohorts refused rather than published.

**An inert feature is indistinguishable from a working one until you check.** The age-differentiation
subsystem is fully built and does nothing in production because a `hasattr` guard silently never
fires. Nothing errored; logs read `Age band: unknown` while scores kept publishing.

**Research over intuition.** The consequential changes came from published research — the
context-aware study, the methodology evaluation on hidden weighting, the discrimination analysis on
flat-tax signals. Research-backed changes survived subsequent validation; intuition-based ones did
not.

## 6. What I Would Change With Hindsight

**Separate business and security metrics on day one** — the largest single source of rework.
**Exposure normalisation and explicit capping from the start**, since both were retrofits after
ranking inversions were already in published scores.

**One source of truth per constant, enforced at load.** The loader already rejects an unexplained
penalty; that discipline should have covered the Business Stability tables. Config drift was a
validation gap, not a documentation problem. `longevity.py` now reads `scoring.yaml`, so the base
curve is 70/75/80/85/100/60 rather than an inert declaration beside a hidden one — though the
going-concern penalty (25) is still hard-coded outside the model file.

**Fix the age band before calibrating anything downstream of it.** Nothing depending on vendor age
is tunable while every production vendor reports `unknown`:

```
Atlassian, live run, evidence weight found = 75
  age_band = unknown  →  75/108 = 69.4%  →  published, band Low
  age_band = veteran  →  75/211 = 35.5%  →  REFUSED (Ghost, no score at all)
```

The leniency is currently the only reason that vendor publishes. In the same run, 13 signals worth
144 weight — breach history, KEV, CVEs, regulator actions — were **collected and then discarded** as
"not expected at this age band". Both directions are wrong at once.

**Version the meaning of a metric, not just its value.** Confidence changed definition without a
version bump; the model's own rules require a notice period and side-by-side publication for exactly
that, as the log-odds transform was given.

**Test behaviour, not shape, and run the whole system more often.** The strongest guard written in
this cycle scores each corpus vendor with and without financial evidence and demands identical
output — worth more than the dozen constant-inspecting tests it replaced. Both fatal defects above
would have surfaced on any single execution.

**Earlier validation with procurement professionals, UI designed alongside the model, and more
calibration data** — all retrofits; the last would have surfaced the entity-resolution and
normalisation defects far sooner.

### Open items

1. **Age band is `unknown` for every production vendor** — dead `hasattr` guard in `pipeline.py`.
2. **`unknown` age is scored as *startup***, halving the evidence bar (108 vs 211); unknown *size*
   is likewise treated as smallest.
3. **Found-but-unexpected signals are discarded** rather than credited.
4. **A clean startup scores 40 / "impaired"** — improved from 20 / "ceased" now the YAML curve is
   live, but still a base-rate prior in vocabulary reserved for an observed outcome.
5. **Four declared financial penalties are not wired** (`voluntary_arrangement`,
   `declining_profitability`, `high_customer_concentration`, `no_recent_funding_18_months`).
6. **`calculate_from_profile` passes `sector` into the `jurisdiction` parameter**, dropping
   `sec_filing` from the denominator for medium+ vendors.
7. Several `age_risk_factors` inputs are placeholders, not collector-fed.
8. `SYSTEM_EXPLANATION.md` documents an age-score table matching neither code nor model.

## 7. Future Work

In dependency order: **fix the age pipeline first**, since several later items are uncalibratable
until it lands. **Continuous monitoring** exists as a by-tier scheduled sweep and needs the age fix
plus real operational hours. **Additional collectors** should prioritise signals that can *order*
vendors, given 19 of 26 existing signals could not. **Financial intelligence for private companies**
is the largest coverage gap; Altman Z-score, cash burn and runway stay deliberately out of scope as
credit-rating territory. **Limited vendor questionnaires** would cover what public data provably
cannot. **Industry benchmarking** requires a peer pool deep enough that cohorts populate without
widening. **AI-assisted explanation** is scaffolded as a read-only layer citing the hashes it was
built from. **Predictive analytics** warrants caution: without outcome data it encodes our
assumptions as forecasts — which is why the highest-value item is **continuous score validation**
against real incidents, failures and disputes, the only feedback that can establish whether this
calibration is correct, and the precondition for the outcome labels the severity ladder currently
defers.

## 8. Conclusion

The platform began as a security scoring exercise and became an evidence-based decision support
system, largely by discovering where a single score was lying. Procurement decisions require several
perspectives — technical posture, evidence confidence, financial stability, independent assurance,
operational continuity — each answering a different question by a different method, and each
degraded by being averaged with the others. A vendor can hold excellent controls while being
financially fragile. Collapsing those into one number does not simplify the decision; it removes the
information the decision depends on.

The second conclusion is less comfortable and more useful. Every principle this system holds was
violated at some point by a reasonable-looking change: age reached the arithmetic through a helper
table, absence of evidence became a deduction, a single-source-of-truth constant acquired three
rivals, and a disclosure obligation survived only as a comment its own test was satisfied by. None
were failures of intent; they were failures of enforcement. What worked was making the system
refuse — to load an unexplained penalty, to grade a gated vendor, to publish a posture we cannot
stand behind. What did not work was anything relying on a person remembering.

The remaining limitations are stated rather than minimised: financial coverage is thin for private
companies, OSINT quality is uneven, the age subsystem is currently inert, and no scoring decision
has yet been validated against a real-world outcome. They are tractable engineering problems on a
defensible foundation — a materially better position than a system that scores confidently and
cannot explain why.
