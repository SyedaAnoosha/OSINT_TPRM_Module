**`PROJECT 05  ·  INTERN BRIEF`**

OSINT for Third-Party Risk

*Enter a vendor name or website — get back a risk record and an overall score, assembled automatically from publicly available information.*

**The opportunity**

Assessing a vendor today means questionnaires, chasing evidence, and waiting weeks for answers the vendor writes about itself. Meanwhile the public record already says a great deal: breaches, expired certificates, exposed infrastructure, adverse media, sanctions, financial distress. We want a product that reads that public record for you — vendor in, structured risk record and score out.

This is a proof-of-concept, not a platform. Prove the idea on a handful of real vendors and prove it well. The lasting value is not the code: it is the methodology and the scoring model — the part that has to stand up when a client asks why a vendor scored what it did. That IP is deliberately undefined. It is yours to propose and defend.

**How we’d like you to approach it**

Research and method first, collectors second, scoring third. We care as much about how you reason as about what you ship — and here, legality and defensibility come before coverage.

* **Assess the sources before you touch them —** what each one signals, how reliable it is, its limits, and its legal and terms-of-service position. Document that position per source, and rule out anything you cannot use lawfully.

* **Scope tightly —** pick a prioritised subset of sources and a handful of named test vendors. Depth over breadth; a few signals collected well beat twenty collected badly.

* **Design the scoring model as the real deliverable —** what dimensions, what weighting, how signals roll up, and why. Be able to defend any score you produce.

* **Be honest about confidence —** public data is patchy and often stale. Say what a signal does and does not tell you.

Show your reasoning and cite your sources — we expect you to teach us what you find.

**What you’ll show us**

* **A research methodology document —** which sources, what each signals, how it is collected, reliability and limits, and the legal / terms-of-service position for each.

* **A working proof-of-concept —** for a handful of named vendors, pulling public signals into a structured risk record.

* **A v1 scoring model —** dimensions, weighting logic, how signals roll up to an overall score, and the rationale behind it.

* **A sample output —** a clean, presentable vendor risk record or scorecard a client would accept.

* **A roadmap —** how this productises and aligns with the wider TPRM platform, and what you would collect next.

**How we’ll work together**

A short weekly check-in, a mid-point review, and a handover at the end. You have deep in-house third-party risk and cyber expertise on hand — use it to pressure-test whether your signals and scores are credible. Ask early when your confidence is low; “I’m not sure yet, here’s what I’m testing” is exactly what we want to hear.

**What good looks like**

A demonstrable PoC scoring a handful of real vendors, backed by a defensible methodology and a documented scoring model — simple is fine, arbitrary is not. Every source is lawful and its position written down. The work is clearly extensible toward the platform, and the methodology and scoring IP are documented well enough to outlive the internship.  
**`PROJECT 05  ·  HOW WE WANT YOU TO BUILD IT`**

Standards & future direction

*These apply to everything you ship for us. Read them before you start — not at the end.*

**Non-negotiables**

* **Legality first.**  Respect each source’s terms of service and the law on scraping and automated collection. Document the position per source and avoid prohibited sources. If you are unsure, ask before you collect — not after.

* **Free or trial data only.**  No paid feeds. If a source only works behind a paywall, note it as a future option and move on.

* **Handle what you collect carefully.**  This is information about real companies. Store it sensibly, and do not republish or expose it.

**Future direction — think beyond v1**

* **AI integration.**  Look for natural places where AI does work the user would otherwise do by hand — reading adverse media and summarising what actually matters, or classifying a trust page’s certifications. Don’t bolt it on; find the moments where it genuinely saves effort.

* **Agentic AI.**  Go a step beyond answering. Where could the system act on the user’s behalf — re-checking a vendor on a schedule and raising a flag when its score moves, rather than waiting to be asked?

* **Speed to answer.**  Design around the user’s actual goal: a defensible view of a vendor. How few steps from vendor name to scorecard? Every extra click or screen is friction.

**Craft — what makes it client-ready, not a prototype**

* **The small things.**  Don’t overlook empty states, error messages, loading indicators, edge cases and sensible defaults — especially a source returning nothing, or timing out. These separate a prototype from something client-ready.

* **Clear labelling.**  Make it obvious what’s a heading and what’s an action. Buttons should say what they do (“Score vendor”, not “Submit”); titles should describe the content beneath them.

* **Consistency.**  Keep spacing, fonts, colours and wording consistent across screens. Inconsistency reads as unfinished, even when the logic underneath is sound.

* **Mobile and resize.**  Check how it behaves on smaller screens and when the window is resized. What looks fine on your monitor often breaks elsewhere.

* **Accessibility basics.**  Readable contrast, sensible text sizes, and labels that work for keyboard and screen-reader users. Easy to build in early, painful to retrofit.

* **Realistic test data.**  Don’t shortcut with “test test”, “asdf” or “Acme Corp”. Use real vendors and real signals — a vendor with a long history of breaches, one with almost no public footprint, an expired certificate, a very long company name. Placeholder junk hides bugs: overflowing fields, broken layouts, validation never tested.


OSINT for Third-Party Risk.

The idea is straightforward to describe and hard to do well — someone enters a vendor name or website, and the system returns a risk record and an overall score assembled from publicly available information.

A few things I want to be clear about up front.

This one matters. The strongest work here is a serious candidate to go into our Wahid AI platform as an option under the third-party module. That is not a guarantee, but it is a real prospect, and it should shape the standard you hold yourselves to — client-ready, not a prototype.

The scoring model is the actual deliverable. The code matters less than the method. We have deliberately left the scoring model undefined because that is the valuable, defensible part, and we want you to propose it and defend it. Any score you produce, you should be able to justify.

Legality comes first. Respect each source's terms of service and the law on scraping and automated collection, document your position per source, and use free or trial data only. If you are unsure about a source, ask before you collect — not after.