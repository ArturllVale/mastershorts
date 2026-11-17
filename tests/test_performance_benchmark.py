"""Fast, deterministic pipeline benchmark with schema-correct fake LLM stages.

Unlike the historical test, mock outputs must match the CURRENT anchor,
score and detail schemas and use real candidate ids. No Gemini calls.
"""
import time
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_video_17min():
    duration = 17 * 60
    words = []
    for i in range(2550):
        start = i * 0.4
        words.append({"word": f"word_{i}", "start": start,
                      "end": start + 0.3, "text": f"word_{i}"})
    return {"language": "pt", "segments": [
        {"start": 0, "end": duration,
         "text": " ".join(w["word"] for w in words),
         "words": words}]}, duration


def test_17min_video_performance_benchmark(mock_video_17min):
    from backend import viral_analysis as va

    transcript, duration = mock_video_17min
    stages = []

    def fake_stage(client, model, items, build_prompt, schema, key, costs, label):
        stages.append(schema.__name__)
        if schema.__name__ == "AnchorResponse":
            return [{"id": "a_001", "start": 45, "end": 55,
                     "text": "interesting moment", "anchor_type": "story"}]
        if schema.__name__ == "ScoreResponse":
            return [{"id": c["id"], "start": c["start"], "end": c["end"],
                     "score": 95} for c in items]
        if schema.__name__ == "DetailResponse":
            return [{"source_window_id": c["id"], "start": c["start"],
                     "end": c["end"], "predicted_score": 95,
                     "explanation": "Strong payoff"} for c in items]
        raise AssertionError(f"Unexpected schema: {schema.__name__}")

    def fake_pair(client, model, prompt, schema):
        return {"winner": {"winner_id": "c_001", "reason": "best hook"}}, None

    started = time.monotonic()
    with patch.object(va.llm_backend, "active", return_value=False), \
         patch.object(va.genai, "Client"), \
         patch.object(va, "_run_stage_split", side_effect=fake_stage), \
         patch.object(va, "_run_gemini_stage", side_effect=fake_pair), \
         patch("clip_metadata.clean_or_generate_clip_metadata"):
        result = va.get_viral_clips(transcript, duration, "Test Video")

    elapsed = time.monotonic() - started
    assert result["shorts"]
    assert all(s["predicted_score"] >= 83 for s in result["shorts"])
    assert "AnchorResponse" in stages
    assert "ScoreResponse" in stages
    assert "DetailResponse" in stages
    assert elapsed < 5.0, f"Pure Python selection too slow: {elapsed:.2f}s"
