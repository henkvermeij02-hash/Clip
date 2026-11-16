"""Application paths and user-editable settings.

Settings live in the SQLite database (table ``settings``) so they can be edited
from the dashboard. ``DEFAULT_SETTINGS`` defines every allowed key, its type and
its default value. Unknown keys are rejected.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

# Everything the app writes (database, copied footage, thumbnails, renders)
# lives under DATA_DIR unless the user points a folder elsewhere in Settings.
DATA_DIR = Path(os.environ.get("GTASTUDIO_DATA_DIR", PROJECT_DIR / "data")).resolve()
DB_PATH = Path(os.environ.get("GTASTUDIO_DB_PATH", DATA_DIR / "studio.db"))
THUMBNAIL_DIR = DATA_DIR / "thumbnails"

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".ts"}

# Origins allowed to call the API (the dashboard). Local only.
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "GTASTUDIO_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if o.strip()
]


@dataclass(frozen=True)
class SettingSpec:
    default: Any
    type: type
    group: str
    label: str
    help: str = ""
    phase: int = 1  # The phase in which the setting starts being used
    choices: tuple | None = None
    minimum: float | None = None
    maximum: float | None = None


DEFAULT_SETTINGS: dict[str, SettingSpec] = {
    # --- Folders -----------------------------------------------------------
    "library_dir": SettingSpec(
        str(DATA_DIR / "library"), str, "folders", "Footage library folder",
        "Where uploaded or copied recordings are stored.",
    ),
    "output_dir": SettingSpec(
        str(DATA_DIR / "renders"), str, "folders", "Rendered Shorts folder",
        "Where finished vertical Shorts will be written.", phase=4,
    ),
    # --- Tools ---------------------------------------------------------------
    "ffmpeg_path": SettingSpec(
        "ffmpeg", str, "tools", "FFmpeg program",
        "Leave as 'ffmpeg' if it is on your PATH, otherwise the full path to ffmpeg(.exe).",
    ),
    "ffprobe_path": SettingSpec(
        "ffprobe", str, "tools", "FFprobe program",
        "Leave as 'ffprobe' if it is on your PATH, otherwise the full path to ffprobe(.exe).",
    ),
    "worker_concurrency": SettingSpec(
        1, int, "tools", "Parallel background jobs",
        "How many processing jobs run at the same time. Keep at 1 on weaker computers. "
        "Takes effect after restarting the backend.", minimum=1, maximum=8,
    ),
    # --- Video ---------------------------------------------------------------
    "short_width": SettingSpec(1080, int, "video", "Short width (px)", phase=4, minimum=360, maximum=2160),
    "short_height": SettingSpec(1920, int, "video", "Short height (px)", phase=4, minimum=640, maximum=3840),
    "short_fps": SettingSpec(30, int, "video", "Short frame rate", phase=4, choices=(24, 30, 60)),
    "short_max_seconds": SettingSpec(
        58, int, "video", "Maximum Short length (seconds)",
        "YouTube Shorts can be up to 3 minutes, but under 60s is the safest default.",
        phase=2, minimum=5, maximum=180,
    ),
    "short_min_seconds": SettingSpec(8, int, "video", "Minimum clip length (seconds)", phase=2, minimum=3, maximum=60),
    # --- AI (Ollama) -----------------------------------------------------------
    "ollama_url": SettingSpec(
        "http://127.0.0.1:11434", str, "ai", "Ollama address",
        "Ollama runs locally and is free. Install it from ollama.com.", phase=2,
    ),
    "ollama_vision_model": SettingSpec(
        "qwen2.5vl:7b", str, "ai", "Vision model (looks at frames)",
        "Needs a model that understands images. Smaller models run on weaker hardware.", phase=2,
    ),
    "ollama_text_model": SettingSpec(
        "llama3.1:8b", str, "ai", "Text model (writes scripts)", phase=3,
    ),
    # --- Voice & transcription ------------------------------------------------
    "piper_path": SettingSpec("piper", str, "voice", "Piper program", phase=3),
    "piper_voice_model": SettingSpec(
        "", str, "voice", "Piper voice model (.onnx)",
        "Check the voice's licence before monetised use and record it on the Rights page.", phase=3,
    ),
    "whisper_model": SettingSpec(
        "small", str, "voice", "faster-whisper model size", phase=3,
        choices=("tiny", "base", "small", "medium", "large-v3"),
    ),
    "whisper_device": SettingSpec(
        "auto", str, "voice", "Transcription device", phase=3, choices=("auto", "cpu", "cuda"),
    ),
    # --- YouTube -----------------------------------------------------------------
    "youtube_default_privacy": SettingSpec(
        "private", str, "youtube", "Default upload privacy",
        "Uploads are private by default. You can change visibility on YouTube afterwards.",
        phase=5, choices=("private", "unlisted", "public"),
    ),
    # --- Branding --------------------------------------------------------------
    "channel_name": SettingSpec("", str, "branding", "Channel name / watermark text", phase=4),
}


def coerce_setting(key: str, value: Any) -> Any:
    """Validate and convert a setting value. Raises ValueError with a friendly message."""
    spec = DEFAULT_SETTINGS.get(key)
    if spec is None:
        raise ValueError(f"Unknown setting '{key}'.")
    try:
        if spec.type is int:
            if isinstance(value, bool):
                raise ValueError
            converted: Any = int(value)
        elif spec.type is bool:
            converted = bool(value)
        else:
            converted = str(value).strip()
    except (TypeError, ValueError):
        raise ValueError(f"'{spec.label}' must be a {spec.type.__name__}.") from None
    if spec.choices is not None and converted not in spec.choices:
        allowed = ", ".join(str(c) for c in spec.choices)
        raise ValueError(f"'{spec.label}' must be one of: {allowed}.")
    if spec.minimum is not None and converted < spec.minimum:
        raise ValueError(f"'{spec.label}' must be at least {spec.minimum:g}.")
    if spec.maximum is not None and converted > spec.maximum:
        raise ValueError(f"'{spec.label}' must be at most {spec.maximum:g}.")
    if spec.type is str and key.endswith("_dir") and not converted:
        raise ValueError(f"'{spec.label}' cannot be empty.")
    return converted
