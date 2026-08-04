"""TLS collector — our own handshake, the deliberate SSL Labs replacement.

Same signal as SSL Labs, no ToS to breach: SSL Labs forbids commercial use, public-site
use, and assessing sites whose owners have not given permission — structurally
incompatible with third-party assessment (source_assessment.md exclusions). Running our
own client is a single connection identical to any browser visiting the site, which is
authorised by the act of publication (Criminal Code Pt 10.7 analysis, §3). It is the
cheaper *legal* position, not just the cheaper technical one.

Observes: negotiated TLS version, whether legacy TLS 1.0/1.1 is *offered*, cipher, and
certificate expiry. Perimeter only — says nothing about encryption at rest or internal
posture, and that limit is stated on the scorecard, not hidden.
"""

from __future__ import annotations

import asyncio
import socket
import ssl
from datetime import UTC, datetime
from typing import Any

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_CAT = "cyber_hygiene_technical"
_SUB = "transport_security"
# TLS 1.0/1.1 are deprecated; we probe whether the server still *offers* them.
_LEGACY = {
    "TLSv1": ssl.TLSVersion.TLSv1,
    "TLSv1.1": ssl.TLSVersion.TLSv1_1,
}


class TlsCollector(Collector):
    source = "tls"
    reliability = 0.95  # direct observation, no intermediary (source_assessment.md §3)
    timeout_s = 20.0
    # Lever 1: a dropped connection on a busy edge shouldn't zero the whole TLS read. Retry a
    # TRANSIENT failure (timeout / connection reset); an SSLError is a real cert/protocol answer
    # and is NOT retried (it must surface, not be papered over by a retry).
    _TLS_ATTEMPTS = 2
    _TLS_BACKOFF_S = 0.6

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        domain = vendor.domain
        if not domain:
            return self.result(vendor, "empty", notes="no domain for TLS handshake")

        raw: dict[str, Any] = {"domain": domain, "port": 443}
        findings: list[Finding] = []

        info: dict[str, Any] | None = None
        last_exc: Exception | None = None
        for attempt in range(1, self._TLS_ATTEMPTS + 1):
            try:
                info = await asyncio.to_thread(self._handshake, domain)
                break
            except ssl.SSLError as exc:
                # cert/protocol failure — definitive, don't retry (ssl.SSLError is an OSError
                # subclass, so this MUST be caught before the transient OSError branch below).
                return self.result(vendor, "error", raw=raw, notes=f"handshake failed: {exc}")
            except (TimeoutError, OSError) as exc:
                last_exc = exc
                if attempt < self._TLS_ATTEMPTS:
                    await asyncio.sleep(self._TLS_BACKOFF_S)
        if info is None:
            return self.result(vendor, "error", raw=raw,
                               notes=f"handshake failed after {self._TLS_ATTEMPTS} attempts: {last_exc}")

        raw.update(info)

        # --- negotiated version + legacy offering ---
        legacy_offered = await asyncio.to_thread(self._offers_legacy, domain)
        raw["legacy_offered"] = legacy_offered
        if legacy_offered:
            observed, band = f"offers {','.join(legacy_offered)}", "tls_10_or_11"
        elif info["version"] in ("TLSv1.2",):
            observed, band = "TLSv1.2 max", "only_tls_12"
        else:
            observed, band = info["version"], "tls_13"
        findings.append(
            Finding(
                source=self.source, signal="tls_version", subcategory=_SUB, category=_CAT,
                observed=observed,
                # `host_role` is what lets the critical ceiling stay legible through the fan-out.
                # The apex is stated EXPLICITLY rather than left implicit: once other hosts start
                # emitting findings, a finding with no role is ambiguous, and the ceiling must
                # never arm on an ambiguous one. See critical_ceiling.auto_signal_scope.
                value={"band": band, "negotiated": info["version"],
                       "legacy_offered": legacy_offered, "host_role": "apex"},
                locator=f"{domain}:443",
            )
        )

        # --- certificate expiry ---
        findings.append(self._cert_finding(info.get("days_to_expiry"), info.get("not_after_iso"), domain))

        return self.result(vendor, "ok", raw=raw, findings=findings, source_version="live")

    # ------------------------------------------------------------------ helpers

    def _handshake(self, domain: str) -> dict[str, Any]:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                version = ssock.version() or "unknown"
                cipher = ssock.cipher()
        not_after = cert.get("notAfter") if cert else None
        expiry = self._parse_cert_time(not_after) if not_after else None
        days = (expiry - datetime.now(UTC)).days if expiry else None
        return {
            "version": version,
            "cipher": cipher[0] if cipher else None,
            "not_after_raw": not_after,
            "not_after_iso": expiry.isoformat() if expiry else None,
            "days_to_expiry": days,
        }

    @staticmethod
    def _offers_legacy(domain: str) -> list[str]:
        """Probe whether the server will negotiate TLS 1.0/1.1 (deprecated)."""
        offered: list[str] = []
        for name, ver in _LEGACY.items():
            try:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                ctx.minimum_version = ver
                ctx.maximum_version = ver
                with socket.create_connection((domain, 443), timeout=5) as sock:
                    with ctx.wrap_socket(sock, server_hostname=domain):
                        offered.append(name)
            except (OSError, ssl.SSLError, ValueError):
                continue
        return offered

    @staticmethod
    def _parse_cert_time(value: str) -> datetime:
        # OpenSSL format: 'Jun  1 12:00:00 2027 GMT'
        return datetime.strptime(value, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=UTC)

    @classmethod
    def _cert_finding(cls, days: int | None, not_after_iso: str | None, domain: str) -> Finding:
        """Build the cert_validity Finding. Kept separate from the network handshake so the
        band-key mapping is testable without a socket — the swap this replaced silently
        dropped the CRITICAL expired-cert band and disabled the knockout floor in production."""
        observed, band = cls._cert_band(days)
        return Finding(
            source=cls.source, signal="cert_validity", subcategory=_SUB, category=_CAT,
            # `host_role: apex` stated explicitly: this is the ONLY signal that arms the critical
            # ceiling, and once other hosts emit cert findings a role-less one is ambiguous. The
            # ceiling must never arm on ambiguity — see critical_ceiling.auto_signal_scope.
            observed=observed,
            value={"band": band, "days_to_expiry": days, "host_role": "apex"},
            event_date=datetime.fromisoformat(not_after_iso) if not_after_iso else None,
            locator=f"{domain}:443 leaf cert",
        )

    @staticmethod
    def _cert_band(days: int | None) -> tuple[str, str]:
        if days is None:
            return "unknown", "valid"
        if days < 0:
            return "expired", "expired_serving_prod"   # feeds the knockout floor (§5.5.2)
        if days < 14:
            return f"expiring in {days}d", "expiring_lt_14d"
        if days < 30:
            return f"expiring in {days}d", "expiring_lt_30d"
        return f"valid ({days}d)", "valid"
