with open("backend/gemini_worker.py", "r", encoding="utf-8") as f:
    code = f.read()

# Replace SCORE_PROMPT_TEMPLATE
old_score_prompt_start = 'SCORE_PROMPT_TEMPLATE = """'
old_score_prompt_end = 'DETAIL_PROMPT_TEMPLATE = """'

new_score_prompt = '''SCORE_PROMPT_TEMPLATE = """
You are a short-form video ranking specialist.

Your task is to rank candidate moments by their probability of holding
a cold viewer's attention.

Do NOT write titles, hooks, captions, descriptions, or creative copy.

Evaluate the CONTENT ONLY. 
Each candidate window contains the `text` of the clip, as well as `before_context` and `after_context` to help you understand the full picture.

For every candidate, consider:

1. Immediate Appeal
2. Curiosity/Tension
3. Payoff
4. Information Density
5. Standalone Clarity
6. Narrative Momentum
7. Emotional / Social Value
8. Editability
9. Setup Cost
10. Weak Ending Risk

IMPORTANT:
Judge the expected viewing experience as a whole.
A 70-second story can beat a 25-second statement.
A 20-second statement can beat a 70-second story.

Return a calibrated score for every candidate.

TRANSCRIPT_LANGUAGE: {language}
VIDEO_DURATION_SECONDS: {video_duration}
CANDIDATES_JSON:
{windows_json}

Return only:
{{
  "windows": [
    {{
      "id": "<window id>",
      "start": <number>,
      "end": <number>,
      "score": <integer 0-100>
    }}
  ]
}}
"""
'''

import re
code = re.sub(r'SCORE_PROMPT_TEMPLATE = """(.*?)DETAIL_PROMPT_TEMPLATE = """', 
              new_score_prompt + '\nDETAIL_PROMPT_TEMPLATE = """', 
              code, flags=re.DOTALL)

# Add handling in `_config_for_strategy` for anchor and tournament
code = code.replace('kwargs["response_schema"] = DetailResponse if mode == "detail" else ScoreResponse',
'''if mode == "detail":
            kwargs["response_schema"] = DetailResponse
        elif mode == "score":
            kwargs["response_schema"] = ScoreResponse
        elif mode == "anchor":
            kwargs["response_schema"] = AnchorResponse
        elif mode == "tournament":
            kwargs["response_schema"] = TournamentResponse''')

code = code.replace('parser.add_argument("--mode", choices=["score", "detail"], required=True)',
                    'parser.add_argument("--mode", choices=["score", "detail", "anchor", "tournament"], required=True)')

code = code.replace('template = SCORE_PROMPT_TEMPLATE if args.mode == "score" else DETAIL_PROMPT_TEMPLATE',
'''if args.mode == "score":
        template = SCORE_PROMPT_TEMPLATE
    elif args.mode == "anchor":
        template = ANCHOR_PROMPT_TEMPLATE
    elif args.mode == "tournament":
        template = PAIRWISE_PROMPT_TEMPLATE
    else:
        template = DETAIL_PROMPT_TEMPLATE''')

# In gemini_worker main args, formatting could change
# We need to inject variables correctly for tournament and anchor
main_fmt_logic = '''
    fmt = {
        "video_duration": payload.get("video_duration", 0),
        "language": language,
    }
    if args.mode == "anchor":
        fmt["transcript_json"] = json.dumps(payload.get("transcript", []), ensure_ascii=False)
    elif args.mode == "tournament":
        fmt["id_a"] = payload["id_a"]
        fmt["text_a"] = payload["text_a"]
        fmt["id_b"] = payload["id_b"]
        fmt["text_b"] = payload["text_b"]
    else:
        fmt["windows_json"] = json.dumps(payload.get("windows", []), ensure_ascii=False)

    if args.mode == "detail":
        fmt["min_clips"], fmt["max_clips"] = clip_count_targets(len(payload.get("windows") or []))
        fmt["min_secs"], fmt["max_secs"] = clip_duration_bounds()
'''

code = re.sub(r'fmt = \{.*?max_secs\] = clip_duration_bounds\(\)\n', main_fmt_logic, code, flags=re.DOTALL)

with open("backend/gemini_worker.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Updated gemini_worker.py for modes")
