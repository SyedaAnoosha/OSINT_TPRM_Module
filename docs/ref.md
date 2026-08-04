Yes. I would study **existing cyber risk rating platforms** rather than generic OSINT tools. These companies have already spent years deciding **what signals matter** and **how to justify a vendor's risk score**. Your goal is not to copy them, but to understand the dimensions they use.

## Tier 1: Must Study (Highest Priority)

### 1. SecurityScorecard ⭐⭐⭐⭐⭐

Probably the closest commercial product to what you're building.

It rates companies continuously based on public data.

Study:

* Risk categories
* Score breakdown
* How they explain deductions
* Evidence shown to users

Risk factors include:

* Network Security
* DNS Health
* Patching
* Endpoint Security
* Application Security
* IP Reputation
* Cubit Score
* Hacker Chatter

Website:
[https://securityscorecard.com](https://securityscorecard.com)

---

### 2. Black Kite ⭐⭐⭐⭐⭐

This is one of the best references for explainable scoring.

Study:

* Cyber rating methodology
* Weighting approach
* Confidence
* Supply chain risk

Interesting concepts:

* Breach history
* Financial impact
* Industry comparisons
* Risk trends

Website:
[https://blackkite.com](https://blackkite.com)

---

### 3. Bitsight ⭐⭐⭐⭐⭐

One of the oldest cyber rating companies.

Very useful because they publicly discuss:

* Rating methodology
* External attack surface
* Evidence collection
* Time-based scoring

Study:

* Score calculation
* Rating changes
* Continuous monitoring

Website:
[https://www.bitsight.com](https://www.bitsight.com)

---

### 4. UpGuard ⭐⭐⭐⭐☆

Very close to your client brief.

It already collects OSINT about vendors.

Study:

* Vendor questionnaires
* Public attack surface
* Security posture
* Vendor reports

Website:
[https://www.upguard.com](https://www.upguard.com)

---

## Tier 2: Excellent for OSINT Sources

### SpiderFoot ⭐⭐⭐⭐⭐

This should be one of your biggest references.

Open-source.

Instead of focusing on scores, study:

* What data sources it queries
* How it structures findings
* Which OSINT modules exist

Examples:

* DNS
* WHOIS
* Leaks
* Email
* SSL
* Malware
* IPs
* Dark web

GitHub:
[https://github.com/smicallef/spiderfoot](https://github.com/smicallef/spiderfoot)

---

### OpenCTI ⭐⭐⭐⭐☆

More threat intelligence than vendor scoring.

Useful for understanding

* Relationships
* Indicators
* Threat actors
* Evidence modeling

GitHub:
[https://github.com/OpenCTI-Platform/opencti](https://github.com/OpenCTI-Platform/opencti)

---

### Maltego ⭐⭐⭐⭐☆

Excellent for understanding

* Entity relationships
* Graph-based OSINT
* Infrastructure mapping

Don't copy the UI.

Study how they connect entities.

---

### OSINT Framework ⭐⭐⭐⭐⭐

Probably the single best directory of OSINT sources.

This is a collection of hundreds of public OSINT resources.

Study it for

* Company intelligence
* Domains
* Emails
* Infrastructure
* Social media
* Government records

Website:
[https://osintframework.com](https://osintframework.com)

---

## Tier 3: Individual Data Sources

These are the sources your collectors will probably query.

| Source               | What you get                                 |
| -------------------- | -------------------------------------------- |
| WHOIS                | Domain age, registrar                        |
| Security Headers     | HTTP security configuration                  |
| SSL Labs             | SSL/TLS rating                               |
| VirusTotal           | Reputation                                   |
| Shodan (respect ToS) | Internet-facing services                     |
| Censys               | Public infrastructure                        |
| NVD                  | CVEs                                         |
| CVE.org              | Vulnerabilities                              |
| MITRE ATT&CK         | Threat context                               |
| Have I Been Pwned    | Public breach information (where applicable) |
| Google News          | Adverse media                                |
| SEC EDGAR            | Public companies                             |
| Companies House (UK) | Company registration                         |
| OFAC                 | Sanctions                                    |
| CISA KEV             | Known exploited vulnerabilities              |

---

# Academic / Standards (Very Important)

Your client wants a **defensible methodology**, not just software.

Read these.

### NIST Cyber Supply Chain Risk Management (C-SCRM)

This is probably the most important standard.

Study:

* Supplier risk
* Supply chain assessment
* Confidence
* Risk categories

---

### NIST SP 800-161

Supply Chain Risk Management.

This explains how governments evaluate suppliers.

---

### NIST SP 1326

Very recent guidance on supplier assessment using public information.

---

### ISO 27036

Information Security for Supplier Relationships.

Very useful for deciding scoring dimensions.

---

### FAIR

Factor Analysis of Information Risk.

Useful for understanding

* Likelihood
* Impact
* Risk quantification

---

## Open-source projects worth reading

### OpenVAS / Greenbone

Shows vulnerability assessment structure.

---

### DefectDojo

Shows how security findings are normalized.

---

### Faraday

Shows how multiple scanners feed into one system.

---

### OWASP Dependency-Track

Shows risk aggregation and evidence management.

---

## If I were doing this internship, this would be my reading order

1. **SecurityScorecard** (understand the categories)
2. **Black Kite** (study explainable scoring)
3. **Bitsight** (see how ratings evolve)
4. **SpiderFoot** (learn what OSINT data can be collected)
5. **OSINT Framework** (identify lawful public data sources)
6. **NIST SP 800-161** and **NIST SP 1326** (ground your methodology in recognized guidance)
7. **ISO 27036** (supplier security concepts)

## One suggestion that could make your project stand out

Most people will likely build:

```
Vendor
    ↓
Collect data
    ↓
Score
```

Instead, build a scoring model that keeps every finding traceable:

```
Vendor
    ↓
OSINT Collectors
    ↓
Normalized Signals
    ↓
Evidence Store
    ↓
Category Scores
    ↓
Overall Risk
    ↓
Confidence
    ↓
Explainability Report
```

Then every point deducted from the score is linked to the exact evidence and source. That directly addresses the client's requirement that **every score be explainable and defensible**, which is the central theme of the brief.
I would not start with the code. If you do, you'll end up rewriting it because the client has made it very clear that **the methodology is the product**. The application is just a way to demonstrate it.

Here's the approach I would take if I were building this from scratch.

---

# Phase 1. Design the methodology first

Forget Python, APIs, and scraping for a day or two.

Answer these questions:

> What makes a vendor risky?

Break that into measurable categories.

For example:

| Risk Category    | What it measures                          | Example sources                                        |
| ---------------- | ----------------------------------------- | ------------------------------------------------------ |
| Cyber Security   | Is the company technically secure?        | SSL Labs, Security Headers, CVE, Shodan (if permitted) |
| Reputation       | Has the company had scandals or breaches? | Google News, Reuters                                   |
| Compliance       | Does it have security certifications?     | Company website, Trust Center                          |
| Financial        | Is it financially healthy?                | SEC filings, Companies House                           |
| Legal            | Lawsuits, sanctions, regulatory actions   | OFAC, SEC, court records                               |
| Company Maturity | Domain age, company age                   | WHOIS, Companies House                                 |

Notice something?

Every category can later become an independent collector.

---

# Phase 2. Build the scoring framework

This is where your real work begins.

Don't immediately think:

```
Cyber = 30%
```

Instead define:

```
Category

↓

Signals

↓

Signal score

↓

Category score

↓

Overall score
```

Example

```
Cyber Security

SSL valid?
Yes

Security Headers?
Grade A

Recent breach?
None

Known exposed services?
No

Category Score

92/100
```

Repeat for every category.

Only after that combine them.

---

# Phase 3. Build collectors

Instead of one giant scraper, make one module per source.

```
collectors/

    ssl.py

    security_headers.py

    whois.py

    google_news.py

    sanctions.py

    companies_house.py

    github.py
```

Each collector should return JSON.

Example

```json
{
    "source": "SSL Labs",
    "ssl_grade": "A+",
    "score": 100,
    "confidence": 0.98
}
```

Everything should look the same so your scoring engine doesn't care where it came from.

---

# Phase 4. Build the scoring engine

Something like

```
Collector Results

↓

Normalizer

↓

Category Scores

↓

Weighting

↓

Overall Score

↓

Risk Report
```

That makes it very easy to add more sources later.

---

# Phase 5. Produce an explainable report

Don't just show

```
Overall Score

2.8
```

Show

```
Overall Risk

2.8 / 5

Reason

✓ SSL configured correctly

✓ Domain active for 14 years

✓ ISO 27001 published

⚠ Two breach reports within five years

⚠ Missing DMARC policy
```

This is exactly what the client means by **"defend your score."**

---

# I would avoid a pure weighted average

Most students will probably do

```
30%

20%

20%

15%

15%
```

That is too simplistic.

I'd make it hierarchical.

```
Overall Risk

├── Cyber
│     ├── SSL
│     ├── DNS
│     ├── Security Headers
│     ├── CVEs
│
├── Reputation
│     ├── News
│     ├── Breaches
│
├── Financial
│     ├── Revenue
│     ├── Bankruptcy
│
├── Legal
│
└── Compliance
```

It is much easier to explain.

---

# I would also introduce confidence

Public data is incomplete.

So every report should contain

```
Risk Score

2.4 / 5

Confidence

82%

Reason

Financial data unavailable.

No Trust Center found.

Security data complete.
```

The client specifically asks you to be honest about confidence because OSINT is often incomplete. ([NIST Computer Security Resource Center][1])

---

# Existing products worth studying

These are useful references. Don't copy them, but study how they think about risk.

### 1. OpenVendor (probably the closest inspiration)

An open-source Third-Party Risk platform.

It focuses on:

* transparent scoring
* explainable methodology
* community intelligence
* vendor database

This aligns very closely with your brief. ([OpenVendor][2])

---

### 2. Black Kite

One of the biggest cyber-risk rating companies.

Their strongest idea is **transparent scoring**. They emphasize that users should understand why a vendor received a particular rating instead of trusting a black-box algorithm. That is almost identical to your client's requirement. ([Black Kite][3])

---

### 3. NIST SP 1326 (2026)

This may be the single most valuable document for your methodology.

It recommends assessing suppliers using areas such as:

* Foreign ownership, control, or influence
* Provenance
* Organizational resilience
* Foundational cyber practices
* Supply chain relationships

These categories can inspire parts of your scoring model. ([NIST Computer Security Resource Center][1])

---

### 4. SANS Vendor Risk Assessment Matrix

This isn't an OSINT scoring system, but it provides a structured way to classify vendors and discusses confidence levels and different assessment types. ([SANS Institute][4])

---

# Sources I'd actually use

| Source                      | Signal                                 |
| --------------------------- | -------------------------------------- |
| WHOIS                       | Domain age, registrar                  |
| Security Headers            | Security header configuration          |
| SSL Labs                    | TLS/SSL quality                        |
| Google News                 | Negative news                          |
| NVD (CVE)                   | Public vulnerabilities                 |
| Company Trust Center        | ISO 27001, SOC 2, certifications       |
| OFAC Sanctions              | Sanctions status                       |
| SEC EDGAR / Companies House | Financial and registration information |
| DNS records                 | Email security (SPF, DKIM, DMARC)      |

---

# A scoring model I'd propose

Instead of arbitrary weights, I'd structure it like this:

```
Overall Risk (0-100)

Cyber Security (35)
    SSL
    DNS
    Security Headers
    Public vulnerabilities

Compliance (20)
    ISO 27001
    SOC 2
    Privacy certifications

Legal & Regulatory (15)
    Sanctions
    Regulatory actions
    Lawsuits

Reputation (15)
    Breaches
    News sentiment
    Public incidents

Business Stability (15)
    Company age
    Financial filings
    Domain maturity
```

Each category computes its own score from individual signals, then contributes to the overall result. That makes every deduction traceable.

## Why I think this approach fits the brief

The client keeps repeating three ideas:

* **The scoring model is the deliverable.**
* **Every score must be explainable.**
* **The methodology should outlive the code.**

A modular pipeline with documented signal definitions, category-level scoring, confidence values, and a clear audit trail satisfies all three. It also makes it easy to plug into a larger Third-Party Risk platform later without redesigning the scoring engine.
At its core, the client wants you to build a system that answers one simple question:

> **"If I am thinking of doing business with this company, how risky is it?"**

The difficult part is **not collecting data**. The difficult part is **deciding how to calculate the risk score and explaining why that score is correct.**

---

# What is OSINT?

**OSINT** stands for **Open Source Intelligence**.

It means collecting information that is already publicly available.

Examples:

* Company website
* News articles
* Security breach reports
* SSL certificate information
* DNS records
* WHOIS records
* Sanctions lists
* Government databases
* Public financial information
* GitHub
* Public security databases like CVE or Shodan (where permitted)

No hacking.
No private information.
Only public sources.

---

# What the client wants

Imagine someone types

```
Microsoft.com
```

or

```
ABC Manufacturing Ltd
```

Your system should automatically collect public information and produce something like:

```
Vendor:
Microsoft

Cyber Risk:
Low

Financial Risk:
Low

Legal Risk:
Medium

Compliance:
High

Overall Risk:
2.1 / 5

Confidence:
91%

Reason:
• SSL certificate valid
• No recent breach
• ISO 27001 certified
• Financially stable
• One lawsuit in 2025
```

That final report is what they want.

---

# The client DOES NOT care most about the code

This sentence is the most important one in the brief:

> **The scoring model is the actual deliverable.**

Meaning...

Suppose two interns build the same application.

Intern A:

> "Vendor scored 3.8"

Client:

> "Why?"

Intern:

> "Because that's what my algorithm produced."

❌ Bad.

---

Intern B:

> "Cyber incidents contribute 30%.
>
> Financial health contributes 20%.
>
> Compliance contributes 25%.
>
> Infrastructure contributes 15%.
>
> Legal issues contribute 10%.
>
> Microsoft had no breaches, valid certificates, good finances and one legal issue, therefore it received 2.1."

✅ That's what they want.

---

# Why are they saying "defend your score"?

Imagine a client asks:

> "Why did Vendor A score 4.2?"

You should be able to answer every point.

For example:

```
Risk = 4.2 because

+ Recent ransomware attack (+20)
+ Expired SSL (+10)
+ Domain only 6 months old (+5)
+ No ISO certification (+15)
+ Financial losses (+10)

Final = 60/100
```

Every number should have a reason.

---

# What is Third-Party Risk?

Suppose your company hires another company.

Examples:

* Cloud provider
* Payroll company
* Software vendor
* Payment gateway
* Law firm

They become your **third party**.

If they get hacked...

You may also suffer.

So companies evaluate vendors before signing contracts.

Normally this takes weeks.

Your system should reduce that to minutes.

---

# What should your project do?

Input:

```
amazon.com
```

↓

Collect data

↓

Analyze

↓

Score

↓

Output

```
Vendor Risk Report
```

That's the entire workflow.

---

# What should you build first?

The client already tells you the order.

## Step 1. Research

Do **not** write code yet.

Find possible public data sources.

Example:

| Source           | What does it tell us?     |
| ---------------- | ------------------------- |
| Company website  | Basic company information |
| Google News      | Bad publicity             |
| SSL Labs         | SSL security              |
| WHOIS            | Domain age                |
| Security Headers | Website security          |
| NVD/CVE          | Known vulnerabilities     |
| OFAC             | Sanctions                 |
| Companies House  | Company registration      |

---

## Step 2. Check legality

For every source ask:

* Can I scrape it?
* Does it provide an API?
* Is it free?
* Is it allowed by its Terms of Service?

The client repeatedly says:

> If you're unsure...

**Ask before collecting.**

---

## Step 3. Decide which sources are most useful

Don't collect 100 sources.

Collect maybe 6 to 10 high-quality sources.

The client says:

> Depth over breadth.

Meaning:

Better to do 6 sources well than 30 poorly.

---

## Step 4. Design the scoring model

This is the biggest task.

Example:

| Category      | Weight |
| ------------- | ------ |
| Cybersecurity | 35%    |
| Compliance    | 20%    |
| Financial     | 20%    |
| Legal         | 15%    |
| Reputation    | 10%    |

Each category gets its own score.

Then combine them into one overall score.

---

## Step 5. Build the collectors

Only now start coding.

Each collector fetches one type of data.

Example:

```
Collector 1

Input:
google.com

↓

Output:
SSL valid
```

Another:

```
Collector 2

↓

Domain age
```

Another:

```
Collector 3

↓

Recent news
```

Eventually all collectors produce one structured dataset.

---

## Step 6. Produce the report

Example:

```
Vendor:
Google

Cyber Risk:
Low

Compliance:
High

Infrastructure:
Excellent

Financial:
Very Stable

Overall Risk:
1.8 / 5

Confidence:
93%
```

---

# What should you submit?

The brief asks for five deliverables.

1. **Research document**

   * Data sources
   * What each source provides
   * Reliability
   * Legal status

2. **Working PoC**

   * Enter a vendor
   * Collect public information
   * Build a structured risk record

3. **Scoring model**

   * Categories
   * Weights
   * Formula
   * Justification

4. **Sample client report**

   * A polished vendor scorecard

5. **Roadmap**

   * How this could become part of the full Third-Party Risk platform

---

# What the client cares about most

If I ranked their priorities from highest to lowest:

1. **A sensible, explainable scoring model** ⭐⭐⭐⭐⭐
2. **Legal use of public data** ⭐⭐⭐⭐⭐
3. **Clear methodology and documentation** ⭐⭐⭐⭐☆
4. **A working proof of concept** ⭐⭐⭐⭐☆
5. **Code quality** ⭐⭐⭐☆☆

---

## In one sentence

The client wants you to build a proof of concept that takes a vendor name or website, gathers lawful public information about that vendor, and produces a client-ready risk report with an overall score that is backed by a clear, documented, and defensible scoring method.
