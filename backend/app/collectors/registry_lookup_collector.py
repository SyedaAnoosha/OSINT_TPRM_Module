"""Registry Lookup collector — Backup global registry data source.

WHY. Registry Lookup provides access to 521M entities across 309 jurisdictions
as a backup when primary collectors fail. For Business Stability assessment,
this provides redundancy for incorporation dates and company status.

LEGALITY — CLEARED (`methodology.md` Part 3). Freemium API with 5,000 free calls/month.
Commercial use permitted. Unset API key -> collector returns `empty`, lowering coverage.

ENTITY-LEVEL ONLY (§4.2). This reads corporate entity data only. No natural-person data.

SIGNAL MAPPING. Findings land in `business_financial_stability` at `entity_status` bands.
Used as fallback when primary jurisdiction-specific collectors are unavailable.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_SEARCH = "https://api.registrylookup.com/v1/search"
_COMPANY = "https://api.registrylookup.com/v1/company/"
_HOST = "api.registrylookup.com"
_CAT = "business_financial_stability"
_SUB = "global_registry_backup"

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


class RegistryLookupCollector(Collector):
    source = "registry_lookup"
    reliability = 0.80  # Backup source with varying data quality
    timeout_s = 20.0
    http_attempts = 2
    http_backoff_s = 1.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        query = vendor.name or vendor.ref
        api_key = ctx.settings.registry_lookup_key.strip() if hasattr(ctx.settings, 'registry_lookup_key') else ""

        # Build search URL
        search_url = f"{_SEARCH}?q={quote(query)}&limit=5"
        if api_key:
            search_url += f"&api_key={api_key}"

        resp = await self._get_with_retry(ctx, search_url, limiter_key=_HOST)
        if resp is None:
            return self.result(vendor, "error", notes="Registry Lookup unavailable")
        if resp.status_code == 401:
            return self.result(vendor, "error", notes="Registry Lookup rejected the API key (401)")
        if resp.status_code == 429:
            return self.result(vendor, "empty", notes="Registry Lookup rate limit exceeded (429)")
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"Registry Lookup returned {resp.status_code}")

        try:
            data = resp.json()
            results = data.get("results", [])
        except Exception:
            return self.result(vendor, "error", notes="Failed to parse Registry Lookup response")

        if not results:
            return self.result(
                vendor, "empty", raw={"query": query, "companies_found": 0},
                notes="No Registry Lookup match found for this vendor",
            )

        # Resolve best match
        best = self._resolve(results, query)
        if best is None:
            return self.result(
                vendor, "empty", raw={"query": query, "candidates": len(results)},
                notes="No confident Registry Lookup match",
            )

        # Extract data
        profile_data = self._extract_profile_data(best)

        findings = []
        if profile_data["incorporation_date"]:
            findings.append(Finding(
                source=self.source, signal="incorporation_date", subcategory=_SUB, category=_CAT,
                observed=f"Incorporated: {profile_data['incorporation_date']}",
                value={"incorporation_date": profile_data["incorporation_date"]},
                locator=profile_data.get("source_url"),
                notes="Incorporation date from Registry Lookup (backup source).",
            ))

        if profile_data["company_status"]:
            band = self._status_band(profile_data["company_status"])
            findings.append(Finding(
                source=self.source, signal="company_status", subcategory=_SUB, category=_CAT,
                observed=f"Status: {profile_data['company_status']}",
                value={"band": band, "company_status": profile_data["company_status"]},
                locator=profile_data.get("source_url"),
                notes="Company status from Registry Lookup (backup source).",
            ))

        raw = {
            "query": query,
            "company_name": profile_data.get("company_name"),
            "jurisdiction": profile_data.get("jurisdiction"),
            "company_number": profile_data.get("company_number"),
            "incorporation_date": profile_data.get("incorporation_date"),
            "company_status": profile_data.get("company_status"),
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
        name = _normalize_name(result.get("name") or "")
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
        status = str(result.get("status", "")).lower()
        active = 1 if "active" in status else 0

        return (name_score, active)

    def _extract_profile_data(self, result: dict[str, Any]) -> dict[str, Any]:
        """Extract financial profile fields from company data."""
        # Parse incorporation date
        inc_date = result.get("incorporation_date")
        if inc_date:
            try:
                parsed_date = datetime.strptime(inc_date[:10], "%Y-%m-%d")
                inc_date = parsed_date.isoformat()
            except Exception:
                inc_date = None

        return {
            "company_name": result.get("name"),
            "jurisdiction": result.get("country"),
            "company_number": result.get("registration_number"),
            "incorporation_date": inc_date,
            "company_status": result.get("status"),
            "source_url": result.get("source_url"),
            "updated_at": result.get("last_updated"),
        }

    @staticmethod
    def _status_band(status: str | None) -> str:
        """Map company status to scoring bands.

        Stems, not whole words — see the matching note in `open_corporates_collector`. A register
        that writes "Liquidation" rather than "Liquidated" must not fall through to
        `registration_lapsed`, which Continuity reads as a `watch` rather than a `ceased`.
        """
        s = str(status or "").lower()
        if "active" in s or "registered" in s:
            return "active_good_standing"
        if any(x in s for x in ["dissolv", "liquidat", "struck off", "strike off",
                                "closed", "wound up", "winding up"]):
            return "entity_inactive"
        if any(x in s for x in ["administration", "receivership", "insolven", "bankrupt"]):
            return "entity_inactive"
        return "registration_lapsed"
