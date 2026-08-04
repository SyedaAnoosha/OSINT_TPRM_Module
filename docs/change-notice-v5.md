# Change notice — scoring model v4.2.0 → v5.0.0 → v5.1.0

**Issued:** 2026-07-30, amended 2026-07-31 · **Applies to:** every score published after this date · **Prepared by:** engineering
**Governing plan:** [phases.md](phases.md) phases E1–E6 · **Config:** [`scoring.yaml`](../scoring.yaml) v5.1.0

> **v5.1.0 (E6) is covered in [§7](#7-v510--the-exposure-denominator-e6) at the end.** It is a
> MINOR bump: the axes, categories, divisor and severity ladder are unchanged, so a 5.0 and a 5.1
> posture *are* comparable. §§1–6 describe the v4.2.0 → v5.0.0 change, which is not.

---

## 1. What a reader needs to know in thirty seconds

Posture now answers one question — **how exposed is this vendor to compromise** — and nothing else. Facts that are not about exposure (whether the company is still trading, whether it publishes a trust page, what sector it is in) have moved to axes that name themselves honestly, or have been dropped from the arithmetic entirely.

**No corpus vendor changed grade.** Postures moved by −4 to +1 points. Confidence did not move at all.

A v4.x posture and a v5.0 posture are **two different measurements**. Do not compare them, do not plot them on one trend line, and do not read a movement between the two as the vendor having changed. Re-score any vendor whose v4.x result is still in circulation.

---

## 2. Movement on the frozen regression corpus

| Vendor | v4.2.0 | v5.0.0 | Δ posture | Grade | Confidence |
|---|--:|--:|--:|:--:|:--:|
| atlassian | 82 / B | **78 / B** | −4 | unchanged | 0.963 → 0.963 |
| myob | 86 / A | **87 / A** | +1 | unchanged | 0.926 → 0.926 |
| onetrust | 86 / A | **85 / A** | −1 | unchanged | 0.963 → 0.963 |
| slack | 84 / B | **82 / B** | −2 | unchanged | 0.926 → 0.926 |
| snowflake | 76 / B | **74 / B** | −2 | unchanged | 0.926 → 0.926 |

Confidence is identical across the board because **no signal was deleted**. Every signal that stopped penalising stayed in the model as `informational`, so it still counts toward coverage. That was a deliberate choice: dropping the signals would have raised every vendor's confidence for no evidential reason — the checks still run and still return an answer.

### Intermediate movement, for anyone who saw a score mid-migration

Scores were re-goldened after each phase. Two vendors visibly moved up and then back down:

| Vendor | v4.2.0 | E1 | E2 | E3 | E4 | **E5 / v5.0.0** |
|---|--:|--:|--:|--:|--:|--:|
| atlassian | 82 | 82 | 82 | 84 | 84 | **78** |
| myob | 86 | 86 | 88 | 90 | 91 | **87** |
| onetrust | 86 | 86 | 87 | 89 | 89 | **85** |
| slack | 84 | 84 | 84 | 86 | 87 | **82** |
| snowflake | 76 | 76 | 80 | 82 | 82 | **74** |

**Slack's grade went B → A at E3 and A → B at E5.** If a Slack assessment was issued between those points it carries a grade A that v5.0.0 does not reproduce. That is the one item on this notice that may need an outbound correction; the cause is stated in §3.5 and it is arithmetic, not new evidence.

E1 moved nothing on the corpus — all five vendors are `technology`, which shipped no industry profile, so removing the profile mechanism was score-neutral here. It was **not** score-neutral for a financial-services or healthcare vendor, where it was promoting severities by one step.

---

## 3. What changed, and why

### 3.1 Sector no longer changes a severity (E1)

`industry_profiles` promoted a finding's severity by one step where a vendor's sector cited a named instrument — a missing DMARC record read as a hygiene gap for a farm supplier and a live fraud exposure for a bank.

That is the same evidence scoring differently because of a label **we** assigned. It destroys cross-vendor comparability, which the entire model rests on, and it is not defensible to a vendor who asks why their score differs from a competitor's on identical findings.

The sector obligation is not lost — it becomes a **Compliance Gap** finding at E9c, which states the obligation and whether it is met rather than silently moving a number. Both `basis:` strings (APRA CPS 234/230; Privacy Act APP 11 / My Health Records Act / OAIC NDB) are preserved verbatim in [compliance-gap-frameworks.md](compliance-gap-frameworks.md).

**Guarded by:** `test_scoring.test_sector_never_changes_a_severity` — the same findings scored against every sector must produce a byte-identical Score.

### 3.2 The norm stopped being a penalty (E2)

Eight bands became `informational`:

```
dnssec.absent · caa.absent · security_txt.absent
program_disclosure.none · program_disclosure.marketing_only
cert_posture.none_claimed
reporting_posture.none · reporting_posture.partial
```

DNSSEC absence is the condition of the overwhelming majority of the internet. Penalising it means penalising almost everyone, which conveys no information about *this* vendor and buries the findings that do.

Two of these eight were **not** in the original plan and were added after checking for monotonicity inversions: reclassifying only the absence bands would have left cases where a vendor **gains points by deleting their trust page**. A model that pays a vendor to disclose less is worse than one that is merely too harsh.

`dnssec.misconfigured` still penalises. Absence is the norm; a broken configuration is a fault.

### 3.3 Contactability is charged once (E3)

`contactability` and `program_disclosure` were both penalising the same underlying fact — that a vendor publishes no security contact — from two categories, so one gap cost points twice. `contactability.partial` and `.none_published` are now `informational`.

### 3.4 Going-concern facts left Posture (E4)

The defect, stated plainly: Companies House maps `liquidation`, `receivership`, `administration` and `insolvency-proceedings` onto `entity_inactive`, **which cost 20 points of technical security posture**. A vendor entering administration does not thereby have worse TLS.

All eleven penalising bands of the old `business_financial_stability` category are now `informational`. The facts are still collected, still published, and arguably more useful than before: they surface as **Continuity flags** with a standing (`ceased` / `impaired` / `watch` / `sound` / `unknown`), each carrying its register, its retrieval date and its evidence receipt — `GET /api/vendors/{ref}/continuity`.

Continuity is **not a score**, deliberately. Runway, cash burn and credit ratings have no lawful free source, so a number would be a guess with a decimal point on it. Absence of financial-distress data is disclosed as absence, never implied as health.

Company age also stopped reaching any penalty. No published evidence links founding date to compromise likelihood. Age keeps its one legitimate arithmetic role — the bounded **confidence** assurance multiplier.

### 3.5 Seven categories became five, and the divisor moved (E5) — **this is the whole of the score movement above**

| Category | Signals | n |
|---|---|--:|
| Breach & Compromise | `breach_by_data_class` `kev_listed_cve` `nvd_cve` | 3 |
| Attack Surface & Hygiene | `tls_version` `cert_validity` `hsts` `csp` `x_frame_opts` `dnssec` `caa` `subdomain_estate` `stale_hosts` `weak_issuance` | 10 |
| Identity & Email | `dmarc` `spf` `dkim` | 3 |
| Transparency | `vd_program` `security_txt` | 2 |
| Compliance & Regulatory | `cert_posture` `regulator_action` | 2 |
| *Continuity (context)* | `entity_status` `entity_existence` `entity_maturity` `domain_registration` | *4* |
| *Assurance (context)* | `program_disclosure` `contactability` `reporting_posture` | *3* |

**27 signals, all accounted for. The two context categories can never carry a penalty**, which is asserted against the shipped config rather than left as an intention.

`penalty_divisor` moved **4.0 → 2.86**. This is not a tuning knob and it was not chosen:

```
divisor(n) = n × (4 / 7)        # holds maximum damage at 175 posture points
5 × 4/7 = 2.857 → 2.86          # verified: 5 × 100 / 2.86 = 174.8
```

Leaving the divisor at 4.0 while shrinking from seven categories to five would have made the model **quietly more forgiving** — a larger fraction of the model must fail before the score bottoms out. The divisor shipped in the same commit as the restructure, because a category move without it re-scores every vendor for an invisible reason.

**This is the entire cause of the E5 column.** Snowflake, worked through:

```
total category penalty = 73.64          (identical before and after)
  ÷ 4.00 → posture 81.6 → 82
  ÷ 2.86 → posture 74.3 → 74
```

The penalties did not move. Only the divisor did.

### 3.6 Two deviations from the plan, recorded rather than buried

The plan's E5 target was "16 scored signals". The shipped model has **18**. Both differences are deliberate:

- **`cert_posture` stayed in a scoring category** rather than relocating to context. A vendor's certification claim, corroborated against a registry, is evidence about their security programme — unlike `program_disclosure`, which only evidences that they have a marketing page.
- **`dnssec` still penalises** its `misconfigured` band (see §3.2). The plan treated the whole signal as informational; only absence is.

Neither changes the divisor: both signals sit in categories that already exist.

### 3.7 `regulator_action` — decision recorded, not defaulted

E5 forced a choice on a signal that **cannot distinguish cyber enforcement from any other kind**. A DOJ antitrust settlement currently scores identically to an ICO data-protection fine.

**Decision: keep the signal in Compliance & Regulatory and accept the defect for now.** Recorded because the plan explicitly warned against arriving here by omission.

Grounds: it fires on 0 of 5 corpus vendors, and the fix is a *collector* change — tagging cyber-relevance in `regulatory_collector` — which does not belong inside the largest re-score in the plan. It is a **blocking prerequisite for E9c** and is pinned by `test_regulator_action_cyber_relevance_is_a_recorded_open_item`, which is written to **fail** once the tagging lands.

---

## 4. What did *not* change

- **No category weights were introduced.** A penalty-subtractive model has none, and adding them would reintroduce exactly the hidden judgement E1 removed.
- **Posture and Confidence remain separate numbers.** Neither collapses into the other. A vendor that looks clean on thin coverage is still flagged as a Ghost and still refused rather than published as an A.
- **The signal count held at 27** through every phase. Coverage, and therefore confidence, is unaffected by all five changes.
- **The sanctions gate, the critical ceiling and the dispute machinery** are untouched.
- **No natural-person data** enters the model, per §4.2 (APP 10, the statutory privacy tort, EU AI Act Art 6(3)).

---

## 5. Verification

```
544 passed, 0 failed
scoring.yaml v5.0.0 · 27 signals · 36 penalising bands · penalty_divisor 2.86
7 categories (5 scoring + 2 context) · max damage 174.8 / 175
```

Down from 57 penalising bands at v4.2.0. The frozen 5-vendor corpus was re-goldened once, at E5; `python -m tests.regolden` prints the movement, and the diff **is** the change.

---

## 6. Action required

| Audience | Action |
|---|---|
| **Anyone holding a v4.x report** | Treat the posture as superseded. Re-score before relying on it. |
| **Anyone who received a Slack assessment between E3 and E5** | The grade A does not reproduce. See §2. |
| **Procurement / supply-chain readers** | Going-concern standing is now on its own axis and is *more* prominent than before — read it. It is no longer buried inside a security number. |
| **Security readers** | Posture is now security-only. A high posture no longer implies the company is solvent, and never did. |
| **Anyone trending scores over time** | Start a new series at v5.0.0. |

---

## 7. v5.1.0 — the exposure denominator (E6)

**Issued 2026-07-31. A MINOR bump: 5.0 and 5.1 postures are the same measurement.** Categories, divisor, axes and severity ladder are untouched. One signal's input changed.

### What was wrong

`stale_hosts` was banded on a **raw count** of abandoned public hosts: 0 was `none`, 1–5 `some`, more `many`. The estate those hosts belonged to was never consulted.

| | Public hosts | Abandoned | Rate | Old band | Old penalty |
|---|--:|--:|--:|---|--:|
| Vendor A | 4 | 2 | **50%** | `some` | −8 |
| Vendor B | 900 | 9 | **1%** | `many` | −20 |

B runs an estate fifty times tidier and paid two and a half times more. The model was measuring **how big a vendor is** and calling the answer risk — and `subdomain_estate` charged for size directly, on top.

This was not hypothetical. [discrimination-analysis.md](discrimination-analysis.md) measured it: `stale_hosts` and `subdomain_estate` penalised **100% of real corpus vendors**, and a penalty nobody escapes cannot rank anyone.

### What changed

**`stale_hosts` now bands on a rate**, computed from the same two numbers `ct_collector` already returned — no new collection, no new network call:

```
r̂ = (f + α) / (D + α + β)                 α=0.5, β=9.5  — prior-corrected share of the estate
g  = λ·r̂ + (1 − λ)·min(1, f/κ)            λ=0.7, κ=50   — blended with an absolute floor
```

Two corrections, each answering a way a naive `f/D` fails. **α, β** stop one abandoned host out of one from reading as a 100% failure rate — it lands at 10%, which is "one observation", not "everything is broken"; without it the smallest vendors get the worst possible score on the thinnest possible evidence. **κ** stops scale buying forgiveness: 60 abandoned hosts out of 900 is 6.6%, and 60 abandoned hosts is still 60 ways in.

**Zero failures short-circuits to `none`, always.** With a prior, zero observed failures still yields a small positive rate — 3.6% for a 4-host vendor — and charging a vendor for a finding of *zero* would be indefensible.

**A new band, `negligible` (low, −3)**, is where a large well-kept estate lands. Without it a vendor with 5 abandoned hosts out of 4,326 paid the same 8 points as one with 5 out of 20.

**`subdomain_estate` stopped penalising entirely.** It is the denominator now. It stays in the model as a collected, informational signal so `planned_signal_count` holds at 27 and no vendor's confidence moves.

### Movement

| Vendor | Estate | Stale | v5.0.0 | v5.1.0 | Δ | Why |
|---|--:|--:|--:|--:|--:|---|
| atlassian | 41 | 13 | 79 → | **79** | +1 | `subdomain_estate` −3; band unchanged (`many`, 32% of a small estate) |
| myob | 84 | 11 | 87 → | **88** | +1 | `subdomain_estate` −3; band unchanged (`many`) |
| onetrust | 99 | 9 | 85 → | **90** | +5 | `many` → `some` (−12) plus `subdomain_estate` (−3) |
| **slack** | 4,326 | 5 | 82 → | **86** | +4 | `some` → `negligible` (−5) plus `subdomain_estate` (−8). **Grade B → A** |
| snowflake | 211 | 119 | 74 → | **77** | +3 | `subdomain_estate` −8; band unchanged — 56% stale is `many` on any denominator |

Confidence did not move for any vendor. Penalising bands: 36 → 35.

**Slack crosses B → A**, its second grade change in this migration (§2 records the earlier B→A→B excursion). The cause is exactly the defect E6 removes: slack operates the largest estate in the corpus by two orders of magnitude and 5 of its 4,326 public names look abandoned — a **0.1% rate**, the best in the corpus, previously scored as though it were the worst.

Snowflake is the control that shows the change is not simply "large vendors gain". 119 of 211 hosts stale is 56%, and it stays `many` at the full −20.

### The denominator is published, and disputable

E6's governing obligation is *publish the denominator*. Every `stale_hosts` finding now carries `denominator` and `exposure_index`; the collector's observed string reads **"5 of 4,326 names look stale/dev/staging"**; and all three `accepts_as_refute` entries invite the challenge this phase creates — *"you counted 340 hosts, we operate 40"*. That correction changes the **band**, not just the wording: the same 9 stale hosts band `some` against 900 and `many` against 40.

### Reverting

`exposure.enabled: false` in [`scoring.yaml`](../scoring.yaml) restores the pre-E6 bands exactly. The old count thresholds are preserved under `fallback_count_bands` rather than deleted, so the switch is a true revert rather than a deletion — pinned by `test_disabling_exposure_restores_the_pre_e6_bands`.

### What E6 did *not* fix

The research claims a denominator exists for most rate-normalisable signals. **It does not.** `tls_version` and `cert_validity` come from **one** handshake against the apex; `hsts`, `csp` and `x_frame_opts` from **one** homepage GET; `nvd_cve` and `kev_listed_cve` from a keyword match with no denominator at all. Only `stale_hosts ÷ subdomain_estate` was free. The rest is E12, a 6–10 week programme, and until it lands those signals remain single-observation checks presented as estate-wide facts.
