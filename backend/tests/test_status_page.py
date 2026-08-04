"""P7 — status-page report: outage history, routed to Continuity, never Posture.

Two layers, same split every disclosed-never-scored feature in this codebase uses:
`status_page_collector.py` fetches and stores raw evidence, emitting NO findings (so nothing here
can ever move a posture point); `status_page.py` interprets that raw evidence into a report.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from app.collectors.status_page_collector import StatusPageCollector
from app.config import Settings
from app.models import Vendor
from app.ratelimit import RateLimiter
from app.collectors.base import CollectorContext
from app.status_page import status_page_report


def _http_ctx(handler):  # noqa: ANN001, ANN202
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return CollectorContext(settings=Settings(), limiter=RateLimiter(), http=client), client


class _Evidence:
    def __init__(self, source: str, status: str, raw: dict | None, fetched_at=None) -> None:
        self.source, self.status, self.raw = source, status, raw
        self.fetched_at = fetched_at or datetime(2026, 7, 30, tzinfo=UTC)
        self.stored_at = self.fetched_at


# ============================================================ the collector — emits no findings


async def test_a_statuspage_shaped_response_is_parsed_and_emits_no_findings():
    def handler(request):  # noqa: ANN001, ANN202
        return httpx.Response(200, json={
            "page": {"name": "Acme Status", "url": "https://status.acme.com",
                     "updated_at": "2026-07-30T00:00:00Z"},
            "status": {"indicator": "minor", "description": "Degraded API"},
            "incidents": [{"id": "1"}],
        })

    ctx, client = _http_ctx(handler)
    async with client:
        res = await StatusPageCollector()._run(Vendor(ref="acme", domain="acme.com"), ctx)

    assert res.status == "ok"
    assert res.findings == []          # THE RULE THIS COLLECTOR HOLDS
    assert res.raw["indicator"] == "minor"
    assert res.raw["open_incident_count"] == 1
    assert res.raw["page_name"] == "Acme Status"


async def test_a_non_statuspage_shaped_response_is_not_guessed_at():
    """An unfamiliar JSON body must not be reported as a status page — guessing at the shape and
    getting the indicator wrong is worse than reporting nothing."""
    def handler(request):  # noqa: ANN001, ANN202
        return httpx.Response(200, json={"hello": "world"})

    ctx, client = _http_ctx(handler)
    async with client:
        res = await StatusPageCollector()._run(Vendor(ref="acme", domain="acme.com"), ctx)
    assert res.status == "empty"
    assert res.findings == []


async def test_no_status_page_found_at_either_candidate_is_empty_not_error():
    ctx, client = _http_ctx(lambda request: httpx.Response(404))  # noqa: ARG005
    async with client:
        res = await StatusPageCollector()._run(Vendor(ref="acme", domain="acme.com"), ctx)
    assert res.status == "empty"
    assert res.findings == []
    assert res.raw["checked_urls"]


async def test_no_domain_is_empty():
    res = await StatusPageCollector()._run(
        Vendor(ref="acme", name="Acme"),
        CollectorContext(settings=Settings(), limiter=RateLimiter(), http=None),
    )
    assert res.status == "empty"
    assert res.findings == []


def test_candidate_urls_are_the_common_custom_domain_convention():
    urls = StatusPageCollector._candidate_urls("Acme.com")
    assert urls[0] == "https://status.acme.com/api/v2/summary.json"
    assert all(u.startswith("https://status.acme.com") for u in urls)


# ============================================================ the report — disclosed, never scored


def test_no_evidence_at_all_is_reported_as_a_coverage_gap_not_an_outage():
    report = status_page_report("acme", [])
    assert report.found is False
    assert "absence of evidence, not a Continuity finding" in report.headline()


def test_an_empty_collector_receipt_is_also_not_found():
    evidence = [_Evidence("status_page", "empty", {"checked_urls": ["https://status.acme.com/x"]})]
    report = status_page_report("acme", evidence)
    assert report.found is False
    assert report.checked_urls == ["https://status.acme.com/x"]


def test_a_clean_operational_page_is_found_and_says_so():
    evidence = [_Evidence("status_page", "ok", {
        "checked_url": "https://status.acme.com/api/v2/summary.json",
        "page_name": "Acme Status", "page_url": "https://status.acme.com",
        "indicator": "none", "description": "All systems operational",
        "open_incident_count": 0, "updated_at": "2026-07-30T00:00:00Z",
    })]
    report = status_page_report("acme", evidence)
    assert report.found is True
    assert report.indicator == "none"
    assert "no open incidents" in report.headline()


def test_a_degraded_indicator_is_named_in_the_headline():
    evidence = [_Evidence("status_page", "ok", {
        "indicator": "major", "description": "Partial outage", "open_incident_count": 2,
    })]
    report = status_page_report("acme", evidence)
    assert "major service disruption" in report.headline()
    assert "2 open incident(s)" in report.headline()


def test_only_status_page_evidence_is_read_other_sources_are_ignored():
    evidence = [_Evidence("dns", "ok", {"unrelated": True}),
                _Evidence("status_page", "ok", {"indicator": "none", "open_incident_count": 0})]
    report = status_page_report("acme", evidence)
    assert report.found is True


def test_the_most_recent_status_page_row_wins():
    older = _Evidence("status_page", "ok", {"indicator": "critical", "open_incident_count": 5},
                      fetched_at=datetime(2026, 1, 1, tzinfo=UTC))
    newer = _Evidence("status_page", "ok", {"indicator": "none", "open_incident_count": 0},
                      fetched_at=datetime(2026, 7, 30, tzinfo=UTC))
    report = status_page_report("acme", [older, newer])
    assert report.indicator == "none"


def test_never_scored_no_posture_field_anywhere_in_the_shape():
    from app.status_page import as_dict

    evidence = [_Evidence("status_page", "ok", {"indicator": "none", "open_incident_count": 0})]
    payload = as_dict(status_page_report("acme", evidence))
    assert "posture" not in payload
    assert any("ROUTED TO CONTINUITY, NOT POSTURE" in c for c in payload["caveats"])
    assert any("COVERAGE GAP" in c for c in payload["caveats"])
