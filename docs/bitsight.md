How are Bitsight Security Ratings Calculated?
 Ingrid
Not yet followed by anyone
For each rated organization, we intelligently identify and classify behaviors emanating from that organization’s network assets, including communication with Command and Control Server (C&C or C2 Server), participation in a Distributed Denial-of-Service (DDoS) attack, malware distribution, network scanning, and email attacks. The machines participating in these behaviors are generally under the control of external adversaries. While these behaviors may not equate to data loss, each is evidence of a compromise. Evidence from sensors deployed across the globe is collected daily. Each individual security event is analyzed for confidence, severity, and duration, and then mapped to a specific organization.

We also gather and analyze data for security issues with Internet communications (open ports, encryption settings, e-mail, etc.), software on endpoint devices and infrastructure (currency of versions, vulnerability remediation practices, etc.), as well as published applications (both web and mobile).

In addition, we gather externally observable configuration information on rated organizations.

Example: We may include analysis of Sender Policy Framework (SPF) records, Transport Security Layer / Secure Sockets Layer (TLS/SSL), and DomainKeys Identified Mail (DKIM) signatures. Failure to use best practices increases risk and therefore negatively impacts a company’s security rating.

The following bullets are jump links to help you find information faster. Click any of the 5 options below to navigate directly to that content. Jump to:

⬇️ Algorithm arrow down emoji

⬇️ Risk Category Weights

⬇️ Letter Grades

⬇️ Finding Grades

⬇️ Normalization

We do not engage in any hacking or any intrusive network penetration testing. Our collected data is externally observed from various sources in the public internet. It is available to anyone who chooses to collect it and has the technological capabilities to do so.

Algorithm
Bitsight Security Ratings are calculated daily using a proprietary algorithm that examines two classes of externally observable data – configuration and security events. Security effectiveness is assessed across the following risk categories:

Compromised Systems
Diligence
User Behavior
Public Disclosures
The ratings algorithm accounts for the following elements:

Number and Type(s) of Compromised Systems: Data is classified into risk vector types and factored into an organization‘s security rating accordingly.
Event Duration: Calculates the time between when the compromised system was first observed and when it was last seen.
Diligence Configurations: Shows steps an organization has taken to prevent attacks. Similar to Compromised Systems, data is classified into risk vector types and factored into an organization‘s security rating accordingly.
Security ratings are the results of the aggregation of all risk vector letter grades (with different weights) that are normalized for that company.

Learn more about the rationale for rating thresholds and why security ratings may fluctuate.

Risk Category Weights
Risk categories are weighted as follows:

Compromised Systems = 26%
Diligence = 71.5%
User Behavior = 2.5%
Public Disclosures = Weighted only if they occur.
Letter Grades
Letter grades provide a quick way to understand how a company is performing in each risk type and also provides a meaningful way to compare risk type performance of one company to another.

Letter grades are directly correlated to how well a company is performing, relative to all companies in the Bitsight inventory. Below is a table that outlines how each grade correlates to their performance, relative to their company size.

Individual Company Reports provide greater precision than letter grades.

A
In the top 10% of companies.

B
In the top 30% of companies.

C
In the top 60% of companies.

D
In the bottom 40% of companies.

F
In the bottom 20% of companies.

N/A
This grade has no correlation with how a company is performing. If a letter grade is “N/A” (Not Available), it may be because:

The risk vector is “informational.”
The grade defaults to it, in the absence of findings.
The risk vector is going through an evaluation period before having an impact on the rating.
Finding Grades
Diligence findings are graded as GOOD, FAIR, WARN, BAD, or NEUTRAL based on inherent risk and if best practices can be improved upon. These finding grades contribute towards the letter grade of the risk vector.

GOOD
Low risk, aligned with best practices. These have a significantly positive impact on the letter grade.

What should I do with my good findings?

Further action is not required.

FAIR
Light risk and some opportunity to achieve best practices. These have a minor negative impact or no impact on the letter grade depending on the risk vector.

What should I do with my fair findings?

There is some opportunity to achieve best practices. Review the finding details.

WARN
Moderate risk and departure from best practices. These have a moderately negative impact on the letter grade.

What should I do with my warn findings?

Review the finding details.

BAD
Significant risk and departure from best practices. These have a significantly negative impact on the letter grade.

What should I do with my bad findings?

Review the finding details.

NEUTRAL
Observed data with neither positive nor negative risk. This does not positively or negatively impact the letter grade.

What should I do with my neutral findings?

Further action is not required.

N/A
Finding grades are not applicable (N/A) to Compromised Systems and User Behavior.

Normalization
Large companies will typically have more findings than smaller companies. To ensure ratings are calculated in a way that doesn't unfairly penalize large companies, we normalize ratings based on the size of an organization. We compare organizations using applicable notions of size -- e.g. employee count, magnitude of digital footprint, overall count of observations, etc. -- to quantify the attack surface.

Frequently Asked Questions
Are all findings of a given company displayed?
For most companies, findings throughout the past 1 year are shown and a complete list can be obtained through the Bitsight API. Companies with over 10 million findings have a sampled view of their findings, meaning that not all of them are visible in the platform.

What do sharp changes in a rating mean?
Sudden drops in rating can occur due to publicly disclosed Security Incidents, an increase in Compromised Systems events, or poorly configured Diligence findings. Improvements in ratings are due to either many simultaneously resolved events or updates to Diligence findings. Any decreases of 10 points or greater are highlighted in a company‘s Overview page, next to its 1-year historical trend graph.

When is a security rating impacted?
Depending on the risk type, they continue to impact the rating over a decay period, or until  Bitsight is able to confirm the risk is no longer present due to remediation or decommissioning of the associated asset(s).

Please refer to the lifetime, duration, and decay of the following findings:

The duration of Compromised System events
The impact & lifetime of Diligence findings
The lifetime of File Sharing events
The severity & decay of Security Incident events
What is a Bitsight Security Rating?
 Jessica
Not yet followed by anyone
Bitsight Security Ratings describe an entity's cybersecurity posture, serve as a measure of their risk, and transform how entities manage security risk by using a data-driven, outside-in approach to rate an entity's security effectiveness.

We provide daily security ratings through an automated service that leverages 1 year of supporting data. The sophisticated analytics and alerting capabilities provide risk managers the insight they need to proactively identify, quantify, and mitigate the risk of being exposed to a breach, unlike the manual and subjective assessments used to manage risk today.

How Security Ratings are Presented
We rate companies on a scale of 250 to 900, with 250 being the lowest measure of security performance and 900 being the highest. The upper and lower edges of this range are reserved for future use. Currently, the effective range is 300-820.

Security Ratings are the results of the aggregation of all risk vector letter grades (with different weights) that are normalized for that entity (as outlined in the risk vectors overview).

Security ratings are based on a 10-point rating system that’s rounded down in 10 point increments. If the current rating is 740, this is a representation of the combined assessments of all risk vectors. The rating may be somewhere between 740 and 749 in actuality.

The rounding method is set so that any change in the rating can be traced back to at least one risk vector. This is so the rating is more explainable in instances where 10-point changes in the security rating could not be explained by a corresponding change to any risk vector

Example: An actual rating of 735 is represented as a 730.

Learn how Bitsight Security Ratings are calculated.

Rating Categories
We use rating categories to help indicate the overall security performance of rated entities. In aggregate, entities with higher ratings have stronger security performance and lower cyber risk than entities with lower ratings. The average rating is 720. As the rating decreases, the risk an entity poses increases.

Each entity's rating falls into one of the following categories:

Category	Meter	Security Rating Ranges	Description	Distribution*
Advanced	Advanced rating category meter	740 – 900	Strong security performance and lower risk	60% of entities
Intermediate	Intermediate rating category meter	640 – 730	Fair security performance and moderate risk.	35% of entities
Basic	Basic rating category meter	250 – 630	Poor security performance and higher risk	5% of entities
*The approximate distribution of entities in the entire Bitsight inventory, across the rating categories.

A majority of the scoring scale is reserved for the bottom half of all entities. This is because there are more ways an entity can be considered “basic” than there are ways to be considered “advanced.” It’s more elusive, in that an entity will have to succeed in several key aspects to be considered “advanced.”

Correlation to Security Performance
Rating categories quickly communicate the overall risk posed by an entity. Each rating category corresponds to a different level of security performance and overall risk.

It is important to remember that no matter what, all entities have some risk of breach. If a threat actor is determined enough in targeting a specific entity, they will almost certainly be able to find a way to breach it.

Advanced: strong security performance and lower risk
Entities in this category have strong security performance and are less likely to experience a data breach. They are the lowest risk. These entities demonstrate evidence of best practice implementation and consistent risk mitigation.

Intermediate: fair security performance and moderate risk
Entities in this category have relatively fair security performance and demonstrate moderate security effectiveness. These entities provide a moderate level of risk and are, on average, 1.5 - 2x more likely to get breached than entities with Advanced ratings.

Basic: poor security performance and higher risk
Entities in this category have lower security ratings and an increased likelihood of data breach. These entities typically have not implemented best practice IT security policies and procedures, may demonstrate evidence of compromised systems on their network, and provide the greatest risk. Basic entities are, on average, 2 - 3x more likely to experience a publicly disclosed data breach than Intermediate entities; entities with a rating of 400 or lower are 5x more likely to experience a publicly disclosed data breach than entities with a security rating of 700 or higher.

Security performance as measured by Bitsight Security Ratings correlates with the likelihood of a publicly disclosed security incident and specifically to the risk of a ransomware incident.

A Guide to Navigating and Prioritizing Bitsight Risk Categories & Risk Vectors
 Ingrid
Not yet followed by anyone
Bitsight Security Ratings are generated and calculated daily, using a proprietary algorithm that evaluates an organization’s security effectiveness.

The below graphic depicts the three primary risk categories, along with their associated weightings on your Bitsight Rating. The following table breaks out the individual risk vectors included in each primary risk category, along with the associated weighting where applicable.

How to Use This Guide
By understanding how risk categories and vectors impact the Bitsight Security Rating, this information can be used to prioritize resources and maximize impact on the rating. Remediation efforts should be aligned with risk categories and associated vectors that contribute the most to the security rating.

Example
A security director sees low grades in their Mobile Software, Open Ports, Web Application Security, and Botnet Infections risk vectors. By taking a look at the below information, this director should be able to easily determine the order in how they should prioritize efforts, starting with improving the area that will impact their rating the most. They should prioritize in the following manner:

Botnet Infections: Botnet Infections are a type of Compromised System Risk Vector (26%). The company’s rating is impacted the most by this risk category because these vectors are the most correlated to breach. By focusing on improving the processes that lead to decreasing the number of Botnet Infections, they will not only improve the company’s rating, but will also improve the company’s overall resiliency.
Open Ports: As part of the Diligence Risk Category (71.5% Weighting), the Open Ports risk vector accounts for 10% (out of 71.5% in Diligence) of a company’s security rating and is a heavily weighted risk vector in the Diligence Category. Therefore, it should be the next focus of the company’s remediation and process improvement efforts. Again, the higher the weighting, the higher the correlation to breach. By focusing efforts on improving those processes, it should lead to an improved rating and greater cyber resiliency.
Web Application Security and Mobile Software: These should be focused on last among this group of risk vectors. They both fall within the Diligence risk category (71.5% weighting); however, their individual contributions to that category are 5% and 1%, respectively. In other words, improving these risk vectors will not improve the overall rating as much as improving the above two risk vectors.
Primary Risk Categories
Compromised Systems
The Compromised Systems risk category indicates the presence of malware or unwanted software, which is evidence of security controls failing to prevent malicious or unwanted software from running within an organization.

A compromised system can also lead to a disruption in daily business operations and can increase the risk of data breach.

Diligence
The Diligence risk category assesses the steps a company has taken to prevent attacks, their best practice implementation, and risk mitigation (e.g., server configurations) to determine if the security practices of an organization are on par with industry-wide best practices.

Failure to align with best practices increases the risk of a data breach.

User Behavior
The User Behavior risk category assesses employee activity, such as file sharing and password re-use. These types of activities can introduce malware to an organization or result in a data breach.

Public Disclosures
The Public Disclosures risk category provides information related to possible incidents of undesirable access to a company’s data, including breaches, general security incidents, and other disclosures. Though these events do not necessarily result in data loss, the interruptions to business continuity are relevant and can be used to improve security preparedness.

Overview of Bitsight’s Risk Categories & Risk Vectors
Risk Category	Risk Vector	Description
Compromised Systems
(26%)	Botnet Infections	
The Botnet Infections risk vector indicates that devices on a company’s network are participating in a botnet (combination of “robot” and “network”), either as bots or as a command and control (C&C or C2) server.

Companies with a Botnet Infections letter grade of B or lower are >2× more likely to experience a publicly disclosed data breach.

Spam Propagation	The Spam Propagation risk vector is composed of spambots, where a device on a company’s network is unsolicitedly sending commercial or bulk email (spam). If spam originates from email addresses or devices within a company’s network, this is an indication of an infection.
Malware Servers	The Malware Servers risk vector is an indication that a system is engaging in malicious activity, such as phishing, fraud, or scams. A company’s network is hosting malware that is meant to lure visitors to a website or send a file that injects malicious code or viruses.
Unsolicited Communications	The Unsolicited Communications risk vector indicates a host is trying to contact a service on another host. It might be attempting to communicate with a server that is not providing or advertising any useful services, the attempt may be unexpected, or the service is unsupported. This also accounts for hosts that might be scanning darknets.
Potentially Exploited	The Potentially Exploited risk vector indicates that a device on a company’s network is running a potentially unwanted program (PUP) or potentially unwanted application (PUA).
Diligence
(71.5%)	SPF Domains
(1%)	The SPF Domains risk vector assesses the effectiveness of Sender Policy Framework (SPF) records, which are DNS records that identify mail servers permitted to send email on behalf of a domain. Properly configured SPF records ensure that only authorized hosts can send email on behalf of a company by providing receiving mail servers the information they need to reject mail sent by unauthorized hosts.
DKIM Records
(1%)	The DKIM Records risk vector assesses the effectiveness of DomainKeys Identified Mail (DKIM) records, which is a countermeasure against adversaries that are attempting to send fake email by using a company’s email domain. Properly configured DKIM records can ensure that only authorized hosts can send email on behalf of a company.
DMARC (1%)	The DMARC risk vector determines whether domains have a Domain-based Message Authentication, Reporting and Conformance (DMARC) policy or not and evaluates how effective it is at ensuring only verified senders are able to use this domain for email.
TLS/SSL Certificates
(10%)	The TLS/SSL Certificates risk vector evaluates the strength and effectiveness of the cryptographic keys within TLS and SSL certificates, which are used to encrypt internet traffic. Certificates are responsible for verifying the authenticity of company servers to associates, clients, and guests, and also serves as the basis for establishing cryptographic trust.
TLS/SSL Configurations
(15%)	The TLS/SSL Configurations risk vector determines if the used security protocol libraries support strong encryption standards when making connections to other machines. TLS/SSL is a widely used method of securing communications over the Internet.
Open Ports
(10%)	The Open Ports risk vector observes ports that are exposed to the Internet, known as “open ports.” While certain ports must be open to support normal business functions and few companies will actually have no ports open, the fewer ports that are exposed to the Internet, the fewer openings there are for attack.
Web Application Security
(5%)	The Web Application Security risk vector performs multiple assessments related to web application security. It provides information about components with known vulnerabilities, broken authentication and access control, sensitive data exposure, cross-site scripting prevention mechanisms, and security misconfigurations.
Critical Vulnerabilities Management
(20%)	The Critical Vulnerabilities Management risk vector evaluates systems that are affected by software vulnerabilities (holes or bugs in software, hardware, or encryption methods that can be used by attackers to gain unauthorized access to systems and their data) and how quickly any issues are fixed.
Insecure Systems
(2.5%)	The Insecure Systems risk vector assesses endpoints (which can be any computer, server, device, system, or appliance with internet access) that are communicating with an unintended destination. The software of these endpoints may be outdated, tampered, or misconfigured. A system is classified as “insecure” when these endpoints try to communicate with a web domain that doesn’t yet exist or isn’t registered to anyone.
Server Software
(2%)	The Server Software risk vector helps track security problems introduced by server software that is no longer supported. Supported software versions receive attention from the software development team and vendor when bugs or vulnerabilities are discovered.
Desktop Software
(3%)	The version information of laptop and desktop software are compared with the latest and currently available software versions to determine if the device software is supported or out-of-date.
Mobile Software
(1%)	The version information of mobile device operating systems and browsers are compared with the latest and currently available software versions to determine if the device software is supported or out-of-date.
DNSSEC*	The DNSSEC risk vector determines if a company is using the DNSSEC protocol, which is a public key encryption that authenticates DNS servers, and then assesses the effectiveness of its configuration. The DNSSEC protocol protects against DNS spoofing, which involves diverting traffic to an attacker’s computer, creating an opportunity for loss of confidentiality, data theft, etc.
Mobile Application Security*	The Mobile Application Security risk vector analyzes the security aspects of an organization’s mobile application offerings that are publicly available in official marketplaces, such as the Apple App Store and Google Play.
Web Application Headers***	The Web Application Headers risk vector analyzes security-related fields in the header section of communications between users and an application. They contain information about the messages, determine how to receive messages, and how recipients should respond to a message.
Domain Squatting**	The Domain Squatting risk vector detects the presence of domains named similarly to those that are owned and trademarked by an organization. Detection for these types of domains is based on information provided by DNS queries.
User Behavior
(2.5%)	File Sharing
(2.5%)	The File Sharing risk vector tracks the sharing of files, such as books, music, movies, TV shows, and applications. This includes files shared over the BitTorrent protocol or when observed on company infrastructure.
Exposed Credentials**	The Exposed Credentials risk vector looks at verified breaches to indicate if the employees of a company had their information publicly disclosed and posted online as a result of a successful cyber attack on their company’s third parties.
Public Disclosures	Security Incidents	The Security Incidents risk vector involves a broad range of events related to the undesirable access of a company’s data or resources, including personal health information, personally identifiable information, trade secrets, and intellectual property. They’re grouped into Breach Security Incidents and General Security Incidents.
Other Disclosures**	The Other Disclosures risk vector includes other kinds of publicly disclosed events. It’s considered to be the least severe among the Public Disclosures risk vectors. Its impact to business continuity is minimal if they were to occur.
* This risk vector is currently in beta. Therefore, it does not affect Bitsight Security Ratings.
** This risk vector is informational and does not affect Bitsight Security Ratings.

