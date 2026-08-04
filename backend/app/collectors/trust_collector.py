"""Trust-page collector — self-reported certifications + contactability.

The vendor talking about itself — the exact input the brief is trying to move away from —
so every output is a CLAIM, flagged self-reported, not verified fact (methodology §5.8).
It still earns its place for the fourth-party angle (subprocessor lists) and because a
published disclosure path is low-cost, high-signal maturity.

Two legal controls enforced here:
  * robots.txt is honoured before fetching any path (source_assessment.md §11).
  * PII MINIMISATION at ingest: named-person emails are stripped; only role addresses
    (security@, abuse@, privacy@) are kept (project_plan §4 / APP 3 + "trades in PI").
"""

from __future__ import annotations

import re
import urllib.robotparser
from typing import Any

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_CAT = "vendor_transparency_gov"
_TRUST_PATHS = ("security", "trust", "trust-center", "legal/security", "security-and-compliance")
# The certifications we can read off a trust page. The KEY is the canonical name and it is what
# `compliance_frameworks.*.asserted_by.claim_contains` matches against, so adding one here is half
# of adding a framework — a framework whose claim string no collector can ever produce would fire
# for nobody while reading as coverage.
_CERTS = {
    "ISO 27001": re.compile(r"iso[\s/]*(?:/?iec[\s/]*)?27001", re.I),
    "SOC 2": re.compile(r"soc\s*2", re.I),
    "PCI DSS": re.compile(r"pci[\s-]*dss", re.I),
    "ISO 27701": re.compile(r"iso[\s/]*(?:/?iec[\s/]*)?27701", re.I),
    # Cloud-specific extensions to 27001, commonly claimed alongside it and rarely scoped
    # correctly — which is the whole reason they are worth reading separately from 27001.
    "ISO 27017": re.compile(r"iso[\s/]*(?:/?iec[\s/]*)?27017", re.I),
    "ISO 27018": re.compile(r"iso[\s/]*(?:/?iec[\s/]*)?27018", re.I),
}
_ROLE_LOCALPARTS = {"security", "abuse", "privacy", "dpo", "soc", "compliance", "legal"}
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class TrustCollector(Collector):
    source = "trust"
    reliability = 0.5  # self-reported — claim, not evidence (source_assessment.md §11)
    timeout_s = 30.0
    # Lever 1: the trust page is the vendor's OWN site and a single transient fetch failure
    # used to drop the whole page set, reading a clean vendor as the_ghost (the Canva case).
    # One retry on a transient blip recovers it; 404s (page just doesn't exist) don't retry.
    http_attempts = 2
    http_backoff_s = 0.8

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        domain = vendor.domain
        if not domain:
            return self.result(vendor, "empty", notes="no domain for trust-page fetch")
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        rp = await self._robots(ctx, domain)
        pages: dict[str, str] = {}
        for path in _TRUST_PATHS:
            url = f"https://{domain}/{path}"
            if rp is not None and not rp.can_fetch(ctx.settings.user_agent, url):
                continue  # honour robots.txt
            r = await self._get_with_retry(ctx, url, limiter_key=domain)
            if r is None:
                continue
            if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
                pages[path] = r.text[:200_000]

        if not pages:
            return self.result(
                vendor, "empty",
                notes="no trust page found (absence correlates with size, not risk)",
            )

        blob = "\n".join(pages.values())
        certs_found = sorted(name for name, rx in _CERTS.items() if rx.search(blob))
        role_contacts = self._role_emails(blob)

        raw: dict[str, Any] = {
            "domain": domain, "pages_found": sorted(pages.keys()),
            "certifications_claimed": certs_found,
            "role_contacts": role_contacts,   # PII-minimised: role addresses only
        }
        findings: list[Finding] = []

        cert_band = "claimed_unverified" if certs_found else "none_claimed"
        findings.append(
            Finding(
                source=self.source, signal="cert_posture",
                subcategory="certifications_attestations", category="compliance_regulatory",
                observed=f"{', '.join(certs_found) if certs_found else 'none claimed'}",
                value={"band": cert_band, "certs": certs_found},
                locator=f"https://{domain}/[{','.join(sorted(pages))}]",
                notes="SELF-REPORTED claim — corroborate against cert registry where possible",
            )
        )
        findings.append(
            Finding(
                source=self.source, signal="program_disclosure",
                subcategory="security_program_disclosure", category=_CAT,
                observed="detailed_policies" if len(blob) > 4000 else "marketing_only",
                value={"pages": sorted(pages.keys()), "chars": len(blob)},
                locator=f"https://{domain}/",
                notes="self-reported program disclosure",
            )
        )
        contact_band = "dpo_and_security_contact" if role_contacts else "none_published"
        findings.append(
            Finding(
                source=self.source, signal="contactability",
                subcategory="contactability_responsiveness", category=_CAT,
                observed=f"{len(role_contacts)} role contact(s)" if role_contacts else "none published",
                value={"role_contacts": role_contacts, "band": contact_band},
                locator=f"https://{domain}/",
            )
        )
        # Published policies/reports feed disclosure_reporting — a scored Compliance subcategory
        # that otherwise had no collector (capping Compliance coverage at 0.50 for every vendor).
        # Inferred from the substance of the trust pages already fetched; self-reported (§5.8).
        report_band = "substantive" if len(blob) > 4000 else "partial"
        findings.append(
            Finding(
                source=self.source, signal="reporting_posture",
                subcategory="disclosure_reporting", category="compliance_regulatory",
                observed=report_band, value={"band": report_band, "chars": len(blob)},
                locator=f"https://{domain}/[{','.join(sorted(pages))}]",
                notes="self-reported — published policies/reports inferred from trust-page substance",
            )
        )
        return self.result(vendor, "ok", raw=raw, findings=findings, source_version="live")

    async def _robots(self, ctx: CollectorContext, domain: str) -> urllib.robotparser.RobotFileParser | None:
        assert ctx.http is not None
        rp = urllib.robotparser.RobotFileParser()
        r = await self._get_with_retry(ctx, f"https://{domain}/robots.txt", limiter_key=domain)
        if r is None or r.status_code != 200:
            return None
        rp.parse(r.text.splitlines())
        return rp

    @staticmethod
    def _role_emails(text: str) -> list[str]:
        """Keep ONLY role addresses; drop named-person emails (PII minimisation)."""
        keep: set[str] = set()
        for addr in _EMAIL.findall(text):
            local = addr.split("@", 1)[0].lower()
            if local in _ROLE_LOCALPARTS:
                keep.add(addr.lower())
        return sorted(keep)
