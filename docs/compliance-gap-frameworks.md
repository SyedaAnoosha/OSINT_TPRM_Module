# Compliance Gap frameworks — backlog for E9c

**Captured from `scoring.yaml:661-683` at E1, immediately before deleting `industry_profiles`.**

E1 removes sector severity promotions from the arithmetic. **The sector obligation itself is real** — it was never the problem. What was wrong was expressing it as a severity change, which makes the same evidence score differently depending on a label we assigned.

The obligation belongs in the **Compliance Gap** (E9c): where a vendor is *bound by* framework `F` and is observed failing a control in `C(F)`, emit a cited finding about the reliability of their compliance position — not a heavier penalty on the underlying observation.

> *"Vendor is APRA-regulated and does not publish a DMARC record"* is a different claim from *"this DMARC finding is worth more points."* The first is disputable, citable and actionable. The second is an opinion wearing a number.

---

## Framework 1 · Financial services

**Basis, verbatim:**
> APRA CPS 234 Information Security (mandatory for APRA-regulated entities) · CPS 230 Operational Risk Management (in force 1 Jul 2026)

| Control observed failing | Was promoted to | Original justification, verbatim |
|---|---|---|
| `dmarc.absent` | critical | *BEC is the dominant fraud loss in this sector and spoofable email is its opening move.* |
| `spf.absent` | high | *(as above — same mechanism)* |
| `cert_posture.none_claimed` | high | *CPS 234 requires an information security capability commensurate with the threat; no independent audit at all is a materially different position for a regulated entity.* |
| `contactability.none_published` | high | *CPS 230 makes an unreachable operator a continuity problem, not just a courtesy gap.* |

**Note for E9c:** two of these four signals leave Posture before E9 lands — `cert_posture` goes to Assurity (E2), `contactability` merges into `security_txt` (E3). The *obligation* survives the signal relocation: a Compliance Gap finding can cite an Assurity input just as well as a Posture one.

---

## Framework 2 · Healthcare

**Basis, verbatim:**
> Privacy Act 1988 APP 11 (security of personal information) · My Health Records Act 2012 · OAIC Notifiable Data Breaches CY2025 — health providers were 19% of all notifications, the largest single sector

| Control observed failing | Was promoted to | Original justification, verbatim |
|---|---|---|
| `breach_by_data_class.personal_info` | critical | *Health data is the most sensitive class most vendors hold, and the OAIC's own figures put this sector first for notified breaches.* |
| `dmarc.absent` | critical | *(as above)* |
| `reporting_posture.none` | high | *(APP 11 / MHR Act reporting expectations)* |

---

## The discipline to carry forward

Three rules from the deleted block were **right** even though the mechanism was wrong. Keep all three in E9c:

1. **Every framework cites a named instrument.** A profile with no legal or regulator-published anchor did not load. `_validate_industry_profiles` enforced this; `_validate_compliance_frameworks` should enforce the same.
2. **Bounded scope.** `max_promotions: 6` existed so a profile could not quietly become a weighting scheme. The Compliance Gap equivalent is a cap on how many controls one framework may cite.
3. **Only what has an unambiguous anchor ships.** Two frameworks, not twelve. *"Never a batch of twelve invented in an afternoon, which is how the weights problem started."*

## What must NOT come back

The Compliance Gap emits a **finding**, never a severity multiplier. If an implementation of E9c ends up changing the points a TLS observation is worth because the vendor is a bank, it has reimplemented `industry_profiles` under a new name — see anti-pattern 2 in [phases.md](phases.md).

## Sector still reaches two places, legitimately

- **Cohort assignment** — a bank is compared against banks (E10a)
- **Compliance Gap** — a bank is measured against the frameworks that bind banks (E9c)

Neither changes what an observation is worth.
