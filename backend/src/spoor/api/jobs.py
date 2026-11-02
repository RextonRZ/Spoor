"""Background jobs with progress events for SSE (PRD §25). In-process for the hackathon build; the interface keeps a
durable queue (e.g. Celery/Redis) a drop-in replacement later."""

import threading
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from spoor.contracts import new_id


@dataclass
class Job:
    job_id: str
    kind: str
    owner: str
    status: Literal["queued", "running", "done", "failed"] = "queued"
    events: list[dict] = field(default_factory=list)
    result: Any = None
    error: str | None = None
    done: threading.Event = field(default_factory=threading.Event)

    def emit(self, message: str, **data: Any) -> None:
        self.events.append({"at": datetime.now(UTC).isoformat(), "message": message, **data})


KEEP_FINISHED = 200  # finished jobs (their events and results) kept for GET /v1/jobs; older ones are dropped


class JobRunner:
    def __init__(self, workers: int = 2, keep: int = KEEP_FINISHED):
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="spoor-job")
        self.jobs: dict[str, Job] = {}
        self.keep = keep

    def submit(self, kind: str, owner: str, fn: Callable[[Job], Any]) -> Job:
        # a long session ran hundreds of jobs and kept every result in memory; keep only the newest finished ones
        finished = [k for k, j in self.jobs.items() if j.done.is_set()]
        for k in finished[: max(0, len(finished) - self.keep + 1)]:
            del self.jobs[k]
        job = Job(new_id("job"), kind, owner)
        self.jobs[job.job_id] = job

        def run() -> None:
            job.status = "running"
            job.emit("started")
            try:
                job.result = fn(job)
                job.status = "done"
                job.emit("done")
            except Exception as e:  # noqa: BLE001 — a failed job is reported, never fabricated as success
                job.status, job.error = "failed", f"{type(e).__name__}: {e}"
                job.emit("failed", error=job.error, trace=traceback.format_exc()[-2000:])
            finally:
                job.done.set()

        self.pool.submit(run)
        return job
