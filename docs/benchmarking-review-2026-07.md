# Benchmarking design — independent review, audited against the tree

**Reviewed:** 2026-07-31 · **Source:** [very_helpful_benchmarking_analysis.md](very_helpful_benchmarking_analysis.md)
**Verdict:** architecture confirmed · **three gaps found and closed** · two deferred with reasons

The review is grounded in NIST SP 800-161, ISO 27036, FFIEC/OCC third-party guidance, Shared
Assessments, and the US Chamber Principles for Fair and Accurate Security Ratings. It was audited
line by line against what is actually in the tree rather than against the phase plan.

---

## 1. What it confirms

| Review principle | Where it lives | State |
|---|---|---|
| Three-layer model: Inherent / Control Posture / Benchmark | `residual_risk.py` · engine · `benchmarking/` | ✅ E10b |
| Cohorts keyed on **supplier attributes only** | `benchmarking/cohorts.py` | ✅ EB decision 1 |
| Buyer-side attributes are **interpretation filters, not cohort keys** | `data_access_scope` → `residual_risk.py` | ✅ |
| Deepen-then-widen ladder, never "all suppliers" | `cohorts.py`, load-validated | ✅ EB |
| Minimum *n* 8–15 directional, 30 for stable percentiles | `min_quartile_n: 8`, `min_percentile_n: 30`, both floored **in code** | ✅ |
| Expectation Gap as a primary output | `expectation_gap.py` | ✅ E10a |
| `rank_of_n` preferred at modest *n* | `placement.py`, required not optional | ✅ EB |
| Quartile always with a direction label | `quartile_label` + `quartile_direction` | ✅ EB |
| Each domain carries its own *n* | `DomainPlacement` | ✅ EB |
| Immutable snapshot per placement | `snapshot.py`, append-only | ✅ EB |
| **Never** a blended benchmark score | asserted by test | ✅ |
| Synthetic peers hard-gated, never a screenshottable ranking | `is_synthetic` | ✅ EB — **and closed in the v1 path at E11** |
| External base rates are *population statistics*, not peer medians | reference-line framing | ✅ |
| Member refs stored, never published | `PublicCohortSnapshot` has no field for them | ✅ EB decision 4 |
| Dispute the **inputs**, never the resulting cell | cohort dispute path | ✅ EB |
| Periodic discrimination analysis | runs on every cohort build | ✅ EB |

The most direct confirmation is §5:

> *"If synthetic or external population reference points are used, they must be hard-gated:
> reference line + prose only. They must never generate a percentile or quartile that can be
> screenshotted as a peer ranking."*

That is verbatim the defect closed at E11 on the deprecated path, which was still the **default
route** and still writing an invented percentile onto every scored vendor.

---

## 2. Three gaps found, all closed

### §6 — *"higher gap or lower peer rank can increase review frequency for high-inherent suppliers"*

**Not built.** `recommend.py` derived `recheck_after` from grade × criticality × the soonest
finding, and never from peer position. E10a made the input available and nothing consumed it.

Closed: `recommend(expectation_gap=...)`. A gap at or beyond **−15 points** shortens the cadence —
30 days for a replaceable supplier, **14 for one the buyer depends on**.

**The line it must not cross, and the test that holds it.** The gap reaches the cadence and nothing
else: `decision`, `headline` and `urgency` are all fixed before it is read. A vendor materially
below its peers at the same grade as one on the median is not a worse vendor by our arithmetic — it
is a vendor whose position is harder to explain, and the honest response is to look again sooner,
not to score them lower. **Letting a peer comparison move a decision would be the firmographic
multiplier E1 deleted, arriving through the benchmark instead of the sector table.**

−15 points rather than a percentile because a percentile needs n≥30 and most cohorts will not have
it for a long time; a signed point gap is meaningful from n=8.

### §7 — *"firmographics-only ablation tests"*

**Not built.** Discrimination analysis existed; the ablation did not.

Closed structurally rather than statistically, and the choice is deliberate: a statistical ablation
needs a seeded pool (E11) and would return `untested` until then — **and an untested control is not
a control.** The structural form holds now and at any pool size: no firmographic is assigned in
`engine.py` or `normalize.py`. If that ever stops being true, no downstream statistic makes it safe.

Paired with an outcome test: identical evidence publishes an identical posture in a strong cohort
and a weak one; only the *context* differs.

### §8 — *"what good looks like"* was reachable only as three separate calls

The composite block the review specifies — posture + confidence, peer context + gap, residual risk,
recommended action — existed as four routes and no assembly. **Assembling them was the client's
job**, and a client that assembles them slightly differently from the next client is how a posture
ends up presented as a residual risk, or a peer gap read as a grade.

Closed: `GET /api/vendors/{ref}/assessment`. It holds **no arithmetic of its own** — each layer is
produced by the module that owns it and copied out — so it cannot become a fourth source of truth.
Each layer degrades alone: no cohort attributes means no peer context and everything else still
renders.

---

## 3. Deferred, with reasons

**§3 "version the cohort schema."** Snapshots are immutable and every placement references the one
it was computed against, so history is safe. What is missing is a `cohort_schema_version` on the
snapshot, which would let a reader distinguish *"my position moved"* from *"the band boundaries
moved"*. Worth doing before the first ladder or size-band change ships — **it is only useful if it
predates the change it would explain**, so it should land before, not with, that edit.

**§1–§3 program-level maturity, KPIs/KRIs, staffing ratios, cycle times.** The review's first half
describes benchmarking *a TPRM programme*: assessment cycle time, remediation SLA attainment,
staffing per 100 vendors, maturity levels 1–5. **This system benchmarks a vendor's posture against
peer vendors** and says nothing about whether the buyer's programme is mature. That is a different
product with different data (the client's own workflow, not public OSINT), and it is already
scoped as **P9** — EB's own "what it does NOT do" section names it. Not a gap in this layer;
recorded so the distinction is not lost.

**§2 five-level maturity model.** Same boundary. It also collides with E9c's settled position that
maturity models do not fit a pass/fail control schema — see
[e9c-framework-roadmap.md](e9c-framework-roadmap.md) §3.1.

---

## 4. One place the review understates the implementation

> *"Enforce a realistic minimum n (industry practice for directional insight is typically 8–15;
> treat 30 as aspirational for stable percentiles)."*

Both thresholds are **floored in code**, not only set in YAML — and that asymmetry is not
belt-and-braces. `min_cohort_n: 1` shipped in `benchmarks.yaml` for months because a demo setting
survived into production, which is indistinguishable from a decision nobody made. A configurable
threshold with no floor is a threshold that will eventually be lowered by someone under time
pressure, and the review's framing does not capture that a YAML value alone is insufficient.
