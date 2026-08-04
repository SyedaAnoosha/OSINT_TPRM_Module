"""Build the SYNTHETIC archetype fixtures (E0.2).

    python -m tests.build_archetypes        (from backend/)

WHY THESE ARE SYNTHETIC, AND WHY THAT IS SAID OUT LOUD
------------------------------------------------------
The five real fixtures (`atlassian`, `myob`, `onetrust`, `slack`, `snowflake`) are collector
output captured live once and frozen. They are evidence. These five are not: they are
CONSTRUCTED, and this file is the construction, committed so that a reviewer reads the spec
rather than a JSON blob that looks like captured evidence.

That distinction is load-bearing in this repo. Sprint 0 (`ebc1dc5`, `18dd4f6`) existed because
six invented postures were being reported as a real peer cohort of `n=6`. The lesson was not
"never construct data" — it was **never let constructed data pass as observed**. So every
archetype here is unmistakable:

  * every ref is prefixed `synthetic_`;
  * every domain sits under `.example`, reserved by RFC 2606 §3 and unregistrable by anyone;
  * every vendor name says `(synthetic)` in it;
  * every fixture carries a top-level `synthetic` block naming this builder and the reason;
  * `test_corpus.test_synthetic_archetypes_are_unmistakably_synthetic` asserts all of the above,
    and `test_no_synthetic_vendor_can_enter_a_peer_cohort` asserts they cannot reach the
    benchmarking pool.

WHY THE CORPUS NEEDED THEM
--------------------------
The real corpus is five large, well-run vendors scoring 74-87 with confidence 0.93-0.96. It
cannot observe a Ghost, a gated vendor, a small supplier or a bad one — so it cannot catch a
regression that only affects them, which is **precisely the population E2 and E6 exist to treat
fairly**. Every phase from E1 to E5 re-goldened against a corpus that structurally could not
disagree with them about small vendors.

Each archetype exercises an engine path the real five never touch:

  synthetic_ghost      refusal on thin coverage             posture is None, ghost=True
  synthetic_gated      the sanctions gate                   blocked, no score at all
  synthetic_smallco    a small supplier doing it right      the E2 fairness proof
  synthetic_weak       the critical ceiling BITING          would publish 78, publishes 49
  synthetic_floor      the bottom of the scale              where E13's compression shows

The fifth is one more than the plan's "at minimum" four. It is here because `synthetic_weak`
is capped by the ceiling, so the arithmetic *below* the cap is never exercised by it — and the
bottom of the scale is exactly where E7's ladder and E13's log-odds will land. A corpus with a
ceiling case but no floor case would go green on a change that flattened everything under 30.

WHAT THEY ARE NOT
-----------------
Not a benchmark, not a peer group, not evidence about any real company, and not a substitute
for E0.4's outcome labels. They constrain the ENGINE's behaviour on inputs the real corpus
lacks. They say nothing about whether the model's ordering is correct — only real outcomes can.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "fixtures"

# Pinned to the same clock the real corpus is measured against (test_corpus.AS_AT), so decay is
# identical for both halves and a fixture never drifts by the day.
FETCHED_AT = "2026-07-23T00:00:00Z"

# Reliability per source, copied from the real fixtures so a synthetic result is weighted exactly
# as its real counterpart would be. Inventing these would quietly change what coverage means.
RELIABILITY = {
    "dns": 0.95, "tls": 0.95, "headers": 0.9, "ct": 0.9, "hibp": 0.55, "kev": 0.95,
    "nvd": 0.55, "ita": 0.95, "gleif": 0.9, "wikidata": 0.7, "rdap": 0.85,
    "regulatory": 0.4, "gdelt": 0.6, "trust": 0.5,
}

# Which collector emits which signal, mirroring the real corpus exactly. A synthetic fixture that
# attributed `dmarc` to the trust collector would be testing a pipeline that does not exist.
SOURCE_OF = {
    "dmarc": "dns", "spf": "dns", "dkim": "dns", "dnssec": "dns", "caa": "dns",
    "tls_version": "tls", "cert_validity": "tls",
    "hsts": "headers", "csp": "headers", "x_frame_opts": "headers",
    "security_txt": "headers", "vd_program": "headers",
    "subdomain_estate": "ct", "stale_hosts": "ct", "weak_issuance": "ct",
    "breach_by_data_class": "hibp", "kev_listed_cve": "kev", "nvd_cve": "nvd",
    "entity_status": "gleif", "entity_existence": "wikidata",
    "entity_maturity": "wikidata", "domain_registration": "rdap",
    "regulator_action": "regulatory",
    "cert_posture": "trust", "contactability": "trust",
    "program_disclosure": "trust", "reporting_posture": "trust",
}

CATEGORY_OF = {
    "breach_by_data_class": "breach_compromise_history",
    "kev_listed_cve": "breach_compromise_history",
    "nvd_cve": "breach_compromise_history",
    "tls_version": "attack_surface_hygiene", "cert_validity": "attack_surface_hygiene",
    "hsts": "attack_surface_hygiene", "csp": "attack_surface_hygiene",
    "x_frame_opts": "attack_surface_hygiene", "dnssec": "attack_surface_hygiene",
    "caa": "attack_surface_hygiene", "subdomain_estate": "attack_surface_hygiene",
    "stale_hosts": "attack_surface_hygiene", "weak_issuance": "attack_surface_hygiene",
    "dmarc": "identity_email", "spf": "identity_email", "dkim": "identity_email",
    "vd_program": "transparency", "security_txt": "transparency",
    "cert_posture": "compliance_regulatory", "regulator_action": "compliance_regulatory",
    "entity_status": "continuity_context", "entity_existence": "continuity_context",
    "entity_maturity": "continuity_context", "domain_registration": "continuity_context",
    "program_disclosure": "assurance_context", "contactability": "assurance_context",
    "reporting_posture": "assurance_context",
}

# Signals whose band is derived from a raw count rather than read directly (normalize._COUNT_SIGNALS).
COUNT_SIGNALS = {"subdomain_estate", "stale_hosts"}


def _finding(signal: str, band: str, *, domain: str, count: int | None = None,
             event_date: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"count": count} if signal in COUNT_SIGNALS else {"band": band}
    return {
        "source": SOURCE_OF[signal],
        "signal": signal,
        "subcategory": signal,
        "category": CATEGORY_OF[signal],
        "observed": band if count is None else f"{count} ({band})",
        "value": value,
        "event_date": event_date,
        "locator": f"synthetic://{domain}/{signal}",
        "remediation_evidenced": False,
        "severity_base": None,
        "notes": None,
    }


def _results(ref: str, domain: str, bands: dict[str, str], *,
             counts: dict[str, int] | None = None,
             event_dates: dict[str, str] | None = None,
             failed_sources: dict[str, str] | None = None,
             extra_findings: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Group per-signal bands into the collector envelopes the engine actually receives.

    `failed_sources` maps a source to a status (`error` / `empty`), so a Ghost is built the way a
    Ghost really happens — collectors that did not come back — rather than by deleting findings
    from a healthy run and leaving a result that claims `ok` with nothing in it.
    """
    counts, event_dates = counts or {}, event_dates or {}
    failed_sources = failed_sources or {}

    by_source: dict[str, list[dict[str, Any]]] = {}
    for signal, band in bands.items():
        by_source.setdefault(SOURCE_OF[signal], []).append(
            _finding(signal, band, domain=domain, count=counts.get(signal),
                     event_date=event_dates.get(signal)))
    for extra in extra_findings or []:
        by_source.setdefault(extra["source"], []).append(extra)

    out = []
    for source in RELIABILITY:
        status = failed_sources.get(source)
        findings = by_source.get(source, [])
        if status is None:
            # `gdelt` is a HELD source: it is queried and returns candidates that the model has no
            # band for, so it must emit zero findings. Mirrored here so the archetypes exercise the
            # same "collected but unscoreable" path the real corpus does.
            status = "ok" if findings else ("empty" if source in ("ita", "gdelt") else "empty")
        out.append({
            "source": source,
            "vendor_ref": ref,
            "status": status,
            "fetched_at": FETCHED_AT,
            "source_version": "synthetic-1",
            "raw": {"synthetic": True, "archetype": ref},
            "findings": [] if status in ("error",) else findings,
            "reliability": RELIABILITY[source],
            "notes": "constructed fixture — see tests/build_archetypes.py",
        })
    return out


# --------------------------------------------------------------------------------------------
# A fully-clean baseline, so each archetype states only its DEVIATIONS from a healthy vendor.
# Reading a spec below should answer "what is different about this one" in one glance.
# --------------------------------------------------------------------------------------------
CLEAN = {
    "dmarc": "p_reject", "spf": "hardfail_all", "dkim": "present",
    "dnssec": "valid", "caa": "present",
    "tls_version": "tls_13", "cert_validity": "valid",
    "hsts": "present", "csp": "present", "x_frame_opts": "present",
    "security_txt": "present", "vd_program": "bug_bounty",
    "subdomain_estate": "small", "stale_hosts": "none", "weak_issuance": "none",
    "breach_by_data_class": "no_known_breach", "kev_listed_cve": "no_kev_match",
    "nvd_cve": "no_critical_cve",
    "entity_status": "active_good_standing", "entity_existence": "entity_active_confirmed",
    "entity_maturity": "mature_gt_10", "domain_registration": "domain_established",
    "regulator_action": "no_action_found",
    "cert_posture": "registry_corroborated", "contactability": "dpo_and_security_contact",
    "program_disclosure": "detailed_policies", "reporting_posture": "substantive",
}
CLEAN_COUNTS = {"subdomain_estate": 6, "stale_hosts": 0}


def _spec(**overrides: str) -> dict[str, str]:
    return {**CLEAN, **overrides}


ARCHETYPES: dict[str, dict[str, Any]] = {
    # ---------------------------------------------------------------- 1. the Ghost
    "synthetic_ghost": {
        "name": "Ghost Archetype Pty Ltd (synthetic)",
        "domain": "ghost-archetype.example",
        "why": (
            "A vendor about whom almost nothing is publicly visible. DNS answers; every other "
            "collector fails or returns nothing. Everything observed is CLEAN, so a model that "
            "reported coverage as quality would publish this as a perfect score — the single "
            "worst call the system could make. Expected: refused, ghost, posture None."
        ),
        "bands": {k: CLEAN[k] for k in ("dmarc", "spf", "dkim", "dnssec", "caa")},
        "counts": {},
        "failed_sources": {
            "tls": "error", "headers": "error", "ct": "error", "hibp": "error",
            "kev": "error", "nvd": "error", "gleif": "error", "wikidata": "error",
            "rdap": "error", "regulatory": "error", "trust": "error",
        },
    },
    # ---------------------------------------------------------------- 2. the gated vendor
    "synthetic_gated": {
        "name": "Gated Archetype LLC (synthetic)",
        "domain": "gated-archetype.example",
        "why": (
            "A well-collected, decent-looking vendor that trips the sanctions screen. The gate is "
            "non-compensatory and legal, not arithmetic: no posture, no grade, routed to a human. "
            "The corpus had no vendor that produced NO SCORE, so nothing pinned that path."
        ),
        "bands": _spec(),
        "counts": dict(CLEAN_COUNTS),
        "extra_findings": [{
            "source": "ita",
            "signal": "sanctions_screen_hit",
            "subcategory": "sanctions_screening",
            "category": "regulatory_legal_sanctions",
            "observed": "POSSIBLE match: GATED ARCHETYPE LLC [SDN] (synthetic)",
            "value": {"list": "SDN", "match": "possible", "synthetic": True},
            "event_date": None,
            "locator": "synthetic://gated-archetype.example/sanctions",
            "remediation_evidenced": False,
            "severity_base": None,
            "notes": "constructed fixture — no real entity is named or implied",
        }],
    },
    # ---------------------------------------------------------------- 3. the small supplier
    "synthetic_smallco": {
        "name": "Smallco Archetype Pty Ltd (synthetic)",
        "domain": "smallco-archetype.example",
        "why": (
            "A three-year-old supplier with six hosts, doing everything that is FREE and nothing "
            "that costs an audit budget: full email authentication, current TLS, a tidy estate — "
            "but no DNSSEC, no CAA, no security.txt, no certification, no trust page, no formal "
            "reporting. This is the archetype E2 was written for, and the one the real corpus "
            "structurally cannot contain. Under v4.2.0 it paid 41 category points for that "
            "profile; under v5.0.0 it pays none of them. `entity_maturity` also fires here — "
            "the ONE signal that never fires anywhere in the real corpus, which left the "
            "confidence assurance multiplier untested against a fixture."
        ),
        "bands": _spec(
            dnssec="absent", caa="absent", security_txt="absent", vd_program="none",
            csp="absent",
            cert_posture="none_claimed", program_disclosure="none",
            contactability="partial", reporting_posture="none",
            entity_maturity="startup_lt_2", domain_registration="domain_recent",
        ),
        "counts": {"subdomain_estate": 6, "stale_hosts": 0},
    },
    # ---------------------------------------------------------------- 4. the ceiling case
    "synthetic_weak": {
        "name": "Weak Archetype Inc (synthetic)",
        "domain": "weak-archetype.example",
        "why": (
            "A mediocre vendor serving an EXPIRED certificate. On the arithmetic alone it lands "
            "around 78 and reads as a grade B that clears any '>= 50' procurement threshold. The "
            "critical ceiling caps it at 49 instead. No real corpus vendor arms the ceiling, so "
            "the knockout — the model's strongest non-compensatory claim — had no fixture at all."
        ),
        "bands": _spec(
            cert_validity="expired_serving_prod", tls_version="only_tls_12", csp="absent",
            dmarc="p_none", vd_program="security_txt_only", cert_posture="claimed_unverified",
            nvd_cve="cvss_medium_or_low",
        ),
        "counts": dict(CLEAN_COUNTS),
        # notAfter is in the PAST for an expired cert. Pinned well back deliberately: it proves
        # `never_decays` holds, i.e. a cert expired six years ago still costs the full 40.
        "event_dates": {"cert_validity": "2020-03-01T00:00:00Z"},
    },
    # ---------------------------------------------------------------- 5. the floor
    "synthetic_floor": {
        "name": "Floor Archetype GmbH (synthetic)",
        "domain": "floor-archetype.example",
        "why": (
            "Comprehensively badly run: no email authentication, TLS 1.0, an abandoned estate, a "
            "credential breach, a KEV listing and a regulator enforcement action. Its purpose is "
            "the BOTTOM of the scale, which `synthetic_weak` cannot test because the ceiling caps "
            "it first. E7's ladder and E13's log-odds both land here, and today the corpus would "
            "stay green through a change that flattened everything under 30."
        ),
        "bands": _spec(
            tls_version="tls_10_or_11", cert_validity="valid",
            hsts="absent", csp="absent", x_frame_opts="absent",
            dnssec="misconfigured", caa="absent",
            subdomain_estate="large", stale_hosts="many", weak_issuance="deprecated_ca_or_key",
            dmarc="absent", spf="absent", dkim="absent",
            security_txt="absent", vd_program="none",
            cert_posture="claimed_expired", regulator_action="enforcement_action",
            breach_by_data_class="passwords_or_cards", kev_listed_cve="listed",
            nvd_cve="cvss_critical",
            entity_status="registration_lapsed", domain_registration="domain_expiring",
            program_disclosure="marketing_only", contactability="none_published",
            reporting_posture="none",
        ),
        "counts": {"subdomain_estate": 340, "stale_hosts": 61},
        "event_dates": {"breach_by_data_class": "2025-11-14T00:00:00Z"},
    },
}


def build_one(ref: str) -> dict[str, Any]:
    spec = ARCHETYPES[ref]
    return {
        "synthetic": {
            "constructed": True,
            "builder": "tests/build_archetypes.py",
            "purpose": "E0.2 — engine archetypes the real five-vendor corpus cannot contain",
            "why_this_one": spec["why"],
            "not_a_real_company": (
                "No real entity is named, described or implied. The domain is under .example, "
                "reserved by RFC 2606 and unregistrable. This fixture must never enter a peer "
                "cohort, a benchmark population or a published report."
            ),
        },
        "vendor": {"ref": ref, "name": spec["name"], "domain": spec["domain"]},
        "results": _results(
            ref, spec["domain"], spec["bands"],
            counts=spec.get("counts"), event_dates=spec.get("event_dates"),
            failed_sources=spec.get("failed_sources"),
            extra_findings=spec.get("extra_findings"),
        ),
    }


def main() -> None:
    for ref in ARCHETYPES:
        path = FIXTURES / f"{ref}.json"
        path.write_text(json.dumps(build_one(ref), indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
        print(f"wrote {path.name}")
    print("\nNow run `python -m tests.regolden` to baseline them.")


if __name__ == "__main__":
    main()
