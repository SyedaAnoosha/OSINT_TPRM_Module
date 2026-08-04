# E9c — Compliance Gap framework library

**Status:** ✅ Tier 1 and Tier 2 shipped · **Raised:** 2026-07-31 · **Closed:** 2026-07-31
**Shipped:** nine frameworks declared, eight assessed · **Config:** [`scoring.yaml`](../scoring.yaml) → `compliance_frameworks:`

---

## 1. What shipped

| Framework | Applies because | Controls | Tier |
|---|---|--:|---|
| **APRA CPS 234** | sector: financial services, insurance | 4 | pre-existing, split |
| **APRA CPS 230** | sector: financial services, insurance | 3 | Tier 2 |
| **Privacy Act APP 11 / My Health Records Act** | sector: healthcare | 3 | pre-existing |
| **SOCI Act 2018 + CIRMP Rules 2023** | sector: utilities, telecommunications | 2 | Tier 2 |
| **ISO/IEC 27001:2022** | vendor asserts it | 3 | pre-existing |
| **PCI DSS v4.0** | vendor asserts it | 2 | Tier 1 |
| **SOC 2 (AICPA TSC)** | vendor asserts it | 3 | Tier 1 |
| **ISO/IEC 27017 / 27018** | vendor asserts it | 3 | Tier 1 |
| **ACSC Essential Eight** | sector: government | — | Tier 2 · **declared, OFF** |

Three shipped at E9c; six added closing it. Four are now sector-bound, covering financial
services, insurance, healthcare, utilities and telecommunications.

### The defect this work found first

**E9c shipped with a live false-attribution bug, and it had to be fixed before any framework could
be added.** `cert_posture` bands say `claimed_unverified` — they do not say *which* standard was
claimed. `asserted_by` matched on the band alone, so a vendor whose trust page said **SOC 2 and
nothing else** was published as *"asserts ISO/IEC 27001:2022, observed failing A.8.24."*

That is us putting a claim in a named third party's mouth and then finding them short against it —
the `industry_profiles` failure one layer over, and the more damaging half, because a false
compliance assertion about a real company is the sort of thing that ends up in front of their
lawyer. Adding PCI DSS and SOC 2 would have tripled it.

Fixed by `asserted_by.claim_contains`, matched against what the trust collector actually read off
the page, and **required at load** — an `asserted_by` without it is refused. Asserted by
`test_a_vendor_is_never_measured_against_a_standard_they_did_not_name`.

---

## 2. The constraint that governed expansion

Every framework carries a `basis` naming a **real, dated instrument**, enforced at load
(`_validate_compliance_frameworks`, ≥40 chars).

> A plausible-sounding expectation with an official-looking citation attached would pass any check
> that only tests for a non-empty string — and would put a regulatory claim about somebody else's
> legal obligations in front of a client. That is precisely what `industry_profiles` was, and E1
> deleted it.

Every basis below cites paragraph or requirement numbers, not just a standard's name.

### One evidence bar, applied uniformly

PCI DSS Req 6.3.3 (patch known vulnerabilities) and Essential Eight ML1 (patch internet-facing
services) are both genuinely in scope for a real assessment, and both would map to
`kev_listed_cve` / `nvd_cve`. **Neither uses it.**

E8 refused to *gate* on `kev_listed_cve` because it is a keyword match against a **product line**,
not against this vendor's deployed version. A published compliance finding is very nearly as
consequential as a gate — it tells a named third party they are short against a named legal
instrument — so the same bar applies. Asserted by
`test_no_framework_rests_a_control_on_a_product_line_keyword_match`, which is written against the
whole library so the bar cannot be lowered for one framework that needed the coverage.

E12 is what lifts this: a version-resolved estate makes the CVE match evidence rather than
inference, and both controls become available at once.

---

## 3. The four open design questions — all settled

### 1. Maturity models do not fit the schema · **excluded, and declared**

`controls: {signal: {failing_bands: [...]}}` expresses pass/fail and nothing else. Essential Eight
is levelled ML0–ML3; AESCSF is SP-1 to SP-3. Publishing "fails Essential Eight" against a standard
that has no pass/fail is a **more confident claim than the instrument itself makes**.

Essential Eight ships **declared and off**, the pattern `gates:` already uses for `kev_overdue`,
with `disabled_because` enforced at load. Two independent blockers are recorded: the levelling, and
the fact that seven of the eight strategies (application control, macros, admin privileges, MFA,
backups, OS patching, user application hardening) are **internal controls no external observer can
see**.

Shipping it enabled would produce a framework that applies to every government vendor and emits
nothing — *"considered, no gaps found"*, which reads as a clean bill and is not one. **That is
strictly worse than an entry saying why it is off.**

**Unblocked by P3's Evidence Request Pack**, which supplies the inside-out answers the model needs.
It then assesses *answers* rather than inference, which is the right basis for a maturity level.

**AESCSF / TISN are not modelled and will not be.** Also maturity models, covering the same
entities as SOCI, whose CIRMP obligation subsumes the enforceable part. A second framework saying
the same thing about the same vendor is the duplicate-gap problem by another name.

### 2. Sector taxonomy was unmanaged · **one controlled vocabulary now**

`applies_to_sectors` matched free text. `banking`, `superannuation`, `health`, `medical` and
`aged_care` all appeared in `scoring.yaml` and **none of them is a sector this system knows** —
benchmarking's `sector_groups` partition has 17 canonical sectors and none of those five is among
them.

So a client answering *"banking"* got the APRA framework and **no peer cohort**; one answering
`financial_services` got both. Same vendor, same obligation, two different reports depending on
which word the intake form captured. Worse, the two failures point in opposite directions: the
cohort refuses (designed behaviour, visible), while compliance silently returns **no gaps** —
which a reader takes as *no obligations breached*.

[`app/sectors.py`](../backend/app/sectors.py) resolves it, and it **reuses benchmarking's
partition rather than inventing a second list**, exactly as this document originally required. That
partition is already load-validated for uniqueness, which makes it the only sector list in the
codebase with a guarantee attached.

- Aliases are **input handling, not vocabulary** — `banking` → `financial_services`. Rejecting
  client spellings outright just moves the failure to the intake form where nobody is watching.
- An alias may only point at a sector that already exists; the loader refuses one that does not.
- `applies_to_sectors` is validated against the vocabulary at load.
- An **unrecognised** sector now emits a caveat instead of a clean report.

### 3. Multi-framework vendors emit duplicate gaps · **report all, charge once**

A vendor asserting ISO 27001, SOC 2 and PCI DSS while negotiating TLS 1.0 breaches three
frameworks with one weakness.

- **All three gaps are reported.** They are genuinely three separate claim-reliability problems and
  a buyer should see each one. Deduplicating the *findings* would hide information.
- **Assurity charges `distinct_observations`, not `gap_count`.** Charging three times would mean
  the axis punished a vendor for **publishing more certifications** — inverting what it measures,
  since publishing is the transparency it rewards everywhere else. This is E3's rule (one fact,
  charged once) applied one axis over.

Asserted by `test_claiming_more_frameworks_never_costs_more_for_the_same_weakness`.

### 4. Certification scope is unmodelled · **disclosed, not modelled**

An ISO 27001 certificate covers a defined scope — specific systems, sites or products — that may
exclude the product being bought. Trust pages rarely publish it and we read the claim off a
marketing page.

Modelling scope would require the certificate itself, which is an inside-out artefact (P3).
Until then every report carrying an asserted-framework gap states that a gap is **a question to put
to the vendor about their certificate's scope, not a finding that the certificate is invalid**.

---

## 4. Coverage — the honest limit, stated on every report

Four sector-bound frameworks cover five of seventeen canonical sectors. A vendor in **retail,
education, professional services, manufacturing, logistics, agriculture, construction, mining,
hospitality, media or technology** is bound by nothing modelled here and will show no gaps
whatever their compliance position.

Every report carries this mechanically — not left to whoever writes it:

> **Coverage:** Compliance gaps are assessed only against the frameworks this system models, and
> only against controls that are externally observable. **NO GAPS FOUND DOES NOT MEAN NO
> OBLIGATIONS EXIST.**

Plus, per report: unrecognised sector · sector alias resolution · disabled frameworks by name ·
certification scope · "does not change the posture score".

**Action:** wire alongside P2's coverage statement, where the same *"what we could not see"*
discipline applies.

---

## 5. Remaining candidates — build only on demand

**SOCI beyond two sectors** is the highest-value addition and it is **not a config edit**. The Act
binds responsible entities for *declared assets*, an entity-level fact. Utilities and
telecommunications ship because essentially every entity in them operates a covered asset. "Data
storage or processing", "food and grocery" and "transport" are narrow subsets of `technology`,
`retail` and `logistics` — applying CIRMP to every technology vendor because some are critical
infrastructure is the `industry_profiles` error exactly. It needs a client-supplied
`critical_infrastructure_asset` flag: **a new intake field, so a scoped change.**

**Tier 3 — international.** DORA (EU financial services) · NIS2 · HIPAA · UK Cyber Essentials.
**Do not build speculatively.** Each is a research task with legal review and none is useful until
a client is actually subject to it.

**ISO 27701** is detected by the collector but not modelled. Its observable controls are a subset
of 27001's, so it would emit duplicate gaps for no new information.
