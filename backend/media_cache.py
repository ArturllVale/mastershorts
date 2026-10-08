"""
Centralized media and transcript caching across all project jobs and folders.

Prevents redundant network downloads and expensive ASR re-transcription by:
1. Normalizing URLs into canonical video keys (e.g. YouTube video ID).
2. Searching existing project job directories (output/*) and the central registry.
3. Hardlinking/copying cached video assets into the current job directory.
4. Reusing cached transcripts if the source video or URL was previously transcribed.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import shutil
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urlparse, parse_qs

from core.config import OUTPUT_DIR
from core.path_utils import to_long_path, safe_exists, safe_getsize

MEDIA_CACHE_DIR = os.path.join(OUTPUT_DIR, ".media_cache")
REGISTRY_FILE = os.path.join(MEDIA_CACHE_DIR, "registry.json")


def extract_video_identifier(url: Optional[str]) -> str:
    """Extract a canonical identifier for a video URL.

    For YouTube: extracts the unique 11-char video ID (independent of query params/domain).
    For other URLs: canonicalizes the scheme/host/path and hashes it.
    """
    if not url:
        return ""
    clean = str(url).strip()
    try:
        parsed = urlparse(clean)
        host = (parsed.hostname or "").lower()

        # youtu.be/<id>
        if host in ("youtu.be", "www.youtu.be"):
            vid = parsed.path.strip("/").split("/")[0]
            if vid and len(vid) >= 6:
                return f"yt_{vid}"

        # youtube.com
        if any(h in host for h in ("youtube.com", "youtube-nocookie.com", "googlevideo.com")):
            # /watch?v=<id>
            qs = parse_qs(parsed.query)
            if "v" in qs and qs["v"] and len(qs["v"][0]) >= 6:
                return f"yt_{qs['v'][0]}"
            # /shorts/<id>
            if "/shorts/" in parsed.path:
                vid = parsed.path.split("/shorts/")[1].strip("/").split("/")[0]
                if vid and len(vid) >= 6:
                    return f"yt_{vid}"
            # /embed/<id>
            if "/embed/" in parsed.path:
                vid = parsed.path.split("/embed/")[1].strip("/").split("/")[0]
                if vid and len(vid) >= 6:
                    return f"yt_{vid}"
            # /v/<id>
            if "/v/" in parsed.path:
                vid = parsed.path.split("/v/")[1].strip("/").split("/")[0]
                if vid and len(vid) >= 6:
                    return f"yt_{vid}"

        # Fallback: Normalized scheme + host + path (strip tracking queries)
        canonical_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        h = hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:16]
        return f"url_{h}"
    except Exception:
        h = hashlib.sha256(clean.encode("utf-8")).hexdigest()[:16]
        return f"url_{h}"


def _get_registry() -> Dict[str, Any]:
    try:
        if safe_exists(REGISTRY_FILE):
            with open(to_long_path(REGISTRY_FILE), "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_registry(registry: Dict[str, Any]) -> None:
    try:
        os.makedirs(to_long_path(MEDIA_CACHE_DIR), exist_ok=True)
        tmp = os.path.join(MEDIA_CACHE_DIR, f"registry_tmp_{os.getpid()}.json")
        with open(to_long_path(tmp), "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
        shutil.move(to_long_path(tmp), to_long_path(REGISTRY_FILE))
    except Exception as e:
        print(f"⚠️ Could not save media cache registry: {e}")


def _is_valid_video_file(path: str) -> bool:
    if not safe_exists(path) or safe_getsize(path) < 1024 * 512:
        return False
    try:
        import cv2
        probe = cv2.VideoCapture(to_long_path(path))
        valid = probe.isOpened() and int(probe.get(cv2.CAP_PROP_FRAME_COUNT) or 0) > 0
        probe.release()
        return valid
    except Exception:
        return True  # If OpenCV check fails to load, rely on size > 512KB


def _link_or_copy(src: str, dst: str) -> None:
    """Prefer hardlink (zero disk cost, instant) and fall back to copy2."""
    if os.path.abspath(src) == os.path.abspath(dst):
        return
    if safe_exists(dst):
        try:
            os.remove(to_long_path(dst))
        except Exception:
            pass
    try:
        os.link(to_long_path(src), to_long_path(dst))
    except Exception:
        shutil.copy2(to_long_path(src), to_long_path(dst))


def find_existing_video(url: str, output_dir: str) -> Optional[Tuple[str, str]]:
    """Search for an already-downloaded video corresponding to this URL across the project.

    Checks:
    1. output_dir itself
    2. Central media cache registry (.media_cache/registry.json)
    3. Any existing job directory in output/
    """
    key = extract_video_identifier(url)
    if not key:
        return None

    # 1. Check registry
    registry = _get_registry()
    entry = registry.get(key)
    if entry:
        cached_path = entry.get("source_video_path")
        base_name = entry.get("base_name")
        if cached_path and _is_valid_video_file(cached_path):
            dest_path = os.path.join(output_dir, os.path.basename(cached_path))
            _link_or_copy(cached_path, dest_path)
            print(f"♻️ Vídeo reutilizado do cache ({cached_path}) — download cancelado!", flush=True)
            return dest_path, base_name or os.path.splitext(os.path.basename(cached_path))[0]

    # 2. Search all output/*/ metadata files for matching source_url or video identifier
    try:
        long_out = to_long_path(OUTPUT_DIR)
        if os.path.isdir(long_out):
            meta_pattern = os.path.join(long_out, "*", "*_metadata.json")
            for meta_path in glob.glob(meta_pattern):
                try:
                    with open(meta_path, "r", encoding="utf-8") as mf:
                        mdata = json.load(mf)
                    m_url = mdata.get("source_url")
                    m_key = extract_video_identifier(m_url) if m_url else None
                    if m_key == key or (m_url and m_url == url):
                        job_dir = os.path.dirname(meta_path)
                        src_name = mdata.get("source_video")
                        if src_name:
                            cand_path = os.path.join(job_dir, os.path.basename(src_name))
                            if _is_valid_video_file(cand_path):
                                base_name = os.path.splitext(os.path.basename(cand_path))[0]
                                dest_path = os.path.join(output_dir, os.path.basename(cand_path))
                                _link_or_copy(cand_path, dest_path)
                                # Register in cache for fast O(1) next time
                                register_cached_video(url, cand_path, base_name)
                                if mdata.get("transcript"):
                                    save_cached_transcript(url, cand_path, mdata["transcript"])
                                print(f"♻️ Vídeo reutilizado do projeto ({cand_path}) — download cancelado!", flush=True)
                                return dest_path, base_name
                except Exception:
                    continue
    except Exception:
        pass

    return None


def register_cached_video(url: str, video_path: str, base_name: str) -> None:
    """Store video entry in registry."""
    key = extract_video_identifier(url)
    if not key or not safe_exists(video_path):
        return
    registry = _get_registry()
    data = registry.get(key, {})
    data.update({
        "url": url,
        "source_video_path": os.path.abspath(video_path),
        "base_name": base_name,
        "updated_at": os.path.getmtime(video_path) if safe_exists(video_path) else 0,
    })
    registry[key] = data
    _save_registry(registry)


def find_existing_transcript(
    url: Optional[str] = None,
    input_video: Optional[str] = None,
    duration: Optional[float] = None
) -> Optional[dict]:
    """Find a pre-computed transcript for this URL or source video across the project."""
    key = extract_video_identifier(url) if url else None
    registry = _get_registry()

    # 1. Direct registry hit by URL key
    if key and key in registry:
        t = registry[key].get("transcript")
        if t and isinstance(t, dict) and t.get("segments"):
            return t

    # 2. Hit by filename and duration in registry
    if input_video:
        video_base = os.path.basename(input_video)
        for _, entry in registry.items():
            if os.path.basename(entry.get("source_video_path", "")) == video_base:
                t = entry.get("transcript")
                if t and isinstance(t, dict) and t.get("segments"):
                    return t

    # 3. Search existing metadata.json files in output/*/
    try:
        long_out = to_long_path(OUTPUT_DIR)
        if os.path.isdir(long_out):
            meta_pattern = os.path.join(long_out, "*", "*_metadata.json")
            for meta_path in glob.glob(meta_pattern):
                try:
                    with open(meta_path, "r", encoding="utf-8") as mf:
                        mdata = json.load(mf)
                    m_url = mdata.get("source_url")
                    m_key = extract_video_identifier(m_url) if m_url else None
                    match_url = (key and m_key == key) or (url and m_url == url)
                    match_video = (input_video and mdata.get("source_video") == os.path.basename(input_video))

                    if match_url or match_video:
                        t = mdata.get("transcript")
                        if t and isinstance(t, dict) and t.get("segments"):
                            # Save to registry for next time
                            if key:
                                save_cached_transcript(url, input_video, t, duration)
                            return t
                except Exception:
                    continue
    except Exception:
        pass

    return None


def save_cached_transcript(
    url: Optional[str],
    input_video: Optional[str],
    transcript: dict,
    duration: Optional[float] = None
) -> None:
    """Store transcript in registry."""
    if not transcript or not isinstance(transcript, dict) or not transcript.get("segments"):
        return
    key = extract_video_identifier(url) if url else None
    if not key and input_video:
        key = f"file_{hashlib.sha256(os.path.basename(input_video).encode()).hexdigest()[:16]}"
    if not key:
        return

    registry = _get_registry()
    data = registry.get(key, {})
    data["transcript"] = transcript
    if url:
        data["url"] = url
    if input_video:
        data["source_video_path"] = os.path.abspath(input_video)
        data["base_name"] = os.path.splitext(os.path.basename(input_video))[0]
    if duration:
        data["duration"] = round(float(duration), 2)
    registry[key] = data
    _save_registry(registry)
