Based on the brief, the source assessment, and NIST SP 1326, I would **not** categorize risks by source. I would categorize them by **what business risk they represent**. Sources are just evidence.

For example, don't do this:

| Category | Source |
| -------- | ------ |
| DNS      | DNS    |
| HIBP     | HIBP   |
| GDELT    | GDELT  |

That's hard to explain to a client.

Instead, do this:

| Risk Category             | Sources Used                        |
| ------------------------- | ----------------------------------- |
| Cyber Hygiene             | DNS, TLS, CT Logs, Security Headers |
| Incident History          | HIBP, GDELT                         |
| Regulatory & Legal        | OFAC, DFAT                          |
| Corporate Stability       | GLEIF (LEI register), Companies House |
| Supplier Transparency     | Trust Center, security.txt          |
| Supply Chain Dependencies | Subprocessor Lists                  |
| ESG / Ethical Risk        | Modern Slavery Register             |

Now the score answers questions clients actually ask.

---

# I would use six main categories

## 1. Cyber Hygiene

**Question**

> Is the vendor following good cybersecurity practices?

Signals:

* Certificate Transparency
* DNS (SPF, DKIM, DMARC)
* TLS
* HTTP Security Headers
* security.txt

Example findings

```
DMARC missing

TLS 1.0 enabled

Certificate expires in 5 days

No HSTS

No security.txt
```

---

## 2. Security Incident History

**Question**

> Has the vendor experienced known security incidents?

Signals

* HIBP
* GDELT
* NVD
* CISA KEV

Example

```
Two public breaches

Product has KEV-listed vulnerabilities

Recent ransomware incident
```

Notice

A breach from 2013 shouldn't count the same as one from last month.

---

## 3. Regulatory & Legal Risk

**Question**

> Is there any legal reason not to do business with this company?

Signals

* OFAC
* DFAT
* ITA Screening List

Possible rule

```
No sanctions

↓

Normal scoring

Sanctioned

↓

High Risk automatically
```

This category contains gate conditions.

---

## 4. Business Stability

**Question**

> Is the company likely to remain a stable supplier?

Signals

* GLEIF (LEI register) — **the wired source (v3.2, replaces SEC EDGAR)**
* Wikidata (structured data, CC0) — **second wired register (v3.3), domain-verified corroboration**
* Companies House / ABN Lookup (roadmap — key-gated; a third register for AU/UK)

Things to check

* Legal-entity status (active / inactive)
* LEI registration currency (issued / lapsed / retired)
* Jurisdiction and entity structure
* Entity existence / dissolution — Wikidata P576, resolved by official-website (P856) domain match

> **Note (v3.2):** SEC EDGAR was removed — it only covered US-*listed* firms (poor recall for AU/private vendors). GLEIF is global, free, no-auth and resolves all five test vendors. Going-concern / liquidation / financial-distress data has no free authoritative source and stays **held**.
>
> **Note (v3.3):** a **second** CC0 register — **Wikidata** — now corroborates GLEIF. It resolves by **domain** (matching the official-website property to the vendor's domain), fixing GLEIF's name-only blind spot, and emits *only* on a domain match (no wrong-entity guess). Where both registers agree, `legal_entity_status` confidence rises 0.90 → 0.97 (earned corroboration, methodology §5.4.3). ABN Lookup + Companies House stay roadmap — both require a registered API key.

---

## 5. Supplier Transparency & Compliance

**Question**

> Does the vendor publicly demonstrate mature security governance?

Signals

* Trust Center
* ISO 27001
* SOC 2
* security.txt
* Privacy policy
* DPA

Example

```
ISO 27001

SOC 2

Security contact published

Incident disclosure process
```

Remember

These are **claims**, not independently verified facts.

---

## 6. Supply Chain & ESG

This is where your project becomes different from most others.

### Supply Chain

Signals

* Subprocessor lists

Questions

```
Who hosts their services?

AWS?

Azure?

Snowflake?

Cloudflare?
```

Shared dependencies can become concentration risk.

---

### ESG

Signals

* Modern Slavery Register

Questions

```
Modern Slavery Statement?

Published?

Missing?

Current?
```

---

# Mapping your sources

| Source                   | Category              |
| ------------------------ | --------------------- |
| Certificate Transparency | Cyber Hygiene         |
| DNS                      | Cyber Hygiene         |
| TLS                      | Cyber Hygiene         |
| Security Headers         | Cyber Hygiene         |
| HIBP                     | Incident History      |
| GDELT                    | Incident History      |
| NVD                      | Incident History      |
| CISA KEV                 | Incident History      |
| OFAC / ITA               | Regulatory & Legal (gate) |
| DFAT                     | Regulatory & Legal (held) |
| Regulator RSS (FTC)      | Adverse Media         |
| GLEIF (LEI register)     | Business Stability    |
| Companies House / ABN    | Business Stability (roadmap) |
| Trust Center             | Supplier Transparency |
| security.txt             | Supplier Transparency + VDP |
| Subprocessor Lists       | Supply Chain (held)   |
| Modern Slavery Register  | ESG (held)            |

---

# Then score each category

Instead of immediately computing one overall score

```
Vendor

↓

Cyber Hygiene

↓

18 / 100
```

```
Vendor

↓

Incident History

↓

42 / 100
```

```
Vendor

↓

Business Stability

↓

10 / 100
```

Repeat for every category.

Only then calculate

```
Overall Vendor Risk
```

---

# Categories that shouldn't behave like normal scores

Not everything should use weighted averages.

For example:

| Signal               | Behavior                       |
| -------------------- | ------------------------------ |
| Sanctions            | Gate (automatic High Risk)     |
| Modern Slavery       | Major penalty or manual review |
| Critical KEV exploit | Large penalty                  |
| Missing Trust Center | Small penalty                  |
| Missing DMARC        | Medium penalty                 |

This makes the model more realistic than assigning every signal an arbitrary weight.

---

## My recommendation

I would structure the model like this:

```
Overall Vendor Risk
│
├── Cyber Hygiene
│   ├── Certificate Transparency
│   ├── DNS
│   ├── TLS
│   └── Security Headers
│
├── Incident History
│   ├── HIBP
│   ├── GDELT
│   ├── NVD
│   └── CISA KEV
│
├── Regulatory & Legal
│   ├── OFAC
│   ├── DFAT
│   └── ITA
│
├── Business Stability
│   ├── GLEIF (LEI register)   ← wired (v3.2)
│   ├── Wikidata (CC0)         ← wired (v3.3) — domain-verified corroboration
│   └── Companies House / ABN  ← roadmap (key-gated)
│
├── Supplier Transparency
│   ├── Trust Center
│   ├── ISO 27001
│   ├── SOC 2
│   └── security.txt
│
└── Supply Chain & ESG
    ├── Subprocessor Lists
    └── Modern Slavery Register
```

This structure is easy to explain to a client because every category represents a business concern rather than a technical data source. It also maps cleanly to the OSINT sources you've already documented, so each score can be traced back to concrete evidence.
