"""Regression tests for hybrid visual + transcript discovery."""
from hybrid_selection import merge_highlights, combine_clip_results

def clip(start, end):
    return {"start": start, "end": end}

def test_balanced_sources_and_deduplication():
    spoken = [clip(10, 40), clip(100, 130), clip(200, 230)]
    visual = [clip(12, 35), clip(150, 185), clip(260, 290)]
    combined = merge_highlights(spoken, visual, 300, max_clips=4)
    assert len(combined) == 4
    assert [c["discovery_source"] for c in combined] == [
        "transcript", "vision", "transcript", "vision"]
    assert all(c["start"] != 12 for c in combined)

def test_no_vision_preserves_spoken_and_input():
    source = [clip(10, 22), clip(30, 42), clip(60, 72)]
    merged = merge_highlights(source, None, 100, max_clips=10)
    assert [c["start"] for c in merged] == [10, 30, 60]
    assert all("discovery_source" not in c for c in source)

def test_visual_only_receives_all_slots():
    assert len(merge_highlights([], [clip(0, 10), clip(20, 30), clip(40, 50)],
                                60, max_clips=3)) == 3

def test_reject_invalid_timestamps_and_clamp():
    source = [clip(float("nan"), 20), clip(20, float("inf")),
              clip(20, 19), clip(0, 0.5), clip(10, 20), clip(25, 1000)]
    result = merge_highlights(source, [], 60)
    assert [(c["start"], c["end"]) for c in result] == [(10, 20), (25, 60)]

def test_costs_and_metadata_survive():
    a = {"shorts": [clip(10, 20)], "transcript": {"language": "en"},
         "cost_analysis": {"input_tokens": 10, "total_cost": .01, "model": "text"}}
    b = {"shorts": [clip(40, 50)],
         "cost_analysis": {"input_tokens": 20, "total_cost": .03, "model": "vision"}}
    combined = combine_clip_results(a, b, 60)
    assert combined["transcript"] == {"language": "en"}
    assert combined["cost_analysis"]["input_tokens"] == 30
    assert abs(combined["cost_analysis"]["total_cost"] - .04) < 1e-8
    assert len(combined["shorts"]) == 2
