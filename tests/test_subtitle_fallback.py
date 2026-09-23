import os
import subprocess
import pytest
from unittest.mock import patch, MagicMock

import ffmpeg_utils
from ffmpeg_utils import ensure_yuv420p, _verified_yuv420p


def test_ensure_yuv420p_nonexistent():
    assert ensure_yuv420p("nonexistent_test_file_123.mp4") is False


def test_ensure_yuv420p_caches_verified(tmp_path, monkeypatch):
    dummy_video = tmp_path / "test.mp4"
    dummy_video.write_bytes(b"dummy")
    norm_path = os.path.abspath(str(dummy_video))

    _verified_yuv420p.discard(norm_path)

    # Mock ffprobe returning yuv420p
    mock_run = MagicMock()
    mock_run.stdout = "yuv420p\n"
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: mock_run)

    # First call probes
    assert ensure_yuv420p(str(dummy_video)) is False
    assert norm_path in _verified_yuv420p

    # Second call uses cache without subprocess
    call_count = [0]
    def counting_run(*args, **kwargs):
        call_count[0] += 1
        return mock_run
    monkeypatch.setattr(subprocess, "run", counting_run)

    assert ensure_yuv420p(str(dummy_video)) is False
    assert call_count[0] == 0


def test_ensure_yuv420p_converts_gbrp(tmp_path, monkeypatch):
    dummy_video = tmp_path / "green_gbrp.mp4"
    dummy_video.write_bytes(b"0" * 2000)
    norm_path = os.path.abspath(str(dummy_video))
    _verified_yuv420p.discard(norm_path)

    # First call to ffprobe returns gbrp
    def fake_subprocess_run(cmd, *args, **kwargs):
        if "ffprobe" in cmd[0]:
            mock = MagicMock()
            mock.stdout = "gbrp\n"
            mock.returncode = 0
            return mock
        elif "ffmpeg" in cmd[0]:
            # Simulate successful conversion writing the temp file
            out_file = cmd[-1]
            with open(out_file, "wb") as f:
                f.write(b"yuv420p_content_" * 200)
            mock = MagicMock()
            mock.returncode = 0
            return mock
        raise ValueError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(subprocess, "run", fake_subprocess_run)

    converted = ensure_yuv420p(str(dummy_video))
    assert converted is True
    assert norm_path in _verified_yuv420p
