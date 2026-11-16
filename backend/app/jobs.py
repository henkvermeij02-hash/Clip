"""Persistent background job queue.

Jobs are rows in the ``jobs`` table, so they survive restarts:

* On startup, jobs that were ``running`` when the app stopped are put back to
  ``queued`` and run again (handlers must therefore be safe to re-run).
* A ``dedupe_key`` stops the same work being queued twice while it is pending.
* Unexpected errors are retried with a growing delay up to ``max_attempts``.
  A :class:`JobError` is a known, user-facing failure and is not retried.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from . import db

log = logging.getLogger("gtastudio.jobs")

ACTIVE_STATUSES = ("queued", "running")


class JobError(Exception):
    """A failure with a message that is safe and useful to show the user."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class JobCancelled(Exception):
    pass


@dataclass
class JobContext:
    job_id: int
    video_id: int | None
    payload: dict[str, Any]
    attempt: int

    def progress(self, fraction: float, message: str | None = None) -> None:
        fraction = max(0.0, min(1.0, float(fraction)))
        with db.connect() as conn:
            row = conn.execute(
                "UPDATE jobs SET progress = ?, message = COALESCE(?, message), updated_at = ? "
                "WHERE id = ? RETURNING status",
                (fraction, message, db.utcnow(), self.job_id),
            ).fetchone()
        if row is not None and row["status"] == "cancelled":
            raise JobCancelled()


@dataclass
class HandlerSpec:
    run: Callable[[JobContext], dict[str, Any] | None]
    on_failure: Callable[[JobContext, str], None] | None = None
    label: str = ""


HANDLERS: dict[str, HandlerSpec] = {}


def register(job_type: str, label: str, on_failure: Callable[[JobContext, str], None] | None = None):
    def decorator(func: Callable[[JobContext], dict[str, Any] | None]):
        HANDLERS[job_type] = HandlerSpec(run=func, on_failure=on_failure, label=label)
        return func

    return decorator


def job_to_dict(row: sqlite3.Row | dict | None) -> dict[str, Any] | None:
    if row is None:
        return None
    job = dict(row)
    job["payload"] = db.loads(job.pop("payload_json", None), {})
    job["result"] = db.loads(job.pop("result_json", None))
    spec = HANDLERS.get(job["type"])
    job["label"] = spec.label if spec else job["type"]
    return job


def enqueue(
    job_type: str,
    *,
    video_id: int | None = None,
    payload: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
    priority: int = 100,
    max_attempts: int = 3,
    conn: sqlite3.Connection | None = None,
) -> tuple[dict[str, Any], bool]:
    """Queue a job. Returns ``(job, created)``; if an identical job is already
    queued or running it is returned instead with ``created=False``."""
    if job_type not in HANDLERS:
        raise ValueError(f"Unknown job type '{job_type}'")
    now = db.utcnow()

    def _insert(c: sqlite3.Connection) -> tuple[dict[str, Any], bool]:
        try:
            row = c.execute(
                "INSERT INTO jobs (type, video_id, payload_json, dedupe_key, priority, max_attempts, "
                "created_at, updated_at, message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Waiting to start') "
                "RETURNING *",
                (job_type, video_id, db.dumps(payload or {}), dedupe_key, priority, max_attempts, now, now),
            ).fetchone()
            return job_to_dict(row), True  # type: ignore[return-value]
        except sqlite3.IntegrityError:
            existing = c.execute(
                "SELECT * FROM jobs WHERE dedupe_key = ? AND status IN ('queued', 'running')",
                (dedupe_key,),
            ).fetchone()
            if existing is None:
                raise
            return job_to_dict(existing), False  # type: ignore[return-value]

    if conn is not None:
        return _insert(conn)
    with db.connect() as c:
        return _insert(c)


def get(job_id: int) -> dict[str, Any] | None:
    with db.connect() as conn:
        return job_to_dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())


def recover_interrupted() -> int:
    """Put jobs that were running when the app stopped back in the queue."""
    with db.connect() as conn:
        cur = conn.execute(
            "UPDATE jobs SET status = 'queued', message = 'Resuming after restart', "
            "attempts = MAX(attempts - 1, 0), updated_at = ? WHERE status = 'running'",
            (db.utcnow(),),
        )
        return cur.rowcount


def _claim_next() -> dict[str, Any] | None:
    now = db.utcnow()
    with db.transaction() as conn:
        row = conn.execute(
            "SELECT id FROM jobs WHERE status = 'queued' AND (run_after IS NULL OR run_after <= ?) "
            "ORDER BY priority, id LIMIT 1",
            (now,),
        ).fetchone()
        if row is None:
            return None
        claimed = conn.execute(
            "UPDATE jobs SET status = 'running', attempts = attempts + 1, started_at = ?, "
            "updated_at = ?, error = NULL, message = 'Starting' WHERE id = ? RETURNING *",
            (now, now, row["id"]),
        ).fetchone()
    return job_to_dict(claimed)


def run_next_job() -> bool:
    """Claim and run one job synchronously. Returns False if nothing was ready."""
    job = _claim_next()
    if job is None:
        return False
    _execute(job)
    return True


def _finish(job_id: int, **fields: Any) -> None:
    fields["updated_at"] = db.utcnow()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    with db.connect() as conn:
        # Never overwrite a cancellation that happened while the job ran.
        conn.execute(
            f"UPDATE jobs SET {assignments} WHERE id = ? AND status = 'running'",
            (*fields.values(), job_id),
        )


def _execute(job: dict[str, Any]) -> None:
    spec = HANDLERS.get(job["type"])
    ctx = JobContext(job_id=job["id"], video_id=job["video_id"], payload=job["payload"], attempt=job["attempts"])
    if spec is None:
        _finish(job["id"], status="failed", error=f"No handler for job type '{job['type']}'", finished_at=db.utcnow())
        return
    log.info("Running job %s (%s) attempt %s", job["id"], job["type"], job["attempts"])
    try:
        result = spec.run(ctx) or {}
    except JobCancelled:
        log.info("Job %s was cancelled", job["id"])
        return
    except Exception as exc:  # noqa: BLE001 - we record every failure
        known = isinstance(exc, JobError)
        message = str(exc) if known else f"Unexpected error: {exc.__class__.__name__}: {exc}"
        retry = (not known or exc.retryable) and job["attempts"] < job["max_attempts"]
        detail = traceback.format_exc()
        if retry:
            delay = timedelta(seconds=10 * job["attempts"])
            run_after = (datetime.now(timezone.utc) + delay).isoformat(timespec="seconds")
            log.warning("Job %s failed, will retry: %s", job["id"], message)
            _finish(job["id"], status="queued", error=message, error_detail=detail, run_after=run_after,
                    message=f"Failed (attempt {job['attempts']}), retrying shortly")
        else:
            log.error("Job %s failed: %s", job["id"], message)
            _finish(job["id"], status="failed", error=message, error_detail=detail,
                    finished_at=db.utcnow(), message="Failed")
            if spec.on_failure:
                try:
                    spec.on_failure(ctx, message)
                except Exception:  # noqa: BLE001
                    log.exception("on_failure hook for job %s raised", job["id"])
        return
    _finish(job["id"], status="succeeded", progress=1.0, result_json=db.dumps(result),
            finished_at=db.utcnow(), message="Done", error=None, error_detail=None)


def cancel(job_id: int) -> dict[str, Any] | None:
    with db.connect() as conn:
        conn.execute(
            "UPDATE jobs SET status = 'cancelled', finished_at = ?, updated_at = ?, message = 'Cancelled' "
            "WHERE id = ? AND status IN ('queued', 'running')",
            (db.utcnow(), db.utcnow(), job_id),
        )
    return get(job_id)


def retry(job_id: int) -> dict[str, Any]:
    """Re-queue a failed or cancelled job. Raises ValueError if not allowed."""
    job = get(job_id)
    if job is None:
        raise LookupError("Job not found")
    if job["status"] not in ("failed", "cancelled"):
        raise ValueError("Only failed or cancelled jobs can be retried.")
    try:
        with db.connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'queued', attempts = 0, progress = 0, error = NULL, "
                "error_detail = NULL, run_after = NULL, started_at = NULL, finished_at = NULL, "
                "message = 'Waiting to start (retry)', updated_at = ? WHERE id = ?",
                (db.utcnow(), job_id),
            )
    except sqlite3.IntegrityError:
        raise ValueError("The same task is already queued or running.") from None
    return get(job_id)  # type: ignore[return-value]


class Worker:
    """Background threads that keep pulling jobs from the queue."""

    def __init__(self, concurrency: int = 1, poll_interval: float = 1.0):
        self.concurrency = max(1, concurrency)
        self.poll_interval = poll_interval
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._threads: list[threading.Thread] = []

    @property
    def running(self) -> bool:
        return any(t.is_alive() for t in self._threads)

    def start(self) -> None:
        if self.running:
            return
        recovered = recover_interrupted()
        if recovered:
            log.info("Recovered %s interrupted job(s)", recovered)
        self._stop.clear()
        for index in range(self.concurrency):
            thread = threading.Thread(target=self._loop, name=f"job-worker-{index}", daemon=True)
            thread.start()
            self._threads.append(thread)

    def wake(self) -> None:
        self._wake.set()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        for thread in self._threads:
            thread.join(timeout=timeout)
        self._threads.clear()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                did_work = run_next_job()
            except Exception:  # noqa: BLE001 - keep the worker alive
                log.exception("Worker loop error")
                did_work = False
            if not did_work:
                self._wake.wait(self.poll_interval)
                self._wake.clear()


worker: Worker | None = None


def notify() -> None:
    """Wake the worker so newly queued jobs start immediately."""
    if worker is not None:
        worker.wake()
