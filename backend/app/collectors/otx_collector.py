"""OTX collector — passive DNS as CERTIFICATE-TRANSPARENCY REDUNDANCY for Digital Footprint.

WHY THIS EXISTS. Digital Footprint depends ENTIRELY on Certificate Transparency (crt.sh, with a
Cert Spotter fallback), and CT is famously flaky — crt.sh 502s and times out routinely. When it is
briefly down the whole category zeros and a genuinely-clean vendor tips to *The Ghost*: honest, but
avoidable. AlienVault OTX publishes passive-DNS observations — hostnames actually seen resolving
under a domain — which is an INDEPENDENT way to enumerate the subdomain estate. When CT answers,
both emit `subdomain_estate` and the engine takes the worst (no double-count); when CT fails, OTX
carries the category so the vendor is not falsely refused.

LEGALITY / KEY. OTX is free with a registered API key (`otx.alienvault.com`). Cleared as CT
redundancy (design note §6). Unset key is NOT an error — the collector returns `empty`, which
lowers coverage and never posture, exactly like every other keyed source. The app runs unconfigured.

WHAT IT IS NOT. Passive DNS shows a hostname was OBSERVED, not that it is live now — the same
"issued, not live" caveat CT carries. So it feeds the same count-banded `subdomain_estate` signal
and inherits the same honest limit, rather than pretending to more certainty than it has.
"""

from __future__ import annotations

from typing import Any

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_API = "https://otx.alienvault.com/api/v1/indicators/domain/{domain}/passive_dns"
_HOST = "otx.alienvault.com"
_CAT = "digital_footprint_assets"


class OtxCollector(Collector):
    source = "otx"
    reliability = 0.7  # community threat-intel feed; independent corroboration of CT, not a register
    timeout_s = 25.0
    http_attempts = 2
    http_backoff_s = 1.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        key = ctx.settings.otx_api_key.strip()
        if not key:
            return self.result(
                vendor, "empty",
                notes="TPRM_OTX_API_KEY not set — OTX not consulted (CT redundancy off; lowers "
                      "coverage, never posture). Free key at otx.alienvault.com",
            )
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")
        if not vendor.domain:
            return self.result(vendor, "empty", notes="no domain — passive DNS is domain-scoped")

        resp = await self._get_with_retry(
            ctx, _API.format(domain=vendor.domain), limiter_key=_HOST,
            headers={"X-OTX-API-KEY": key},
        )
        if resp is None:
            return self.result(vendor, "error", notes="OTX unavailable")
        if resp.status_code == 404:
            # OTX genuinely has nothing on this domain — a coverage fact, not a risk fact.
            return self.result(vendor, "empty", raw={"domain": vendor.domain, "http": 404},
                               notes="no passive-DNS record for this domain")
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"OTX returned {resp.status_code}")

        try:
            payload = resp.json()
        except ValueError:
            return self.result(vendor, "error", notes="OTX response was not JSON")

        subdomains = self._subdomains(payload, vendor.domain)
        if not subdomains:
            return self.result(vendor, "empty", raw={"domain": vendor.domain, "passive_dns": 0},
                               notes="passive DNS returned no in-scope hostnames")

        raw: dict[str, Any] = {
            "domain": vendor.domain,
            "unique_subdomains": len(subdomains),
            "subdomains_sample": sorted(subdomains)[:50],
            "source_note": "passive DNS (observed, not necessarily live) — CT redundancy",
        }
        finding = Finding(
            source=self.source, signal="subdomain_estate", subcategory="subdomain_hygiene",
            category=_CAT, observed=f"{len(subdomains)} subdomains via passive DNS",
            value={"count": len(subdomains)}, locator=f"OTX passive DNS for {vendor.domain}",
            notes="independent of Certificate Transparency — carries Digital Footprint when CT is "
                  "briefly unavailable (issued/observed ≠ live, same caveat as CT)",
        )
        return self.result(vendor, "ok", raw=raw, findings=[finding], source_version="live")

    @staticmethod
    def _subdomains(payload: dict[str, Any], domain: str) -> set[str]:
        """Registrable-scoped hostnames from the passive_dns list. Only names UNDER the vendor's
        own domain — passive DNS can return unrelated hosts sharing an IP, which are not this
        vendor's estate and must not inflate its footprint."""
        base = domain.lower().lstrip(".")
        out: set[str] = set()
        for record in payload.get("passive_dns") or []:
            host = str(record.get("hostname") or "").strip().lower().rstrip(".")
            if host and (host == base or host.endswith("." + base)):
                out.add(host)
        return out
