"""E12 — the estate probe. The second wave, and the reason there is a second wave at all.

WHY THIS IS NOT PART OF THE TLS COLLECTOR. The estate is derived from certificate transparency,
and every collector in the first wave runs CONCURRENTLY — so at the moment the TLS collector starts,
the CT result does not exist. A collector that wanted the estate would have to fetch CT itself,
which means querying someone else's free service twice for one answer, and two collectors sampling
independently would probe different hosts and publish two rates against two different denominators
for the same estate. A reader comparing *"8 of 340"* with *"2 of 290"* has no way to know the
populations differ.

So the estate is resolved ONCE, between the waves, and shared on the context.

THIS IS ALSO THE HONEST SHAPE OF THE PHASE. Fan-out is a budgeted activity — it multiplies every
probe by the cap against services nobody is paying for — and a budgeted activity belongs in its own
pass where its cost is visible, not folded into a collector that used to make one connection.

AT `probe_cap: 1` THIS COLLECTOR DOES NOT RUN. That is exactly the pre-E12 behaviour: apex only,
one handshake, no extra traffic. The pipeline skips the whole wave.

IT EMITS A RATE, NEVER ONE FINDING PER HOST. `tls_version` is banded per observation, so N per-host
findings would be N charges for one weakness — E7c's root-cause problem multiplied by the estate
size. The shape emitted here (`count` + `denominator`) is exactly what E6's exposure branch already
consumes, so this signal bands on a rate the day it is added to `exposure:` with no new mechanism.

WHAT LEAVES THE DENOMINATOR: any host we could not reach. A name we failed to connect to is not a
name that passed and not a name that failed — the same rule the engine applies to an unchecked
signal, and the same rule E12's design record fixes for liveness.
"""

from __future__ import annotations

import asyncio
import ssl
from typing import Any

from ..models import CollectorResult, Finding, Vendor
from ..scoring_config import get_scoring_config
from .base import Collector, CollectorContext
from .tls_collector import TlsCollector

_CAT = "cyber_hygiene_technical"
_SUB = "transport_security"


class EstateCollector(Collector):
    """Probes the sampled non-apex estate. Runs in the second wave, only when the cap allows."""

    source = "estate"
    # Direct observation, same as the apex handshake — but one step down, because a SAMPLE is
    # weaker evidence about an estate than a full census, and the reliability figure is where that
    # belongs rather than buried in a caveat.
    reliability = 0.85
    timeout_s = 120.0
    # Not in the first wave. The pipeline invokes it explicitly once `ctx.estate` is resolved;
    # leaving it on the default schedule would run it before the estate exists.
    on_demand = False

    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        sample = ctx.estate
        if sample is None:
            return self.result(vendor, "empty",
                               notes="no estate resolved — apex-only run (probe_cap 1, or no CT data)")
        if sample.denominator <= 1:
            return self.result(vendor, "empty", notes=sample.rule())

        apex = sample.apex
        base_cap = get_scoring_config().estate_probe_cap()

        # Age-based probe cap adjustment: mature vendors have broader CT history and more
        # potential shadow assets. Young vendors have thin estates, so probing deeper yields
        # diminishing returns. Use domain age as a proxy for company age.
        age_adjusted_cap = base_cap
        if ctx.domain_age_days is not None:
            years = ctx.domain_age_days / 365.25
            if years >= 10:
                # Mature vendor: double the cap to detect shadow assets from long history
                age_adjusted_cap = base_cap * 2
            elif years >= 3:
                # Established vendor: 50% increase
                age_adjusted_cap = int(base_cap * 1.5)
            # Under 3 years: use base cap (young vendors have thin estates)

        # Re-sample the estate with the age-adjusted cap
        from ..collectors.estate import build_estate
        cfg = get_scoring_config()
        spec = cfg.estate_spec()
        adjusted_sample = build_estate(
            vendor.ref, vendor.domain, sample.probed_names,
            cap=age_adjusted_cap,
            wildcard_seen=sample.wildcard_seen,
            sibling_threshold=int(spec.get("tenant_sibling_threshold", 25)),
            is_live=None,
        )

        legacy_hosts: list[str] = []
        expired_hosts: list[str] = []
        reached = 0

        for host in adjusted_sample.probed_names:
            if host == apex:
                continue          # the apex has its own findings and its own ceiling semantics
            try:
                offered = await asyncio.to_thread(TlsCollector._offers_legacy, host)
                info = await asyncio.to_thread(TlsCollector._handshake, host)
            except (OSError, ssl.SSLError, ValueError):
                continue          # unreachable -> leaves the denominator entirely
            reached += 1
            if offered:
                legacy_hosts.append(host)
            days = info.get("days_to_expiry")
            if days is not None and days < 0:
                expired_hosts.append(host)

        raw: dict[str, Any] = {
            "rule": adjusted_sample.rule(), "base_cap": base_cap, "age_adjusted_cap": age_adjusted_cap,
            "sampled": adjusted_sample.denominator, "reached": reached,
            "eligible": adjusted_sample.eligible, "discovered": adjusted_sample.discovered,
            "tenants_excluded": adjusted_sample.tenants_excluded,
            "not_live_excluded": adjusted_sample.not_live_excluded,
            "legacy_hosts": sorted(legacy_hosts)[:50], "expired_hosts": sorted(expired_hosts)[:50],
        }
        if reached == 0:
            return self.result(vendor, "empty", raw=raw,
                               notes=f"no sampled host could be reached. {adjusted_sample.rule()}")

        findings = [
            self._rate("estate_tls_legacy", len(legacy_hosts), reached, adjusted_sample,
                       f"{len(legacy_hosts)} of {reached} probed hosts still offer TLS 1.0/1.1"),
            self._rate("estate_cert_expired", len(expired_hosts), reached, adjusted_sample,
                       f"{len(expired_hosts)} of {reached} probed hosts serve an expired certificate"),
        ]
        return self.result(vendor, "ok", raw=raw, findings=findings, source_version="live")

    def _rate(self, signal: str, count: int, denominator: int, sample: Any,
              observed: str) -> Finding:
        """One rate finding, carrying its denominator AND the rule that produced it.

        `host_role: estate` is what keeps this out of the critical ceiling. An expired certificate
        somewhere in a 400-host estate must never cap the vendor at the top of Grade D — that is
        the any-host failure E12's design record rejects, and the role field is how the normaliser
        knows the difference.
        """
        return Finding(
            source=self.source, signal=signal, subcategory=_SUB, category=_CAT,
            observed=observed,
            value={"count": count, "denominator": denominator,
                   "host_role": "estate", "rule": sample.rule()},
            locator=f"{sample.apex} (estate sample of {denominator} reached hosts)",
            notes=sample.rule(),
        )
