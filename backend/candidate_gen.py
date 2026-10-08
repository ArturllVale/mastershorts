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
