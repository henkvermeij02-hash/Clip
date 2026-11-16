"""Health, setup checks, dashboard statistics and settings."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import config, db, jobs, settings_store
from ..services import media

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health():
    return {"ok": True, "app": "GTA Shorts AI Studio", "phase": 1}


def check_ollama(url: str) -> dict[str, Any]:
    """Ollama is optional until Phase 2. Only contacts the local address you configure."""
    try:
        resp = httpx.get(url.rstrip("/") + "/api/tags", timeout=2.0)
        resp.raise_for_status()
        models = [m.get("name") for m in resp.json().get("models", [])]
        return {"available": True, "models": models, "error": None}
    except (httpx.HTTPError, ValueError) as exc:
        return {"available": False, "models": [], "error": f"Ollama is not reachable at {url} ({exc.__class__.__name__})."}


@router.get("/system/status")
def system_status():
    settings = settings_store.get_all()
    library = Path(settings["library_dir"]).expanduser()
    disk_folder = library if library.exists() else config.DATA_DIR
    disk_folder.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(disk_folder)
    return {
        "ffmpeg": media.tool_version("ffmpeg_path"),
        "ffprobe": media.tool_version("ffprobe_path"),
        "ollama": check_ollama(settings["ollama_url"]),
        "worker_running": bool(jobs.worker and jobs.worker.running),
        "data_dir": str(config.DATA_DIR),
        "library_dir": str(library),
        "disk": {"folder": str(disk_folder), "free_bytes": usage.free, "total_bytes": usage.total},
    }


@router.get("/stats")
def stats():
    with db.connect() as conn:
        v = conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(status = 'ready') AS ready, SUM(status IN ('pending','processing')) AS processing, "
            "SUM(status = 'error') AS errors, COALESCE(SUM(duration_seconds), 0) AS total_seconds, "
            "COALESCE(SUM(CASE WHEN storage_mode = 'copied' THEN file_size END), 0) AS library_bytes, "
            "SUM(rights_confirmed = 0) AS rights_unconfirmed FROM videos"
        ).fetchone()
        j = conn.execute(
            "SELECT SUM(status = 'queued') AS queued, SUM(status = 'running') AS running, "
            "SUM(status = 'failed') AS failed FROM jobs"
        ).fetchone()
    return {
        "videos": {k: (v[k] or 0) for k in v.keys()},
        "jobs": {k: (j[k] or 0) for k in j.keys()},
    }


# ---------------------------------------------------------------- settings

class SettingsUpdate(BaseModel):
    values: dict[str, Any]


@router.get("/settings")
def get_settings():
    return {"values": settings_store.get_all(), "schema": settings_store.schema()}


@router.put("/settings")
def put_settings(body: SettingsUpdate):
    try:
        values = settings_store.update(body.values)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    return {"values": values, "schema": settings_store.schema()}


class OllamaTest(BaseModel):
    url: str | None = None


@router.post("/settings/test-ollama")
def test_ollama(body: OllamaTest):
    url = body.url or settings_store.get("ollama_url")
    result = check_ollama(url)
    settings = settings_store.get_all()
    if result["available"]:
        installed = set(result["models"])

        def has(name: str) -> bool:
            return name in installed or f"{name}:latest" in installed

        result["vision_model_installed"] = has(settings["ollama_vision_model"])
        result["text_model_installed"] = has(settings["ollama_text_model"])
    return result
