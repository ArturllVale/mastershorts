"""Merge independent transcript and visual highlights without heavy dependencies."""
import math

def _number(value, default=0.0):
    try:
        n = float(value)
        return n if math.isfinite(n) else default
    except (TypeError, ValueError):
        return default

def _valid(clips, duration, origin):
    result = []
    for raw in clips or []:
        if not isinstance(raw, dict):
            continue
        start = _number(raw.get("start"), -1)
        end = _number(raw.get("end"), -1)
        if start < 0 or end < 0:
            continue
        start, end = max(0.0, start), min(duration, end)
        if end - start < 1.0:
            continue
        item = dict(raw)
        item.update(start=round(start, 3), end=round(end, 3), discovery_source=origin)
        result.append(item)
    return result

def _overlap_ratio(a, b):
    overlap = max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
    shorter = min(a["end"] - a["start"], b["end"] - b["start"])
    return overlap / shorter if shorter > 0 else 0.0

def merge_highlights(speech_clips, visual_clips, duration, max_clips=15,
                     visual_share=0.5, overlap_limit=0.45):
    """Round-robin merge avoids comparing uncalibrated scores across models."""
    duration = max(0.0, _number(duration))
    if not duration:
        return []
    limit = max(1, min(100, int(max_clips)))
    share = min(1.0, max(0.0, _number(visual_share, 0.5)))
    queues = [_valid(speech_clips, duration, "transcript"),
              _valid(visual_clips, duration, "vision")]
    visual_cap = limit if not queues[0] else (max(1, round(limit * share)) if share else 0)
    selected = []
    counts = [0, 0]

    def take(source):
        if source == 1 and counts[1] >= visual_cap:
            return False
        while queues[source]:
            candidate = queues[source].pop(0)
            if any(_overlap_ratio(candidate, existing) > overlap_limit for existing in selected):
                continue
            selected.append(candidate)
            counts[source] += 1
            return True
        return False

    while len(selected) < limit:
        progress = take(0)
        if len(selected) < limit:
            progress = take(1) or progress
        if not progress:
            break
    return selected

def combine_clip_results(speech_result, visual_result, duration, max_clips=15):
    """Keep the existing API shape; aggregate reported model costs."""
    speech_result, visual_result = speech_result or {}, visual_result or {}
    result = dict(speech_result)
    result["shorts"] = merge_highlights(speech_result.get("shorts"),
                                        visual_result.get("shorts"), duration,
                                        max_clips=max_clips)
    costs = [c for c in (speech_result.get("cost_analysis"),
                         visual_result.get("cost_analysis")) if isinstance(c, dict)]
    if costs:
        result["cost_analysis"] = {
            **{k: sum(_number(c.get(k)) for c in costs)
               for k in ("input_tokens", "output_tokens", "total_cost")},
            "model": " + ".join(str(c.get("model", "unknown")) for c in costs),
        }
    return result
