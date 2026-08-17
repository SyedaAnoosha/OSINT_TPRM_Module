"""Regulatory-feed collector — hard-fact adverse media from official enforcement feeds.

The high-signal, low-noise alternative to raw GDELT sentiment (source_assessment.md §13).
GDELT tracks *newsworthiness* and reports *allegations*; a regulator's own enforcement feed
reports *facts* — a named order, settlement, or investigation — dated and attributed. So this
collector scores, where GDELT only gathers candidates.

HONEST LIMITS, carried into the reliability, not hidden:
  * A feed only exposes its RECENT window (~the last N items), not a searchable history — so a
    three-year-old action won't appear. This is recent-monitoring, not a comprehensive record.
  * v3.4 coverage is US + UK + EU: FTC / SEC / DOJ (US), CMA + ICO via gov.uk Atom (UK, incl. the
    UK data-protection regulator), and CNIL (EU/GDPR). CISA hard-blocks automated access (anti-bot);
    AU regulators (ACCC/ASIC/OAIC) publish no stable public RSS (verified 2026-07-21) — an honest
    gap, not silent. Feeds are polled in parallel and the collector degrades per-feed.
Because of the recent-window limit, a "no action found" result is still a WEAK clean receipt
(clean_reliability 0.4) — checked, but far from a comprehensive enforcement history.

Defamation control (methodology §4.2 / §5.4.1): a matched item is worded as "named in
<regulator> publication", flagged for review, and — on a thin-coverage vendor — lands in the
uncorroborated_signal quadrant (review, never auto-report), never a client-facing verdict.
"""

from __future__ import annotations

import asyncio
import re
from datetime import UTC, datetime
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_CAT = "adverse_media_reputation"
_SUB = "regulatory_actions"

# Cleared, reachable regulator feeds only (source_assessment.md §13), each verified live
# 2026-07-21. All are government open data (US public domain / UK OGL / FR Licence Ouverte) —
# free commercial + automated reuse. The collector polls them in parallel and degrades per-feed.
_FEEDS: list[tuple[str, str]] = [
    ("FTC", "https://www.ftc.gov/feeds/press-release.xml"),                       # US — consumer protection
    ("SEC", "https://www.sec.gov/news/pressreleases.rss"),                        # US — securities
    ("DOJ", "https://www.justice.gov/news/rss"),                                  # US — DoJ
    ("UK-CMA", "https://www.gov.uk/search/news-and-communications.atom"
               "?organisations%5B%5D=competition-and-markets-authority"),         # UK — competition
    ("UK-ICO", "https://www.gov.uk/search/news-and-communications.atom"
               "?organisations%5B%5D=information-commissioner-s-office"),         # UK — data protection
    ("CNIL", "https://www.cnil.fr/fr/rss.xml"),                                   # EU/FR — GDPR
    ("UK-FCA", "https://www.fca.org.uk/news/rss.xml"), # FCA enforcement & warnings
    ("US-FedReg-FDIC", "https://www.federalregister.gov/api/v1/documents.rss?conditions[]=agencies:FDIC&conditions[]=topics:banking"),
    ("US-FedReg-OCC", "https://www.federalregister.gov/api/v1/documents.rss?conditions[]=agencies:OCC"),
    ("US-FedReg-CFPB", "https://www.federalregister.gov/api/v1/documents.rss?conditions[]=agencies:CFPB"),

]

_ENFORCE = re.compile(
    r"\b(order|settlement|penalt|fine[ds]?|enforcement|banned|charged?|sues?|sued|"
    r"deceptive|unlawful|violat|consent\s+order|cease\s+and\s+desist|civil\s+money\s+penalty)\w*", re.I
)
_INVESTIGATE = re.compile(r"\b(investigat|inquiry|probe|warning|alleg|complaint)\w*", re.I)


class RegulatoryCollector(Collector):
    source = "regulatory"
    reliability = 0.9   # a named regulator action is a hard fact (source_assessment.md §13)
    clean_reliability = 0.4  # recent-window + US-weighted -> weak evidence of absence
    # Enable age-based reliability adjustment: a clean result from a young company is weaker
    # evidence than the same result from a mature company (fewer years to attract enforcement).
    age_adjusted_clean_reliability = True
    timeout_s = 40.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")
        tokens = self._vendor_tokens(vendor)
        if not tokens:
            return self.result(vendor, "empty", notes="no vendor name/domain to match")

        # Poll every feed in parallel — 6 feeds sequentially would dominate the collector's runtime.
        results = await asyncio.gather(*(self._fetch_feed(ctx, url) for _, url in _FEEDS))

        matches: list[dict[str, Any]] = []
        reached: list[str] = []
        for (regulator, _url), entries in zip(_FEEDS, results, strict=True):
            if entries is None:
                continue
            reached.append(regulator)
            for e in entries:
                haystack = f"{e['title']} {e['summary']}".lower()
                if self._matches(haystack, tokens):
                    matches.append({**e, "regulator": regulator})

        if not reached:
            # Could reach no feed at all — a collection gap, not a clean bill of health.
            return self.result(vendor, "error", notes="no regulator feed reachable")

        raw: dict[str, Any] = {"tokens": sorted(tokens), "feeds_reached": reached,
                               "match_count": len(matches), "matches": matches[:25]}
        if not matches:
            # Clean receipt: polled the reachable feeds, no action names this vendor.
            finding = Finding(
                source=self.source, signal="regulator_action", subcategory=_SUB, category=_CAT,
                observed="no regulatory action found (recent window)",
                value={"band": "no_action_found", "feeds": reached},
                locator=f"regulator feeds: {', '.join(reached)}",
                notes="clean receipt — recent-window, US-weighted; absence is weak (§5.4.2)",
            )
            return self.result(vendor, "ok", raw=raw, findings=[finding],
                               reliability=self._clean_reliability(ctx),
                               notes="no regulator match — clean receipt (§5.4.2)")

        findings: list[Finding] = []
        for m in matches[:10]:
            band = "enforcement_action" if _ENFORCE.search(m["title"] + m["summary"]) else "formal_investigation"
            findings.append(Finding(
                source=self.source, signal="regulator_action", subcategory=_SUB, category=_CAT,
                observed=f"named in {m['regulator']} publication: {m['title'][:120]}",
                value={"band": band, "regulator": m["regulator"], "url": m["link"]},
                event_date=m["date"],
                locator=m["link"] or f"{m['regulator']} feed",
                notes="CANDIDATE — regulator-published; review attribution before reporting (§5.4.1)",
            ))
        return self.result(vendor, "ok", raw=raw, findings=findings, source_version="live")

    # --- feed fetch + parse (RSS 2.0 and Atom, dependency-free) ---

    async def _fetch_feed(self, ctx: CollectorContext, url: str) -> list[dict[str, Any]] | None:
        assert ctx.http is not None
        host = httpx.URL(url).host or "regulator"
        await ctx.limiter.acquire(host)
        try:
            r = await ctx.http.get(url)
        except httpx.HTTPError:
            return None
        if r.status_code != 200 or not r.text.strip():
            return None
        try:
            return self._parse_feed(r.text)
        except ET.ParseError:
            return None

    @staticmethod
    def _parse_feed(text: str) -> list[dict[str, Any]]:
        """Parse RSS <item> or Atom <entry> into normalised dicts. Namespace-agnostic."""
        root = ET.fromstring(text)

        def local(tag: str) -> str:
            return tag.rsplit("}", 1)[-1].lower()

        def text_of(el: ET.Element, *names: str) -> str:
            for child in el:
                if local(child.tag) in names and child.text:
                    return child.text.strip()
            return ""

        def link_of(el: ET.Element) -> str:
            for child in el:
                if local(child.tag) == "link":
                    return (child.text or child.attrib.get("href", "")).strip()
            return ""

        out: list[dict[str, Any]] = []
        for el in root.iter():
            if local(el.tag) in {"item", "entry"}:
                out.append({
                    "title": text_of(el, "title"),
                    "summary": text_of(el, "description", "summary", "content"),
                    "link": link_of(el),
                    "date": RegulatoryCollector._parse_date(
                        text_of(el, "pubdate", "published", "updated", "date")
                    ),
                })
        return out

    @staticmethod
    def _parse_date(value: str) -> datetime | None:
        if not value:
            return None
        for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                    "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                dt = datetime.strptime(value.strip(), fmt)
                return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
            except ValueError:
                continue
        return None

    @staticmethod
    def _vendor_tokens(vendor: Vendor) -> set[str]:
        tokens: set[str] = set()
        for raw in (vendor.name, vendor.ref):
            if raw:
                tokens.update(w for w in re.split(r"[^a-z0-9]+", raw.lower()) if len(w) > 3)
        if vendor.domain:
            root = vendor.domain.split(".")[0]
            if len(root) > 3:
                tokens.add(root.lower())
        return tokens

    @staticmethod
    def _matches(haystack: str, tokens: set[str]) -> bool:
        return any(re.search(rf"\b{re.escape(t)}\b", haystack) for t in tokens)
