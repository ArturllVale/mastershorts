import os
import subprocess
import time
import uuid
from ffmpeg_utils import video_encode_args, QUALITY, METADATA_SCRUB

ASPECT_RATIO = 9 / 16

from reframe_v1 import process_video_to_vertical

def finalize_clip_passthrough(input_video, final_output_video):
    """Keep the clip's native framing (for horizontal/16:9 output).

    The input is the freshly encoded cut, so a stream-copy remux is enough to
    add +faststart — re-encoding here would only cost time and quality.
    """
    if os.path.exists(final_output_video):
        os.remove(final_output_video)
    print(f"🎬 Passthrough (native framing): {input_video}")
    cmd = [
        'ffmpeg', '-y', '-i', input_video,
        '-c', 'copy', *METADATA_SCRUB, '-movflags', '+faststart',
        final_output_video,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800)
    print(f"✅ Clip saved to {final_output_video}")
    return True


def auto_caption_clip(clip_path, transcript, clip_start, clip_end, split_ranges=None):
    """Burn the default caption style onto a finished clip.

    ``split_ranges``: (start, end) stretches, in clip seconds, rendered with
    the SPLIT layout; captions there sit on the seam between the two speakers
    instead of the bottom. None reads the render's own sidecar next to
    ``clip_path`` (layout_ranges), which is where recut hands it over.

    Captions are mandatory for short-form to land, but they were opt-in behind a
    modal and only 9% of delivered clips ever got them (prod audit, 25-jul-2026).
    So every clip now ships captioned by default.

    The captioned file is written ALONGSIDE the clip as
    ``subtitled_<ts>_<clip>.mp4`` — the same convention /api/subtitle uses — so
    the untouched original stays on disk and re-styling from the modal replaces
    the captions instead of burning a second layer over them.

    Returns the captioned path, or None when captions were skipped (silent
    video, no words in range, AUTO_CAPTIONS=0, or any failure — a caption
    problem must never cost the user the clip they already paid for).
    """
    if os.environ.get("AUTO_CAPTIONS", "1").strip() == "0":
        return None
    if not transcript or not transcript.get('segments'):
        return None  # silent video: nothing to caption
    try:
        import subtitles as _subs
        style = _subs.AUTO_CAPTION_STYLE
        output_dir = os.path.dirname(clip_path)
        stem = os.path.basename(clip_path)
        generation_id = int(time.time())
        # The output name MUST stay exactly "subtitled_<ts>_<clip filename>":
        # the modal's walk-back and _canonical_clip_file both reconstruct the
        # clean original from it, so trimming the stem here would orphan the
        # pair. Length is bounded upstream instead, by MAX_TITLE_BYTES at
        # download time. A legacy clip whose name predates that budget can still
        # overflow — that raises OSError 36, which the except below turns into
        # "ship the clip uncaptioned" rather than a broken filename.
        # The .ass path is interpolated INTO an ffmpeg filter string
        # (-vf ass='...'), where a literal apostrophe closes the quote and
        # breaks the filter. Titles carry apostrophes constantly in English
        # ("Earth's", "Don't"), so this name must stay free of the clip stem —
        # which is exactly why /api/subtitle has always used a neutral
        # "subs_<i>_<ts>.ass". Deriving it from the stem silently cost captions
        # on every apostrophe title until 29-jul-2026.
        #
        # The OUTPUT name still carries the stem, and must: the modal's
        # walk-back and _canonical_clip_file reconstruct the clean original
        # from it. That one is only ever passed as an argv element, never
        # inside a filter string, so quoting never applies to it.
        # Unique per clip, not just per second: clips render in parallel
        # (CLIP_WORKERS), so a bare timestamp would collide and let one clip
        # burn another's captions.
        ass_path = os.path.join(
            output_dir, f"autosubs_{generation_id}_{uuid.uuid4().hex[:8]}.ass")
        out_path = os.path.join(output_dir, f"subtitled_{generation_id}_{stem}")

        if split_ranges is None:
            import layout_ranges as _layouts
            split_ranges = _layouts.split_ranges(_layouts.read(clip_path))
        if not _subs.generate_ass(
                transcript, clip_start, clip_end, ass_path,
                split_ranges=split_ranges,
                max_chars=style["max_chars"], max_duration=style["max_duration"],
                alignment=style["alignment"], fontsize=style["font_size"],
                font_name=style["font_name"], font_color=style["font_color"],
                border_color=style["border_color"], border_width=style["border_width"],
                highlight_color=style["highlight_color"], effect=style["effect"],
                base_opacity=style["base_opacity"], uppercase=style["uppercase"]):
            print("   ℹ️ No words in range — clip ships without captions.")
            return None

        _subs.burn_subtitles(
            clip_path, ass_path, out_path,
            alignment=style["alignment"], fontsize=style["font_size"],
            font_name=style["font_name"], font_color=style["font_color"],
            border_color=style["border_color"], border_width=style["border_width"])
        print(f"   💬 Captions burned: {os.path.basename(out_path)}")
        return out_path
    except Exception as e:
        print(f"   ⚠️ Auto-captions failed ({type(e).__name__}: {e}) — "
              f"delivering the clip without them.")
        return None


def auto_hook_clip(clip_path, clip):
    """Burn the clip's Gemini hook text as a DERIVED file (AUTO_HOOK=1).

    Writes ``hooked_<ts>_<clip filename>`` next to the canonical clip, exactly
    like captions write ``subtitled_<ts>_...``: the canonical stays clean, so
    the hook can later be replaced or removed by walking the prefix back
    (app.py `_strip_burned_hook`). Captions are then burned ON TOP of the
    hooked file, keeping the "captions are always the last layer" invariant.

    Returns (hooked_path, hook_config), or None when skipped or failed — a
    hook problem must never cost the user the clip itself (same fail-open
    contract as auto_caption_clip)."""
    from clip_metadata import is_placeholder_or_empty, clean_or_generate_clip_metadata
    text = (clip.get('viral_hook_text') or '').strip()
    if is_placeholder_or_empty(text):
        clean_or_generate_clip_metadata(clip)
        text = (clip.get('viral_hook_text') or '').strip()
    if is_placeholder_or_empty(text):
        return None
    style = os.environ.get("AUTO_HOOK_STYLE", "classic")
    try:
        seconds = float(os.environ.get("AUTO_HOOK_SECONDS", "5"))
    except ValueError:
        seconds = 5.0
    try:
        from hooks import add_hook_to_video, HOOK_STYLES
        if style not in HOOK_STYLES:
            style = "classic"
        output_dir = os.path.dirname(clip_path)
        out_path = os.path.join(
            output_dir, f"hooked_{int(time.time())}_{os.path.basename(clip_path)}")
        add_hook_to_video(clip_path, text, out_path, position="top",
                          duration=seconds, style=style)
        print(f"   🪝 Hook burned ({style}, {seconds:g}s): {text}")
        return out_path, {"text": text, "style": style, "position": "top",
                          "duration_seconds": seconds}
    except Exception as e:
        print(f"   ⚠️ Auto-hook failed ({type(e).__name__}: {e}) — "
              f"delivering the clip without it.")
        return None


def render_clip(input_video, final_output_video, output_format="auto",
                force_strategy=None, crop_overrides=None):
    """Route a cut clip through the right renderer for the chosen output format.
    vertical/auto -> 9:16 reframe, square -> 1:1 reframe, horizontal -> keep.
    ``force_strategy`` (e.g. 'WIDE'/'TRACK') pins every scene's layout — the
    clip editor's whole-clip framing override. ``crop_overrides`` positions
    individual scenes by hand (the per-scene reframing editor) and wins over
    ``force_strategy`` for the scenes it names."""
    if output_format == "horizontal":
        return finalize_clip_passthrough(input_video, final_output_video)
    aspect = 1.0 if output_format == "square" else ASPECT_RATIO
    return process_video_to_vertical(input_video, final_output_video, aspect_ratio=aspect,
                                     force_strategy=force_strategy,
                                     crop_overrides=crop_overrides)


# Watermark geometry, as fractions of the clip width/height.
#
# Vertical placement is the whole point: the top and bottom strips of a 9:16
# clip are either black bars or blurred filler (GENERAL layout), so a mark up
# there is cropped away without touching a single pixel of real footage. At 40%
# of the height it sits inside the content band — a 16:9 source letterboxed
# into 9:16 spans roughly 34%-66% — so removing the mark means cutting into the
# picture. Left-aligned, like OpusClip's.
WATERMARK_WIDTH_RATIO = 0.30
WATERMARK_MARGIN_RATIO = 0.05
WATERMARK_Y_RATIO = 0.40
WATERMARK_OPACITY = 0.85


def apply_watermark(video_path):
    """Burn the OpenShorts watermark into a finished clip (free plan).

    One re-encode pass on the final file so every output format (TRACK,
    GENERAL, horizontal passthrough) gets the mark, and later subtitle/hook
    re-encodes keep it — they re-encode the already-marked pixels.
    """
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "assets", "watermark.png")
    if not os.path.exists(logo_path):
        print(f"   ⚠️ Watermark asset missing ({logo_path}); clip kept unmarked.")
        return False

    # Scale the lockup from the clip's real width: overlay can't read the other
    # input's size, and computing it here avoids the deprecated scale2ref.
    try:
        probe = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", video_path],
            stderr=subprocess.STDOUT, timeout=60,
        ).decode().strip().split("x")
        vw, vh = int(probe[0]), int(probe[1])
    except Exception as e:
        print(f"   ⚠️ Could not probe clip for watermark ({e}); clip kept unmarked.")
        return False

    wm_w = max(80, int(vw * WATERMARK_WIDTH_RATIO))
    x = int(vw * WATERMARK_MARGIN_RATIO)
    y = int(vh * WATERMARK_Y_RATIO)
    filt = (
        f"[1:v]scale={wm_w}:-1,format=rgba,"
        f"colorchannelmixer=aa={WATERMARK_OPACITY}[wm];"
        f"[0:v][wm]overlay=x={x}:y={y}"
    )
    tmp_path = video_path + ".wm.mp4"
    cmd = ["ffmpeg", "-y", "-i", video_path, "-i", logo_path,
           "-filter_complex", filt,
           *video_encode_args(QUALITY), "-c:a", "copy", *METADATA_SCRUB,
           "-movflags", "+faststart", tmp_path]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            timeout=1800)
    if result.returncode == 0 and os.path.exists(tmp_path):
        os.replace(tmp_path, video_path)
        return True
    err = (result.stderr or b"").decode(errors="ignore")[-300:]
    print(f"   ⚠️ Watermark pass failed (clip kept unmarked): {err}")
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    return False


