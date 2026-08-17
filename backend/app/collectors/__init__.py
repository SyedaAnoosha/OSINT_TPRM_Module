"""Collector registry.

Each collector is registered by its `source` id. The pipeline (Phase 3) will fan out
over `all_collectors()`; for Phase 1 the harness runs them one at a time. New collectors
are added here as they are built.
"""

from __future__ import annotations

from .abn_collector import AbnCollector
from .base import Collector, CollectorContext
from .companies_house_collector import CompaniesHouseCollector
from .ct_collector import CtCollector
from .dns_collector import DnsCollector
from .firmographics_collector import FirmographicsCollector
from .gdelt_collector import GdeltCollector
from .gleif_collector import GleifCollector
from .headers_collector import HeadersCollector
from .hibp_collector import HibpCollector
from .ita_collector import ItaCollector
from .kev_collector import KevCollector
from .nvd_collector import NvdCollector
from .otx_collector import OtxCollector
from .pdl_collector import PdlCollector
from .rdap_collector import RdapCollector
from .regulatory_collector import RegulatoryCollector
from .status_page_collector import StatusPageCollector
from .tls_collector import TlsCollector
from .trust_collector import TrustCollector
from .wikidata_collector import WikidataCollector
from .edgar_collector import EdgarCollector
from .gazette_collector import GazetteCollector
from .courtlistener_bankruptcy_collector import CourtListenerBankruptcyCollector
# Financial & Business Stability collectors (Phase 2)
from .eu_insolvency_collector import EUInsolvencyCollector
from .german_insolvency_collector import GermanInsolvencyCollector
from .canada_bankruptcy_collector import CanadaBankruptcyCollector
from .asic_insolvency_collector import ASICInsolvencyCollector
from .sec_xbrl_collector import SecXbrlCollector

_REGISTRY: dict[str, Collector] = {}


def register(collector: Collector) -> None:
    _REGISTRY[collector.source] = collector


def get_collector(source: str) -> Collector | None:
    return _REGISTRY.get(source)


def all_collectors() -> list[Collector]:
    return list(_REGISTRY.values())


# --- register built collectors ---
register(DnsCollector())
register(TlsCollector())
register(HeadersCollector())
register(CtCollector())
register(HibpCollector())
register(KevCollector())
register(NvdCollector())
register(ItaCollector())
register(GleifCollector())       # business_financial — replaces EDGAR (global, CC0, no auth)
register(WikidataCollector())    # business_financial — 2nd register, domain-verified corroboration
register(RdapCollector())        # business_financial — UNIVERSAL domain standing (any domain, no auth)
register(RegulatoryCollector())  # adverse_media — hard-fact regulator feeds
register(GdeltCollector())       # adverse_media candidates only (held, ai_adjudicated)
register(TrustCollector())
register(AbnCollector())         # business_financial — AUTHORITATIVE AU status (needs a free GUID)
register(CompaniesHouseCollector())  # business_financial — AUTHORITATIVE UK status (needs a free key)
register(OtxCollector())         # digital_footprint — CT REDUNDANCY via passive DNS (needs a free key)
# Profile context ONLY — emits no findings by design, so it can touch neither the posture nor the
# confidence axis. It exists so a vendor can be placed in a peer cohort (app/benchmark.py).
register(FirmographicsCollector())
register(PdlCollector())          # profile context — OFFLINE firmographics FALLBACK (opt-in index)
# P7 — emits no findings by design, so it can touch neither posture nor confidence. Routed to
# Continuity (app/status_page.py) as a disclosed, never-scored operational signal.
register(EdgarCollector())
register(GazetteCollector())
register(CourtListenerBankruptcyCollector())
register(StatusPageCollector())
# Financial & Business Stability collectors (Phase 2)
# register(OpenCorporatesCollector())      # Global registry aggregator
# register(RegistryLookupCollector())      # Backup global registry
register(EUInsolvencyCollector())        # EU insolvency proceedings
register(GermanInsolvencyCollector())    # German insolvency register
register(CanadaBankruptcyCollector())    # Canadian bankruptcy records
register(ASICInsolvencyCollector())      # Australian insolvency data
register(SecXbrlCollector())             # SEC XBRL financial data
# register(AsxCollector())   # HELD — asx.api.markitdigital.com is undocumented; ASX's own
#                              "Information Services Policy Guidelines" govern permitted data use
#                              and a separate LICENSED API (ASXonline/MIA) exists as the sanctioned
#                              path. Ask-before-collect, same gate as DFAT/Modern Slavery/
#                              OpenCorporates in docs/roadmap.md §2.4 — not wired until confirmed.
# register(AsicCollector())  # HELD — publishednotices.asic.gov.au (the Companies-House/Gazette
#                              analogue for AU insolvency notices) is legally clear (a statutory
#                              public record, Corporations Act 2001) but its current site structure
#                              could not be verified live (returns "Page Not Found" on known routes
#                              as of 2026-08-04 — mid-restructure or bot-gated). Not wired against a
#                              guessed schema; see the courtlistener_bankruptcy_collector.py
#                              precedent for why that's refused on principle, not just caution.

__all__ = ["Collector", "CollectorContext", "all_collectors", "get_collector", "register"]
