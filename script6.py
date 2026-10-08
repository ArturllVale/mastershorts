import codecs
import json

with codecs.open("backend/viral_analysis.py", "r", encoding="utf-8") as f:
    code = f.read()

import re

old_call = """                prompt = gemini_worker.PAIRWISE_PROMPT_TEMPLATE.format(
                    id_a=ca["id"], text_a=ca["text"],
                    id_b=cb["id"], text_b=cb["text"]
                )"""

new_call = """                prompt = gemini_worker.PAIRWISE_PROMPT_TEMPLATE.format(
                    id_a=ca["id"], text_a=ca["text"],
                    id_b=cb["id"], text_b=cb["text"],
                    audio_a=json.dumps(ca.get("audio_features", {})),
                    audio_b=json.dumps(cb.get("audio_features", {}))
                )"""

code = code.replace(old_call, new_call)

with codecs.open("backend/viral_analysis.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Updated viral_analysis.py to pass audio features.")
