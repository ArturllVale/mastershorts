import os
import sys
import tempfile
import subprocess
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from services.clip_render import build_final_render_command
import ffmpeg_utils

def create_dummy_video(path, duration=5):
    # Create a 5s dummy 16:9 video
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=1920x1080:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration}",
        "-c:v", "libx264", "-c:a", "aac", path
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def test_render():
    input_video = "test_input.mp4"
    if not os.path.exists(input_video):
        create_dummy_video(input_video, 10)
        
    clip_temp_path = "test_clip_proxy.mp4"
    # Create exact cut proxy
    subprocess.run([
        "ffmpeg", "-y", "-ss", "2", "-t", "5", "-i", input_video,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
        "-c:a", "aac", clip_temp_path
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    out_video = "test_output.mp4"
    print("Testing Unified Render Pipeline...")
    t0 = time.time()
    success = build_final_render_command(
        original_video=input_video,
        clip_temp_path=clip_temp_path,
        final_output_video=out_video,
        start=2.0,
        duration=5.0,
        watermark_path=None,
        hook_video_path=None,
        ass_subtitles_path=None,
        aspect_ratio=9.0/16.0
    )
    t1 = time.time()
    print(f"Success: {success}, Time: {t1-t0:.2f}s")
    if success:
        print(f"Video created: {out_video}")
        os.remove(out_video)
    os.remove(input_video)
    os.remove(clip_temp_path)

if __name__ == "__main__":
    test_render()
