"""In-memory job manager — async scoring runs + SSE progress fan-out.

A scoring run is long (a dozen live collectors), so the API accepts a request, returns a
job id immediately (202), and streams progress over SSE as each source lands — the
"speed to answer" the brief asks for. This is deliberately in-memory: the PoC scores on
demand and the *durable* record is the evidence store + persisted Score, not the job. A
platform build would back jobs with a queue; that is out of scope (project_plan §2).

Fan-out is race-free by construction: a subscriber snapshots past events and registers its
queue in one synchronous step (no `await` between), so under asyncio's cooperative
scheduling no event can slip in between the snapshot and the subscription — no gaps, no dups.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any, Literal

from .logging_config import get_logger
from .models import Vendor, utcnow
from .pipeline import run_pipeline
from .scoring.engine import ScoreResult

log = get_logger("jobs")

JobStatus = Literal["pending", "running", "done", "error"]
_END = "_end"  # internal sentinel that closes an SSE stream


@dataclass
class Job:
    id: str
    vendor_ref: str
    status: JobStatus = "pending"
    created_at: str = field(default_factory=lambda: utcnow().isoformat())
    finished_at: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    result: ScoreResult | None = None
    error: str | None = None

    def public(self) -> dict[str, Any]:
        s = self.result.score if self.result else None
        return {
            "job_id": self.id, "vendor_ref": self.vendor_ref, "status": self.status,
            "created_at": self.created_at, "finished_at": self.finished_at,
            "error": self.error,
            "score": s.model_dump(mode="json") if s else None,
        }


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def submit(self, vendor: Vendor, **context: Any) -> Job:
        """`context` carries the CLIENT-SUPPLIED fields (criticality, size_band, sector) through to
        the profile. They are kept out of the `Vendor` model deliberately: `Vendor` is the resolved
        identity, and what a buyer knows about their own exposure is not part of who the company is.
        """
        job = Job(id=uuid.uuid4().hex, vendor_ref=vendor.ref)
        self._jobs[job.id] = job
        asyncio.create_task(self._run(job, vendor, **context))
        return job

    async def _run(self, job: Job, vendor: Vendor, **context: Any) -> None:
        job.status = "running"
        try:
            job.result = await run_pipeline(vendor, progress=self._progress(job), **context)
            job.status = "done"
        except Exception as exc:  # noqa: BLE001 — a job failure must not crash the server
            log.warning("job %s failed: %r", job.id, exc)
            job.status = "error"
            job.error = f"{type(exc).__name__}: {exc}"
            self._publish(job, "error", {"message": job.error})
        finally:
            job.finished_at = utcnow().isoformat()
            self._publish(job, _END, {})

    def _progress(self, job: Job):  # noqa: ANN202
        async def progress(event: str, payload: dict[str, Any]) -> None:
            self._publish(job, event, payload)
        return progress

    def _publish(self, job: Job, event: str, payload: dict[str, Any]) -> None:
        item = {"event": event, "data": payload}
        if event != _END:
            job.events.append(item)
        for q in list(job.subscribers):
            q.put_nowait(item)

    async def stream(self, job: Job) -> AsyncGenerator[dict[str, Any], None]:
        """Yield past events (replay) then live events until the job ends."""
        q: asyncio.Queue = asyncio.Queue()
        # Snapshot + subscribe in one synchronous step — no await between, so race-free.
        replay = list(job.events)
        already_finished = job.status in ("done", "error")
        job.subscribers.add(q)
        try:
            for item in replay:
                yield item
            if already_finished:
                return
            while True:
                item = await q.get()
                if item["event"] == _END:
                    return
                yield item
        finally:
            job.subscribers.discard(q)


jobs = JobManager()
