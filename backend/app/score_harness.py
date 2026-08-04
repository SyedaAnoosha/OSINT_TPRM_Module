"""End-to-end scoring harness — collect -> store -> score -> explainable breakdown.

    python -m app.score_harness --domain atlassian.com --ref atlassian --name Atlassian

Runs the real pipeline in order: collectors -> EVIDENCE STORE (first) -> scoring engine,
then prints the overall score with its quadrant and confidence, the per-category roll-up,
and the top signal contributions with their evidence refs (Finding A: every deduction is
traceable). Use --entity-confidence to simulate an ambiguous entity (gate).
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import httpx

# Windows consoles default to cp1252; force UTF-8 so status markers render.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

from .collectors import all_collectors
from .collectors.base import CollectorContext
from .config import get_settings
from .models import Vendor
from .ratelimit import RateLimiter
from .scoring import ScoringEngine
from .storage import get_store


async def collect_and_store(vendor: Vendor):  # noqa: ANN201
    settings = get_settings()
    store = get_store()
    results = []
    evidence_ids: dict[str, str] = {}
    async with httpx.AsyncClient(
        headers={"User-Agent": settings.user_agent}, timeout=settings.http_timeout_s, follow_redirects=True
    ) as http:
        ctx = CollectorContext(settings=settings, limiter=RateLimiter(), http=http)
        for collector in all_collectors():
            result = await collector.collect(vendor, ctx)
            ev = store.put(result)              # EVIDENCE STORE FIRST
            results.append(result)
            evidence_ids[result.source] = ev.id
    store.close()
    return results, evidence_ids


def print_score(vendor: Vendor, res) -> None:  # noqa: ANN001
    s = res.score
    print("\n" + "=" * 70)
    print(f"VENDOR: {vendor.name or vendor.ref}  ({vendor.domain})")
    print("=" * 70)
    if s.blocked:
        print(f"  STATUS: 🚫 BLOCKED — {s.blocked_reason}")
        print("  (no score emitted — routed to human adjudication)")
        return
    if s.refused:
        print(f"  STATUS: ⚠  INSUFFICIENT EVIDENCE — {s.blocked_reason}")
        print(f"  confidence {s.overall_confidence}  quadrant={s.quadrant}")
    else:
        print(f"  OVERALL RISK: {s.overall_risk}/100   CONFIDENCE: {s.overall_confidence}   "
              f"QUADRANT: {s.quadrant}")
    if s.knockout_applied:
        print(f"  ⛔ KNOCKOUT FLOOR applied — {s.knockout_cause}")

    print("\n  Category breakdown (risk | confidence | coverage | weight):")
    for c in sorted(s.categories, key=lambda c: -c.weight):
        risk = f"{c.risk:5.1f}" if c.risk is not None else "  —  "
        print(f"    {c.category:30} {risk} | conf {c.confidence:.2f} | cov {c.coverage:.2f} "
              f"| w {c.weight:>2}  [{len(c.contributing_finding_ids)} evidence]")

    print("\n  Top signal contributions (score — detail — evidence):")
    for sig in sorted(res.signal_scores, key=lambda x: -x.score)[:12]:
        crit = " ⛔CRITICAL" if sig.is_critical else ""
        ev = sig.evidence_ids[0][:8] if sig.evidence_ids else "—"
        print(f"    {sig.score:5.1f}  {sig.detail}{crit}  (ev {ev})")


def main() -> None:
    p = argparse.ArgumentParser(description="Collect, store, and score a vendor end-to-end.")
    p.add_argument("--domain")
    p.add_argument("--ref")
    p.add_argument("--name")
    p.add_argument("--entity-confidence", type=float, default=1.0,
                   help="simulate entity-resolution confidence (< 0.5 blocks)")
    args = p.parse_args()

    ref = args.ref or (args.domain.split(".")[0] if args.domain else "unknown")
    vendor = Vendor(ref=ref, name=args.name, domain=args.domain, resolved=True,
                    resolution_confidence=args.entity_confidence)

    results, evidence_ids = asyncio.run(collect_and_store(vendor))
    res = ScoringEngine().score(vendor, results, evidence_ids)
    print_score(vendor, res)


if __name__ == "__main__":
    main()
