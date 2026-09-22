import os
import shutil
import subprocess
import time
from ffmpeg_utils import video_encode_args, QUALITY_FAST, QUALITY, METADATA_SCRUB

def build_final_render_command(
    original_video: str,
    clip_temp_path: str,
    final_output_video: str,
    start: float,
    duration: float,
    watermark_path: str = None,
    hook_video_path: str = None,
    ass_subtitles_path: str = None,
    aspect_ratio: float = 9/16,
    content_ranges = None,
    force_strategy = None,
    crop_overrides = None
):
    """
    Constroi e executa o comando FFmpeg único para renderizar o clip.
    Usa o clip_temp_path (corte exato) APENAS para análise (reframe_v2),
    mas usa o original_video com -ss para o encode final, garantindo 1 encode do original.
    """
    import reframe_v2
    import layout_ranges
    from ffmpeg_utils import nvenc_available
    
    # Montamos o filter_complex dinamicamente
    filter_chains = []
    
    input_args = [
        "ffmpeg", "-y", "-loglevel", "error",
    ]
    
    if nvenc_available():
        input_args.extend(["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"])
        
    input_args.extend([
        "-ss", str(start), "-t", str(duration),
        "-i", original_video
    ])
    
    input_index = 1
    
    # 1. Reframe_v2 build graph (instead of rendering)
    try:
        reframe_graph, out_node, workdir, ranges, fps = reframe_v2.build_reframe_filtergraph(
            clip_temp_path, aspect_ratio, content_ranges, force_strategy, crop_overrides
        )
        filter_chains.append(reframe_graph)
        current_video_node = out_node
    except Exception as e:
        print(f"   ⚠️ Reframe v2 failed to build graph ({e}). Falling back to simple scale.")
        workdir = None
        ranges = []
        fps = 30.0
        # Simple fallback graph if reframe_v2 fails
        filter_chains.append(f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[v_crop]")
        current_video_node = "[v_crop]"

    # 2. Watermark
    if watermark_path and os.path.exists(watermark_path):
        input_args.extend(["-i", watermark_path])
        filter_chains.append(f"[{input_index}:v]scale=162:-1[wm];{current_video_node}[wm]overlay=W-w-10:10[v_wm]")
        current_video_node = "[v_wm]"
        input_index += 1
        
    # 3. Hook (video pré-renderizado transparente ou overlay)
    if hook_video_path and os.path.exists(hook_video_path):
        input_args.extend(["-i", hook_video_path])
        filter_chains.append(f"{current_video_node}[{input_index}:v]overlay=0:0:eof_action=pass[v_hook]")
        current_video_node = "[v_hook]"
        input_index += 1
        
    # 4. Legendas (ASS)
    if ass_subtitles_path and os.path.exists(ass_subtitles_path):
        safe_ass = ass_subtitles_path.replace("\\", "/").replace(":", "\\:")
        filter_chains.append(f"{current_video_node}ass='{safe_ass}'[v_subs]")
        current_video_node = "[v_subs]"
        
    if filter_chains:
        filter_complex_str = ";".join(filter_chains)
        input_args.extend(["-filter_complex", filter_complex_str])
        
    input_args.extend(["-map", current_video_node, "-map", "0:a?"])
    
    input_args.extend(video_encode_args(QUALITY_FAST)) # NVENC se disponível
    input_args.extend([
        "-c:a", "aac",
        *METADATA_SCRUB,
        "-movflags", "+faststart",
        final_output_video
    ])
    
    t0 = time.time()
    try:
        subprocess.run(input_args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=1800)
        print(f"   ✓ Unified render total: {time.time() - t0:.1f}s")
        if ranges and fps:
            layout_ranges.write(final_output_video, [(s / fps, e / fps, strategy) for s, e, strategy in ranges])
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ❌ Unified render failed. Stderr: {e.stderr.decode(errors='ignore')}")
        return False
    finally:
        if workdir:
            shutil.rmtree(workdir, ignore_errors=True)

