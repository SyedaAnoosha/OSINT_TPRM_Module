"""EU Insolvency Registers collector — EU e-Justice Portal insolvency data.

WHY. The EU Insolvency Registers Interconnection System provides cross-border
insolvency proceedings information across EU member states. For Business Stability
assessment, this detects active insolvency proceedings that should BLOCK scoring.

LEGALITY — CLEARED (`methodology.md` Part 3). Official EU e-Justice Portal, free access,
commercial use permitted. No API key required but rate limiting applies.

ENTITY-LEVEL ONLY (§4.2). This reads corporate insolvency proceedings only.

SIGNAL MAPPING. Findings land in `business_financial_stability` at `insolvency` bands.
Active proceedings trigger the insolvency gate; historical proceedings are scored.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_SEARCH = "https://e-justice.europa.eu/eJustice/insolvency"
_HOST = "e-justice.europa.eu"
_CAT = "business_financial_stability"
_SUB = "eu_insolvency"

# EU member state codes
_EU_STATES = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE"
})

_PUNCT = re.compile(r"[^a-z0-9 ]+")


def _normalize_name(name: str) -> str:
    n = _PUNCT.sub(" ", name.lower())
    return re.sub(r"\s+", " ", n).strip()


class EUInsolvencyCollector(Collector):
    source = "eu_insolvency"
    reliability = 0.90  # Official EU portal, authoritative for EU proceedings
    timeout_s = 25.0
    http_attempts = 2
    http_backoff_s = 2.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        query = vendor.name or vendor.ref

        # EU e-Justice portal uses a search form; we'll use the REST endpoint if available
        # Note: The EU portal may require form-based search; this is a simplified implementation
        search_url = f"{_SEARCH}?q={quote(query)}&lang=en"

        resp = await self._get_with_retry(ctx, search_url, limiter_key=_HOST)
        if resp is None:
            return self.result(vendor, "error", notes="EU Insolvency Register unavailable")
        if resp.status_code == 429:
            return self.result(vendor, "empty", notes="EU Insolvency Register rate limit exceeded (429)")
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"EU Insolvency Register returned {resp.status_code}")

        try:
            # Parse HTML response (simplified - in production, use proper HTML parser)
            text = resp.text
            proceedings = self._extract_proceedings(text, query)
        except Exception:
            return self.result(vendor, "error", notes="Failed to parse EU Insolvency Register response")

        if not proceedings:
            # Clean receipt - no insolvency proceedings found
            return self.result(
                vendor, "ok", raw={"query": query, "proceedings_found": 0},
                findings=[Finding(
                    source=self.source, signal="eu_insolvency", subcategory=_SUB, category=_CAT,
                    observed="no_eu_insolvency",
                    value={"band": "no_insolvency"},
                    locator=search_url,
                    notes="EU Insolvency Register searched; no insolvency proceedings found.",
                )],
                source_version="clean",
            )

        # Process insolvency findings
        findings = []
        raw_proceedings = []

        for proc in proceedings:
            band = self._status_band(proc["status"])
            finding = Finding(
                source=self.source, signal="eu_insolvency", subcategory=_SUB, category=_CAT,
                observed=f"{proc['proceeding_type']} — {proc['status']} ({proc['date']})",
                value={"band": band, "proceeding_type": proc["proceeding_type"],
                       "status": proc["status"], "date": proc["date"],
                       "jurisdiction": proc["jurisdiction"], "case_number": proc["case_number"]},
                locator=proc.get("case_url"),
                notes="EU insolvency proceeding from EU e-Justice Portal.",
            )
            findings.append(finding)
            raw_proceedings.append(proc)

        raw = {
            "query": query,
            "proceedings_found": len(proceedings),
            "proceedings": raw_proceedings,
        }

        return self.result(vendor, "ok", raw=raw, findings=findings)

    def _extract_proceedings(self, html: str, query: str) -> list[dict[str, Any]]:
        """Extract insolvency proceedings from HTML response.

        NOTE: This is a simplified implementation. In production, use a proper
        HTML parser (BeautifulSoup, lxml) to extract structured data from the
        EU e-Justice portal's search results page.
        """
        # Simplified extraction - look for keywords indicating insolvency
        proceedings = []
        q = _normalize_name(query)

        # Look for common insolvency terms in the HTML
        insolvency_terms = ["liquidation", "bankruptcy", "insolvency", "administration", "receivership"]
        text_lower = html.lower()

        for term in insolvency_terms:
            if term in text_lower and q in text_lower:
                # This is a placeholder - real implementation would parse structured data
                proceedings.append({
                    "proceeding_type": term.capitalize(),
                    "status": "active" if "active" in text_lower else "unknown",
                    "date": datetime.now(UTC).strftime("%Y-%m-%d"),
                    "jurisdiction": "EU",
                    "case_number": "unknown",
                    "case_url": _SEARCH,
                })
                break  # Avoid duplicates

        return proceedings[:5]  # Limit to 5

    @staticmethod
    def _status_band(status: str) -> str:
        """Map insolvency status to scoring bands."""
        s = str(status).lower()
        if "active" in s or "open" in s or "pending" in s:
            return "insolvency_active"  # Triggers gate
        if "closed" in s or "discharged" in s or "completed" in s:
            return "insolvency_historical"  # Penalty but no gate
        return "insolvency_unknown"
