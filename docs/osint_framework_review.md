# OSINT Framework — source review against our clearance bar

**Reviewed:** [osintframework.com](https://osintframework.com/) · [github.com/lockfale/OSINT-Framework](https://github.com/lockfale/OSINT-Framework)
**Method:** the framework's own machine-readable index (`public/arf.json`, 1.1 MB) parsed and filtered against the register's bar — *free · commercial + automated use permitted · no ToS trap · reachable and parseable · entity-level, never natural persons*.
**Date:** 24 July 2026 · **Entries examined:** 1,168 across 33 categories

---

## The headline

**About 9% of the framework is even shaped like a source we could use, and most of that we already
have.** This is not a criticism of the framework — it is an excellent directory for the job it was
built for. That job is **investigating people**, and this project is built on a bright line that
says we do not.

| Filter | Entries | Why it removes them |
|---|---|---|
| Total leaf entries | **1,168** | — |
| Person-centric categories | **255** | Username · Email · Social Networks · Instant Messaging · People Search · Dating · Telephone Numbers · Classifieds. All collide with **§4.2 — no natural persons** |
| `opsec: active` | **257** | They probe the target. v1 makes no active connections beyond one TLS handshake and one GET — a deliberate ToS and lawful-access boundary |
| `localInstall: true` | **253** | Tools, not sources — theHarvester, recon-ng, Belati, EyeWitness, Subfinder. Several also scan actively |
| Deprecated | **68** | Dead |
| **Free + passive + hosted + has API + live** | **113 (9%)** | The only shape that can become a collector |

Narrowing to entity-relevant categories (Domain · Cloud Infra · IP/ASN · Public Records ·
Compliance & Risk · Business Records · CTI · Archives): **410 entries → 260 free and live → 71 with
an API → 56 not already in our register or permanently excluded.**

> **The structural point.** The framework indexes what an investigator can *look at*. We need what a
> pipeline can *lawfully ingest, attribute to a company, and defend in front of a regulator*. Those
> are different sets, and the gap between them is most of the 1,168.

---

## Worth pursuing — ranked by the gap each closes

Each still needs the full per-source clearance pass before ingestion. **Located ≠ cleared.**

### 1. Team Cymru IP-to-ASN · PeeringDB · iptoasn.com — *netblock attribution without scanning*

**Closes:** the biggest free-tier gap — attack-surface attribution — without crossing the
active-scanning line, and **without RIPEstat's non-commercial bar** (recorded in
[`doable_methodology.md`](doable_methodology.md) Tier 1c).

You cannot see *services* for free. You **can** establish which ASNs and netblocks a vendor
announces, which is the difference between "we know their primary domain" and "we know the estate
they operate". It also feeds fourth-party mapping: shared hosting and transit show up here.

**Status:** Team Cymru's service is free and long-running; **terms not confirmed in writing** —
treat as *ask-first* until they are. PeeringDB is community data with a stated licence. **Highest
value on this list.**

### 2. VIES VAT validation (EU) — *completes the registry adapter*

`ec.europa.eu/taxation_customs/vies` — the European Commission's official VAT number validation.
Free, no key, machine-readable.

**Closes:** the EU leg of the jurisdiction adapter. We have GLEIF (global), ABN Lookup (AU, built),
Companies House (UK, cleared). VIES adds authoritative **EU entity existence**, which today falls
back to GLEIF alone. Slots straight into `collectors/registry/` behind the existing interface.

### 3. Mnemonic passive DNS · ThreatMiner — *CT redundancy*

**Closes:** the documented single point of failure — Digital Footprint depends **entirely** on
Certificate Transparency, and a crt.sh outage tips a genuinely clean vendor to *The Ghost*.
AlienVault OTX is already the nominated fix; these are second and third options, which matters
because the whole point is not depending on one source.

### 4. CourtListener / RECAP / Caselaw Access Project — *the litigation half*

**Closes:** part of what §7.2 admits is missing — *"Business Stability = standing, not financials …
no distress/litigation data"*. Free APIs over US federal and state court records. **US-only**, so it
deepens the existing US weighting rather than correcting it — worth stating plainly if adopted.

### 5. FireHOL IP Lists · Blocklist.de · DShield (SANS ISC) — *IP reputation*

**Closes:** part of the `ip_reputation` category currently held as *"Deliberate v1 constraint:
commercial blocklist feeds require paid licences"* ([`additions.md`](additions.md), Roadmap
Priority #1). If a vendor's own netblocks appear on abuse blocklists, that is a real posture
observation about their estate.

**Caution:** FireHOL is an *aggregation* of many lists, each with its own licence. Clearance means
clearing every list you actually ingest, not the aggregator. Pairs with #1 — you need the netblocks
before a blocklist hit can be attributed to the vendor at all.

### 6. OpenOwnership — *FOCI, entity edges only*

**Closes:** the ownership chain behind **FOCI**, which [`methodology.md`](methodology.md) §8.3 calls
the highest-value next item, with a **~mid-2028 SOCI deadline**.

**Hard constraint:** beneficial-ownership data is substantially **about natural persons**. Ingest
**corporate-entity edges only** — company owns company. The moment a person node enters the store,
§4.2 is breached, and "the source offered it" is not a defence.

---

## Rejected, with reasons

| Source | Why not |
|---|---|
| **Google Safe Browsing API** | **Verified 24 Jul 2026: commercial use is prohibited.** Google's terms send revenue-generating use to the paid **Web Risk API**. This is the VirusTotal pattern exactly — free-looking, and closed to us. It was the most attractive item on the whole list, and it fails the bar |
| **Shadowserver Foundation** | Free daily reports go to **the network owner or a national CERT** — i.e. reports about *your* ASN. Not a third-party assessment source, however often it is listed as one |
| **ICIJ Offshore Leaks** | Leaked-document provenance and heavily person-centric. Publishing a vendor score partly derived from leaked personal data is not a position this project should take. Ask-first at best |
| **OCCRP Aleph** | Same person-centric problem, plus registration and use restrictions |
| **Cisco Umbrella / Tranco popularity lists** | Tempting as a *size proxy* for the benchmark cohort — and **refuse it on principle**. Domain popularity correlates with attack surface, which correlates with the score. That circularity is the size bias §7.3 warns about, and it is why the client-supplied `size_band` exists instead |
| **theHarvester · recon-ng · Belati · EyeWitness · Subfinder** | Tools, not sources; several actively probe the target |
| **EveryPolitician · Political MoneyLine · FEC** | Natural persons, and political-affiliation data at that. Not scored, not stored |
| **Dating · Telephone · Username · People Search** (255 entries) | §4.2 |

---

## What it confirms, which is worth as much as what it adds

Three of the register's standing positions came through this review **unchanged and better
evidenced**:

1. **There is no free substitute for commercial attack-surface data.** 1,168 curated entries, and
   the closest anything comes is ASN attribution — the estate's *shape*, never its *services*.
   Censys/Shodan remain Roadmap Priority #1, and the reason is now measured rather than asserted.
2. **No free source publishes private-company financials.** Nothing in Business Records or Public
   Records changes that. D&B / Moody's stay the only real answer.
3. **The person/entity split is the real filter, not price.** 781 of 1,168 entries are free. The
   binding constraint is that most OSINT tooling exists to investigate *people*, and this project
   is built not to.

---

## Recommended next actions

| # | Action | Effort |
|---|---|---|
| 1 | Written terms query to **Team Cymru**; clearance pass on **PeeringDB** | S |
| 2 | Build **VIES** as the EU registry adapter (interface already exists) | S |
| 3 | Add **Mnemonic passive DNS** as CT redundancy #2 behind OTX | S |
| 4 | Clearance pass on **CourtListener** — litigation, US-only, state the skew | M |
| 5 | Per-list clearance on **FireHOL / Blocklist.de / DShield**, after #1 | M |
| 6 | **OpenOwnership** for FOCI — corporate edges only, person nodes never stored | M |
| — | Record **Google Safe Browsing** in the excluded register beside VirusTotal and SSL Labs | Done above |

---

### See also

- [`source_assessment.md`](source_assessment.md) — the per-source register these must join
- [`doable_methodology.md`](doable_methodology.md) — Tier 1b/1c, where these candidates land
- [`perfect_methodology.md`](perfect_methodology.md) §15 — what still needs money, and why
- [`methodology.md`](methodology.md) §4.2 — the natural-persons bright line that removed 255 entries
