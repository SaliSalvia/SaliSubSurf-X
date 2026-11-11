"""Thread-safe background job registry for deep-processing runs.

Deep analyses run on a single-worker executor (they are CPU/RAM heavy); job
state is kept in memory with a lock and artifacts on disk. Completed jobs are
retained up to ``MAX_RETAINED`` — the oldest are pruned together with their
artifact directories.
"""

from __future__ import annotations

import logging
import shutil
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .outputs import job_dir
from .pipeline import DeepParams, data_dir, new_job_id, run_live, run_selftest

log = logging.getLogger("subsurface_api.deep.jobs")

MAX_RETAINED = 20
# Deep runs are CPU/RAM heavy; a bounded active queue keeps one caller from exhausting
# the worker's memory or starving every other request.
MAX_ACTIVE_JOBS = 4


class QueueFull(RuntimeError):
    """Raised when the active deep-processing queue has no free slot."""


@dataclass
class Job:
    job_id: str
    mode: str
    status: str = "queued"          # queued | running | done | error
    progress: int = 0
    stage: str = "queued"
    created_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    params: Dict = field(default_factory=dict)
    error: Optional[str] = None
    report: Optional[Dict] = None
    _dir: str = ""

    def public(self) -> Dict:
        return {
            "job_id": self.job_id,
            "mode": self.mode,
            "status": self.status,
            "progress": self.progress,
            "stage": self.stage,
            "created_utc": self.created_utc,
            "params": self.params,
            "error": self.error,
        }


class JobManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, Job] = {}
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="deep")

    # ------------------------------------------------------------------ api

    def submit(self, params: DeepParams, mode: str) -> str:
        job_id = new_job_id()
        job = Job(
            job_id=job_id,
            mode=mode,
            params={
                "date_from": params.date_from,
                "date_to": params.date_to,
                "grid": params.grid,
                "max_cloud_percent": params.max_cloud_percent,
                "max_dates": params.max_dates,
                "model": params.model,
                "fusion_mode": params.fusion_mode,
                "n_surrogates": params.n_surrogates,
                "alpha": params.alpha,
                "resolution_m": params.resolution_m,
            },
        )
        with self._lock:
            active = sum(
                1 for j in self._jobs.values() if j.status in ("queued", "running")
            )
            if active >= MAX_ACTIVE_JOBS:
                raise QueueFull(
                    f"Deep-processing queue is full ({active} active jobs); retry shortly."
                )
            job._dir = job_dir(data_dir(), job_id)
            self._jobs[job_id] = job
            self._prune_locked()
        self._pool.submit(self._worker, job, params, mode)
        return job_id

    def shutdown(self) -> None:
        """Stop accepting work; queued futures are cancelled, running work is left to finish."""
        self._pool.shutdown(wait=False, cancel_futures=True)

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> List[Dict]:
        with self._lock:
            return [j.public() for j in sorted(self._jobs.values(), key=lambda j: j.created_utc)]

    def job_dir_of(self, job_id: str) -> Optional[str]:
        job = self.get(job_id)
        return job._dir if job else None

    # -------------------------------------------------------------- internal

    def _progress(self, job: Job):
        def cb(pct: int, stage: str) -> None:
            with self._lock:
                job.progress = int(max(0, min(100, pct)))
                job.stage = stage
        return cb

    def _worker(self, job: Job, params: DeepParams, mode: str) -> None:
        with self._lock:
            job.status = "running"
            job.stage = "starting"
        try:
            ring = [(float(p_[0]), float(p_[1])) for p_ in params.polygon]
            if mode == "selftest":
                report = run_selftest(params, ring, self._progress(job), job._dir)
            else:
                report = run_live(params, ring, self._progress(job), job._dir)
            with self._lock:
                job.report = report
                job.status = "done"
                job.progress = 100
                job.stage = "done"
        except Exception as exc:  # noqa: BLE001 — jobs must never crash the executor
            log.error("deep job %s failed: %s\n%s", job.job_id, exc, traceback.format_exc())
            with self._lock:
                job.status = "error"
                job.stage = "error"
                job.error = str(exc)

    def _prune_locked(self) -> None:
        done = [j for j in self._jobs.values() if j.status in ("done", "error")]
        if len(done) <= MAX_RETAINED:
            return
        done.sort(key=lambda j: j.created_utc)
        for job in done[: len(done) - MAX_RETAINED]:
            shutil.rmtree(job._dir, ignore_errors=True)
            self._jobs.pop(job.job_id, None)


manager = JobManager()
