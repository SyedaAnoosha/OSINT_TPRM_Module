"""SEC EDGAR collector — US public company going-concern and bankruptcy filings.

WHY. For US SEC-registered/public companies, EDGAR provides authoritative, timely signals:
- 8-K Item 1.03 (bankruptcy) filed within 4 business days of the event
- "going concern" / "substantial doubt" language in the entity's own recent 10-K/10-Q

This is narrow coverage (public companies only) but very high signal quality where it applies.
For TPRM continuity assessment, this complements The Gazette (UK) and Companies House with a
US-specific authoritative source.

LEGALITY — CLEARED (`methodology.md` Part 3). Free, no API key required, commercial use permitted.
The SEC's EDGAR system is designed for programmatic access. Rate limit: be respectful (≤10 req/sec).

ENTITY-LEVEL ONLY (§4.2). This reads corporate filings only. No natural-person data enters the model.

SIGNAL MAPPING. Findings land in `continuity_context` at `informational` bands, mirroring the
existing `entity_status`/`entity_existence` pattern. The worst standing observed becomes the
headline in `continuity.py`.

DATA SOURCE — VERIFIED AGAINST THE LIVE API, 2026-08. `efts.sec.gov/LATEST/search-index` returns a
raw Elasticsearch result: `hits` is an OBJECT (`{"total": {...}, "hits": [...]}`), not a list — the
actual result rows are at `data["hits"]["hits"]`, each a `{"_id", "_source": {...}}` pair. Query
param is `forms` (comma-separated, e.g. `8-K`), not `type`. Per-hit fields live under `_source`:
`form` (str), `items` (list of 8-K item numbers, e.g. `["1.01","1.03"]`), `file_date`,
`display_names` (list — the FILING PARTY's own name(s), not incidental text mentions), `adsh`
(accession number), `ciks` (list). None of `formType`/`fileNum`/`filmNum`/`fileDate`/`title`/
`description` exist on a real hit; an earlier version of this collector used those names and
returned `status=error` on every single run because of it.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_SEARCH = "https://efts.sec.gov/LATEST/search-index"
_HOST = "efts.sec.gov"
# v5.0.0 (E4/E5) renamed this category from `business_financial_stability` to `continuity_context`
# — see design note §3.4. Findings land here at `informational` bands only; they are
# reported (app/continuity.py) and NEVER penalise posture.
_CAT = "continuity_context"
_SUB = "sec_filing"

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
    """True if `query` names one of the actual FILING parties, not just matched text somewhere.

    `q=<name>` on EDGAR full-text search matches the name ANYWHERE in the document — including a
    competitor's 10-K that merely mentions the vendor. `display_names` is the filer's own name as
    SEC recorded it, so checking against that (not the raw hit) is what keeps a positive finding
    tied to the vendor's OWN filing rather than someone else's filing that mentions them.
    """
    q = _normalize_name(query)
    if not q:
        return False
    for dn in display_names:
        if q in _normalize_name(dn):
            return True
    return False


class EdgarCollector(Collector):
    source = "sec_edgar"
    reliability = 0.97  # SEC's official filing system — authoritative for US public companies
    timeout_s = 20.0
    http_attempts = 2
    http_backoff_s = 1.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        query = vendor.name or vendor.ref

        # SEC's fair-access policy requires an accurate contact in the User-Agent or it can block
        # the IP — reuse the platform's configured contact, never a placeholder address.
        headers = {"User-Agent": ctx.settings.user_agent}

        bankruptcy_url = f"{_SEARCH}?q={quote(query)}&forms=8-K"
        resp = await self._get_with_retry(ctx, bankruptcy_url, limiter_key=_HOST, headers=headers)
        if resp is None:
            return self.result(vendor, "error", notes="SEC EDGAR unavailable")
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"SEC EDGAR returned {resp.status_code}")

        try:
            hits = resp.json().get("hits", {}).get("hits", [])
            filings = self._extract_bankruptcy_filings(hits, query)
        except Exception:
            return self.result(vendor, "error", notes="Failed to parse SEC EDGAR response")

        if not filings:
            gc_url = f"{_SEARCH}?q={quote(f'{query} going concern')}&forms=10-K,10-Q"
            resp_gc = await self._get_with_retry(ctx, gc_url, limiter_key=_HOST, headers=headers)
            if resp_gc is not None and resp_gc.status_code == 200:
                try:
                    hits_gc = resp_gc.json().get("hits", {}).get("hits", [])
                    filings = self._extract_going_concern_flags(hits_gc, query)
                except Exception:
                    filings = []

        if not filings:
            return self.result(
                vendor, "ok", raw={"query": query, "filings_found": 0},
                findings=[Finding(
                    source=self.source, signal="sec_filing", subcategory=_SUB, category=_CAT,
                    observed="no_adverse_sec_filings",
                    value={"band": "no_adverse_filings"},
                    locator=bankruptcy_url,
                    notes="SEC EDGAR searched; no bankruptcy or going-concern filings found.",
                )],
                source_version="clean",
            )

        findings = []
        for filing in filings:
            band = self._band(filing["filing_type"])
            signal_name = self._signal_name(filing["filing_type"])
            findings.append(Finding(
                source=self.source, signal=signal_name, subcategory=_SUB, category=_CAT,
                observed=f"{filing['filing_type']} — {filing['filing_date']}",
                value={"band": band, "filing_type": filing["filing_type"],
                       "filing_date": filing["filing_date"],
                       "document_url": filing["document_url"]},
                locator=filing["document_url"],
                notes="SEC filing indicating bankruptcy or going-concern uncertainty.",
            ))

        raw = {"query": query, "filings_found": len(filings), "filings": filings}
        return self.result(vendor, "ok", raw=raw, findings=findings)

    @staticmethod
    def _extract_bankruptcy_filings(hits: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
        """8-K Item 1.03 filings, matched via the real `items` field, not title-text guessing."""
        filings = []
        for hit in hits:
            src = hit.get("_source", {})
            if "1.03" not in src.get("items", []):
                continue
            if not _filed_by(src.get("display_names", []), query):
                continue
            filings.append({
                "filing_type": "8-K Item 1.03 (Bankruptcy)",
                "filing_date": src.get("file_date", "unknown"),
                "document_url": _filing_index_url(src),
            })
            if len(filings) >= 5:
                break
        return filings

    @staticmethod
    def _extract_going_concern_flags(hits: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
        """10-K/10-Q hits for a going-concern/substantial-doubt query, filed BY this vendor."""
        filings = []
        for hit in hits:
            src = hit.get("_source", {})
            if src.get("form", "") not in ("10-K", "10-K/A", "10-Q", "10-Q/A"):
                continue
            if not _filed_by(src.get("display_names", []), query):
                continue
            filings.append({
                "filing_type": "Going Concern Flag",
                "filing_date": src.get("file_date", "unknown"),
                "document_url": _filing_index_url(src),
            })
            if len(filings) >= 5:
                break
        return filings

    @staticmethod
    def _band(filing_type: str) -> str:
        """Map SEC filing type onto the EXISTING entity_status bands."""
        ft = filing_type.lower()
        if "bankruptcy" in ft or "item 1.03" in ft:
            return "entity_inactive"  # ceased
        return "registration_lapsed"  # going-concern doubt — watch, not yet ceased

    @staticmethod
    def _signal_name(filing_type: str) -> str:
        """Map SEC filing type to appropriate signal name to avoid duplication."""
        ft = filing_type.lower()
        if "going concern" in ft:
            return "sec_going_concern"  # Separate signal for going-concern
        return "sec_filing"  # Default signal for bankruptcy


def _filing_index_url(src: dict[str, Any]) -> str:
    """The filing's index page — always resolvable from `ciks`/`adsh` alone, unlike a specific
    document filename (which would need parsing the hit's compound `_id`)."""
    ciks = src.get("ciks") or []
    adsh = src.get("adsh", "")
    if not ciks or not adsh:
        return "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
    cik = ciks[0].lstrip("0") or "0"
    accession_nodash = adsh.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{adsh}-index.htm"
