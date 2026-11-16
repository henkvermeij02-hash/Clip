from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .. import db, jobs
from ..services import videos as svc

router = APIRouter(prefix="/api/videos", tags=["videos"])


class ImportPathBody(BaseModel):
    path: str
    mode: Literal["reference", "copy"] = "reference"


class ImportFolderBody(ImportPathBody):
    recursive: bool = False


class VideoUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=5000)
    rights_source: Literal["own_recording", "licensed", "other"] | None = None
    rights_confirmed: bool | None = None
    monetization_status: Literal["unknown", "not_monetized", "cleared", "not_allowed"] | None = None
    rights_notes: str | None = Field(default=None, max_length=5000)


def _raise(exc: svc.ImportError_) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc))


@router.get("")
def list_videos(status: str | None = None, q: str | None = None, limit: int = Query(200, le=1000)):
    sql = "SELECT * FROM videos WHERE 1=1"
    params: list = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if q:
        sql += " AND (title LIKE ? OR original_filename LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with db.connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [svc.video_to_dict(r) for r in rows]


@router.put("/upload")
async def upload_video(request: Request, filename: str = Query(..., min_length=1)):
    """Stream a file straight to disk. The request body is the raw file, which
    lets multi-gigabyte recordings upload without being held in memory."""
    try:
        svc.check_extension(filename)
        declared = int(request.headers.get("content-length") or 0)
        folder = svc.incoming_dir()
        if declared:
            svc.ensure_free_space(folder, declared)
    except svc.ImportError_ as exc:
        _raise(exc)
    temp = svc.new_incoming_path()
    written = 0
    try:
        with temp.open("wb") as handle:
            async for chunk in request.stream():
                handle.write(chunk)
                written += len(chunk)
    except Exception:
        temp.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The upload was interrupted. Please try again.")
    if written == 0:
        temp.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if declared and written != declared:
        temp.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The upload was incomplete. Please try again.")
    return svc.import_uploaded_file(temp, filename)


@router.post("/import-path")
def import_path(body: ImportPathBody):
    try:
        return svc.import_from_path(body.path, body.mode)
    except svc.ImportError_ as exc:
        _raise(exc)


@router.post("/import-folder")
def import_folder(body: ImportFolderBody):
    try:
        return svc.import_folder(body.path, body.mode, body.recursive)
    except svc.ImportError_ as exc:
        _raise(exc)


def _get_or_404(video_id: int):
    row = svc.get_video_row(video_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Video not found.")
    return row


@router.get("/{video_id}")
def get_video(video_id: int):
    row = _get_or_404(video_id)
    video = svc.video_to_dict(row)
    with db.connect() as conn:
        job_rows = conn.execute("SELECT * FROM jobs WHERE video_id = ? ORDER BY id DESC LIMIT 50", (video_id,)).fetchall()
    video["jobs"] = [jobs.job_to_dict(j) for j in job_rows]
    video["file_path"] = row["file_path"]
    return video


@router.patch("/{video_id}")
def update_video(video_id: int, body: VideoUpdate):
    _get_or_404(video_id)
    changes = body.model_dump(exclude_unset=True)
    if "rights_confirmed" in changes:
        changes["rights_confirmed"] = int(changes["rights_confirmed"])
    if "title" in changes and not (changes["title"] or "").strip():
        raise HTTPException(status_code=400, detail="Title cannot be empty.")
    if changes:
        svc.update_video(video_id, **changes)
    return svc.video_to_dict(svc.get_video_row(video_id))


@router.delete("/{video_id}")
def delete_video(video_id: int, delete_file: bool = False):
    try:
        return svc.delete_video(video_id, delete_file)
    except svc.ImportError_ as exc:
        _raise(exc)


@router.post("/{video_id}/reprocess")
def reprocess(video_id: int):
    row = _get_or_404(video_id)
    if not Path(row["file_path"]).exists():
        raise HTTPException(status_code=409, detail=f"The video file is missing: {row['file_path']}")
    job, created = jobs.enqueue("probe_video", video_id=video_id, dedupe_key=f"probe:{video_id}")
    jobs.notify()
    return {"job": job, "created": created}


@router.get("/{video_id}/thumbnail")
def thumbnail(video_id: int):
    row = _get_or_404(video_id)
    if not row["thumbnail_path"] or not Path(row["thumbnail_path"]).exists():
        raise HTTPException(status_code=404, detail="No thumbnail yet.")
    return FileResponse(row["thumbnail_path"], media_type="image/jpeg", headers={"Cache-Control": "no-cache"})


@router.get("/{video_id}/stream")
def stream(video_id: int):
    """Serve the video for the in-browser player (supports seeking)."""
    row = _get_or_404(video_id)
    path = Path(row["file_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="The video file is missing.")
    return FileResponse(path)
