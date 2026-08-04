"""Per-host async rate limiting.

Firing every collector concurrently with `asyncio.gather` does NOT throttle anything —
EDGAR's requests would race past its ~10 req/s ceiling and the IP gets a ~10-minute ban
(project_plan.md Phase 1 note). So each host gets its own token bucket, keyed by
hostname, and collectors `await limiter.acquire(host)` before every request.

Defaults are deliberately polite. EDGAR is throttled below its stated ceiling; crt.sh
has no stated limit so we self-limit hard.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

# requests-per-second ceilings per host. Conservative on purpose.
DEFAULT_RATES: dict[str, float] = {
    "www.sec.gov": 8.0,        # stated ceiling 10/s — stay under it
    "data.sec.gov": 8.0,
    "crt.sh": 1.0,             # no stated limit -> self-limit hard (unstated-ToS caveat)
    "services.nvd.nist.gov": 1.0,   # ~5/30s without a key; 1/s is safe
    "api.gdeltproject.org": 0.2,  # GDELT throttles aggressively (429s) — 1 req / 5s
    "haveibeenpwned.com": 1.0,
    "search.marginalia.nu": 1.0,
    "_default": 4.0,
}


@dataclass
class _Bucket:
    rate: float                       # tokens per second
    capacity: float                   # burst size
    tokens: float
    updated: float
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class RateLimiter:
    """A collection of per-host token buckets shared across a run."""

    def __init__(self, rates: dict[str, float] | None = None) -> None:
        self._rates = rates or DEFAULT_RATES
        self._buckets: dict[str, _Bucket] = {}

    def _bucket(self, host: str) -> _Bucket:
        if host not in self._buckets:
            rate = self._rates.get(host, self._rates["_default"])
            # capacity == rate: allow a modest 1-second burst, then steady-state.
            self._buckets[host] = _Bucket(
                rate=rate, capacity=max(1.0, rate), tokens=max(1.0, rate), updated=time.monotonic()
            )
        return self._buckets[host]

    async def acquire(self, host: str) -> None:
        """Block until a token is available for `host`, then consume it."""
        bucket = self._bucket(host)
        async with bucket.lock:
            while True:
                now = time.monotonic()
                elapsed = now - bucket.updated
                bucket.tokens = min(bucket.capacity, bucket.tokens + elapsed * bucket.rate)
                bucket.updated = now
                if bucket.tokens >= 1.0:
                    bucket.tokens -= 1.0
                    return
                deficit = (1.0 - bucket.tokens) / bucket.rate
                await asyncio.sleep(deficit)
