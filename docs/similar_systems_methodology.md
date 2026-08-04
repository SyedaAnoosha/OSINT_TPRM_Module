**Several commercial platforms and tools offer functionality similar to the described OSINT-based Third-Party Risk (TPRM) product: input a vendor name/website and receive an automated risk record/score derived from public data (breaches, certificates, exposures, adverse media, etc.).**

These focus on **cybersecurity ratings**, external attack surface analysis, continuous monitoring, and OSINT signals. They emphasize defensibility, legality (mostly passive scanning/public data), and integration into broader TPRM workflows. Here's a curated list of prominent examples:

### Leading Commercial Platforms
- **Black Kite** — Provides third-party cyber risk intelligence with ratings, ransomware susceptibility indexing, continuous monitoring, and OSINT-driven insights (e.g., breaches, vulnerabilities). Strong on supply chain/cascading risk and AI agents for investigations.
- **SecurityScorecard** — Delivers security ratings (A-F or numeric) based on external scans, breach detection, and supply chain visibility (including fourth-party). Supports automated vendor detection and continuous monitoring.
- **BitSight** — Offers daily Security Ratings for vendors using public data, with TPRM features like portfolio risk matrices, fourth-party mapping, and dark web intelligence. Widely used for continuous third-party monitoring.
- **UpGuard** — Focuses on Vendor Risk with security ratings (0-950 scale), AI-powered assessments (e.g., analyzing SOC 2 reports), data leak detection, and continuous external scanning. Includes questionnaire automation and attack surface insights.

### Other Notable Tools/Platforms
- **RiskImmune Vendor Auto-Grader** — AI-powered OSINT scoring without questionnaires; analyzes 200+ signals like exposed infrastructure, certificates, DNS, dark web, CVEs, and sanctions for instant scorecards.
- **Owlin** — AI-driven third-party screening and continuous monitoring from public/online sources, with risk insights and compliance focus.
- **OneTrust** (and integrations) — Broader TPRM with cyber risk ratings from partners (e.g., SecurityScorecard, BitSight) and some OSINT/adverse media capabilities.
- **Ven-monitor** — Centralized risk profiles/ratings across domains (cyber, privacy, etc.) using external intelligence.
- **ShieldRisk AI** and similar (e.g., Panorays, Prevalent) — AI risk scoring, assessments, and monitoring with OSINT elements.

### Open-Source / Research / Niche Options
- **Fair TPRM** — Free/open-source platform with integrations for external scoring (e.g., UpGuard, Shodan) and compliance-focused vendor monitoring.
- **OSINT Risk Mapper** (GitHub) — Passive reconnaissance tool mapping digital footprints, breaches, subdomains, etc., for risk reports.
- Academic/proof-of-concept examples like **GEN-TPRM** (OSINT + LLM for ISO-aligned scoring).

**Key Commonalities**: Most rely on passive/public data (avoiding heavy scraping where restricted), produce defendable scores with evidence/rationale, support continuous monitoring, and handle patchy/stale data transparently. Many integrate AI for summarization/classification (e.g., adverse media) and aim for low-friction "vendor in, scorecard out" workflows.

**Differentiation Opportunities for Your PoC**: Emphasize a transparent, custom scoring model (with dimensions/weights/rationale), strict legality documentation per source, and extensibility. Many commercial tools are enterprise-focused/paid; a well-documented open methodology could stand out. Always prioritize free/trial data and document TOS positions, as noted in the brief. 

For deeper dives, search specific vendors or review their methodologies (many publish reports on breaches/supply chain risks).

**Scoring models in these OSINT/TPRM tools are generally designed for transparency, defensibility, and correlation to real outcomes (e.g., breach likelihood), using passive/public data collection.** They combine automated external scans, threat intelligence, and (sometimes) questionnaires. Here's how the main ones work, based on their documented methodologies:

### **Black Kite**
- **Structure**: 298+ controls (based on MITRE ATT&CK/CTSA, CWSS, CVSS, etc.) grouped into ~20 risk categories (e.g., Application Security, Patch Management, Brand Monitoring, DNS Security).
- **Calculation**: 
  - Controls scored individually (using CWSS/CWRAF and remediation factors).
  - Category scores averaged from controls, then weighted (e.g., higher weight for critical areas like patching or app security).
  - Overall grade (letter) via weighted average of categories.
- **Additional Layers**: Ransomware Susceptibility Index, Open FAIR™ for financial impact quantification, compliance mappings. Emphasizes hacker-perspective OSINT and standards (MITRE, NIST) for defensibility. Continuous, non-intrusive.
- **Philosophy**: Fully transparent and auditable; avoids arbitrary scoring.

### **SecurityScorecard**
- **Structure** (Scoring 3.0): 10 risk factors (e.g., Network Security, Application Security). Hundreds of issue types with severity (High/Medium/Low/Info) tied to breach correlation.
- **Calculation**:
  - Scans collect signals → issues attributed → analyzed.
  - Size normalization (logarithmic/z-score) for fair comparison across org sizes.
  - Issue z-scores weighted by severity/breach risk → factor scores (0-100) → overall score/letter grade (A-F).
  - Trained on 15k+ breaches for strong predictive power (F-rated orgs ~13.8x more likely to breach).
- **Philosophy**: Data-driven, breach-outcome focused, with machine learning tuning. Monthly updates.

### **BitSight**
- **Structure**: Risk vectors grouped into main categories: Compromised Systems (~27%), Diligence (~70.5%), User Behavior (~2.5%), plus Public Disclosures. Vectors include botnets, spam, patching, TLS config, open ports, etc.
- **Calculation**:
  - Daily analysis of configuration data + security events (frequency, severity, duration).
  - Letter grades per vector (normalized for size, e.g., per-employee for some).
  - Weighted aggregation into overall numeric rating (300-820 scale, effectively ~300-820; rounded in 10s).
- **Philosophy**: Credit-score style; focuses on externally observable behaviors correlated to risk. Annual methodology updates with governance.

### **UpGuard**
- **Structure**: 10 risk categories (e.g., IP/Domain Reputation, Website, Encryption, Vulnerability Management, Attack Surface). Hundreds of individual checks.
- **Calculation** (subtractive):
  - Assets (domains/IPs) start at 950.
  - Deductions weighted by severity (critical/high/medium/low) per failed check.
  - Asset scores → Gaussian weighted average (penalizes weak links more) for org score.
  - 50% automated scans + 50% questionnaires (if used).
  - Letter grades (A-F) mapped to numeric ranges.
- **Philosophy**: Weakest-link emphasis via Gaussian averaging; CVSS for vuln severity. Daily updates, passive collection.

### Common Design Principles Across Tools
- **Passive/OSINT Focus**: Non-intrusive scans (ports, certs, DNS, leaks, etc.) + public sources. No active exploitation.
- **Normalization**: Adjust for org size/digital footprint to avoid biasing larger entities.
- **Weighting & Predictiveness**: Heavier weights on high-impact signals (e.g., compromises, patching). Often validated against breach data.
- **Output**: Numeric score + letter grade, with drill-down evidence for defensibility. Continuous monitoring (daily/near-real-time).
- **Transparency**: Many publish methodologies, adhere to "Fair & Accurate Security Ratings" principles, and allow disputes.
- **Hybrid Elements**: Combine pure OSINT with optional questionnaires/AI summarization for completeness.

**For Your PoC**: These models succeed by being **explainable** (why a score changed), **weighted by real risk** (breach correlation), and **balanced** (categories + overall). Propose dimensions like Technical Hygiene, Exposure/Breaches, Reputation/Media, Compliance Signals, etc., with clear weights/rationale you can defend. Document data sources' reliability/limits and use subtractive or z-score approaches for intuitiveness.

check this:
https://help.bitsighttech.com/hc/en-us/articles/231352528-What-is-a-Bitsight-Security-Rating
https://help.bitsighttech.com/hc/en-us/articles/360007320574-A-Guide-to-Navigating-and-Prioritizing-Bitsight-Risk-Categories-Risk-Vectors
https://support.securityscorecard.com/hc/en-us/articles/8366223642651-How-SecurityScorecard-calculates-your-scores
https://support.securityscorecard.com/hc/en-us/articles/16235105523739-Prepare-for-Scoring-3-0
https://support.securityscorecard.com/hc/en-us/articles/22601556325147-A-Closer-Look-at-Scoring-3-0-Vocabulary-and-Breach-Likelihood
https://blackkite.com/blog/cybersecurity-ratings
https://cwe.mitre.org/cwraf/
https://cwe.mitre.org/cwss/cwss_v1.0.1.html
https://help.bitsighttech.com/hc/en-us/articles/231950968-How-are-Bitsight-Security-Ratings-Calculated
https://help.upguard.com/en/articles/3765184-how-are-upguard-s-security-ratings-calculated
https://help.upguard.com/en/articles/3765166-what-are-security-ratings
