"""Importing footage into the library and the background jobs that process it."""

from __future__ import annotations

import re
import shutil
import sqlite3
import unicodedata
import uuid
from pathlib import Path
from typing import Any

from .. import config, db, jobs, settings_store
from ..jobs import JobContext, JobError
from . import hashing, media

COPY_CHUNK = 8 * 1024 * 1024


class ImportError_(Exception):
    """User-facing import problem (bad path, unsupported file...)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_filename(name: str) -> str:
    """Make a filename safe for every operating system."""
    name = Path(name.replace("\\", "/")).name
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    stem, ext = Path(name).stem[:120] or "video", Path(name).suffix.lower()
    return f"{stem}{ext}"


def check_extension(filename: str) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in config.VIDEO_EXTENSIONS:
        allowed = ", ".join(sorted(config.VIDEO_EXTENSIONS))
        raise ImportError_(f"'{filename}' is not a supported video file. Supported types: {allowed}.")


def library_dir() -> Path:
    path = Path(settings_store.get("library_dir")).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def incoming_dir() -> Path:
    path = library_dir() / ".incoming"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_free_space(folder: Path, needed_bytes: int) -> None:
    free = shutil.disk_usage(folder).free
    margin = 512 * 1024 * 1024  # keep 512 MB spare
    if free < needed_bytes + margin:
        raise ImportError_(
            f"Not enough free disk space in {folder}. Needed {needed_bytes / 1e9:.1f} GB, "
            f"available {free / 1e9:.1f} GB.",
            status_code=507,
        )


def video_to_dict(row: sqlite3.Row | dict | None) -> dict[str, Any] | None:
    if row is None:
        return None
    video = dict(row)
    video.pop("metadata_json", None)
    video["has_audio"] = None if video.get("has_audio") is None else bool(video["has_audio"])
    video["rights_confirmed"] = bool(video.get("rights_confirmed"))
    video["has_thumbnail"] = bool(video.get("thumbnail_path")) and Path(video["thumbnail_path"]).exists()
    video["file_exists"] = Path(video["file_path"]).exists()
    video.pop("thumbnail_path", None)
    return video


def get_video_row(video_id: int) -> sqlite3.Row | None:
    with db.connect() as conn:
        return conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()


def find_by_hash(content_hash: str) -> sqlite3.Row | None:
    with db.connect() as conn:
        return conn.execute("SELECT * FROM videos WHERE content_hash = ?", (content_hash,)).fetchone()


def _insert_video(conn: sqlite3.Connection, **fields: Any) -> sqlite3.Row:
    now = db.utcnow()
    fields.setdefault("title", Path(fields["original_filename"]).stem)
    fields.update(created_at=now, updated_at=now)
    cols = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    return conn.execute(f"INSERT INTO videos ({cols}) VALUES ({marks}) RETURNING *", tuple(fields.values())).fetchone()


def update_video(video_id: int, **fields: Any) -> None:
    fields["updated_at"] = db.utcnow()
    assignments = ", ".join(f"{k} = ?" for k in fields)
    with db.connect() as conn:
        conn.execute(f"UPDATE videos SET {assignments} WHERE id = ?", (*fields.values(), video_id))


def _duplicate_result(existing: sqlite3.Row) -> dict[str, Any]:
    return {
        "status": "duplicate",
        "message": f"Already in your library as '{existing['title'] or existing['original_filename']}'.",
        "video": video_to_dict(existing),
        "job": None,
    }


# ---------------------------------------------------------------------------
# Import entry points
# ---------------------------------------------------------------------------

def import_uploaded_file(temp_path: Path, original_filename: str) -> dict[str, Any]:
    """Register a file that was streamed into the incoming folder."""
    content_hash = hashing.quick_hash(temp_path)
    existing = find_by_hash(content_hash)
    if existing is not None:
        temp_path.unlink(missing_ok=True)
        return _duplicate_result(existing)

    dest = library_dir() / f"{content_hash[4:16]}_{safe_filename(original_filename)}"
    temp_path.replace(dest)
    try:
        with db.transaction() as conn:
            row = _insert_video(
                conn, original_filename=original_filename, file_path=str(dest), storage_mode="copied",
                file_size=dest.stat().st_size, content_hash=content_hash,
            )
            job, _ = jobs.enqueue("probe_video", video_id=row["id"], dedupe_key=f"probe:{row['id']}", conn=conn)
    except sqlite3.IntegrityError:
        # Another upload of the same file finished a moment earlier.
        existing = find_by_hash(content_hash)
        if existing is not None and Path(existing["file_path"]) != dest:
            dest.unlink(missing_ok=True)
        return _duplicate_result(existing)  # type: ignore[arg-type]
    jobs.notify()
    return {"status": "imported", "message": "Imported. Reading metadata…", "video": video_to_dict(row), "job": job}


def import_from_path(path_str: str, mode: str = "reference") -> dict[str, Any]:
    """Import a single file that already exists on this computer.

    ``reference`` keeps the file where it is (no extra disk space used);
    ``copy`` copies it into the library folder in the background.
    """
    if mode not in ("reference", "copy"):
        raise ImportError_("Import mode must be 'reference' or 'copy'.")
    if not path_str or not path_str.strip():
        raise ImportError_("Please enter the path to a video file.")
    source = Path(path_str.strip().strip('"')).expanduser()
    if not source.exists():
        raise ImportError_(f"File not found: {source}", status_code=404)
    if not source.is_file():
        raise ImportError_(f"This is a folder, not a file: {source}. Use folder import instead.")
    check_extension(source.name)
    source = source.resolve()
    size = source.stat().st_size
    if size == 0:
        raise ImportError_(f"The file is empty: {source}")

    content_hash = hashing.quick_hash(source)
    existing = find_by_hash(content_hash)
    if existing is not None:
        return _duplicate_result(existing)

    if mode == "copy":
        dest = library_dir() / f"{content_hash[4:16]}_{safe_filename(source.name)}"
        ensure_free_space(dest.parent, size)
        status, file_path = "pending", dest
    else:
        status, file_path = "pending", source

    try:
        with db.transaction() as conn:
            row = _insert_video(
                conn, original_filename=source.name, file_path=str(file_path),
                storage_mode="copied" if mode == "copy" else "referenced",
                file_size=size, content_hash=content_hash, status=status,
            )
            if mode == "copy":
                job, _ = jobs.enqueue(
                    "copy_video", video_id=row["id"], payload={"source": str(source), "dest": str(dest)},
                    dedupe_key=f"copy:{row['id']}", conn=conn,
                )
            else:
                job, _ = jobs.enqueue("probe_video", video_id=row["id"], dedupe_key=f"probe:{row['id']}", conn=conn)
    except sqlite3.IntegrityError:
        existing = find_by_hash(content_hash)
        return _duplicate_result(existing)  # type: ignore[arg-type]
    jobs.notify()
    message = "Copying into your library…" if mode == "copy" else "Imported. Reading metadata…"
    return {"status": "imported", "message": message, "video": video_to_dict(row), "job": job}


def import_folder(path_str: str, mode: str = "reference", recursive: bool = False) -> dict[str, Any]:
    if not path_str or not path_str.strip():
        raise ImportError_("Please enter the path to a folder.")
    folder = Path(path_str.strip().strip('"')).expanduser()
    if not folder.exists():
        raise ImportError_(f"Folder not found: {folder}", status_code=404)
    if not folder.is_dir():
        raise ImportError_(f"This is a file, not a folder: {folder}")
    pattern = "**/*" if recursive else "*"
    library = library_dir().resolve()
    files = sorted(
        p for p in folder.glob(pattern)
        if p.is_file() and p.suffix.lower() in config.VIDEO_EXTENSIONS
        and library not in p.resolve().parents  # never re-import our own library
    )
    results = []
    for file in files:
        try:
            result = import_from_path(str(file), mode)
        except ImportError_ as exc:
            result = {"status": "error", "message": str(exc), "video": None, "job": None}
        except OSError as exc:
            result = {"status": "error", "message": f"Could not read file: {exc}", "video": None, "job": None}
        result["path"] = str(file)
        results.append(result)
    summary = {s: sum(1 for r in results if r["status"] == s) for s in ("imported", "duplicate", "error")}
    return {"folder": str(folder), "found": len(files), "summary": summary, "results": results}


def delete_video(video_id: int, delete_file: bool) -> dict[str, Any]:
    row = get_video_row(video_id)
    if row is None:
        raise ImportError_("Video not found.", status_code=404)
    with db.connect() as conn:
        conn.execute(
            "UPDATE jobs SET status = 'cancelled', message = 'Video deleted', updated_at = ? "
            "WHERE video_id = ? AND status IN ('queued', 'running')",
            (db.utcnow(), video_id),
        )
        conn.execute("DELETE FROM videos WHERE id = ?", (video_id,))
    removed_file = False
    # Only ever delete files that the app itself copied into the library.
    if delete_file and row["storage_mode"] == "copied":
        path = Path(row["file_path"])
        if path.exists():
            path.unlink()
            removed_file = True
    if row["thumbnail_path"]:
        Path(row["thumbnail_path"]).unlink(missing_ok=True)
    return {"deleted": True, "file_deleted": removed_file}


def new_incoming_path() -> Path:
    return incoming_dir() / f"{uuid.uuid4().hex}.part"


# ---------------------------------------------------------------------------
# Background job handlers
# ---------------------------------------------------------------------------

def _mark_video_failed(ctx: JobContext, message: str) -> None:
    if ctx.video_id is not None:
        update_video(ctx.video_id, status="error", error=message)


@jobs.register("copy_video", label="Copy into library", on_failure=_mark_video_failed)
def handle_copy(ctx: JobContext) -> dict[str, Any]:
    source = Path(ctx.payload["source"])
    dest = Path(ctx.payload["dest"])
    if get_video_row(ctx.video_id) is None:  # type: ignore[arg-type]
        raise JobError("The video was deleted before it could be copied.")
    if not source.exists():
        raise JobError(f"The original file is no longer available: {source}")
    update_video(ctx.video_id, status="processing", error=None)  # type: ignore[arg-type]
    total = source.stat().st_size
    if dest.exists() and dest.stat().st_size == total:
        ctx.progress(0.95, "Already copied, verifying")
    else:
        part = dest.with_name(dest.name + ".part")
        copied = 0
        with source.open("rb") as src, part.open("wb") as dst:
            while chunk := src.read(COPY_CHUNK):
                dst.write(chunk)
                copied += len(chunk)
                ctx.progress(0.95 * copied / max(total, 1), f"Copying {copied / 1e9:.2f} / {total / 1e9:.2f} GB")
        if part.stat().st_size != total:
            part.unlink(missing_ok=True)
            raise JobError("The copy is incomplete (size mismatch). Please retry.", retryable=True)
        part.replace(dest)
    jobs.enqueue("probe_video", video_id=ctx.video_id, dedupe_key=f"probe:{ctx.video_id}")
    jobs.notify()
    return {"dest": str(dest), "bytes": total}


@jobs.register("probe_video", label="Read video metadata", on_failure=_mark_video_failed)
def handle_probe(ctx: JobContext) -> dict[str, Any]:
    row = get_video_row(ctx.video_id)  # type: ignore[arg-type]
    if row is None:
        raise JobError("The video was deleted before it could be processed.")
    path = Path(row["file_path"])
    if not path.exists():
        raise JobError(f"The video file is missing: {path}. Was it moved or deleted?")
    update_video(row["id"], status="processing", error=None)
    ctx.progress(0.1, "Reading metadata with FFprobe")
    meta = media.probe(path)

    ctx.progress(0.6, "Creating thumbnail")
    duration = meta["duration_seconds"] or 0
    thumb_at = min(duration * 0.1, 30.0) if duration else 0.0
    thumb_path = config.THUMBNAIL_DIR / f"video_{row['id']}.jpg"
    try:
        media.make_thumbnail(path, thumb_path, thumb_at)
        thumbnail = str(thumb_path)
    except JobError:
        # A missing thumbnail must not block using the video.
        thumbnail = None

    update_video(
        row["id"], status="ready", error=None,
        duration_seconds=meta["duration_seconds"], width=meta["width"], height=meta["height"],
        fps=meta["fps"], video_codec=meta["video_codec"], audio_codec=meta["audio_codec"],
        has_audio=int(meta["has_audio"]), bitrate=meta["bitrate"], container=meta["container"],
        metadata_json=db.dumps(meta["raw"]), thumbnail_path=thumbnail, file_size=path.stat().st_size,
    )
    return {k: v for k, v in meta.items() if k != "raw"} | {"thumbnail": bool(thumbnail)}
