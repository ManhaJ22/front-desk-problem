"""List the Gemini models this API key can see, and optionally probe the configured ones.

Run: python scripts/list_models.py           # list only
     python scripts/list_models.py --probe   # also make one tiny call to each configured model

Being LISTED does not mean USABLE (decision log #22): gemini-2.5-flash is listed but
returns 404 for new keys, and gemini-embedding-2 merges a batch into one vector.
--probe checks that the configured generate model returns structured output and that
the configured embedding model returns one vector per input.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google import genai  # noqa: E402

from backend import config, gemini  # noqa: E402
from backend.schemas import SensitivityResult  # noqa: E402

if not config.GEMINI_API_KEY:
    sys.exit("GEMINI_API_KEY is not set (.env)")

client = genai.Client(api_key=config.GEMINI_API_KEY)
configured = {config.GEMINI_MODEL, config.GEMINI_EMBEDDING_MODEL}

rows = []
for m in client.models.list():
    actions = set(m.supported_actions or [])
    if "generateContent" in actions or "embedContent" in actions:
        short = m.name.removeprefix("models/")
        kind = "embed" if "embedContent" in actions else "generate"
        rows.append((kind, short, "  <-- configured" if short in configured else ""))

for kind, name, mark in sorted(rows):
    print(f"{kind:9} {name}{mark}")

missing = configured - {name for _, name, _ in rows}
if missing:
    sys.exit(f"\nNOT LISTED for this key: {', '.join(sorted(missing))}")

if "--probe" in sys.argv:
    print("\nProbing configured models (2 small calls)...")
    ok = True
    try:
        vectors = gemini.embed(["hello", "world"], "RETRIEVAL_QUERY")
        print(f"  OK   {config.GEMINI_EMBEDDING_MODEL}: {len(vectors)} vectors x {len(vectors[0])} dims")
    except gemini.GeminiError as e:
        ok = False
        print(f"  FAIL {config.GEMINI_EMBEDDING_MODEL}: {e}")
    try:
        r = gemini.generate_structured("Parent's question:\nAre you open today?", "Classify sensitivity.", SensitivityResult)
        print(f"  OK   {config.GEMINI_MODEL}: {r.category.value}, score {r.score}")
    except gemini.GeminiError as e:
        ok = False
        print(f"  FAIL {config.GEMINI_MODEL}: {e}")
    sys.exit(0 if ok else 1)
