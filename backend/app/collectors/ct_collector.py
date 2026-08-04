"""Certificate Transparency collector — subdomain estate + shadow assets.

CT logs are public by RFC 6962 design; crt.sh is a convenience index over them (unstated ToS,
so we rate-limit hard and identify our agent honestly). crt.sh is also **notoriously flaky** —
it times out or 502s for minutes at a time, and it is the sole feed for Digital Footprint
(10% weight), so an outage used to silently zero the whole category for every vendor. Two
fixes (source_assessment.md §1): retry crt.sh with backoff, then **fall back to SSLMate's Cert
Spotter API** (api.certspotter.com), which indexes the same public CT data and whose ToS bars
no commercial/automated use — free no-key tier is evaluation-only, used here for the PoC and
flagged clear-conditional for production (§1). Both are convenience layers over the same logs.

Key limit carried into the data: CT shows certificates *issued*, not hosts *live* — so counts
are "breadth of what was ever exposed", not live attack surface. COUNT signals, size-normalized
at scoring time (log-damp), not here — the collector just reports honest counts.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_CAT = "digital_footprint_assets"
_STALE = re.compile(r"\b(dev|staging|stage|test|uat|qa|sandbox|legacy|old|deprecated)\b", re.I)
# crt.sh: fail FAST (short timeout, 2 tries) so the certspotter fallback kicks in quickly when
# crt.sh is down — better a 2s fallback than 75s of dead retries (what stalled the 5-vendor run).
_ATTEMPTS = 2
_BACKOFF_S = 1.5
_CRTSH_TIMEOUT = 12.0
_CERTSPOTTER = "https://api.certspotter.com/v1/issuances"


class CtCollector(Collector):
    source = "ct"
    reliability = 0.9  # cryptographically anchored, not self-reported (source_assessment.md §1)
    timeout_s = 50.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        domain = vendor.domain
        if not domain:
            return self.result(vendor, "empty", notes="no domain for CT lookup")
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        # Primary: crt.sh (public CT index). Fallback: certspotter (same public logs).
        names, used, err = await self._fetch_crtsh(ctx, domain)
        if names is None:
            names, cs_err = await self._fetch_certspotter(ctx, domain)
            if names is None:
                return self.result(
                    vendor, "error",
                    notes=f"CT unavailable — crt.sh: {err}; certspotter: {cs_err}",
                )
            used = "certspotter"

        subdomains, stale, wildcard = self._analyse_names(names, domain)
        raw: dict[str, Any] = {
            "domain": domain, "ct_source": used, "raw_names": len(names),
            "unique_subdomains": len(subdomains), "stale_candidates": stale[:200],
            "wildcard_seen": wildcard, "subdomains_sample": subdomains[:200],
        }
        findings = self._findings(domain, subdomains, stale, wildcard, used)
        return self.result(vendor, "ok", raw=raw, findings=findings, source_version=used)

    async def _fetch_crtsh(
        self, ctx: CollectorContext, domain: str
    ) -> tuple[list[str] | None, str, str | None]:
        """Fetch crt.sh, retrying transient failures. Returns (dns_names, source_used, error)."""
        assert ctx.http is not None
        last_err = "unknown"
        for attempt in range(1, _ATTEMPTS + 1):
            await ctx.limiter.acquire("crt.sh")  # self-limit hard (unstated ToS)
            try:
                resp = await ctx.http.get(
                    "https://crt.sh/", params={"q": f"%.{domain}", "output": "json"},
                    timeout=_CRTSH_TIMEOUT,
                )
            except httpx.HTTPError as exc:
                last_err = f"{type(exc).__name__}"
            else:
                if resp.status_code == 200 and resp.text.strip():
                    try:
                        names: list[str] = []
                        for e in resp.json():
                            names.extend(str(e.get("name_value", "")).split("\n"))
                        return names, "crt.sh", None
                    except ValueError:
                        last_err = "non-JSON"
                else:
                    last_err = f"{resp.status_code}/empty"
            if attempt < _ATTEMPTS:
                await asyncio.sleep(_BACKOFF_S * attempt)
        return None, "crt.sh", f"{last_err} (after {_ATTEMPTS} attempts)"

    async def _fetch_certspotter(
        self, ctx: CollectorContext, domain: str
    ) -> tuple[list[str] | None, str | None]:
        """Fallback: SSLMate Cert Spotter — same public CT logs, different index.

        The anonymous tier is rate-limited hard (a few searches -> 429). If a free key is
        configured (`TPRM_CERTSPOTTER_TOKEN`) it is sent as a Bearer token to lift the ceiling —
        the documented production path. Without it we still try anonymously, then the caller
        surfaces the CT gap honestly (digital_footprint -> lower coverage, never fabricated).
        """
        assert ctx.http is not None
        token = getattr(ctx.settings, "certspotter_token", "") or ""
        headers = {"Authorization": f"Bearer {token}"} if token else None
        await ctx.limiter.acquire("api.certspotter.com")
        try:
            resp = await ctx.http.get(
                _CERTSPOTTER,
                params={"domain": domain, "include_subdomains": "true", "expand": "dns_names"},
                headers=headers, timeout=20.0,
            )
        except httpx.HTTPError as exc:
            return None, f"{type(exc).__name__}"
        if resp.status_code != 200:
            return None, f"{resp.status_code}" + (" (rate-limited; set TPRM_CERTSPOTTER_TOKEN)"
                                                  if resp.status_code == 429 and not token else "")
        try:
            names: list[str] = []
            for issuance in resp.json():
                names.extend(issuance.get("dns_names", []))
            return names, None
        except ValueError:
            return None, "non-JSON"

    @staticmethod
    def _analyse_names(raw_names: list[str], domain: str) -> tuple[list[str], list[str], bool]:
        """Reduce a flat list of certificate DNS names to (subdomains, stale, wildcard-seen).

        Pure and testable — the CT sources are flaky live, so the logic is covered by a fixture."""
        names: set[str] = set()
        wildcard = False
        for nm in raw_names:
            nm = str(nm).strip().lower()
            if not nm:
                continue
            if nm.startswith("*."):
                wildcard = True
                nm = nm[2:]
            if nm == domain or nm.endswith("." + domain):
                names.add(nm)
        subdomains = sorted(names)
        stale = [n for n in subdomains if _STALE.search(n)]
        return subdomains, stale, wildcard

    @staticmethod
    def parse_entries(entries: list[dict[str, Any]], domain: str) -> tuple[list[str], list[str], bool]:
        """crt.sh row format ({name_value}) -> analysis. Kept for the fixture test."""
        raw: list[str] = []
        for e in entries:
            raw.extend(str(e.get("name_value", "")).split("\n"))
        return CtCollector._analyse_names(raw, domain)

    def _findings(
        self, domain: str, subdomains: list[str], stale: list[str], wildcard: bool, source: str
    ) -> list[Finding]:
        loc = f"{source} %.{domain}"
        return [
            Finding(
                source=self.source, signal="subdomain_estate", subcategory="subdomain_hygiene",
                category=_CAT, observed=f"{len(subdomains)} subdomains",
                value={"count": len(subdomains)}, locator=loc,
            ),
            Finding(
                source=self.source, signal="stale_hosts", subcategory="abandoned_shadow_assets",
                category=_CAT,
                # The denominator is in the OBSERVED string, not only in `value` — E6 charges a
                # rate, and a rate reported without the number it was taken over cannot be checked
                # or disputed by the vendor it is about.
                observed=f"{len(stale)} of {len(subdomains)} names look stale/dev/staging",
                # `denominator` (E6) makes the receipt self-contained: the engine can also pair
                # this with the sibling `subdomain_estate` finding, and does so for evidence
                # captured before this field existed, but a stored finding should not need its
                # sibling to be interpretable years later.
                value={"count": len(stale), "denominator": len(subdomains)}, locator=loc,
                notes="certs issued, not hosts live — possible forgotten hosts",
            ),
            Finding(
                source=self.source, signal="weak_issuance",
                subcategory="certificate_transparency_issues", category=_CAT,
                observed="wildcard_sprawl" if wildcard else "none",
                value={"wildcard_sprawl": wildcard}, locator=loc,
            ),
        ]
