"""FFmpeg / FFprobe helpers."""

from __future__ import annotations

import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

from .. import settings_store
from ..jobs import JobError

PROBE_TIMEOUT = 120
THUMBNAIL_TIMEOUT = 120


def _resolve_tool(setting_key: str) -> str:
    configured = settings_store.get(setting_key) or setting_key.replace("_path", "")
    found = shutil.which(configured)
    if found:
        return found
    if Path(configured).is_file():
        return configured
    tool = setting_key.replace("_path", "").upper()
    raise JobError(
        f"{tool} was not found ('{configured}'). Install FFmpeg and make sure it is on your PATH, "
        f"or set the full path to the program on the Settings page."
    )


def tool_version(setting_key: str) -> dict[str, Any]:
    """Return {'available': bool, 'path': ..., 'version': ..., 'error': ...}."""
    try:
        path = _resolve_tool(setting_key)
    except JobError as exc:
        return {"available": False, "path": None, "version": None, "error": str(exc)}
    try:
        out = subprocess.run([path, "-version"], capture_output=True, text=True, timeout=15)
        first_line = (out.stdout or out.stderr).splitlines()[0] if (out.stdout or out.stderr) else ""
        return {"available": out.returncode == 0, "path": path, "version": first_line, "error": None}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "path": path, "version": None, "error": str(exc)}


def _parse_rate(value: str | None) -> float | None:
    if not value or value in ("0/0", "0"):
        return None
    try:
        rate = float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None
    return round(rate, 3) if rate > 0 else None


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def probe(path: str | Path) -> dict[str, Any]:
    """Run ffprobe and return normalised metadata. Raises JobError."""
    ffprobe = _resolve_tool("ffprobe_path")
    cmd = [ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=PROBE_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise JobError("Reading the video's metadata took too long. The file may be damaged.", retryable=True) from None
    except OSError as exc:
        raise JobError(f"Could not run FFprobe: {exc}") from None
    if proc.returncode != 0:
        reason = (proc.stderr or "").strip().splitlines()
        detail = reason[-1] if reason else "unknown error"
        raise JobError(f"FFprobe could not read this file. It may be damaged or not a video. ({detail})")
    try:
        raw = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        raise JobError("FFprobe returned unreadable output.") from None
    return parse_probe_output(raw)


def parse_probe_output(raw: dict[str, Any]) -> dict[str, Any]:
    streams = raw.get("streams") or []
    fmt = raw.get("format") or {}
    video = next(
        (s for s in streams if s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic")),
        None,
    )
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        raise JobError("This file has no video track, so it cannot be used as gameplay footage.")

    width, height = _to_int(video.get("width")), _to_int(video.get("height"))
    # Phone recordings may be stored rotated; report the displayed size.
    rotation = _to_int((video.get("tags") or {}).get("rotate"))
    for side in video.get("side_data_list") or []:
        if "rotation" in side:
            rotation = _to_int(side.get("rotation"))
    if rotation in (90, -90, 270, -270) and width and height:
        width, height = height, width

    duration = _to_float(fmt.get("duration")) or _to_float(video.get("duration"))
    return {
        "duration_seconds": round(duration, 3) if duration else None,
        "width": width,
        "height": height,
        "fps": _parse_rate(video.get("avg_frame_rate")) or _parse_rate(video.get("r_frame_rate")),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name") if audio else None,
        "has_audio": audio is not None,
        "bitrate": _to_int(fmt.get("bit_rate")),
        "container": fmt.get("format_name"),
        "raw": raw,
    }


def make_thumbnail(source: str | Path, dest: str | Path, at_seconds: float) -> Path:
    """Save a JPEG frame from the video, 480px wide. Raises JobError."""
    ffmpeg = _resolve_tool("ffmpeg_path")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp.jpg")
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{max(0.0, at_seconds):.3f}", "-i", str(source),
        "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "4", str(tmp),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=THUMBNAIL_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise JobError("Creating the thumbnail took too long.", retryable=True) from None
    if proc.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        detail = (proc.stderr or "").strip().splitlines()[-1:] or ["no frame produced"]
        raise JobError(f"Could not create a thumbnail ({detail[0]}).")
    tmp.replace(dest)
    return dest
