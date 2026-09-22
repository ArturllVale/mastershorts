import re

with open("backend/main.py", "r", encoding="utf-8") as f:
    code = f.read()

replacement = """def get_visual_clips(video_path, video_duration, language="en"):
    from services.cache import get_or_compute
    import asyncio
    import os
    source_hash = os.environ.get("SOURCE_HASH")

    def _compute():
        return _compute_visual_clips(video_path, video_duration, language)

    if source_hash:
        return asyncio.run(get_or_compute(source_hash, "visual_clips", _compute))
    return _compute()

def _compute_visual_clips(video_path, video_duration, language="en"):"""

code = code.replace('def get_visual_clips(video_path, video_duration, language="en"):', replacement)

with open("backend/main.py", "w", encoding="utf-8") as f:
    f.write(code)
