from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import db, jobs

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def list_jobs(status: str | None = None, video_id: int | None = None, limit: int = Query(100, le=500)):
    sql = "SELECT * FROM jobs WHERE 1=1"
    params: list = []
    if status:
        statuses = [s for s in status.split(",") if s]
        sql += f" AND status IN ({','.join('?' for _ in statuses)})"
        params += statuses
    if video_id is not None:
        sql += " AND video_id = ?"
        params.append(video_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with db.connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [jobs.job_to_dict(r) for r in rows]


@router.get("/{job_id}")
def get_job(job_id: int):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.post("/{job_id}/retry")
def retry_job(job_id: int):
    try:
        job = jobs.retry(job_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Job not found.") from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if job.get("video_id"):
        from ..services.videos import update_video

        update_video(job["video_id"], status="pending", error=None)
    jobs.notify()
    return job


@router.post("/{job_id}/cancel")
def cancel_job(job_id: int):
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["status"] not in jobs.ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail="This job has already finished.")
    return jobs.cancel(job_id)
