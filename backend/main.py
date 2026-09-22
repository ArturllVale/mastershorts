import sys
import os
import time

# Force UTF-8 stdio on Windows to avoid UnicodeEncodeError crashes on emojis/unicode symbols
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # Windows-safe rename: On Windows, os.rename fails with [WinError 183] if destination exists.
    # yt-dlp's FFmpegMergerPP calls os.rename(temp_filename, filename) during postprocessing merge.
    # os.replace provides atomic overwrite semantics, avoiding WinError 183 and handling transient file locks.
    _orig_os_rename = os.rename
    def _windows_safe_rename(src, dst, *args, **kwargs):
        last_exc = None
        for attempt in range(15):
            try:
                return os.replace(src, dst)
            except (FileExistsError, PermissionError, OSError) as err:
                last_exc = err
                if attempt >= 5:
                    try:
                        if os.path.isfile(dst):
                            os.remove(dst)
                        return os.replace(src, dst)
                    except Exception:
                        pass
                time.sleep(0.1 * (attempt + 1))
        if last_exc:
            raise last_exc
        return _orig_os_rename(src, dst, *args, **kwargs)

    os.rename = _windows_safe_rename
    try:
        import yt_dlp.postprocessor.ffmpeg as fpp
        fpp.os.rename = _windows_safe_rename
    except Exception:
        pass
    try:
        import yt_dlp.postprocessor.common as cpp
        cpp.os.rename = _windows_safe_rename
    except Exception:
        pass

import cv2
import subprocess
import argparse
import re
import threading
import unicodedata
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector
from ultralytics import YOLO
import torch
import os
import math
import numpy as np
from tqdm import tqdm
import yt_dlp
import mediapipe as mp
# import whisper (replaced by faster_whisper inside function)
from google import genai
from google.genai import types as genai_types

import gemini_worker
import hook_grounding
import layout_picker
import llm_backend
from clip_selection import (build_transcript_windows, clip_count_targets,
                            clip_duration_bounds, snap_clip_to_words,
                            trim_to_best)
from ffmpeg_utils import (video_encode_args, audio_encode_args, cut_clip, QUALITY,
                          QUALITY_FAST, METADATA_SCRUB)
from dotenv import load_dotenv
import json

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='google.protobuf')

# Load environment variables
load_dotenv()

# --- Constants ---
ASPECT_RATIO = 9 / 16

from core.prompts import GEMINI_PROMPT_TEMPLATE
from cameraman import SmoothedCameraman, SpeakerTracker

# Load the YOLO model once (Keep for backup or scene analysis if needed)
# YOLO_MODEL_PATH lets deployments point at a pre-downloaded weights file so a
# volume mounted over the workdir doesn't trigger a re-download at startup.
model = YOLO(os.environ.get("YOLO_MODEL_PATH", "yolov8n.pt"))

# --- MediaPipe Setup ---
# Use standard Face Detection (BlazeFace) for speed
mp_face_detection = mp.solutions.face_detection
face_detection = mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)

# Consecutive detections a large target move must survive before the camera
# follows it (see SmoothedCameraman.update_target). Env-overridable so the
# damping can be dialled back without a deploy; 1 restores the old behaviour.
JUMP_CONFIRM_FRAMES = max(int(os.environ.get("JUMP_CONFIRM_FRAMES", "3")), 1)

from reframe_v1 import process_video_to_vertical, create_general_frame, analyze_scenes_strategy, detect_scenes, get_video_resolution
from postprocessing import finalize_clip_passthrough, auto_caption_clip, auto_hook_clip, apply_watermark, render_clip
from checkpointing import TRANSCRIPT_CHECKPOINT, _checkpoint_source_key, save_transcript_checkpoint, load_transcript_checkpoint, clear_transcript_checkpoint
from core.path_utils import to_long_path, safe_exists, safe_getsize, safe_getmtime
from viral_analysis import _run_gemini_stage, _run_stage_split, score_batch_size, detail_batch_size, get_viral_clips, speech_is_sparse, get_visual_clips, _compute_visual_clips, transcribe_video
from download import download_youtube_video


def cap_source_duration(input_video, max_minutes):
    """Cut ``input_video`` down to its first ``max_minutes`` minutes, in place.

    Set through ``MAX_SOURCE_MINUTES`` by app.py when the user accepted the
    quota wall's "clip the first N minutes" offer: only N minutes were
    reserved, so nothing downstream may see more of the source than that.
    Cutting the file itself (rather than passing a window around) keeps every
    later stage byte-identical: transcription, the layout picker, the clip
    editor's re-renders and ``/api/source`` all read the same path. A source
    already within the cap is left untouched.

    Stream copy first (seconds, no quality loss; the cut lands on a packet
    boundary a fraction of a second past N). If the container refuses a copy
    the fallback re-encodes, which is slow but rare.
    """
    try:
        secs = float(max_minutes) * 60.0
    except (TypeError, ValueError):
        return input_video
    if secs <= 0:
        return input_video
    duration = 0.0
    try:
        cap = cv2.VideoCapture(input_video)
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        duration = (int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / fps) if fps else 0.0
        cap.release()
    except Exception:
        duration = 0.0
    if duration and duration <= secs + 1.0:
        return input_video
    root, ext = os.path.splitext(input_video)
    tmp = f"{root}.capped{ext or '.mp4'}"
    attempts = [
        ["-c", "copy"],
        ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k"],
    ]
    for codec_args in attempts:
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", input_video,
               "-t", f"{secs:.3f}", *codec_args, "-movflags", "+faststart", tmp]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=3600)
            os.replace(tmp, input_video)
            shown = f"{int(math.ceil(duration / 60))}" if duration else "?"
            print(f"✂️ Clipping the first {float(max_minutes):g} min of {shown}: "
                  f"that is what the plan's remaining minutes cover.")
            return input_video
        except Exception as e:
            try:
                os.remove(tmp)
            except OSError:
                pass
            print(f"⚠️ Could not cut the source to {float(max_minutes):g} min "
                  f"({' '.join(codec_args[:2])}): {str(e)[:200]}")
    raise RuntimeError(f"could not cut the source to its first {float(max_minutes):g} minutes")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="AutoCrop-Vertical with Viral Clip Detection.")
    
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('-i', '--input', type=str, help="Path to the input video file.")
    input_group.add_argument('-u', '--url', type=str, help="YouTube URL to download and process.")
    
    parser.add_argument('-o', '--output', type=str, help="Output directory or file (if processing whole video).")
    parser.add_argument('--keep-original', action='store_true', help="Keep the downloaded YouTube video.")
    parser.add_argument('--skip-analysis', action='store_true', help="Skip AI analysis and convert the whole video.")
    parser.add_argument('--format', type=str, default="auto", choices=["auto", "vertical", "horizontal", "square"],
                        help="Output aspect: vertical/auto (9:16), horizontal (keep 16:9), square (1:1).")
    parser.add_argument('--transcript', type=str,
                        help="Path to a precomputed transcript JSON (transcribe_media shape); skips transcription.")

    args = parser.parse_args()
    output_format = args.format

    script_start_time = time.time()
    
    def _ensure_dir(path: str) -> str:
        """Create directory if missing and return the same path."""
        if path:
            os.makedirs(path, exist_ok=True)
        return path
    
    # 1. Get Input Video
    if args.url:
        # For multi-clip runs, treat --output as an OUTPUT DIRECTORY (create it if needed).
        # For whole-video runs (--skip-analysis), --output can be a file path.
        if args.output and not args.skip_analysis:
            output_dir = _ensure_dir(args.output)
        else:
            # If output is a directory, use it; if it's a filename, use its directory; else default "."
            if args.output and os.path.isdir(args.output):
                output_dir = args.output
            elif args.output and not os.path.isdir(args.output):
                output_dir = os.path.dirname(args.output) or "."
            else:
                output_dir = "."
        
        input_video, video_title = download_youtube_video(args.url, output_dir)
    else:
        input_video = args.input
        video_title = os.path.splitext(os.path.basename(input_video))[0]
        
        if args.output and not args.skip_analysis:
            # For multi-clip runs, treat --output as an OUTPUT DIRECTORY (create it if needed).
            output_dir = _ensure_dir(args.output)
        else:
            # If output is a directory, use it; if it's a filename, use its directory; else default to input dir.
            if args.output and os.path.isdir(args.output):
                output_dir = args.output
            elif args.output and not os.path.isdir(args.output):
                output_dir = os.path.dirname(args.output) or os.path.dirname(input_video)
            else:
                output_dir = os.path.dirname(input_video)

    if not os.path.exists(input_video):
        print(f"❌ Input file not found: {input_video}")
        exit(1)

    # Quota-wall offer: only the first N minutes were paid for (see
    # cap_source_duration). Must run before anything reads the file.
    if os.environ.get("MAX_SOURCE_MINUTES", "").strip():
        input_video = cap_source_duration(input_video, os.environ["MAX_SOURCE_MINUTES"])

    # Layout choice is per SOURCE video, not per clip: one upload and one call
    # instead of one per clip, and the answer is a property of the material
    # ("this is a screencast"), which does not change between its own clips.
    # It runs before any render so the modules are switched on in time.
    if layout_picker.ENABLED:
        try:
            _cap = cv2.VideoCapture(input_video)
            _fps = _cap.get(cv2.CAP_PROP_FPS) or 30.0
            _duration = int(_cap.get(cv2.CAP_PROP_FRAME_COUNT)) / _fps
            _w = int(_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            _h = int(_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            _cap.release()
            from reframe_v2 import source_already_fits  # imports main back
            # A source already shot vertical has no width to reorganise, and
            # the render passes it through whatever the model says. Asking
            # anyway costs a Gemini call per upload to be ignored.
            if _w and _h and source_already_fits(_w, _h, ASPECT_RATIO):
                print(f"   ↕️  Source is {_w}x{_h} — already vertical, no layout to pick.")
            else:
                layout_picker.pick_and_apply(input_video, _duration)
        except Exception as e:
            print(f"⚠️ Layout choice skipped ({e}) — using the default layout.")

    # 2. Decision: Analyze clips or process whole?
    if args.skip_analysis:
        print("⏩ Skipping analysis, processing entire video...")
        # --output is documented as "directory or file". When it names a
        # directory we still need a filename: passing the directory through
        # ends up in os.remove() on it further down and dies with EACCES.
        output_file = args.output
        if (not output_file or os.path.isdir(output_file)
                or output_file.endswith(("/", os.sep))):
            output_file = os.path.join(output_dir, f"{video_title}_vertical.mp4")
        render_clip(input_video, output_file, output_format)
    else:
        # Get duration (needed by both the transcript and the vision path).
        cap = cv2.VideoCapture(input_video)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps
        cap.release()

        # 3. Transcribe — unless the video has no audio, in which case fall back
        # to Gemini vision (picks clips from the imagery instead of the speech).
        from transcribe_backends import NoAudioError
        transcript = None
        # Module handover (issue #68): another module already transcribed this
        # exact source with the same backend, so reuse its output. Any problem
        # with the file falls back to transcribing normally rather than failing.
        if args.transcript:
            try:
                with open(args.transcript, 'r') as f:
                    transcript = json.load(f)
                if not transcript.get('segments'):
                    raise ValueError("transcript has no segments")
                print(f"⏩ Reusing precomputed transcript "
                      f"({len(transcript['segments'])} segments) — skipping transcription.")
            except Exception as e:
                print(f"⚠️ Could not use precomputed transcript ({e}) — transcribing normally.")
                transcript = None
        if transcript is None:
            transcript = load_transcript_checkpoint(output_dir, input_video, duration)
            if transcript is not None:
                print(f"♻️ Reusing the transcript from the interrupted run "
                      f"({len(transcript['segments'])} segments) — skipping transcription.")
        if transcript is None:
            try:
                transcript = transcribe_video(input_video)
                save_transcript_checkpoint(output_dir, transcript, input_video, duration)
            except NoAudioError as e:
                print(f"🔇 {e} — switching to visual analysis.")

        # Music-only or wordless footage transcribes to a handful of words.
        # Clip it by what is on screen instead, like a video with no audio.
        if transcript is not None and speech_is_sparse(transcript, duration):
            n_words = sum(len((sg.get("text") or "").split()) for sg in transcript["segments"])
            print(f"🔇 Only {n_words} word(s) of speech in {duration:.0f}s — "
                  f"switching to visual analysis.")
            transcript = None

        # Check if metadata already exists from prior run in output_dir
        clips_data = None
        existing_meta = glob.glob(os.path.join(output_dir, "*_metadata.json"))
        if existing_meta:
            try:
                with open(to_long_path(existing_meta[0]), 'r', encoding='utf-8') as mf:
                    cand_data = json.load(mf)
                if cand_data and cand_data.get('shorts'):
                    clips_data = cand_data
                    metadata_file = existing_meta[0]
                    print(f"♻️ Reutilizando análise e {len(clips_data['shorts'])} momentos virais já identificados!", flush=True)
            except Exception:
                clips_data = None

        if clips_data is None:
            # 4. Gemini Analysis (transcript-driven, or vision for silent videos)
            print("🤖 Analisando momentos virais com Inteligência Artificial...", flush=True)
            if transcript is not None:
                clips_data = get_viral_clips(transcript, duration, video_title=video_title)
            else:
                clips_data = get_visual_clips(input_video, duration)

            if not clips_data or 'shorts' not in clips_data:
                # Deliberately fail instead of reframing the whole video: that path
                # wrote no metadata.json, so app.py marked the job failed anyway
                # (app.py:1087) after burning GPU on a render nobody could see.
                raise RuntimeError(
                    "Clip detection failed — the AI model did not return usable clips for this video.")
            else:
                print(f"🔥 {len(clips_data['shorts'])} momentos virais identificados!", flush=True)
                from clip_metadata import clean_or_generate_clip_metadata
                for c in clips_data.get('shorts', []):
                    clean_or_generate_clip_metadata(
                        c, transcript=transcript, start=c.get('start'), end=c.get('end'),
                        video_title=video_title)

                # Save metadata. Silent videos have no transcript → no subtitles,
                # which is correct (there's no speech to caption).
                clips_data['transcript'] = transcript or {"language": "none", "segments": []}
                # The clip editor's re-render path needs to find the source video
                # again and reproduce the render settings, so record both. The
                # basename is enough — the file sits in the job dir (URL jobs with
                # --keep-original) or in uploads/ (upload jobs).
                clips_data['source_video'] = os.path.basename(input_video)
                clips_data['output_format'] = output_format
                metadata_file = os.path.join(output_dir, f"{video_title}_metadata.json")
                with open(to_long_path(metadata_file), 'w', encoding='utf-8') as f:
                    json.dump(clips_data, f, indent=2)
                print(f"   Saved metadata to {metadata_file}")

        # 5. Process clips in parallel: each worker cuts + renders one
        # clip. Renders are mostly ffmpeg subprocesses (parallelize well);
        # detector inference is serialized internally via DETECT_LOCK.
        import traceback as _traceback
        import json as _json

        def _process_one_clip(i, clip):
            # Check if this clip has already been completely rendered and styled
            clean_filename = f"{video_title}_clip_{i+1}.mp4"
            suffix = f"_clip_{i+1}.mp4"
            existing_ready = None
            try:
                long_out = to_long_path(output_dir)
                if os.path.isdir(long_out):
                    candidates = []
                    for f in os.listdir(long_out):
                        if f.endswith(suffix) and not f.startswith("temp_"):
                            full_p = os.path.join(output_dir, f)
                            if safe_getsize(full_p) > 1024 * 50:
                                candidates.append(f)
                    if candidates:
                        def _score(name):
                            sc = safe_getmtime(os.path.join(output_dir, name))
                            if name.startswith("subtitled_"): sc += 1e9
                            elif name.startswith("hooked_"): sc += 5e8
                            return sc
                        existing_ready = max(candidates, key=_score)
            except Exception:
                existing_ready = None

            if existing_ready:
                print(f"♻️ Corte {i+1} já concluído anteriormente ({existing_ready}) — pulando re-renderização!", flush=True)
                print(f"CLIP_READY {i} {existing_ready}", flush=True)
                return True

            # Signal to the parent process that this clip is now being rendered.
            print(f"CLIP_RENDERING {i}", flush=True)

            start = clip['start']
            end = clip['end']
            print(f"\n🎬 Gerando corte {i+1} de {len(shorts)}…", flush=True)
            print(f"   Title: {clip.get('video_title_for_youtube_short', 'No Title')}")

            clip_filename = f"{video_title}_clip_{i+1}.mp4"
            clip_temp_path = os.path.join(output_dir, f"temp_{clip_filename}")
            clip_final_path = os.path.join(output_dir, clip_filename)

            try:
                # ffmpeg cut — re-encoding for precision on strict seconds
                cut_clip(input_video, clip_temp_path, start, end, i + 1)

                success = render_clip(clip_temp_path, clip_final_path, output_format)
                # Layer order: watermark burns into the canonical (so any
                # later hook replacement, which re-derives from it, keeps
                # the branding), the hook is a derived hooked_ file, and
                # captions go last on top of whichever is current. Each
                # worker writes only its own clip dict, so the re-dump
                # after the pool is race-free.
                if success and os.environ.get("WATERMARK") == "1":
                    apply_watermark(clip_final_path)
                deliver_path = clip_final_path
                # Which stretches were stacked (SPLIT): captions go on the
                # seam there, and /api/subtitle needs it again later.
                import layout_ranges as _layouts
                clip['layout_ranges'] = _layouts.read(clip_final_path)
                # The hook was written from the transcript alone. When the
                # render put this clip's meaning on the screen, rewrite hook
                # and title from three of its frames BEFORE burning them.
                if success and hook_grounding.wanted(clip['layout_ranges'], end - start):
                    hook_grounding.reground(clip_final_path, clip, transcript, start, end)
                if success and os.environ.get("AUTO_HOOK") == "1":
                    hooked = auto_hook_clip(clip_final_path, clip)
                    if hooked:
                        deliver_path, clip['auto_hook'] = hooked
                if success:
                    print(f"   💬 Aplicando legendas automáticas no corte {i+1}…", flush=True)
                    captioned = auto_caption_clip(
                        deliver_path, transcript, start, end,
                        split_ranges=_layouts.split_ranges(clip['layout_ranges']))
                    print(f"   ✅ Corte {i+1} pronto!", flush=True)
                    print(f"CLIP_READY {i} "
                          f"{os.path.basename(captioned or deliver_path)}", flush=True)
                return success
            finally:
                if os.path.exists(clip_temp_path):
                    os.remove(clip_temp_path)

            clip_workers = max(int(os.environ.get("CLIP_WORKERS", "3")), 1)
            shorts = clips_data['shorts']
            # Mark all clips as queued before submitting to the executor so the
            # parent process sees an explicit initial state for every clip.
            for _qi in range(len(shorts)):
                print(f"CLIP_QUEUED {_qi}", flush=True)
            with ThreadPoolExecutor(max_workers=min(clip_workers, len(shorts))) as pool:
                futures = {pool.submit(_process_one_clip, i, clip): i
                           for i, clip in enumerate(shorts)}
                _clip_outcomes: dict[int, str] = {}  # index -> "ready" | "failed"
                for future in as_completed(futures):
                    i = futures[future]
                    try:
                        future.result()
                        # CLIP_READY already printed inside _process_one_clip on
                        # success; record the outcome here for JOB_CLIPS_DONE.
                        _clip_outcomes[i] = "ready"
                    except Exception as e:
                        _clip_outcomes[i] = "failed"
                        # Emit structured failure marker so the parent (job_queue.py)
                        # can record exc_type, message and truncated traceback per clip
                        # without swallowing the exception silently.
                        _tb_text = _traceback.format_exc()[:2000]
                        _err_payload = _json.dumps({
                            "exc_type": type(e).__name__,
                            "message": str(e)[:500],
                            "traceback": _tb_text,
                        }, ensure_ascii=False)
                        print(f"CLIP_FAILED {i} {_err_payload}", flush=True)
                        print(f"   ❌ Clip {i+1} failed: {type(e).__name__}: {e}")

            # Signal to the parent how many clips landed in each terminal state
            # so it can apply the canonical job-status policy without re-scanning
            # the filesystem (which is unreliable when clips are still being written).
            _n_ready = sum(1 for s in _clip_outcomes.values() if s == "ready")
            _n_failed = sum(1 for s in _clip_outcomes.values() if s == "failed")
            print(f"JOB_CLIPS_DONE {_n_ready} {_n_failed}", flush=True)


            # Persist per-clip render results added by the workers (auto_hook)
            # so the editor can see what is already burned into each clip.
            if any('auto_hook' in c or 'hook_grounding' in c for c in shorts):
                with open(to_long_path(metadata_file), 'w', encoding='utf-8') as f:
                    json.dump(clips_data, f, indent=2)

    # Clean up original if requested
    if args.url and not args.keep_original and os.path.exists(input_video):
        os.remove(input_video)
        print(f"🗑️  Cleaned up downloaded video.")
    # The job finished: a later run in this directory must transcribe afresh.
    if not args.skip_analysis:
        clear_transcript_checkpoint(output_dir)

    total_time = time.time() - script_start_time
    print(f"\n⏱️  Total execution time: {total_time:.2f}s")
    print("🎉 Processamento finalizado com sucesso!", flush=True)

