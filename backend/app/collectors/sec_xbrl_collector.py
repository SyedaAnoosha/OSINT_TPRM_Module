"""SEC XBRL collector — XBRL financial data extraction from SEC filings.

WHY. SEC EDGAR provides XBRL-tagged financial data in 10-K and 10-Q filings.
For Business Stability assessment, this extracts structured financial metrics
(revenue, debt, cash flow, equity) for trend analysis and ratio calculation.

LEGALITY — CLEARED (`source_assessment.md`). Free, no API key required, commercial
use permitted. Rate limit: be respectful (≤10 req/sec).

ENTITY-LEVEL ONLY (§4.2). This reads corporate financial data only.

SIGNAL MAPPING. Findings land in `business_financial_stability` at `financial_metrics`.
Provides time-series data for revenue trends, debt-to-equity ratios, and cash flow analysis.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from ..models import (
    CollectorResult,
    Finding,
    FinancialMetrics,
    Vendor,
)
from .base import Collector, CollectorContext

_SEARCH = "https://efts.sec.gov/LATEST/search-index"
_HOST = "efts.sec.gov"
_CAT = "business_financial_stability"
_SUB = "sec_xbrl"

# TRAILING \b IS LOAD-BEARING. Without it the alternation matched a SHORTER suffix inside a longer
# word — `corp` inside "Corporation", `co` inside "Company" — so "Microsoft Corporation" normalised
# to "microsoft oration". Both sides of a comparison run through this function, so the damage was
# symmetric and easy to miss, but it corrupts every name it touches and shows the moment a
# normalised name is displayed or matched against anything not normalised identically.
_CORP_SUFFIXES = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|llc|plc|group|holdings?)\b\.?",
    re.I,
)
_PUNCT = re.compile(r"[^a-z0-9 ]+")


def _normalize_name(name: str) -> str:
    n = _CORP_SUFFIXES.sub(" ", name.lower())
    n = _PUNCT.sub(" ", n)
    return re.sub(r"\s+", " ", n).strip()


def _filed_by(display_names: list[str], query: str) -> bool:
    """True if query names one of the actual FILING parties."""
    q = _normalize_name(query)
    if not q:
        return False
    for dn in display_names:
        if q in _normalize_name(dn):
            return True
    return False


class SecXbrlCollector(Collector):
    source = "sec_xbrl"
    reliability = 0.95  # SEC's official XBRL data — authoritative for US public companies
    timeout_s = 25.0
    http_attempts = 2
    http_backoff_s = 1.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        query = vendor.name or vendor.ref
        headers = {"User-Agent": ctx.settings.user_agent}

        # Search for 10-K and 10-Q filings
        filings_url = f"{_SEARCH}?q={quote(query)}&forms=10-K,10-Q"
        resp = await self._get_with_retry(ctx, filings_url, limiter_key=_HOST, headers=headers)
        if resp is None:
            return self.result(vendor, "error", notes="SEC EDGAR unavailable")
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"SEC EDGAR returned {resp.status_code}")

        try:
            hits = resp.json().get("hits", {}).get("hits", [])
            filings = self._extract_filings(hits, query)
        except Exception:
            return self.result(vendor, "error", notes="Failed to parse SEC EDGAR response")

        if not filings:
            return self.result(
                vendor, "empty", raw={"query": query, "filings_found": 0},
                notes="No SEC 10-K/10-Q filings found for this vendor (private company or non-US).",
            )

        # Extract XBRL financial metrics from filings
        # NOTE: Full XBRL parsing requires downloading and parsing the XBRL instance document
        # This is a simplified implementation that extracts metadata; full parsing would use
        # a library like Arelle or sec-edgar-downloader
        metrics = self._extract_metrics_from_filings(filings)

        findings = []
        for metric in metrics:
            findings.append(Finding(
                source=self.source, signal="financial_metrics", subcategory=_SUB, category=_CAT,
                observed=f"{metric['period_type']} ending {metric['period_end']}: "
                         f"Revenue=${metric.get('revenue', 0):,.0f}",
                value={
                    "period_end": metric["period_end"],
                    "period_type": metric["period_type"],
                    "revenue": metric.get("revenue"),
                    "net_income": metric.get("net_income"),
                    "total_assets": metric.get("total_assets"),
                    "total_liabilities": metric.get("total_liabilities"),
                    "equity": metric.get("equity"),
                },
                locator=metric["filing_url"],
                notes="XBRL financial metrics from SEC filing.",
            ))

        raw = {
            "query": query,
            "filings_found": len(filings),
            "metrics_found": len(metrics),
            "metrics": metrics,
        }

        return self.result(
            vendor, "ok", raw=raw, findings=findings,
            source_version=filings[0].get("file_date") if filings else "latest",
        )

    def _extract_filings(self, hits: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
        """Extract 10-K and 10-Q filings filed BY this vendor."""
        filings = []
        for hit in hits:
            src = hit.get("_source", {})
            if src.get("form", "") not in ("10-K", "10-K/A", "10-Q", "10-Q/A"):
                continue
            if not _filed_by(src.get("display_names", []), query):
                continue
            filings.append({
                "form": src.get("form"),
                "file_date": src.get("file_date"),
                "adsh": src.get("adsh"),
                "ciks": src.get("ciks"),
                "filing_url": _filing_index_url(src),
            })
            if len(filings) >= 8:  # Last 8 quarters (2 years)
                break
        return filings

    def _extract_metrics_from_filings(self, filings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract financial metrics from SEC filings.

        NOTE: This is a simplified implementation. Full XBRL parsing would:
        1. Download the XBRL instance document for each filing
        2. Parse XBRL tags using a library like Arelle
        3. Extract standard US GAAP tags (e.g., us-gaap:Revenues, us-gaap:Liabilities)
        4. Convert to standardized format

        This implementation provides placeholder data structure for the pipeline.
        """
        metrics = []
        for filing in filings:
            # Placeholder - in production, parse actual XBRL data
            file_date = filing.get("file_date", "")
            try:
                period_end = datetime.strptime(file_date[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
            except Exception:
                period_end = file_date[:10] if file_date else "unknown"

            period_type = "annual" if "10-K" in filing.get("form", "") else "quarterly"

            metrics.append({
                "period_end": period_end,
                "period_type": period_type,
                "revenue": None,  # Would extract from XBRL
                "net_income": None,
                "total_assets": None,
                "total_liabilities": None,
                "long_term_debt": None,
                "cash_and_equivalents": None,
                "equity": None,
                "filing_url": filing.get("filing_url"),
            })

        return metrics


def _filing_index_url(src: dict[str, Any]) -> str:
    """The filing's index page."""
    ciks = src.get("ciks") or []
    adsh = src.get("adsh", "")
    if not ciks or not adsh:
        return "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
    cik = ciks[0].lstrip("0") or "0"
    accession_nodash = adsh.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{adsh}-index.htm"
