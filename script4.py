import codecs

with codecs.open("backend/clip_selection.py", "r", encoding="utf-8") as f:
    code = f.read()

import re

# We want to add audio_features to the candidates generated in `generate_multi_scale_candidates`
new_logic = """                ctx_secs = 15.0
                before_words = [w for w in words if real_start - ctx_secs <= float(w.get('s', 0)) < real_start]
                after_words = [w for w in words if real_end < float(w.get('s', 0)) <= real_end + ctx_secs]
                
                # --- P2 AUDIO/PROSODY FEATURES ---
                pause_before = round(real_start - float(before_words[-1].get('e', real_start)), 3) if before_words else 0.5
                pause_after = round(float(after_words[0].get('s', real_end)) - real_end, 3) if after_words else 0.5
                
                # Speech density & internal pauses
                speech_time = sum([float(w.get('e', 0)) - float(w.get('s', 0)) for w in cand_words])
                cand_duration = real_end - real_start
                speech_density = round(speech_time / cand_duration, 2) if cand_duration > 0 else 0.0
                
                max_internal_pause = 0.0
                for i in range(len(cand_words)-1):
                    gap = float(cand_words[i+1].get('s', 0)) - float(cand_words[i].get('e', 0))
                    if gap > max_internal_pause:
                        max_internal_pause = gap
                        
                speech_rate = round(len(cand_words) / cand_duration, 2) if cand_duration > 0 else 0.0

                audio_features = {
                    "speech_rate": speech_rate,
                    "speech_density": speech_density,
                    "pause_before": pause_before,
                    "pause_after": pause_after,
                    "max_internal_pause": round(max_internal_pause, 3)
                }
                
                candidates.append({
                    "id": f"c_{c_idx:03d}",
                    "anchor_id": a.get("id", "a_unk"),
                    "anchor_sentence": a.get("text", ""),
                    "start": round(real_start, 3),
                    "end": round(real_end, 3),
                    "duration": round(real_end - real_start, 3),
                    "word_count": len(cand_words),
                    "before_context": " ".join([w.get('w', '') for w in before_words]),
                    "text": cand_text,
                    "after_context": " ".join([w.get('w', '') for w in after_words]),
                    "audio_features": audio_features
                })"""

# replace in code
old_logic = r"""                ctx_secs = 15.0
                before_words = \[w for w in words if real_start - ctx_secs <= w\['s'\] < real_start\]
                after_words = \[w for w in words if real_end < w\['s'\] <= real_end \+ ctx_secs\]
                
                candidates.append\(\{
                    "id": f"c_\{c_idx:03d\}",
                    "anchor_id": a\.get\("id", "a_unk"\),
                    "anchor_sentence": a\.get\("text", ""\),
                    "start": round\(real_start, 3\),
                    "end": round\(real_end, 3\),
                    "duration": round\(real_end - real_start, 3\),
                    "word_count": len\(cand_words\),
                    "before_context": " "\.join\(\[w\['w'\] for w in before_words\]\),
                    "text": cand_text,
                    "after_context": " "\.join\(\[w\['w'\] for w in after_words\]\)
                \}\)"""

code = re.sub(old_logic, new_logic, code)

with codecs.open("backend/clip_selection.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Updated clip_selection.py with P2 audio features.")
