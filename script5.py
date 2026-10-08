import codecs

with codecs.open("backend/gemini_worker.py", "r", encoding="utf-8") as f:
    code = f.read()

import re

old_prompt = """PAIRWISE_PROMPT_TEMPLATE = \"\"\"
You are a short-form video ranking expert. 
Which of these two candidate clips is more likely to retain a cold viewer and perform better on TikTok/Shorts?

Candidate A (ID: {id_a}):
{text_a}

Candidate B (ID: {id_b}):
{text_b}

Consider the hooks, the narrative momentum, and the payoff.
Return the ID of the winner ("{id_a}" or "{id_b}") and a short reason why.
Return only valid JSON.
\"\"\""""

new_prompt = """PAIRWISE_PROMPT_TEMPLATE = \"\"\"
You are a short-form video ranking expert. 
Which of these two candidate clips is more likely to retain a cold viewer and perform better on TikTok/Shorts?

Candidate A (ID: {id_a}):
Transcript: {text_a}
Prosody/Audio Features: {audio_a}

Candidate B (ID: {id_b}):
Transcript: {text_b}
Prosody/Audio Features: {audio_b}

Consider the hooks, the narrative momentum, the payoff, and the prosodic delivery (e.g. pauses, speech rate).
Return the ID of the winner ("{id_a}" or "{id_b}") and a short reason why.
Return only valid JSON.
\"\"\""""

code = code.replace(old_prompt, new_prompt)

# update main script logic in gemini_worker
code = code.replace('fmt["text_b"] = payload["text_b"]',
                    'fmt["text_b"] = payload["text_b"]\n        fmt["audio_a"] = json.dumps(payload.get("audio_a", {}))\n        fmt["audio_b"] = json.dumps(payload.get("audio_b", {}))')

with codecs.open("backend/gemini_worker.py", "w", encoding="utf-8") as f:
    f.write(code)
print("Updated gemini_worker.py for P2 audio in pairwise.")
