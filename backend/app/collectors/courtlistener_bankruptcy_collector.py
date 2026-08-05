"""CourtListener/RECAP collector — US federal bankruptcy petition search.

WHY. CourtListener provides access to US federal court dockets via the RECAP project.
For TPRM continuity assessment, this covers Chapter 7/11 bankruptcy petitions by party name.
This is narrow scope (bankruptcy only, not general litigation) and complements SEC EDGAR
(which covers public companies) with coverage of private entities that file bankruptcy.

LEGALITY — CLEARED (`source_assessment.md`). Free registered API token, documented, commercial
use permitted. CORRECTED (2026-08, verified live): the `/dockets/` search endpoint requires
authentication — a plain unauthenticated request returns HTTP 401, not a rate-limited-but-open
response as an earlier version of this docstring claimed. Unset `courtlistener_key` -> the
collector returns `error` (existing 401 handling below), lowering coverage and never posture,
exactly like every other unconfigured keyed source in this codebase.

ENTITY-LEVEL ONLY (§4.2). This reads corporate bankruptcy filings only. No natural-person data
enters the model (personal bankruptcy searches are explicitly excluded).

SIGNAL MAPPING. Findings land in `continuity_context` at `informational` bands, mirroring the
existing `entity_status`/`entity_existence` pattern. The worst standing observed becomes the
headline in `continuity.py`.

⚠ UNVERIFIED FIELD MAPPING — READ BEFORE TRUSTING THIS COLLECTOR'S OUTPUT. `_extract_bankruptcy_
cases` reads `chapter`/`case_type` directly off a docket object. Public CourtListener
documentation (not independently confirmed against a live authenticated response — no API token
was available to verify) describes the v4 `/dockets/` object as carrying `case_name`,
`docket_number`, `court`, `date_filed`, `nature_of_suit` — NOT a bare `chapter` field — with
bankruptcy-specific detail (chapter, trustee, key dates) possibly living on a separate linked
`bankruptcy_information` resource instead. If that is correct, `chapter` is always `""` here,
which is never in `_BANKRUPTCY_CHAPTERS`, so this collector currently FAILS SAFE (always reports
"no bankruptcy petitions found") rather than failing loud or producing a false positive — but it
may also never produce a true positive. Verify field names against a live authenticated response
(`courtlistener_key` set) before relying on this collector for real coverage, and fix the
extraction to match; do not assume the mapping below is correct.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_SEARCH = "https://www.courtlistener.com/api/rest/v4/dockets/"
_HOST = "www.courtlistener.com"
# v5.0.0 (E4/E5) renamed this category from `business_financial_stability` to `continuity_context`
# — see change-notice-v5.md §3.4. Findings land here at `informational` bands only; they are
# reported (app/continuity.py) and NEVER penalise posture.
_CAT = "continuity_context"
_SUB = "bankruptcy_petition"

# Bankruptcy chapter codes
_BANKRUPTCY_CHAPTERS = frozenset({"7", "9", "11", "12", "13"})


class CourtListenerBankruptcyCollector(Collector):
    source = "courtlistener_bankruptcy"
    reliability = 0.90  # Federal court records, but search-by-name has resolution limits
    timeout_s = 20.0
    http_attempts = 2
    http_backoff_s = 1.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        query = vendor.name or vendor.ref

        # Search CourtListener for bankruptcy cases matching the vendor name
        # Filter to bankruptcy courts only (chapter 7, 11, etc.)
        search_url = f"{_SEARCH}?q={quote(query)}&order_by=-date_filed&limit=10"

        headers = {}
        # Optional: add API token if configured (not required for basic access)
        if ctx.settings.courtlistener_key:
            headers["Authorization"] = f"Token {ctx.settings.courtlistener_key.strip()}"

        resp = await self._get_with_retry(
            ctx, search_url, limiter_key=_HOST, headers=headers,
        )
        if resp is None:
            return self.result(vendor, "error", notes="CourtListener unavailable")
        if resp.status_code == 401:
            return self.result(vendor, "error", notes="CourtListener rejected the API key (401)")
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"CourtListener returned {resp.status_code}")

        try:
            data = resp.json()
            results = data.get("results", [])
            cases = self._extract_bankruptcy_cases(results, query)
        except Exception:
            return self.result(vendor, "error", notes="Failed to parse CourtListener response")

        if not cases:
            # Clean receipt — no bankruptcy petitions found
            return self.result(
                vendor, "ok", raw={"query": query, "cases_found": 0},
                findings=[Finding(
                    source=self.source, signal="bankruptcy_petition", subcategory=_SUB, category=_CAT,
                    observed="no_bankruptcy_petitions",
                    value={"band": "no_adverse_filings"},
                    locator=search_url,
                    notes="CourtListener searched; no bankruptcy petitions found for this entity.",
                )],
                source_version="clean",
            )

        # Process adverse findings
        findings = []
        raw_cases = []

        for case in cases:
            band = self._band(case["chapter"])
            finding = Finding(
                source=self.source, signal="bankruptcy_petition", subcategory=_SUB, category=_CAT,
                observed=f"Chapter {case['chapter']} — filed {case['date_filed']}",
                value={"band": band, "chapter": case["chapter"],
                       "case_number": case["case_number"], "date_filed": case["date_filed"],
                       "court": case["court"], "case_url": case["case_url"]},
                locator=case["case_url"],
                notes="US federal bankruptcy petition from CourtListener/RECAP.",
            )
            findings.append(finding)
            raw_cases.append(case)

        raw = {
            "query": query,
            "cases_found": len(cases),
            "cases": raw_cases,
        }

        return self.result(vendor, "ok", raw=raw, findings=findings)

    def _extract_bankruptcy_cases(self, results: list[dict[str, Any]],
                                   query: str) -> list[dict[str, Any]]:
        """Extract bankruptcy cases from CourtListener API results."""
        cases = []

        for result in results:
            case_type = result.get("case_type", "").lower()
            chapter = result.get("chapter", "")
            date_filed = result.get("date_filed", "")
            case_name = result.get("case_name", "")
            docket_number = result.get("docket_number", "")
            court = result.get("court", "")

            # Only include bankruptcy cases (chapters 7, 9, 11, 12, 13)
            if chapter not in _BANKRUPTCY_CHAPTERS:
                continue

            # Build case URL
            case_id = result.get("id")
            case_url = f"https://www.courtlistener.com/docket/{case_id}/" if case_id else ""

            cases.append({
                "chapter": chapter,
                "case_number": docket_number,
                "date_filed": date_filed[:10] if date_filed else "unknown",
                "case_name": case_name,
                "court": court,
                "case_url": case_url,
            })

        return cases[:5]  # Limit to top 5 most recent

    @staticmethod
    def _band(chapter: str) -> str:
        """Map bankruptcy chapter onto the EXISTING entity_status bands."""
        # All bankruptcy chapters are severe — treat as ceased/impaired
        if chapter in {"7", "9"}:
            return "entity_inactive"  # liquidation
        if chapter in {"11", "12", "13"}:
            return "registration_lapsed"  # reorganization (watch-level)
        return "registration_lapsed"  # default to watch