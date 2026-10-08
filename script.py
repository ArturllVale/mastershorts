import json
import re

with open("backend/gemini_worker.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Add schemas
schemas = """
class AnchorModel(BaseModel):
    id: str
    start: float
    end: float
    text: str
    anchor_type: str

class AnchorResponse(BaseModel):
    anchors: List[AnchorModel]

class TournamentWinnerModel(BaseModel):
    winner_id: str
    reason: str

class TournamentResponse(BaseModel):
    winner: TournamentWinnerModel
"""
if "AnchorModel" not in code:
    code = code.replace("class ScoredWindowModel(BaseModel):", schemas + "\nclass ScoredWindowModel(BaseModel):")

# 2. Add prompts
prompts = """
ANCHOR_PROMPT_TEMPLATE = \"\"\"
You are a short-form video expert. Your task is to find "Anchors" in this transcript chunk.
An Anchor is a specific sentence or event that is the perfect starting point or center of a short-form clip.

Examples of good anchors:
- "I lost $80,000." (revelation/hook)
- "I think most people are completely wrong about this." (strong opinion)
- "I was running my company..." (start of a story)
- "Nobody told me this." (curiosity gap)

Identify the best anchors in this transcript. 
For each, return an id (e.g. "a_01"), the exact start and end timestamps, the text, and classify the anchor_type as "opinion", "story", "revelation", "joke", or "other".

TRANSCRIPT_LANGUAGE: {language}
TRANSCRIPT_JSON:
{transcript_json}

Return only valid JSON.
\"\"\"

PAIRWISE_PROMPT_TEMPLATE = \"\"\"
You are a short-form video ranking expert. 
Which of these two candidate clips is more likely to retain a cold viewer and perform better on TikTok/Shorts?

Candidate A (ID: {id_a}):
{text_a}

Candidate B (ID: {id_b}):
{text_b}

Consider the hooks, the narrative momentum, and the payoff.
Return the ID of the winner ("{id_a}" or "{id_b}") and a short reason why.
Return only valid JSON.
\"\"\"
"""
if "ANCHOR_PROMPT_TEMPLATE" not in code:
    code = code.replace("VISUAL_PROMPT_TEMPLATE = ", prompts + "\nVISUAL_PROMPT_TEMPLATE = ")

with open("backend/gemini_worker.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Updated gemini_worker.py schemas and templates")
