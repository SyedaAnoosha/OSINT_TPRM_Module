"""Phase 5 — free keyed sources: OTX (CT redundancy) and Companies House (UK registry).

Both need a free API key, so the load-bearing property is the same one every keyed source in this
system holds: WITHOUT the key they return `empty`, never `error`, so the app runs unconfigured and
an operator's missing key lowers coverage rather than breaking a score. The parse tests then prove
that WITH a response, each maps onto the existing bands correctly — no live key required.
"""

from __future__ import annotations

import httpx

from app.collectors import all_collectors, get_collector
from app.collectors.base import CollectorContext
from app.config import Settings
from app.models import Vendor
from app.ratelimit import RateLimiter


def _ctx(**settings_over) -> CollectorContext:
    base = {"database_url": "postgresql://u:p@h/db"}
    base.update(settings_over)
    return CollectorContext(settings=Settings(**base), limiter=RateLimiter(), http=None)


def _ctx_with_http(handler, **settings_over) -> CollectorContext:
    base = {"database_url": "postgresql://u:p@h/db"}
    base.update(settings_over)
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    return CollectorContext(settings=Settings(**base), limiter=RateLimiter(), http=http)


# --------------------------------------------------------------------- registration


def test_both_collectors_are_registered():
    sources = {c.source for c in all_collectors()}
    assert {"otx", "companies_house"} <= sources


# --------------------------------------------------------------------- graceful skip


async def test_otx_returns_empty_without_a_key():
    otx = get_collector("otx")
    result = await otx.collect(Vendor(ref="acme", domain="acme.com"), _ctx(otx_api_key=""))
    assert result.status == "empty"
    assert "TPRM_OTX_API_KEY" in result.notes
    assert result.findings == []          # empty lowers coverage, never posture


async def test_companies_house_returns_empty_without_a_key():
    ch = get_collector("companies_house")
    result = await ch.collect(Vendor(ref="acme", name="Acme"), _ctx(companies_house_key=""))
    assert result.status == "empty"
    assert "TPRM_COMPANIES_HOUSE_KEY" in result.notes
    assert result.findings == []


# --------------------------------------------------------------------- OTX parsing


async def test_otx_enumerates_in_scope_subdomains_only():
    """Passive DNS can return hosts sharing an IP that are NOT the vendor's — those must not inflate
    the footprint. Only names under the vendor's own domain count."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"passive_dns": [
            {"hostname": "www.acme.com"},
            {"hostname": "api.acme.com"},
            {"hostname": "mail.acme.com"},
            {"hostname": "unrelated-neighbour.example"},   # shares an IP; not acme's estate
        ]})

    ctx = _ctx_with_http(handler, otx_api_key="k")
    result = await get_collector("otx").collect(Vendor(ref="acme", domain="acme.com"), ctx)
    assert result.status == "ok"
    (f,) = result.findings
    assert f.signal == "subdomain_estate"
    assert f.value["count"] == 3            # the neighbour is excluded
    await ctx.http.aclose()


async def test_otx_feeds_the_same_signal_as_ct_for_redundancy():
    """OTX emits the SAME count-banded signal CT does, so when CT fails OTX carries Digital
    Footprint, and when both run the engine's worst-of collapse prevents double-counting."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"passive_dns": [{"hostname": "a.acme.com"}]})

    ctx = _ctx_with_http(handler, otx_api_key="k")
    result = await get_collector("otx").collect(Vendor(ref="acme", domain="acme.com"), ctx)
    assert result.findings[0].category == "digital_footprint_assets"
    assert result.findings[0].signal == "subdomain_estate"
    await ctx.http.aclose()


async def test_otx_404_is_empty_not_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={})

    ctx = _ctx_with_http(handler, otx_api_key="k")
    result = await get_collector("otx").collect(Vendor(ref="acme", domain="acme.com"), ctx)
    assert result.status == "empty"
    await ctx.http.aclose()


# --------------------------------------------------------------------- Companies House parsing


async def test_companies_house_maps_status_onto_existing_bands():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [
            {"company_number": "12345678", "title": "ACME LTD",
             "company_status": "active", "company_type": "ltd"},
        ]})

    ctx = _ctx_with_http(handler, companies_house_key="k")
    result = await get_collector("companies_house").collect(Vendor(ref="acme", name="Acme"), ctx)
    assert result.status == "ok"
    (f,) = result.findings
    assert f.signal == "entity_status"
    assert f.category == "business_financial_stability"
    assert f.value["band"] == "active_good_standing"
    await ctx.http.aclose()


async def test_companies_house_flags_a_dissolved_company_as_inactive():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [
            {"company_number": "99999999", "title": "DEFUNCT LTD",
             "company_status": "dissolved", "company_type": "ltd"},
        ]})

    ctx = _ctx_with_http(handler, companies_house_key="k")
    result = await get_collector("companies_house").collect(Vendor(ref="defunct", name="Defunct"), ctx)
    assert result.findings[0].value["band"] == "entity_inactive"
    await ctx.http.aclose()


async def test_companies_house_no_confident_match_is_empty():
    """A non-UK vendor has no UK company; that is a coverage fact, not a risk fact."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [
            {"company_number": "1", "title": "SOMETHING ENTIRELY DIFFERENT",
             "company_status": "active"},
        ]})

    ctx = _ctx_with_http(handler, companies_house_key="k")
    result = await get_collector("companies_house").collect(
        Vendor(ref="usvendor", name="Acme US Corp"), ctx)
    assert result.status == "empty"
    await ctx.http.aclose()


def test_companies_house_bands_are_all_real_scoring_bands():
    """Every band this collector emits must exist in scoring.yaml, or it would score nothing and
    the drift guard's whole point is defeated."""
    from app.scoring_config import get_scoring_config
    ch = get_collector("companies_house")
    cfg = get_scoring_config()
    # Resolved from the model, not from the collector's `_CAT` — `entity_status` moved from
    # business_financial_stability to continuity_context at E5 and will move again.
    valid = set(cfg.signals_of(cfg.category_of("entity_status") or "")["entity_status"])
    for status in ("active", "dissolved", "liquidation", "unknown-status"):
        assert ch._band(status) in valid
