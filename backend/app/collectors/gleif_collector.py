"""GLEIF collector — legal-entity standing, the EDGAR replacement for business stability.

WHY GLEIF, not EDGAR (source_assessment.md §12). EDGAR covers only US-*listed* companies —
terrible recall for the AU/private vendors an Australian client cares about, and it needs a
contact User-Agent to avoid a 403 ban. GLEIF (the Global LEI Foundation) publishes the Legal
Entity Identifier register: global, free, NO auth, and Level-1 data is CC0 / public domain
(commercial use permitted, no attribution required; the only ToU bar is not misrepresenting
the data as GLEIF-endorsed). All five test vendors resolve to an LEI record — the coverage
EDGAR could never give.

WHAT it tells us — ENTITY standing, not financials (§4.2 no natural persons; this is entity-
level only). A live business is an ACTIVE entity whose LEI registration is ISSUED (renewed on
time). The strong signals GLEIF authoritatively carries:
  * entityStatus INACTIVE  -> the legal entity has ceased (merger/dissolution) — real distress.
  * registrationStatus RETIRED/ANNULLED/MERGED -> LEI closed; entity gone or absorbed.
  * registrationStatus LAPSED -> LEI not renewed — a mild governance/attentiveness signal.
  * ACTIVE + ISSUED -> in good administrative standing (benign, POSITIVE observation).
Financial-distress (going concern), litigation, and ownership-CHANGE remain HELD: no free
authoritative source, and change-detection needs history GLEIF's snapshot can't give (§5.9).

Entity resolution is name-based and therefore coarse (GLEIF has no domain index): we rank the
returned records and pick the best corporate match, recording the candidate count so an
ambiguous pick is visible, never silent.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_API = "https://api.gleif.org/api/v1/lei-records"
_CAT = "business_financial_stability"
_SUB = "legal_entity_status"
# Corporate-form suffixes stripped before name comparison (entity resolution).
_SUFFIXES = re.compile(
    r"\b(inc|incorporated|llc|llp|ltd|limited|pty|corp|corporation|plc|gmbh|ag|sa|"
    r"nv|bv|oy|ab|as|group|holding|holdings|co|company|technologies|technology)\b",
    re.I,
)
_PUNCT = re.compile(r"[^a-z0-9 ]+")


class GleifCollector(Collector):
    source = "gleif"
    reliability = 0.9  # authoritative public register (source_assessment.md §12)
    timeout_s = 25.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")
        query = vendor.name or vendor.ref

        await ctx.limiter.acquire("api.gleif.org")
        try:
            resp = await ctx.http.get(
                _API,
                params={"filter[entity.legalName]": query, "page[size]": 15},
                headers={"Accept": "application/vnd.api+json"},
            )
        except httpx.HTTPError as exc:
            return self.result(vendor, "error", notes=f"GLEIF fetch failed: {type(exc).__name__}: {exc}")
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"GLEIF returned {resp.status_code}")

        records = [self._summarise(r) for r in resp.json().get("data", [])]
        records = [r for r in records if r.get("lei")]
        if not records:
            # No LEI on the register for this name — a genuine per-vendor gap (some small
            # vendors have no LEI). Lowers confidence, never risk (the MYOB philosophy).
            return self.result(
                vendor, "empty", raw={"query": query, "candidates": 0},
                notes="no LEI record for this entity name (confidence, not risk)",
            )

        best = self._resolve(records, query)
        band = self._band(best)
        ambiguous = self._strong_matches(records, query) > 1
        raw: dict[str, Any] = {
            "query": query, "candidates": len(records),
            "resolved": best,
            "other_candidates": [r for r in records if r["lei"] != best["lei"]][:10],
            # Attribution quality, surfaced for the entity-resolution assessor rather than left
            # buried in a note: how close the winning legal name was, and whether more than one
            # record matched strongly (i.e. "which of these companies did you mean?").
            "ambiguous": ambiguous,
            "name_match": self._match_score(best, self._norm(query))[0],
            "strong_matches": self._strong_matches(records, query),
            "exact_matches": self._exact_matches(records, query),
        }
        finding = Finding(
            source=self.source, signal="entity_status", subcategory=_SUB, category=_CAT,
            observed=f"{best['legalName']} — {best['entityStatus']}/{best['regStatus']}",
            value={"band": band, "lei": best["lei"], "jurisdiction": best["jurisdiction"],
                   "entity_status": best["entityStatus"], "registration_status": best["regStatus"]},
            locator=f"GLEIF LEI {best['lei']}",
            notes=("ENTITY-level standing; " + ("MULTIPLE strong name matches — review attribution"
                   if ambiguous else "single best name match")),
        )
        return self.result(vendor, "ok", raw=raw, findings=[finding], source_version="live")

    # --- entity resolution (name-based, coarse — recorded, never hidden) ---

    def _resolve(self, records: list[dict[str, Any]], query: str) -> dict[str, Any]:
        """Pick the best corporate match: closest name, preferring live (ISSUED+ACTIVE) records."""
        q = self._norm(query)
        return max(records, key=lambda r: self._match_score(r, q))

    def _match_score(self, rec: dict[str, Any], q: str) -> tuple:
        legal = self._norm(rec.get("legalName") or "")
        if legal == q:
            name_score = 3
        elif q and (legal.startswith(q) or q in legal):
            name_score = 2
        elif q and set(q.split()) & set(legal.split()):
            name_score = 1
        else:
            name_score = 0
        issued = 1 if rec.get("regStatus") == "ISSUED" else 0
        active = 1 if rec.get("entityStatus") == "ACTIVE" else 0
        # Prefer strong name match first, then a live registration, then a shorter (less
        # sub-entity-ish) legal name as a tiebreak.
        return (name_score, issued, active, -len(legal))

    def _strong_matches(self, records: list[dict[str, Any]], query: str) -> int:
        q = self._norm(query)
        return sum(1 for r in records if self._match_score(r, q)[0] >= 2)

    def _exact_matches(self, records: list[dict[str, Any]], query: str) -> int:
        """How many entities share the query's legal name EXACTLY (suffixes normalised away).

        This, not `_strong_matches`, is the real ambiguity signal. "Snowflake" strong-matches 15
        records — "Snowflake Capital", "Snowflake Holdings" and so on — but exactly ONE of them
        normalises to `snowflake`, so there is no doubt which company was meant. Counting merely
        *strong* matches would block a household name for having a common word in it.
        """
        q = self._norm(query)
        return sum(1 for r in records if self._match_score(r, q)[0] == 3)

    @staticmethod
    def _norm(name: str) -> str:
        name = _PUNCT.sub(" ", name.lower())
        name = _SUFFIXES.sub(" ", name)
        return " ".join(name.split())

    @staticmethod
    def _band(rec: dict[str, Any]) -> str:
        if rec.get("entityStatus") == "INACTIVE":
            return "entity_inactive"
        reg = rec.get("regStatus")
        if reg in {"RETIRED", "ANNULLED", "MERGED", "DUPLICATE"}:
            return "registration_retired"
        if reg == "LAPSED":
            return "registration_lapsed"
        return "active_good_standing"

    @staticmethod
    def _summarise(rec: dict[str, Any]) -> dict[str, Any]:
        a = rec.get("attributes", {})
        ent = a.get("entity", {})
        reg = a.get("registration", {})
        return {
            "lei": a.get("lei"),
            "legalName": (ent.get("legalName") or {}).get("name"),
            "jurisdiction": ent.get("jurisdiction"),
            "entityStatus": ent.get("status"),
            "regStatus": reg.get("status"),
        }
