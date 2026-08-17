"""Canada Bankruptcy collector — Office of the Superintendent of Bankruptcy.

WHY. The Office of the Superintendent of Bankruptcy (OSB) provides official
bankruptcy records for Canadian companies. For Business Stability assessment,
this detects active bankruptcy proceedings that should BLOCK scoring.

LEGALITY — CLEARED (`source_assessment.md`). Official Canadian government portal,
paid access ($8 per search). Unset API key -> collector returns `empty`.

ENTITY-LEVEL ONLY (§4.2). This reads corporate bankruptcy filings only.

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

_SEARCH = "https://ised-isde.canada.ca/site/ised/en/osb-search"
_HOST = "ised-isde.canada.ca"
_CAT = "business_financial_stability"
_SUB = "canada_bankruptcy"

_PUNCT = re.compile(r"[^a-z0-9 ]+")


def _normalize_name(name: str) -> str:
    n = _PUNCT.sub(" ", name.lower())
    return re.sub(r"\s+", " ", n).strip()


class CanadaBankruptcyCollector(Collector):
    source = "canada_bankruptcy"
    reliability = 0.92  # Official Canadian government register
    timeout_s = 25.0
    http_attempts = 2
    http_backoff_s = 2.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        query = vendor.name or vendor.ref
        api_key = ctx.settings.canada_bankruptcy_key.strip() if hasattr(ctx.settings, 'canada_bankruptcy_key') else ""

        if not api_key:
            return self.result(
                vendor, "empty",
                notes="TPRM_CANADA_BANKRUPTCY_KEY not set — OSB not consulted (lowers coverage). "
                      "Paid access at ised-isde.canada.ca.",
            )

        search_url = f"{_SEARCH}?q={quote(query)}"
        if api_key:
            search_url += f"&api_key={api_key}"

        resp = await self._get_with_retry(ctx, search_url, limiter_key=_HOST)
        if resp is None:
            return self.result(vendor, "error", notes="Canada OSB unavailable")
        if resp.status_code == 401:
            return self.result(vendor, "error", notes="Canada OSB rejected the API key (401)")
        if resp.status_code == 429:
            return self.result(vendor, "empty", notes="Canada OSB rate limit exceeded (429)")
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"Canada OSB returned {resp.status_code}")

        try:
            data = resp.json()
            results = data.get("results", [])
        except Exception:
            return self.result(vendor, "error", notes="Failed to parse Canada OSB response")

        if not results:
            return self.result(
                vendor, "ok", raw={"query": query, "records_found": 0},
                findings=[Finding(
                    source=self.source, signal="canada_bankruptcy", subcategory=_SUB, category=_CAT,
                    observed="no_canada_bankruptcy",
                    value={"band": "no_insolvency"},
                    locator=search_url,
                    notes="Canada OSB searched; no bankruptcy records found.",
                )],
                source_version="clean",
            )

        findings = []
        raw_records = []

        for record in results:
            band = self._status_band(record.get("status"))
            finding = Finding(
                source=self.source, signal="canada_bankruptcy", subcategory=_SUB, category=_CAT,
                observed=f"{record.get('proceeding_type')} — {record.get('status')} ({record.get('date')})",
                value={"band": band, "proceeding_type": record.get("proceeding_type"),
                       "status": record.get("status"), "date": record.get("date"),
                       "city": record.get("city"), "province": record.get("province"),
                       "file_number": record.get("file_number")},
                locator=record.get("record_url"),
                notes="Canadian bankruptcy record from Office of the Superintendent of Bankruptcy.",
            )
            findings.append(finding)
            raw_records.append(record)

        raw = {
            "query": query,
            "records_found": len(results),
            "records": raw_records,
        }

        return self.result(vendor, "ok", raw=raw, findings=findings)

    @staticmethod
    def _status_band(status: str | None) -> str:
        """Map bankruptcy status to scoring bands."""
        s = str(status or "").lower()
        if "active" in s or "open" in s:
            return "insolvency_active"
        if "discharged" in s or "closed" in s or "completed" in s:
            return "insolvency_historical"
        return "insolvency_unknown"
