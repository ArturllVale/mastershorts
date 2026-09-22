import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from core.path_utils import to_long_path, safe_exists, safe_getsize, safe_getmtime
from services.job_queue import _canonical_clip_file, _clips_actually_rendered


def test_to_long_path():
    p = os.path.abspath("backend/output/test.mp4")
    lp = to_long_path(p)
    if os.name == 'nt':
        assert lp.startswith('\\\\?\\')
    else:
        assert lp == p


def test_safe_helpers():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"12345")
        temp_path = f.name
    try:
        assert safe_exists(temp_path) is True
        assert safe_getsize(temp_path) == 5
        assert safe_getmtime(temp_path) > 0
    finally:
        os.remove(temp_path)
    assert safe_exists(temp_path) is False
    assert safe_getsize(temp_path) == 0


def test_canonical_clip_file_suffix_resolution(tmp_path):
    out_dir = str(tmp_path)
    base = "video_title"
    # Create clean and derived hooked + subtitled
    clean_clip = os.path.join(out_dir, f"{base}_clip_1.mp4")
    hooked_clip = os.path.join(out_dir, f"hooked_100_{base}_clip_1.mp4")
    subtitled_clip = os.path.join(out_dir, f"subtitled_200_hooked_100_{base}_clip_1.mp4")
    
    with open(clean_clip, "wb") as f: f.write(b"x" * 100)
    with open(hooked_clip, "wb") as f: f.write(b"x" * 100)
    with open(subtitled_clip, "wb") as f: f.write(b"x" * 100)
    
    # Ensure subtitled has highest mtime
    os.utime(clean_clip, (100, 100))
    os.utime(hooked_clip, (200, 200))
    os.utime(subtitled_clip, (300, 300))
    
    chosen = _canonical_clip_file(out_dir, base, 0)
    assert chosen == os.path.basename(subtitled_clip)


def test_clips_actually_rendered_string_and_int_keys(tmp_path):
    out_dir = str(tmp_path)
    base = "video"
    clip_file = os.path.join(out_dir, f"{base}_clip_1.mp4")
    with open(clip_file, "wb") as f: f.write(b"x" * 100)

    clips = [{"title": "Clip 1"}]

    # Test with string key "0" in ready_files
    job_id = "test_job_str"
    from core.state import jobs
    jobs[job_id] = {
        'status': 'processing',
        'ready_files': {"0": f"{base}_clip_1.mp4"},
        'logs': [],
    }

    rendered, missing = _clips_actually_rendered(job_id, out_dir, base, clips)
    assert len(rendered) == 1
    assert missing == 0
    assert rendered[0]['video_url'] == f"/videos/{job_id}/{base}_clip_1.mp4"
