import re
import codecs

with codecs.open("backend/viral_analysis.py", "r", encoding="utf-8") as f:
    code = f.read()

# We need to replace the logic inside `get_viral_clips` after `min_clips, max_clips = clip_count_targets(...)`
# But `get_viral_clips` is complex. Let's find the start and end of the block to replace.

start_marker = "if use_single_pass:"
end_marker = "for s in shorts:\n            s_start = float(s.get(\"start\", 0))"

new_logic = """
        print("🔍 [Passo 1/4] Descobrindo âncoras...")
        chunk_windows = build_transcript_windows(transcript_result, video_duration, window_seconds=180, overlap_seconds=20)
        
        anchors = []
        def _anchor_prompt(ws):
            return gemini_worker.ANCHOR_PROMPT_TEMPLATE.format(
                language=language,
                transcript_json=json.dumps([{"start": w["start"], "end": w["end"], "text": w["text"]} for w in ws], ensure_ascii=False)
            )
            
        anchor_batch_items = [ (idx, [w]) for idx, w in enumerate(chunk_windows, 1) ]
        def _run_anchor_batch(item):
            b_idx, batch_windows = item
            local_costs = []
            batch_anchors = _run_stage_split(
                client, model_name, batch_windows, _anchor_prompt,
                gemini_worker.AnchorResponse, "anchors", local_costs, "anchor"
            )
            return b_idx, batch_anchors, local_costs

        with ThreadPoolExecutor(max_workers=min(4, len(anchor_batch_items))) as executor:
            anchor_results = list(executor.map(_run_anchor_batch, anchor_batch_items))
        for _, batch_anchors, local_costs in sorted(anchor_results, key=lambda r: r[0]):
            anchors.extend(batch_anchors)
            costs.extend(local_costs)

        print(f"🔗 Encontradas {len(anchors)} âncoras potenciais.")
        
        print("🛠️ [Passo 2/4] Gerando candidatos multi-escala...")
        from clip_selection import generate_multi_scale_candidates
        candidates = generate_multi_scale_candidates(anchors, words, video_duration, min_secs, max_secs)
        print(f"🎬 Gerados {len(candidates)} candidatos.")
        
        if not candidates:
            # Fallback to older sliding windows if anchors fail
            candidates = build_transcript_windows(transcript_result, video_duration, window_seconds=90)
            
        print("📊 [Passo 3/4] Ranking (Pointwise)...")
        def _score_prompt(ws):
            return gemini_worker.SCORE_PROMPT_TEMPLATE.format(
                video_duration=video_duration, language=language,
                windows_json=json.dumps(ws, ensure_ascii=False))
                
        SCORE_BATCH = score_batch_size()
        scored = []
        total_batches = (len(candidates) + SCORE_BATCH - 1) // SCORE_BATCH
        score_batch_items = [
            (batch_idx, candidates[b:b + SCORE_BATCH])
            for batch_idx, b in enumerate(range(0, len(candidates), SCORE_BATCH), 1)
        ]
        
        def _run_score_batch(item):
            batch_idx, batch_windows = item
            local_costs = []
            batch_scored = _run_stage_split(
                client, model_name, batch_windows, _score_prompt,
                gemini_worker.ScoreResponse, "windows", local_costs, "score")
            return batch_idx, batch_scored, local_costs
            
        if total_batches > 1:
            with ThreadPoolExecutor(max_workers=min(4, total_batches)) as executor:
                score_results = list(executor.map(_run_score_batch, score_batch_items))
            for _, batch_scored, local_costs in sorted(score_results, key=lambda r: r[0]):
                scored.extend(batch_scored)
                costs.extend(local_costs)
        else:
            for item in score_batch_items:
                _, batch_scored, local_costs = _run_score_batch(item)
                scored.extend(batch_scored)
                costs.extend(local_costs)
            
        cand_by_id = {c["id"]: c for c in candidates}
        scored_candidates = []
        for s in scored:
            if s["id"] in cand_by_id:
                cand = dict(cand_by_id[s["id"]])
                cand["predicted_score"] = s.get("score", 0)
                scored_candidates.append(cand)
                
        scored_candidates.sort(key=lambda x: x["predicted_score"], reverse=True)
        top_candidates = scored_candidates[:12] # Top 12 for pairwise
        
        print("🏆 [Passo 4/4] Pairwise Reranking (Torneio)...")
        current_pool = top_candidates
        while len(current_pool) > max_clips and len(current_pool) > 1:
            next_pool = []
            pair_items = []
            for i in range(0, len(current_pool), 2):
                if i + 1 < len(current_pool):
                    pair_items.append((current_pool[i], current_pool[i+1]))
                else:
                    next_pool.append(current_pool[i])
                    
            def _run_pair(pair):
                ca, cb = pair
                local_costs = []
                prompt = gemini_worker.PAIRWISE_PROMPT_TEMPLATE.format(
                    id_a=ca["id"], text_a=ca["text"],
                    id_b=cb["id"], text_b=cb["text"]
                )
                try:
                    parsed, cost = _run_gemini_stage(client, model_name, prompt, gemini_worker.TournamentResponse)
                    if cost: local_costs.append(cost)
                    winner_id = parsed.get("winner", {}).get("winner_id")
                    return winner_id, local_costs
                except Exception as e:
                    return ca["id"], local_costs
                    
            if pair_items:
                with ThreadPoolExecutor(max_workers=min(4, len(pair_items))) as executor:
                    pair_results = list(executor.map(_run_pair, pair_items))
                for idx, (winner_id, local_costs) in enumerate(pair_results):
                    costs.extend(local_costs)
                    ca, cb = pair_items[idx]
                    if winner_id == cb["id"]:
                        next_pool.append(cb)
                    else:
                        next_pool.append(ca)
            current_pool = next_pool
            
        shorts = current_pool[:max_clips]
        print(f"🔥 Vencedores do torneio: {len(shorts)} shorts!")
        
        print("🎯 [Passo 5/5] Extração de Detalhes e Metadados...")
        def _detail_prompt(ws):
            return gemini_worker.DETAIL_PROMPT_TEMPLATE.format(
                video_duration=video_duration, language=language,
                min_clips=len(ws), max_clips=len(ws),
                min_secs=min_secs, max_secs=max_secs,
                windows_json=json.dumps([{"id": w["id"], "start": w["start"], "end": w["end"], "text": w["text"]} for w in ws], ensure_ascii=False))
                
        local_costs = []
        detail_results = _run_stage_split(client, model_name, shorts, _detail_prompt, gemini_worker.DetailResponse, "shorts", local_costs, "detail")
        costs.extend(local_costs)
        
        det_by_id = {d.get("source_window_id"): d for d in detail_results}
        final_shorts = []
        for s in shorts:
            det = det_by_id.get(s["id"], {})
            
            # Use dictionary merge carefully so we don't overwrite ID
            merged = dict(s)
            
            # The DetailClipModel has these keys
            for k in ["predicted_score", "explanation", "reasons", "risks", "hook_type", "payoff_type", "story_type", "context_dependency"]:
                if k in det:
                    merged[k] = det[k]
                    
            # Important: Detail model might update start/end based on boundaries, let's keep them if present
            if "start" in det and "end" in det:
                merged["start"] = det["start"]
                merged["end"] = det["end"]

            final_shorts.append(merged)
            
        shorts = final_shorts

        # """

# Need to replace the whole block carefully.
import re
pattern = re.compile(r"if use_single_pass:.*?# Inject text for semantic MMR\n        for s in shorts:", re.DOTALL)

# Let's ensure it matches
if not pattern.search(code):
    print("Could not find the block to replace!")
else:
    new_code = pattern.sub(new_logic + "\n        # Inject text for semantic MMR\n        for s in shorts:", code)
    with codecs.open("backend/viral_analysis.py", "w", encoding="utf-8") as f:
        f.write(new_code)
    print("Replaced pipeline block in viral_analysis.py successfully.")

