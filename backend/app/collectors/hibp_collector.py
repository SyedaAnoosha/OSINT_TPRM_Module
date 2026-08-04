"""Have I Been Pwned collector — /breaches only, the company-level endpoint.

We learn *that a company was breached*, never *which of its users were*. The domain-search
endpoint needs domain verification + an API key + a paid plan and is excluded on both
legality and the free-data rule (source_assessment.md §4) — and the /breaches choice is
also the privacy-respecting one. Unauthenticated; HIBP requires a descriptive User-Agent
(set on the client) and is licensed CC BY 4.0 (attribution is a UI requirement).

Absence of a breach record is NOT evidence of security — it is evidence of *no publicly
known breach*. We record that as a CLEAN RECEIPT: a benign, low-risk finding emitted at
`clean_reliability` (below the positive-detection reliability), so "we queried the largest
public breach corpus and this domain is absent" counts toward coverage without claiming
security (methodology §5.4.2). The residual "maybe undisclosed" uncertainty is carried by
the reduced reliability, not by pretending we never looked.
Breach date -> event_date so a 2013 breach decays below last month's (NIST SP 1326).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_CAT = "breach_compromise_history"
_SUB = "confirmed_breaches"
_SEVERE = {"Passwords", "Credit cards", "Bank account numbers", "Historical passwords"}
_PERSONAL = {"Phone numbers", "Physical addresses", "Dates of birth", "Government issued IDs"}


class HibpCollector(Collector):
    source = "hibp"
    reliability = 0.9  # curated, verified/unverified flagged (source_assessment.md §4)
    # A clean HIBP result rules out PUBLICLY-KNOWN breaches only — undisclosed breaches
    # exist, so a clean receipt is materially weaker than a positive hit (source_assessment §4).
    clean_reliability = 0.55
    timeout_s = 20.0

    def _clean(self, vendor: Vendor, domain: str | None) -> CollectorResult:
        """Clean receipt: reached HIBP, no known breach. Benign finding, reduced reliability."""
        finding = Finding(
            source=self.source, signal="breach_by_data_class", subcategory=_SUB, category=_CAT,
            observed="no known public breach",
            value={"band": "no_known_breach"},
            locator=f"HIBP /breaches Domain={domain}",
            notes="clean receipt — no PUBLICLY known breach; absence is not proof of security",
        )
        return self.result(vendor, "ok", raw={"domain": domain, "breaches": []},
                           findings=[finding], reliability=self._clean_reliability(),
                           notes="no breach record — recorded as clean receipt (§5.4.2)")

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        domain = vendor.domain
        if not domain:
            return self.result(vendor, "empty", notes="no domain for HIBP lookup")
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        await ctx.limiter.acquire("haveibeenpwned.com")
        try:
            resp = await ctx.http.get(
                "https://haveibeenpwned.com/api/v3/breaches", params={"Domain": domain}
            )
        except httpx.HTTPError as exc:
            return self.result(vendor, "error", notes=f"HIBP fetch failed: {exc}")

        if resp.status_code == 404:
            return self._clean(vendor, domain)
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"HIBP returned {resp.status_code}")

        breaches = resp.json()
        if not breaches:
            return self._clean(vendor, domain)

        raw: dict[str, Any] = {"domain": domain, "breach_count": len(breaches), "breaches": breaches}
        findings: list[Finding] = []
        for b in breaches:
            classes = set(b.get("DataClasses", []))
            band = self._band(classes)
            breach_date = self._parse_date(b.get("BreachDate"))
            findings.append(
                Finding(
                    source=self.source, signal="breach_by_data_class", subcategory=_SUB, category=_CAT,
                    observed=f"{b.get('Name')} ({band})",
                    value={"band": band, "name": b.get("Name"), "pwn_count": b.get("PwnCount"),
                           "data_classes": sorted(classes), "verified": b.get("IsVerified")},
                    event_date=breach_date,
                    locator=f"HIBP /breaches Domain={domain} :: {b.get('Name')}",
                    notes=None if b.get("IsVerified", True) else "unverified breach",
                )
            )
        return self.result(vendor, "ok", raw=raw, findings=findings, source_version="live")

    @staticmethod
    def _band(classes: set[str]) -> str:
        if classes & _SEVERE:
            return "passwords_or_cards"
        if classes & _PERSONAL:
            return "personal_info"
        return "email_only"

    @staticmethod
    def _parse_date(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            return None
