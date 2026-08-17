"""OpenCorporates collector — Global company registry aggregator.

WHY. OpenCorporates aggregates company data from 140+ jurisdictions, providing
incorporation dates, company status, and registry numbers globally. For Business
Stability assessment, this fills coverage gaps where jurisdiction-specific
collectors are unavailable or fail.

LEGALITY — CLEARED (`source_assessment.md`). Freemium API with 5,000 free calls/month.
Commercial use permitted with attribution. Unset API key -> collector returns `empty`,
lowering coverage and never posture.

ENTITY-LEVEL ONLY (§4.2). This reads corporate entity data only. No natural-person data.

SIGNAL MAPPING. Findings land in `business_financial_stability` at `entity_status` bands.
Provides incorporation date for age-based scoring and company status for gate logic.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from ..models import (
    CollectorResult,
    Finding,
    FinancialProfile,
    InsolvencyRecord,
    InsolvencyStatus,
    ProfileField,
    Vendor,
)
from .base import Collector, CollectorContext

_SEARCH = "https://api.opencorporates.com/v0.4/companies/search"
_COMPANY = "https://api.opencorporates.com/v0.4/companies/"
_HOST = "api.opencorporates.com"
_CAT = "business_financial_stability"
_SUB = "global_registry"

# TRAILING \b IS LOAD-BEARING. Without it the alternation matched a SHORTER suffix inside a longer
# word — `corp` inside "Corporation", `co` inside "Company" — so "Microsoft Corporation" normalised
# to "microsoft oration". Both sides of a comparison run through this function, so the damage was
# symmetric and easy to miss, but it corrupts every name it touches and shows the moment a
# normalised name is displayed or matched against anything not normalised identically.
_CORP_SUFFIXES = re.compile(
    r"\b(inc|incorporated|corp|corporation|co|company|ltd|limited|llc|plc|group|holdings?|gmbh|sarl|sa|bv|nv|pty)\b\.?",
    re.I,
)
_PUNCT = re.compile(r"[^a-z0-9 ]+")


def _normalize_name(name: str) -> str:
    n = _CORP_SUFFIXES.sub(" ", name.lower())
    n = _PUNCT.sub(" ", n)
    return re.sub(r"\s+", " ", n).strip()


class OpenCorporatesCollector(Collector):
    source = "open_corporates"
    reliability = 0.85  # Aggregator with varying source quality across jurisdictions
    timeout_s = 20.0
    http_attempts = 2
    http_backoff_s = 1.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        query = vendor.name or vendor.ref
        api_key = ctx.settings.opend_corporates_key.strip() if hasattr(ctx.settings, 'opend_corporates_key') else ""

        # Build search URL
        search_url = f"{_SEARCH}?q={quote(query)}&order=score&per_page=5"
        if api_key:
            search_url += f"&api_token={api_key}"

        resp = await self._get_with_retry(ctx, search_url, limiter_key=_HOST)
        if resp is None:
            return self.result(vendor, "error", notes="OpenCorporates unavailable")
        if resp.status_code == 401:
            return self.result(vendor, "error", notes="OpenCorporates rejected the API key (401)")
        if resp.status_code == 429:
            return self.result(vendor, "empty", notes="OpenCorporates rate limit exceeded (429)")
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"OpenCorporates returned {resp.status_code}")

        try:
            data = resp.json()
            results = data.get("results", {}).get("companies", [])
        except Exception:
            return self.result(vendor, "error", notes="Failed to parse OpenCorporates response")

        if not results:
            return self.result(
                vendor, "empty", raw={"query": query, "companies_found": 0},
                notes="No OpenCorporates match found for this vendor",
            )

        # Resolve best match
        best = self._resolve(results, query)
        if best is None:
            return self.result(
                vendor, "empty", raw={"query": query, "candidates": len(results)},
                notes="No confident OpenCorporates match",
            )

        # Fetch full company details
        company_id = best.get("company", {}).get("jurisdiction_code", "") + "/" + best.get("company", {}).get("company_number", "")
        company_url = f"{_COMPANY}{company_id}"
        if api_key:
            company_url += f"?api_token={api_key}"

        company_resp = await self._get_with_retry(ctx, company_url, limiter_key=_HOST)
        if company_resp is None or company_resp.status_code != 200:
            # Use search results if detail fetch fails
            company_data = best
        else:
            try:
                company_data = company_resp.json().get("results", {}).get("company", {})
            except Exception:
                company_data = best

        # Extract financial profile data
        profile_data = self._extract_profile_data(company_data)

        findings = []
        if profile_data["incorporation_date"]:
            findings.append(Finding(
                source=self.source, signal="incorporation_date", subcategory=_SUB, category=_CAT,
                observed=f"Incorporated: {profile_data['incorporation_date']}",
                value={"incorporation_date": profile_data["incorporation_date"]},
                locator=company_url,
                notes="Incorporation date from OpenCorporates global registry.",
            ))

        if profile_data["company_status"]:
            band = self._status_band(profile_data["company_status"])
            findings.append(Finding(
                source=self.source, signal="company_status", subcategory=_SUB, category=_CAT,
                observed=f"Status: {profile_data['company_status']}",
                value={"band": band, "company_status": profile_data["company_status"]},
                locator=company_url,
                notes="Company status from OpenCorporates global registry.",
            ))

        raw = {
            "query": query,
            "company_id": company_id,
            "company_name": profile_data.get("company_name"),
            "jurisdiction": profile_data.get("jurisdiction"),
            "company_number": profile_data.get("company_number"),
            "incorporation_date": profile_data.get("incorporation_date"),
            "company_status": profile_data.get("company_status"),
            "company_type": profile_data.get("company_type"),
        }

        return self.result(
            vendor, "ok", raw=raw, findings=findings,
            source_version=profile_data.get("updated_at") or "latest",
        )

    def _resolve(self, results: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
        """Resolve the best matching company from search results."""
        q = _normalize_name(query)
        scored = [(r, self._score(r, q)) for r in results]
        strong = [(r, s) for r, s in scored if s[0] >= 2]
        if not strong:
            return None
        return max(strong, key=lambda p: p[1])[0]

    def _score(self, result: dict[str, Any], query: str) -> tuple:
        """Score a search result against the query."""
        company = result.get("company", {})
        name = _normalize_name(company.get("name") or "")
        q = _normalize_name(query)

        if name == q:
            name_score = 3
        elif q and (name.startswith(q) or q in name):
            name_score = 2
        elif q and set(q.split()) & set(name.split()):
            name_score = 1
        else:
            name_score = 0

        # Prefer active companies
        status = str(company.get("current_status", "")).lower()
        active = 1 if "active" in status else 0

        return (name_score, active)

    def _extract_profile_data(self, company_data: dict[str, Any]) -> dict[str, Any]:
        """Extract financial profile fields from company data."""
        company = company_data.get("company", {})

        # Parse incorporation date
        inc_date = company.get("incorporation_date")
        if inc_date:
            try:
                # OpenCorporates dates are typically YYYY-MM-DD
                parsed_date = datetime.strptime(inc_date[:10], "%Y-%m-%d")
                inc_date = parsed_date.isoformat()
            except Exception:
                inc_date = None

        return {
            "company_name": company.get("name"),
            "jurisdiction": company.get("jurisdiction_code"),
            "company_number": company.get("company_number"),
            "incorporation_date": inc_date,
            "company_status": company.get("current_status"),
            "company_type": company.get("company_type"),
            "registered_address": company.get("registered_address_in_full"),
            "updated_at": company.get("updated_at"),
        }

    @staticmethod
    def _status_band(status: str | None) -> str:
        """Map company status to scoring bands.

        MATCHED ON STEMS, not on whole words. The register writes the NOUN as often as the
        participle — Companies House says "Liquidation", not "Liquidated" — and a list of
        participles silently dropped every one of those to `registration_lapsed`, which reads as an
        administrative oversight rather than a company being wound up. That is the single most
        consequential misclassification this function can make: `entity_inactive` is what
        `continuity.py` maps to a `ceased` standing and a hard procurement gate, while
        `registration_lapsed` maps to `watch`.
        """
        s = str(status or "").lower()
        if "active" in s or "registered" in s:
            return "active_good_standing"
        # dissolv- : dissolved / dissolution   ·   liquidat- : liquidated / liquidation / in liquidation
        # wound up / winding up  ·  struck off / strike off
        if any(x in s for x in ["dissolv", "liquidat", "struck off", "strike off",
                                "closed", "wound up", "winding up"]):
            return "entity_inactive"
        if any(x in s for x in ["administration", "receivership", "insolven", "bankrupt"]):
            return "entity_inactive"
        return "registration_lapsed"
