"""Central video-encoder selection for every ffmpeg encode call site.

FFMPEG_ENCODER env values:
  x264  (default) — CPU libx264, exact pre-GPU behavior
  nvenc           — force h264_nvenc; probed once and falls back to x264
                    (with a warning) if the GPU/driver is unavailable
  auto            — h264_nvenc when the probe succeeds, else x264

Only the codec/quality args live here; surrounding args (-movflags, -pix_fmt,
audio codecs, filters) stay at each call site.
"""
import os
import subprocess
import threading
import time

# Quality tiers pinning the historical libx264 settings.
QUALITY = "quality"            # was: -preset medium -crf 18
QUALITY_FAST = "quality_fast"  # was: -preset fast -crf 18
DELIVERY = "delivery"          # was: -preset fast -crf 22

_X264_ARGS = {
    QUALITY: ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"],
    QUALITY_FAST: ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"],
    DELIVERY: ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"],
}

_NVENC_ARGS = {
    QUALITY: ["-c:v", "h264_nvenc", "-preset", "p4", "-pix_fmt", "yuv420p"],
    QUALITY_FAST: ["-c:v", "h264_nvenc", "-preset", "p4", "-pix_fmt", "yuv420p"],
    DELIVERY: ["-c:v", "h264_nvenc", "-preset", "p4", "-pix_fmt", "yuv420p"],
}

# Output args that drop container/stream metadata carried over from the source
# — most notably YouTube's "produced by Google Inc." stream handler, which
# otherwise survives every re-encode (ffmpeg copies input metadata by default)
# and rides into the published clip. The per-stream specifiers are required:
# global -map_metadata -1 alone leaves the audio handler_name intact on a
# stream copy. Empty audio/video specifiers are harmless when a clip lacks that
# stream (ffmpeg ignores them, verified). Spliced in before the output filename
# at each final-artifact producer; kept out of video_encode_args() so that
# stays purely codec/quality args.
METADATA_SCRUB = ["-map_metadata", "-1", "-map_chapters", "-1",
                  "-map_metadata:s:v", "-1", "-map_metadata:s:a", "-1"]

# Loudness normalisation for the delivered clip.
#
# Without this the clip inherits whatever the source was mastered at, so a
# user's clips land anywhere: measured across real delivered clips on
# 26-jul-2026, from -13.8 LUFS on a loud upload down to -28 LUFS on a quiet
# talk. TikTok, Reels and Shorts all normalise playback to roughly -14 LUFS,
# which means the quiet ones just sound thin next to everything else in the
# feed — the loud ones aren't rewarded, the quiet ones are punished.
#
# I=-14 matches the platforms' target, LRA=11 is the usual allowance for speech.
# Applied at the clip cut, where the audio is being encoded to AAC anyway, so it
# costs nothing extra. AUDIO_NORMALIZE=0 turns it off.
#
# TP=-2.0, not the -1.5 that matches the platforms' own advice, because the
# ceiling is enforced BEFORE the AAC encode and the encoder then adds
# inter-sample peaks on top. Measured over 14 corpus clips (31-jul-2026):
#
#   TP=-1.5   peak reached +0.2 dBTP, 1 clip clipping,  8 above -1.0
#   TP=-2.0   peak reached -0.3 dBTP, 0 clipping,       5 above -1.0
#   TP=-3.0   peak reached -0.9 dBTP, 0 clipping,       1 above -1.0
#
# -3.0 also costs level: only 8 of 14 stayed inside -15..-13 LUFS versus 12 at
# -2.0, and level is what the listener notices. Two other fixes were tried and
# do NOT work, so don't reach for them again: an `alimiter` after loudnorm
# (limits sample peaks, not inter-sample, and measured WORSE at +0.7), and
# two-pass loudnorm with linear=true (+0.4, still clipping). The overshoot is
# the codec's, so the only lever is headroom.
LOUDNORM_FILTER = "loudnorm=I=-14:TP=-2.0:LRA=11"


# AI Act art. 50(2): a provider whose system generates synthetic audio or video
# has to mark the output in a machine-readable way. The regulation asks for the
# marking, not for a particular standard, and the cheap one that survives every
# player and every upload is a container tag: `ffprobe -show_format` reads it
# back, and TikTok/Reels/YouTube ignore it. Stamped by a stream copy, so it is
# a remux (no quality loss, ~0.2 s) and never a re-encode.
#
# Deliberately narrow: it goes on outputs where a machine actually synthesised
# voice or a person (dubbing, AI actors), not on an ordinary clip, whose audio
# and pixels are the user's own footage. Marking everything would make the tag
# mean nothing.
AI_DISCLOSURE = "AI-generated content produced with OpenShorts (openshorts.app)"


def mark_ai_generated(path, detail=""):
    """Stamp AI Act art. 50(2) machine-readable tags on a finished file.

    Returns True when the file now carries the tags. Never raises: a missing
    tag must not lose the user the video they just paid minutes for.
    """
    note = f"{AI_DISCLOSURE}: {detail}" if detail else AI_DISCLOSURE
    tmp = f"{path}.aitag.mp4"
    # `comment` and not a custom `ai_generated` key: mp4 only carries the
    # standard iTunes-style tags, and ffmpeg drops anything else without
    # warning (verified with ffprobe -show_entries format_tags).
    # -map 0 because ffmpeg's default picks one stream per type: a dubbed file
    # that ever ships two audio tracks would come back with one.
    cmd = ["ffmpeg", "-y", "-i", path, "-map", "0", "-c", "copy",
           "-metadata", f"comment={note}",
           "-movflags", "+faststart", tmp]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
            print(f"[ai-tag] skipped for {os.path.basename(path)}: {r.stderr[-300:]}")
            if os.path.exists(tmp):
                os.remove(tmp)
            return False
        os.replace(tmp, path)
        return True
    except Exception as e:
        print(f"[ai-tag] skipped for {os.path.basename(path)}: {e}")
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        return False


def audio_encode_args():
    """AAC encode args for a delivered clip, with loudness normalisation."""
    args = ["-c:a", "aac"]
    filters = ["aresample=async=1"]
    if os.environ.get("AUDIO_NORMALIZE", "1").strip() != "0":
        filters.append(LOUDNORM_FILTER)
    args = ["-af", ",".join(filters)] + args
    return args

_probe_lock = threading.Lock()
_nvenc_ok = None  # None = not probed yet
_announced = False


def _probe_nvenc():
    """Detect NVENC availability by testing real encoding on a dummy frame."""
    cmd_probe = ["ffmpeg", "-hide_banner", "-encoders"]
    try:
        result = subprocess.run(
            cmd_probe, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5, text=True
        )
        if "h264_nvenc" not in result.stdout:
            return False
    except Exception:
        return False

    cmd_test = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "color=s=64x64:d=0.04",
        "-c:v", "h264_nvenc",
        "-f", "null", "-"
    ]
    try:
        r = subprocess.run(cmd_test, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def nvenc_available():
    """Probe h264_nvenc once and cache the verdict (thread-safe)."""
    global _nvenc_ok
    if _nvenc_ok is None:
        with _probe_lock:
            if _nvenc_ok is None:
                _nvenc_ok = _probe_nvenc()
    return _nvenc_ok


def reset_encoder_cache():
    """Test hook: forget the cached probe result."""
    global _nvenc_ok, _announced
    with _probe_lock:
        _nvenc_ok = None
        _announced = False


def video_encode_args(tier=QUALITY):
    """Return the codec/quality args for one encode, honoring FFMPEG_ENCODER (defaults to auto/GPU)."""
    global _announced
    if tier not in _X264_ARGS:
        raise ValueError(f"Unknown encode tier: {tier!r}")

    mode = os.environ.get("FFMPEG_ENCODER", "auto").strip().lower()
    if mode not in ("x264", "nvenc", "auto"):
        mode = "auto"

    use_nvenc = False
    if mode in ("nvenc", "auto"):
        use_nvenc = nvenc_available()
        if mode == "nvenc" and not use_nvenc:
            print("⚠️ [Encoder] FFMPEG_ENCODER=nvenc but h264_nvenc is not "
                  "usable here — falling back to libx264")

    if not _announced:
        _announced = True
        print(f"Encoder escolhido: {'h264_nvenc (GPU)' if use_nvenc else 'libx264 (CPU)'}")

    return list((_NVENC_ARGS if use_nvenc else _X264_ARGS)[tier])


def get_selected_encoder_name() -> str:
    """Return friendly name of the active encoder: 'GPU - NVIDIA NVENC' or 'CPU - libx264'."""
    mode = os.environ.get("FFMPEG_ENCODER", "auto").strip().lower()
    use_nvenc = False
    if mode in ("nvenc", "auto"):
        use_nvenc = nvenc_available()
    return "GPU - NVIDIA NVENC" if use_nvenc else "CPU - libx264"


def escape_filter_value(value):
    r"""Escape a path/value for use inside a quoted FFmpeg filter argument.

    Windows absolute paths are why this exists: ``:`` separates filter options,
    so an interpolated ``C:/x/y.txt`` makes the parser look for an option named
    ``/x/y.txt`` and the whole filtergraph fails to build.

    NOTE: an apostrophe in the path cannot be made safe here. ffmpeg's
    filtergraph parser is not a shell -- the shell idiom ``'\''`` was tried on
    29-jul-2026 and is worse than doing nothing: it drops the apostrophe AND
    swallows the following option, so ``ass='...Earth'\''s.ass':fontsdir='...'``
    resolved to a filename of "...Earths.ass:fontsdir=..." and failed to open.

    The only reliable answer is to keep apostrophes OUT of any path that is
    interpolated into a filter. Callers generate their own filenames, so they
    control this: use a neutral name, never one derived from a video title.
    """
    return value.replace('\\', '/').replace(':', '\\:').replace("'", "\\'")


# An mp4 that ffmpeg abandoned before writing the moov atom is a few dozen
# bytes of ftyp, or nothing at all. Anything a real cut produces is orders of
# magnitude larger, so this only ever catches a failed encode.
MIN_CUT_BYTES = 1024

# Retries of a failed cut, on the SAME encoder, and how long to wait before
# each one. Deliberately not a fallback to libx264: the clip has to come out
# of the GPU like every other one, and a CPU re-encode of a 1080p cut on a box
# that is already busy enough to have failed the first attempt is the wrong
# trade. Waiting is the whole mechanism — whatever the GPU could not give this
# encode, another job finishes and gives back.
CUT_RETRY_WAITS = (3, 9)


def cut_clip(input_video, clip_temp_path, start, end, clip_number):
    """Cut [start, end] out of the source into ``clip_temp_path``.

    Raises RuntimeError with ffmpeg's own stderr when the cut does not produce
    a playable file. That report is the point: since dec-2025 the cut ran with
    its return code ignored and stderr captured into a pipe nobody read, so a
    failed cut handed an empty file to the reframer and the job's only visible
    error was "moov atom not found" three layers downstream — from ffmpeg,
    TransNetV2 and PySceneDetect in turn, each naming the temp file rather
    than the encode that never wrote it (prod, 9-sep-2026: three clips of one
    job lost, cause unrecoverable because the stderr had been discarded).

    A failed cut is retried on the same encoder after a wait. The failure this
    exists for is transient: the same command, on the same source file, cut
    fine by hand minutes later, and the nvenc probe is a 256x256 lavfi frame
    cached for the life of the process, so it stays true while a real 1080p
    session cannot allocate on a GPU that other jobs are filling.
    """
    start_f = float(start)
    end_f = float(end)
    if start_f >= end_f:
        # Invalid timestamps from LLM: swap or fix to avoid ffmpeg crash (0:00 video)
        if start_f > end_f and end_f > 0:
            start_f, end_f = end_f, start_f
        else:
            end_f = start_f + 15.0
            
    encode_args = video_encode_args(QUALITY_FAST)
    command = [
        'ffmpeg', '-y',
        '-ss', str(start_f),
        '-t', str(end_f - start_f),
        '-i', input_video,
        *encode_args,
        *audio_encode_args(),
        clip_temp_path
    ]

    def _run():
        result = subprocess.run(command, stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, text=True, errors="replace")
        # ffmpeg has been seen exiting 0 having written nothing, so the file
        # itself is the verdict, not just the return code.
        size = os.path.getsize(clip_temp_path) if os.path.exists(clip_temp_path) else 0
        ok = result.returncode == 0 and size >= MIN_CUT_BYTES
        return ok, f"exit {result.returncode}, {size} bytes\n{(result.stderr or '').strip()[-800:]}"

    for attempt, wait in enumerate(CUT_RETRY_WAITS + (None,), start=1):
        ok, report = _run()
        if ok:
            if attempt > 1:
                print(f"   ✅ Clip {clip_number} cut on attempt {attempt}.")
            return
        if wait is None:
            break
        print(f"   ⚠️ Cut of clip {clip_number} failed ({report}) — "
              f"retrying in {wait}s.")
        time.sleep(wait)

    raise RuntimeError(
        f"ffmpeg could not cut clip {clip_number} ({start}s-{end}s) from "
        f"{os.path.basename(input_video)} in {len(CUT_RETRY_WAITS) + 1} "
        f"attempts: {report}")


_verified_yuv420p = set()

def ensure_yuv420p(video_path: str) -> bool:
    """Checks if video is encoded in an incompatible pixel format (gbrp, yuv444p, etc.)
    and converts it in-place to yuv420p so browser playback does not show green screens
    or decoding failures. Thread-safe and caches verified paths."""
    if not video_path or not os.path.isfile(video_path):
        return False
    norm_path = os.path.abspath(video_path)
    if norm_path in _verified_yuv420p:
        return False
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=pix_fmt', '-of', 'default=noprint_wrappers=1:nokey=1',
            norm_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        pix_fmt = res.stdout.strip().lower()
        if not pix_fmt or pix_fmt == 'yuv420p':
            _verified_yuv420p.add(norm_path)
            return False

        # Incompatible with standard browser/hardware decoders (gbrp causes the green tint bug)
        if pix_fmt in ('gbrp', 'yuv444p', 'rgb24', 'bgr24', 'yuv422p', 'gbrp10le', 'gbrp12le'):
            print(f"⚠️ Video {os.path.basename(norm_path)} is in '{pix_fmt}'. Converting to 'yuv420p'...")
            temp_path = norm_path + ".fixed.mp4"
            conv_cmd = [
                'ffmpeg', '-y', '-i', norm_path,
                *video_encode_args(QUALITY_FAST),
                '-c:a', 'copy',
                *METADATA_SCRUB,
                '-movflags', '+faststart',
                temp_path
            ]
            conv_res = subprocess.run(conv_cmd, capture_output=True, timeout=120)
            if conv_res.returncode == 0 and os.path.exists(temp_path) and os.path.getsize(temp_path) > 1000:
                os.replace(temp_path, norm_path)
                _verified_yuv420p.add(norm_path)
                print(f"✅ Converted {os.path.basename(norm_path)} to yuv420p successfully.")
                return True
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
    except Exception as e:
        print(f"⚠️ ensure_yuv420p check failed for {norm_path}: {e}")
    return False


