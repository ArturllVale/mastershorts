"""test_clip_state_machine — testes da máquina de estados de clips.

Verifica:
- compute_job_status() com todas as combinações canônicas
- Integração com enqueue_output(): markers CLIP_QUEUED / CLIP_RENDERING /
  CLIP_READY / CLIP_FAILED são parseados e persistidos em clip_states /
  clip_errors
- Cenário principal: 3 clips, 2 ready + 1 failed → job.status == "partial"
"""
import io
import json

import pytest

# ---------------------------------------------------------------------------
# Import: clip_state (sem dependências externas — deve importar sempre)
# ---------------------------------------------------------------------------
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "services"))

from clip_state import compute_job_status, make_clip_error, encode_clip_failed_marker


# ===========================================================================
# Unit tests — compute_job_status
# ===========================================================================

class TestComputeJobStatus:
    def test_all_ready_is_completed(self):
        assert compute_job_status(["ready", "ready", "ready"]) == "completed"

    def test_all_failed_is_failed(self):
        assert compute_job_status(["failed", "failed"]) == "failed"

    def test_mixed_ready_and_failed_is_partial(self):
        assert compute_job_status(["ready", "failed", "ready"]) == "partial"

    def test_single_ready_is_completed(self):
        assert compute_job_status(["ready"]) == "completed"

    def test_single_failed_is_failed(self):
        assert compute_job_status(["failed"]) == "failed"

    def test_empty_list_is_failed(self):
        assert compute_job_status([]) == "failed"

    def test_non_terminal_states_alone_are_failed(self):
        # Pool finished but no marker reached terminal state — treat as failed
        assert compute_job_status(["queued", "rendering"]) == "failed"

    def test_ready_and_nonterminal_is_completed(self):
        # If at least one ready and none failed, it's completed
        # (non-terminal left over from a crashed marker pipeline)
        assert compute_job_status(["ready", "queued"]) == "completed"

    def test_partial_ignores_nonterminal(self):
        assert compute_job_status(["ready", "failed", "rendering"]) == "partial"


# ===========================================================================
# Unit tests — make_clip_error / encode_clip_failed_marker
# ===========================================================================

class TestMakeClipError:
    def test_keys_present(self):
        try:
            raise ValueError("something broke")
        except ValueError as e:
            err = make_clip_error(e)
        assert err["exc_type"] == "ValueError"
        assert "something broke" in err["message"]
        assert "ValueError" in err["traceback"]

    def test_message_truncated_at_500(self):
        try:
            raise RuntimeError("x" * 1000)
        except RuntimeError as e:
            err = make_clip_error(e)
        assert len(err["message"]) <= 500

    def test_traceback_truncated_at_2000(self):
        try:
            raise OSError("big")
        except OSError as e:
            err = make_clip_error(e)
        assert len(err["traceback"]) <= 2000

    def test_encode_marker_is_parseable(self):
        try:
            raise TypeError("bad type")
        except TypeError as e:
            line = encode_clip_failed_marker(2, e)
        assert line.startswith("CLIP_FAILED 2 ")
        payload = json.loads(line[len("CLIP_FAILED 2 "):])
        assert payload["exc_type"] == "TypeError"


# ===========================================================================
# Integration — enqueue_output marker parsing
# ===========================================================================

app = pytest.importorskip("app")
from services.job_queue import _clip_state_cache, _clip_error_cache

def _feed(job_id, *lines):
    stream = io.BytesIO(b"".join(ln.encode("utf-8") + b"\n" for ln in lines))
    app.enqueue_output(stream, job_id)


class TestEnqueueOutputParsesNewMarkers:
    def setup_method(self):
        self.job_id = "test-state-machine"
        app.jobs[self.job_id] = {"logs": []}
        _clip_state_cache.pop(self.job_id, None)
        _clip_error_cache.pop(self.job_id, None)

    def teardown_method(self):
        app.jobs.pop(self.job_id, None)
        _clip_state_cache.pop(self.job_id, None)
        _clip_error_cache.pop(self.job_id, None)

    def test_clip_queued_sets_state(self):
        _feed(self.job_id, "CLIP_QUEUED 0", "CLIP_QUEUED 1")
        states = _clip_state_cache.get(self.job_id, {})
        assert states.get(0) == "queued"
        assert states.get(1) == "queued"

    def test_clip_rendering_transitions_state(self):
        _feed(self.job_id, "CLIP_QUEUED 0", "CLIP_RENDERING 0")
        states = _clip_state_cache.get(self.job_id, {})
        assert states.get(0) == "rendering"

    def test_clip_ready_sets_ready_state(self):
        _feed(self.job_id, "CLIP_READY 0 my_video_clip_1.mp4")
        states = _clip_state_cache.get(self.job_id, {})
        assert states.get(0) == "ready"
        # Also populates ready_files as before (no regression)
        assert app.jobs[self.job_id]["ready_files"].get(0) == "my_video_clip_1.mp4"

    def test_clip_failed_sets_failed_state_and_error(self):
        err_payload = json.dumps({
            "exc_type": "RuntimeError",
            "message": "ffmpeg died",
            "traceback": "Traceback...",
        })
        _feed(self.job_id, f"CLIP_FAILED 1 {err_payload}")
        states = _clip_state_cache.get(self.job_id, {})
        errors = _clip_error_cache.get(self.job_id, {})
        assert states.get(1) == "failed"
        assert errors.get(1, {}).get("exc_type") == "RuntimeError"
        assert "ffmpeg died" in errors.get(1, {}).get("message", "")

    def test_malformed_clip_failed_does_not_raise(self):
        _feed(self.job_id, "CLIP_FAILED notanumber {bad json}")
        # Must not crash — state simply not recorded

    def test_new_markers_never_reach_user_log(self):
        err_payload = json.dumps({"exc_type": "E", "message": "m", "traceback": "t"})
        _feed(
            self.job_id,
            "CLIP_QUEUED 0",
            "CLIP_RENDERING 0",
            "CLIP_READY 0 file.mp4",
            f"CLIP_FAILED 1 {err_payload}",
            "JOB_CLIPS_DONE 1 1",
            "Normal log line",
        )
        # Only the plain log line must appear in user-visible logs
        logs = list(app.jobs[self.job_id].get("logs", []))
        for entry in logs:
            assert not entry.startswith("CLIP_QUEUED")
            assert not entry.startswith("CLIP_RENDERING")
            assert not entry.startswith("CLIP_READY")
            assert not entry.startswith("CLIP_FAILED")
            assert not entry.startswith("JOB_CLIPS_DONE")
        assert any("Normal log line" in e for e in logs)


# ===========================================================================
# Main scenario: 3 clips, 2 ready + 1 forced failure → job.status == "partial"
# ===========================================================================

class TestPartialJobScenario:
    """
    Simulates 3 clips:
        clip 0 → ready
        clip 1 → failed (forced exception)
        clip 2 → ready

    Expected:
        job.status == "partial"
        exactly 2 clips with state "ready"
        exactly 1 clip with state "failed", containing error details
    """

    def setup_method(self):
        self.job_id = "test-partial-job"
        app.jobs[self.job_id] = {"logs": []}
        _clip_state_cache.pop(self.job_id, None)
        _clip_error_cache.pop(self.job_id, None)

    def teardown_method(self):
        app.jobs.pop(self.job_id, None)
        _clip_state_cache.pop(self.job_id, None)
        _clip_error_cache.pop(self.job_id, None)

    def _feed_3clip_scenario(self):
        err_payload = json.dumps({
            "exc_type": "RuntimeError",
            "message": "simulated render crash",
            "traceback": "Traceback (most recent call last):\n  ...\nRuntimeError: simulated render crash",
        })
        _feed(
            self.job_id,
            # queued phase
            "CLIP_QUEUED 0",
            "CLIP_QUEUED 1",
            "CLIP_QUEUED 2",
            # rendering phase
            "CLIP_RENDERING 0",
            "CLIP_RENDERING 1",
            "CLIP_RENDERING 2",
            # outcomes
            "CLIP_READY 0 video_clip_1.mp4",
            f"CLIP_FAILED 1 {err_payload}",
            "CLIP_READY 2 video_clip_3.mp4",
            "JOB_CLIPS_DONE 2 1",
        )

    def test_job_status_is_partial(self):
        self._feed_3clip_scenario()
        clip_states = _clip_state_cache.get(self.job_id, {})
        status = compute_job_status(list(clip_states.values()))
        assert status == "partial", f"Expected 'partial', got '{status}'"

    def test_exactly_2_clips_ready(self):
        self._feed_3clip_scenario()
        clip_states = _clip_state_cache.get(self.job_id, {})
        n_ready = sum(1 for s in clip_states.values() if s == "ready")
        assert n_ready == 2

    def test_exactly_1_clip_failed(self):
        self._feed_3clip_scenario()
        clip_states = _clip_state_cache.get(self.job_id, {})
        n_failed = sum(1 for s in clip_states.values() if s == "failed")
        assert n_failed == 1

    def test_failed_clip_has_error_details(self):
        self._feed_3clip_scenario()
        clip_errors = _clip_error_cache.get(self.job_id, {})
        # clip index 1 failed
        assert 1 in clip_errors, f"Expected error for clip 1, got keys: {list(clip_errors)}"
        err = clip_errors[1]
        assert err.get("exc_type") == "RuntimeError"
        assert "simulated render crash" in err.get("message", "")
        assert "traceback" in err

    def test_failed_clip_index_is_correct(self):
        self._feed_3clip_scenario()
        clip_states = _clip_state_cache.get(self.job_id, {})
        assert clip_states.get(0) == "ready"
        assert clip_states.get(1) == "failed"
        assert clip_states.get(2) == "ready"
