import os
import subprocess
import tempfile
from pathlib import Path

import pytest

# Must be set before the app is imported so nothing touches your real data folder.
_SESSION_DIR = Path(tempfile.mkdtemp(prefix="gtastudio-tests-"))
os.environ["GTASTUDIO_DATA_DIR"] = str(_SESSION_DIR)
os.environ["GTASTUDIO_DISABLE_WORKER"] = "1"

from app import config, db, jobs, settings_store  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    """Every test gets its own empty database and folders."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "DB_PATH", data / "studio.db")
    monkeypatch.setattr(config, "THUMBNAIL_DIR", data / "thumbnails")
    db.init_db()
    settings_store.update({"library_dir": str(data / "library"), "output_dir": str(data / "renders")})
    yield data


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


def make_video(path: Path, seconds: float = 2.0, size: str = "320x180", audio: bool = True, color: str = "") -> Path:
    """Create a small real video file with FFmpeg."""
    path.parent.mkdir(parents=True, exist_ok=True)
    src = f"color=c={color}:s={size}:r=30:d={seconds}" if color else f"testsrc=size={size}:rate=30:duration={seconds}"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", src]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:a", "aac", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(cmd, check=True)
    return path


@pytest.fixture
def sample_video(tmp_path):
    return make_video(tmp_path / "footage" / "gta_session_01.mp4")


def run_all_jobs(limit: int = 20) -> int:
    count = 0
    while count < limit and jobs.run_next_job():
        count += 1
    return count
