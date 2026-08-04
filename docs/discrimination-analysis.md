# Discrimination analysis — which signals can actually rank a vendor

**Generated:** 2026-07-31 by `python -m tests.analyse_discrimination` · **Model:** `scoring.yaml` v5.2.0 · **Population:** 8 published corpus vendors (5 real, 5 synthetic archetypes)

> **Do not read this as evidence that the model ranks vendors correctly.** It answers a narrower question — *can this signal distinguish anyone at all?* A signal every vendor fails and a signal every vendor passes are equally useless for ordering, and both look fine on a per-vendor report. Whether the ordering it produces is *right* needs outcome labels (E0.4), which do not exist.

## The population, and what it cannot tell you

- **8 published vendors.** The discrimination threshold in `benchmarks.yaml` is `min_observations: 8` — so this analysis **could not have run at all before E0.2**, when the corpus held 5 published vendors. Every verdict would have read `untested`.
- **5 of the 10 fixtures are CONSTRUCTED**, not observed (`tests/build_archetypes.py`). They were built to exercise engine paths, so they widen the band spread **by design**. A signal that discriminates here has been shown to be capable of varying — not shown to vary across real vendors.
- **2 fixtures publish no posture** and are excluded rather than counted as zero: `synthetic_ghost`, `synthetic_gated`. A refused or gated vendor is not a peer.
- **This is not the seeded-pool run** E0.3's exit criterion asks for. That needs `python -m app.seed_cohorts --all` against ~115 real vendors and remains outstanding.

## Signals that cannot rank anyone

**None.** Every observed signal varies across the population at `max_modal_share = 0.95`.

## ⚠️ The real five, analysed separately — the number that matters

**Read this section before the one above it.** Across all eight the answer is *"everything discriminates"*, and that is an artefact: the archetypes were constructed to exercise distinct engine paths, so they vary **by design**. Removing them and asking the question of the five real vendors gives the opposite answer, and it is the answer E0.3 was written to obtain.

n = 5, which is **below** the `min_observations: 8` threshold. Reported anyway, flagged as under-powered, because a constant across five vendors is still a constant — and suppressing it until the pool is seeded is how this finding stayed invisible.

| | Count | Signals |
|---|--:|---|
| **Charges every vendor** — a flat tax, whatever the bands do | 3 | `stale_hosts` `vd_program` `weak_issuance` |
| **Charges no vendor** — all-pass, so it ranks nobody either | 16 | `breach_by_data_class` `caa` `cert_validity` `contactability` `dmarc` `dnssec` `domain_registration` `entity_status` `hsts` `program_disclosure` `regulator_action` `reporting_posture` `security_txt` `subdomain_estate` `tls_version` `x_frame_opts` |
| **Separates the real five** | 7 | `cert_posture` `csp` `dkim` `entity_existence` `kev_listed_cve` `nvd_cve` `spf` |

**19 of the 26 signals observed on real vendors cannot order them at all.** The 3 that charge everyone cost a mean of **18 category points ≈ 6.4 posture points** before anything specific to a vendor is considered — moving the whole population down together and separating none of it.

> **Two different failures, and they are easy to conflate.** A signal can charge every vendor while its *bands* vary — `stale_hosts` reads `many` for three and `some` for two, so modal share calls it discriminating, and yet nobody escapes a penalty. 14 signals are constant-BAND; **3 are constant-CHARGE**, and it is the second number E0.3 is about. An earlier draft of this report reported the first and understated the flat tax by three signals.

One further signal is never observed on a real vendor at all — `entity_maturity` — so it occupies a slot in the confidence denominator and contributes to neither axis. It fires only on `synthetic_smallco`, which is why that archetype was built.

This is a finding about the **corpus** as much as the model: five large, well-run technology vendors genuinely are alike. It becomes a finding about the model only once the seeded pool shows the same constants across a diverse population — which is exactly why the exit criterion asks for the seeded run and not this one.

### Against the by-hand baseline, and what the migration actually bought

The original E0.3 pass, run by hand against `scoring.yaml` v4.2.0 on the same five vendors, found **six signals penalising 100% of them** — `stale_hosts` `contactability` `weak_issuance` `subdomain_estate` `cert_posture` `vd_program` — worth **≥28 category points, roughly 7 posture points of flat tax**.

Same five vendors, same analysis, v5.2.0: **3 signals** — `stale_hosts` `vd_program` `weak_issuance` — worth a mean 18 category points ≈ 6.4 posture points.

**Compare the signal counts, not the posture points.** The two posture figures are on different scales — `penalty_divisor` moved 4.0 → 2.86 at E5, so the same category point costs more posture now — and the v4.2.0 figure was written as a lower bound (`≥28`). **Six flat taxes became four.** That is the comparable number.

Two went away and four did not, which is a more useful result than a clean sweep would have been. `contactability` stopped charging at E3 and `cert_posture` at E2 (`none_claimed` is free now, and the vendors that still pay are the ones asserting a certification that does not check out — a different and defensible charge).

**The four that remain are the case for E6, stated in one line.** `stale_hosts`, `subdomain_estate` and `weak_issuance` all charge every real vendor, and all three are footprint signals with no denominator: they measure how *large* a vendor's estate is and call the answer risk. E6 divides the first by the second. `vd_program` is the fourth and is a different problem — no real vendor runs a bug bounty we can observe — which puts it with E9b's positive credit rather than with E6.

## The full population — signals that discriminate across all 8

| Signal | Modal share | Bands observed |
|---|--:|---|
| `subdomain_estate` | 0.38 | `medium`×3 · `large`×3 · `small`×2 |
| `csp` | 0.50 | `present`×4 · `absent`×4 |
| `dnssec` | 0.50 | `valid`×4 · `absent`×3 · `misconfigured`×1 |
| `nvd_cve` | 0.50 | `cvss_medium_or_low`×4 · `no_critical_cve`×3 · `cvss_critical`×1 |
| `security_txt` | 0.50 | `present`×4 · `absent`×4 |
| `stale_hosts` | 0.50 | `many`×4 · `none`×2 · `some`×1 · `negligible`×1 |
| `vd_program` | 0.50 | `security_txt_only`×4 · `none`×4 |
| `caa` | 0.62 | `absent`×5 · `present`×3 |
| `cert_posture` | 0.62 | `claimed_unverified`×5 · `none_claimed`×2 · `claimed_expired`×1 |
| `entity_status` | 0.62 | `active_good_standing`×5 · `registration_lapsed`×3 |
| `spf` | 0.62 | `hardfail_all`×5 · `softfail_all`×2 · `absent`×1 |
| `weak_issuance` | 0.62 | `wildcard_sprawl`×5 · `none`×2 · `deprecated_ca_or_key`×1 |
| `contactability` | 0.75 | `none_published`×6 · `partial`×1 · `dpo_and_security_contact`×1 |
| `dmarc` | 0.75 | `p_reject`×6 · `p_none`×1 · `absent`×1 |
| `domain_registration` | 0.75 | `domain_established`×6 · `domain_recent`×1 · `domain_expiring`×1 |
| `kev_listed_cve` | 0.75 | `no_kev_match`×6 · `listed`×2 |
| `program_disclosure` | 0.75 | `detailed_policies`×6 · `none`×1 · `marketing_only`×1 |
| `reporting_posture` | 0.75 | `substantive`×6 · `none`×2 |
| `tls_version` | 0.75 | `tls_13`×6 · `only_tls_12`×1 · `tls_10_or_11`×1 |
| `breach_by_data_class` | 0.88 | `no_known_breach`×7 · `passwords_or_cards`×1 |
| `cert_validity` | 0.88 | `valid`×7 · `expired_serving_prod`×1 |
| `hsts` | 0.88 | `present`×7 · `absent`×1 |
| `regulator_action` | 0.88 | `no_action_found`×7 · `enforcement_action`×1 |
| `x_frame_opts` | 0.88 | `present`×7 · `absent`×1 |

### Untested — 3

Observed on too few vendors to test. Not a pass.

- `dkim` — only 7 peers were checked for this signal (need 8) — not enough to test
- `entity_existence` — only 6 peers were checked for this signal (need 8) — not enough to test
- `entity_maturity` — only 3 peers were checked for this signal (need 8) — not enough to test

## Category postures

| Category | Verdict | Statistic |
|---|---|---|
| `assurance_context` | non discriminating | the middle half of the cohort all score 100 — this domain does not separate suppliers here |
| `attack_surface_hygiene` | discriminating | spread is 21.0% of the mean across 8 peers (IQR 14) |
| `breach_compromise_history` | discriminating | spread is 36.7% of the mean across 8 peers (IQR 33) |
| `compliance_regulatory` | non discriminating | the middle half of the cohort all score 98 — this domain does not separate suppliers here |
| `continuity_context` | non discriminating | the middle half of the cohort all score 100 — this domain does not separate suppliers here |
| `identity_email` | discriminating | spread is 8.4% of the mean across 8 peers (IQR 2) |
| `transparency` | discriminating | spread is 2.1% of the mean across 8 peers (IQR 4) |

## Published postures

| Vendor | Posture | Confidence |
|---|--:|--:|
| `synthetic_smallco` (synthetic) | 97 | 0.980 |
| `onetrust` (real) | 94 | 0.963 |
| `myob` (real) | 90 | 0.926 |
| `slack` (real) | 87 | 0.926 |
| `atlassian` (real) | 79 | 0.963 |
| `snowflake` (real) | 75 | 0.926 |
| `synthetic_weak` (synthetic) | 49 | 1.000 |
| `synthetic_floor` (synthetic) | 39 | 1.000 |

Range **39–97**, spread 58 points. Real vendors alone span 75–94 — **a 13-point band across five vendors**, which is the compression this whole migration is trying to fix and the reason a 5-vendor corpus cannot detect a discrimination problem.

---

*Regenerate with `python -m tests.analyse_discrimination`. Do not hand-edit.*
