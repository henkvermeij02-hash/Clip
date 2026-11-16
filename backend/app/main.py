"""GTA Shorts AI Studio — backend entry point.

Run with:  uvicorn app.main:app --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import config, db, jobs, settings_store
from .routers import jobs as jobs_router
from .routers import licenses, system, videos
from .services import videos as _video_handlers  # noqa: F401 - registers job handlers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("gtastudio")


@asynccontextmanager
async def lifespan(_: FastAPI):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    # Set GTASTUDIO_DISABLE_WORKER=1 to run the API without background processing (used by tests).
    if os.environ.get("GTASTUDIO_DISABLE_WORKER") != "1":
        jobs.worker = jobs.Worker(concurrency=settings_store.get("worker_concurrency"))
        jobs.worker.start()
    log.info("GTA Shorts AI Studio backend ready. Data folder: %s", config.DATA_DIR)
    yield
    if jobs.worker is not None:
        jobs.worker.stop()
        jobs.worker = None


app = FastAPI(title="GTA Shorts AI Studio", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_error(_: Request, exc: Exception):
    log.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Something went wrong on the server: {exc.__class__.__name__}: {exc}"},
    )


app.include_router(system.router)
app.include_router(videos.router)
app.include_router(jobs_router.router)
app.include_router(licenses.router)
