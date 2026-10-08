import codecs
with codecs.open("backend/viral_analysis.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "if use_single_pass:" in line:
        print(f"Start at line {i}")
    if "# Inject text for semantic MMR" in line:
        print(f"End at line {i}")
