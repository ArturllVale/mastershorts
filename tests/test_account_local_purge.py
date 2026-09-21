"""Local-disk purge on account erasure (app._purge_local_jobs_for_user).

Two failure modes matter here and neither shows up in a unit-free reading of
the code: erasing one user's files must not touch another's (the API is
multi-tenant, and the three stores record ownership three different ways), and
a session id or output_dir that walks out of the working directories must not
delete anything at all.
"""
import os
import pytest
from core import state
from services import job_queue

MINE = "aaaa-1111"
THEIRS = "bbbb-2222"

def _write(path, body="x"):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w") as f:
        f.write(body)

@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("output/thumbnails", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)
    fake_jobs = {}
    fake_thumbs = {}
    monkeypatch.setattr(state, "jobs", fake_jobs)
    monkeypatch.setattr(state, "thumbnail_sessions", fake_thumbs)
    monkeypatch.setattr(job_queue, "jobs", fake_jobs)
    monkeypatch.setattr(job_queue, "thumbnail_sessions", fake_thumbs)
    from core import config
    monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(config, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(config, "THUMBNAILS_DIR", str(tmp_path / "output" / "thumbnails"))
    monkeypatch.setattr(job_queue, "OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setattr(job_queue, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(job_queue, "THUMBNAILS_DIR", str(tmp_path / "output" / "thumbnails"))
    return tmp_path

class TestClipJobs:
    def test_erases_jobs_marked_with_an_owner_file(self, workdir):
        _write("output/job1/.owner", MINE)
        _write("output/job1/clip.mp4")
        _write("uploads/job1_source.mp4")

        job_queue._purge_local_jobs_for_user(MINE)

        assert not os.path.exists("output/job1")
        assert not os.path.exists("uploads/job1_source.mp4")

    def test_erases_in_memory_jobs_with_no_owner_file(self, workdir):
        _write("output/job2/clip.mp4")
        state.jobs["job2"] = {"user_id": MINE, "status": "completed"}

        job_queue._purge_local_jobs_for_user(MINE)

        assert not os.path.exists("output/job2")
        assert "job2" not in state.jobs

    def test_leaves_another_users_jobs_alone(self, workdir):
        _write("output/theirs/.owner", THEIRS)
        _write("output/theirs/clip.mp4")
        _write("uploads/theirs_source.mp4")

        job_queue._purge_local_jobs_for_user(MINE)

        assert os.path.exists("output/theirs/clip.mp4")
        assert os.path.exists("uploads/theirs_source.mp4")

    def test_leaves_unowned_self_host_jobs_alone(self, workdir):
        _write("output/anon/clip.mp4")
        state.jobs["anon"] = {"user_id": None, "status": "completed"}

        job_queue._purge_local_jobs_for_user(MINE)

        assert os.path.exists("output/anon/clip.mp4")

class TestOtherStores:
    def test_erases_generated_thumbnails_and_their_source(self, workdir):
        _write("output/thumbnails/t1/thumb.png")
        _write("uploads/thumb_t1_video.mp4")
        state.thumbnail_sessions["t1"] = {
            "user_id": MINE, "video_path": "uploads/thumb_t1_video.mp4"}

        job_queue._purge_local_jobs_for_user(MINE)

        assert not os.path.exists("output/thumbnails/t1")
        assert not os.path.exists("uploads/thumb_t1_video.mp4")
        assert "t1" not in state.thumbnail_sessions

    def test_leaves_another_users_thumbnails_alone(self, workdir):
        _write("output/thumbnails/t2/thumb.png")
        state.thumbnail_sessions["t2"] = {"user_id": THEIRS}

        job_queue._purge_local_jobs_for_user(MINE)

        assert os.path.exists("output/thumbnails/t2/thumb.png")

    def test_keeps_the_thumbnails_directory_itself(self, workdir):
        _write("output/thumbnails/t1/thumb.png")
        state.thumbnail_sessions["t1"] = {"user_id": MINE}

        job_queue._purge_local_jobs_for_user(MINE)

        assert os.path.isdir("output/thumbnails")

class TestPathTraversal:
    def test_a_poisoned_session_id_deletes_nothing(self, workdir):
        _write("secret.txt", "keep me")
        state.thumbnail_sessions["../../secret.txt"] = {"user_id": MINE}

        job_queue._purge_local_jobs_for_user(MINE)

        assert os.path.exists("secret.txt")
