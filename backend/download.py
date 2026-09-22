import os
import re
import sys
import time
import unicodedata
import yt_dlp
from urllib.parse import urlparse
import json
import glob
from core.path_utils import to_long_path, safe_exists, safe_getsize

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

MAX_TITLE_BYTES = 50

def truncate_bytes(s, max_bytes):
    b = s.encode('utf-8')
    if len(b) <= max_bytes:
        return s
    return b[:max_bytes].decode('utf-8', errors='ignore')

def sanitize_filename(filename):
    filename = unicodedata.normalize('NFC', filename)
    filename = re.sub(r'[\U00010000-\U0010ffff]', '', filename)
    filename = re.sub(r'[<>:"/\\|?*#]', '', filename)
    filename = filename.replace(' ', '_')
    return truncate_bytes(filename, MAX_TITLE_BYTES)

def is_youtube_url(url):
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return True
    return host.endswith(("youtube.com", "youtu.be", "youtube-nocookie.com", "googlevideo.com"))

def plan_download_attempts(direct_first, statics, paid, have_hd, youtube=True):
    """Ordered (label, capped, proxy) download plan — pure, unit-tested.

    ``youtube=False`` (a direct file URL): the server's own IP first, then one
    static proxy as the only fallback; the paid per-GB proxy is never used.

    Cheapest bandwidth first: the server's own IP, then the flat-rate static
    ISP proxies (uncapped 1080p, free bytes), then the per-GB paid proxy
    (720p cost cap), and last the conservative fallback strategy through the
    paid proxy (or a static/direct when no paid proxy is configured).
    ``capped`` marks attempts whose bytes are billed per GB."""
    if not youtube:
        plan = [('direct', False, None)]
        if statics:
            plan.append(('static-fallback', False, statics[0]))
        return plan
    plan = []
    if direct_first:
        plan.append(('HD-direct', False, None))
    if have_hd:
        for i, s in enumerate(statics):
            plan.append((f'HD-static{i + 1}', False, s))
    if statics and paid:
        # The conservative clients (tv_embed/android) through a FREE static,
        # before any per-GB attempt: YouTube serves a fake "Video unavailable"
        # to the web/HD client from datacenter-ISP ranges on some videos while
        # the fallback clients pass on the very same IPs (verified 4-sep-2026,
        # all three statics, three countries). Costs nothing and the paid path
        # was capped to 720p anyway, so there is no quality trade.
        plan.append(('fallback-static', False, statics[0]))
    if have_hd:
        plan.append(('HD', bool(paid), paid))
    plan.append(('fallback', bool(paid),
                 paid if paid else (statics[0] if statics else None)))
    return plan

def download_youtube_video(url, output_dir="."):
    from security_utils import assert_public_url
    assert_public_url(url)
    import file_hosts
    url = file_hosts.resolve(url)
    from yt_clients import NotASingleVideo, youtube_non_video_reason
    reason = youtube_non_video_reason(url)
    if reason:
        raise NotASingleVideo(f"This link is {reason}.")

    # Fast reuse: if output_dir already has the source video from an earlier run, skip download
    try:
        # 1. Check metadata.json
        meta_files = glob.glob(os.path.join(output_dir, "*_metadata.json"))
        if meta_files:
            try:
                with open(to_long_path(meta_files[0]), 'r', encoding='utf-8') as mf:
                    mdata = json.load(mf)
                src_name = mdata.get('source_video')
                if src_name:
                    src_path = os.path.join(output_dir, os.path.basename(src_name))
                    if safe_exists(src_path) and safe_getsize(src_path) > 1024 * 512:
                        base_name = os.path.splitext(os.path.basename(src_path))[0]
                        print(f"♻️ Vídeo fonte já baixado encontrado (metadata): {src_path} — pulando download.", flush=True)
                        return src_path, base_name
            except Exception:
                pass

        # 2. Check output_dir directly for any existing source video
        long_out = to_long_path(output_dir)
        if os.path.isdir(long_out):
            for f in os.listdir(long_out):
                if f.endswith(('.mp4', '.mkv', '.webm')) and not any(p in f for p in ('_clip_', 'subtitled_', 'hooked_', 'temp_', 'recut_')):
                    cand_path = os.path.join(output_dir, f)
                    if safe_getsize(cand_path) > 1024 * 512:
                        try:
                            import cv2
                            probe = cv2.VideoCapture(to_long_path(cand_path))
                            is_valid = probe.isOpened() and int(probe.get(cv2.CAP_PROP_FRAME_COUNT)) > 0
                            probe.release()
                            if is_valid:
                                base_name = os.path.splitext(f)[0]
                                print(f"♻️ Vídeo fonte já baixado encontrado: {cand_path} — pulando download.", flush=True)
                                return cand_path, base_name
                        except Exception:
                            pass
    except Exception:
        pass

    print(f"🔍 Debug: yt-dlp version: {yt_dlp.version.__version__}")
    print("📥 Iniciando download do vídeo...", flush=True)
    step_start_time = time.time()

    cookies_path = '/app/cookies.txt'
    cookies_env = os.environ.get("YOUTUBE_COOKIES")
    if cookies_env:
        print("🍪 Found YOUTUBE_COOKIES env var, creating cookies file inside container...")
        try:
            with open(cookies_path, 'w') as f:
                f.write(cookies_env)
            if os.path.exists(cookies_path):
                 print(f"   Debug: Cookies file created. Size: {os.path.getsize(cookies_path)} bytes")
        except Exception as e:
            print(f"⚠️ Failed to write cookies file: {e}")
            cookies_path = None
    else:
        cookies_path = None
        print("⚠️ YOUTUBE_COOKIES env var not found.")

    _proxy = os.environ.get("PROXY_URL", "").strip() or None
    if _proxy:
        print("🌐 Using proxy for download.")

    _statics = [p.strip() for p in
                os.environ.get("STATIC_PROXY_URLS", "").split(",") if p.strip()]
    if _statics:
        import random as _random
        k = _random.randrange(len(_statics))
        _statics = _statics[k:] + _statics[:k]
        print(f"🌐 {len(_statics)} static ISP proxies configured.")

    _bgutil_http = os.environ.get("BGUTIL_BASE_URL", "").strip()
    _bgutil_script = os.environ.get("BGUTIL_SCRIPT_PATH", "").strip()
    from yt_clients import hd_extractor_args, fallback_extractor_args
    hd_args = hd_extractor_args(_bgutil_http, _bgutil_script)
    fallback_args = fallback_extractor_args(_bgutil_http, _bgutil_script)

    def _hd_fmt_for(capped):
        if capped:
            return ('bestvideo[vcodec^=avc1][height<=720][ext=mp4]+bestaudio[ext=m4a]/'
                    'bestvideo[vcodec^=avc1][height<=720]+bestaudio/'
                    'best[height<=720][ext=mp4]/best[height<=720]/best')
        return ('bestvideo[vcodec^=avc1][height<=1080][ext=mp4]+bestaudio[ext=m4a]/'
                'bestvideo[vcodec^=avc1][height<=1080]+bestaudio/'
                'best[height<=1080][ext=mp4]/best[ext=mp4]/best')

    def _base_opts(extractor_args, proxy, cookies=True):
        opts = {
            'quiet': False, 'verbose': True, 'no_warnings': False,
            'cookiefile': cookies_path if (cookies and cookies_path) else None,
            'proxy': proxy, 'socket_timeout': 30, 'retries': 10, 'fragment_retries': 10,
            'nocheckcertificate': True, 'cachedir': False,
            'noplaylist': True,
            'nopart': True,
            'continuedl': False,
            'file_access_retries': 15,
            'retry_sleep_functions': {'file_access': lambda n: 0.5 * (2 ** min(n, 3))},
            'windowsfilenames': True,
            'extractor_args': extractor_args,
        }
        if not is_youtube_url(url):
            opts['http_headers'] = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ),
            }
        return opts

    _dl_bytes = {"total": 0, "partial": 0}

    def _progress_hook(d):
        if d.get('status') == 'downloading':
            _dl_bytes["partial"] = int(d.get('downloaded_bytes') or 0)
            total = int(d.get('total_bytes') or d.get('total_bytes_estimate') or 0)
            downloaded = _dl_bytes["partial"]
            if total > 0:
                pct = int((downloaded / total) * 100)
                last = _dl_bytes.get("last_pct", -1)
                if pct != last and (pct % 5 == 0 or pct in (1, 2, 99, 100)):
                    _dl_bytes["last_pct"] = pct
                    print(f"📥 Baixando vídeo: {pct}%", flush=True)
        elif d.get('status') == 'finished':
            _dl_bytes["partial"] = 0
            _dl_bytes["total"] += int(d.get('total_bytes')
                                      or d.get('total_bytes_estimate')
                                      or d.get('downloaded_bytes') or 0)
            print("✅ Download concluído com sucesso!", flush=True)

    def _attempt(extractor_args, fmt, proxy, cookies=True):
        _dl_bytes["total"] = 0
        _dl_bytes["partial"] = 0
        with yt_dlp.YoutubeDL(_base_opts(extractor_args, proxy, cookies)) as ydl:
            info = ydl.extract_info(url, download=False)
        sanitized = sanitize_filename(info.get('title', 'youtube_video'))

        # Reuse existing downloaded video if present and valid (e.g. from an interrupted or retried run)
        for ext in ('mp4', 'mkv', 'webm'):
            existing_candidate = os.path.join(output_dir, f'{sanitized}.{ext}')
            if safe_exists(existing_candidate) and safe_getsize(existing_candidate) > 1024 * 512:
                try:
                    import cv2
                    probe = cv2.VideoCapture(to_long_path(existing_candidate))
                    is_valid = probe.isOpened() and int(probe.get(cv2.CAP_PROP_FRAME_COUNT)) > 0
                    probe.release()
                    if is_valid:
                        print(f"♻️ Vídeo já baixado encontrado: {existing_candidate} — pulando download.", flush=True)
                        return sanitized
                except Exception:
                    pass

        try:
            long_out = to_long_path(output_dir)
            if os.path.isdir(long_out):
                for f in os.listdir(long_out):
                    if f.startswith(sanitized) and not f.endswith(('.json', '.ass')) and not any(k in f for k in ('_clip_', 'subtitled_', 'hooked_', 'temp_', 'recut_')):
                        target = os.path.join(output_dir, f)
                        if os.path.isfile(to_long_path(target)):
                            try:
                                os.remove(to_long_path(target))
                            except Exception as rm_err:
                                print(f"⚠️ Notice: Could not remove existing file {target}: {rm_err}")
        except Exception:
            pass
        dl_opts = {
            **_base_opts(extractor_args, proxy, cookies),
            'format': fmt,
            'outtmpl': os.path.join(output_dir, f'{sanitized}.%(ext)s'),
            'merge_output_format': 'mp4', 'overwrites': True,
            'progress_hooks': [_progress_hook],
        }
        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            ydl.download([url])
        return sanitized

    _direct_first = (os.environ.get("DIRECT_FIRST", "").strip() == "1"
                     and (_proxy or _statics) and hd_args and cookies_path)

    attempts = [
        (label,
         fallback_args if label.startswith('fallback') else hd_args,
         _hd_fmt_for(capped),
         proxy,
         not (label.startswith('fallback') and hd_args))
        for label, capped, proxy in plan_download_attempts(
            _direct_first, _statics, _proxy, bool(hd_args), youtube=is_youtube_url(url))
    ]
    if not is_youtube_url(url):
        print("🌐 Direct file URL: downloading from the server's own IP (no proxy).")

    sanitized_title = None
    last_err = None
    used_proxy = False
    attempt_log = []
    for label, ea, fmt, proxy, cookies in attempts:
        for retry in range(2):
            try:
                print(f"📥 Download attempt: {label}" + (f" (retry {retry})" if retry else ""))
                sanitized_title = _attempt(ea, fmt, proxy, cookies)
                used_proxy = proxy is not None and proxy == _proxy
                attempt_log.append({"label": label, "ok": True,
                                    "bytes": _dl_bytes["total"] + _dl_bytes["partial"],
                                    "paid": used_proxy})
                print(f"✅ Download succeeded ({label}).")
                break
            except Exception as e:
                last_err = e
                attempt_log.append({"label": label, "ok": False,
                                    "bytes": _dl_bytes["total"] + _dl_bytes["partial"],
                                    "paid": proxy is not None and proxy == _proxy,
                                    "error": str(e)[:300]})
                print(f"⚠️  Download attempt '{label}' failed: {str(e)[:200]}")
                retryable = any(tok in str(e) for tok in (
                    '403', 'Forbidden', 'WinError 32', 'used by another process',
                    'WinError 183', 'FileExistsError', 'already exists',
                    'PermissionError', 'Unable to rename', '416', 'Requested range not satisfiable'
                ))
                if any(tok in str(e) for tok in ('416', 'Requested range not satisfiable', 'WinError 183', 'FileExistsError', 'already exists')):
                    try:
                        for f in os.listdir(output_dir):
                            if not f.endswith(('.json', '.ass')):
                                target = os.path.join(output_dir, f)
                                if os.path.isfile(target):
                                    try:
                                        os.remove(target)
                                    except Exception:
                                        pass
                    except Exception:
                        pass
                if not retryable or retry == 1:
                    break
                time.sleep(3)
        if sanitized_title is not None:
            break

    if sanitized_title is None and is_youtube_url(url):
        try:
            print("📥 Download attempt: fallback-android (direct)", flush=True)
            ea_android = {'youtube': {'player_client': ['android', 'ios']}}
            sanitized_title = _attempt(ea_android, _hd_fmt_for(False), None, cookies=False)
            if sanitized_title is not None:
                attempt_log.append({"label": "fallback-android", "ok": True,
                                    "bytes": _dl_bytes["total"] + _dl_bytes["partial"],
                                    "paid": False})
                print("✅ Download succeeded (fallback-android).", flush=True)
        except Exception as e_android:
            last_err = e_android
            attempt_log.append({"label": "fallback-android", "ok": False,
                                "bytes": _dl_bytes["total"] + _dl_bytes["partial"],
                                "paid": False, "error": str(e_android)[:300]})
            print(f"⚠️  Download attempt 'fallback-android' failed: {str(e_android)[:200]}", flush=True)

    if sanitized_title is None:
        if last_err and "Sign in to confirm" in str(last_err):
             raise Exception("YouTube is demanding an account login (age restriction or bot check).")
        from yt_clients import NoVideoFormat
        if last_err and isinstance(last_err, NoVideoFormat):
             raise Exception(f"No usable video format found for {url}. It may be a live stream, audio-only, or DRM-protected.")
        if last_err and "HTTP Error 403: Forbidden" in str(last_err):
             raise Exception(f"Download forbidden (HTTP 403). YouTube might be blocking the server's IP. {url}")
        raise Exception(f"Download final falhou após todas as tentativas: {last_err}")

    print(f"PROXY_ROUTE={__import__('json').dumps(attempt_log)}", flush=True)

    candidates = []
    for ext in ['mp4', 'mkv', 'webm']:
        path = os.path.join(output_dir, f'{sanitized_title}.{ext}')
        if safe_exists(path):
            candidates.append(path)

    if not candidates:
        try:
            long_out = to_long_path(output_dir)
            if os.path.isdir(long_out):
                for f in os.listdir(long_out):
                    if f.endswith(('.mp4', '.mkv', '.webm')) and not any(k in f for k in ('_clip_', 'subtitled_', 'hooked_', 'recut_', 'temp_')):
                        cand = os.path.join(output_dir, f)
                        if safe_getsize(cand) > 1024 * 512:
                            candidates.append(cand)
        except Exception:
            pass

    if not candidates:
        raise Exception(f"Expected to find downloaded file for '{sanitized_title}' in {output_dir}, but found none.")

    video_path = max(candidates, key=safe_getsize)
    print(f"✅ Download finalizado em {time.time() - step_start_time:.2f}s: {video_path}", flush=True)

    return video_path, sanitized_title
