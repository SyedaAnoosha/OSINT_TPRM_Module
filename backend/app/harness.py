"""Phase 1 harness — run collectors against a vendor, store to evidence, print findings.

    python -m app.harness --domain atlassian.com --ref atlassian
    python -m app.harness --domain atlassian.com --only dns

This is the thin end-to-end proof: collector -> CollectorResult -> EVIDENCE STORE (first)
-> findings printed. It writes to the real evidence DB so you can confirm rows land and
verify byte-identical afterwards.
"""

from __future__ import annotations

import argparse
import asyncio

import httpx

from .collectors import all_collectors, get_collector
from .collectors.base import Collector, CollectorContext
from .config import get_settings
from .logging_config import get_logger
from .models import Vendor
from .ratelimit import RateLimiter
from .storage import get_store

log = get_logger("harness")


async def run(vendor: Vendor, collectors: list[Collector]) -> None:
    settings = get_settings()
    limiter = RateLimiter()
    store = get_store()
    async with httpx.AsyncClient(
        headers={"User-Agent": settings.user_agent}, timeout=settings.http_timeout_s, follow_redirects=True
    ) as http:
        ctx = CollectorContext(settings=settings, limiter=limiter, http=http)
        for collector in collectors:
            result = await collector.collect(vendor, ctx)
            evidence = store.put(result)  # EVIDENCE STORE FIRST — before any scoring
            _print_result(collector.source, result, evidence.id)
    store.close()


def _print_result(source: str, result, evidence_id: str) -> None:  # noqa: ANN001
    print(f"\n=== {source}  [{result.status}]  reliability={result.reliability}  ev={evidence_id[:8]}")
    if result.source_version:
        print(f"    source_version: {result.source_version}")
    if result.notes:
        print(f"    notes: {result.notes}")
    if not result.findings:
        print("    (no scoring findings)")
    for f in result.findings:
        loc = f" @ {f.locator}" if f.locator else ""
        note = f"  — {f.notes}" if f.notes else ""
        print(f"    - {f.subcategory or '?'}/{f.signal} = {f.observed}{loc}{note}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OSINT collectors against a vendor.")
    parser.add_argument("--domain", help="vendor domain, e.g. atlassian.com")
    parser.add_argument("--ref", help="canonical vendor ref (slug); defaults from domain")
    parser.add_argument("--name", help="vendor display name")
    parser.add_argument("--only", help="run a single collector by source id, e.g. dns")
    args = parser.parse_args()

    ref = args.ref or (args.domain.split(".")[0] if args.domain else "unknown")
    vendor = Vendor(ref=ref, name=args.name, domain=args.domain, resolved=True, resolution_confidence=1.0)

    if args.only:
        c = get_collector(args.only)
        if not c:
            raise SystemExit(f"no collector registered for {args.only!r}")
        collectors = [c]
    else:
        collectors = all_collectors()

    asyncio.run(run(vendor, collectors))


if __name__ == "__main__":
    main()
