"""Text-only LLM backend for the moment picker: any OpenAI-compatible server.

Ollama, LM Studio, vLLM, llama.cpp's server, LocalAI and OpenRouter all speak
``POST {base}/chat/completions``. When ``LLM_BASE_URL`` is set (or
``LLM_PROVIDER=openai``), the transcript scoring and detail passes in
``main.get_viral_clips`` go here instead of Gemini, so a self-hosted install
can run the whole pipeline without a Google key.

What stays on Gemini, because it needs a model that can look at frames or a
video file: the layout picker (``layout_picker.py``), the on-screen content
detector (``screencast_layout.py``) and the silent-video path
(``main.get_visual_clips``). Without a Gemini key those degrade the way they
already did: the first two return "none", the third fails the job with a clear
message. Nothing in this module is imported by them.

Structured output: the prompts already spell out the exact JSON shape, so a
plain ``json_object`` mode is enough for most models. The request first asks
for ``json_schema`` (Ollama, vLLM, llama.cpp and LM Studio enforce it); a
server that rejects that field gets the same request again with
``json_object``, then with no ``response_format`` at all. Whatever comes back
is validated with the same pydantic model Gemini's ``response_schema`` uses,
so ``main.py`` sees one shape regardless of provider.
"""
from __future__ import annotations

import json
import os
import time
from typing import Optional, Tuple, Type

import httpx
from pydantic import BaseModel

DEFAULT_MODEL = "llama3.1:8b"
DEFAULT_TIMEOUT = 120.0  # reasonable timeout preventing indefinite hangs


def provider() -> str:
    """``"openai"`` when a compatible endpoint is configured, else ``"gemini"``."""
    explicit = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if explicit in ("openai", "ollama", "local", "openai-compatible"):
        return "openai"
    if explicit == "gemini":
        return "gemini"
    return "openai" if base_url() else "gemini"


def base_url() -> str:
    return (os.environ.get("LLM_BASE_URL") or "").strip().rstrip("/")


def model_name() -> str:
    return (os.environ.get("LLM_MODEL") or "").strip() or DEFAULT_MODEL


def active() -> bool:
    """True when the moment picker should call the OpenAI-compatible server."""
    return provider() == "openai" and bool(base_url())


def fallback_models() -> list[str]:
    raw = (os.environ.get("LLM_FALLBACK_MODELS") or "").strip()
    if raw:
        return [m.strip() for m in raw.replace("\n", ",").split(",") if m.strip()]
    return []


def describe() -> Optional[dict]:
    """What ``/api/config`` tells the dashboard, or ``None`` when inactive."""
    if not active():
        return None
    return {
        "provider": "openai",
        "model": model_name(),
        "baseUrl": base_url(),
        "fallbackModels": fallback_models(),
    }


def _timeout() -> float:
    try:
        return float(os.environ.get("LLM_TIMEOUT") or DEFAULT_TIMEOUT)
    except ValueError:
        return DEFAULT_TIMEOUT


def _headers() -> dict:
    # Ollama ignores the key but the OpenAI client convention (and vLLM with
    # --api-key) wants the header present; "ollama" is the documented placeholder.
    key = (os.environ.get("LLM_API_KEY") or "ollama").strip()
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _client(**kwargs) -> httpx.Client:
    """Factory so tests can swap in ``httpx.MockTransport``."""
    return httpx.Client(timeout=_timeout(), **kwargs)


def _response_formats(schema: Type[BaseModel]):
    name = getattr(schema, "__name__", "response").lower()
    yield {"type": "json_schema",
           "json_schema": {"name": name, "schema": schema.model_json_schema()}}
    yield {"type": "json_object"}
    yield None


def _is_format_rejection(resp: httpx.Response) -> bool:
    if resp.status_code not in (400, 422):
        return False
    body = resp.text.lower()
    return "response_format" in body or "json_schema" in body or "json_object" in body \
        or "format" in body


def generate_json(prompt: str, schema: Type[BaseModel], model: Optional[str] = None,
                  ) -> Tuple[dict, Optional[dict]]:
    """One chat completion that must come back as JSON matching ``schema``.

    Returns ``(parsed_dict, cost_analysis)`` in the exact shape
    ``main._run_gemini_stage`` returns. If a model fails (HTTP error,
    rate limit, or schema mismatch), tries fallback models configured in
    ``LLM_FALLBACK_MODELS`` sequentially.
    """
    from core.json_utils import parse_json_response_text  # local import: keeps this module free of the google SDK

    primary = model or model_name()
    candidates = [primary]
    for fb in fallback_models():
        if fb and fb not in candidates:
            candidates.append(fb)

    last_error: Optional[Exception] = None
    for idx, candidate_model in enumerate(candidates):
        url = f"{base_url()}/chat/completions"
        messages = [
            {"role": "system", "content": "You answer with a single JSON object and nothing else."},
            {"role": "user", "content": prompt},
        ]
        last_rejection: Optional[str] = None
        try:
            with _client() as client:
                data = None
                for fmt in _response_formats(schema):
                    body = {"model": candidate_model, "messages": messages, "temperature": 0.2, "stream": False}
                    if fmt is not None:
                        body["response_format"] = fmt
                    t_start = time.time()
                    print(f"   🤖 Enviando requisição para '{candidate_model}'...", flush=True)
                    resp = client.post(url, json=body, headers=_headers())
                    elapsed = time.time() - t_start
                    if fmt is not None and _is_format_rejection(resp):
                        last_rejection = resp.text[:200]
                        print(f"   ⚠️ Modelo rejeitou formato, tentando alternativa... ({elapsed:.1f}s)", flush=True)
                        continue
                    if resp.status_code >= 400:
                        raise RuntimeError(
                            f"LLM server {resp.status_code} from {url}: {resp.text[:300]}")
                    data = resp.json()
                    print(f"   ⚡ Resposta recebida de '{candidate_model}' em {elapsed:.1f}s", flush=True)
                    break
                else:
                    raise RuntimeError(
                        f"LLM server rejected every response_format variant: {last_rejection}")

            choices = data.get("choices") or []
            text = ""
            if choices:
                msg = choices[0].get("message") or {}
                text = msg.get("content") or ""
                if isinstance(text, list):  # some servers return content parts
                    text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
                if not text and msg.get("reasoning_content"):
                    text = msg.get("reasoning_content") or ""
            parsed = parse_json_response_text(text)
            validated = schema.model_validate(parsed).model_dump()

            usage = data.get("usage") or {}
            cost = {
                "input_tokens": int(usage.get("prompt_tokens") or 0),
                "output_tokens": int(usage.get("completion_tokens") or 0),
                "thinking_tokens": 0,
                "input_cost": 0.0,
                "output_cost": 0.0,
                "total_cost": 0.0,
                "model": candidate_model,
                "price_estimated": False,
                "local": True,
            }
            if idx > 0:
                print(f"[LLM Fallback] Succeeded with fallback model: {candidate_model}")
            return validated, cost

        except Exception as e:
            last_error = e
            if idx < len(candidates) - 1:
                next_model = candidates[idx + 1]
                print(f"[LLM Fallback] Model '{candidate_model}' failed ({e}). Switching to fallback '{next_model}'...")
            else:
                print(f"[LLM Fallback] All candidate models failed. Last error: {e}")

    if last_error:
        raise last_error
    raise RuntimeError("No LLM models available to execute prompt")
