"""ABN Lookup collector — AUTHORITATIVE Australian entity status. The source that solves MYOB.

WHY. The register is honestly US-weighted (`methodology.md` §7.2) and Business Stability rests on
GLEIF plus Wikidata — global, but neither is the Australian government's own answer to "is this
company real and current?". For an Australian TPRM product assessing Australian vendors, the ABR
is that answer: Active / Cancelled, straight from the Commonwealth register.

LEGALITY — CLEAR-CONDITIONAL (`methodology.md` Part 3). The ABN Lookup Web Services Agreement
permits providing "relevant extracts of the ABN Lookup Web Services to third parties" at your own
risk, sets **no commercial bar** and **no bulk-harvest bar** (we do targeted per-vendor lookups,
never bulk extraction), and requires only that we **not imply Commonwealth endorsement** — hence
the notes on every finding. It needs a free registration GUID, which is the same identify-yourself
posture several other cleared sources take.

**Unset key is not an error.** With no `TPRM_ABN_GUID` the collector returns `empty` — the source
was simply not consulted, which lowers coverage and therefore confidence, and never touches
posture. The app runs unconfigured, exactly like the other keyed collectors.

ANZSIC IS NOT AVAILABLE HERE, and this matters because it is the obvious thing to expect. The ABR
holds an industry classification for every ABN, but it is **non-public data released only to
eligible government agencies** — the public JSON services do not carry it (verified 24 Jul 2026).
So this collector supplies STATUS, and sector classification falls back to the Wikidata label
mapping in `industry.py`. Recorded here rather than discovered later by whoever wonders why AU
vendors have no ANZSIC code.

ENTITY-LEVEL ONLY (§4.2). ABN Lookup exposes entity and trading names. Associates and other
natural-person data are not read, and would not be read if the endpoint offered them.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_NAMES = "https://abr.business.gov.au/json/MatchingNames.aspx"
_DETAILS = "https://abr.business.gov.au/json/AbnDetails.aspx"
_HOST = "abr.business.gov.au"
_CAT = "business_financial_stability"
_SUB = "legal_entity_status"

# The JSON services answer as JSONP — `callback({...})` — even when no callback is named.
_JSONP = re.compile(r"^[^(]*\((.*)\)[^)]*$", re.S)

# Corporate-form suffixes stripped before comparing names, mirroring the GLEIF matcher so the two
# registers agree on what counts as the "same" name.
_SUFFIXES = re.compile(
    r"\b(pty|ltd|limited|inc|incorporated|llc|corp|corporation|plc|"
    r"group|holdings?|co|company|australia|australian)\b", re.I,
)
_PUNCT = re.compile(r"[^a-z0-9 ]+")


class AbnCollector(Collector):
    source = "abn"
    reliability = 0.95  # the Commonwealth's own register — as authoritative as AU entity data gets
    timeout_s = 20.0
    http_attempts = 2
    http_backoff_s = 1.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        guid = ctx.settings.abn_guid.strip()
        if not guid:
            return self.result(
                vendor, "empty",
                notes="TPRM_ABN_GUID not set — ABR not consulted (lowers coverage, never posture). "
                      "Register free at abr.business.gov.au/Tools/WebServices",
            )
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        query = vendor.name or vendor.ref
        matches = await self._matching_names(ctx, query, guid)
        if matches is None:
            return self.result(vendor, "error", notes="ABN Lookup unavailable")

        best = self._resolve(matches, query)
        if best is None:
            # Genuinely common and genuinely fine: a non-Australian vendor has no ABN. That is a
            # coverage fact about the register, not a risk fact about the vendor.
            return self.result(
                vendor, "empty", raw={"query": query, "candidates": len(matches)},
                notes="no matching current ABN — expected for non-Australian entities",
            )

        detail = await self._abn_details(ctx, best["abn"], guid)
        if detail is None:
            return self.result(vendor, "error", notes=f"ABN detail fetch failed for {best['abn']}")

        band = self._band(detail)
        raw: dict[str, Any] = {
            "query": query,
            "candidates": len(matches),
            "resolved": best,
            "abn": detail.get("Abn"),
            "abn_status": detail.get("AbnStatus"),
            "entity_name": detail.get("EntityName"),
            "entity_type": detail.get("EntityTypeName"),
            "gst_registered": bool(detail.get("Gst")),
            "state": detail.get("AddressState"),
            "postcode": detail.get("AddressPostcode"),
            "status_from": detail.get("AbnStatusEffectiveFrom"),
            "business_names": (detail.get("BusinessName") or [])[:10],
            "ambiguous": self._exact_matches(matches, query) > 1,
            # Stated in the payload, not only in the docstring, so an auditor reading the receipt
            # sees why an AU vendor carries no industry code from the Commonwealth register.
            "anzsic_available": False,
            "anzsic_note": "ANZSIC is non-public ABR data (government agencies only); "
                           "sector is derived from other sources",
        }
        finding = Finding(
            source=self.source, signal="entity_status", subcategory=_SUB, category=_CAT,
            observed=f"{detail.get('EntityName')} — ABN {detail.get('Abn')} {detail.get('AbnStatus')}",
            value={"band": band, "abn": detail.get("Abn"),
                   "abn_status": detail.get("AbnStatus"),
                   "entity_type": detail.get("EntityTypeName"),
                   "state": detail.get("AddressState")},
            locator=f"ABN {detail.get('Abn')}",
            notes="ENTITY-level standing from the Australian Business Register. Corroborates GLEIF "
                  "for AU entities. Sourced from ABN Lookup; not endorsed by the Commonwealth.",
        )
        return self.result(vendor, "ok", raw=raw, findings=[finding],
                           source_version=str(detail.get("AbnStatusEffectiveFrom") or "live"))

    # --- fetch ---------------------------------------------------------------------------

    async def _matching_names(self, ctx: CollectorContext, name: str,
                              guid: str) -> list[dict[str, Any]] | None:
        resp = await self._get_with_retry(
            ctx, _NAMES, limiter_key=_HOST,
            params={"name": name, "maxResults": 20, "guid": guid},
        )
        payload = self._parse(resp)
        if payload is None:
            return None
        names = payload.get("Names")
        return names if isinstance(names, list) else []

    async def _abn_details(self, ctx: CollectorContext, abn: str,
                           guid: str) -> dict[str, Any] | None:
        resp = await self._get_with_retry(
            ctx, _DETAILS, limiter_key=_HOST, params={"abn": abn, "guid": guid},
        )
        return self._parse(resp)

    @staticmethod
    def _parse(resp: Any) -> dict[str, Any] | None:
        """Unwrap the JSONP envelope. Returns None on any transport or shape failure — the caller
        turns that into `error`, keeping 'unreachable' distinct from 'nothing found'."""
        if resp is None or resp.status_code != 200:
            return None
        body = (resp.text or "").strip()
        m = _JSONP.match(body)
        if m:
            body = m.group(1)
        try:
            data = json.loads(body)
        except ValueError:
            return None
        if not isinstance(data, dict) or data.get("Message"):
            # The service reports errors in-band with HTTP 200 and a populated `Message`.
            return None
        return data

    # --- entity resolution ---------------------------------------------------------------

    def _resolve(self, matches: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
        """Best CURRENT match, or None. Never returns a weak match: attaching an Australian
        registration to the wrong company is exactly the failure the entity gate exists to stop."""
        q = self._norm(query)
        scored = [
            ({"abn": m.get("Abn"), "name": m.get("Name"), "name_type": m.get("NameType"),
              "state": m.get("State"), "postcode": m.get("Postcode"),
              "is_current": bool(m.get("IsCurrent"))}, self._score(m, q))
            for m in matches if m.get("Abn")
        ]
        strong = [(rec, s) for rec, s in scored if s[0] >= 2 and rec["is_current"]]
        if not strong:
            return None
        return max(strong, key=lambda p: p[1])[0]

    def _score(self, match: dict[str, Any], q: str) -> tuple:
        name = self._norm(match.get("Name") or "")
        if name == q:
            name_score = 3
        elif q and (name.startswith(q) or q in name):
            name_score = 2
        elif q and set(q.split()) & set(name.split()):
            name_score = 1
        else:
            name_score = 0
        # ABN Lookup's own relevance score breaks ties between equally-good name matches.
        return (name_score, 1 if match.get("IsCurrent") else 0, float(match.get("Score") or 0))

    def _exact_matches(self, matches: list[dict[str, Any]], query: str) -> int:
        q = self._norm(query)
        return sum(1 for m in matches if self._score(m, q)[0] == 3 and m.get("IsCurrent"))

    @staticmethod
    def _norm(name: str) -> str:
        name = _PUNCT.sub(" ", (name or "").lower())
        name = _SUFFIXES.sub(" ", name)
        return " ".join(name.split())

    @staticmethod
    def _band(detail: dict[str, Any]) -> str:
        """Map ABR status onto the EXISTING `entity_status` bands — no new bands, no scoring.yaml
        change. A cancelled ABN is the same fact GLEIF calls an inactive entity, so it lands in the
        same band and the two registers corroborate instead of arguing."""
        status = str(detail.get("AbnStatus") or "").strip().lower()
        if status.startswith("active"):
            return "active_good_standing"
        if status.startswith("cancel"):
            return "entity_inactive"
        return "registration_lapsed"
