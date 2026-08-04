# Step-by-Step Migration Plan — `scoring.yaml` v4.2.0 → the revised model

**Expands:** [migration-plan.md](migration-plan.md) · **Derived from:** [report.md](report.md) Parts VI–X
**Baseline verified against the working tree on 2026-07-29**, not quoted from the source document.
**Measured baseline:** `scoring.yaml` v4.2.0 · `benchmarks.yaml` v1.0.0 · **417 passed, 15 failed** (`pytest -q`, 299 s)

---

## How to read this document

[migration-plan.md](migration-plan.md) is the *argument* — why each change is right. This document is the *runbook* — what to type, in what order, and what breaks if you do it wrong. Where the two disagree, this one has been checked against the code; see **[Corrections to the source plan](#corrections-to-the-source-plan)** below for the seven places that matter.

Each phase gives you:

| Section | What it is |
|---|---|
| **Preconditions** | What must be true before you start. Verify, don't assume |
| **Steps** | Numbered, each naming an exact file and symbol |
| **Loader traps** | The `scoring_config.py` validators that will refuse to start if you miss a step |
| **Tests to write first** | Written *before* the implementation, named as they should appear |
| **Exit criteria** | Mechanically checkable |
| **Rollback** | How to get back, and whether stored data survives |

The ordering rule from the source plan stands, and everything below obeys it:

> **Relocate before you re-weight, and re-weight before you re-shape.**

---

## The invariants — verified present, and what enforces each

Re-verified against the tree. These are the properties the report credits as *"better than most commercial security ratings"*. A change that breaks one is out of scope regardless of merit.

| Invariant | Enforced at | Verified |
|---|---|---|
| Posture and Confidence never collapse into one number | [engine.py:210-220](../backend/app/scoring/engine.py#L210-L220) — `Score.posture` and `Score.overall_confidence` are separate fields | ✅ |
| Missing data reduces Confidence, never Posture | [engine.py:187](../backend/app/scoring/engine.py#L187) — fixed divisor, `cfg.penalty_divisor()` | ✅ **= 4.0**, not 7 |
| Evidence stored before scoring | [pipeline.py:145](../backend/app/pipeline.py#L145) — `store.put(result)` precedes `engine.score` at line 186 | ✅ |
| Every penalising band has a plain-English reason | [scoring_config.py:328](../backend/app/scoring_config.py#L328) `_validate_every_penalty_is_explainable` | ✅ **57 bands** |
| Every penalising band has an action + recheck date | [scoring_config.py:354](../backend/app/scoring_config.py#L354) `_validate_every_penalty_is_actionable` | ✅ |
| No natural-person data | `excluded_signals`, and [models.py:335](../backend/app/models.py#L335) `VendorProfile` docstring | ✅ |
| Ongoing findings never decay | [engine.py:124-128](../backend/app/scoring/engine.py#L124-L128) passes `event_date=None` for `never_decays` | ✅ set is `{cert_validity}` |
| No dead config | [scoring_config.py:449](../backend/app/scoring_config.py#L449) `_validate_no_dead_config` | ✅ **see Loader traps** |
| Frozen regression corpus stays green or moves deliberately | [tests/test_corpus.py](../backend/tests/test_corpus.py), `python -m tests.regolden` | ✅ 5 vendors |

### The invariant the source plan does not list, and you will hit first

`_validate_no_dead_config` ([scoring_config.py:449](../backend/app/scoring_config.py#L449)) means **every top-level key in `scoring.yaml` must be declared in either `_ENGINE_READS` or `_DOCUMENTATION_ONLY`** ([scoring_config.py:39-62](../backend/app/scoring_config.py#L39-L62)). Add a key without registering it and the loader raises `ScoringConfigError` at import — the app will not start, and every test fails at collection.

Phases 1, 2 and 3 each add or remove a top-level key. **Each one needs a matching edit to `_ENGINE_READS`.** This is called out per phase below.

---

## Baseline measurements — taken 2026-07-29

Recorded here so Phase 0 has a "before" that is not a guess.

### Config shape

```
version                4.2.0
planned_signal_count   27
penalising_bands       57
penalty_divisor        4.0          # NOT 7 — see Corrections
ceiling_score          49.0
refuse_below           0.4
severity_penalties     critical 40 · high 20 · medium 8 · low 3 · informational 0
ceiling_auto_signals   {cert_validity}
never_decays           {cert_validity}
frequency_exempt       {kev_listed_cve, nvd_cve}
industry_profiles      {financial_services, healthcare}
count_bands            subdomain_estate {small:10, medium:100} · stale_hosts {none:0, some:5}
```

### The 27 planned signals, by category

| Category | n | Signals |
|---|--:|---|
| `cyber_hygiene_technical` | 11 | `tls_version` `cert_validity` `dmarc` `spf` `dkim` `hsts` `csp` `x_frame_opts` `security_txt` `dnssec` `caa` |
| `breach_compromise_history` | 3 | `breach_by_data_class` `kev_listed_cve` `nvd_cve` |
| `digital_footprint_assets` | 3 | `subdomain_estate` `stale_hosts` `weak_issuance` |
| `vendor_transparency_gov` | 3 | `program_disclosure` `contactability` `vd_program` |
| `business_financial_stability` | 4 | `entity_status` `entity_existence` `entity_maturity` `domain_registration` |
| `compliance_regulatory` | 2 | `cert_posture` `reporting_posture` |
| `adverse_media_reputation` | 1 | `regulator_action` |

### The frozen corpus, as it stands

| Vendor | Posture | Grade | Conf | `digital_footprint_assets` penalty | Largest category penalty |
|---|--:|:--:|--:|--:|---|
| atlassian | 82 | B | 0.963 | **26.0** | breach 27.06 |
| myob | 86 | A | 0.926 | **26.0** | **footprint 26.0** |
| onetrust | 86 | A | 0.963 | **26.0** | **footprint 26.0** |
| slack | 84 | B | 0.926 | **19.0** | breach 23.85 |
| snowflake | 76 | B | 0.926 | **31.0** | breach 39.64 |

> **Read this table before starting Phase 2.** `digital_footprint_assets` is the largest or second-largest penalty for **all five** corpus vendors, and it holds only three signals — two of which (`subdomain_estate`, `stale_hosts`) are raw counts with no denominator. Defect #2 is not theoretical here; it is the single biggest line item in the shipped baseline, and every vendor in the corpus is a large one. This is the concrete "before" that Phase 2 must move.

### The 15 failing tests, grouped by actual root cause

Measured, not quoted. The source plan's 9/5/1 split is close but mis-assigns the boundary.

| Root cause | Count | Tests |
|---|--:|---|
| `min_cohort_n: 1` + synthetic-peer fallback vs. tests expecting refusal | **8** | `test_benchmark.py`: `test_ladder_widens_when_the_exact_cohort_is_thin`, `test_ladder_drops_revenue_before_headcount`, `test_insufficient_at_every_width_reports_how_close_it_came`, `test_no_cohort_means_no_comparison`, `test_min_cohort_n_is_tunable` · `test_cohorts.py`: `test_benchmark_refuses_below_minimum_peers`, `test_benchmark_widens_and_says_so`, `test_peers_endpoint_returns_only_the_cohort` |
| `_derive_cohort` defaulting sector → `technology`, employee_band → `medium` | **6** | `test_profile.py`: `test_unclassifiable_vendor_gets_no_cohort`, `test_missing_size_also_blocks_the_cohort`, `test_client_size_override_forms_a_cohort_that_public_data_could_not`, `test_cohort_forms_with_only_one_size_dimension`, `test_repair_yields_no_cohort_when_the_profile_cannot_support_one`, `test_no_size_signal_at_all_blocks_the_cohort` |
| Band count drift: [test_actions.py:38](../backend/tests/test_actions.py#L38) asserts **54**, actual is **57** | **1** | `test_every_penalising_band_has_an_action_and_a_recheck` |

All 15 are **config-vs-test drift, not regressions**. Both cohort clusters trace to deliberate demo settings ([benchmarks.yaml:35](../benchmarks.yaml#L35) `min_cohort_n: 1`) and a deliberate fallback ([profile.py:257](../backend/app/profile.py#L257) sector default). The decision in Phase 0 is which side to move.

---

## Corrections to the source plan

Seven items in [migration-plan.md](migration-plan.md) do not survive contact with the code. Each is carried into the phases below in corrected form.

### 1. `penalty_divisor` is **4.0**, not 7 — every posture-impact number changes

[scoring_config.py:111-119](../backend/app/scoring_config.py#L111-L119) documents a default of "the category count" (7), but [scoring.yaml](../scoring.yaml) ships `overall.penalty_divisor: 4`. Verified: `cfg.penalty_divisor() == 4.0`.

**Consequence.** Every "N points of penalty" figure in the report and source plan is a *category* penalty. Divide by 4 for posture impact. Twelve hygiene failures at 56 category-points cost **14 posture points**, not 56. One Critical at 50 costs **12.5**. State which units you mean in every test assertion you write, or the tests will encode the wrong claim.

### 2. Phase 2's denominator exists for **1 of 10** Class-P signals, not "most"

The source plan says *"Most collectors already know this; they discard it."* That is true for exactly one pair. Verified by reading each collector:

| Signal | Collector | What it actually probes | `D_s` available today? |
|---|---|---|:--:|
| `stale_hosts` ÷ `subdomain_estate` | [ct_collector.py:166-176](../backend/app/collectors/ct_collector.py#L166-L176) | `len(subdomains)`, `len(stale)` from CT logs | ✅ **yes** |
| `tls_version`, `cert_validity` | [tls_collector.py:48-90](../backend/app/collectors/tls_collector.py#L48-L90) | **one** handshake, `vendor.domain:443` | ❌ `D_s` = 1 |
| `hsts`, `csp`, `x_frame_opts` | [headers_collector.py:36-60](../backend/app/collectors/headers_collector.py#L36-L60) | **one** GET of `https://{domain}/` | ❌ `D_s` = 1 |
| `nvd_cve`, `kev_listed_cve` | `nvd_collector.py`, `kev_collector.py` | keyword match on product names | ❌ no host denominator exists |

So the honest position: **one signal pair can be normalized this week; the other eight need the collectors to fan out across the estate first** — a much larger job with rate-limit, runtime and politeness consequences the repo takes seriously ([seed_cohorts.py:22-26](../backend/app/seed_cohorts.py#L22-L26), *"politeness is not optional"*). Phase 2 below is therefore split into **2A (free, this week)** and **2B (the real work)**.

### 3. Phase 0's ablation AUC is **not executable** — there are no outcome labels

`grep -rn "auc\|outcome\|ground_truth"` over `app/` and `tests/` returns nothing relevant. There is no label set, no AUC function, and the corpus is **5 vendors**, all scoring 76–86 (A/B). AUC over 5 unlabelled points is not a measurement.

Phase 0 below replaces this with a two-track approach: a **label acquisition** work item (the real prerequisite) and **label-free diagnostics** that can run immediately and still falsify the "size classifier" hypothesis.

### 4. There is **no bonus mechanism** in the engine — Phase 1b cannot land as written

`penalty_for` ([scoring_config.py:88-92](../backend/app/scoring_config.py#L88-L92)) returns `0.0` for `pass`/`informational` and a positive number otherwise. Nothing returns a negative. `posture = max_score − penalties` ([engine.py:187](../backend/app/scoring/engine.py#L187)) has no additive path, and `max_score` caps at 100 anyway.

Phase 1b says four signals become *"bonus → Assurity"* — but Assurity is **Phase 5a**, which does not exist yet. Sequencing the source plan gives (Phase 1 → Phase 5a) is backwards for these four.

**Resolution, used below:** split 1b into

- **1b-i — stop penalising.** Set the band to `informational`. Already supported, keeps the signal in `covered_by_cat` so `planned_signal_count()` stays 27 and confidence does not move. Fully reversible.
- **1b-ii — credit positively.** Lands *after* 5a ships. Purely additive to Assurity; Posture is untouched.

This makes the confidence-denominator exit criterion automatic rather than something to hope for.

### 5. Reclassifying a band **orphans its `reasons` and `actions` entries** and the loader will refuse to start

Both validators check the reverse direction ([scoring_config.py:344-352](../backend/app/scoring_config.py#L344-L352) and [377-388](../backend/app/scoring_config.py#L377-L388)): a `reasons:` or `actions:` entry for a band that no longer penalises raises `ScoringConfigError`.

**Every band you move to `informational` in Phase 1b-i must have its `reasons:` and `actions:` entries deleted in the same commit.** Not a follow-up. The app will not boot otherwise.

### 6. Phase 1a is a **hard** prerequisite for 1b, not merely a nice ordering

`_validate_industry_profiles` ([scoring_config.py:402](../backend/app/scoring_config.py#L402), `real = {(sig, band) …penalising_bands()}`) requires every promoted band to *be* a penalising band. The shipped profiles promote:

```yaml
financial_services:  dmarc.absent · spf.absent · cert_posture.none_claimed · contactability.none_published
healthcare:          breach_by_data_class.personal_info · dmarc.absent · reporting_posture.none
```

Three of these — `cert_posture.none_claimed`, `contactability.none_published`, `reporting_posture.none` — are on Phase 1b's reclassification list. Reclassify before deleting the profiles and the loader dies with *"promotes X, which is not a penalising band"*.

### 7. Line references in the source plan have drifted

| Source plan says | Actually at |
|---|---|
| `scoring.yaml:645+` (`promote` blocks) | [`scoring.yaml:661`](../scoring.yaml#L661) — `promote:` at 666 and 678 |
| `normalize.py:93` (`promote_severity` call) | [`normalize.py:121`](../backend/app/scoring/normalize.py#L121) |
| `normalize.py:67` (`_count_of`) | [`normalize.py:95`](../backend/app/scoring/normalize.py#L95) — line 67 is `_band_key` |
| `scoring_config.py:249` (`promote_severity`) | ✅ correct |
| `engine.py:187` (fixed divisor) | ✅ correct |

---

## Phase 0 · Instrument before changing anything

**Duration:** 2–3 weeks (was 1–2 — label acquisition is real work) · **Risk:** none · **Changes scores:** no

### Preconditions

- Working tree clean; `git init` if not yet under version control (**the repo is currently not a git repository** — do this first, or you cannot read the corpus diffs that make every later phase falsifiable)
- `backend/.venv` active

### Step 0.1 — Put the repo under version control

Non-negotiable prerequisite for every later phase. `regolden` is only meaningful if you can diff its output.

```bash
cd backend && git init && git add -A && git commit -m "baseline: scoring.yaml v4.2.0, 417 pass / 15 fail"
```

### Step 0.2 — Resolve the 15 failing tests

**Do this before anything else.** Migrating on a 15-red suite means you cannot distinguish a new break from an old one.

Decide per cluster. The two cohort clusters are one decision each, not fourteen:

| Cluster | Option A — move the config | Option B — move the tests |
|---|---|---|
| `min_cohort_n` (8 tests) | Set [benchmarks.yaml:35](../benchmarks.yaml#L35) to `8`. Tests pass. **Every cohort comparison stops publishing** until Phase 6 seeds a pool | Re-assert against `min_cohort_n: 1`. Demo keeps working; the tests no longer defend the threshold that is the feature |
| `_derive_cohort` defaults (6 tests) | Remove the `technology` / `medium` fallbacks at [profile.py:257-261](../backend/app/profile.py#L257-L261). Tests pass; some vendors get no cohort | Re-assert that a fallback cohort forms. Documents current behaviour |

**Recommended:** Option B for both, with a written note, *plus* a new test that pins the demo setting explicitly (`test_min_cohort_n_demo_setting_is_deliberate`). Rationale: Phase 6 changes `min_cohort_n` properly, with a seeded pool behind it. Flipping it now buys a green suite and a dead benchmark feature for six weeks.

The third is a one-character fix:

```python
# tests/test_actions.py:38
assert len(cfg.penalising_bands()) == 57   # was 54
```

Better: make it drift-proof, since Phases 1–3 all change this number.

```python
# The count is a tripwire, not a spec — it exists so a band added without a reason
# and an action fails loudly here. Update it deliberately when the model changes.
assert len(cfg.penalising_bands()) == 57, (
    "penalising band count moved — if intentional, update this number in the same "
    "commit as the scoring.yaml change, and say why in the message"
)
```

**Exit:** `pytest -q` → **432 passed, 0 failed**, or each remaining failure has a written reason in `docs/known-failures.md`.

### Step 0.3 — Build the outcome label set (the real prerequisite)

There is no ground truth in this repo. Without it, "did the model get better" is unanswerable, and Phases 2 and 3 have nothing to prove themselves against.

Labels do not have to be breaches. In descending order of availability:

| Label source | Signal | Availability |
|---|---|---|
| HIBP breach records | Confirmed compromise, dated | Collector already exists — `hibp_collector.py` |
| CISA KEV + vendor product mapping | Known-exploited exposure | `kev_collector.py` exists |
| Regulator enforcement actions | Adverse outcome, dated | `regulatory_collector.py` exists |
| GDELT adverse media | Weak/noisy; use as tiebreak only | `gdelt_collector.py` exists |

**Concrete task.** Extend the seed run to 115 vendors ([seed_cohorts.py](../backend/app/seed_cohorts.py) — verified: **115 `SeedVendor(` entries** across 10 sectors), then join each against HIBP/KEV/regulatory to produce `backend/tests/fixtures/outcome_labels.json`:

```json
{"vendor_ref": "…", "label": 0 | 1, "basis": "HIBP breach 2023-04-11 …", "as_of": "2026-07-29"}
```

**Honesty requirement.** A public-breach label is *itself* observability-biased — large disclosed companies are over-represented, which is the exact bias the model is accused of. Record this on the artefact. It makes AUC a **lower bound with a known lean**, not a verdict. Within-cohort AUC (below) is the partial defence.

### Step 0.4 — Label-free diagnostics you can run today

These do not wait on 0.3, and they can already falsify the "it's a size classifier" hypothesis.

1. **Firmographics-only reconstruction.** Fit posture from `{sector, revenue_band, employee_band, region}` alone across the seeded pool. Report R². **An R² above ~0.5 means half the score is demographics** — no outcome labels needed to find that alarming.
2. **Rank correlation, posture vs. size.** Spearman ρ between posture and employee band. Publish it. Re-run after Phase 2; it must fall.
3. **Score distribution.** Posture histogram, per-category penalty shares, count of vendors at 0 and at the 49 ceiling. Store as `docs/baseline-distribution.md`.
4. **Signal firing rates.** For each of the 27 signals: how many vendors have a penalising band. This is what tells you which Phase 1b reclassifications actually matter.
5. **Change-impact counts.** Verified starting points: `industry_profiles` promotions can fire for **2 sectors / 7 bands**; `cert_posture` and `reporting_posture` penalise **1 band each** in the corpus (all 5 vendors show `compliance_regulatory` penalties of 3.0–8.0).

### Step 0.5 — Freeze the baseline artefacts

```bash
cd backend
python -m tests.regolden                 # confirm it reproduces the committed golden file
git diff --exit-code tests/fixtures/golden_scores.json   # MUST be empty
```

A non-empty diff here means the corpus is not reproducible and every later phase's evidence is worthless. Fix before proceeding.

### Exit criteria

- [ ] Repo under git; baseline committed
- [ ] `pytest -q` green, or each failure written down with a reason
- [ ] `outcome_labels.json` exists, with its bias disclosed — or Phase 0.3 explicitly deferred and the consequence accepted in writing
- [ ] `docs/baseline-distribution.md` committed
- [ ] `regolden` reproduces the committed golden file byte-for-byte

### Stop and reconsider if

Firmographics-only R² exceeds ~0.5, or firmographics-only AUC lands within a few points of the full model. That means the score is largely a size-and-sector classifier, and **Phase 2 becomes urgent rather than important** — consider running 2A before Phase 1.

---

## Phase 1 · Structural relocations

**Duration:** 2–3 weeks · **Risk:** low · **Changes scores:** yes — only by removing what should not have been there

No arithmetic changes. Best ratio of noise removed to risk taken.

**Internal order is mandatory: 1a → 1b-i → 1c.** See [Correction 6](#6-phase-1a-is-a-hard-prerequisite-for-1b-not-merely-a-nice-ordering) — reversing it breaks the loader.

### 1a · Delete `industry_profiles` severity promotions

The report is unambiguous: this is **mechanism #10, *dynamic severity adjustment*, rejected** — the one adjustment every commercial platform declines to implement. It also puts `scoring.yaml` in direct contradiction with `benchmarks.yaml`, which states interpretation lives in benchmarking and never in the arithmetic. **These two files currently disagree.**

#### Steps

1. **`scoring.yaml`** — delete the whole `industry_profiles:` block, [lines 661–685](../scoring.yaml#L661).
2. **`scoring_config.py`** — remove `industry_profiles()`, `industry_profile()`, `promote_severity()` ([lines 242–266](../backend/app/scoring_config.py#L242-L266)) and `_validate_industry_profiles()` ([line 390](../backend/app/scoring_config.py#L390)) plus its call at [line 326](../backend/app/scoring_config.py#L326).
3. **⚠️ Loader trap** — remove `"industry_profiles"` from `_ENGINE_READS` ([scoring_config.py:54](../backend/app/scoring_config.py#L54)). Leave it in and `_validate_no_dead_config` is fine, but the key is gone so nothing breaks; **the real trap is the reverse** — if you delete the code but leave the YAML block, the loader raises *"declares key(s) nothing reads"* and the app will not start.
4. **`normalize.py`** — drop the `promote_severity` call at [line 121](../backend/app/scoring/normalize.py#L121); `make()` collapses to `severity = severity`, `promoted_by = None`.
5. **`engine.py`** — `industry_profile=sector if self.cfg.industry_profile(sector) else None` at [line 219](../backend/app/scoring/engine.py#L219) becomes `industry_profile=None`. Also strip the `sector` parameter's promotion contract from the docstring at [lines 62-67](../backend/app/scoring/engine.py#L62-L67).
6. **`pipeline.py`** — the `industry_profile` field in the `profiled` progress event at [line 199](../backend/app/pipeline.py#L199).
7. **Keep** `NormalizedFinding.base_severity` and `.promoted_by` ([normalize.py:50-51](../backend/app/scoring/normalize.py#L50-L51)) for one release so stored receipts still deserialise. Mark them deprecated in the docstring with the release they go.
8. **Re-point the sector expectation at the Compliance Gap (Phase 5b).** The sector obligation is real — APRA CPS 234, OAIC NDB figures — it just is not a severity change. Copy the two `basis:` strings verbatim into the Phase 5b backlog now, while you still have them in front of you.

#### Tests to write first

```python
def test_sector_never_changes_a_severity():
    """The same findings scored with and against every sector produce an identical Score."""

def test_scoring_yaml_declares_no_industry_profiles():
    """The block is gone from config, not merely unread."""
```

Note `test_profile.py` already asserts the profile-does-not-move-the-score property; extend rather than duplicate it.

#### Expected corpus movement

`promoted_by` is `None` for all five corpus vendors (none carry a sector at fixture-score time — [test_corpus.py:47](../backend/tests/test_corpus.py#L47) passes no `sector`). **Expect zero movement in `golden_scores.json`.** If anything moves, you removed more than promotions — stop and read the diff.

### 1b-i · Stop penalising the low-base-rate signals

Roughly a third of the signal list. **The single highest-leverage change for noise reduction.**

Per [Correction 4](#4-there-is-no-bonus-mechanism-in-the-engine--phase-1b-cannot-land-as-written), this step only sets bands to `informational`. Positive credit is **1b-ii**, after Phase 5a.

| Signal | Now | 1b-i (this step) | 1b-ii (post-5a) | Base-rate justification |
|---|---|---|---|---|
| `dnssec` | `absent: low` | `informational` | Assurity bonus | 7–18% adoption — penalising absence penalises the norm |
| `caa` | `absent: low` | `informational` | Assurity bonus | ~1.6% at early measurement; no published breach correlation |
| `security_txt` | `absent: low` | `informational` | Assurity bonus | <0.25% of domains; 60% point at a platform's generic contact |
| `vd_program` | `none: medium` | **keep, footprint-scaled** | — | The one governance signal with a causal mechanism — scale by host count (Phase 2B), not age |
| `program_disclosure` | `none: medium` | `informational` | → Assurity | Measures go-to-market motion; NIS2 Art. 20 requires governance, not a public page |
| `contactability` | `none_published: medium` | **merged** (1c) | — | Same fact observed three ways, currently charged three times |
| `cert_posture` | `none_claimed: medium` | `informational` | → Assurity | Penalising absence is a tax on audit budget |
| `reporting_posture` | `none: medium` | `informational` | → Assurity | Private SMBs cannot produce this signal at all |

#### Steps, per reclassified band

For each of `dnssec.absent`, `caa.absent`, `security_txt.absent`, `program_disclosure.none`, `cert_posture.none_claimed`, `reporting_posture.none`:

1. **`scoring.yaml` `categories:`** — change the band's value to `informational`.
2. **⚠️ `scoring.yaml` `reasons:`** — **delete** the entry for that `signal.band`. Leaving it raises *"reason(s) for band(s) that … no longer penalise"* ([scoring_config.py:349](../backend/app/scoring_config.py#L349)) at load.
3. **⚠️ `scoring.yaml` `actions:`** — **delete** the entry. Same failure mode, [scoring_config.py:385](../backend/app/scoring_config.py#L385).
4. Update `tests/test_actions.py` band count in the same commit.

> **Do all four edits per band in one commit.** A commit that changes the band but not `reasons:` leaves the tree unbootable, and bisecting through it later is miserable.

#### The confidence denominator — why it holds automatically

`planned_signal_count()` ([scoring_config.py:108-109](../backend/app/scoring_config.py#L108-L109)) counts **signals**, not bands, and `normalize_one` still emits a `NormalizedFinding` for an `informational` severity ([normalize.py:156-158](../backend/app/scoring/normalize.py#L156-L158)), so `covered_by_cat` ([engine.py:162-164](../backend/app/scoring/engine.py#L162-L164)) still records the signal as covered.

**Therefore: 27 stays 27, and confidence does not move.** This is the structural reason to prefer `informational` over deleting the signal — a bonus signal is still *planned and checked*. Assert it anyway:

```python
def test_planned_signal_count_is_unchanged_by_reclassification():
    assert get_scoring_config().planned_signal_count() == 27

def test_reclassified_signals_still_count_toward_coverage():
    """A vendor missing DNSSEC is still a vendor whose DNSSEC we checked."""

def test_corpus_confidence_is_unmoved():
    """Posture may move in Phase 1. Confidence may not."""
```

#### Expected corpus movement

From the baseline table, all five vendors carry `compliance_regulatory` penalties of 3.0–8.0 — that is `cert_posture` and/or `reporting_posture`. **Expect all five to gain posture.** A `medium` (8) removed from one category is `8/4 = 2` posture points.

### 1c · Merge `contactability` into `security_txt`

RFC 9116's `Contact:` field, a VDP page and a published security address are usually the same fact. Under flat accumulation that fact is charged three times, quietly making Governance heavier than any deliberate weighting decision would have made it.

Note the collector already knows this: [headers_collector.py:73-84](../backend/app/collectors/headers_collector.py#L73-L84) emits **both** `security_txt` *and* `vd_program` from the single `security.txt` observation, with a comment saying so. The triple-charge is visible in the source.

#### Steps

1. Remove `contactability` from `scoring.yaml` `categories.vendor_transparency_gov`, plus its `reasons:` and `actions:` entries.
2. Stop emitting it from whichever collector supplies it (`trust_collector.py`).
3. **⚠️ `planned_signal_count()` drops 27 → 26.** This is the one place in Phase 1 where the denominator legitimately moves, because a signal is genuinely gone rather than reclassified.
   - Update the assertion to 26 **in the same commit**
   - Expect a small confidence *rise* for every vendor (same numerator, smaller denominator)
   - **Record this in the Phase 1 change notice** — it is a real, if benign, published-number movement
4. Alternative worth considering: keep `contactability` as an `informational` signal so the denominator holds at 27. Costs nothing, avoids a confidence movement you have to explain, and keeps the evidence that the check ran. **Recommended.**

### 1d · Category consolidation + divisor recalibration

**Duration:** 1–2 weeks · **Risk:** medium · **Changes scores:** **yes, everywhere** · **Blocked on:** 1b-i **and** 5e

Once 1b-i has parked the low-base-rate signals and 5e has moved the going-concern signals out, two categories are empty and two are thin. This step collapses the survivors into a coherent set and **re-derives the divisor in the same commit**.

**Do this before Phases 2 and 3.** Both are defined *per category* — exposure denominators and λ-diminishing-returns both operate inside a category boundary. Landing the boundaries first means one re-golden instead of three.

#### The target set — all 27 signals accounted for, verified

| # | Category | Signals | n |
|---|---|---|--:|
| 1 | `breach_compromise_history` | `breach_by_data_class` `kev_listed_cve` `nvd_cve` | 3 |
| 2 | `attack_surface_hygiene` | `tls_version` `cert_validity` `hsts` `csp` `x_frame_opts` `stale_hosts` `weak_issuance` | 7 |
| 3 | `identity_email` | `dmarc` `spf` `dkim` | 3 |
| 4 | `transparency_disclosure` | `vd_program` `security_txt` | 2 |
| 5 | `regulatory` | `regulator_action` | 1 |

**Disposition of the other 11:** `subdomain_estate` → denominator (Phase 2A) · `dnssec`, `caa` → informational (1b-i) · `entity_status`, `entity_existence`, `entity_maturity`, `domain_registration` → Continuity (5e) · `cert_posture`, `reporting_posture`, `program_disclosure` → Assurity (5a) · `contactability` → merged into `security_txt` (1c).

**16 scored · 1 denominator · 2 informational · 8 relocated = 27.** Verified against the live config: nothing unaccounted, nothing invented.

#### Two mistakes to avoid — both are easy to make here

**⚠️ No signal may appear in two categories.** The engine keys on `(category, signal)` and collapses within that pair ([engine.py:109-121](../backend/app/scoring/engine.py#L109-L121)), so a duplicated signal is charged twice. The two that tempt duplication:

- `stale_hosts` reads as both "attack surface" and "digital footprint" — it goes in **category 2 only**.
- `kev_listed_cve` reads as both "breach history" and "vulnerability exposure" — it goes in **category 1 only**. Splitting it also breaks Phase 3c's precedence rule (*KEV > EPSS > CVSS, one penalty*).

**⚠️ Do not create a "Vulnerability & Exposure" category around KEV-past-due.** That finding is a **Phase 4 gate** — it emits no score at all. A category built on a gate has no penalising member.

#### The divisor — derive it, do not guess

`penalty_divisor` is **4.0**, tuned against seven categories. Each category caps at 100, so the model can currently inflict `700 / 4 = 175` posture points of damage — i.e. a vendor floors once ~57% of total capacity is saturated.

**Leaving the divisor at 4.0 while shrinking the category count makes the model more forgiving**, because a larger *fraction* of the model must fail before the score bottoms out. Preserve the ratio instead:

```
divisor(n) = n × (4 / 7)          # holds max damage at 175 posture points
```

| Categories | Divisor | Max damage | Floors at |
|--:|--:|--:|--:|
| 7 (today) | 4.00 | 175 | 0 |
| 6 | 3.43 | 175 | 0 |
| **5 (target)** | **2.86** | 175 | 0 |
| 4 | 2.29 | 175 | 0 |
| 3 | 1.71 | 175 | 0 |

At the target of five categories, **`overall.penalty_divisor: 2.86`**. Ship it in the same commit as the restructure — a category move without the divisor change silently re-scores every vendor for an invisible reason.

> **Sanity check before committing:** with the divisor left at 4.0, a 3-category Posture would floor at **25** — the worst vendor imaginable could not score below a C. That is the failure mode this derivation exists to prevent.

#### The one decision this step forces

**`regulator_action` (category 5) needs a ruling.** Its bands are `formal_investigation` (medium) and `enforcement_action` (high), and they do **not** distinguish cyber from non-cyber enforcement. A regulator sanctioning a vendor over a data breach is security evidence; one sanctioning them over consumer-credit conduct is not.

Three options, pick one explicitly:

1. **Tag cyber-relevance in `regulatory_collector`** and keep only cyber enforcement in Posture. Most correct, most work.
2. **Keep the category as-is** and accept that non-cyber enforcement scores as security risk. Cheapest, and wrong in a way a vendor will eventually dispute.
3. **Move the whole signal to Continuity/Compliance Gap.** Posture drops to four categories, divisor 2.29.

Recommended: **(1)**, falling back to **(3)** if the collector work does not fit. Do not default to (2) by omission.

#### Loader traps

- [ ] Renaming a category changes every `categories.<name>` key — `reasons:` and `actions:` are keyed on `signal.band`, not category, so they survive; **verify anyway**
- [ ] `penalty_divisor` updated in the same commit
- [ ] `_ENGINE_READS` unchanged (no new top-level key), but confirm `overall` still validates
- [ ] `count_bands.subdomain_estate` retired alongside its scoring

#### Tests to write first

```python
def test_no_signal_appears_in_two_categories():
    """The engine keys on (category, signal). A duplicate is charged twice."""
    seen = {}
    for cat in cfg.category_names():
        for sig in cfg.signals_of(cat):
            assert sig not in seen, f"{sig} in both {seen[sig]} and {cat}"
            seen[sig] = cat

def test_divisor_preserves_maximum_damage():
    """n categories x 100 / divisor == 175, whatever n is."""
    n = len(cfg.category_names())
    assert abs((n * 100) / cfg.penalty_divisor() - 175) < 1.0

def test_every_planned_signal_has_exactly_one_home():
    """16 scored + 1 denominator + 2 informational = 19 in Posture; 8 relocated."""
```

#### Exit criteria

- [ ] Five categories, 16 scored signals, no duplicates — asserted by test
- [ ] `penalty_divisor` = 2.86 (or 2.29 if `regulator_action` relocates), asserted by test
- [ ] `regulator_action` decision recorded in writing
- [ ] **No category weights introduced.** A penalty model has none — §5.6 deleted them, and percentages are unfalsifiable. Weighting emerges from the inventory; Phase 3 fixes it via aggregation
- [ ] Corpus re-goldened, per-vendor justification written
- [ ] Confidence denominator movement disclosed (see 5e — `planned_signal_count()` falls as signals relocate)

#### Rollback

Config-only, but it moves every published number. Revert is a single commit; **stored scores are unaffected** (append-only rows). Version the model and give notice before shipping — this is the largest single re-score in the plan.

### Loader traps for Phase 1 — checklist

- [ ] `industry_profiles` removed from **both** `scoring.yaml` and `_ENGINE_READS`
- [ ] Every reclassified band's `reasons:` entry deleted
- [ ] Every reclassified band's `actions:` entry deleted
- [ ] `test_actions.py` band count updated
- [ ] No `industry_profiles.promote` entry survives naming a now-informational band

Fastest check — it catches all five at once, because the loader validates on import:

```bash
cd backend && python -c "from app.scoring_config import load_scoring_config; \
  c = load_scoring_config(); print('OK', c.version, c.planned_signal_count(), len(c.penalising_bands()))"
```

### Exit criteria

- [ ] Corpus re-goldened, **with a written justification per moved vendor** — `python -m tests.regolden`, then read the diff
- [ ] `planned_signal_count()` == 27 (or 26 with 1c-as-deletion, deliberately recorded)
- [ ] Corpus confidence distribution unmoved — asserted, not eyeballed
- [ ] Every reclassified signal still appears in the receipt, marked informational rather than silently dropped
- [ ] `git diff tests/fixtures/golden_scores.json` reviewed line by line before commit

### Rollback

Pure config plus small code deletions. `git revert` the range. **Stored scores are unaffected** — they are append-only rows ([pipeline.py:186](../backend/app/pipeline.py#L186) `store.put_score`), so historic scores keep their original numbers and only new runs change. Retaining `base_severity`/`promoted_by` (step 1a.7) is what keeps old receipts deserialising.

### Stop and reconsider if

Confidence moves materially. That means the denominator changed, which was not the intent.

---

## Phase 2 · Exposure normalization — **the big one**

**Duration:** 2A: 1 week · 2B: 6–10 weeks (was "3–4 weeks" for both) · **Risk:** high · **Changes scores:** substantially, and that is the point

This is defect #2 and the report's #1 recommendation. It removes an existing bias rather than adding a new one.

Split per [Correction 2](#2-phase-2s-denominator-exists-for-1-of-10-class-p-signals-not-most). **2A is free and proves the mechanism. 2B is the real engineering.** Do not conflate them in planning or the phase will look like a 3-week job and take three months.

### Phase 2A · The one denominator that already exists

`stale_hosts ÷ subdomain_estate` is computable today with no new collection. Both come from the same `ct_collector` call, both already carry raw counts ([ct_collector.py:166-176](../backend/app/collectors/ct_collector.py#L166-L176), `value={"count": len(subdomains)}` and `{"count": len(stale)}`), and both are read by `_count_of` at [normalize.py:95](../backend/app/scoring/normalize.py#L95).

**The defect, in one line.** `count_bands.stale_hosts` is `{none: 0, some: 5}` — so **a 900-host vendor with 6 stale hosts scores `many`, identically to a 6-host vendor with 6 stale hosts.** And per the baseline table, `digital_footprint_assets` is the largest or second-largest penalty for all five corpus vendors.

#### Tests to write first — before any implementation

```python
def test_large_estate_with_low_stale_rate_beats_small_estate_with_high_rate():
    """The A/B inversion. Written first; it must FAIL against v4.2.0."""
    #   Vendor A:   4 hosts,   2 stale  ->  50% failure rate
    #   Vendor B: 900 hosts,   9 stale  ->   1% failure rate
    # Before:  A -16,  B -72   (B scores worse, wrongly, by ~4.5x)
    # After:   A worse than B
    assert posture(vendor_a) < posture(vendor_b)

def test_one_of_one_failure_is_not_scored_as_one_hundred_percent():
    """The alpha/beta prior earns its place here."""

def test_a_single_severe_finding_is_not_diluted_by_a_large_estate():
    """The kappa floor earns its place here."""
```

#### Steps

1. **Create `backend/app/scoring/exposure.py`.** Pure functions, no config reads, so the curve is inspectable and unit-testable in isolation — the same discipline [modifiers.py](../backend/app/scoring/modifiers.py) already follows.

   ```
   r̂_s = (f_s + α_s) / (D_s + α_s + β_s)          # beta-binomial posterior mean
   g_s = λ_s·r̂_s + (1 − λ_s)·min(1, f_s/κ_s)      # blend rate with an absolute floor
   ```

   `α/β` stop a 1-of-1 failure reading as 100%. `κ_s` preserves an absolute component so a large vendor cannot dilute a genuinely severe finding to nothing.

2. **Carry the denominator on the finding.** Add `denominator: int | None` to `NormalizedFinding` ([normalize.py:29-65](../backend/app/scoring/normalize.py#L29-L65)) and a `_denominator_of(finding)` helper beside `_count_of`. For `stale_hosts` the denominator is the sibling `subdomain_estate` count from the same `CollectorResult`.

   > **Design note.** `normalize_one` currently sees one `Finding` at a time. Pairing `stale_hosts` with `subdomain_estate` needs either (a) the collector to put both counts on the `stale_hosts` finding's `value` dict — *simplest, do this*; or (b) a normalize pass with result-level context. (a) is a three-line collector change and keeps the normalizer pure.

3. **`ct_collector.py`** — add `"denominator": len(subdomains)` to the `stale_hosts` finding's `value`. One line, no new network calls.

4. **Retire `count_bands` for `stale_hosts`.** It becomes a rate. Add an `exposure:` block to `scoring.yaml` with per-signal `α`, `β`, `λ`, `κ` and rate→severity thresholds.

5. **⚠️ Loader trap** — add `"exposure"` to `_ENGINE_READS` ([scoring_config.py:39-55](../backend/app/scoring_config.py#L39-L55)) **in the same commit**, with a comment naming the reader. The app will not start otherwise.

6. **`subdomain_estate` stops being scored** and becomes the denominator only. Set its bands to `informational`, delete its `reasons:`/`actions:` entries (Correction 5 applies again), and keep it in the signal list so `planned_signal_count()` holds at 27.

7. **`_COUNT_SIGNALS`** ([normalize.py:26](../backend/app/scoring/normalize.py#L26)) — remove `stale_hosts`; it now routes through `exposure.py` rather than `count_band`.

#### Expected corpus movement — substantial and intended

All five vendors are large, so all five should **gain** posture in `digital_footprint_assets` (currently 19.0–31.0 penalty). If a corpus vendor gets *worse*, either its stale rate is genuinely high or the denominator is wrong — investigate before re-goldening.

#### Phase 2A exit criteria

- [ ] The A/B inversion test passes (and demonstrably failed before)
- [ ] The prior and floor tests pass
- [ ] `digital_footprint_assets` penalty falls for the large corpus vendors, with per-vendor written justification
- [ ] `python -m tests.regolden` diff reviewed and committed

### Phase 2B · The nine signals that need collector fan-out

This is the part the source plan understates. `tls_version`, `cert_validity`, `hsts`, `csp`, `x_frame_opts` currently probe **one host** — the apex domain. There is no denominator to recover because there is no fleet being measured.

#### Steps

1. **Decide the asset scope, and write it down.** From CT you have a subdomain list ([ct_collector.py:149](../backend/app/collectors/ct_collector.py#L149)). Which of them do you probe? Options, in increasing cost:
   - apex + `www` + any name in the vendor's own MX/SPF records (cheap, low value)
   - a sample of *N* live names, resolved first, sampled deterministically by hash so results are reproducible (**recommended starting point**)
   - the full estate (expensive; hostile to the "politeness is not optional" position)

   The sample size and selection rule **must be published** — it is the denominator, and per the report *attribution error is the dominant source of vendor disputes with external ratings*.

2. **Multi-tenant detection, before computing `D_s`.** Non-negotiable — without it your best-architected SaaS vendors bottom out. Detect naming regularity, shared wildcard certificates (`wildcard_seen` is **already carried** at [ct_collector.py:61](../backend/app/collectors/ct_collector.py#L61)) and uniform infrastructure fingerprints; exclude those names from **both** the denominator and the finding counts.

3. **Liveness resolution before probing.** CT shows certificates *issued*, not hosts *live* — the collector's own docstring says so ([ct_collector.py:12-14](../backend/app/collectors/ct_collector.py#L12-L14)). Probing dead names inflates `D_s` and *flatters* the vendor. Resolve first; count only what answers.

4. **Rate limiting and runtime.** `RateLimiter` exists ([ratelimit.py](../backend/app/ratelimit.py)) and collectors already retry with backoff. Fanning out to *N* hosts multiplies every collector's runtime by *N*. Budget it: the corpus suite already takes 299 s at *N*=1.

5. **Re-scope `tls_collector` and `headers_collector`** to accept a host list, returning per-host findings plus a `denominator`. Preserve the single-host path for cheap re-scores and disputes.

6. **Apply to the 10 Class-P signals only:** `cert_validity`, `tls_version`, cipher findings, `hsts`, `csp`, `x_frame_opts`, `nvd_cve`, `kev_listed_cve`, `stale_hosts`, `subdomain_estate`. **Class-B signals keep binary treatment** — DMARC is one decision at the apex, not a rate. `dmarc`, `spf`, `dkim`, `dnssec`, `caa` are all Class-B.

7. **`nvd_cve` / `kev_listed_cve` have no host denominator at all** — they are keyword matches against product names. **Leave them un-normalized and say so on the card.** Per the source plan's own stop-condition: *better to leave a signal un-normalized and say so than to divide by a denominator you cannot defend under dispute.*

#### The critical-ceiling interaction — an easy thing to break

`cert_validity` is the **only** `ceiling_auto_signal` and the **only** `never_decays` signal. Once it becomes a rate, "an expired certificate" becomes "3% of certificates expired". **Decide explicitly what arms the ceiling:**

- any expired cert on any probed host (current behaviour, generalised — noisiest)
- an expired cert on the **apex** specifically (**recommended** — preserves today's semantics exactly, and the apex is the asset a buyer actually transacts with)
- a rate above a threshold (defensible, but a new policy judgement that needs its own basis)

Whichever you choose, `test_corpus.py` pins `critical_ceiling_applied` for all five vendors — the corpus will tell you if you changed it by accident.

#### Phase 2B exit criteria

- [ ] Asset scope and sampling rule documented and published
- [ ] Multi-tenant vendors in the corpus no longer floor
- [ ] `D_s` published per signal on every card
- [ ] Signals without a defensible `D_s` explicitly marked un-normalized
- [ ] Ceiling semantics decided in writing and asserted by test
- [ ] Corpus re-goldened with per-vendor justification
- [ ] **Ablation re-run — firmographics-only AUC should now be materially worse than the full model. That is the proof.**
- [ ] Spearman ρ (posture vs. size) from Step 0.4 has fallen

### Rollback

**Harder than Phase 1.** Config revert restores the arithmetic, but collector schema changes affect stored evidence. Keep `exposure.py` behind a `scoring.yaml` flag (`exposure.enabled: false`) for the first release so a revert is a one-line config change, not a redeploy. Stored evidence is append-only and survives either way.

### Stop and reconsider if

`D_s` is unavailable or unreliable for a signal. Better to leave that signal un-normalized and say so than to divide by a denominator you cannot defend under dispute.

---

## Phase 3 · Aggregation

**Duration:** 2–3 weeks · **Risk:** medium · **Changes scores:** yes

Fixes defect #1 — hygiene trivia outranking active exploitation. [report.md VIII.2](report.md#viii2-aggregation--diminishing-returns-or-log-odds) records that the sources propose two incompatible fixes.

### The arithmetic, computed rather than quoted

The source plan says twelve hygiene failures drop from 56 to ≈15.9. **Verified — but only if you do 3a and 3b together.** Computed:

| Configuration | 4 Medium + 8 Low | vs. one Critical | Ratio |
|---|--:|--:|--:|
| **Current** (flat, 8/3) | **56.00** | 40 | 0.71 : 1 ✗ *trivia wins* |
| 3a only (λ=0.7 DR, old ladder) | 22.53 | 40 | 1.78 : 1 |
| 3b only (flat, new 6/1.5) | 36.00 | 50 | 1.39 : 1 |
| **3a + 3b** (λ=0.7 DR, new ladder) | **16.33** | 50 | **3.06 : 1** ✅ |

> **Therefore 3a and 3b ship together.** 3a alone reaches only 1.78:1, which does not deliver the report's "better than 3:1". Sequencing them as separate releases publishes an intermediate state that satisfies neither the old model nor the new.

**In posture points** (÷ `penalty_divisor` = 4.0, per [Correction 1](#1-penalty_divisor-is-40-not-7--every-posture-impact-number-changes)): twelve hygiene failures fall from **14.0 → 4.08** posture points; one Critical rises from 10.0 → **12.5**.

### 3a · Diminishing returns within category

```
CategoryPenalty(c) = Σᵢ pᵢ · λ^(rankᵢ − 1)      λ = 0.7, rank by descending pᵢ
```

**Correct ordering restored without introducing category weights**, which preserves the emergence principle while killing the correlated-stacking bug.

#### Steps

1. **`engine.py`** — this is the one structural change. Today, [line 143](../backend/app/scoring/engine.py#L143) accumulates `cat_penalty[cat] += penalty` inside the per-`(cat, sig)` loop. Diminishing returns needs **all** of a category's penalties before it can rank them.

   Restructure: collect `(cat, sig) → penalty` into a dict, then apply the transform per category **after** the loop closes at [line 159](../backend/app/scoring/engine.py#L159).

   > ⚠️ **Preserve the bookkeeping.** `rep.effective_penalty` ([line 147](../backend/app/scoring/engine.py#L147)) is what makes stored receipts reconstruct the published score. After the transform, `effective_penalty` must be the **post-discount** value or the receipts visibly stop adding up — which is the exact defect the comment at [lines 60-64](../backend/app/scoring/normalize.py#L60-L64) says these fields exist to fix. Assert it.

2. **`scoring.yaml`** — add `aggregation.within_category: {method: diminishing_returns, lambda: 0.7}`.

3. **⚠️ Loader trap** — `aggregation` is currently in `_DOCUMENTATION_ONLY` ([scoring_config.py:61](../backend/app/scoring_config.py#L61), *"multi-asset weakest-link — declared; the PoC scores one asset"*). **Move it to `_ENGINE_READS`.** If you write real config under a documentation-only key, the loader will not complain — and that is worse: you get a live-looking rule that scores nothing, which is precisely the drift the guard exists to catch.

### 3b · Widen the severity ladder

| Level | Now | After | Why |
|---|--:|--:|---|
| Critical | 40 | **50** | Should approach unrecoverable alone |
| High | 20 | **20** | Unchanged |
| Medium | 8 | **6** | Slight compression reduces mid-band stacking |
| Low | 3 | **1.5** | Should be a nudge, not a lever |
| Informational | 0 | **0 → routes to Confidence** | An informational observation *is* evidence of coverage |

**Critical:Low moves from 13.3:1 to 33.3:1** (verified). At 13:1, fourteen trivia outrank one actively-exploited vulnerability.

#### Steps and traps

1. **`scoring.yaml` `severity_penalties`** — the four numbers.
2. **`_validate`** ([scoring_config.py:310](../backend/app/scoring_config.py#L310)) requires `critical ≥ high ≥ medium ≥ low ≥ 0`. `50 ≥ 20 ≥ 6 ≥ 1.5 ≥ 0` ✅ passes.
3. **⚠️ `low: 1.5` is a float.** `penalty_for` casts with `float()` so the engine is fine, but check every test asserting an integer penalty. `test_scoring.py` is the place to look.
4. **Ceiling interaction:** a Critical at 50 with `penalty_divisor` 4 costs 12.5 posture — a vendor at 100 lands at 87.5, still far above the 49 ceiling. The ceiling continues to do the real work for `cert_validity`. Unchanged, but confirm by test.
5. **"Informational routes to Confidence"** is a *new mechanism*, not a renaming. Today informational findings already count toward coverage via `covered_by_cat` ([engine.py:162-164](../backend/app/scoring/engine.py#L162-L164)) — so this line may already be satisfied. **Verify before building anything.**

### 3c · Root-cause deduplication

> **One remediation ticket, one penalty.** If fixing one thing clears four findings, it was one finding.

| Cluster | Rule | Implementation note |
|---|---|---|
| KEV / CVE / CVSS / EPSS | Precedence **KEV > EPSS > CVSS**. One penalty; others are modifiers | Both are already `frequency_exempt`, so the bag-collapse is half-built |
| TLS version / ciphers | Score the protocol finding; ciphers add an increment only beyond the version | `tls_version` bands are `tls_10_or_11` / `only_tls_12` / `tls_13` |
| CSP / X-Frame-Options | `frame-ancestors` satisfies XFO. Accept either, never penalise twice | Needs the CSP **value** — [headers_collector.py:58](../backend/app/collectors/headers_collector.py#L58) already carries it in `value["value"]` ✅ |
| Subdomains / shadow assets / CT | One footprint model, several views | Largely delivered by Phase 2A |

The existing `(category, signal)` worst-of collapse ([engine.py:136](../backend/app/scoring/engine.py#L136)) already dedupes *within* a signal. 3c dedupes *across* signals — a genuinely new grouping layer. Model it as a `root_cause:` map in `scoring.yaml` (another `_ENGINE_READS` entry) rather than a hardcoded set, so it stays arguable without a redeploy.

### Ghost ceiling ramp — ship the cheap half here

Costs nothing and preserves the current axiom exactly (Confidence bounds what you assert, never the arithmetic):

```
< 40%    → no publish; "Insufficient Evidence" (explicitly ADVERSE); manual review required
40–60%   → publish, ceiling 80
60–75%   → publish, ceiling 90
75–90%   → publish, ceiling 97
≥ 90%    → publish, ceiling 100
```

The `< 40%` rung **already exists** — `refuse_below: 0.4` at [engine.py:204](../backend/app/scoring/engine.py#L204). What is new is the graduated ceiling above it and the adverse framing.

**Both proposals agree on the governance point, and it costs nothing to do immediately: publish "Insufficient Evidence" as an explicitly adverse state, not a neutral absence.** Procurement must not be able to read a Ghost as a pass. Check the frontend renders it that way — an adverse state displayed in neutral grey is not an adverse state.

### Deferred to Phase 7 — bounded log-odds

The log-odds reshape (`L̃ = c^τ·L + (1−c^τ)·L_peer`, `Posture = 100·(1−σ(L̃))`) is statistically better and solves saturation properly. Deferred because it **requires dense cohort medians to supply `L_peer`**, and those do not exist — `min_cohort_n` is **1**, with synthetic peers standing in.

### Tests to write first

```python
def test_one_critical_kev_outranks_twelve_hygiene_failures():
    """The §VI.2 inversion, asserted directly. Must FAIL before 3a+3b."""

def test_monotonicity_remediation_never_loses_points():
    """A vendor that fixes a finding must never score worse.
    The diminishing-returns transform is THE place this breaks: re-ranking after
    removal can, done wrong, promote a survivor into a higher-weighted rank."""

def test_effective_penalty_sums_to_the_published_category_penalty():
    """Receipts must reconstruct the score after the DR transform, not merely gesture at it."""

def test_severity_ladder_is_monotonic_after_widening():
    """Guards the loader invariant at scoring_config.py:310."""
```

**Write the monotonicity test with generated inputs, not three hand-picked cases.** It is the one property most likely to break silently and least likely to be caught by the 5-vendor corpus.

### Exit criteria

- [ ] The §VI.2 inversion is gone: one Critical KEV outranks twelve hygiene failures, asserted at ≥ 3:1
- [ ] **Monotonicity test passes** over generated inputs
- [ ] `effective_penalty` reconciliation test passes
- [ ] `aggregation` moved from `_DOCUMENTATION_ONLY` to `_ENGINE_READS`
- [ ] Bottom-quartile discrimination measured; noted as improved but not solved until Phase 7
- [ ] Ghost ramp shipped; "Insufficient Evidence" renders as adverse in the UI

---

## Phase 4 · Gates

**Duration:** 1 week · **Risk:** low · **Changes scores:** no — changes outcomes

Everything in the model is currently arithmetic, so everything is fungible. A vendor at 100 with one actively-exploited internet-facing vulnerability publishes at 60 and clears a "≥50" threshold.

**Independent of Phases 1–3.** Can run in parallel throughout.

### Current gate machinery

Two gates exist, both in `ScoringEngine.score`:

| Gate | Where | Trigger |
|---|---|---|
| `entity_ambiguous` | [engine.py:77-85](../backend/app/scoring/engine.py#L77-L85) | `resolution_confidence < 0.5` |
| `sanctions` | [engine.py:98-103](../backend/app/scoring/engine.py#L98-L103) | any `is_sanctions` finding |

Both route to `_blocked()` ([engine.py:307](../backend/app/scoring/engine.py#L307)), which emits `posture=None`. That is the pattern to extend.

### Steps

1. **Generalise `_blocked` into a gate list.** Today each gate is bespoke inline code. Add a `gates:` evaluation pass over normalized findings, driven by config, so a new gate is a YAML edit — consistent with the file's own stated philosophy (*"the model is the product, and it lives in config so it can be argued with a client in a room without a deploy"*).

2. **Add the four gates**, each with a named basis:

   | Gate | Trigger | Basis needed |
   |---|---|---|
   | KEV past CISA due date | on an internet-facing authenticated or data-bearing asset | CISA BOD 22-01 due dates — **check `kev_collector` carries the due date; it may not** |
   | Legal entity dissolved / struck off | already `entity_status` at `high` severity — promote to gate | ASIC / Companies House register status |
   | No valid TLS on a data-bearing endpoint | distinct from expired — *absent* | Depends on Phase 2B host scope |
   | Ownership or attribution unresolvable | extends `entity_ambiguous` | Already partly present |

3. **⚠️ `_validate` hard-codes the sanctions invariant** ([scoring_config.py:317-321](../backend/app/scoring_config.py#L317-L321)): `gates.sanctions.behaviour` must equal `"block"`. Preserve this exactly when generalising — it is a legal position (s16(7)), not a default.

4. **Every gate needs a `basis:`.** Follow the `industry_profiles` precedent that Phase 1a deletes: the *validation discipline* was right even though the mechanism was wrong. Add a `_validate_gates` requiring a non-empty `basis` per gate.

5. **Route gated vendors to the adjudication queue, not to a low score.** Check `recommend.py` and the API surface handle `posture=None` distinctly from `posture=0`. `_blocked` already sets `blocked_reason`; make sure it reaches the card.

6. **The `critical_ceiling` (49) stays as-is** for directly-observed criticals. A gate is stronger: it emits no score at all.

7. **The Tier matrix** ([report.md VII.8](report.md#vii8-the-new-dimensions)) drives what a gate means per criticality tier — see Phase 5d.

### Exit criteria

- [ ] Each gate has a named basis, enforced at load as the sanctions gate is
- [ ] Gated vendors route to adjudication, not to a low score — asserted by test
- [ ] `gates.sanctions.behaviour == "block"` invariant preserved
- [ ] Tier matrix drives per-tier gate consequences
- [ ] A gated vendor is visually distinct from a zero-scoring vendor in the UI

---

## Phase 5 · Context outputs

**Duration:** 3–4 weeks · **Risk:** low · **Changes scores:** no — adds dimensions beside them

Nothing here touches Posture. This is where every firmographic the research question asked about legitimately lives.

### 5a · Assurity

Partially built — [targets.py](../backend/app/targets.py) and the `target_maturity` block ([benchmarks.yaml:191](../benchmarks.yaml#L191)) established the pattern: positive-only, instrument-cited controls with an attainability rule. Read [targets.py:1-30](../backend/app/targets.py#L1-L30) before designing Assurity; it already articulates the three disciplines you need.

```
Assurity = 100 · σ( A₀ + Σ_j v_j · valid_j · scope_j − Σ_k γ_k · ComplianceGap_k )
```

**Absence never subtracts.** A vendor with no certifications has low Assurity, not bad Posture. **This is the single most important structural fix for demographic fairness in the model**, and it is where the Phase 1b relocations land.

Three disciplines to carry over verbatim from `targets.py`:

- a signal never **checked** is not a signal **failed** — it leaves the denominator
- a control that could not yet **exist** at this vendor's age leaves the denominator, and is **disclosed by name** rather than dropped silently
- below `min_controls` observed, publish nothing

**Unblocks Phase 1b-ii.** Once Assurity ships, the six signals parked at `informational` gain positive credit. Schedule 1b-ii immediately after.

### 5b · Compliance Gap

Where a vendor asserts (or is bound by) framework `F` and is observed failing control `c ∈ C(F)`, emit a cited finding. *"Vendor asserts PCI DSS compliance and negotiates TLS 1.0"* is **not a more severe TLS finding** — it is a distinct, high-signal finding about the reliability of the vendor's own attestations.

**This is where the deleted `industry_profiles` sector expectation goes.** Both `basis:` strings from Phase 1a step 8 land here as framework definitions:

- `financial_services` → APRA CPS 234 · CPS 230 (in force 1 Jul 2026)
- `healthcare` → Privacy Act 1988 APP 11 · My Health Records Act 2012 · OAIC NDB CY2025

Gaming it means dropping the claim, which is itself informative.

### 5c · Expectation Gap

```
EG = Posture − E[Posture | cohort]
```

The widening ladder in [benchmark.py](../backend/app/benchmark.py) already computes the cohort and already discloses `n` and the rung reached. **This is the answer to the entire research question** and it needs no arithmetic change:

> *"Posture 68. Median for financial services, 1,000–10,000 staff, ANZ (n=14): 87. **This vendor sits 19 points below its peer group and in the bottom decile of it.** The gap is driven by absent DMARC (95% of Fortune 500 peers have it) and by TLS 1.0 on 8 of 340 checked hosts."*

Note that second clause — *"8 of 340 checked hosts"* — is a **Phase 2B output**. Without host fan-out the sentence can only say "TLS 1.0 on the apex". Plan the copy accordingly.

**Prerequisite: this is only honest once cohorts are real. See Phase 6.**

### 5d · Impact / Inherent Risk Tier

`criticality` is already client-supplied and already reaches [recommend.py:41](../backend/app/scoring/recommend.py#L41) — it just never reaches a tier (today it only sets `high_stakes` at [line 76](../backend/app/scoring/recommend.py#L76)). Formalise the Tier matrix and drive review cadence and gate consequences from it.

This is the **Inherent Risk** layer, and it runs on a different clock from Posture: it changes only when the relationship or the vendor's fundamentals change, where Posture refreshes continuously. **Residual Risk** (Posture × Tier) is a **derived matrix view, not a dimension** — a lookup over two already-published inputs. Build it as a rendering concern, not a stored score, so nobody can dispute a cell instead of an input.

### 5e · Continuity — flags, not a score

**Duration:** 1 week · **Risk:** low · **Changes scores:** **yes** — removes misplaced penalty

The destination for the Class-C signals leaving Posture. **This is a relocation, not a build** — every signal and collector already exists.

#### What is wrong today, measured

| Signal | Band | Penalty | What it actually measures |
|---|---|--:|---|
| `entity_status` | `entity_inactive` | **20.0** | Companies House maps `liquidation`, `receivership`, `administration`, `insolvency-proceedings` here ([companies_house_collector.py:150-154](../backend/app/collectors/companies_house_collector.py#L150-L154)) |
| `entity_status` | `registration_lapsed` | 3.0 | Fires on **myob** and **slack** in the corpus |
| `entity_existence` | `entity_dissolved` | 20.0 | Going-concern, not security |
| `entity_maturity` | `young_2_5` / `startup_lt_2` / `new_lt_1` | 3.0 | **Founding date** — which the "does not do" table forbids |
| `domain_registration` | `domain_recent` / `domain_new` | 3.0 | Company-age proxy. Already tagged `subcategory="business_continuity"` at [rdap_collector.py:105](../backend/app/collectors/rdap_collector.py#L105) |

**A vendor entering administration currently loses 20 points of *technical security posture*.** That is a category error, and it is the single clearest one left in the model.

#### Steps

1. **Move the four signals out of `categories.business_financial_stability`** in `scoring.yaml`, together with their `reasons:` and `actions:` entries (Correction 5 applies — orphaned entries break the loader).
2. **⚠️ The category count drops 7 → 6.** `penalty_divisor` is **4.0**, tuned against seven categories. Six categories cap at 600 penalty points; 600/4 = 150, so posture still reaches 0 and the scale survives. **Verify this rather than assuming it** — see the divisor table under Phase 3 if further categories move.
3. **⚠️ `planned_signal_count()` drops 27 → 23.** Every vendor's confidence rises for no evidential reason. Either accept and disclose it, or move to **per-axis confidence** (Posture confidence over its own signals, Continuity over its own) — the more honest option, and a prerequisite if more categories relocate later.
4. **Emit Continuity as structured flags**, never a 0–100 axis:

   > *"In administration — Companies House company status, retrieved 2026-07-29."*

5. **`entity_maturity` is also the confidence assurance signal** ([scoring.yaml](../scoring.yaml) `confidence.assurance_multiplier.signal`). It currently hits **both** axes — a posture penalty *and* a confidence multiplier (curve 0.96–1.04). Removing the penalty leaves the multiplier, which is where the engine docstring at [engine.py:169-171](../backend/app/scoring/engine.py#L169-L171) always said age belonged. **Confirm the multiplier still resolves once the signal no longer penalises.**
6. **Phase 4 interaction:** `entity_dissolved` is slated to become a **gate**. Decide which wins — a dissolved entity is arguably both a gate (emit no score) and a Continuity flag. Recommended: gate for `dissolved`, Continuity flag for `lapsed` / `administration`.

#### Why flags and not a number

1. The sources establish these signals must *leave* Posture; they do not specify an arithmetic to replace them. A score would be invention wearing the report's authority.
2. Four registry bands cannot support hundred-point precision.
3. A cited register fact carries the same legal footing as every other published observation. A *derived* distress index is credit-rating territory and defamation-adjacent when wrong.

#### Tests to write first

```python
def test_administration_does_not_reduce_posture():
    """A vendor in administration has a continuity problem, not worse TLS."""

def test_company_age_never_reaches_a_penalty():
    """entity_maturity may move confidence. It may not move posture."""

def test_continuity_flags_carry_a_citation_and_a_retrieval_date():
    """An uncited going-concern assertion is the one thing this axis must never publish."""
```

#### Exit criteria

- [ ] No going-concern signal carries a posture penalty
- [ ] Every Continuity flag carries a source and a retrieval date
- [ ] Confidence denominator change disclosed, or per-axis confidence shipped
- [ ] `entity_maturity` assurance multiplier still resolves
- [ ] Corpus re-goldened — **expect myob and slack to gain 3 posture points** (`registration_lapsed`)

---

## Phase 6 · Make the cohorts real

**Duration:** ongoing · **Risk:** low · **Changes scores:** no

Phases 5c and 7 both depend on cohort medians that can be trusted. Today they cannot be.

| Issue | Current state | Target |
|---|---|---|
| `min_cohort_n` | **1** ([benchmarks.yaml:35](../benchmarks.yaml#L35)) — *"set to 1 for live demo/interactive use"*. Code default is 8 ([benchmark.py:108](../backend/app/benchmark.py#L108)) | 8, once the pool supports it |
| Synthetic fallback | 6 hard-coded postures `[65,72,78,83,89,94]` ([benchmark.py:370](../backend/app/benchmark.py#L370)), reported as `n=6` | Removed, or labelled so `n` cannot read as six real companies |
| Peer pool | Whatever this deployment has scored | Seeded across 10 sectors × 4 regions × size bands |

**Good news: this is a YAML change, not a code change.** The threshold is already tunable and the code default is already 8.

### The disclosure defect worth fixing first, independently of everything else

A reference-baseline card reports `n=6` alongside the caveat *"Industry Reference Baseline: Benchmarked against sector peer baseline metrics"* ([benchmark.py:457-459](../backend/app/benchmark.py#L457-L459)). **A reader sees `n=6` and thinks six real companies.** The `is_synthetic` flag already exists at [benchmark.py:438-443](../backend/app/benchmark.py#L438-L443) — the fix is to consume it, which is a small change with an outsized honesty return:

- suppress `n` entirely when `is_synthetic`, **or**
- state plainly on the card that these are not real peers

**Do this in the current sprint.** It is independent of every other phase and it is the one item here that is actively misleading a reader today.

### Seeding

```bash
python -m app.seed_cohorts --list                  # what would be scored, by sector
python -m app.seed_cohorts --all --concurrency 2   # everything, politely
```

**115 real vendors** (verified count) across 10 sectors, deliberately spread across ANZ / North America / UK-EU / APAC and across size bands. **Politeness is not optional** — every collector queries someone else's free service, and a seeding run multiplies that by 115. The default concurrency of 1 is the right setting; `--concurrency 2` is the impatient maximum.

**Cohort maths.** 115 vendors ÷ (10 sectors × 4 regions × 3 size bands) = 120 cells. **Seeding alone will not reach `min_cohort_n: 8` in most cells** — it fills the widening ladder's upper rungs (sector-only, sector+size) rather than the exact cohort. Set expectations: Phase 6 is *ongoing* precisely because the pool grows with real client assessments, not with one seed run.

---

## Phase 7 · Bounded log-odds — the destination

**Duration:** 3–4 weeks · **Risk:** medium-high · **Changes scores:** substantially · **Blocked on Phase 6**

```
z_s = w_sev(s) · a(s) · φ(s) · m(s) · g_s · κ_cat(s)
L   = L₀ + Σ_s z_s
L̃   = c^τ·L + (1 − c^τ)·L_peer          τ ≈ 1.5
Posture = 100 · (1 − σ(L̃))
```

Solves what Phase 3 only partially addresses:

- **Never floors.** Three Criticals at the new ladder reach 150 points against a 100-point scale, so a vendor with three and a vendor with fifteen both publish as 0 — all discrimination lost exactly where triage matters most. Note `posture = max(0.0, …)` at [engine.py:187](../backend/app/scoring/engine.py#L187) is the floor in question, and the `min(p, max_score)` cap at [line 186](../backend/app/scoring/engine.py#L186) is a partial mitigation already present.
- **Never saturates at the top.** `L₀` replaces the unjustified "start at 100" prior — the engine docstring's *"Every vendor starts at 100"* becomes a fitted constant rather than an assumption.
- **Makes the Ghost cliff unnecessary.** At `c = 0.3`, roughly 84% of the estimate is the cohort prior. **A vendor who becomes unmeasurable gets their cohort's median, not a free pass** — which removes the gaming vector entirely, because hiding stops being better than being average.

### Preconditions — verify, do not assume

- [ ] Phase 6 complete: `min_cohort_n ≥ 8` with **real** peers in the cohorts you will publish against
- [ ] `_synthetic_baseline_peers` removed or hard-excluded from `L_peer` — feeding `[65,72,78,83,89,94]` into a shrinkage prior would shrink every thin-cohort vendor toward six invented numbers
- [ ] Phase 3 monotonicity tests still green — they must be re-run against the new transform, not assumed to carry over

This is a **second release**, not a continuation of the first. It changes the meaning of the number, so it needs its own version, its own notice period, and its own diff.

---

## Sequencing and dependencies — corrected

```
Phase 0  Instrument (incl. labels + git) ───────────────────┐
              │                                             │
              ▼                                             │
Phase 1a Delete industry_profiles                           │
              │  (HARD prerequisite — loader)               │
              ▼                                             │
Phase 1b-i Stop penalising  ──►  1c Merge contactability    │
              │                                             │
              ├──────────────────────────┐                  │
              ▼                          ▼                  │
Phase 2A Stale-host rate          Phase 5a/b  Assurity,     │
   (free, 1 week)                 Compliance Gap            │
              │                          │                  │
              ▼                          ▼                  │
Phase 2B Collector fan-out        Phase 1b-ii Positive      │
   (6-10 weeks, the real work)      credit  ◄───────────────┘
              │
              ▼
Phase 3  Aggregation 3a+3b TOGETHER + ceiling ramp
              │
              ▼
Phase 4  Gates  (independent — can start any time)
              │
              ▼
Phase 6  Real cohorts ─────────────► Phase 5c Expectation Gap
              │
              ▼
Phase 7  Log-odds + shrinkage
```

### Dependencies that are genuinely hard

| Dependency | Why | Source plan |
|---|---|---|
| **1a → 1b-i** | `_validate_industry_profiles` requires promoted bands to be penalising | Implied by ordering, not stated as hard |
| **5a → 1b-ii** | No bonus mechanism exists until Assurity does | **Shown backwards** |
| **3a + 3b together** | 3a alone reaches 1.78:1, missing the ≥3:1 target | Presented as separable |
| **6 → 7** | No trustworthy `L_peer` without real cohorts | ✅ correct |
| **6 → 5c** | Same reason | ✅ correct |
| **0.1 (git) → everything** | `regolden` diffs are the evidence for every later phase | Not mentioned |

**Phases 1, 4, 5 and 6 do not change published posture** and can run in parallel with the others if you have the hands. Phase 4 is fully independent. The Phase 6 `n=6` disclosure fix should ship this sprint regardless of everything else.

---

## Validation, running throughout

Applies from Phase 2 onward, not at the end.

| Test | What it catches | Runnable today? |
|---|---|:--:|
| **Firmographics-only ablation** | Whether you built a security rating or a size classifier. Re-run after Phase 2 — the AUC gap should widen | ❌ needs Step 0.3 labels |
| **Firmographics-only R²** | The same question, label-free | ✅ needs the seeded pool |
| **Within-cohort discrimination, never pooled** | Pooled AUC is inflated by the model's ability to detect size, which correlates with disclosure probability. You would be measuring your own selection bias and reporting it as accuracy | ❌ needs labels + Phase 6 |
| **Calibration, not just ranking** | A model that orders well but calibrates badly produces risk-acceptance decisions systematically wrong in magnitude | ❌ needs labels |
| **Monotonicity** | A vendor that remediates must never lose points. Phase 3's DR transform is where this breaks | ✅ **write it now** |
| **Stability** | Re-cohorting must not silently move published scores. Version and diff | ✅ |
| **Frozen corpus** | Every phase re-goldens deliberately, with written justification per moved vendor | ✅ |
| **Loader boot check** | Every config edit; catches all five Phase-1 loader traps at once | ✅ **add to CI** |

**The corpus is 5 vendors, all A/B grade, all large.** It cannot catch a regression that only affects small vendors, low scorers, or Ghosts. Extend it with at least: one Ghost (confidence < 0.4), one gated vendor, one small vendor, one bottom-quartile scorer. **Do this in Phase 0** — every phase after leans on the corpus as its evidence, and right now the corpus cannot see the failures these phases are meant to fix.

---

## Governance obligations that attach as you go

Publishing scores about other companies carries duties, and several of these phases increase them.

| Trigger | Obligation |
|---|---|
| Phase 1 changes what signals cost | **Notice before the change**, not after |
| Phase 1c drops `planned_signal_count` to 26 | Every vendor's confidence rises slightly for no evidential reason. Disclose, or take the `informational` route instead |
| Phase 2 introduces a denominator | **Publish it**, including the sampling rule and multi-tenant exclusions. Attribution and denominator disputes will be a top-two dispute category |
| Phase 2B changes what "checked" means | A vendor's score can move because you probed more hosts, not because anything changed. Version the asset-scope rule and diff it |
| Phase 3 changes the ladder | Version it. Label expert-set severities as **expert judgment until calibrated** — most are, and that is fine if declared |
| Phase 5c publishes cohort placement | **Make cohort assignment disputable.** Misclassification is the other top-two dispute category |
| Phase 6 changes `min_cohort_n` | A cohort redefinition can move many scores overnight with no change in any vendor's behaviour. Notice and diff |
| Phase 7 changes the scale's meaning | New model version, new notice period, side-by-side publication during transition |

The dispute machinery already exists — `test_disputes.py` and `_apply_dispute` ([engine.py:259](../backend/app/scoring/engine.py#L259)) support `nullify` and `mitigate` against a `(signal, band_key)` pair. **Phase 2 breaks this shape**: a rate-based finding's band is derived, so a dispute keyed on `band_key` may no longer match a stable string. Check `_apply_dispute` against the new band keys in Phase 2A, and extend disputes to cover *denominator* challenges — "you counted 340 hosts, we operate 40" is the dispute Phase 2 invites, and there is currently no way to file it.

### One scheduled change to record now rather than discover as drift

**CA/Browser Forum Ballot SC-081v3** compresses maximum certificate lifetimes to **100 days from March 2027** and **47 days from March 2029**. As lifetimes compress, an expired certificate stops meaning *"someone forgot"* and starts meaning *"this vendor has no certificate lifecycle automation"* — a materially stronger inference.

**Schedule the weight increase at both boundaries and announce it in advance.** Concretely: put a dated entry in `scoring.yaml` alongside `cert_validity` now, while the reasoning is fresh. `cert_validity` is the only ceiling-arming signal, so this change has more reach than its size suggests.

---

## What this plan deliberately does not do

| Not doing | Why |
|---|---|
| Firmographic severity multipliers | Rejected on five independent grounds ([report.md VII.7](report.md#vii7-the-twelve-candidate-mechanisms-scored)) |
| Cohort-scaled severity tables | Contested 3–2 across the sources ([report.md VIII.1](report.md#viii1-may-severity-be-cohort-scaled--the-sources-split-32)). The Expectation Gap expresses the same insight and keeps the score comparable. **This is the correct second choice if the Expectation Gap proves insufficient — a bare multiplier never is** |
| Baseline maturity curves as f(company age) | No published evidence. Not one of Bitsight, SecurityScorecard, RiskRecon, Cyentia, NIST, ENISA or CISA scores by founding date |
| Any geography or nationality adjustment in Posture | Weakly predictive, ethically fraught, legally exposed. Surface jurisdiction as a disclosed attribute instead |
| Cross-tenant peer pooling | A contractual question before an engineering one |
| Probing non-public endpoints for a bigger denominator | The legal position in [tls_collector.py:1-12](../backend/app/collectors/tls_collector.py#L1-L12) depends on the request being identical to an ordinary browser visit. Phase 2B must not spend that |

---

## Effort summary — revised

| Phase | Weeks | Changes scores | Risk | Blocked by | Δ vs. source plan |
|---|--:|:--:|:--:|---|---|
| 0 · Instrument (+ git, + labels, + corpus extension) | **2–3** | no | none | — | +1 wk: labels are real work |
| 1a · Delete `industry_profiles` | 1 | yes (≈0 on corpus) | low | 0 | split out |
| 1b-i · Stop penalising | 1–2 | yes | low | **1a** | split; hard dep named |
| 1c · Merge `contactability` | 0.5 | yes | low | 1b-i | — |
| 1d · Category consolidation + divisor | **1–2** | **yes, everywhere** | medium | **1b-i + 5e** | **new — was unscheduled** |
| 2A · Stale-host rate | **1** | yes | medium | 1 | **new — free win** |
| 2B · Collector fan-out | **6–10** | **substantially** | **high** | 2A | +3–7 wks: was understated |
| 3 · Aggregation 3a+3b + ceiling ramp | 2–3 | yes | medium | 2A (2B preferred) | must ship together |
| 4 · Gates | 1 | no | low | — | independent |
| 5a/b · Assurity, Compliance Gap | 3–4 | no | low | 1 | — |
| 5e · Continuity relocation | **1** | **yes** — removes ~20 pts misplaced | low | 1 | **new — was undocumented** |
| 1b-ii · Positive credit | 0.5 | no | low | **5a** | **new — dep was inverted** |
| 5c · Expectation Gap | 1 | no | low | 6 | — |
| 5d · Impact / Tier | 1 | no | low | — | — |
| 6 · Real cohorts | ongoing | no | low | — | `n=6` fix: **now** |
| 7 · Log-odds + shrinkage | 3–4 | **substantially** | med-high | **6** | second release |

**Critical path: 0 → 1a → 1b-i → 2A → 3.** Roughly **8–11 weeks**, and it carries most of the value — 2A alone fixes the largest penalty line item for every corpus vendor. **2B is a separate 6–10 week programme** that should be planned and resourced as such rather than folded into "Phase 2". Phases 4, 5 and 6 run alongside. Phase 7 is a second release.

---

## The one-line summary per phase

| Phase | In one line |
|---|---|
| **0** | Prove what is broken before fixing it — and get labels, or admit you cannot prove it |
| **1a** | Take the sector opinion out of the arithmetic |
| **1b-i** | Stop charging vendors for not doing what almost nobody does |
| **1c** | Stop charging the same fact three times |
| **1d** | Make Posture only security, and fix the divisor so that means something |
| **2A** | Divide the one number you already have by the other number you already have |
| **2B** | Go and measure the estate you have been scoring by proxy |
| **3** | Stop letting a dozen missing headers outrank an actively-exploited vulnerability |
| **4** | Make the unforgivable findings unaveraged |
| **5** | Give every firmographic a legitimate home outside the score |
| **5e** | Stop charging a company in administration for bad TLS |
| **1b-ii** | Now that there is somewhere to put credit, give it |
| **6** | Make the peer group real enough to compare against — and stop `n=6` reading as six companies |
| **7** | Stop the scale saturating at both ends |

---

## Appendix A · Per-phase command reference

```bash
cd backend && source .venv/Scripts/activate     # Git Bash;  .venv\Scripts\Activate.ps1 in PowerShell

# --- after ANY scoring.yaml edit: does it still load? (catches all Phase-1 loader traps) ---
python -c "from app.scoring_config import load_scoring_config as L; c=L(); \
  print('OK', c.version, 'signals', c.planned_signal_count(), 'bands', len(c.penalising_bands()))"

# --- the corpus: the evidence for every phase ---
pytest tests/test_corpus.py -q                  # did anything move?
python -m tests.regolden                        # re-baseline (DELIBERATE)
git diff tests/fixtures/golden_scores.json      # <-- THIS DIFF IS THE CHANGE. Read it.

# --- targeted suites ---
pytest tests/test_scoring.py tests/test_scoring_config.py tests/test_actions.py -q   # Phases 1-3
pytest tests/test_benchmark.py tests/test_cohorts.py -q                              # Phases 5c, 6
pytest tests/test_disputes.py -q                                                     # Phase 2 band-key risk
pytest -q                                                                            # full: ~300 s

# --- end-to-end against a live vendor ---
python -m app.score_harness --domain atlassian.com --ref atlassian --name Atlassian

# --- Phase 6 ---
python -m app.seed_cohorts --list
python -m app.seed_cohorts --all --concurrency 2
```

## Appendix B · Config-key registration checklist

Every phase that adds a top-level `scoring.yaml` key must register it, or the app will not start ([scoring_config.py:449](../backend/app/scoring_config.py#L449)).

| Phase | Key | Action in `scoring_config.py` |
|---|---|---|
| 1a | `industry_profiles` | **Remove** from `_ENGINE_READS` (line 54) and delete the YAML block together |
| 2A | `exposure` | **Add** to `_ENGINE_READS`, comment naming `exposure.py` as the reader |
| 3a | `aggregation` | **Move** from `_DOCUMENTATION_ONLY` (line 61) to `_ENGINE_READS` |
| 3c | `root_cause` | **Add** to `_ENGINE_READS` |
| 4 | `gates.*` | Already in `_ENGINE_READS`; preserve the `sanctions.behaviour == "block"` invariant at line 320 |
| 5a | `assurity` | **Add** to `_ENGINE_READS` — or keep it in `benchmarks.yaml`, which has no such guard |

## Appendix C · Verification log

Every claim in this document was checked against the working tree on **2026-07-29**.

| Claim | Method | Result |
|---|---|---|
| 417 pass / 15 fail | `pytest -q` | ✅ 298.86 s |
| `planned_signal_count()` = 27 | live config introspection | ✅ |
| `penalising_bands()` = 57 | live config introspection | ✅ (`test_actions.py:38` asserts 54) |
| `penalty_divisor()` = **4.0** | live config introspection | ⚠️ **source plan implies 7** |
| `industry_profiles` at `scoring.yaml:661` | `grep -n` | ⚠️ source plan says 645 |
| `promote_severity` call at `normalize.py:121` | file read | ⚠️ source plan says 93 |
| `_count_of` at `normalize.py:95` | file read | ⚠️ source plan says 67 |
| Fixed divisor at `engine.py:187` | file read | ✅ |
| `promote_severity` at `scoring_config.py:249` | file read | ✅ |
| TLS collector probes one host | `tls_collector.py:48-90` | ⚠️ **no denominator** |
| Headers collector probes one URL | `headers_collector.py:36-60` | ⚠️ **no denominator** |
| CT collector carries counts | `ct_collector.py:166-176` | ✅ **the only real `D_s`** |
| No outcome labels / AUC anywhere | `grep -rn "auc\|outcome\|ground_truth"` | ⚠️ **Phase 0 not executable as written** |
| No bonus/negative-penalty path | `penalty_for`, `engine.py:187` | ⚠️ **Phase 1b needs 5a** |
| `min_cohort_n: 1` in YAML, `8` in code | `benchmarks.yaml:35`, `benchmark.py:108` | ✅ |
| Synthetic peers `[65,72,78,83,89,94]` | `benchmark.py:370` | ✅ |
| 115 seed vendors | `grep -c "SeedVendor("` | ✅ |
| 12 hygiene ≈ 16.33 with 3a+3b | computed | ✅ (3a alone = 22.53) |
| Critical:Low 13.3:1 → 33.3:1 | computed | ✅ |
| Corpus footprint penalty 19–31 for all 5 | `golden_scores.json` | ✅ |
| Repo is **not** a git repository | environment | ⚠️ **fix in Step 0.1** |
