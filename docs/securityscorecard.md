A Closer Look at Scoring 3.0 Vocabulary and Breach Likelihood

maddy maletz
8 months ago Updated
FollowNot yet followed by anyone
The cybersecurity landscape continues to transform, reflecting the ever-changing spectrum of threats and an escalating number of breaches annually. SecurityScorecard is thrilled to announce the launch of Scoring 3.0 coming on April 9, 2024, an advancement that will revolutionize the way breach likelihood is assessed.

Breach Likelihood Defined
Central to the SecurityScorecard framework is the concept of "breach likelihood." This term is the gold standard in the security ratings industry, where organizations leverage objective assessments to evaluate their security posture. The scoring system, ranging from 'A' to 'F,' categorizes companies based on the number of assets and issues detected on their Scorecard. Notably, organizations with an 'F' score face a higher breach likelihood.

With Scoring 3.0, companies with an 'F' rating will be a staggering 13.8 times more likely to suffer a breach than those with an 'A' rating. The question we most commonly receive: how has SecurityScorecard arrived at such a precise breach likelihood?

Unveiling the 13.8x Breach Likelihood
Previously, the Total Score was derived from the weighted average of 10 Factor Scores, each shedding light on specific vulnerabilities grouped into different categories. However, Scoring 3.0 takes a leap forward by calculating the Total Score based on 200+ weighted issue types and the volume of corresponding findings.

Using 15,000 breaches in the last 4 years, our Data Science team led the analysis to assign a risk-based weight for every issue type, leading to "Breach Risk." Issue types with higher correlation for breach had a higher weight and issue types with lower correlation for breach resulted in lower weights.This dynamic, data-centric approach promises a more accurate reflection of breach likelihood through SecurityScorecard ratings using proven breach history correlated across +200 issue types.

Severity Levels Redefined
Critical to understanding Scoring 3.0 is the redefinition of severity levels. The severity column in the issues page is directly representative of 'Breach Risk,' clearly outlining the impact on an organization's score. Four distinct levels – High, Medium, Low, and Info – classify issue types based on their correlation with breach incidents:

High: This issue type had significant correlation with breach
Medium: This issue type had medium correlation with breach
Low: This issue type had low correlation breach
Info: This issue type had insignificant correlation with breach or the issue type weight will be updated at a later date
This granular classification provides organizations with a nuanced view of their security posture, empowering them to address vulnerabilities with a strategic focus.

The Scoring 3.0 View & Recommendations
We have enabled a toggle to view Scoring 3.0. When Scoring 3.0 is turned on, users gain visibility into their organization's score exclusively based on the gold standard of breach likelihood. This refined approach ensures that the scoring system aligns more closely with real-world breach scenarios, offering organizations a clearer understanding of their security standing.

Leading up to the official cutover of Scoring 3.0, we recommend you review issue types that have the biggest impact on your organization's score. Remediating issues in this preview will improve the score for both Scoring 2.0 and Scoring 3.0 depending on the weight of that specific issue type. This also requires continuous validation of your digital footprint, ensuring that your rating is as accurate as possible.

As we work toward the arrival of Scoring 3.0 in April 2024, SecurityScorecard continues to lead the charge in revolutionizing how breach likelihood is assessed. The result of data-driven insights and a redefined scoring algorithm positions Scoring 3.0 as a pivotal advancement in the world of security ratings.

Prepare for Scoring 3.0

Mark Glinski
8 months ago Updated
FollowNot yet followed by anyone
On April 9, 2024, SecurityScorecard introduced Scoring 3.0, an updated methodology that tightens the correlation of scores to breach likelihood. 

We introduced a preview of Scoring 3.0 on September 13, 2023, to help you prepare for the permanent changeover. During this introductory period, you were able to see your previous, official Scorecard score that reflects our previous methodology and compare it with your upcoming Scoring 3.0 score.

Please watch the video below or this webinar to understand how we developed our new scoring algorithm, what changes were made, and how it will benefit your organization.



When is this change happening?
The cutover to Scoring 3.0, occurred on April 9, 2024. To ensure that you have access to Scoring 3.0 within the platform on April 9, the deployment is strategically commenced on Monday, April 8 at 4pm ET. This timing helped minimize disruption to our valued users.

Upon logging into SecurityScorecard on Tuesday, April 9, you will observe that the toggled view is no longer available and your score will reflect the new Scoring 3.0 score. 

As of Thursday, April 9, all areas of the platform have been updated to reflect the new scoring.

How 3.0 is different
The new methodology features several major changes:

In 3.0, the overall Scorecard score directly reflects all the security issues that we discover on an organization's internet-facing assets. This differs from our current scoring methodology, where the overall Scorecard Score is a weighted average of 10 factor scores. 
Factors in 3.0 no longer have weights. They have numeric scores of 0 to 100. Issue types in 3.0 continue to have weights. This makes the scoring calculation process clearer and simpler to understand.
Certain issue types have different severity levels and score impact in 3.0 compared to the current scoring methodology. Some are lower and some are higher See the Cybersecurity Signals in our scoring methodology white paper, where you can compare severity levels in both methodologies.
Letter grades below A in 3.0 have greater correlations to breach likelihood:
Grade	Breach likelihood in current methodology	Breach likelihood
in 3.0
A	1x	1x
B	2.6x	2.9x
C	4.3x	5.4x
D	6x	9.2x
F	7.7x	13.8x
How you can prepare for the changeover to 3.0
Depending on the issue findings on your Scorecard, your score may change significantly. Use the 3.0 preview to help you adjust your issue resolution priorities accordingly in advance of the April, 2024 changeover.

Go to Issues tab in your Scorecard and turn on the the 3.0 preview.
Compare the breach risk levels and score impacts for 3.0 and the current methodology.

scoring_30_issues.png
Please take advantage of this free-trial offered in collaboration with one of our partners, Red Sift. Red Sift can help improve a company’s cybersecurity rating by proactively addressing SecurityScorecard issues that indicate unsafe behaviors and a high-likelihood of a breach.

Issue Type Severity Feedback
Please use this feedback mechanism on the issue type details page to provide feedback and drive future scoring decisions.

Threat Level:

Threat Level indicates the severity identified by SecurityScorecard threat experts as High, Medium, Low, or Info. These are based on their understanding of the threat and can be defined as below: 

Issue	Impact	Action
Info	Minimal or no impact, would likely not result in material loss	Monitor; Record for future reference
Low	Minor impact, would likely not result in material loss	Review; Apply minor fixes
Medium	Noticeable impact, would likely result in material loss	Investigate; Implement remedial actions
High	Significant or severe impact, highly likely would result in material loss	Immediate investigation; Implement strong countermeasures
Breach Risk:

Breach Risk indicates the level of seriousness based on our data-driven approach of correlation to breach. Our Data Science team assessed over 15,000 breaches to identify a correlation to breach and issue types. Based on that assessment, the issue types have levels of High, Medium, Low, or Info. 

Based on the definitions above, we are gathering your feedback on whether the score impact should be high, low, or if it looks good. Your feedback is extremely valuable to us and your responses will be considered for future scoring recalibrations.

Find the below feedback mechanism in the details page of each issue type. 

My Scorecard view: You can view the issues and provide feedback on your own scorecard. 


Other’s Scorecard view: You can only view the issues on others' Scorecards. 


Scoring 3.0 Recalibrations
Weights and breach risk levels of issue types are reviewed based on your feedback as we continue to improve and refine Scoring 3.0.

December 6, 2023
Issue Type	New Scoring 3.0 Level
Website Copyright is current	INFO
Unsafe implementation of Subresource integrity	LOW
Cloud Provider Service Used	INFO
Email exposed	MEDIUM
Potential vulnerability detected	INFO
Website does not implement X-XSS-Protection Best Practices	INFO
 
Recommended Next Steps:

In the near future, we plan to apply substantial weights and breach risk levels to each of the CVSSv3 issue types. We encourage you to focus your efforts on remediating CVSSv3 issues in their current state. If these issues remain unresolved, you will see large score impacts in the next scoring 3.0 recalibration.

Recommended actions to improve your score
Follow these recommendations to begin improving your score.

FAQ
Why is SecurityScorecard updating the scoring methodology?
Changing the scoring algorithm improves breach predictability. 

Additionally, the new methodology clarifies the scoring calculation process with a direct correlation between issue types and overall score.

We are committed to constantly improving our methodologies to accurately reflect the current, dynamic state of cybersecurity, so that our you can make the most informed decisions about how to manage your cyber risk.

How often do scoring algorithm changes occur?
Our scoring algorithm changes every three to four years.

How will Scoring 3.0 impact the score data on the History page?
When the full changeover to 3.0 happens in April 2024, the History page will start to show Scoring 3.0 data on the platform while retaining the historical data Scoring 2.0 data prior to the cutover.

What are the scanning frequencies for Scoring 3.0?
The frequencies is identical to those for the current methodology. See the Cybersecurity Signals in our scoring methodology white paper for frequencies.

Which of the two scores in the platform should I pay attention to ?
While remediating issue types will improve the score for both methodologies, the specific impact will be different depending on the breach risk level of that specific issue type. 

If I resolve issue findings on my Scorecard, will both scores increase?
Yes, if you remediate issues on your Scorecard, both 3.0 scores will increase differently due to different issue breach risk levels.


How SecurityScorecard calculates your scores

Catherine Fuentealba
1 month ago Updated
FollowNot yet followed by anyone
Your Scorecard rating reflects your organization's security posture and is an objective, data-driven, and quantifiable measure of its overall cybersecurity performance. Your letter grade (A through F) and the numeric score to which the grade is mapped (100 through 0) correspond to the likelihood of your organization sustaining a breach.

Scorecard ratings help organizations manage internal and third-party cyber risk. Some of the top benefits of these ratings include :

Continuously monitoring the cyberhealth of your entire ecosystem
Gaining insight into the cyber posture and security practices of your organization and partner organizations
Accelerating business opportunities and partnerships
Providing security assurance to existing and potential customers
Realizing enhanced data protection
Benchmarking security progress and comparing to industry performance
Providing transparency to organizational stakeholders
The lower the score, the greater the likelihood. An organization with an F grade (score of 60 or lower) is statistically 13.8 times more likely to sustain a breach than an organization with an A (score of 90 to 100). 

For details on how our scoring works, see our Scoring Methodology Whitepaper.

Issues: The main components of your scores
Your score shows the security issues we find in your organization's internet-facing assets, along with other factors in our scoring methodology.

Issue types
We discover security issues in your exposed network assets during our recurring internet scans. You can view these on the Issues tab of your Scorecard. Each issue type may include multiple findings on your Scorecard, or instances where we observed the issue, for example, on different IP addresses.

Each of these issue types has a High, Medium, or Low severity level, which reflects the degree of risk to your organization.

These severity levels, in turn, have varying weights, or degrees of negative impact on your score, from High (greatest impact) to Low (least impact). 

Note: Some issue types do not impact your score. Positive issues highlight healthy security practices that can mitigate risk. Informational issue types identify areas of risk worth inspection. Over time, we may assign score-impacting severity levels to certain Informational issue types, as noted in our scoring updates.

Factors
Every issue type that appears on your Scorecard is grouped within one of 10 factors, including Network Security, DNS Health, Patching Cadence, Endpoint Security, IP Reputation, Application Security, Cubit Score, Hacker Chatter, Information Leak, and Social Engineering. These are the categories of cyber risk and protection that SecurityScorecard uses to assess and score your organization’s security resilience. Each factor has a numerical score that reflects the severity or risk it contributes to the overall cybersecurity posture.

Factor score calculation is based on the severity and quantity of issues or findings associated with the factor.

Operations that contribute to the calculation of your scores
The calculation of scores follows, and is informed by, a sequence of three major operations that produce the issue findings in your Scorecard.

Signal collection
Attribution
Signal analysis
Signal collection
We scan the entire IPv4 web space, more than 3.9 billion routable IP addresses, every 10 days across more than 1,400 ports.

Note: We scan cloud assets multiple times daily because they change ownership so frequently.

Our in-house global internet scanning framework collects all the information that threat actors would see as they search for attack targets:

IP addresses
Exposed port mappings
Fingerprints of services, products, libraries, operating systems, devices, and other internet-exposed resources, including version numbers
Common Platform Enumeration (CPE) IDs
Common Vulnerability Enumeration (CVE) Version 2 IDs
Script output from Nmap, the open-source scanner that is one of the components of our own scanning framework.
Additionally, we monitor signals across the internet using a network of sensors spanning three continents. We operate one of the world’s largest networks of sinkholes and honeypots to capture malware signals and further enrich our dataset by leveraging commercial and open-source intelligence.

We supplement our data collection with external feeds from public and commercial data sources. These additional data-gathering methods help produce issue types related to leaked data.

Attribution
At this stage, we associate the collected signals with IPs or related domains, then match them to an organization based on its digital footprint. We use a number of reliable sources, such as DNS lookups, to make attribution as accurate as possible.

We also encourage you to validate these attributions by claiming and refuting assets, and by adding them to the digital footprint.

Analysis of signals
We used a suite of analytics tools developed by our threat researchers, data scientists, and engineers to derive issue findings and other key insights from the signals we collect. Examples of analysis include:

Identification of malware strains and characterization of their behavior and threat level
Identification of CVEs and other vulnerabilities based on examination of digital asset identification in HTTP header data, website code bases, communication protocols, secure socket layer (SSL) certifications, and more
We also apply machine-learning algorithms to improve the quality and accuracy of security findings and provide key insights on security posture.

Our scoring methodology
Issue types are primary components of your score calculation, but other important considerations and adjustments help ensure that the calculation is as fair and accurate as possible.

Size normalization
A small or mid-size organization has fewer IPs than a large enterprise, so it has fewer issue types. That does not mean it is more secure than the enterprise.

Our scoring methodology uses a logarithmic scale, where each increment corresponds to a multiple of 10. Richter and decibel scales are based on similar approaches. For each issue type, we generate scatter plots in which each organization we score (more than 12 million) is represented as a point, showing how the number of occurrences of a given issue varies with organization size. 

For example, one organization has three findings for the DNS open resolver issue type. Based on our analysis of more than 12 million organizations, only 12 percent of organizations of comparable size have this security flaw. And among those organizations, the average number of findings is 2, while this organization has 3, which is worse than average.

Calibration
We apply a calibration algorithm to each scored issue type, using two months of collected data to smooth out statistical fluctuations. This ensures fair performance comparisons for organizations of similar size.

Calculation of issue, factor, and overall scores
We calculate scores for issues using a modified "z-score”, where z = 0 if no findings are present, while z = 1 when the number of findings equals the mean for organizations with the same size Digital Footprint.

To calculate each factor score, we first compute the raw total score by summing the z-scores for issue findings, each multiplied by its weight.

After calculating the raw total score, we scale it based on the expected distribution of issue-finding counts. We want to fairly score an organization by comparing it to others with similar Digital Footprint sizes. Informational and positive issues do not contribute to the score.

Breach penalties
For the scoring impact of breach penalties, see Understand how breaches affect your score.

Updates and recalibrations
We update factor and total scores daily. We also calculate and update modified z-scores daily for every organization and issue type on the SecurityScorecard platform. This ensures inherently low score volatility. If an organization's digital footprint and issue counts remain stable, its security score will remain unchanged.

Additionally, SecurityScorecard recalibrates its scoring algorithm every quarter. 

We maintain a regular scoring update cadence to keep cybersecurity risk ratings fair in a dynamic threat environment and to introduce new issue types as needed, so you stay better informed about threats to your organization and vendor ecosystem.

Validation
SecurityScorecard’s scoring algorithm has passed rigorous internal verification and validation testing, in which we determine whether its outputs conform to the inputs. We subject the algorithm to a battery of statistical tests, including edge cases, to verify its accuracy and stability.

This testing determines whether the scoring algorithm meets its intended use as a cybersecurity risk assessment tool, i.e., whether low scores correlate with a higher likelihood of an adverse event.