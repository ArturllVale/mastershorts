"""The OpenAI-compatible moment-picker backend (llm_backend.py).

Self-hosters asked for a pipeline that never calls Google. The transcript
passes go to any /chat/completions server when LLM_BASE_URL is set; these
tests pin the contract viral_analysis.py relies on: same (parsed, cost) shape as the
Gemini stage, schema validation, and the response_format fallback ladder.
"""
import json

import httpx
import pytest

import gemini_worker
import llm_backend


@pytest.fixture
def local(monkeypatch):
    llm_backend._capability_cache.clear()
    monkeypatch.setenv("LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:14b")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MAX_RETRIES", raising=False)


def _serve(handler, monkeypatch):
    """Route llm_backend's httpx client through an in-process handler."""
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(llm_backend, "_client",
                        lambda **kw: httpx.Client(transport=transport, **kw))


def _completion(payload, usage=None):
    return httpx.Response(200, json={
        "choices": [{"message": {"role": "assistant", "content": json.dumps(payload)}}],
        "usage": usage or {"prompt_tokens": 120, "completion_tokens": 40},
    })


# --- activation -----------------------------------------------------------

def test_inactive_without_a_base_url(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert llm_backend.active() is False
    assert llm_backend.describe() is None


def test_base_url_alone_activates_and_describes(local):
    assert llm_backend.active() is True
    assert llm_backend.describe() == {
        "provider": "openai", "model": "qwen2.5:14b", "baseUrl": "http://llm.test/v1",
        "fallbackModels": []}


def test_explicit_gemini_provider_wins_over_base_url(local, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert llm_backend.active() is False


# --- generate_json ---------------------------------------------------------

def test_returns_validated_payload_and_zero_cost(local, monkeypatch):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return _completion({"windows": [{"id": "w0", "start": 0, "end": 90, "score": 88, "reason": "hook"}]})

    _serve(handler, monkeypatch)
    parsed, cost = llm_backend.generate_json("prompt", gemini_worker.ScoreResponse)

    assert seen["url"] == "http://llm.test/v1/chat/completions"
    assert seen["body"]["model"] == "qwen2.5:14b"
    assert seen["body"]["response_format"]["type"] == "json_schema"
    assert seen["auth"] == "Bearer ollama"  # documented placeholder when no key is set
    assert parsed["windows"][0]["score"] == 88
    assert cost["total_cost"] == 0.0 and cost["local"] is True
    assert cost["input_tokens"] == 120 and cost["output_tokens"] == 40


def test_falls_back_to_json_object_when_schema_mode_is_rejected(local, monkeypatch):
    formats = []

    def handler(request):
        body = json.loads(request.content)
        fmt = (body.get("response_format") or {}).get("type")
        formats.append(fmt)
        if fmt == "json_schema":
            return httpx.Response(400, json={"error": {"message": "response_format json_schema not supported"}})
        return _completion({"windows": []})

    _serve(handler, monkeypatch)
    parsed, _ = llm_backend.generate_json("prompt", gemini_worker.ScoreResponse)
    assert formats == ["json_schema", "json_object"]
    assert parsed == {"windows": []}


def test_code_fenced_json_is_accepted(local, monkeypatch):
    """Small models wrap the object in ```json fences even when told not to."""
    def handler(request):
        text = "```json\n" + json.dumps({"windows": []}) + "\n```"
        return httpx.Response(200, json={"choices": [{"message": {"content": text}}], "usage": {}})

    _serve(handler, monkeypatch)
    parsed, _ = llm_backend.generate_json("prompt", gemini_worker.ScoreResponse)
    assert parsed == {"windows": []}


def test_schema_violation_raises_instead_of_leaking_into_the_pipeline(local, monkeypatch):
    _serve(lambda r: _completion({"windows": [{"id": "w0"}]}), monkeypatch)
    with pytest.raises(Exception) as exc:
        llm_backend.generate_json("prompt", gemini_worker.ScoreResponse)
    assert "validation error" in str(exc.value)


def test_server_errors_surface_with_status_and_url(local, monkeypatch):
    _serve(lambda r: httpx.Response(503, text="loading model"), monkeypatch)
    with pytest.raises(RuntimeError) as exc:
        llm_backend.generate_json("prompt", gemini_worker.ScoreResponse)
    assert "503" in str(exc.value) and "loading model" in str(exc.value)


# --- viral_analysis.py routing (needs the heavy deps; skipped on minimal CI) ------------

def test_stage_routes_to_local_backend_and_retries_transient(local, monkeypatch):
    viral_analysis = pytest.importorskip("viral_analysis")
    monkeypatch.setattr(viral_analysis.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    def fake_generate(prompt, schema, model=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("ConnectError: connection refused")
        return {"windows": [{"id": "w0", "start": 0, "end": 1, "score": 50, "reason": ""}]}, {"total_cost": 0.0}

    monkeypatch.setattr(llm_backend, "generate_json", fake_generate)
    parsed, cost = viral_analysis._run_gemini_stage(None, "qwen2.5:14b", "prompt", gemini_worker.ScoreResponse)
    assert calls["n"] == 2
    assert parsed["windows"][0]["score"] == 50
    assert cost["total_cost"] == 0.0


def test_score_batch_shrinks_for_local_models(local, monkeypatch):
    viral_analysis = pytest.importorskip("viral_analysis")
    monkeypatch.delenv("LLM_SCORE_BATCH", raising=False)
    assert viral_analysis.score_batch_size() == 3
    monkeypatch.setenv("LLM_SCORE_BATCH", "5")
    assert viral_analysis.score_batch_size() == 5
    monkeypatch.delenv("LLM_BASE_URL")
    monkeypatch.delenv("LLM_SCORE_BATCH")
    assert viral_analysis.score_batch_size() == 8


# --- combo provider & fallback tests ---------------------------------------

def test_combo_activation(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "combo")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    assert llm_backend.provider() == "combo"
    assert llm_backend.active() is False

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    assert llm_backend.active() is True
    desc = llm_backend.describe()
    assert desc["provider"] == "combo"
    assert "openrouter/free" in desc["models"]
    assert desc["hasOpenRouterKey"] is True
    assert desc["hasGeminiKey"] is False


def test_combo_fallback_gemini_to_openrouter(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "combo")
    monkeypatch.setenv("GEMINI_API_KEY", "ai-gemini-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-key")
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    seen = []

    def handler(request):
        seen.append((str(request.url), json.loads(request.content)))
        if "generativelanguage.googleapis.com" in str(request.url):
            # Simulate Gemini rate limited
            return httpx.Response(429, json={"error": {"message": "Resource has been exhausted (rate limit)"}})
        if "openrouter.ai" in str(request.url):
            # OpenRouter receives openrouter/free
            return _completion({"windows": [{"id": "w_or", "start": 10, "end": 40, "score": 95, "reason": "viral"}]})
        return httpx.Response(500)

    _serve(handler, monkeypatch)
    parsed, cost = llm_backend.generate_json("prompt", gemini_worker.ScoreResponse)

    assert len(seen) >= 2
    # Ensure OpenRouter received openrouter/free
    or_call = next(c for c in seen if "openrouter.ai" in c[0])
    assert or_call[1]["model"] == "openrouter/free"
    assert parsed["windows"][0]["score"] == 95


def test_combo_fallback_openrouter_to_mistral(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "combo")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-openrouter-key")
    monkeypatch.setenv("MISTRAL_API_KEY", "sk-mistral-key")

    seen = []

    def handler(request):
        seen.append((str(request.url), json.loads(request.content)))
        if "openrouter.ai" in str(request.url):
            # OpenRouter is down
            return httpx.Response(503, text="Service Temporarily Unavailable")
        if "api.mistral.ai" in str(request.url):
            return _completion({"windows": [{"id": "w_mis", "start": 0, "end": 30, "score": 90, "reason": "hook"}]})
        return httpx.Response(500)

    _serve(handler, monkeypatch)
    parsed, cost = llm_backend.generate_json("prompt", gemini_worker.ScoreResponse)

    assert any("openrouter.ai" in c[0] for c in seen)
    mis_call = next(c for c in seen if "api.mistral.ai" in c[0])
    assert mis_call[1]["model"] == "mistral-small-latest"
    assert parsed["windows"][0]["score"] == 90


