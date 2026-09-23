import os
import json
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from google import genai
from google.genai import types as genai_types

import gemini_worker
import llm_backend
from clip_selection import build_transcript_windows, clip_count_targets, clip_duration_bounds, snap_clip_to_words, trim_to_best

def transcribe_video(video_path):
    print("🎙️ Iniciando transcrição do áudio...", flush=True)
    from transcribe_backends import transcribe_media
    from services.cache import get_or_compute
    import asyncio
    
    source_hash = os.environ.get("SOURCE_HASH")
    
    def _compute():
        return transcribe_media(video_path)

    if source_hash:
        transcript = asyncio.run(get_or_compute(source_hash, "transcript", _compute))
    else:
        transcript = _compute()

    print("🎙️ Transcrição iniciada com sucesso!", flush=True)

    print(f"   Detected language '{transcript['language']}', "
          f"{len(transcript['segments'])} segments")
    for segment in transcript['segments']:
        # Print progress to keep user informed (and prevent timeouts feeling)
        print(f"   [{segment['start']:.2f}s -> {segment['end']:.2f}s] {segment['text']}")

    return transcript

def _run_gemini_stage(client, model_name, prompt, schema):
    """One schema-enforced model call with transient-error backoff.
    Returns (parsed_dict, cost_analysis).

    With an OpenAI-compatible server configured (``llm_backend.active()``)
    the call goes there instead of Gemini and ``client`` is unused; the
    retry policy is handled natively by llm_backend.py.
    """
    use_local = llm_backend.active()
    config = None if use_local else genai_types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
    )
    
    if use_local:
        max_attempts = int(os.environ.get("LLM_MAX_RETRIES", "2")) + 1
    else:
        max_attempts = int(os.environ.get("GEMINI_MAX_RETRIES", "5")) + 1
    
    for attempt in range(1, max_attempts + 1):
        try:
            if use_local:
                return llm_backend.generate_json(prompt, schema, model=model_name)

            response = client.models.generate_content(model=model_name, contents=prompt, config=config)
            # Policy blocks are deterministic — retrying only burns quota and
            # time, and the user deserves the real reason instead of a generic
            # "empty response" (prod 23-jul: PROHIBITED_CONTENT on every try).
            gemini_worker.raise_if_blocked(response)
            # Parsing lives inside the retry loop on purpose: Gemini sometimes
            # returns 200 with an empty body, which raises here rather than at
            # the call. Retrying that recovered every occurrence seen in prod
            # (22-jul-2026) — the same payload succeeds on the next attempt.
            parsed_obj = getattr(response, "parsed", None)
            if parsed_obj is not None:
                parsed = parsed_obj.model_dump() if hasattr(parsed_obj, "model_dump") else parsed_obj
            else:
                from core.json_utils import parse_json_response_text
                parsed = parse_json_response_text(
                    gemini_worker._get_response_text(response))
            return parsed, gemini_worker._calculate_cost_analysis(response, model_name)
        except gemini_worker.GeminiBlockedError:
            raise  # deterministic policy block — never retry
        except Exception as e:
            msg = str(e)
            transient = any(tok in msg.lower() for tok in (
                '503', 'unavailable', '429', 'resource_exhausted',
                '500', 'internal', 'overloaded', 'deadline',
                'empty response body', 'did not contain a json object',
                'failed to parse gemini json response',
                'validation error', 'connect', 'timeout', 'reset', 'refused'))
            if attempt == max_attempts or not transient:
                print(f"[LLM] stage=score model={model_name} attempt={attempt} error={type(e).__name__} details={msg[:100]}")
                raise
            
            # Use smaller backoff for Gemini to avoid blocking for dozens of seconds
            wait = 2 * attempt 
            print(f"[LLM] stage=score model={model_name} attempt={attempt} error=transient_error retrying_in={wait}s details={msg[:100]}")
            time.sleep(wait)



def _run_stage_split(client, model_name, items, build_prompt, schema, key, costs, label):
    """Run a Gemini stage over ``items``; on a policy block, bisect.

    Google's prompt filter (PROHIBITED_CONTENT) fires on some COMBINATIONS of
    transcript windows that pass individually (27-aug-2026: windows 5+6 of a
    software walkthrough blocked 3/3, each alone fine, all three models).
    A block is deterministic for a given prompt, so instead of failing the
    job the batch is split in halves until the offending combination is
    isolated; a single item that still blocks is dropped with a log line.
    Returns the merged list found under ``key`` in each response."""
    if not items:
        return []
    prompt = build_prompt(items)
    try:
        parsed, cost = _run_gemini_stage(client, model_name, prompt, schema)
        if cost:
            costs.append(cost)
        return list(parsed.get(key) or [])
    except gemini_worker.GeminiBlockedError as e:
        if len(items) == 1:
            print(f"   🚫 {label}: Gemini blocked window {items[0].get('id')} on its own; skipping it ({e})")
            return []
        mid = len(items) // 2
        print(f"   🚫 {label}: Gemini blocked a batch of {len(items)}; retrying as {mid} + {len(items) - mid}")
        return (_run_stage_split(client, model_name, items[:mid], build_prompt, schema, key, costs, label)
                + _run_stage_split(client, model_name, items[mid:], build_prompt, schema, key, costs, label))


def score_batch_size():
    """Transcript windows per scoring call: ``LLM_SCORE_BATCH`` if set, else
    8 for Gemini (1M context) and 3 for an OpenAI-compatible server."""
    raw = os.environ.get("LLM_SCORE_BATCH", "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return 3 if llm_backend.active() else 8


def detail_batch_size():
    """Candidate windows per detail call: ``LLM_DETAIL_BATCH`` if set, else
    4 for Gemini and 2 for an OpenAI-compatible server."""
    raw = os.environ.get("LLM_DETAIL_BATCH", "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    return 2 if llm_backend.active() else 4


def get_viral_clips(transcript_result, video_duration, video_title=None):
    """Two-pass clip selection with adaptive batching."""
    language = str(transcript_result.get('language') or 'unknown')
    if llm_backend.active():
        client = None
        model_name = llm_backend.model_name()
        if llm_backend.provider() == "combo":
            print("🤖  Analyzing with Combo (Gemini + OpenRouter + Mistral)...")
        else:
            print(f"🤖  Analyzing with local LLM at {llm_backend.base_url()}...")
    else:
        print("🤖  Analyzing with Gemini...")
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("❌ Error: GEMINI_API_KEY not found")
            return None
        client = genai.Client(api_key=api_key)
        model_name = os.environ.get("GEMINI_MODEL") or 'gemini-3.1-flash-lite'

    words = []
    for segment in transcript_result['segments']:
        for word in segment.get('words', []):
            words.append({'w': word['word'], 's': word['start'], 'e': word['end']})

    try:
        min_secs, max_secs = clip_duration_bounds()
        costs = []
        shorts = []
        
        # Token estimation
        total_words = sum(len(w['w'].split()) for w in words)
        estimated_tokens = total_words * 1.5
        
        use_single_pass = False
        if video_duration <= 600:
            token_limit = 6000 if llm_backend.active() else 50000
            if estimated_tokens < token_limit:
                use_single_pass = True

        def _payload(ws):
            return [{"id": w["id"], "start": w["start"], "end": w["end"], "text": w["text"]} for w in ws]

        min_clips, max_clips = clip_count_targets(1 if use_single_pass else int(video_duration // 90))

        if use_single_pass:
            print("⚡ Usando Single-Pass para vídeo curto/leve...")
            full_text = " ".join(w['w'] for w in words)
            win = [{"id": "full_video", "start": 0, "end": video_duration, "text": full_text}]
            
            def _detail_prompt(ws):
                return gemini_worker.DETAIL_PROMPT_TEMPLATE.format(
                    video_duration=video_duration, language=language,
                    min_clips=min_clips, max_clips=max_clips,
                    min_secs=min_secs, max_secs=max_secs,
                    windows_json=json.dumps(_payload(ws), ensure_ascii=False))

            shorts = _run_stage_split(client, model_name, win, _detail_prompt,
                                     gemini_worker.DetailResponse, "shorts", costs, "detail")
        else:
            print("📊 Usando Two-Pass para vídeo longo...")
            windows = build_transcript_windows(
                transcript_result, video_duration,
                window_seconds=max(90, int(max_secs * 1.5)))
                
            scored = []
            SCORE_BATCH = score_batch_size()
            if 600 < video_duration <= 1800 and not llm_backend.active():
                SCORE_BATCH = 15 
            
            def _score_prompt(ws):
                return gemini_worker.SCORE_PROMPT_TEMPLATE.format(
                    video_duration=video_duration, language=language,
                    windows_json=json.dumps(_payload(ws), ensure_ascii=False))

            total_batches = (len(windows) + SCORE_BATCH - 1) // SCORE_BATCH
            score_batch_items = [
                (batch_idx, windows[b:b + SCORE_BATCH])
                for batch_idx, b in enumerate(range(0, len(windows), SCORE_BATCH), 1)
            ]

            def _run_score_batch(item):
                batch_idx, batch_windows = item
                print(f"📊 [Passo 1/2] Lote {batch_idx}/{total_batches}...", flush=True)
                local_costs = []
                batch_scored = _run_stage_split(
                    client, model_name, batch_windows, _score_prompt,
                    gemini_worker.ScoreResponse, "windows", local_costs, "score")
                return batch_idx, batch_scored, local_costs

            if total_batches > 1:
                with ThreadPoolExecutor(max_workers=min(4, total_batches)) as executor:
                    score_results = list(executor.map(_run_score_batch, score_batch_items))
                score_results.sort(key=lambda r: r[0])
                for _, batch_scored, local_costs in score_results:
                    scored.extend(batch_scored)
                    costs.extend(local_costs)
            else:
                for item in score_batch_items:
                    _, batch_scored, local_costs = _run_score_batch(item)
                    scored.extend(batch_scored)
                    costs.extend(local_costs)

            scored.sort(key=lambda w: w.get("score", 0), reverse=True)
            target = max(3, min(10, int(video_duration // 90) + 2))
            by_id = {w["id"]: w for w in windows}
            shortlist = [by_id[w["id"]] for w in scored[:target] if w.get("id") in by_id]
            if not shortlist: shortlist = windows[:target]

            DETAIL_BATCH = detail_batch_size()
            if 600 < video_duration <= 1800 and not llm_backend.active():
                DETAIL_BATCH = 8
                
            detail_batches = (len(shortlist) + DETAIL_BATCH - 1) // DETAIL_BATCH
            detail_batch_items = [
                (b_idx, shortlist[b:b + DETAIL_BATCH])
                for b_idx, b in enumerate(range(0, len(shortlist), DETAIL_BATCH), 1)
            ]

            def _run_detail_batch(item):
                b_idx, batch_windows = item
                b_min = max(1, int(round(min_clips * len(batch_windows) / len(shortlist))))
                b_max = max(b_min, int(round(max_clips * len(batch_windows) / len(shortlist))) + 1)

                def _detail_prompt(ws):
                    return gemini_worker.DETAIL_PROMPT_TEMPLATE.format(
                        video_duration=video_duration, language=language,
                        min_clips=b_min, max_clips=b_max,
                        min_secs=min_secs, max_secs=max_secs,
                        windows_json=json.dumps(_payload(ws), ensure_ascii=False))

                print(f"🎯 [Passo 2/2] Lote {b_idx}/{detail_batches}...", flush=True)
                local_costs = []
                batch_shorts = _run_stage_split(client, model_name, batch_windows, _detail_prompt,
                                               gemini_worker.DetailResponse, "shorts", local_costs, "detail")
                return b_idx, batch_shorts, local_costs

            if detail_batches > 1:
                with ThreadPoolExecutor(max_workers=min(4, detail_batches)) as executor:
                    detail_results = list(executor.map(_run_detail_batch, detail_batch_items))
                detail_results.sort(key=lambda r: r[0])
                for _, batch_shorts, local_costs in detail_results:
                    shorts.extend(batch_shorts)
                    costs.extend(local_costs)
            else:
                for item in detail_batch_items:
                    _, batch_shorts, local_costs = _run_detail_batch(item)
                    shorts.extend(batch_shorts)
                    costs.extend(local_costs)
                
            if len(shorts) < min_clips:
                print(f"ℹ️ Completando {len(shorts)} -> {min_clips}...")
                for win in shortlist:
                    if len(shorts) >= min_clips: break
                    w_start, w_end = float(win.get("start") or 0.0), float(win.get("end") or 0.0)
                    overlaps = any(not (s.get("end", 0) <= w_start or s.get("start", 0) >= w_end) for s in shorts)
                    if not overlaps:
                        clip_len = min(45.0, max_secs)
                        c_start = w_start
                        c_end = min(w_end, c_start + clip_len)
                        if c_end - c_start >= min_secs:
                            shorts.append({
                                "start": c_start, "end": c_end,
                                "source_window_id": win.get("id", "window_fallback"),
                                "predicted_score": win.get("score", 75),
                                "explanation": "Fallback clip.",
                            })

        print(f"🔥 Encontrados {len(shorts)} shorts!")
        if len(shorts) > max_clips:
            dropped = len(shorts) - max_clips
            shorts = trim_to_best(shorts, max_clips)

        # Preserve model-generated metadata or initialize if absent
        for s in shorts:
            s.setdefault("video_description_for_tiktok", "")
            s.setdefault("video_description_for_instagram", "")
            s.setdefault("video_title_for_youtube_short", "")
            s.setdefault("viral_hook_text", "")

        for s in shorts:
            ns, ne = snap_clip_to_words(s.get("start", 0), s.get("end", 0), words, video_duration,
                                        min_duration=min_secs, max_duration=max_secs)
            s["start"], s["end"] = ns, ne

        from clip_metadata import clean_or_generate_clip_metadata
        import concurrent.futures

        def generate_meta(s):
            clean_or_generate_clip_metadata(
                s, transcript=transcript_result, start=s["start"], end=s["end"],
                video_title=video_title, language=language)

        print(f"⚡ Gerando metadados textuais de {len(shorts)} shorts em paralelo...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(shorts) or 1)) as executor:
            executor.map(generate_meta, shorts)
        print("⚡ Metadados textuais concluídos.")

        cost_analysis = None
        if costs:
            cost_analysis = {
                "input_tokens": sum(c.get("input_tokens", 0) for c in costs),
                "output_tokens": sum(c.get("output_tokens", 0) for c in costs),
                "total_cost": sum(c.get("total_cost", 0) for c in costs),
                "model": model_name,
            }
            print(f"💰 Total cost: ${cost_analysis['total_cost']:.6f}")

        if not shorts:
            return None

        result = {"shorts": shorts}
        if cost_analysis: result["cost_analysis"] = cost_analysis
        return result
    except gemini_worker.GeminiBlockedError as e:
        print(f"🚫 {e}")
        raise
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

# --- Speech too sparse to clip by transcript -------------------------------
# The vision path used to fire only on a missing audio TRACK. A nursery-rhyme
# video or a dashcam drive has audio, so it went through transcription, came
# back as one segment ("Uh uh"), produced one scoring window and Gemini
# returned no clips — three failed jobs on 25-aug-2026, one user twice. Speech
# is ~120-160 words/min; below these floors there is nothing to clip by words.
MIN_SPEECH_WORDS_PER_MIN = float(os.environ.get("MIN_SPEECH_WORDS_PER_MIN", "5"))
MIN_SPEECH_WORDS = int(os.environ.get("MIN_SPEECH_WORDS", "8"))


def speech_is_sparse(transcript, duration):
    """True when the transcript is too thin to drive clip selection."""
    words = sum(len((seg.get("text") or "").split())
                for seg in (transcript or {}).get("segments", []))
    minutes = max(float(duration or 0) / 60.0, 1e-6)
    return words < MIN_SPEECH_WORDS or words / minutes < MIN_SPEECH_WORDS_PER_MIN


def get_visual_clips(video_path, video_duration, language="en"):
    from services.cache import get_or_compute
    import asyncio
    import os
    source_hash = os.environ.get("SOURCE_HASH")

    def _compute():
        return _compute_visual_clips(video_path, video_duration, language)

    if source_hash:
        return asyncio.run(get_or_compute(source_hash, "visual_clips", _compute))
    return _compute()

def _compute_visual_clips(video_path, video_duration, language="en"):
    """Clip a SILENT video by vision: Gemini watches the footage and picks the
    most engaging visual moments (no transcript). Returns the same
    {"shorts", "cost_analysis"} shape as get_viral_clips, or None."""
    print("🎥  Silent video — analyzing with Gemini vision (no transcript)...")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        if llm_backend.active():
            print("❌ This video has no usable speech, so it has to be clipped by "
                  "watching it, and that needs Gemini (a text-only LLM server "
                  "cannot see the footage). Add a GEMINI_API_KEY for silent videos.")
        else:
            print("❌ Error: GEMINI_API_KEY not found.")
        return None
    client = genai.Client(api_key=api_key)
    model_name = os.environ.get("GEMINI_MODEL") or 'gemini-3.1-flash-lite'
    print(f"🎥  Model: {model_name} | uploading {os.path.basename(video_path)}…")

    file_upload = None
    try:
        file_upload = client.files.upload(file=video_path)
        deadline = time.time() + 180
        while True:
            info = client.files.get(name=file_upload.name)
            state = str(getattr(getattr(info, "state", info), "name", "")).upper()
            if state == "ACTIVE":
                break
            if state == "FAILED":
                print("❌ Gemini could not process the video.")
                return None
            if time.time() > deadline:
                print("❌ Gemini video processing timed out.")
                return None
            time.sleep(2)

        # The vision path has no scoring windows to derive a count from, so the
        # env targets (user request) apply directly over the classic 3-15.
        def _env_int(name, default):
            try:
                return max(1, int(os.environ.get(name, "")))
            except ValueError:
                return default
        v_min_clips = _env_int("CLIP_TARGET_MIN", 3)
        v_max_clips = max(v_min_clips, _env_int("CLIP_TARGET_MAX", 15))
        v_min_secs, v_max_secs = clip_duration_bounds()
        prompt = gemini_worker.VISUAL_PROMPT_TEMPLATE.format(
            video_duration=video_duration, language=language,
            min_clips=v_min_clips, max_clips=v_max_clips,
            min_secs=v_min_secs, max_secs=v_max_secs)
        config = genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=gemini_worker.VisualResponse,
        )
        response = client.models.generate_content(
            model=model_name, contents=[file_upload, prompt], config=config)
        gemini_worker.raise_if_blocked(response)
        parsed = json.loads(response.text)
        shorts = parsed.get("shorts") or []
        # Clamp to the real duration; drop anything degenerate.
        clean = []
        for s in shorts:
            s["start"] = max(0.0, float(s.get("start", 0)))
            s["end"] = min(float(video_duration), float(s.get("end", 0)))
            if s["end"] - s["start"] >= 1.0:
                clean.append(s)
        if not clean:
            print("⚠️ Vision pass returned no usable clips.")
            return None

        cost = gemini_worker._calculate_cost_analysis(response, model_name)
        if cost:
            print(f"💰 Vision cost ({model_name}): ${cost.get('total_cost', 0):.6f}")
        result = {"shorts": clean}
        if cost:
            result["cost_analysis"] = cost
        return result
    except gemini_worker.GeminiBlockedError as e:
        print(f"🚫 {e}")
        raise
    except Exception as e:
        print(f"❌ Gemini vision error: {e}")
        return None
    finally:
        if file_upload is not None:
            try:
                client.files.delete(name=file_upload.name)
            except Exception:
                pass


