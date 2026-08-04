"""HTTP security-headers collector — one GET of the public homepage.

A single request identical to what any browser issues visiting the site; no auth
bypassed, no non-public endpoint touched (source_assessment.md §3). Observes HSTS, CSP,
X-Frame-Options and the presence of a security.txt (RFC 9116). A header is a *mitigation*,
not a vulnerability — which is why this whole subcategory is weighted low (§5.6.2).
"""

from __future__ import annotations

from typing import Any

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_CAT = "cyber_hygiene_technical"
_SUB = "web_hardening"


class HeadersCollector(Collector):
    source = "headers"
    reliability = 0.9
    timeout_s = 20.0
    # Lever 1: the homepage is the vendor's own site; a transient blip shouldn't zero the whole
    # header read (which feeds web_hardening AND the transparency vuln-disclosure signal).
    http_attempts = 2
    http_backoff_s = 0.8

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        domain = vendor.domain
        if not domain:
            return self.result(vendor, "empty", notes="no domain for header fetch")
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        url = f"https://{domain}/"
        resp = await self._get_with_retry(ctx, url, limiter_key=domain)
        if resp is None:
            return self.result(vendor, "error", raw={"url": url},
                               notes="fetch failed after retries (transient network/connection)")

        headers = {k.lower(): v for k, v in resp.headers.items()}
        raw: dict[str, Any] = {"url": str(resp.url), "status_code": resp.status_code, "headers": headers}
        findings: list[Finding] = []

        checks = {
            "hsts": "strict-transport-security",
            "csp": "content-security-policy",
            "x_frame_opts": "x-frame-options",
        }
        for signal, header in checks.items():
            present = header in headers
            findings.append(
                Finding(
                    source=self.source, signal=signal, subcategory=_SUB, category=_CAT,
                    observed="present" if present else "absent",
                    value={"present": present, "value": headers.get(header)},
                    locator=f"{url} [{header}]",
                )
            )

        # security.txt (RFC 9116) — check the well-known location
        sec_txt = await self._has_security_txt(ctx, domain)
        raw["security_txt_present"] = sec_txt
        findings.append(
            Finding(
                source=self.source, signal="security_txt", subcategory=_SUB, category=_CAT,
                observed="present" if sec_txt else "absent", value={"present": sec_txt},
                locator=f"https://{domain}/.well-known/security.txt",
            )
        )

        # A published security.txt IS a vulnerability-disclosure path (RFC 9116) — so the same
        # observation also feeds vuln_disclosure_program, a scored Transparency subcategory that
        # otherwise has no collector (it was capping Transparency coverage at 0.67 for every
        # vendor — a structural build-gap, not vendor opacity). bug_bounty is a future upgrade.
        findings.append(
            Finding(
                source=self.source, signal="vd_program", subcategory="vuln_disclosure_program",
                category="vendor_transparency_gov",
                observed="security_txt_only" if sec_txt else "none",
                value={"band": "security_txt_only" if sec_txt else "none", "security_txt": sec_txt},
                locator=f"https://{domain}/.well-known/security.txt",
                notes="published vulnerability-disclosure path inferred from security.txt (RFC 9116)",
            )
        )

        return self.result(vendor, "ok", raw=raw, findings=findings, source_version="live")

    async def _has_security_txt(self, ctx: CollectorContext, domain: str) -> bool:
        for path in (".well-known/security.txt", "security.txt"):
            r = await self._get_with_retry(ctx, f"https://{domain}/{path}", limiter_key=domain)
            if r is not None and r.status_code == 200 and (
                "contact:" in r.text.lower() or "-----begin pgp" in r.text.lower()
            ):
                return True
        return False
