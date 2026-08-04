"""CISA KEV collector — vulnerabilities KNOWN to be exploited in the wild.

KEV membership means *observed exploitation*, not theoretical badness — a sharper signal
than CVSS, and the one that drives the knockout floor (§5.5.2). Public JSON feed, no auth.
`catalogVersion` is captured as `source_version` so a finding can be reconstructed against
the exact catalog it came from.

PRODUCT-SCOPED, deliberately (source_assessment.md §9): we match the vendor to the KEV
`vendorProject` field. That only works for vendors who *make software*; for everyone else
KEV is correctly `empty`. Name-matching is coarse and is an entity-resolution limitation,
not a precise attribution — so matched findings are candidates for review, not verdicts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_FEED = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
_CAT = "breach_compromise_history"
_SUB = "exploited_vulnerabilities"


class KevCollector(Collector):
    source = "kev"
    reliability = 0.95  # observed exploitation, not hypothesis (source_assessment.md §9)
    # No KEV match means "no known-exploited CVE name-matches this vendor" — but coarse
    # name-matching and "vendor ships no software" both land here, so a clean receipt is
    # weaker than a positive hit (source_assessment §9).
    clean_reliability = 0.6
    timeout_s = 30.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        await ctx.limiter.acquire("www.cisa.gov")
        try:
            resp = await ctx.http.get(_FEED)
        except httpx.HTTPError as exc:
            return self.result(vendor, "error", notes=f"KEV fetch failed: {type(exc).__name__}: {exc}")
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"KEV returned {resp.status_code}")

        data = resp.json()
        catalog_version = data.get("catalogVersion")
        vulns = data.get("vulnerabilities", [])

        tokens = self._vendor_tokens(vendor)
        matches = [
            v for v in vulns if self._matches(str(v.get("vendorProject", "")).lower(), tokens)
        ]
        if not matches:
            # Clean receipt: reached KEV, no known-exploited CVE name-matches this vendor.
            finding = Finding(
                source=self.source, signal="kev_listed_cve", subcategory=_SUB, category=_CAT,
                observed="no KEV product match",
                value={"band": "no_kev_match"},
                locator=f"CISA KEV {catalog_version}",
                notes="clean receipt — no known-exploited CVE name-matches (or vendor ships no software)",
            )
            return self.result(
                vendor, "ok", source_version=catalog_version, findings=[finding],
                reliability=self._clean_reliability(),
                raw={"catalog_version": catalog_version, "total_kev": len(vulns), "matched": 0},
                notes="no KEV match — recorded as clean receipt (§5.4.2)",
            )

        raw: dict[str, Any] = {
            "catalog_version": catalog_version, "matched": len(matches),
            "matches": [{"cve": m.get("cveID"), "product": m.get("product"),
                         "name": m.get("vulnerabilityName"), "vendor": m.get("vendorProject"),
                         "due": m.get("dueDate"), "ransomware": m.get("knownRansomwareCampaignUse")}
                        for m in matches[:50]],
        }
        findings: list[Finding] = []
        for m in matches:
            findings.append(
                Finding(
                    source=self.source, signal="kev_listed_cve", subcategory=_SUB, category=_CAT,
                    observed=f"{m.get('cveID')} in {m.get('product')} (KEV)",
                    # Band states only what KEV asserts: this product line is known-exploited.
                    # KEV carries no evidence that THIS vendor has patched, so
                    # remediation_evidenced stays False and the mitigation factor stays 1.0.
                    value={"band": "listed", "cve": m.get("cveID"), "product": m.get("product"),
                           "vendor_project": m.get("vendorProject"),
                           "ransomware": m.get("knownRansomwareCampaignUse")},
                    event_date=self._parse_date(m.get("dateAdded")),  # old KEV concerns decay
                    locator=f"CISA KEV {catalog_version} :: {m.get('cveID')}",
                    notes="name-matched to vendorProject — review before treating as attributed",
                )
            )
        return self.result(vendor, "ok", raw=raw, findings=findings, source_version=catalog_version)

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            return None

    @staticmethod
    def _vendor_tokens(vendor: Vendor) -> set[str]:
        tokens = {vendor.ref.lower()}
        if vendor.name:
            tokens.add(vendor.name.lower())
            tokens.update(w for w in vendor.name.lower().split() if len(w) > 3)
        tokens.update(a.lower() for a in vendor.aliases)
        return tokens

    @staticmethod
    def _matches(vendor_project: str, tokens: set[str]) -> bool:
        return any(t in vendor_project or vendor_project in t for t in tokens if t)
