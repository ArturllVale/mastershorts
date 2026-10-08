"""
Pure helpers for the Gemini clip-selection pipeline.

Standard-library only so both main.py and gemini_worker.py can import it and
the logic stays unit-testable without the heavy video dependencies.
"""

# USD per 1M tokens (input, output incl. thinking), from ai.google.dev pricing.
MODEL_PRICES = {
    "gemini-3.5-flash": (1.50, 9.00),
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3-flash-preview": (0.50, 3.00),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.0-flash": (0.10, 0.40),  # deprecated (shut down 2026-06-01)
}


def lookup_model_prices(model_name):
    """Longest-prefix match against MODEL_PRICES; None if unknown."""
    name = str(model_name or "").lower()
    best_key = None
    for key in MODEL_PRICES:
        if name.startswith(key) and (best_key is None or len(key) > len(best_key)):
            best_key = key
    return MODEL_PRICES[best_key] if best_key else None


def clip_count_targets(n_windows):
    """How many clips to ask the detail pass for, given the shortlist size.

    Measured on prod 3-ago-2026: 408 of 429 jobs (95%) delivered 3 clips or
    fewer, the mode being ONE, while the prompt was free to return one per
    shortlisted window. Users who received 1-3 clips came back a second day
    0.4% of the time; those who received 4-9 came back 16.1% — so the clip
    count, not the clip quality, is what the retention curve hangs on.

    The old prompt biased hard the other way ("prefer one great clip per
    candidate window") and handed the model two unbounded licences to drop
    clips (the 2-second rule and STANDS ALONE both end in "or skip it"), with
    no floor to stop it collapsing to a single clip. This puts a floor and a
    realistic ceiling on it instead.

    ``CLIP_TARGET_MIN`` / ``CLIP_TARGET_MAX`` override both for A/B runs
    without a deploy (the reframe-testing harness drives them).
    """
    import os

    n = max(1, int(n_windows or 1))
    # Floor grows with the material: 3 windows -> 4, 5 -> 5, 10+ -> 7.
    low = max(3, min(8, n // 2 + 2))
    # Ceiling allows a rich window to yield more than one without inviting padding.
    high = min(18, max(6, n * 2))
    low = min(low, high)

    def _override(name, current):
        raw = os.environ.get(name)
        if not raw:
            return current
        try:
            return max(1, int(raw))
        except ValueError:
            return current

    low = _override("CLIP_TARGET_MIN", low)
    high = _override("CLIP_TARGET_MAX", high)
    return low, max(low, high)


def trim_to_best(shorts, max_clips):
    """Cut an over-long detail-pass result down to ``max_clips`` BY SCORE,
    applying Maximum Marginal Relevance (MMR) for diversity and temporal coverage.

    Ranking is initially by ``predicted_score``. A similarity penalty is applied
    to prevent selecting overlapping or highly similar clips. We also enforce
    a hard overlap limit and an optional quota for story arcs.
    """
    max_clips = max(1, int(max_clips or 1))
    if len(shorts) <= max_clips:
        return list(shorts)

    def score(clip):
        try:
            return float(clip.get("predicted_score") or 0)
        except (TypeError, ValueError, AttributeError):
            return 0.0

    def _similarity(clip_a, clip_b):
        start_a = float(clip_a.get("start", 0))
        end_a = float(clip_a.get("end", 0))
        start_b = float(clip_b.get("start", 0))
        end_b = float(clip_b.get("end", 0))
        
        # Temporal overlap
        overlap = 0.0
        if not (start_a >= end_b or start_b >= end_a):
            intersection = min(end_a, end_b) - max(start_a, start_b)
            min_dur = min(end_a - start_a, end_b - start_b)
            if min_dur > 0:
                overlap = intersection / min_dur

        # Semantic similarity
        text_a = clip_a.get("text", "").lower().split()
        text_b = clip_b.get("text", "").lower().split()
        semantic_sim = 0.0
        if text_a and text_b:
            set_a, set_b = set(text_a), set(text_b)
            intersection = len(set_a.intersection(set_b))
            union = len(set_a.union(set_b))
            if union > 0:
                semantic_sim = intersection / union

        # Combine
        return 0.6 * overlap + 0.4 * semantic_sim

    indexed_shorts = list(enumerate(shorts))
    selected_indices = []
    
    # Hyperparameters for diversity and coverage
    lambda_penalty = 40.0  # Assumes score is 0-100.
    overlap_limit = 0.5    # Hard limit on overlap (50%).
    arc_quota = max(1, max_clips // 2) # Quota per story arc (e.g., max 2 arcs for 5 clips).
    selected_arcs = {}

    while len(selected_indices) < max_clips and indexed_shorts:
        best_idx = -1
        best_mmr_score = -float('inf')
        best_candidate = None
        
        for i, (orig_idx, clip) in enumerate(indexed_shorts):
            relevance = score(clip)
            
            max_sim = 0.0
            for sel_idx in selected_indices:
                sel_clip = shorts[sel_idx]
                sim = _similarity(clip, sel_clip)
                if sim > max_sim:
                    max_sim = sim
                    
            if max_sim > overlap_limit and selected_indices:
                continue
                
            arc = clip.get("arc_label")
            if arc and selected_arcs.get(arc, 0) >= arc_quota:
                continue

            selection_score = relevance - lambda_penalty * max_sim
            
            if selection_score > best_mmr_score:
                best_mmr_score = selection_score
                best_idx = i
                best_candidate = (orig_idx, clip)
                
        if best_idx == -1:
            # If all constraints fail, fall back to pure score without hard constraints
            for i, (orig_idx, clip) in enumerate(indexed_shorts):
                relevance = score(clip)
                max_sim = 0.0
                for sel_idx in selected_indices:
                    sel_clip = shorts[sel_idx]
                    sim = _similarity(clip, sel_clip)
                    if sim > max_sim:
                        max_sim = sim
                selection_score = relevance - lambda_penalty * max_sim
                if selection_score > best_mmr_score:
                    best_mmr_score = selection_score
                    best_idx = i
                    best_candidate = (orig_idx, clip)
            
        if best_candidate is None:
            break

        orig_idx, clip = best_candidate
        selected_indices.append(orig_idx)
        indexed_shorts.pop(best_idx)
        
        arc = clip.get("arc_label")
        if arc:
            selected_arcs[arc] = selected_arcs.get(arc, 0) + 1

    return [shorts[i] for i in sorted(selected_indices)]


def clip_duration_bounds():
    """The clip length band (seconds) the selection prompts and word-snapping
    enforce. ``CLIP_MIN_SECONDS`` / ``CLIP_MAX_SECONDS`` override the classic
    15-60 — set per job by /api/process when the user asks for a specific
    length, or by hand for A/B runs. Values are clamped to platform-sane
    limits and re-ordered so bad input degrades instead of breaking the job.
    """
    import os

    def _read(name, default):
        try:
            return float(os.environ.get(name, ""))
        except ValueError:
            return default

    lo = _read("CLIP_MIN_SECONDS", 60.0)
    hi = _read("CLIP_MAX_SECONDS", 120.0)
    lo = min(max(lo, 10.0), 175.0)
    hi = min(max(hi, 20.0), 180.0)
    if hi < lo + 5.0:  # keep a real band: degenerate ranges starve the model
        hi = min(180.0, lo + 5.0)
    return round(lo, 3), round(hi, 3)


def compact_words(words, precision=2):
    """Round word timestamps for prompts — full float precision wastes tokens."""
    return [
        {
            "w": w.get("w", ""),
            "s": round(float(w.get("s", 0)), precision),
            "e": round(float(w.get("e", 0)), precision),
        }
        for w in words
    ]


def build_transcript_windows(transcript_result, video_duration,
                             window_seconds=90, overlap_seconds=30):
    """
    Build scoring windows aligned to Whisper segment boundaries, so a sentence
    (and usually a viral moment) is never cut in half mid-window. Windows grow
    segment by segment to roughly window_seconds (up to 1.25x for the closing
    segment) and the next window starts ~overlap_seconds before the previous
    end, also snapped to a segment start.
    """
    segments = []
    for segment in transcript_result.get("segments", []):
        text = str(segment.get("text") or "").strip()
        if not text:
            continue
        segments.append((float(segment.get("start", 0)), float(segment.get("end", 0)), text))

    windows = []
    window_index = 1
    i = 0
    n = len(segments)
    while i < n:
        w_start = segments[i][0]
        j = i
        # Extend while the NEXT segment still fits within a tolerant cap, so the
        # window closes on a segment boundary near window_seconds.
        while j + 1 < n and segments[j + 1][1] - w_start <= window_seconds * 1.25:
            j += 1
            if segments[j][1] - w_start >= window_seconds:
                break
        w_end = segments[j][1]
        windows.append({
            "id": f"window_{window_index:03d}",
            "start": round(w_start, 3),
            "end": round(w_end, 3),
            "text": " ".join(seg[2] for seg in segments[i:j + 1]),
        })
        window_index += 1

        if j >= n - 1:
            break
        # Next window starts at the first segment beginning after (end - overlap),
        # but always makes progress.
        target = w_end - overlap_seconds
        k = i + 1
        while k <= j and segments[k][0] < target:
            k += 1
        i = max(k, i + 1)

    if not windows:
        windows.append({
            "id": "window_001",
            "start": 0.0,
            "end": round(float(video_duration), 3),
            "text": str(transcript_result.get("text", "") or ""),
        })
    return windows


def snap_clip_to_words(start, end, words, video_duration,
                       min_duration=60.0, max_duration=120.0,
                       search_window=1.5, max_lead=0.35, max_tail=0.45):
    """
    Snap Gemini-proposed clip boundaries onto real word boundaries plus a bit
    of the surrounding silence. LLMs are bad at millisecond arithmetic; the
    word-level timestamps are ground truth, so cuts land in pauses instead of
    mid-word.

    words: [{'w','s','e'}, ...] for the whole video, sorted by start.
    Returns (start, end); falls back to the input if no words are nearby or
    snapping cannot satisfy the duration bounds.
    """
    start_f = round(float(start), 3)
    end_f = round(float(end), 3)
    if start_f > end_f and end_f > 0:
        start_f, end_f = end_f, start_f

    original = (start_f, end_f)
    if not words:
        return original

    starts = [float(w.get("s", 0)) for w in words]
    ends = [float(w.get("e", 0)) for w in words]

    # START: snap to the nearest word start, then lead into the silence before it.
    new_start = start_f
    candidates = [s for s in starts if abs(s - new_start) <= search_window]
    if candidates:
        word_start = min(candidates, key=lambda s: abs(s - new_start))
        prev_ends = [e for e in ends if e <= word_start]
        if prev_ends:
            gap = max(0.0, word_start - max(prev_ends))
            lead = min(max_lead, gap / 2)
        else:
            lead = max_lead
        new_start = max(0.0, word_start - lead)

    # END: snap to the nearest word end, then trail into the silence after it.
    new_end = end_f
    candidates = [e for e in ends if abs(e - new_end) <= search_window]
    if candidates:
        word_end = min(candidates, key=lambda e: abs(e - new_end))
        next_starts = [s for s in starts if s >= word_end]
        if next_starts:
            gap = max(0.0, min(next_starts) - word_end)
            tail = min(max_tail, gap / 2)
        else:
            tail = max_tail
        new_end = min(float(video_duration), word_end + tail)

    # Repair duration bounds while staying on word boundaries.
    if new_end - new_start < min_duration:
        target = new_start + min_duration
        later = sorted(e for e in ends if e >= target)
        if later and later[0] - new_start <= max_duration:
            new_end = min(float(video_duration), later[0] + 0.2)
        else:
            return original
    if new_end - new_start > max_duration:
        target = new_start + max_duration
        earlier = [e for e in ends if new_start < e <= target]
        new_end = (max(earlier) + 0.2) if earlier else target
        new_end = min(new_end, new_start + max_duration, float(video_duration))

    if new_end <= new_start or new_end - new_start < min_duration:
        return original
    return (round(new_start, 3), round(new_end, 3))


# Characters that mark a clean sentence boundary in any Latin-script language.
_SENTENCE_ENDERS = frozenset(".!?…")


def snap_to_sentence_end(
    start: float,
    end: float,
    words: list,
    video_duration: float,
    max_duration: float = 120.0,
    look_ahead: float = 15.0,
    check_window: float = 2.0,
) -> tuple:
    """Extend a clip's end to the next sentence boundary if it is mid-thought.

    After ``snap_clip_to_words`` lands the end on a word boundary, this pass
    checks whether the last word of the clip ends a sentence.  If not, it
    scans forward up to ``look_ahead`` seconds to find the next word whose
    text ends with strong punctuation (.  !  ?  …) and moves the cut there,
    provided the resulting duration stays within ``max_duration + look_ahead``.

    Allows clips to exceed max_duration by look_ahead if it ensures a complete
    thought and supports monetization (e.g. TikTok Creator Rewards > 60s,
    YouTube Shorts up to 180s).
    """
    if not words:
        return (round(float(start), 3), round(float(end), 3))

    end_f = round(float(end), 3)
    start_f = round(float(start), 3)
    # Cap allows look_ahead so thoughts resolve cleanly
    cap = min(float(video_duration), start_f + max_duration + look_ahead)

    # 1. Check whether the current end already sits at a sentence boundary.
    #    Look at words whose end-timestamp is within check_window BEFORE the cut
    #    (strictly <= end_f so we never pick a word that starts after the cut).
    near_end_words = [
        w for w in words
        if float(w.get("e", 0)) <= end_f
        and (end_f - float(w.get("e", 0))) <= check_window
    ]
    if near_end_words:
        # The word closest to the cut from the left.
        last_word = max(near_end_words, key=lambda w: float(w.get("e", 0)))
        text = str(last_word.get("w", "")).rstrip()
        if text and text[-1] in _SENTENCE_ENDERS:
            # Already a clean cut — nothing to do.
            return (start_f, end_f)

    # 2. Scan forward for the next sentence-ending word within scan_limit.
    scan_limit = min(end_f + look_ahead, cap)
    candidates = [
        w for w in words
        if float(w.get("e", 0)) > end_f
        and float(w.get("e", 0)) <= scan_limit
        and str(w.get("w", "")).rstrip()
        and str(w.get("w", "")).rstrip()[-1] in _SENTENCE_ENDERS
    ]
    if not candidates:
        return (start_f, end_f)

    best = min(candidates, key=lambda w: float(w.get("e", 0)))
    new_end = round(min(float(best.get("e", end_f)) + 0.15, cap), 3)
    if new_end > end_f and new_end - start_f <= (max_duration + look_ahead):
        return (start_f, new_end)

    return (start_f, end_f)

def generate_multi_scale_candidates(anchors, words, video_duration, min_secs=60.0, max_secs=120.0):
    candidates = []
    c_idx = 1
    
    for a in anchors:
        a_start = float(a.get("start", 0))
        a_end = float(a.get("end", 0))
        a_type = str(a.get("anchor_type", "other")).lower()
        
        if "opinion" in a_type:
            scales = [35.0, 50.0, 65.0]
        elif "story" in a_type:
            scales = [60.0, 80.0, 100.0]
        elif "joke" in a_type or "revelation" in a_type:
            scales = [30.0, 45.0, 60.0]
        else:
            scales = [45.0, 60.0, 80.0]
            
        valid_scales = []
        for s in scales:
            if s < min_secs:
                valid_scales.append(min_secs)
            elif s > max_secs:
                valid_scales.append(max_secs)
            else:
                valid_scales.append(s)
        valid_scales = sorted(list(set(valid_scales)))
        
        for scale in valid_scales:
            shifts = [0.0]
            if scale >= 45.0:
                shifts.append(scale * 0.33)
                
            for shift in shifts:
                c_start = max(0.0, a_start - shift)
                c_end = min(video_duration, c_start + scale)
                
                cand_words = [w for w in words if w['e'] > c_start and w['s'] < c_end]
                if not cand_words:
                    continue
                    
                real_start = float(cand_words[0]['s'])
                real_end = float(cand_words[-1]['e'])
                cand_text = " ".join([w['w'] for w in cand_words])
                
                ctx_secs = 15.0
                before_words = [w for w in words if real_start - ctx_secs <= w['s'] < real_start]
                after_words = [w for w in words if real_end < w['s'] <= real_end + ctx_secs]
                
                candidates.append({
                    "id": f"c_{c_idx:03d}",
                    "anchor_id": a.get("id", "a_unk"),
                    "anchor_sentence": a.get("text", ""),
                    "start": round(real_start, 3),
                    "end": round(real_end, 3),
                    "duration": round(real_end - real_start, 3),
                    "word_count": len(cand_words),
                    "before_context": " ".join([w['w'] for w in before_words]),
                    "text": cand_text,
                    "after_context": " ".join([w['w'] for w in after_words])
                })
                c_idx += 1
                
    unique_cands = []
    for c in candidates:
        duplicate = False
        for u in unique_cands:
            if abs(c["start"] - u["start"]) < 2.0 and abs(c["end"] - u["end"]) < 2.0:
                duplicate = True
                break
        if not duplicate:
            unique_cands.append(c)
            
    return unique_cands
