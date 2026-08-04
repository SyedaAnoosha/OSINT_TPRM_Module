"""RDAP collector — universal domain standing (the WHOIS successor).

WHY RDAP (source_assessment.md). Most of the register is vendor-SPECIFIC: GLEIF needs an LEI,
Wikidata needs notability, KEV/NVD need shipped products, HIBP needs a breach. For a random
private vendor anywhere in the world those all come back empty, and Business Stability reads as
The Ghost. RDAP (RFC 9082/9083, the IETF replacement for WHOIS) closes that gap: it is free, needs
NO auth, is served by the registries themselves, and answers for essentially ANY registered domain
— global coverage by construction. We query the public bootstrap at rdap.org, which 302-redirects
to the authoritative RDAP server for the TLD.

WHAT it tells us — domain STANDING, not financials (§4.2 entity-level only, no natural persons):
  * a registry HOLD / pendingDelete / redemptionPeriod  -> the domain is suspended or dying: a
    real availability crisis for a vendor whose service lives on it.
  * expiry within 30 days                               -> operational risk (the site can go dark).
  * created < ~180 days ago                             -> mild fly-by-night / typosquat signal.
  * created < ~2 years                                  -> recent, slightly less reassuring.
  * long-established + active                            -> a benign, POSITIVE observation.

It is deliberately weighted a MINORITY of Business Stability (scoring.yaml): a domain is not the
company, so this is weaker evidence than an authoritative entity register — but it is the slice
available for EVERY vendor, which is the point.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .. import maturity
from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_BOOTSTRAP = "https://rdap.org/domain/"
_CAT = "business_financial_stability"
_SUB = "domain_standing"
_SIG = "domain_registration"

# RDAP status strings (RFC 9083 §10.2.2) that mean the domain is suspended / on its way out.
_SUSPENDED = {"client hold", "server hold", "pending delete", "redemption period", "pending restore"}
_NEW_DAYS = 180
_RECENT_DAYS = 730
_EXPIRING_DAYS = 30


class RdapCollector(Collector):
    source = "rdap"
    reliability = 0.85          # authoritative registry data, but a domain ≠ the company
    clean_reliability = 0.7
    timeout_s = 20.0
    http_attempts = 2           # registries occasionally 429/503; one short backoff clears it

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        if not vendor.domain:
            # Domain-driven; a name-only vendor never reaches scoring (the API asks for a domain).
            return self.result(vendor, "empty", notes="no domain to look up")
        if ctx.http is None:
            return self.result(vendor, "error", notes="no http client in context")

        registrable = self._registrable(vendor.domain)
        resp = await self._get_with_retry(
            ctx, f"{_BOOTSTRAP}{registrable}", limiter_key="rdap.org",
            headers={"Accept": "application/rdap+json"}, follow_redirects=True,
        )
        if resp is None:
            return self.result(vendor, "error", notes="RDAP request failed after retries")
        if resp.status_code == 404:
            # Not found: some ccTLDs don't publish RDAP, or the domain is unregistered. A genuine
            # per-vendor gap — lowers confidence, never risk.
            return self.result(vendor, "empty", raw={"domain": registrable, "http": 404},
                               notes="no RDAP record (unregistered or ccTLD without RDAP)")
        if resp.status_code != 200:
            return self.result(vendor, "error", notes=f"RDAP returned {resp.status_code}")

        try:
            payload = resp.json()
        except ValueError:
            return self.result(vendor, "error", notes="RDAP response was not JSON")

        created, expires = self._events(payload)
        statuses = [str(s).lower() for s in payload.get("status", [])]
        band, observed = self._classify(created, expires, statuses)

        raw: dict[str, Any] = {
            "domain": registrable,
            "ldhName": payload.get("ldhName"),
            "status": statuses,
            "created": created.isoformat() if created else None,
            "expires": expires.isoformat() if expires else None,
        }
        finding = Finding(
            source=self.source, signal=_SIG, subcategory=_SUB, category=_CAT,
            observed=observed,
            value={"band": band, "created": raw["created"], "expires": raw["expires"],
                   "status": statuses},
            locator=f"RDAP {registrable}",
            notes="domain STANDING (entity-level) — a domain is not the company; minority weight",
        )

        findings = [finding]
        if ctx.settings.rdap_emit_entity_maturity and created is not None:
            m_band, years = self._maturity_band(created, now=datetime.now(UTC))
            findings.append(Finding(
                source=self.source,
                signal="entity_maturity",
                subcategory="business_continuity",
                category=_CAT,
                observed=f"domain established ~{years:.1f} year(s)",
                # `years` and `maturity_index` travel with the band because the band alone cannot
                # tell an 11-year-old vendor from a 40-year-old one — every rung above ten years is
                # `mature_gt_10`. The index is what the confidence curve and the peer cohort read.
                value={"band": m_band, "created": raw["created"], "years": round(years, 2),
                       "maturity_index": maturity.maturity_index(years),
                       "assurance_index": maturity.assurance_index(years, self.source),
                       "evidence_strength": maturity.evidence_strength(self.source)},
                event_date=None,
                locator=f"RDAP {registrable}",
                notes="Optional secondary maturity signal from RDAP domain age; posture impact "
                      "comes only from model banding, confidence may be adjusted by multiplier. "
                      "Domain age is a DISCOUNTED maturity source — an aged domain is purchasable "
                      "and a registered entity's inception date is not.",
            ))

        return self.result(vendor, "ok", raw=raw, findings=findings, source_version="live")

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _registrable(domain: str) -> str:
        """RDAP is queried on the registrable domain, not a sub-host. Best-effort last-two-labels
        (a public-suffix list is the precise upgrade; the model's domain is already registrable
        for the vendors we target)."""
        host = domain.strip().lower().rstrip(".")
        parts = host.split(".")
        return ".".join(parts[-2:]) if len(parts) > 2 else host

    @staticmethod
    def _events(payload: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
        """Pull registration + expiration dates from the RDAP `events` array."""
        created = expires = None
        for ev in payload.get("events", []) or []:
            action = str(ev.get("eventAction", "")).lower()
            when = RdapCollector._parse_date(ev.get("eventDate"))
            if when is None:
                continue
            if action == "registration":
                created = when
            elif action == "expiration":
                expires = when
        return created, expires

    @staticmethod
    def _parse_date(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)

    @staticmethod
    def _classify(
        created: datetime | None, expires: datetime | None, statuses: list[str],
    ) -> tuple[str, str]:
        """Map (age, expiry, status) onto a scoring band. Worst-wins order."""
        now = datetime.now(UTC)
        if any(s in _SUSPENDED for s in statuses):
            return "domain_suspended", "domain suspended / pending-delete at the registry"
        if expires is not None and (expires - now).days < _EXPIRING_DAYS:
            days = (expires - now).days
            return "domain_expiring", f"domain registration expires in {days} day(s)"
        if created is not None:
            age = (now - created).days
            if age < _NEW_DAYS:
                return "domain_new", f"domain registered {age} day(s) ago — very new"
            if age < _RECENT_DAYS:
                return "domain_recent", f"domain registered {age // 30} month(s) ago"
            years = age // 365
            return "domain_established", f"domain established ~{years} year(s), active"
        # Registered, no dates exposed (some registries redact) but not suspended — treat as
        # established-ish rather than inventing risk.
        return "domain_established", "domain active (registry did not expose dates)"

    @staticmethod
    def _maturity_band(created: datetime, *, now: datetime) -> tuple[str, float]:
        """Delegates to `maturity.py`, which owns the age curve for every source. Kept as a method
        so the collector's call site reads unchanged; the banding logic itself lives in one place
        now, because two collectors independently re-deriving the same ladder is how they drift."""
        years = maturity.years_between(created, now) or 0.0
        return maturity.maturity_band(years) or "new_lt_1", years
