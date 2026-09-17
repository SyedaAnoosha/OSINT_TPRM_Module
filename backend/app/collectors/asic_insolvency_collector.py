"""ASIC Insolvency collector — Australian Securities and Investments Commission.

WHY. ASIC provides official insolvency and liquidator registers for Australian
companies. For Business Stability assessment, this detects active insolvency
proceedings that should BLOCK scoring.

LEGALITY — CLEARED (`methodology.md` Part 3). Official Australian government portal,
free access for basic searches, commercial use permitted.

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

_SEARCH = "https://connectonline.asic.gov.au/Regulator/Find.Lodgement"
_HOST = "connectonline.asic.gov.au"
_CAT = "business_financial_stability"
_SUB = "asic_insolvency"

_PUNCT = re.compile(r"[^a-z0-9 ]+")


def _normalize_name(name: str) -> str:
    n = _PUNCT.sub(" ", name.lower())
    return re.sub(r"\s+", " ", n).strip()


class ASICInsolvencyCollector(Collector):
    source = "asic_insolvency"
    reliability = 0.92  # Official Australian government register
    timeout_s = 25.0
    http_attempts = 2
    http_backoff_s = 2.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        query = vendor.name or vendor.ref

        # ASIC insolvency search
        search_url = f"{_SEARCH}?q={quote(query)}&type=insolvency"

        resp = await self._get_with_retry(ctx, search_url, limiter_key=_HOST)
        if resp is None:
            return self.result(vendor, "error", notes="ASIC Insolvency Register unavailable")
        if resp.status_code == 429:
            return self.result(vendor, "empty", notes="ASIC Insolvency Register rate limit exceeded (429)")
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"ASIC Insolvency Register returned {resp.status_code}")

        try:
            text = resp.text
            proceedings = self._extract_proceedings(text, query)
        except Exception:
            return self.result(vendor, "error", notes="Failed to parse ASIC Insolvency Register response")

        if not proceedings:
            return self.result(
                vendor, "ok", raw={"query": query, "proceedings_found": 0},
                findings=[Finding(
                    source=self.source, signal="asic_insolvency", subcategory=_SUB, category=_CAT,
                    observed="no_asic_insolvency",
                    value={"band": "no_insolvency"},
                    locator=search_url,
                    notes="ASIC Insolvency Register searched; no insolvency proceedings found.",
                )],
                source_version="clean",
            )

        findings = []
        raw_proceedings = []

        for proc in proceedings:
            band = self._status_band(proc["status"])
            finding = Finding(
                source=self.source, signal="asic_insolvency", subcategory=_SUB, category=_CAT,
                observed=f"{proc['proceeding_type']} — {proc['status']} ({proc['date']})",
                value={"band": band, "proceeding_type": proc["proceeding_type"],
                       "status": proc["status"], "date": proc["date"],
                       "liquidator": proc["liquidator"], "acn": proc["acn"]},
                locator=proc.get("case_url"),
                notes="Australian insolvency proceeding from ASIC.",
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

        NOTE: This is a simplified implementation. ASIC uses specific
        HTML structure; in production, use proper HTML parsing.
        """
        proceedings = []
        q = _normalize_name(query)

        # Look for Australian insolvency terms
        aus_terms = ["liquidation", "administration", "insolvency", "winding up", "receivership"]
        text_lower = html.lower()

        for term in aus_terms:
            if term in text_lower and q in text_lower:
                proceedings.append({
                    "proceeding_type": term.capitalize(),
                    "status": "active" if "active" in text_lower else "unknown",
                    "date": datetime.now(UTC).strftime("%Y-%m-%d"),
                    "liquidator": "unknown",
                    "acn": "unknown",
                    "case_url": _SEARCH,
                })
                break

        return proceedings[:5]

    @staticmethod
    def _status_band(status: str) -> str:
        """Map insolvency status to scoring bands."""
        s = str(status).lower()
        if "active" in s or "current" in s:
            return "insolvency_active"
        if "completed" in s or "finalised" in s or "closed" in s:
            return "insolvency_historical"
        return "insolvency_unknown"
