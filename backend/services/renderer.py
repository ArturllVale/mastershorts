import httpx
import time
import asyncio
from core.config import RENDER_SERVICE_URL

async def call_render_service(job_id: str, clip_index: int, video_url: str, duration_frames: int, fps: float, width: int, height: int, subtitles: dict, hook: dict = None):
    url = f"{RENDER_SERVICE_URL.rstrip('/')}/render"
    payload = {
        "jobId": job_id,
        "clipIndex": clip_index,
        "props": {
            "videoUrl": video_url,
            "durationInFrames": duration_frames,
            "fps": fps,
            "width": width,
            "height": height,
            "subtitles": subtitles,
            "hook": hook
        }
    }
    
    timeout = httpx.Timeout(10.0, connect=5.0)
    global_timeout_seconds = 600
    poll_interval = 2.0
    start_time = time.monotonic()
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            res = await client.post(url, json=payload)
            res.raise_for_status()
            try:
                data = res.json()
            except Exception:
                raise Exception("Render service returned invalid JSON on start")
        except httpx.ConnectError:
            raise Exception(f"Render service is unavailable (connection error). Check if it is running at {RENDER_SERVICE_URL}")
        except httpx.HTTPStatusError as e:
            raise Exception(f"Render service HTTP error on start: {e.response.status_code}")
        except Exception as e:
            if "invalid JSON" in str(e): raise e
            raise Exception(f"Render request failed: {e}")
            
        render_id = data.get("renderId")
        if not render_id:
            raise Exception("Render service did not return a renderId")

        status_url = f"{RENDER_SERVICE_URL.rstrip('/')}/render/{render_id}"
        
        while True:
            if time.monotonic() - start_time > global_timeout_seconds:
                raise Exception("Global render timeout exceeded")
                
            try:
                status_res = await client.get(status_url)
                status_res.raise_for_status()
                try:
                    sdata = status_res.json()
                except Exception:
                    raise Exception("Render service returned invalid JSON during polling")
            except httpx.ConnectError:
                raise Exception("Render service disconnected during polling")
            except httpx.HTTPStatusError as e:
                raise Exception(f"Render service status HTTP error: {e.response.status_code}")
            except Exception as e:
                if "invalid JSON" in str(e): raise e
                raise Exception(f"Render status check failed: {e}")
                
            status = sdata.get("status")
            if status == "done":
                import os
                from core.config import OUTPUT_DIR
                rel_path = sdata.get("outputUrl")
                if rel_path and not os.path.isabs(rel_path):
                    return os.path.normpath(os.path.join(OUTPUT_DIR, rel_path))
                return rel_path
            elif status == "error":
                raise Exception(f"Render failed: {sdata.get('error', 'Unknown error inside renderer')}")
                
            await asyncio.sleep(poll_interval)
