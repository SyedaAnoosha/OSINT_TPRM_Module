"""Companies House collector — AUTHORITATIVE UK entity standing, corroborating GLEIF.

WHY. The register is honestly US-weighted and Business Stability rests on GLEIF plus Wikidata —
global, but neither is the UK government's own answer to "is this company real and current?". For
a UK vendor, Companies House is that answer: active / dissolved / liquidation, straight from the
statutory register, and it exposes filed accounts and the PSC (people-with-significant-control)
register that the FOCI roadmap needs.

LEGALITY — CLEARED (`methodology.md` Part 3). Open Government Licence, commercial use permitted,
free API key (600 requests / 5 min). Unset key is NOT an error: the collector returns `empty`,
lowering coverage and never posture, and the app runs unconfigured like every other keyed source.

ENTITY-LEVEL ONLY (§4.2). This reads company STATUS. The PSC register is people — natural persons —
and is deliberately NOT read here; the FOCI roadmap will consume only the corporate-ownership edges
of it, never a person record. The bright line does not move because the endpoint offers more.

CORROBORATION, NOT A NEW CATEGORY. Companies House maps onto the SAME `entity_status` /
`entity_existence` bands GLEIF uses, so when both resolve the same UK entity they combine at higher
confidence through the existing noisy-OR path — no engine change, no new signal.
"""

from __future__ import annotations

import re
from typing import Any

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_SEARCH = "https://api.company-information.service.gov.uk/search/companies"
_HOST = "api.company-information.service.gov.uk"
_CAT = "business_financial_stability"
_SUB = "legal_entity_status"

_SUFFIXES = re.compile(
    r"\b(plc|ltd|limited|llp|lp|holdings?|group|uk|company|co)\b", re.I)
_PUNCT = re.compile(r"[^a-z0-9 ]+")


class CompaniesHouseCollector(Collector):
    source = "companies_house"
    reliability = 0.95  # the UK's own statutory register — as authoritative as UK entity data gets
    timeout_s = 20.0
    http_attempts = 2
    http_backoff_s = 1.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        key = ctx.settings.companies_house_key.strip()
        if not key:
            return self.result(
                vendor, "empty",
                notes="TPRM_COMPANIES_HOUSE_KEY not set — Companies House not consulted (lowers "
                      "coverage, never posture). Free key at developer.company-information.service.gov.uk",
            )
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")
        query = vendor.name or vendor.ref

        # Companies House uses HTTP Basic auth with the API key as the username, empty password.
        resp = await self._get_with_retry(
            ctx, _SEARCH, limiter_key=_HOST,
            params={"q": query, "items_per_page": 20},
            auth=(key, ""),
        )
        if resp is None:
            return self.result(vendor, "error", notes="Companies House unavailable")
        if resp.status_code == 401:
            return self.result(vendor, "error", notes="Companies House rejected the API key (401)")
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"Companies House returned {resp.status_code}")

        try:
            items = resp.json().get("items") or []
        except ValueError:
            return self.result(vendor, "error", notes="Companies House response was not JSON")

        best = self._resolve(items, query)
        if best is None:
            # No confident UK match — expected for non-UK vendors. A coverage fact, not a risk fact.
            return self.result(
                vendor, "empty", raw={"query": query, "candidates": len(items)},
                notes="no confident Companies House match — expected for non-UK entities",
            )

        band = self._band(best.get("company_status"))
        raw: dict[str, Any] = {
            "query": query,
            "candidates": len(items),
            "company_number": best.get("company_number"),
            "title": best.get("title"),
            "company_status": best.get("company_status"),
            "company_type": best.get("company_type"),
            "date_of_creation": best.get("date_of_creation"),
            "address_snippet": best.get("address_snippet"),
            "ambiguous": self._exact_matches(items, query) > 1,
        }
        finding = Finding(
            source=self.source, signal="entity_status", subcategory=_SUB, category=_CAT,
            observed=f"{best.get('title')} — {best.get('company_status')} "
                     f"(UK {best.get('company_number')})",
            value={"band": band, "company_number": best.get("company_number"),
                   "company_status": best.get("company_status")},
            locator=f"Companies House {best.get('company_number')}",
            notes="ENTITY-level standing from the UK statutory register (OGL). Corroborates GLEIF "
                  "for UK entities. Company status only — the PSC register (natural persons) is "
                  "not read (§4.2).",
        )
        return self.result(vendor, "ok", raw=raw, findings=[finding],
                           source_version=str(best.get("company_status") or "live"))

    # --- entity resolution + banding ------------------------------------------------------

    def _resolve(self, items: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
        q = self._norm(query)
        scored = [(m, self._score(m, q)) for m in items if m.get("company_number")]
        strong = [(m, s) for m, s in scored if s[0] >= 2]
        if not strong:
            return None
        return max(strong, key=lambda p: p[1])[0]

    def _score(self, match: dict[str, Any], q: str) -> tuple:
        title = self._norm(match.get("title") or "")
        if title == q:
            name_score = 3
        elif q and (title.startswith(q) or q in title):
            name_score = 2
        elif q and set(q.split()) & set(title.split()):
            name_score = 1
        else:
            name_score = 0
        # Prefer an active company over a dissolved namesake when names tie.
        active = 1 if str(match.get("company_status") or "").lower() == "active" else 0
        return (name_score, active)

    def _exact_matches(self, items: list[dict[str, Any]], query: str) -> int:
        q = self._norm(query)
        return sum(1 for m in items if self._score(m, q)[0] == 3)

    @staticmethod
    def _norm(name: str) -> str:
        name = _PUNCT.sub(" ", (name or "").lower())
        name = _SUFFIXES.sub(" ", name)
        return " ".join(name.split())

    @staticmethod
    def _band(status: str | None) -> str:
        """Map Companies House status onto the EXISTING entity_status bands — no new bands, no
        scoring.yaml change, so it corroborates GLEIF instead of arguing with it."""
        s = str(status or "").strip().lower()
        if s == "active":
            return "active_good_standing"
        if s in {"dissolved", "liquidation", "receivership", "administration",
                 "insolvency-proceedings", "converted-closed", "closed"}:
            return "entity_inactive"
        return "registration_lapsed"
