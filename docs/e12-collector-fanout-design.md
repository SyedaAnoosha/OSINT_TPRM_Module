# E12 — Collector fan-out: the decisions, taken before the build

**Status:** design record · decisions taken · **the fan-out itself is NOT built**
**Raised:** 2026-07-31 · **Size:** 6–10 weeks · **Risk:** high · **Changes scores: substantially**

---

## 0. What this document is, and what it is not

E12 turns *"TLS 1.0 on the homepage"* into *"TLS 1.0 on 8 of 340 checked hosts"*. It is the change
that makes this an estate assessment rather than a homepage check.

**It is a programme, not a phase**, and the plan says so: 6–10 weeks, resourced separately. It
cannot be delivered as part of a sequence of config-and-engine phases, and pretending otherwise
would produce a half-fan-out — which is worse than none, because a denominator that covers some
hosts and not others is a rate nobody can defend in a dispute.

**What this document delivers instead:** the six scope decisions, taken and reasoned, plus the one
interaction that was cheap to protect *now* and expensive to discover *later*. A build team should
be able to start from here without reopening any of it.

**One decision is already enforced in code** (§7). The rest are recorded, not implemented.

---

## 1. The scoping correction that has to be stated first

The research assumed the denominator exists for most Class-P signals. **Verified: it does not.**

| Signal | What it actually probes | `D_s` today |
|---|---|:--:|
| `stale_hosts ÷ subdomain_estate` | CT log counts | ✅ real, delivered at E6 |
| `tls_version`, `cert_validity` | **one** handshake, apex:443 | ❌ = 1 |
| `hsts`, `csp`, `x_frame_opts` | **one** GET of the homepage | ❌ = 1 |
| `dmarc`, `spf`, `dkim`, `dnssec`, `caa` | DNS at the apex — **genuinely one per domain** | n/a |
| `nvd_cve`, `kev_listed_cve` | keyword match on product names | ❌ none exists |

Three groups, and they need different treatment. The email/DNS signals are **correctly** N=1: a
domain has one DMARC record, and fanning out would invent a denominator where none exists. That
distinction is not in the original plan and matters for scoping — roughly a third of the signal set
is already at its natural resolution.

---

## 2. Decision — asset scope: deterministic hash sampling, and the rule is published

**The sampling rule IS the denominator.** *"8 of 340"* means nothing unless a reader knows how the
340 were chosen, and a vendor disputing the figure is disputing the rule, not the count.

- **Deterministic**, seeded on the vendor ref: the same estate yields the same sample next month, so
  a change in the rate is a change in the estate rather than a change in the dice. A random sample
  makes every re-scan produce a different number and no trend means anything.
- **Published in full** — sample size, seed basis, exclusion rules — on the finding and in the
  evidence pack, in the way E6 already publishes `denominator`.
- **Capped**, not proportional. A vendor with 40 000 CT entries does not get 40 000 probes; the cap
  is a politeness and runtime budget and it is part of the published rule.

> **Attribution disputes are already a top-two category** (*"you counted 340, we operate 40"*), and
> E6's `accepts_as_refute` text already invites the correction. Fan-out multiplies both the value
> and the frequency of that dispute. The sampling rule must be quotable in one sentence.

---

## 3. Decision — multi-tenant detection runs BEFORE `D_s` is computed

Non-negotiable, and it is the decision most likely to be skipped under time pressure.

A vendor hosting `customer1.vendor.com … customer9000.vendor.com` has a CT footprint that is an
artefact of their **business model**, not their attack surface. Counting those as assets means the
best-architected SaaS vendors bottom out on estate size — the exact inversion E6 was built to fix,
reintroduced one layer up and much harder to see.

`wildcard_seen` is already carried by the CT collector. It is a signal of the pattern, **not a
solution**: a `*.vendor.com` certificate says wildcards exist, not which names are tenants.

**Order of operations, and it is not negotiable:** classify → exclude tenants → resolve liveness →
*then* count. Computing `D_s` before classification produces a denominator that is wrong in a
direction that flatters nobody and confuses everybody.

---

## 4. Decision — liveness is resolved before probing, and non-resolving names leave the denominator

CT shows certificates **issued**, never hosts **live**. A name that was certified in 2019 and has
not resolved since is not part of an attack surface.

Including dead names inflates `D_s` and therefore **flatters the vendor** — 8 of 340 reads better
than 8 of 60, and the 280 difference is names nobody can reach. That is the failure in the
comfortable direction, which is why it needs stating: it will not be caught by anyone reviewing a
report that looks fine.

Same rule as E6's zero-handling and the same rule as coverage: **a host we could not resolve leaves
the denominator; it does not enter it as a pass.**

---

## 5. Decision — runtime and rate limits are a design input, not an afterthought

The suite already takes ~299s at N=1. Fan-out multiplies **every** collector by N.

- Every collector queries **someone else's free service.** Fan-out is where a polite client becomes
  an impolite one without anyone deciding to.
- The per-host budget is part of the sampling rule (§2), so the cap has one owner and one number.
- The frozen corpus is captured evidence and does not re-probe, so **regression cost does not
  scale** — but a fixture captured at N=1 cannot exercise the fan-out, so E12 needs its own
  multi-host fixture. That is a corpus extension, and E0.2 is the precedent: it was the silent
  prerequisite that paid for itself immediately.

---

## 6. Decision — `nvd_cve` / `kev_listed_cve` stay un-normalised, and the reason is published

They are keyword matches against a **product line**, not against this vendor's deployed version.
There is no honest denominator, and inventing one would produce a rate with a decimal point and no
meaning.

**Better to publish an un-normalised count and say why than to divide by a number we cannot
defend.** This is the same evidence bar E8 applied when it refused to *gate* on `kev_overdue`, and
the same one E9c applied when it excluded PCI DSS Req 6.3.3 and Essential Eight ML1 from the
compliance library. One bar, three phases, no exceptions — and E12 is what eventually lifts it,
because a version-resolved estate makes the CVE match evidence rather than inference.

---

## 7. Decision — the critical ceiling arms on the APEX ✅ **enforced in code now**

The interaction the phase plan flags as *easy to break*, and the only part of E12 implemented here.

`cert_validity` is simultaneously the **only** `auto_signals` entry and the **only** `never_decays`
signal. Today it is one handshake and "expired" is unambiguous. Once it becomes a rate, the ceiling
must arm off something, and there are two wrong answers that both look reasonable in a diff:

| Option | Why it fails |
|---|---|
| **Any host expired** | A 400-host estate almost certainly has one abandoned staging box with a dead certificate. Every large vendor is capped at 49 permanently. **A non-compensatory knockout that fires constantly is one nobody reads** — strictly worse than not having it |
| **A rate threshold** | Makes the most severe response in the model a tunable percentage, and invites the argument *"3% of hosts is acceptable"*. That is not an argument anyone should be having about a knockout |

**Decided: the apex, specifically.** It preserves today's semantics exactly through the fan-out,
keeps the knockout rare and legible, and leaves abandoned-certificate decay to `stale_hosts` —
which is a rate signal, and a rate is where a rate belongs.

Implemented as `critical_ceiling.auto_signal_scope` with its `basis`, read by
`ScoringConfig.ceiling_scope_satisfied` and applied in `normalize.py`. It is trivially satisfied at
N=1, so it changes no score today. **A fanned-out collector must set `host_role` on its findings**;
one that emits a per-host expired certificate without saying which host cannot arm the ceiling —
the safe direction, because the alternative is a knockout firing on evidence that does not support
it.

Recorded now rather than at E12 because the failure is silent and arrives as a one-line diff.

---

## 8. Legal boundary — unchanged, and it constrains the design

**Do not probe non-public endpoints.** The legal position rests on every request being identical to
an ordinary browser visit. Fan-out multiplies the number of requests, not the kind — a directory
brute-force or a port sweep is a different activity with a different legal character, and no volume
of it becomes acceptable because the individual requests are small.

`robots.txt` is honoured today (`trust_collector`). It must be honoured **per host**, not once for
the apex.

---

## 9. What lands when E12 lands

- Every rate signal publishes its denominator and its sampling rule.
- `stale_hosts` stops being the only real exposure rate — E6's mechanism generalises to `tls_version`
  and the header signals without a model change, because `exposure:` was built for it.
- `kev_overdue` becomes gateable (E8's declared-but-off gate) once versions are resolved per host.
- PCI DSS Req 6.3.3 and Essential Eight ML1 become modellable (E9c's excluded controls).

**Three phases are waiting on this one.** That is the argument for resourcing it properly rather
than attempting it inside a phase sequence.
