from pathlib import Path

from .conftest import make_video, run_all_jobs


def test_health(client):
    assert client.get("/api/health").json()["ok"] is True


def test_system_status_reports_tools(client):
    data = client.get("/api/system/status").json()
    assert data["ffmpeg"]["available"] and data["ffprobe"]["available"]
    assert "available" in data["ollama"]


def test_import_by_path_reference(client, sample_video):
    r = client.post("/api/videos/import-path", json={"path": str(sample_video), "mode": "reference"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "imported" and body["video"]["status"] == "pending"
    vid = body["video"]["id"]

    run_all_jobs()
    video = client.get(f"/api/videos/{vid}").json()
    assert video["status"] == "ready"
    assert (video["width"], video["height"], video["fps"]) == (320, 180, 30)
    assert video["storage_mode"] == "referenced" and video["file_path"] == str(sample_video.resolve())
    assert video["has_thumbnail"]
    assert client.get(f"/api/videos/{vid}/thumbnail").headers["content-type"] == "image/jpeg"
    assert video["jobs"][0]["status"] == "succeeded"


def test_duplicate_import_is_detected(client, sample_video, tmp_path):
    client.post("/api/videos/import-path", json={"path": str(sample_video)})
    copy = tmp_path / "renamed_copy.mp4"
    copy.write_bytes(sample_video.read_bytes())
    r = client.post("/api/videos/import-path", json={"path": str(copy)})
    assert r.json()["status"] == "duplicate"
    assert len(client.get("/api/videos").json()) == 1


def test_import_copy_mode_runs_copy_then_probe(client, sample_video, isolated_data):
    body = client.post("/api/videos/import-path", json={"path": str(sample_video), "mode": "copy"}).json()
    assert body["job"]["type"] == "copy_video"
    assert run_all_jobs() == 2
    video = client.get(f"/api/videos/{body['video']['id']}").json()
    assert video["status"] == "ready" and video["storage_mode"] == "copied"
    assert Path(video["file_path"]).parent == isolated_data / "library"
    assert Path(video["file_path"]).read_bytes() == sample_video.read_bytes()


def test_upload_streams_file_and_processes(client, sample_video):
    data = sample_video.read_bytes()
    r = client.put("/api/videos/upload", params={"filename": "my clip.mp4"}, content=data)
    assert r.status_code == 200, r.text
    vid = r.json()["video"]["id"]
    run_all_jobs()
    video = client.get(f"/api/videos/{vid}").json()
    assert video["status"] == "ready" and video["original_filename"] == "my clip.mp4"
    # Same bytes again → duplicate, and no stray temp file left behind
    again = client.put("/api/videos/upload", params={"filename": "other.mp4"}, content=data).json()
    assert again["status"] == "duplicate"
    incoming = Path(video["file_path"]).parent / ".incoming"
    assert list(incoming.glob("*.part")) == []


def test_upload_rejects_wrong_extension(client):
    r = client.put("/api/videos/upload", params={"filename": "notes.txt"}, content=b"hello")
    assert r.status_code == 400 and "not a supported video" in r.json()["detail"]


def test_corrupt_file_marks_video_error(client, tmp_path):
    bad = tmp_path / "broken.mp4"
    bad.write_bytes(b"not really a video" * 1000)
    vid = client.post("/api/videos/import-path", json={"path": str(bad)}).json()["video"]["id"]
    run_all_jobs()
    video = client.get(f"/api/videos/{vid}").json()
    assert video["status"] == "error" and "FFprobe could not read" in video["error"]
    assert video["jobs"][0]["status"] == "failed"


def test_import_path_errors(client, tmp_path):
    assert client.post("/api/videos/import-path", json={"path": str(tmp_path / "nope.mp4")}).status_code == 404
    assert client.post("/api/videos/import-path", json={"path": str(tmp_path)}).status_code == 400
    assert client.post("/api/videos/import-path", json={"path": ""}).status_code == 400


def test_import_folder(client, tmp_path):
    folder = tmp_path / "captures"
    make_video(folder / "one.mp4", color="red")
    make_video(folder / "two.mkv", color="green")
    make_video(folder / "sub" / "three.mp4", color="blue")
    (folder / "readme.txt").write_text("ignore me")
    flat = client.post("/api/videos/import-folder", json={"path": str(folder)}).json()
    assert flat["found"] == 2 and flat["summary"]["imported"] == 2
    deep = client.post("/api/videos/import-folder", json={"path": str(folder), "recursive": True}).json()
    assert deep["summary"] == {"imported": 1, "duplicate": 2, "error": 0}


def test_update_rights_and_delete(client, sample_video):
    vid = client.post("/api/videos/import-path", json={"path": str(sample_video)}).json()["video"]["id"]
    r = client.patch(f"/api/videos/{vid}", json={"rights_confirmed": True, "monetization_status": "not_monetized", "title": "Car chase"})
    assert r.json()["rights_confirmed"] is True and r.json()["title"] == "Car chase"
    assert client.patch(f"/api/videos/{vid}", json={"monetization_status": "bogus"}).status_code == 422
    # Deleting a referenced video never deletes your original file
    assert client.delete(f"/api/videos/{vid}", params={"delete_file": True}).json()["file_deleted"] is False
    assert sample_video.exists()
    assert client.get(f"/api/videos/{vid}").status_code == 404


def test_reprocess_is_deduplicated(client, sample_video):
    vid = client.post("/api/videos/import-path", json={"path": str(sample_video)}).json()["video"]["id"]
    r = client.post(f"/api/videos/{vid}/reprocess").json()
    assert r["created"] is False  # the import's probe job is still queued


def test_stream_supports_range_requests(client, sample_video):
    vid = client.post("/api/videos/import-path", json={"path": str(sample_video)}).json()["video"]["id"]
    r = client.get(f"/api/videos/{vid}/stream", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100


def test_job_endpoints(client, tmp_path):
    bad = tmp_path / "broken.mp4"
    bad.write_bytes(b"x" * 5000)
    client.post("/api/videos/import-path", json={"path": str(bad)})
    run_all_jobs()
    job = client.get("/api/jobs", params={"status": "failed"}).json()[0]
    retried = client.post(f"/api/jobs/{job['id']}/retry").json()
    assert retried["status"] == "queued"
    assert client.post(f"/api/jobs/{job['id']}/retry").status_code == 409
    assert client.post(f"/api/jobs/{job['id']}/cancel").json()["status"] == "cancelled"


def test_settings_roundtrip_and_validation(client):
    s = client.get("/api/settings").json()
    assert s["values"]["youtube_default_privacy"] == "private"
    assert any(item["key"] == "ollama_url" for item in s["schema"])
    ok = client.put("/api/settings", json={"values": {"worker_concurrency": 2, "short_fps": 60}})
    assert ok.status_code == 200 and ok.json()["values"]["short_fps"] == 60
    assert client.put("/api/settings", json={"values": {"short_fps": 25}}).status_code == 400
    assert client.put("/api/settings", json={"values": {"made_up": 1}}).status_code == 400
    assert client.put("/api/settings", json={"values": {"short_min_seconds": 100}}).status_code == 400


def test_licenses_crud(client):
    r = client.post("/api/licenses", json={"asset_type": "voice", "name": "Piper en_US voice", "license_name": "CC BY 4.0",
                                          "attribution_required": True, "attribution_text": "Voice by X"})
    assert r.status_code == 201
    lid = r.json()["id"]
    assert client.post("/api/licenses", json={"asset_type": "music", "name": "x", "license_name": "y",
                                              "attribution_required": True}).status_code == 400
    assert len(client.get("/api/licenses").json()) == 1
    assert client.delete(f"/api/licenses/{lid}").json()["deleted"]


def test_stats(client, sample_video):
    client.post("/api/videos/import-path", json={"path": str(sample_video)})
    run_all_jobs()
    s = client.get("/api/stats").json()
    assert s["videos"]["total"] == 1 and s["videos"]["ready"] == 1 and s["videos"]["rights_unconfirmed"] == 1
