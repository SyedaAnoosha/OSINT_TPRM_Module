"""P7 — status-page report: outage history, routed to Continuity, never Posture.

WHY THIS IS A SIBLING MODULE, NOT AN EXTENSION OF `continuity.py`. Continuity interprets
`PersistedFinding`s that OTHER collectors already put through the scored pipeline (informational
bands, counted for coverage). The status-page collector deliberately emits none — see its module
docstring — so there is nothing in `PersistedFinding` for `continuity.py` to read. This module reads
the raw `Evidence` row instead, exactly the shape `fourth_party.py` and `concentration.py` already
use for the same reason: a disclosed-never-scored fact that still needs its own interpretation.

FREQUENT OUTAGES ARE A DELIVERY PROBLEM, NOT A SECURITY PROBLEM (verbatim from the phase plan).
Nothing here computes a posture point, and nothing here is fed into Continuity's `standing` either —
mixing an operational-availability signal into a going-concern axis would blur two different
questions ("is this entity still a legal person" vs "does their service fall over often") the same
way E4 separated going-concern out of Posture for being a different question from "is TLS current".

THE CAVEAT THAT DOES THE WORK: absence of a discoverable status page is a COVERAGE gap, not a
Continuity finding. Most vendors run no machine-readable status page, or run one this collector's
URL guesses do not reach — instatus, a hand-rolled page, or Statuspage.io on an uncommon subdomain.
Reading "not found" as "no outages" would flatter a vendor; reading it as "unstable" would punish one
for a naming convention. Neither is licensed by the evidence, so neither is asserted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Statuspage.io's own vocabulary for `status.indicator`, worst-first — used only to order/describe,
#: never to score.
_INDICATOR_ORDER = {"critical": 0, "major": 1, "minor": 2, "none": 3}
_INDICATOR_LABEL = {
    "none": "operational", "minor": "minor service disruption",
    "major": "major service disruption", "critical": "critical outage",
}

_CAVEATS = [
    "ROUTED TO CONTINUITY, NOT POSTURE. A degraded-service or open-incident observation is an "
    "operational/delivery signal, not a security control, and never subtracts a posture point — "
    "the same separation E4 drew for going-concern facts.",
    "ABSENCE OF A DISCOVERABLE STATUS PAGE IS A COVERAGE GAP, NOT A CONTINUITY FINDING. Many "
    "vendors run one without a machine-readable summary at a checked location, or run one this "
    "check does not try. 'Not found' says nothing about how often they actually have outages.",
    "Only the Statuspage.io v2 JSON API shape is recognised, at `status.<domain>/api/v2/*.json`. A "
    "vendor on Instatus, a custom page, or one that does not publish at that path reads as 'not "
    "found' even if a status page exists elsewhere — this is a known, stated gap, not a claim the "
    "vendor has none.",
    "A snapshot of ONE point in time, taken when this assessment ran. It says nothing about outage "
    "FREQUENCY or history — only the state and open incidents observed at the moment of the check.",
]


@dataclass(frozen=True)
class StatusPageReport:
    vendor_ref: str
    found: bool
    checked_urls: list[str]
    checked_url: str | None
    page_name: str | None
    page_url: str | None
    indicator: str | None
    description: str | None
    open_incident_count: int
    updated_at: str | None
    retrieved_at: str | None
    caveats: list[str] = field(default_factory=list)

    def headline(self) -> str:
        if not self.found:
            return (
                "No status page was discoverable at the checked locations. This is an absence of "
                "evidence, not a Continuity finding — it does not mean outages are frequent, only "
                "that we could not observe them."
            )
        label = _INDICATOR_LABEL.get(self.indicator or "none", self.indicator or "unknown")
        if (self.indicator or "none") != "none":
            tail = f", {self.open_incident_count} open incident(s)" if self.open_incident_count else ""
            return f"Status page reports {label}{tail}."
        if self.open_incident_count:
            return f"Status page reports operational, but {self.open_incident_count} open incident(s)."
        return "Status page found and reports operational, with no open incidents."


def status_page_report(vendor_ref: str, evidence: list[Any]) -> StatusPageReport:
    """Build the report from the raw `Evidence` row `status_page_collector.py` stored.

    `evidence` is whatever `store.for_vendor(ref)` returns — anything carrying `.source`, `.status`,
    `.raw` and `.fetched_at`. Multiple rows across re-scans are possible; the most recent wins,
    because this is a point-in-time snapshot and an older one would misreport the current state.
    """
    rows = [e for e in evidence if getattr(e, "source", None) == "status_page"]
    if not rows:
        return StatusPageReport(
            vendor_ref=vendor_ref, found=False, checked_urls=[], checked_url=None,
            page_name=None, page_url=None, indicator=None, description=None,
            open_incident_count=0, updated_at=None, retrieved_at=None, caveats=list(_CAVEATS),
        )

    latest = max(rows, key=lambda e: getattr(e, "fetched_at", None) or getattr(e, "stored_at", None))
    raw = latest.raw or {}
    found = getattr(latest, "status", None) == "ok"
    retrieved_at = latest.fetched_at.isoformat() if getattr(latest, "fetched_at", None) else None

    if not found:
        return StatusPageReport(
            vendor_ref=vendor_ref, found=False,
            checked_urls=list(raw.get("checked_urls") or []), checked_url=None,
            page_name=None, page_url=None, indicator=None, description=None,
            open_incident_count=0, updated_at=None, retrieved_at=retrieved_at,
            caveats=list(_CAVEATS),
        )

    return StatusPageReport(
        vendor_ref=vendor_ref, found=True,
        checked_urls=list(raw.get("checked_urls") or []), checked_url=raw.get("checked_url"),
        page_name=raw.get("page_name"), page_url=raw.get("page_url"),
        indicator=raw.get("indicator"), description=raw.get("description"),
        open_incident_count=int(raw.get("open_incident_count") or 0),
        updated_at=raw.get("updated_at"), retrieved_at=retrieved_at, caveats=list(_CAVEATS),
    )


def as_dict(report: StatusPageReport) -> dict[str, Any]:
    return {
        "vendor_ref": report.vendor_ref,
        "found": report.found,
        "headline": report.headline(),
        "indicator": report.indicator,
        "indicator_label": (_INDICATOR_LABEL.get(report.indicator or "none")
                            if report.found else None),
        "description": report.description,
        "open_incident_count": report.open_incident_count,
        "page_name": report.page_name,
        "page_url": report.page_url,
        "updated_at": report.updated_at,
        "checked_url": report.checked_url,
        "checked_urls": report.checked_urls,
        "retrieved_at": report.retrieved_at,
        "caveats": report.caveats,
    }
