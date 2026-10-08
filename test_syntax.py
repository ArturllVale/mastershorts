import sys
import traceback
import os
sys.path.insert(0, os.path.abspath('backend'))
try:
    import clip_selection
    import gemini_worker
    print("Syntax OK")
except Exception as e:
    traceback.print_exc()
    sys.exit(1)
