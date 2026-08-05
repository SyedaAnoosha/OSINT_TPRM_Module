"""The Gazette (UK) collector — OFFICIAL notices of insolvency and appointment of officers.

WHY. The Gazette is the UK's official public record — the primary legal source for winding-up
petitions, liquidator/receiver/administrator appointments, and insolvency notices. It is not a
downstream aggregation; it is the register itself. For TPRM continuity assessment, this is the
cleanest signal on the table for UK entities.

LEGALITY — CLEARED (`source_assessment.md`). Crown copyright, Open Government Licence (OGL),
commercial use permitted, no API key required. Rate limit: be respectful (the service asks for
≤10 req/sec). Unreachable is NOT an error: the collector returns `empty`, lowering coverage and
never posture, and the app runs unconfigured like every other keyed source.

ENTITY-LEVEL ONLY (§4.2). This reads company insolvency notices and officer appointments — all
corporate records. No natural-person data enters the model.

SIGNAL MAPPING. Findings land in `continuity_context` at `informational` bands, mirroring the
existing `entity_status`/`entity_existence` pattern. The worst standing observed becomes the
headline in `continuity.py`.

DATA SOURCE. The Gazette's `/insolvency/notice/data.json` endpoint returns structured JSON
(verified against the live API, 2026-08) — an `entry` list already scoped to the insolvency
category, each with a human-readable `title` (e.g. "Petitions to Wind Up (Companies)",
"Appointment of Administrators"), a `published` date, and a canonical `id` URL. No HTML scraping
is needed or used.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_SEARCH = "https://www.thegazette.co.uk/insolvency/notice/data.json"
_HOST = "www.thegazette.co.uk"
# v5.0.0 (E4/E5) renamed this category from `business_financial_stability` to `continuity_context`
# — see change-notice-v5.md §3.4. Findings land here at `informational` bands only; they are
# reported (app/continuity.py) and NEVER penalise posture.
_CAT = "continuity_context"
_SUB = "insolvency_notice"

class GazetteCollector(Collector):
    source = "the_gazette"
    reliability = 0.98  # the UK's official public record — primary legal source
    timeout_s = 20.0
    http_attempts = 2
    http_backoff_s = 1.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        query = vendor.name or vendor.ref

        search_url = f"{_SEARCH}?text={quote(query)}"

        resp = await self._get_with_retry(
            ctx, search_url, limiter_key=_HOST,
        )
        if resp is None:
            return self.result(vendor, "error", notes="The Gazette unavailable")
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"The Gazette returned {resp.status_code}")

        try:
            data = resp.json()
            notices = self._extract_notices(data)
        except Exception:
            return self.result(vendor, "error", notes="Failed to parse The Gazette response")

        if not notices:
            # No insolvency notices found — a clean receipt, not an error
            return self.result(
                vendor, "ok", raw={"query": query, "notices_found": 0},
                findings=[Finding(
                    source=self.source, signal="insolvency_notice", subcategory=_SUB, category=_CAT,
                    observed="no_insolvency_notices",
                    value={"band": "no_adverse_filings"},
                    locator=search_url,
                    notes="The Gazette searched; no insolvency notices found for this entity.",
                )],
                source_version="clean",
            )

        findings = []
        raw_notices = []

        for notice in notices:
            band = self._band(notice["notice_code"])
            finding = Finding(
                source=self.source, signal="insolvency_notice", subcategory=_SUB, category=_CAT,
                observed=f"{notice['title']} — {notice['published']}",
                value={"band": band, "notice_title": notice["title"],
                       "notice_code": notice["notice_code"],
                       "notice_date": notice["published"], "notice_url": notice["url"]},
                locator=notice["url"],
                notes="Insolvency notice from The Gazette (UK official public record).",
            )
            findings.append(finding)
            raw_notices.append(notice)

        raw = {
            "query": query,
            "notices_found": len(notices),
            "notices": raw_notices,
        }

        return self.result(vendor, "ok", raw=raw, findings=findings)

    @staticmethod
    def _extract_notices(data: dict[str, Any]) -> list[dict[str, Any]]:
        """Pull CORPORATE notices from the real `/insolvency/notice/data.json` shape.

        A zero-result search omits the `entry` key entirely rather than returning `[]`
        (verified against the live API) — `.get("entry", [])` covers both.

        THE §4.2 BRIGHT LINE, ENFORCED HERE. The Gazette's insolvency search mixes corporate
        notices with PERSONAL bankruptcy notices in the same result set — e.g. a search for
        "Acme" can return an entry titled with an individual's full name (a personal bankruptcy
        notice that happens to mention an "Acme"-named employer or address). Title text is not a
        safe filter: some corporate entries are titled with a category label ("Resolutions for
        Winding-up") and others with the company's own name ("ACME PHARMA LTD"), so a name-shaped
        title cannot be told apart from a person's name by pattern alone.
        The Gazette's own published notice-code taxonomy (thegazette.co.uk/noticecodes) draws the
        line precisely: **codes 2401-2465 are "24 Corporate insolvency"; codes 2501-2528 are
        "25 Personal insolvency"** (individual bankruptcy, statutory demands, sequestration).
        Filtering on `f:notice-code` — not on title text — is what makes this a hard exclusion
        rather than a heuristic. An entry with no notice-code, or one outside 2401-2465, is
        dropped, never defaulted in.
        """
        entries = data.get("entry", []) or []
        notices = []
        for entry in entries:
            title = entry.get("title", "")
            code_raw = entry.get("f:notice-code")
            if not title or not code_raw:
                continue
            try:
                code = int(code_raw)
            except (TypeError, ValueError):
                continue
            if not (2401 <= code <= 2465):
                continue  # outside the corporate-insolvency range — may be personal (2501-2528)
            notices.append({
                "title": title,
                "notice_code": code,
                "published": entry.get("published", "unknown"),
                "url": entry.get("id", ""),
            })
            if len(notices) >= 5:
                break
        return notices

    @staticmethod
    def _band(notice_code: int) -> str:
        """Map the Gazette's own corporate-insolvency notice-code sub-range onto entity_status.

        Winding-up (members'/creditors'/by-court, 2431-2465) is a liquidation process — the
        entity is ceasing to exist. Administration and receivership (2410-2424) are recovery
        procedures the entity may exit — watch, not ceased. General corporate-insolvency notices
        (2401-2409) are procedural/preliminary — also watch, the more conservative read.
        """
        if 2431 <= notice_code <= 2465:
            return "entity_inactive"
        return "registration_lapsed"
