"""DNS collector — the thin vertical slice, DMARC first.

DMARC is the sharpest cheap signal available and, uniquely, gradeable on a real scale
(methodology §5.3): absent -> p=none (monitoring only) -> p=quarantine -> p=reject.
It ties straight to business email compromise, which a breach-trained model under-weights
(§5.6.2, open item 11) — which is exactly why we weight it.

Honesty rule enforced here: **absence is only a finding where absence is knowable.**
DMARC/SPF live at one well-known name, so their absence is real evidence and scores.
DKIM needs a *selector* we cannot enumerate; failing to guess it is NOT evidence of
absence, so a not-found DKIM emits an *inconclusive* finding (no penalty) and simply
lowers coverage/confidence — never risk (§5.4).
"""

from __future__ import annotations

import asyncio
from typing import Any

import dns.asyncresolver
import dns.rdatatype
import dns.resolver

from ..models import CollectorResult, Finding, Vendor
from .base import Collector, CollectorContext

_CAT = "cyber_hygiene_technical"
# common DKIM selectors — presence is conclusive, absence is not
_DKIM_SELECTORS = ("google", "default", "selector1", "selector2", "k1", "dkim", "s1", "mail", "smtp")


class DnsCollector(Collector):
    source = "dns"
    reliability = 0.95  # source_assessment.md §2 — authoritative, real-time
    timeout_s = 20.0
    # Lever 1: a resolver timeout / transient SERVFAIL used to return "no record", which reads
    # as a missing control (absent DMARC/DNSSEC) — a wobble masquerading as a finding. Retry the
    # TRANSIENT failures only; NXDOMAIN/NoAnswer are definitive answers and are never retried.
    _DNS_ATTEMPTS = 2
    _DNS_BACKOFF_S = 0.5

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        domain = vendor.domain
        if not domain:
            return self.result(vendor, "empty", notes="no domain to resolve")

        resolver = dns.asyncresolver.Resolver()
        resolver.lifetime = 8.0
        resolver.timeout = 4.0

        raw: dict[str, Any] = {"domain": domain}
        findings: list[Finding] = []

        # --- DMARC: _dmarc.<domain> TXT, tag p= drives the ladder ---
        dmarc_txt = await self._txt(resolver, f"_dmarc.{domain}")
        raw["dmarc_txt"] = dmarc_txt
        dmarc_record = next((t for t in dmarc_txt if t.lower().startswith("v=dmarc1")), None)
        policy = self._dmarc_policy(dmarc_record)
        raw["dmarc_policy"] = policy
        findings.append(
            Finding(
                source=self.source, signal="dmarc", subcategory="email_authentication", category=_CAT,
                observed=policy, value={"policy": policy, "record": dmarc_record},
                locator=f"_dmarc.{domain} TXT",
                notes="no DMARC record" if policy == "absent" else None,
            )
        )

        # --- SPF: <domain> TXT with v=spf1, 'all' qualifier ---
        root_txt = await self._txt(resolver, domain)
        raw["root_txt"] = root_txt
        spf_record = next((t for t in root_txt if t.lower().startswith("v=spf1")), None)
        spf_state = self._spf_state(spf_record)
        raw["spf_state"] = spf_state
        findings.append(
            Finding(
                source=self.source, signal="spf", subcategory="email_authentication", category=_CAT,
                observed=spf_state, value={"state": spf_state, "record": spf_record},
                locator=f"{domain} TXT",
            )
        )

        # --- DKIM: presence is conclusive; not-found is INCONCLUSIVE (no penalty) ---
        dkim_selector = await self._find_dkim(resolver, domain)
        raw["dkim_selector"] = dkim_selector
        if dkim_selector:
            findings.append(
                Finding(
                    source=self.source, signal="dkim", subcategory="email_authentication", category=_CAT,
                    observed="present", value={"selector": dkim_selector},
                    locator=f"{dkim_selector}._domainkey.{domain} TXT",
                )
            )
        else:
            # No finding that scores. Recorded so the gap is visible, but it lowers
            # coverage/confidence — never risk. We could not enumerate the selector.
            raw["dkim_note"] = "no DKIM found via common selectors — inconclusive, not scored"

        # --- DNSSEC: DNSKEY presence (deployment signal, not full validation) ---
        dnskey = await self._has_records(resolver, domain, "DNSKEY")
        raw["dnssec_dnskey_present"] = dnskey
        findings.append(
            Finding(
                source=self.source, signal="dnssec", subcategory="dns_infrastructure", category=_CAT,
                observed="valid" if dnskey else "absent",
                value={"dnskey_present": dnskey},
                locator=f"{domain} DNSKEY",
                notes=None if dnskey else "no DNSKEY — DNSSEC not deployed (presence check, not validation)",
            )
        )

        # --- CAA: <domain> CAA restricts which CAs may issue ---
        caa = await self._has_records(resolver, domain, "CAA")
        raw["caa_present"] = caa
        findings.append(
            Finding(
                source=self.source, signal="caa", subcategory="dns_infrastructure", category=_CAT,
                observed="present" if caa else "absent", value={"present": caa},
                locator=f"{domain} CAA",
            )
        )

        # --- MX: contextual only (does the domain even send mail?) — stored, not scored ---
        raw["mx"] = await self._records(resolver, domain, "MX")

        return self.result(vendor, "ok", raw=raw, findings=findings, source_version="live")

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _dmarc_policy(record: str | None) -> str:
        if not record:
            return "absent"
        tags = {
            k.strip().lower(): v.strip().lower()
            for k, _, v in (part.partition("=") for part in record.split(";"))
            if k.strip()
        }
        p = tags.get("p", "none")
        return {"reject": "p_reject", "quarantine": "p_quarantine", "none": "p_none"}.get(p, "p_none")

    @staticmethod
    def _spf_state(record: str | None) -> str:
        if not record:
            return "absent"
        low = record.lower()
        if "-all" in low:
            return "hardfail_all"
        if "~all" in low:
            return "softfail_all"
        # ?all / +all / no 'all' — permissive; treat as soft (still better than none)
        return "softfail_all"

    async def _txt(self, resolver: dns.asyncresolver.Resolver, name: str) -> list[str]:
        records = await self._records(resolver, name, "TXT")
        # TXT rdata come quoted and possibly chunked; join and strip quotes.
        return [r.replace('" "', "").strip('"') for r in records]

    async def _records(self, resolver: dns.asyncresolver.Resolver, name: str, rdtype: str) -> list[str]:
        for attempt in range(1, self._DNS_ATTEMPTS + 1):
            try:
                answer = await resolver.resolve(name, rdtype)
                return [r.to_text() for r in answer]
            except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
                return []  # definitive: the name genuinely has no such record — retry wouldn't help
            except (dns.resolver.NoNameservers, dns.resolver.LifetimeTimeout):
                # transient: SERVFAIL / timeout — one short backoff usually clears it
                if attempt < self._DNS_ATTEMPTS:
                    await asyncio.sleep(self._DNS_BACKOFF_S)
                    continue
                return []
        return []

    async def _has_records(self, resolver: dns.asyncresolver.Resolver, name: str, rdtype: str) -> bool:
        return len(await self._records(resolver, name, rdtype)) > 0

    async def _find_dkim(self, resolver: dns.asyncresolver.Resolver, domain: str) -> str | None:
        for sel in _DKIM_SELECTORS:
            txt = await self._txt(resolver, f"{sel}._domainkey.{domain}")
            if any("dkim1" in t.lower() or "p=" in t.lower() for t in txt):
                return sel
        return None
