import pytest

from app.jobs import JobError
from app.services import hashing, media

from .conftest import make_video


def test_probe_reads_real_metadata(sample_video):
    meta = media.probe(sample_video)
    assert meta["width"] == 320 and meta["height"] == 180
    assert meta["fps"] == 30
    assert meta["video_codec"] == "h264"
    assert meta["has_audio"] is True and meta["audio_codec"] == "aac"
    assert 1.8 < meta["duration_seconds"] < 2.3


def test_probe_without_audio(tmp_path):
    meta = media.probe(make_video(tmp_path / "silent.mp4", audio=False))
    assert meta["has_audio"] is False and meta["audio_codec"] is None


def test_probe_rejects_non_video(tmp_path):
    bogus = tmp_path / "fake.mp4"
    bogus.write_bytes(b"this is not a video" * 100)
    with pytest.raises(JobError):
        media.probe(bogus)


def test_parse_rejects_audio_only():
    with pytest.raises(JobError, match="no video track"):
        media.parse_probe_output({"streams": [{"codec_type": "audio", "codec_name": "aac"}], "format": {}})


def test_parse_handles_rotation_and_fractional_fps():
    meta = media.parse_probe_output({
        "streams": [{"codec_type": "video", "codec_name": "hevc", "width": 1920, "height": 1080,
                     "avg_frame_rate": "60000/1001", "side_data_list": [{"rotation": -90}]}],
        "format": {"duration": "12.5", "bit_rate": "8000000", "format_name": "mov,mp4"},
    })
    assert (meta["width"], meta["height"]) == (1080, 1920)
    assert meta["fps"] == 59.94


def test_thumbnail(sample_video, tmp_path):
    out = media.make_thumbnail(sample_video, tmp_path / "t.jpg", 0.5)
    assert out.exists() and out.stat().st_size > 0


def test_quick_hash_is_stable_and_distinguishes(tmp_path):
    a = make_video(tmp_path / "a.mp4", color="red")
    b = make_video(tmp_path / "b.mp4", color="blue")
    copy = tmp_path / "a_copy.mp4"
    copy.write_bytes(a.read_bytes())
    assert hashing.quick_hash(a) == hashing.quick_hash(copy)
    assert hashing.quick_hash(a) != hashing.quick_hash(b)


def test_quick_hash_large_file_samples(tmp_path):
    big = tmp_path / "big.bin"
    big.write_bytes(b"\0" * (13 * 1024 * 1024))
    h1 = hashing.quick_hash(big)
    data = bytearray(big.read_bytes())
    data[len(data) // 2] = 1  # change inside the middle sample
    big.write_bytes(bytes(data))
    assert hashing.quick_hash(big) != h1
