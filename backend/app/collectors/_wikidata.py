"""Shared Wikidata primitives — search, entity fetch, claim reading, domain matching.

WHY SHARED. Two collectors read Wikidata for different purposes: `wikidata` corroborates entity
STANDING (a scored signal), `firmographics` reads size/industry/ownership (never scored). They
must agree on ONE thing above all — **which entity they are talking about**. If the profile
collector resolved "Slack" to a different QID than the standing collector, a scorecard would show
one company's industry beside another company's status, and nothing on the card would say so.

So entity selection lives here, once: search by name, then keep only a candidate whose official
website (P856) matches the vendor's registrable domain. No domain match -> no entity, for both
callers. A wrong match is worse than no match, and it is worse still if only one of two collectors
makes it.
"""

from __future__ import annotations

import re
from typing import Any

from ..models import Vendor
from .base import Collector, CollectorContext

SEARCH_URL = "https://www.wikidata.org/w/api.php"
ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
LIMITER_KEY = "www.wikidata.org"
CANDIDATES = 7  # how many name hits to inspect for a domain match

P_WEBSITE = "P856"     # official website — the identity anchor
P_DISSOLVED = "P576"   # dissolved, abolished or demolished date
P_INDUSTRY = "P452"
P_EMPLOYEES = "P1128"
P_REVENUE = "P2139"
P_EXCHANGE = "P414"    # stock exchange — presence implies listed
P_COUNTRY = "P17"      # country (of the LEGAL entity — can be an incorporation domicile)
P_HEADQUARTERS = "P159"  # headquarters location — the OPERATIONAL home, resolved to its own country
P_INCEPTION = "P571"
P_PARENT = "P749"      # parent organization — a corporate entity, never a person

_HOST = re.compile(r"https?://([^/]+)", re.I)
_WWW = re.compile(r"^www\.", re.I)


def host_of(url: str) -> str:
    m = _HOST.match(url or "")
    return m.group(1) if m else ""


def registrable(host_or_domain: str) -> str:
    """Best-effort registrable domain: last two labels, lower-cased, www-stripped.

    Deliberately simple (no PSL): the vendor domains in scope are ordinary second-level domains,
    and this only ever gates an EXACT equality between two hosts, so a coarse rule is safe — a
    mismatch just means 'no corroboration', never a wrong match.
    """
    host = _WWW.sub("", (host_or_domain or "").strip().lower()).rstrip("/")
    parts = [p for p in host.split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def claim_values(entity: dict[str, Any], pid: str) -> list[Any]:
    """Every datavalue for one property. Wikidata claims are lists; so is the answer."""
    out: list[Any] = []
    for claim in entity.get("claims", {}).get(pid, []):
        dv = claim.get("mainsnak", {}).get("datavalue", {})
        if "value" in dv:
            out.append(dv["value"])
    return out


def claim_ids(entity: dict[str, Any], pid: str) -> list[str]:
    """QIDs for an entity-valued property (industry, parent, country, exchange)."""
    return [v["id"] for v in claim_values(entity, pid)
            if isinstance(v, dict) and isinstance(v.get("id"), str)]


P_POINT_IN_TIME = "P585"


def claim_amount(entity: dict[str, Any], pid: str) -> tuple[float, str, str | None] | None:
    """The MOST RECENT quantity claim, as (amount, unit-QID, as-of date).

    WHY THIS IS NOT "TAKE THE FIRST ONE", AND HOW WE FOUND OUT. Wikidata keeps quantity properties
    as a TIME SERIES: one claim per reported figure, each qualified with `P585 point in time`.
    Atlassian's `P1128 employees` carries ten claims spanning 2012-2022. Reading the first returned
    1,100 — a figure from **March 2015**, eleven years stale, displayed on a scorecard as though it
    were current. It also decides a size band, and therefore which peer group a vendor is compared
    against, so a decade-old headcount is not a cosmetic error.

    So: skip `deprecated` claims, prefer the latest `P585`, and RETURN THE DATE with the number.
    An undated figure is shown as-is; a dated one can be shown as "8,179 (as at Apr 2022)", which
    is the difference between a reader trusting a stale number and a reader seeing that it is old.
    """
    best: tuple[float, str, str | None] | None = None
    best_when = ""
    for claim in entity.get("claims", {}).get(pid, []):
        if claim.get("rank") == "deprecated":
            continue
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if not isinstance(value, dict) or "amount" not in value:
            continue
        try:
            amount = float(str(value["amount"]).lstrip("+"))
        except (TypeError, ValueError):
            continue
        unit = str(value.get("unit", "")).rsplit("/", 1)[-1]

        when = ""
        for qualifier in claim.get("qualifiers", {}).get(P_POINT_IN_TIME, []):
            time = qualifier.get("datavalue", {}).get("value", {}).get("time")
            if isinstance(time, str):
                # '+2022-04-28T00:00:00Z' -> '2022-04-28'. Wikidata writes unknown month/day as
                # '00', which sorts before any real date — correct for "latest wins".
                when = time.lstrip("+")[:10]
                break

        # Undated claims lose to any dated one: a figure someone bothered to date is the figure
        # they meant to be read as current.
        if best is None or when > best_when:
            best, best_when = (amount, unit, when or None), when
    return best


def claim_time(entity: dict[str, Any], pid: str) -> str | None:
    """A time claim's ISO-ish string ('+1985-10-02T00:00:00Z' -> '1985-10-02')."""
    for v in claim_values(entity, pid):
        if isinstance(v, dict) and isinstance(v.get("time"), str):
            return v["time"].lstrip("+")[:10]
    return None


def label_of(entity: dict[str, Any], lang: str = "en") -> str | None:
    labels = entity.get("labels", {})
    entry = labels.get(lang) or next(iter(labels.values()), None)
    return entry.get("value") if isinstance(entry, dict) else None


async def search(collector: Collector, ctx: CollectorContext, query: str) -> list[dict[str, Any]] | None:
    """Name search. Returns None on transport failure so the caller can report `error`, not `empty` —
    'the source was unreachable' and 'the source had nothing' are different facts about a vendor."""
    resp = await collector._get_with_retry(
        ctx, SEARCH_URL, limiter_key=LIMITER_KEY,
        params={"action": "wbsearchentities", "search": query, "language": "en",
                "type": "item", "limit": CANDIDATES, "format": "json"},
    )
    if resp is None or resp.status_code != 200:
        return None
    try:
        return list(resp.json().get("search", []))
    except (ValueError, AttributeError):
        return None


async def entity(collector: Collector, ctx: CollectorContext, qid: str) -> dict[str, Any] | None:
    resp = await collector._get_with_retry(ctx, ENTITY_URL.format(qid=qid), limiter_key=LIMITER_KEY)
    if resp is None or resp.status_code != 200:
        return None
    try:
        return resp.json().get("entities", {}).get(qid)
    except (ValueError, AttributeError):
        return None


async def resolve_by_domain(
    collector: Collector, ctx: CollectorContext, vendor: Vendor,
) -> tuple[dict[str, Any] | None, str, int]:
    """Find the Wikidata entity whose official website matches the vendor's domain.

    Returns `(entity_or_None, qid, candidates_inspected)`. **The domain match is the whole point:**
    a bare name search is noisy — "Xero" returns a film, "Cochlear" returns the implant — so an
    entity is accepted only when P856 resolves to the same registrable domain we are assessing.
    Without that anchor, both callers emit nothing rather than describing a stranger.
    """
    if not vendor.domain:
        return None, "", 0
    target = registrable(vendor.domain)
    hits = await search(collector, ctx, vendor.name or vendor.ref)
    if hits is None:
        return None, "", -1  # -1 distinguishes "search failed" from "searched, found nothing"

    inspected = 0
    for hit in hits[:CANDIDATES]:
        qid = hit.get("id")
        if not qid:
            continue
        ent = await entity(collector, ctx, qid)
        if ent is None:
            continue
        inspected += 1
        sites = claim_values(ent, P_WEBSITE)
        if any(registrable(host_of(s)) == target for s in sites if isinstance(s, str)):
            return ent, qid, inspected
    return None, "", inspected
