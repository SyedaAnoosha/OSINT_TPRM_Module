"""GDELT collector — adverse media candidates (NOT scored directly).

GDELT has the strongest licence on the register — unrestricted commercial use with
citation (source_assessment.md §10; attribution is a UI requirement). But media reports
*allegations, not findings*, and coverage tracks newsworthiness, not risk. So this
collector emits CANDIDATES, never scores: every item is worded as reported/alleged,
dated, attributed, and left for AI adjudication (Phase 5) + human review. It must never
drive a score directly (scoring.yaml adverse_media_reputation is ai_adjudicated).

Defamation control (methodology §4.2 / §5.4.1): an uncorroborated hit against a small
vendor is exposure. These findings are candidates for the Uncorroborated-signal path,
not client-facing statements.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from ..models import CollectorResult, Vendor
from .base import Collector, CollectorContext

_API = "https://api.gdeltproject.org/api/v2/doc/doc"
_CAT = "adverse_media_reputation"
# risk-framing terms to bias the query toward adverse coverage (still noisy)
_RISK_TERMS = '(breach OR hack OR lawsuit OR fine OR investigation OR scandal OR outage OR ransomware)'


class GdeltCollector(Collector):
    source = "gdelt"
    reliability = 0.6  # media reports allegations, not findings (source_assessment.md §10)
    timeout_s = 25.0
    # Enrichment-only: findings are held/ai_adjudicated (contribute 0 to the score), and GDELT's
    # free API throttles hard (429). So it does NOT run on the synchronous scoring path — it is a
    # Phase 5 scheduled-enrichment source. Include it explicitly with run_pipeline(include_enrichment=True).
    on_demand = False

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")
        name = vendor.name or vendor.ref
        query = f'"{name}" {_RISK_TERMS}'

        await ctx.limiter.acquire("api.gdeltproject.org")
        try:
            resp = await ctx.http.get(
                _API,
                params={"query": query, "mode": "artlist", "format": "json",
                        "maxrecords": 50, "timespan": "12m", "sort": "hybridrel"},
            )
        except httpx.HTTPError as exc:
            return self.result(vendor, "error", notes=f"GDELT fetch failed: {type(exc).__name__}: {exc}")
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"GDELT returned {resp.status_code}")

        try:
            data = resp.json()
        except ValueError:
            # GDELT sometimes returns an HTML notice for rate limits / empty queries
            return self.result(vendor, "empty", notes="GDELT returned non-JSON (rate limit or no hits)")

        articles = data.get("articles", [])
        if not articles:
            return self.result(
                vendor, "empty", raw={"query": query, "articles": 0},
                notes="no adverse-media candidates in 12m (absence is near-meaningless for small vendors)",
            )

        raw: dict[str, Any] = {
            "query": query, "article_count": len(articles),
            "articles": [{"title": a.get("title"), "url": a.get("url"),
                          "domain": a.get("domain"), "seendate": a.get("seendate"),
                          "language": a.get("language")} for a in articles[:50]],
        }
        # HELD BY DESIGN, not by accident. These are candidates — reported/alleged, awaiting AI
        # adjudication and human review (roadmap §3) — so they must never reach the scoring model.
        #
        # This used to emit a `tone_volume` Finding that scoring.yaml had no band for. The
        # normaliser dropped it with a warning on every run, so "held" was achieved by the model
        # failing to recognise the signal rather than by the collector declining to score it.
        # That is the same defect as config nothing reads, pointing the other way: a collector
        # emitting a signal the model does not know. Candidates now live in `raw` — captured in
        # the evidence store, retrievable for adjudication, structurally unable to score.
        raw["candidates"] = len(articles)
        raw["latest_seen"] = (d.isoformat() if (d := self._latest(articles)) else None)
        return self.result(
            vendor, "ok", raw=raw, findings=[], source_version="live",
            notes=(f"{len(articles)} adverse-media CANDIDATES gathered (12m) — reported/alleged, "
                   "held for AI adjudication + human review; never scored"),
        )

    @staticmethod
    def _latest(articles: list[dict[str, Any]]) -> datetime | None:
        newest: datetime | None = None
        for a in articles:
            sd = a.get("seendate")
            if not sd:
                continue
            try:
                dt = datetime.strptime(sd, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
            except ValueError:
                continue
            if newest is None or dt > newest:
                newest = dt
        return newest
