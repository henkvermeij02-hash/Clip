# How GTA Shorts AI Studio fits together

```
 Browser (http://localhost:3000)                Your computer only
 ┌────────────────────────────┐   HTTP/JSON   ┌──────────────────────────────┐
 │ Next.js dashboard          │ ────────────► │ FastAPI backend :8000        │
 │ (pages poll for updates)   │ ◄──────────── │  routers/  → services/       │
 └────────────────────────────┘               │        │          │          │
                                              │        ▼          ▼          │
                                              │   SQLite db   FFmpeg/FFprobe │
                                              │        ▲                     │
                                              │   job worker threads         │
                                              └──────────────────────────────┘
```

## Background jobs (`backend/app/jobs.py`)

Anything slow (copying a 20 GB file, reading metadata, later: AI analysis, rendering,
uploading) is a **job row** in the `jobs` table, processed by worker threads.

- **Persistent:** jobs are in the database, so nothing is lost if the app stops.
- **Resumable:** on startup, jobs that were `running` go back to `queued` and run again.
  Every handler is written so that running it twice is safe.
- **No duplicates:** each job has a `dedupe_key` (e.g. `probe:12`). A unique index makes it
  impossible to queue the same work twice while it is pending. Phases 4 and 5 will use the
  same mechanism to prevent duplicate renders and uploads.
- **Errors:** a `JobError` is a known problem with a friendly message (not retried).
  Any other exception is retried with a growing delay, up to `max_attempts`, and the full
  technical details are stored for the “Technical details” button.
- **Progress & cancel:** handlers report progress; cancelling marks the row and the handler
  stops at its next progress update.

To add a new kind of work:

```python
@jobs.register("detect_scenes", label="Detect scenes", on_failure=_mark_video_failed)
def handle_detect_scenes(ctx: JobContext) -> dict:
    ctx.progress(0.1, "Loading video")
    ...
    return {"scenes": 42}          # stored as the job result
```

## Imports (`backend/app/services/videos.py`)

1. Uploads are streamed straight to `library/.incoming/*.part` (no memory limit).
2. A fingerprint (size + three 4 MB samples, SHA-256) detects duplicates in milliseconds.
3. A `videos` row is created and a `probe_video` job queued in the same transaction.
4. “Copy into library” imports first run a `copy_video` job, which then queues `probe_video`.

## Database migrations (`backend/app/db.py`)

`MIGRATIONS` is a list of SQL scripts; `PRAGMA user_version` records how many have run.
New phases **append** a migration — existing databases upgrade automatically on startup.

## Settings (`backend/app/config.py`)

Every setting is declared once in `DEFAULT_SETTINGS` with its type, limits and the phase
that uses it. The Settings page is generated from this list, and the backend validates
every change.
