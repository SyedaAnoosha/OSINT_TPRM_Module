"""Status-page collector (P7) — outage history, routed to Continuity, never Posture.

WHAT THIS CHECKS. The Statuspage.io v2 public JSON API (`/api/v2/summary.json`), which is the one
status-page format stable and documented enough to parse with confidence. A vendor that hosts a
Statuspage.io page on a custom domain (the common pattern: `status.<domain>` CNAMEd to Statuspage)
serves the identical JSON at that path — no auth, GET only, the same request an ordinary browser
visiting the page would trigger indirectly. We do not attempt Instatus, a hand-rolled page, or any
format this collector cannot verify the shape of: guessing at an unfamiliar JSON body and reporting
a wrong indicator would be worse than reporting nothing.

THE RULE THIS COLLECTOR HOLDS — IT EMITS NO FINDINGS. Not one, `ok` or `empty`. Outage frequency is
an OPERATIONAL/DELIVERY signal, not a security control (E4 drew exactly this line for going-concern
facts, and the plan repeats it here verbatim: "frequent outages are a delivery problem, not a
security problem"). A finding is the unit that becomes a penalty; emitting one would let uptime move
Posture one release after Continuity was built specifically to stop going-concern facts doing that.
`raw` is persisted to the evidence store exactly like every other source — `app/status_page.py`
reads it — and the scoring engine never sees it. Same discipline as `FirmographicsCollector`.

ABSENCE IS A COVERAGE GAP, NOT A CONTINUITY FINDING. Most vendors run no machine-readable status
page at all, or run one this collector's URL guesses do not reach. `status="empty"` records that
honestly; `status_page.py` is the module that must not read "not found" as "no outages" (an absence
that would flatter a vendor) or as "unstable" (an absence that would falsely blame one).
"""

from __future__ import annotations

from typing import Any

from ..models import CollectorResult, Vendor
from .base import Collector, CollectorContext

# Statuspage.io serves the same summary JSON whether the buyer hits <page>.statuspage.io or a
# custom CNAMEd domain — `status.<domain>` is by far the most common custom-domain convention, so
# it is the one URL worth guessing rather than requiring a client-supplied page id.
_CANDIDATE_PATHS = ("/api/v2/summary.json", "/api/v2/status.json")


class StatusPageCollector(Collector):
    source = "status_page"
    # Community-hosted, third-party-formatted data about the vendor's OWN infrastructure — reliable
    # when it parses, but this collector emits no findings, so reliability affects nothing scored.
    reliability = 0.6
    clean_reliability = 0.6
    timeout_s = 15.0

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if not vendor.domain:
            return self.result(vendor, "empty", notes="no domain to check for a status page")
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        checked = self._candidate_urls(vendor.domain)
        for url in checked:
            resp = await self._get_with_retry(ctx, url, limiter_key="status-page")
            if resp is None or resp.status_code != 200:
                continue
            try:
                payload = resp.json()
            except ValueError:
                continue
            if not isinstance(payload, dict) or "status" not in payload or "page" not in payload:
                continue  # not Statuspage.io-shaped — do not guess at an unfamiliar format
            return self.result(vendor, "ok", raw=self._summarise(url, checked, payload))

        return self.result(
            vendor, "empty", raw={"checked_urls": checked},
            notes="no Statuspage.io-shaped status page found at the checked locations",
        )

    @staticmethod
    def _candidate_urls(domain: str) -> list[str]:
        host = domain.strip().lower().rstrip(".")
        return [f"https://status.{host}{path}" for path in _CANDIDATE_PATHS]

    @staticmethod
    def _summarise(url: str, checked: list[str], payload: dict[str, Any]) -> dict[str, Any]:
        status = payload.get("status") or {}
        page = payload.get("page") or {}
        incidents = payload.get("incidents") or []
        return {
            "checked_url": url,
            "checked_urls": checked,
            "page_name": page.get("name"),
            "page_url": page.get("url"),
            "updated_at": page.get("updated_at"),
            "indicator": status.get("indicator"),
            "description": status.get("description"),
            "open_incident_count": len(incidents) if isinstance(incidents, list) else 0,
        }
