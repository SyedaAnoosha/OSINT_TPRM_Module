"""Firmographics collector — WHO the vendor is: industry, size, ownership, country, age.

WHY THIS EXISTS. Until now the system could score a vendor without knowing what it does or how
big it is. That is fine for an absolute grade and fatal for a comparison: you cannot pick a peer
group for a company you have not classified. Sector and size are the inputs to the peer cohort
(`benchmark.py`), and the industry severity profile keys off sector too.

THE RULE THIS COLLECTOR HOLDS — IT EMITS NO FINDINGS. Not one. A finding is the unit that becomes
a penalty, so a collector that emitted them would let revenue or headcount move a score, and the
size bias in methodology §7.3 ("coverage tracks company size, not company risk") would re-enter one
level up. It returns `raw` only: provenance is persisted to the evidence store exactly like every
other source, `app/profile.py` reads it, and the scoring engine never sees it. Zero findings also
means zero effect on the CONFIDENCE axis — a thin profile weakens the COMPARISON, not the score.

LEGALITY. Wikidata structured data is CC0 / public domain — no attribution, no commercial or
automated-access bar (`source_assessment.md` §13). The one hard condition is Wikimedia's robot
policy: a descriptive, contact-bearing User-Agent, which the shared client already sends.

ENTITY-LEVEL ONLY (§4.2). `P749 parent organization` is a corporate parent. Founders, directors,
officers and beneficial owners are natural persons and are not read here — not because Wikidata
withholds them (it does not), but because the bright line does not move for convenience.
"""

from __future__ import annotations

from typing import Any

from ..models import CollectorResult, Vendor
from . import _wikidata as wd
from .base import Collector, CollectorContext

# Wikidata unit QIDs for the currencies we bother to name. An unrecognised unit is reported as the
# bare QID rather than silently dropped — a revenue figure whose currency we cannot state is not
# usable for a size band, and saying so is better than implying dollars.
_CURRENCIES = {
    "Q4917": "USD", "Q4916": "EUR", "Q25224": "GBP", "Q259502": "AUD",
    "Q1104069": "CAD", "Q1811": "NZD", "Q41509": "SGD", "Q8146": "INR", "Q8867": "JPY",
}


class FirmographicsCollector(Collector):
    source = "firmographics"
    # Community-edited, but every emission is anchored to a domain-verified entity, and nothing
    # here can move a score — the downside of a stale employee count is a slightly wrong peer
    # group, which the cohort's published `n` and the profile's completeness both expose.
    reliability = 0.7
    timeout_s = 25.0
    http_attempts = 2
    http_backoff_s = 1.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")
        if not vendor.domain:
            # Resolution here is domain-anchored; without a domain we will not guess an entity.
            return self.result(vendor, "empty", notes="no domain — cannot domain-verify an entity")

        entity, qid, inspected = await wd.resolve_by_domain(self, ctx, vendor)
        if inspected == -1:
            return self.result(vendor, "error", notes="Wikidata search unavailable")
        if entity is None:
            return self.result(
                vendor, "empty",
                raw={"query": vendor.name or vendor.ref, "candidates_inspected": inspected},
                notes="no domain-verified Wikidata entity — profile left unpopulated rather than "
                      "attached to a company we cannot prove is this one",
            )

        raw: dict[str, Any] = {
            "qid": qid,
            "label": wd.label_of(entity),
            "candidates_inspected": inspected,
            "industry": await self._labels(ctx, wd.claim_ids(entity, wd.P_INDUSTRY)),
            "country": await self._labels(ctx, wd.claim_ids(entity, wd.P_COUNTRY)),
            "parent": await self._labels(ctx, wd.claim_ids(entity, wd.P_PARENT)),
            "listed_on": await self._labels(ctx, wd.claim_ids(entity, wd.P_EXCHANGE)),
            "employees": None,
            "employees_as_of": None,
            "revenue": None,
            "revenue_currency": None,
            "revenue_as_of": None,
            "inception": wd.claim_time(entity, wd.P_INCEPTION),
        }

        # Both are TIME SERIES on Wikidata, so the as-of date travels with the figure. Without it a
        # scorecard shows a 2015 headcount as though it were today's — see `_wikidata.claim_amount`.
        employees = wd.claim_amount(entity, wd.P_EMPLOYEES)
        if employees:
            raw["employees"] = int(employees[0])
            raw["employees_as_of"] = employees[2]

        revenue = wd.claim_amount(entity, wd.P_REVENUE)
        if revenue:
            amount, unit, as_of = revenue
            raw["revenue"] = amount
            raw["revenue_currency"] = _CURRENCIES.get(unit, unit or None)
            raw["revenue_as_of"] = as_of

        # HEADQUARTERS country — the OPERATIONAL home, which is what a reader means by "where is this
        # vendor" and what its regulatory regime tracks. It differs from the legal `country`/P17 for a
        # re-domiciled company (Atlassian: HQ Sydney, but incorporated in the US since 2022), so it is
        # resolved separately (P159 location → that location's P17) and preferred in `profile.py`.
        hq_ids = wd.claim_ids(entity, wd.P_HEADQUARTERS)
        if hq_ids:
            hq_entity = await wd.entity(self, ctx, hq_ids[0])
            if hq_entity:
                raw["hq_country"] = await self._labels(ctx, wd.claim_ids(hq_entity, wd.P_COUNTRY))

        # Ownership is INFERRED, and the inference is narrow and stated: an entity listed on a
        # stock exchange is public. The absence of a P414 claim is NOT evidence of private
        # ownership — Wikidata is incomplete — so it reads 'unknown', never 'private'.
        raw["ownership"] = "listed" if raw["listed_on"] else "unknown"

        return self.result(
            vendor, "ok", raw=raw, source_version="live",
            notes="firmographic context only — NO findings emitted, so this cannot move the "
                  "posture or the confidence axis (methodology §7.3)",
        )

    async def _labels(self, ctx: CollectorContext, qids: list[str]) -> list[str]:
        """Resolve entity-valued claims to English labels, capped at three.

        Capped because a large company lists a dozen industries and the tail is noise; the sector
        mapper reads them in order and takes the first that maps, so three is enough to classify
        and few enough not to hammer a free API.
        """
        out: list[str] = []
        for qid in qids[:3]:
            ent = await wd.entity(self, ctx, qid)
            label = wd.label_of(ent) if ent else None
            if label:
                out.append(label)
        return out
