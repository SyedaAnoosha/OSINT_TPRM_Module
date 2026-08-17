"""Collector base contract.

Every collector returns the same `CollectorResult` envelope, so the scoring engine
never knows or cares where data came from. The one guarantee that lives HERE, not in
each collector, is **failure isolation**: `collect()` wraps the real work in a timeout
and a catch-all, and always returns a `CollectorResult` — a timeout becomes
`status="timeout"`, an exception becomes `status="error"`, and "the source returned
nothing" is the collector's own `status="empty"`. A collector must never raise out of
`collect()`, because one dead source must not sink the whole assessment (project_plan
Phase 1: collectors are parallel and failure-isolated).

`status="empty"` is deliberately distinct from `"error"`: empty means "reached the
source, it had nothing for this vendor" and must reduce *confidence*, never *risk*
(methodology §5.4). Errors/timeouts reduce coverage too but flag a collection problem.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import Settings
from ..logging_config import get_logger
from ..models import CollectorResult, Finding, Vendor, utcnow
from ..ratelimit import RateLimiter

# HTTP statuses worth a retry — transient server/infrastructure states, never a definitive
# answer. A 404/403 is the source SAYING something and must not be retried (it wastes the
# vendor's rate budget and hides the real answer); a 502/503/504/429 is the source being
# briefly unavailable, which one short backoff usually clears.
_RETRY_STATUS = frozenset({502, 503, 504, 429})


@dataclass
class CollectorContext:
    """Shared, per-run collaborators handed to every collector."""

    settings: Settings
    limiter: RateLimiter
    http: httpx.AsyncClient | None = None  # dns/tls collectors do their own I/O

    # E12. The sampled host set, resolved ONCE per run and shared, rather than each collector
    # deriving its own. Two collectors that sample independently would probe different hosts and
    # publish two rates against two different denominators for the same estate — and a reader
    # comparing "8 of 340" against "2 of 290" has no way to know the populations differ.
    #
    # None means the estate was never resolved (no CT data, or `probe_cap: 1`), which every
    # collector must treat as apex-only. It is deliberately not an empty sample: "we did not fan
    # out" and "we fanned out and found nothing" are different facts.
    estate: Any = None

    # Domain age in days (from RDAP), used as a proxy for company age during collection.
    # This enables age-based reliability modifiers for clean receipts before operating_years
    # is computed during profile assembly. None if RDAP hasn't run or failed.
    domain_age_days: int | None = None


class Collector(ABC):
    """Base class. Subclasses implement `_run` (which MAY raise); `collect` isolates it."""

    source: str = "base"
    reliability: float = 0.5           # overridden per source (source_assessment.md)
    # Reliability of a CLEAN RECEIPT — a successful query that found nothing. Lower than
    # `reliability` because absence from a non-exhaustive corpus is weaker evidence than a
    # positive detection (methodology §5.4.2). Defaults to `reliability`; collectors that
    # emit "checked, clean" benign findings set it below that. None -> fall back to reliability.
    clean_reliability: float | None = None
    timeout_s: float = 15.0
    # Does this collector run in the SYNCHRONOUS on-demand scoring path? True for everything
    # that feeds a SCORED category. Set False for enrichment-only sources whose findings are
    # `held`/`ai_adjudicated` and therefore contribute nothing to the score — running them on
    # every request only adds latency and hammers an aggressively-throttled API (GDELT -> 429).
    # Those belong in Phase 5 scheduled enrichment, not the hot path.
    on_demand: bool = True
    # Per-request resilience (lever 1: collection reliability). A single transient blip on the
    # vendor's own site — a dropped connection, a momentary 503 — used to zero a whole source
    # for a run (the cause of a genuinely-clean vendor reading as the_ghost). Collectors that
    # hit HTTP fetch via `_get_with_retry` get a bounded retry with linear backoff. Off by
    # default (attempts=1) so nothing retries unless it opts in.
    http_attempts: int = 1
    http_backoff_s: float = 1.0

    @abstractmethod
    async def _run(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        """Do the real work. May raise; `collect` turns that into status='error'."""
        raise NotImplementedError

    async def collect(self, vendor: Vendor, ctx: CollectorContext) -> CollectorResult:
        log = get_logger(f"collector.{self.source}")
        try:
            result = await asyncio.wait_for(self._run(vendor, ctx), timeout=self.timeout_s)
            log.info("%s: %s (%d findings)", vendor.ref, result.status, len(result.findings))
            return result
        except TimeoutError:
            log.warning("%s: timeout after %.1fs", vendor.ref, self.timeout_s)
            return self.result(vendor, "timeout", notes=f"timed out after {self.timeout_s}s")
        except Exception as exc:  # noqa: BLE001 — deliberate catch-all: isolation is the point
            log.warning("%s: error %r", vendor.ref, exc)
            return self.result(vendor, "error", notes=f"{type(exc).__name__}: {exc}")

    def result(
        self,
        vendor: Vendor,
        status: str,
        *,
        raw: dict[str, Any] | None = None,
        findings: list[Finding] | None = None,
        source_version: str | None = None,
        notes: str | None = None,
        reliability: float | None = None,
    ) -> CollectorResult:
        """Build a CollectorResult stamped with this collector's identity/reliability.

        `reliability` overrides the class default for THIS result — used to stamp a clean
        receipt (a successful-but-empty query emitted as a benign finding) at the lower
        `clean_reliability`, so absence-of-evidence counts toward coverage honestly without
        borrowing the confidence of a positive detection (methodology §5.4.2).
        """
        return CollectorResult(
            source=self.source,
            vendor_ref=vendor.ref,
            status=status,  # type: ignore[arg-type]
            fetched_at=utcnow(),
            source_version=source_version,
            raw=raw,
            findings=findings or [],
            reliability=self.reliability if reliability is None else reliability,
            notes=notes,
        )

    def _clean_reliability(self, ctx: CollectorContext | None = None) -> float:
        """Reliability to stamp on a clean receipt — `clean_reliability` if set, else default.

        Age-based adjustment: For certain signals (HIBP, regulatory), a clean result from a
        very young company is weaker evidence than the same result from a mature company.
        This is a confidence modifier, not a posture modifier. The adjustment is applied
        only if the collector explicitly opts in via `age_adjusted_clean_reliability = True`.
        """
        base = self.reliability if self.clean_reliability is None else self.clean_reliability

        # Only apply age adjustment if the collector opts in and we have age data
        if not getattr(self, "age_adjusted_clean_reliability", False):
            return base

        if ctx is None or ctx.domain_age_days is None:
            return base

        # Convert domain age to years
        years = ctx.domain_age_days / 365.25

        # Age-based reliability adjustment:
        # - Under 3 years: reduce clean reliability by 30% (weak evidence)
        # - 3-10 years: reduce by 15% (moderate evidence)
        # - 10+ years: no reduction (strong evidence)
        if years < 3:
            return base * 0.7
        elif years < 10:
            return base * 0.85
        else:
            return base

    async def _get_with_retry(
        self,
        ctx: CollectorContext,
        url: str,
        *,
        limiter_key: str,
        attempts: int | None = None,
        backoff_s: float | None = None,
        **kwargs: Any,
    ) -> httpx.Response | None:
        """GET with bounded retry + linear backoff on TRANSIENT failure only.

        Retries on connection/timeout errors and on `_RETRY_STATUS` responses; a definitive
        answer (2xx/3xx/4xx) returns immediately without retrying. Rate-limited per attempt on
        `limiter_key` so a retry still respects the source's ceiling. Returns the final Response
        (which may itself be a retryable-status response on the last attempt) or None if every
        attempt raised. Never raises — the isolation contract in `collect` is preserved.
        """
        assert ctx.http is not None, "_get_with_retry needs an http client in context"
        n = self.http_attempts if attempts is None else attempts
        base = self.http_backoff_s if backoff_s is None else backoff_s
        log = get_logger(f"collector.{self.source}")
        resp: httpx.Response | None = None
        for attempt in range(1, n + 1):
            await ctx.limiter.acquire(limiter_key)
            try:
                resp = await ctx.http.get(url, **kwargs)
            except httpx.HTTPError as exc:
                resp = None
                last = type(exc).__name__
            else:
                if resp.status_code not in _RETRY_STATUS:
                    return resp  # definitive answer — done
                last = f"HTTP {resp.status_code}"
            if attempt < n:
                log.info("%s: transient %s, retry %d/%d", url, last, attempt, n)
                await asyncio.sleep(base * attempt)
        return resp
