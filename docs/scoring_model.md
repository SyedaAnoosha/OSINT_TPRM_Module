# Scoring Model — v1 (`scoring.yaml` v5.2.0, penalty-based posture)

**OSINT TPRM vendor scoring — the model in brief.**

> **Direction, stated once and never inverted: `100 = strongest posture, 0 = weakest`. A penalty is *subtracted* for each issue found.**

*The model is the deliverable. It lives in machine-readable form in [`scoring.yaml`](../scoring.yaml) — a file a
non-engineer can read in a room with a client. This page is the guided summary; the full legal and epistemic
defence is [`methodology.md`](methodology.md) §5, and the one-level-deeper tour is [`scoring_framework.md`](scoring_framework.md).*

---

## The model in one line

Take a vendor name or domain, collect lawfully-public evidence, and **start every vendor at 100**. For each
issue found, **subtract a penalty sized by severity**. A category's posture is 100 minus its own penalties; the
**overall posture** is 100 minus the total penalty spread over a **fixed divisor**, published with a letter
**grade (A–F)** and a plain-English sentence for every deduction. Reported *beside* it — never mixed in — are
**confidence** (how much of the planned evidence actually came back, §7) and **assurity** (how much independent
assurance the vendor carries, §8). Two things sit outside the arithmetic: a **sanctions gate** that blocks the
score, and a **critical ceiling** that stops one directly-observed live critical from being diluted by good
hygiene elsewhere.

The core difference from a single-grade platform: **we never collapse posture, confidence and assurity into one
figure.**

### The three axes, and the four readings beside them

| | What it answers | Range | Who owns it |
|:--|:--|:--|:--|
| **Posture** (§1–6) | How strong does this vendor look from outside? | 0–100 · A–F | Ours to measure |
| **Confidence** (§7) | How much of the vendor could we actually see? | 0–1 · High/Med/Low | Ours to measure |
| **Assurity** (§8) | Has anyone independent checked? | 0–100 | Ours to measure |
| Compliance gap (§8.1) | Are the vendor's own claims reliable? | a list, with citations | Observed |
| Inherent → residual (§9) | How much do *we* stand to lose? | 4 tiers → 16 cells | **The buyer declares it** |
| Peer placement (§10) | Am I typical? | quartile / percentile, with `n` | Computed from the book |
| Expectation gap (§10.1) | Am I what my peer group predicts? | posture − E[posture ∣ cohort] | Computed from the book |
| Target maturity (§7.2) | Am I adequate? | met / applicable controls | Published standards |

Everything below the three axes **interprets** the posture. None of it can move it.

---

## Why penalty-based (and why we changed)

The earlier model needed a defensible *weight* for every category — *why is Cyber Hygiene 31%?* — a question with
no authoritative answer (no standard publishes vendor-risk weights). A penalty model **deletes that problem**: a
category's influence **emerges** from how many issues it has and how bad they are. One lever — four severity
numbers — and every number maps to a plain sentence a client can challenge. It is inspired by UpGuard's subtractive
method but is **our own**: our 0–100 scale (not 950), our five scoring categories, and our three differentiators (below)
that a pure technical rating does not have.

---

## 1 · Severity penalties — the only points table

Every signal is a **pass** (no penalty) or a fail at exactly one severity. Four fixed penalties drive everything —
no per-signal point-tuning, no category-weight derivation to defend.

| Severity | Penalty | Assign when… |
|:--|--:|:--|
| **Critical** | **−40** | Actively dangerous & confirmable — expired production cert, unpatched KEV CVE, breach exposing passwords/cards, CVSS 9–10 |
| **High** | **−20** | Serious weakness — no DMARC, TLS 1.0/1.1, confirmed breach of personal data, CVSS 7–8.9 |
| **Medium** | **−8** | Meaningful gap — weak TLS, `p=none`, missing SPF, CVSS 4–6.9 |
| **Low** | **−3** | Minor hygiene — a missing security header, no DNSSEC, CVSS 0.1–3.9 |
| **Informational** | **0** | Recorded, **not** scored — unverifiable (unproven open port, unconfirmed media allegation) |

**All bands live in [`scoring.yaml`](../scoring.yaml), not in code** — the model must be arguable with a client
without a redeploy. Each finding is then adjusted by the NIST SP 1326 variables (§4) before it is subtracted.

---

## 2 · The grades

The overall posture (0–100) maps to a letter grade — a documented, client-tunable default (no authority publishes
vendor-risk cut-points).

| Posture | Grade | Meaning |
|:--|:--|:--|
| 85–100 | **A** | Robust posture, few or no external issues |
| 70–84 | **B** | Reasonable controls, some gaps |
| 50–69 | **C** | Poor controls, serious issues to address |
| 30–49 | **D** | Severe issues; should not handle sensitive data |
| 0–29 | **F** | Little to no basic external security investment |

Confidence runs **0–1** and is reported *beside* the grade, never mixed into it (§5).

---

## 3 · Categories and signals

**Five scoring categories and two context categories.** Each **signal** maps an observation to a severity (or
pass) in [`scoring.yaml`](../scoring.yaml) — **no category percentages**; a category's influence emerges from
the issues found in it, which is the whole point of a penalty model.

The keys below are the ones the engine uses and the scorecard renders, so a category name can be carried from
this page to a vendor's record and back.

### Scoring categories — *how exposed is this vendor to compromise?*

| # | Category | Engine key | Example signals | Fed by |
|:-:|:--|:--|:--|:--|
| 1 | **Breach & Compromise History** | `breach_compromise_history` | confirmed breaches by data class, KEV-listed CVEs, NVD CVEs by CVSS | HIBP, CISA KEV, NVD, FIRST EPSS |
| 2 | **Attack Surface & Hygiene** | `attack_surface_hygiene` | TLS version, certificate validity, HSTS/CSP/X-Frame-Options, DNSSEC/CAA, stale hosts, weak issuance, estate-wide TLS and expiry | self-run TLS, DNS, HTTP headers, Certificate Transparency |
| 3 | **Identity & Email** | `identity_email` | DMARC, SPF, DKIM | DNS |
| 4 | **Transparency** | `transparency` | vulnerability-disclosure programme, `security.txt` | HTTP headers, trust pages |
| 5 | **Compliance & Regulatory** | `compliance_regulatory` | certification posture (claimed vs registry-corroborated), regulator action | trust pages, regulator feeds |

### Context categories — collected, counted toward coverage, **never penalising**

| Category | Engine key | Signals | Feeds |
|:--|:--|:--|:--|
| **Continuity Context** | `continuity_context` | entity status, entity existence, entity maturity, domain registration | the Continuity axis (E4) |
| **Assurance Context** | `assurance_context` | programme disclosure, contactability, reporting posture | **Assurity** (§8) |

Three things about this split are worth stating plainly, because it is the largest structural change the model
has had:

- **Why two categories stopped scoring.** A vendor entering administration does not thereby have worse TLS.
  Companies House mapped liquidation and insolvency onto `entity_inactive`, which cost **20 points of technical
  security posture**. And penalising the absence of an audit or a public security page is a tax on audit budget
  — it measures spend, not risk, and falls hardest on small suppliers. Both facts are still collected and still
  published; neither charges posture any more.
- **Why they were not simply deleted.** `planned_signal_count` is the confidence denominator. Delete nine
  signals and every vendor's confidence rises for no evidential reason — the check still ran, we merely stopped
  charging for it. Keeping them holds the denominator at **27** and keeps the receipt showing the check
  happened. `test_context_categories_never_penalise` asserts they carry no penalising band.
- **Identity & email is separate from hygiene on purpose.** It is one decision at the apex, answered by three
  DNS records that stand or fall together, and a per-host *rate* has no meaning for it.

**Signals are unique across categories** — the engine keys penalties on `(category, signal)`, so a signal
appearing twice would be charged twice. Asserted by `test_no_signal_appears_in_two_categories`.

**Held** (designed, but no free lawful source feeds them yet — out of the runtime model, in a roadmap note):
Supply Chain & Dependency · Data Privacy & Leakage · Geopolitical & FOCI · ESG & Ethical · Emerging Tech & AI.

**The directness ladder** (inside Category 1, worth calling out): a realized breach outranks observed
exploitation (KEV) outranks a theoretical CVE (NVD). What *happened* penalises harder than what merely *could*.

---

## 4 · How a single finding is penalised — the NIST variables

NIST SP 1326's variables, applied to the **penalty** per finding before it is subtracted:

```
effective_penalty = severity_penalty × age × frequency × mitigation
```

| Variable | Rule | Why |
|:--|:--|:--|
| **Severity** | the four-tier penalty above | signal-specific, the main lever |
| **Age** | `max(0.15, 0.5 ^ (months / 36))` | 3-year half-life, floored at 0.15 — a 2013 breach penalises less than one from last month, but never decays to nothing |
| ↳ *exception* | current-state signals **never decay** | a cert's `event_date` is its expiry boundary, not an event. Decaying it made a cert expired 6 years ago cost **−10** while one expiring next week cost **−20** — the longer it stayed broken, the cheaper it got. Listed in `modifiers.age.never_decays` |
| **Frequency** | `1 + 0.25 × (n − 1)`, cap 2.0 | three breaches are a pattern, not one counted thrice |
| **Mitigation** | `× 0.6` only where remediation is **evidenced** | claims don't count; corroboration does |

**Collapse, then amplify — never sum.** Every `(category, signal)` group contributes **one** penalty: its
**worst instance after decay**. Recurrence is then counted exactly once, by the frequency factor. Three
breaches are `20 × 1.5 = 30`, not `20+20+20 = 60` — summing *and* amplifying would count the same pattern
twice, and two breaches would already outweigh a −40 critical.

**CVE bags are frequency-exempt.** Forty keyword-matched CVEs are match *volume*, not forty events: they
collapse to their worst representative with no amplification, so coarse-match noise can't tank a clean
estate. Realized events (breaches, regulator actions) *are* amplified — there, recurrence is real.

**Mitigation is live but dormant.** It is carried on the finding, never inferred from severity — and no
free source we collect currently evidences that a vendor fixed a given issue, so nothing sets it today.
The rule is real; the discount is not yet being handed out.

---

## 5 · How the numbers roll up

```
observation → severity → penalty (× age × frequency × mitigation)
   ↓  collapse each (category, signal) group to its WORST instance
   ↓  sum penalties PER CATEGORY, each capped at 100
category posture = 100 − its own penalties      (for the breakdown)
   ↓  GATE ── sanctions hit / ambiguous entity ──►  BLOCKED, no score emitted
overall posture = 100 − (total penalty ÷ FIXED divisor, currently 2.86)
   ↓  CRITICAL CEILING ── directly-observed current critical ──►  capped at 49 (top of D)
grade (A–F)  +  confidence (coverage, reported separately)  +  assurity (§8)
   +  a plain-English reason per deduction (§11)
```

**Overall is `100 − total penalty ÷ a fixed divisor`.** Each category's damage is capped at its own 100 first
(one catastrophic category cannot dominate without bound), then the total is divided by a divisor **fixed by the
model** — currently **2.86**. Not a running sum: on a 0–100 scale that tanks a merely-mediocre vendor to F. And
deliberately **not** an average of the categories that happened to return data — that let a clean trust page buy
**+23 posture**, because each clean category entered the average as a 100 and pulled it up. A silent source adds
no penalty and cannot move the denominator, so *"missing data never changes posture"* is arithmetic, not a promise.

### Why 2.86, and why the divisor must move when the category count does

The model's **maximum damage** is `scoring_categories × 100 ÷ divisor`. That product is the thing being held
fixed, and it is the trap the E5 restructure had to avoid:

| Scoring categories | 7 | 6 | **5** | 4 | 3 |
|:--|--:|--:|--:|--:|--:|
| Divisor | 4.00 | 3.43 | **2.86** | 2.29 | 1.71 |

At seven categories and a divisor of 4, maximum damage was **175 posture points**. E5 left five scoring
categories — the other two are context and can never penalise — so **leaving the divisor at 4 would have cut
maximum damage to 125 and made the model quietly more forgiving**: a larger *fraction* of the model would have
to fail before a vendor bottomed out. Nobody would have decided that; it would simply have happened.
`test_divisor_preserves_maximum_damage` counts scoring categories only and asserts the relationship.

The original calibration argument still holds underneath: a divisor equal to the category count is
algebraically the plain mean of the category postures, and that proved very forgiving of *concentrated*
failure — every benchmark vendor scored A (86–92), including one with 13 known-exploited product matches. The
current value is calibrated against the frozen corpus (`backend/tests/fixtures`). A genuinely severe *live*
critical is still handled non-compensatorily by the ceiling (§6).

**The order is not negotiable: gate → total → ceiling.** The gate is first because a blocked record has no score to
cap. The ceiling is last because its job is to correct the division's compensatory arithmetic — applying it earlier
would let the spreading dilute it again.

**The rule that keeps this honest:**

> **Missing data reduces *confidence*. It never changes *posture*.**

A signal that returns nothing is dropped from its category's coverage — never scored as a comfortable pass and
never as a penalty. **A vendor cannot look strong simply by being invisible**, and cannot be punished for silence
either; silence is a confidence problem, surfaced as such.

---

## 6 · The three differentiators (where normal subtraction stops)

Spreading the total over a divisor is *compensatory* — strengths dilute weaknesses. That is correct for hygiene
signals that genuinely trade off, and **wrong** for these three, which we keep deliberately.

**① Sanctions gate — emits nothing.** A sanctions / watchlist hit does **not** score badly or grade F — under the
Autonomous Sanctions Act 2011 s16(7) a weighted contribution is legally meaningless. The record is **blocked** and
routed to human adjudication. An entity too ambiguous to resolve (confidence < 0.5) blocks too — we never silently
score the wrong company. Matching is **whole-word** (so *asana* can't trip on *villaSANA*) and recall-tuned: this
is the one place recall beats precision.

**② Critical ceiling — non-compensatory (our knockout).** A **directly-observed current critical** — an expired
production certificate, seen live — **caps** the posture at the top of Grade D (49) so one severe live issue can't
be averaged away by good hygiene elsewhere. Only signals we observe as *current* auto-apply; a coarse KEV
name-match penalises but does **not** ceiling (it proves "this product line had a known-exploited CVE," not
"unpatched here"). A fired ceiling **bypasses the Ghost refusal** — a directly-observed critical is certain even on
thin coverage.

**③ The Ghost — refuse rather than mislead.** Below **40% evidence coverage** the product publishes **no grade**,
names the silent sources, and labels the vendor a Ghost. A clean-*looking* vendor we can't stand behind is a
designed refusal, not an error. (A high-*penalty* vendor with thin coverage is not refused — we found a real
problem — it surfaces flagged for review.)

**Weakest-link across assets.** A vendor is only as strong as its weakest exposed asset: the vendor posture is the
**lowest** asset posture, not the average. (The PoC scores the primary asset; multi-asset collection is roadmap.)

---

## 7 · Confidence — the second axis

Confidence is **evidence coverage first**: of the signals we planned to collect, how many returned data. A
bounded multiplier for the vendor's **operating history** is then applied — how much track record stands behind
the measurement (§7.1). It moves confidence only; posture arithmetic is untouched.

```
coverage        = signals_covered / signals_planned
confidence      = coverage × assurance_multiplier      (0.96 … 1.04, continuous)
confidence_band = High (≥0.90) · Medium (≥0.70) · Low (<0.70)
```

Posture is always read *with* confidence, never alone. A strong-looking posture on **Low confidence** is flagged
**The Ghost** — unassessed, not safe. This is the single most important honesty guarantee in the model: an 87 built
on thin evidence must never read like an 87 built on full coverage.

**Clean receipts count toward coverage.** "Checked and found nothing" must not read the same as "never checked". A
source that is successfully queried and comes back clean (HIBP no breach, KEV no product match) contributes to
coverage as a benign pass — this is what lifts a genuinely-clean vendor out of the Ghost quadrant without claiming
false certainty. Note this is the *only* thing a clean receipt does: it lifts confidence and **never** posture (§5).

### The ceiling ramp — thin evidence caps how good a vendor may *look*

`refuse_below: 0.4` used to be the whole story: a cliff at 40%, and above it nothing. So a vendor seen through
four collectors could publish **100** and read identically to one seen through fourteen — which made *being
hard to observe* the cheapest route to a high score, the precise incentive this product exists to remove.

| Coverage | Published posture may not exceed | |
|:--|--:|:--|
| ≥ 0.90 | **100** | full collection — no cap |
| ≥ 0.75 | **97** | can still reach A, cannot be flawless |
| ≥ 0.60 | **90** | the top of A is not available on this evidence |
| ≥ 0.40 | **80** | B at best |
| < 0.40 | *not published* | the Ghost refusal (§6③) |

**It is a cap, never a deduction.** It touches no category penalty, so §5's honesty rule holds exactly as
before — missing data still costs no posture. What it limits is **the claim we are prepared to publish on the
evidence we hold**. The findings are the vendor's; the ceiling above them is ours.

**And the refusal below 0.40 is adverse, not neutral.** The config carries the required wording so the UI
cannot quietly soften it: *"this supplier could not be assessed from public sources, and it must not be read as
a clean bill of health."* A grey chip reading as neutral is the failure mode — a supplier nobody can see is a
supplier nobody has checked, and **that is a finding**.

**The bands are calibrated, not decorative.** All five benchmark vendors return **0.96–1.00** on a full
collection run and band **High**, so the ladder discriminates rather than pinning everything to Low. A
regression test asserts this: if a signal is ever added to the model with no collector to feed it, the
denominator grows, `High` becomes unreachable, and the build fails rather than quietly turning every vendor
into a Ghost.

---

## 7.1 · Operating history — continuous, and fenced off from posture

How long the entity has traded, on a **saturating curve** rather than a ladder of bands
([`backend/app/maturity.py`](../backend/app/maturity.py)):

```
maturity_index(y) = min(1, ln(1 + y) / ln(1 + 25))
```

| Years | 1 | 2 | 5 | 10 | 20 | 25+ |
|:--|--:|--:|--:|--:|--:|--:|
| index | 0.21 | 0.34 | 0.55 | 0.74 | 0.93 | 1.00 |

**Why a curve.** The previous model banded age into five rungs whose top one opened at ten years, so an
11-year-old vendor and a 40-year-old one were **byte-identical**, and a 2-year-old differed from a 40-year-old by
a single `low` — 3 penalty points, **0.75 posture** after the divisor, well inside the noise of a grade band.
The curve is steep where the difference is real (year one against year five is a genuine difference in
demonstrated continuity) and flat where it is not (year twenty-five against year forty is not), so
*diminishing returns on operating history* is a claim the arithmetic actually makes rather than one the prose
asserts. The band keys are **unchanged**, so every severity, reason and action in `scoring.yaml` still resolves;
the band is now a label and the index is what the model computes with.

**Sources are weighted, because age is purchasable.** An aged domain is bought at auction for a few hundred
dollars; a company inception date in a national register is not. So a registered inception (GLEIF, Companies
House, ABN, Wikidata P571) carries full weight and an RDAP domain-creation date is discounted to **0.6** — a
40-year domain with no corroborating register earns roughly what a 5-year registered company earns. The discount
is **one-directional**: it can only lower assurance, never manufacture it, and where sources disagree the engine
takes the most conservative reading.

**What the CURVE is allowed to change.** Confidence, and which baseline controls could yet exist (§7.2). It sets
no penalty of its own.

> **The continuous index never reaches a penalty.** `tests/test_maturity.py::test_maturity_never_reaches_a_penalty`
> asserts it, and the frozen corpus is unmoved.

**Be precise about the band, which is a separate and older thing.** `entity_maturity` *is* a scored signal:
`young_2_5`, `startup_lt_2` and `new_lt_1` each carry a **Low (−3)**, worth about **0.75 posture** after the
divisor, while `established_5_10` and `mature_gt_10` are a `pass`. So a vendor under five years old does carry
one small age-related deduction, and from five years upward age costs nothing. That predates the curve and is
deliberately unchanged. The claim worth making is the narrow one — *the continuous measure is confined to
confidence* — not the broad one that age never touches posture at all.

This is not squeamishness. [`context-aware-vendor-risk-scoring-study.md`](context-aware-vendor-risk-scoring-study.md)
§1.4 records the finding plainly — *"Company **age** predicts security posture: **No published evidence found**"* —
and §1.6 places maturity in Confidence and Benchmarking only. A firmographic multiplier on posture would make the
score non-comparable across vendors, unvalidatable against outcomes, and purchasable.

---

## 7.2 · Target maturity — the baseline that needs no peers

Peer benchmarking answers *"am I typical?"*. This answers *"am I adequate?"* — and the vendors where the two
**disagree** are the interesting ones. Configured in [`benchmarks.yaml`](../benchmarks.yaml) under
`target_maturity`, evaluated in [`backend/app/targets.py`](../backend/app/targets.py).

**Why both.** A percentile has two failure modes a cohort cannot fix from the inside. The peer pool is a
**convenience sample** of whatever this deployment happened to score, so a book skewed toward weak vendors
produces a flattering median and every comparison inherits the skew; and below the minimum peer count it
publishes nothing at all — precisely the position of a new deployment or a niche sector. A published baseline is
fixed and external, so it cannot drift with the portfolio and it **works at n=0 peers**.

**Every control names a real instrument, or it does not ship.** The loader refuses a control with no `basis`,
exactly as it refuses an `expected_posture` without one.

| Control | Expected | Basis |
|:--|:--|:--|
| DMARC | `p=reject` (partial: `p=quarantine`) | CISA **BOD 18-01** (Oct 2017) — `p=none` in 90 days, `p=reject` within one year |
| SPF | hard fail | CISA **BOD 18-01** — valid SPF on all second-level domains within 90 days |
| TLS version | 1.3 or 1.2 | **NIST SP 800-52 Rev. 2** (Aug 2019); **PCI DSS v4.0** req. 4.2.1 forbids SSL and early TLS |
| Certificate validity | valid | **NIST SP 800-52 Rev. 2** |
| HSTS | present | CISA **BOD 18-01** |
| Known-exploited CVEs | none matched | CISA **BOD 26-04** (10 Jun 2026), which revoked and replaced BOD 22-01 and BOD 19-02 |
| Vuln-disclosure programme | bug bounty (partial: `security.txt` only) | CISA **BOD 20-01** (Sep 2020) — VDP published by March 2021 |
| `security.txt` | present | **RFC 9116** (Apr 2022). *Not* mandated by BOD 20-01 — the directive requires the **policy**; RFC 9116 is the mechanism |
| Independent certification | registry-corroborated | **ISO/IEC 27001** Stage 1 + Stage 2 audit; **AICPA SOC 2 Type II** observation period |

Controls we could not source — DNSSEC and CAA among them — are **absent rather than asserted**. It is easy to
write a plausible baseline out of professional intuition and hang an official-sounding citation on it; that
produces numbers a client cannot trace, which is the failure this file exists to refuse.

**Scope, stated rather than implied.** Most of these bind US federal civilian agencies, not private vendors. They
are used as the strongest available *published, dated, checkable* statement of what a competent operator does —
never as a claim that a given vendor is legally bound by them.

**Attainability is not leniency.** `attainable_after_years` exists only where an artefact is **arithmetically
impossible** sooner: a SOC 2 Type II attests to controls operating *across* an observation window, so a company
younger than that window cannot hold one, and counting its absence would measure the calendar rather than the
vendor. Excluded controls leave the denominator and are **named** in the summary. It is *not* a grace period —
DMARC, SPF, TLS, certificate validity and HSTS cost engineering hours rather than years, small firms
under-adopt them badly (Inc. 5000 at 15.2% `p=reject` against Fortune 500 at 62.7%), and every vendor is held to
them from day one. A vendor whose age we could not determine is held to the **full** baseline, so being
unmeasurable is never a way to shed controls.

**Not observed is not failed**, and below `min_controls` observed nothing is published — the same two
disciplines the engine applies one level up.

---

## 8 · Assurity — the third axis

*Implemented in [`backend/app/assurity.py`](../backend/app/assurity.py); configured under `assurity:` in
[`scoring.yaml`](../scoring.yaml). Served at `GET /api/vendors/{ref}/assurity`.*

Posture cannot answer *"has anyone independent actually checked?"*. **"Their TLS is current and they have no
known breaches"** and **"an auditor has examined their controls"** are different claims, and a buyer needs
both. `synthetic_smallco` in the corpus is exactly the vendor where they diverge: **posture 97, assurity 13**.

```
Assurity = 100 × sigmoid( A₀ + Σⱼ creditⱼ − Σₖ γ · ComplianceGapₖ )
```

| Parameter | Value | Why |
|:--|--:|:--|
| `intercept` (A₀) | **−1.2** → ≈23/100 | A vendor with nothing observable sits at a **low intercept, not zero**. Unevidenced is not disproved, and a 0 would read as *audited and failed* |
| `scale` | 1.0 | sigmoid steepness |
| `min_observed_signals` | **3** | Below this, **nothing is published**. "2 of 3" assembled from whichever signals happened to return is the same false precision as a median over three peers |

**Absence never subtracts — enforced, not merely intended.** `_validate` rejects a negative credit *at load*.
This is the other half of E2's argument. E2 said "not doing what almost nobody does is not a failing" and
stopped `cert_posture.none_claimed` costing 8 points — a charge that fired on **five of five** corpus vendors,
which is a tax on audit budget rather than a measure of risk, falling hardest on exactly the small suppliers
this product exists to assess fairly. E2 could not say *"and doing it **is** a distinction"*, because
`penalty_for` returns zero or positive and the engine had no bonus path. This axis is that path.

**The credits** (abridged — full table in `scoring.yaml`):

| Signal | Band | Credit |
|:--|:--|--:|
| `cert_posture` | registry-corroborated | **+1.4** — an independently *verifiable* certification, the strongest signal here |
| `cert_posture` | claimed, uncorroborated | +0.2 — worth something, not much |
| `reporting_posture` | substantive | +0.9 — a real security report, not a landing page |
| `vd_program` | funded bug bounty | +0.8 — evidence of an operating security function |
| `program_disclosure` | detailed policies | +0.6 |
| `contactability` | DPO **and** security contact | +0.4 |
| `security_txt` | present | +0.2 |

**Why a sigmoid rather than a sum.** Bounded without a cliff at either end: the twentieth certification cannot
buy what the second did, and no vendor is ever pinned at 0 or 100 — so the axis keeps resolving differences at
both extremes.

> **Why it is a separate axis and not a posture bonus.** Credit for publishing a trust page must never buy back
> points lost to an expired certificate. Keeping them apart is what stops assurance theatre becoming a security
> score, and it is the same discipline that keeps confidence out of posture.

### 8.1 · The compliance gap — the only thing that lowers assurity

*Implemented in [`backend/app/compliance_gap.py`](../backend/app/compliance_gap.py).*

A gap is **not an absence**. It is a vendor **asserting a framework** and then being **observed failing one of
its controls** — a statement about the reliability of their own claims, which is precisely what this axis
measures. Everything else on this axis only ever adds.

This is where E1's deleted sector expectation landed, correctly. `industry_profiles` used to *promote a
finding's severity by one step* when a sector cited a named instrument, so a missing DMARC record read as a
hygiene gap for a farm supplier and a live fraud exposure for a bank. That destroyed cross-vendor
comparability: the same evidence scoring differently because of a label **we** assigned. Compare:

> *"This DMARC finding is worth more points."* ← an opinion wearing a number
>
> *"Vendor is APRA-regulated and publishes no DMARC record; CPS 234 requires controls commensurate with the
> threat."* ← disputable, citable, actionable

The second changes no arithmetic. It states an obligation, names the instrument, names the observation, and
can be argued with — which the first cannot, because there is nothing to argue with except our judgement.

**Four disciplines the implementation enforces:**

- **Bound-by vs asserted are kept apart.** A framework applies either because the client told us the vendor is
  subject to it (`sector` — client-supplied, **never inferred**) or because the **vendor claims it**. Both are
  recorded, because they carry different weight in a conversation: one is a legal obligation the vendor cannot
  decline, the other is the vendor's own marketing. The asserted case is higher-signal precisely because gaming
  it means dropping the claim.
- **Which certification, not merely that there is one.** `cert_posture` bands say `claimed_unverified`, not
  `claimed ISO 27001`. Matching on the band alone would fire for every framework keyed to that signal, so a
  vendor claiming SOC 2 and nothing else would have been published as *"asserts ISO/IEC 27001:2022"* — us
  putting a claim in the vendor's mouth and then finding them short against it. Every `asserted_by` block must
  name `claim_contains`, matched against what the collector actually read off the trust page.
- **Distinct observations, not gap count.** A vendor asserting ISO 27001, SOC 2 and PCI DSS while negotiating
  TLS 1.0 breaches three frameworks with **one weakness**. Assurity charges it **once**; all three gaps are
  still reported. Charging three times would mean the axis punished a vendor for publishing more
  certifications, which is the opposite of what it measures.
- **Posture is untouched.** The underlying finding already charged whatever it charges. Charging it again here
  would be the double-count E3 spent a phase removing.

---

## 9 · Inherent risk and residual risk

*Implemented in [`backend/app/residual_risk.py`](../backend/app/residual_risk.py). Served at
`GET /api/vendors/{ref}/residual-risk`.*

Posture answers *"how strong is this vendor?"*. It cannot answer *"how much do we stand to lose if they
fail?"* — that depends on what **this buyer** has given them, which no amount of outside-in scanning can
observe. So the buyer declares it, and the two combine.

| Layer | Owner | Moves when |
|:--|:--|:--|
| **Posture** | Ours to measure | Their TLS moves — twice a quarter is normal |
| **Inherent** | **Theirs to declare** | The *relationship* moves, and not otherwise |
| **Residual** | Neither — a deterministic lookup | Either input moves |

**Inherent tier is `max(criticality, data_access_scope)` — never an average.** A low-criticality vendor with
production-data access is not a medium-risk vendor. Non-compensatory, like every other roll-up here.

**The published matrix — sixteen cells, argued over once, then fixed.** Rows are posture bands
(`strong ≥80 · moderate ≥60 · weak ≥40 · poor`), columns are inherent tiers:

| Posture ↓ / Inherent → | low | medium | high | critical |
|:--|:--|:--|:--|:--|
| **strong** | Low | Low–Med | Medium | Med–High |
| **moderate** | Low–Med | Medium | High | High |
| **weak** | Medium | High | High | Critical |
| **poor** | Med–High | High | Critical | Critical |

Three properties of that table are deliberate:

- **A strong posture never reaches Low at high inherent exposure.** An A-grade vendor holding your production
  data lands at Medium. They are still holding your production data, and the day their posture moves you
  discover how much was riding on it.
- **Undeclared is not Low.** A relationship nobody has classified routes to the **deepest** assessment, not the
  shallowest — the vendors nobody has got round to classifying are disproportionately the ones nobody has
  looked at.
- **Sole-source escalates one band.** If the relationship has no substitute, the cell moves one rung up the
  ladder, and the response names that this happened.

**Residual is recomputed on read and stored nowhere.** It is a lookup over two things that are each stored, so
it can never drift from the inputs it was derived from. It is also **advisory**: it states what the evidence
and the declared exposure together support. The client decides.

---

## 10 · Peer benchmarking — am I typical?

*Implemented in [`backend/app/benchmarking/`](../backend/app/benchmarking/), configured under `benchmarking:`
in [`benchmarks.yaml`](../benchmarks.yaml), served under `/api/v2/suppliers/{ref}/…`. Design notes:
[`benchmarking-design.md`](benchmarking-design.md).*

**`n` travels with every figure, and the refusal is the figure.** Not a greyed-out number, not a dash that
reads as a rendering bug — the sentence, with the actual `n` in it.

| Resolution | Floor | Why that number |
|:--|--:|:--|
| **Percentile** | **n ≥ 30** | The conventional floor for treating a sample percentile as a point estimate. Below it the sampling error is wider than the gap between adjacent percentile labels |
| **Quartile** | **n ≥ 8** | Below this a single peer is more than an eighth of the population, so "bottom quartile" can flip on one supplier joining |
| Below 8 | — | **Insufficient peer data**, with the `n` stated. Read the absolute posture |

Both floors are **enforced in code**, not only in YAML. A YAML edit may raise them; it may not lower them.
That is not paranoia: the superseded v1 module shipped `min_cohort_n: 1`, and *"make it 3 for the demo"* is
exactly how a demo setting survives into production, where it is indistinguishable from a decision nobody made.

**The cohort is a widening ladder, and every rung it tried is published** with that rung's `n` — because
"which peers?" is the only question anyone actually asks about a benchmark. `sector + size + delivery model`
first, then `sector + size`, then `sector`. **There is deliberately no rung meaning "every supplier ever
assessed"**: a comparison against everything is not a peer group. When the ladder widens, the card says so on
its face, because a comparison against a wider population is a weaker claim.

**Comparison reliability is published separately from confidence.** They are different facts: a
well-evidenced supplier can sit in a poorly-supported peer group. Reliability combines sample adequacy, how
exact the winning rung was, how well-evidenced the peers themselves are, and freshness.

**Per-domain discrimination is stated on every row.** A domain where every peer scores 100 cannot rank
anybody, and presenting a rank among identical values manufactures signal from a constant. Each domain is
labelled *discriminating*, *peers barely differ*, or *too few peers to test*.

**A snapshot is frozen when published.** The percentile trend reads points that were true when taken, never
today's cohort against an old posture — otherwise the cohort's movement gets attributed to the supplier.
Snapshots are member-bearing internally and every tenant-facing path calls `.public()`, which structurally
cannot carry peer refs.

**The cohort is disputable; the placement is not.** The cohort, snapshot and resulting placement are
deterministic lookups over the inputs and carry no independent judgement. Dispute an *input* — sector, size
band, delivery model, headcount, revenue.

### 10.1 · The expectation gap — am I what my peer group predicts?

`Posture − E[Posture ∣ cohort]`, with the observations that account for it. The sentence this whole subsystem
exists to produce:

> *"Posture 68. Cohort median (n=14): 87. This vendor sits 19 points below its peer group. The gap is driven
> by dmarc (absent) — 12 of 14 peers are not in this band."*

A buyer handed `−19` has a fact. A buyer handed `−19, driven by DMARC, which 12 of 14 of their own peers
publish` has a **remediation** — and one they can take to the vendor with a count of the vendor's own peer
group attached, rather than an opinion of ours.

Two disciplines:

- **The drivers are ranked, not a decomposition**, and the response says so. Since E7a what a finding costs
  depends on what else was charged alongside it, so per-signal attributions **do not sum to the gap** and no
  arrangement of them can be made to. A reader who adds them up and finds they miss has caught a real property
  of the model, not a bug.
- **Constants are excluded and named.** A signal that does not vary across the cohort is not a comparison
  there; reporting it as a driver would dress a constant as a difference.

---

## 11 · Every deduction has a sentence

A score a client cannot have explained to them is the thing this product exists **not** to produce. So every
band that costs points carries a plain-English reason in [`scoring.yaml`](../scoring.yaml), written
**consequence first**:

```yaml
reasons:
  dmarc:
    absent: "Anyone can send email pretending to be this company. There is no published rule
             telling mail servers to stop it, which is the standard opening move in invoice
             fraud and staff impersonation."
```

"Anyone can send email pretending to be this company" is what a procurement lead reads; *"no DMARC record"* is
the supporting fact and sits underneath. The page stops needing a translator.

**The loader refuses to start if a penalising band has no reason** — and equally if a reason exists for a band
that doesn't. All **57** penalising bands are covered. The explanation can't silently fall behind the model.

**Adjustments are shown, not hidden.** The receipts also state *why* a charge differs from the base penalty —
which is the most defensible thing the model does and used to be invisible:

> *Customer passwords were exposed in a confirmed public breach.* **−16**
> This is historic, so it counts for less than a recent finding would — at full weight it would have been −40.

> *A product this company is associated with appears on the register of vulnerabilities actively exploited in
> the wild.* **−27.1**
> 13 matches found — only the most serious one is counted, so a long list of name matches cannot inflate the score.

Note the second sentence is *not* "counted once as a pattern" — CVE bags are frequency-**exempt** (§4), and the
UI must not describe a calculation that never ran.

---

## 12 · Worked example — a real vendor, reproducible

Not a toy. **Atlassian**, as it stands in the live store. Re-run the frozen-corpus version with
`python -m tests.regolden`.

| Category | Kind | Penalty | Posture |
|:--|:--|--:|--:|
| Breach & Compromise History | scoring | −33.62 | 66 |
| Attack Surface & Hygiene | scoring | −21.05 | 79 |
| Identity & Email | scoring | −1.50 | 98 |
| Transparency | scoring | −1.50 | 98 |
| Compliance & Regulatory | scoring | −1.50 | 98 |
| Continuity Context | context | 0 *(cannot penalise)* | 100 |
| Assurance Context | context | 0 *(cannot penalise)* | 100 |
| **Total** | | **−59.17** | |

**Overall = 100 − 59.17 ÷ 2.86 = 79 (B)**, at **100% coverage / High confidence**.

Beside it, on their own axes: **assurity 82** from 8 observed signals with **no compliance gaps**, and a peer
placement of **9th percentile, ranked 36 of 39** against a `sector=technology` cohort — with an expectation
gap of **−11** driven by `kev_listed_cve`, which **28 of its 39 peers** avoid.

That cohort clears **n ≥ 30**, so a percentile is published rather than a quartile — but only because the
peer group was populated. The same vendor read *"insufficient peer data, n=3"* until the scoring pipeline
began recording cohort attributes (§10); the peers had been assessed all along and were simply not in the
table the cohort query reads.

Read those together and the record says something no single grade can: this vendor is well-documented and
publishes what it claims (assurity 82), it is not carrying an assurance problem, and its posture deficit
against its own peer group has **one named cause**. That is a conversation to have with the vendor, not a
letter to file.

Two mechanisms are visible in the breach figure. KEV product matches collapse to **one** penalty
(frequency-exempt worst-of, §4), and that survivor decays with age. Under the pre-4.2.0
mean-of-covered-categories this vendor scored **90 (A)** — *"robust posture, few or no external issues"* while
carrying 13 known-exploited product matches. That is the leniency the fixed divisor corrects.

*Change one fact — the certificate is expired and serving production — and the **critical ceiling** fires:
Attack Surface & Hygiene collapses, and the published posture is capped at **49 (Grade D)**, cause named,
regardless of the good hygiene elsewhere.*

---

## 13 · Honest about what this simplifies

- **Perimeter ≠ posture.** OSINT measures what a stranger can see; a perfect header score is fully compatible with
  a bad internal posture. It's a proxy, labelled as one.
- **No live-blocklist / open-port visibility (a deliberate v1 constraint).** Active port-scanning risks an
  unauthorised-access classification, and the obvious feeds (Shodan/Censys free tiers) bar commercial use. We proxy
  attack surface via Certificate Transparency (certs *issued*, not ports *open*) and own the gap.
- **Coverage tracks *size*, not *risk*.** Big vendors publish more, so they surface more signal. The confidence
  axis mitigates this — it does not cure it. Read the confidence band, not the grade alone.
- **Peers are a convenience sample, not the industry.** Every cohort is built from vendors this deployment
  happened to score, so a skewed portfolio produces a skewed median. The target maturity baseline (§7.2) exists
  to give a reading that does not inherit that bias; the placement still does, and says so on the card. The
  `n ≥ 30` / `n ≥ 8` floors (§10) bound how confidently the skew can be stated — they do not remove it.
- **The expectation gap's drivers are ranked, not apportioned.** They will not sum to the gap, by construction
  (§10.1). Anyone reading them as a decomposition will conclude the arithmetic is broken; it is not, and the
  response says so in its own caveats.
- **Assurity measures observable assurance, not security.** A vendor can hold every certification listed and
  still be poorly run. It is published on its own axis precisely so that it can never be mistaken for, or
  averaged into, a security judgement.
- **Residual risk is advisory.** It states what the evidence and the declared exposure together support. It
  does not make the decision, and it is only ever as good as the declaration behind it (§9).
- **Operating history is a weak signal, carried weakly.** No authoritative source scores by founding date, so
  age is confined to a bounded confidence multiplier and to control attainability — never to posture (§7.1).
- **Fixed penalties are blunter than a calibrated curve** — four tiers, deliberately, because they are easier to
  defend and tune than a continuous deduction curve.
- **We score entities, not people.** Executive/brand risk, PEP screening, person-level ownership, and demographic
  signals are excluded at a bright line (§4.2: APP 10, the privacy tort, EU AI Act Art 6(3)) — logged with a
  reason in `excluded_signals`, never silently dropped.

---

### See also

- [`scoring.yaml`](../scoring.yaml) — the machine-readable model (the actual deliverable)
- [`scoring_framework.md`](scoring_framework.md) — the guided tour, one level deeper than this page
- [`methodology.md`](methodology.md) §5 — full derivation, legal basis, and benchmark defence
- [`research_doc.md`](research_doc.md) — per-source reliability, legality, and limits
- [`roadmap.md`](roadmap.md) — how this productises toward the Wahid AI third-party module
