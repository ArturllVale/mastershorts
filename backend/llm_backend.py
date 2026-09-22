from __future__ import annotations

import json
import os
import time
from typing import Optional, Tuple, Type, Dict, Any, Generator

import httpx
from pydantic import BaseModel
import threading

DEFAULT_MODEL = "llama3.1:8b"
DEFAULT_TIMEOUT = 120.0  # reasonable timeout preventing indefinite hangs


def provider() -> str:
    """``"combo"`` when combo free router is configured, ``"openai"`` when a compatible endpoint is configured, else ``"gemini"``."""
    explicit = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if explicit in ("combo", "combo_free", "free_combo"):
        return "combo"
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
    """True when the moment picker should call the OpenAI-compatible server or combo router."""
    p = provider()
    if p == "combo":
        return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("MISTRAL_API_KEY"))
    return p == "openai" and bool(base_url())


def fallback_models() -> list[str]:
    raw = (os.environ.get("LLM_FALLBACK_MODELS") or "").strip()
    if raw:
        return [m.strip() for m in raw.replace("\n", ",").split(",") if m.strip()]
    return []


def describe() -> Optional[dict]:
    """What ``/api/config`` tells the dashboard, or ``None`` when inactive."""
    if not active():
        return None
    if provider() == "combo":
        return {
            "provider": "combo",
            "models": ["gemini-2.5-flash", "openrouter/free", "mistral-small-latest"],
            "hasGeminiKey": bool(os.environ.get("GEMINI_API_KEY")),
            "hasOpenRouterKey": bool(os.environ.get("OPENROUTER_API_KEY")),
            "hasMistralKey": bool(os.environ.get("MISTRAL_API_KEY")),
        }
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
    key = (os.environ.get("LLM_API_KEY") or "ollama").strip()
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _client(**kwargs) -> httpx.Client:
    return httpx.Client(timeout=_timeout(), **kwargs)


def _all_response_formats(schema: Type[BaseModel]) -> list[dict | None]:
    name = getattr(schema, "__name__", "response").lower()
    return [
        {"type": "json_schema", "json_schema": {"name": name, "schema": schema.model_json_schema()}},
        {"type": "json_object"},
        None
    ]


def _is_format_rejection(resp: httpx.Response) -> bool:
    if resp.status_code not in (400, 422):
        return False
    body = resp.text.lower()
    return "response_format" in body or "json_schema" in body or "json_object" in body or "format" in body

# Global cache to discover capabilities per base_url + model
_capability_cache: Dict[str, dict | None] = {}
_capability_lock = threading.Lock()

class RetryableError(Exception):
    pass

class NonRetryableError(Exception):
    pass

class FallbackError(Exception):
    pass

def classify_error(resp: httpx.Response | None, exc: Exception | None) -> str:
    """Returns 'RETRYABLE', 'FALLBACK', or 'NON_RETRYABLE'"""
    if resp is None and isinstance(exc, httpx.HTTPStatusError):
        resp = exc.response

    if resp is not None:
        if _is_format_rejection(resp):
            return 'NON_RETRYABLE'
        if resp.status_code in (429, 500, 502, 503, 504):
            return 'RETRYABLE'
        if resp.status_code in (401, 403, 404):
            return 'NON_RETRYABLE'
        if resp.status_code >= 400:
            return 'FALLBACK'

    if exc is not None:
        msg = str(exc).lower()
        if any(x in msg for x in ('timeout', 'connect', 'read', 'remote', 'reset')):
            return 'RETRYABLE'
        return 'FALLBACK'

    return 'FALLBACK'


def _execute_chat_completion(
    url: str,
    headers: dict,
    model: str,
    prompt: str,
    schema: Type[BaseModel],
    max_retries: int = 1,
) -> Tuple[dict, Optional[dict]]:
    """Executes a single chat completion across formats and retries, returning (validated_dict, cost)."""
    from core.json_utils import parse_json_response_text

    cache_key = f"{url}_{model}"
    with _capability_lock:
        cached_format = _capability_cache.get(cache_key, "UNKNOWN")

    all_formats = _all_response_formats(schema)
    formats_to_try = [cached_format] + [f for f in all_formats if f != cached_format] if (cached_format != "UNKNOWN" and cached_format in all_formats) else all_formats

    messages = [
        {"role": "system", "content": "You answer with a single JSON object and nothing else."},
        {"role": "user", "content": prompt},
    ]

    last_err: Optional[Exception] = None

    for fmt in formats_to_try:
        retry_count = 0
        while retry_count <= max_retries:
            body = {"model": model, "messages": messages, "temperature": 0.2, "stream": False}
            if fmt is not None:
                body["response_format"] = fmt

            t_start = time.time()
            resp = None
            exc = None
            try:
                with _client() as client:
                    resp = client.post(url, json=body, headers=headers)
                    resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                resp = e.response
                exc = e
            except Exception as e:
                exc = e

            elapsed = time.time() - t_start

            if not exc and resp and resp.status_code == 200:
                if cached_format == "UNKNOWN":
                    with _capability_lock:
                        _capability_cache[cache_key] = fmt
                print(f"[LLM] stage=generate model={model} attempt={retry_count+1} status=success latency={elapsed:.2f}s")

                data = resp.json()
                choices = data.get("choices") or []
                text = ""
                if choices:
                    msg = choices[0].get("message") or {}
                    text = msg.get("content") or ""
                    if isinstance(text, list):
                        text = "".join(p.get("text", "") for p in text if isinstance(p, dict))
                    if not text and msg.get("reasoning_content"):
                        text = msg.get("reasoning_content") or ""

                try:
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
                        "model": model,
                        "price_estimated": False,
                        "local": True,
                    }
                    return validated, cost
                except Exception as parse_err:
                    print(f"[LLM] stage=generate model={model} attempt={retry_count+1} error=parse_error: {parse_err}")
                    exc = parse_err

            err_class = classify_error(resp, exc)
            err_msg = str(exc) if exc else f"HTTP {resp.status_code}: {resp.text[:200]}"

            if err_class == 'NON_RETRYABLE':
                if resp and _is_format_rejection(resp):
                    with _capability_lock:
                        _capability_cache.pop(cache_key, None)
                    break  # try next response format
                raise RuntimeError(f"Non-retryable LLM error: {err_msg}")

            elif err_class == 'RETRYABLE':
                retry_count += 1
                if retry_count <= max_retries:
                    time.sleep(1)
                    continue
                else:
                    if isinstance(exc, httpx.HTTPStatusError) and resp is not None:
                        last_err = RuntimeError(f"Server error {resp.status_code}: {resp.text}")
                    elif exc and isinstance(exc, RuntimeError):
                        last_err = exc
                    else:
                        last_err = RuntimeError(err_msg)
                    break

            elif err_class == 'FALLBACK':
                last_err = exc or RuntimeError(err_msg)
                break

        if classify_error(resp, exc) != 'NON_RETRYABLE' or (resp and not _is_format_rejection(resp)):
            break

    if last_err:
        raise last_err
    raise RuntimeError(f"Failed to generate JSON with model {model}")


def _generate_json_combo(prompt: str, schema: Type[BaseModel]) -> Tuple[dict, Optional[dict]]:
    """Combo free router: rotates and falls back between Gemini, OpenRouter (openrouter/free), and Mistral."""
    providers = []

    gemini_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if gemini_key:
        providers.append({
            "name": "Gemini",
            "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "headers": {"Authorization": f"Bearer {gemini_key}", "Content-Type": "application/json"},
            "models": [os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash", "gemini-3.1-flash-lite"],
        })

    openrouter_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if openrouter_key:
        providers.append({
            "name": "OpenRouter",
            "url": "https://openrouter.ai/api/v1/chat/completions",
            "headers": {
                "Authorization": f"Bearer {openrouter_key}",
                "HTTP-Referer": "https://mastershorts.com",
                "X-Title": "MasterShorts",
                "Content-Type": "application/json",
            },
            "models": ["openrouter/free"],
        })

    mistral_key = (os.environ.get("MISTRAL_API_KEY") or "").strip()
    if mistral_key:
        providers.append({
            "name": "Mistral",
            "url": "https://api.mistral.ai/v1/chat/completions",
            "headers": {"Authorization": f"Bearer {mistral_key}", "Content-Type": "application/json"},
            "models": [os.environ.get("MISTRAL_MODEL") or "mistral-small-latest", "open-mistral-nemo"],
        })

    if not providers:
        raise RuntimeError("Combo provider selected, but no API keys configured for Gemini, OpenRouter, or Mistral.")

    errors = []
    for prov in providers:
        prov_name = prov["name"]
        url = prov["url"]
        headers = prov["headers"]
        for model in prov["models"]:
            print(f"[Combo] Routing to provider={prov_name} model={model}...")
            try:
                validated, cost = _execute_chat_completion(url, headers, model, prompt, schema, max_retries=1)
                print(f"[Combo] Success with provider={prov_name} model={model}")
                return validated, cost
            except Exception as e:
                err_msg = str(e)
                print(f"[Combo] Fallback triggered: {prov_name} ({model}) error: {err_msg[:120]}")
                errors.append(f"{prov_name}/{model}: {err_msg[:80]}")

    raise RuntimeError(f"All combo providers failed: {'; '.join(errors)}")


def generate_json(prompt: str, schema: Type[BaseModel], model: Optional[str] = None,
                  ) -> Tuple[dict, Optional[dict]]:
    """One chat completion that must come back as JSON matching ``schema``."""
    if provider() == "combo":
        return _generate_json_combo(prompt, schema)

    primary = model or model_name()
    candidates = [primary]
    for fb in fallback_models():
        if fb and fb not in candidates:
            candidates.append(fb)

    # Configurable Limits
    max_retries = int(os.environ.get("LLM_MAX_RETRIES", 2))
    max_fallbacks = int(os.environ.get("LLM_FALLBACK_MAX", 1))

    last_error: Optional[Exception] = None
    fallback_count = 0
    url = f"{base_url()}/chat/completions"

    for candidate_model in candidates:
        if fallback_count > max_fallbacks and candidate_model != primary:
            break

        try:
            return _execute_chat_completion(url, _headers(), candidate_model, prompt, schema, max_retries=max_retries)
        except Exception as e:
            last_error = e
            fallback_count += 1
    if last_error:
        raise last_error
    raise RuntimeError("No LLM models available to execute prompt")


