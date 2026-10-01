"""Environment settings and every tunable constant. See docs/architecture.md."""

import os

from dotenv import load_dotenv

load_dotenv()

# --- Gemini -----------------------------------------------------------------
# Confirm ids with `python scripts/list_models.py --probe` (decision log #22).
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite"
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL") or "gemini-embedding-001"
EMBEDDING_DIM = 768
# One retry on rate-limit / server errors before a question becomes a system_error.
RETRY_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
RETRY_DELAY_S = 2

# --- Storage ------------------------------------------------------------------
DB_PATH = os.getenv("DB_PATH", "front_desk.db")
HANDBOOK_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "handbook.json")

# --- Retrieval ------------------------------------------------------------------
# Max chunks passed to the model; relevant() still drops any below SIMILARITY_FLOOR.
# Kept small for accuracy (less unrelated text), but 2 so two-topic questions can be answered (#20).
TOP_K = 2
# Raw cosine values for gemini-embedding-001 @ 768 dims, from scripts/calibrate_embeddings.py
# (2026-10-01: on-topic 0.663-0.778, off-topic 0.503-0.624; decision log #21). Re-run if the
# embedding model or the handbook changes substantially.
SIMILARITY_FLOOR = 0.64  # out-of-scope gate: best match below this -> escalate, no LLM calls
SEMANTIC_ZERO = 0.50  # semantic_score is 0 here (where clearly unrelated questions land)...
SIMILARITY_CEILING = 0.77  # ...and 1 here (90th percentile of on-topic questions)

# --- Confidence -------------------------------------------------------------------
SEMANTIC_WEIGHT = 0.35
ADHERENCE_WEIGHT = 0.65
CONFIDENCE_THRESHOLD = 0.80  # combined score needed to answer a non-sensitive question
FACT_TOKEN_MATCH_RATIO = 0.7

# --- Sensitivity (decision log #18, revised by #25) -------------------------------
# Sensitive = (category != "none" AND score >= SENSITIVE_CATEGORY_MIN_SCORE)
#             OR (score - 1) / 4 >= SENSITIVITY_THRESHOLD.   Sensitive always escalates.
SENSITIVITY_THRESHOLD = 0.70  # score 4-5 is sensitive whatever the category
SENSITIVE_CATEGORY_MIN_SCORE = 3  # a category tag scored 1-2 ("call her in sick") doesn't force escalation

# --- Copy -------------------------------------------------------------------------------
# Always gives the parent a next step (decision log #25). Mirrored in frontend/src/mockApi.js.
ESCALATION_MESSAGE = (
    "Thanks for your question. I've notified the Little Acorns staff about it. "
    "If it's urgent, call (555) 014-2200."
)
# Shown under a fully verified answer to a sensitive question, which still goes to staff (#37).
SENSITIVE_ANSWER_NOTE = (
    "I've also shared your question with the Little Acorns staff. If it's urgent, call (555) 014-2200."
)

# Topic categories for handbook chunks (not sensitivity categories). Mirrored in frontend/src/api.js.
KB_CATEGORIES = [
    "general",
    "calendar",
    "tuition",
    "enrollment",
    "health",
    "meals",
    "daily",
    "safety",
    "development",
    "faq",
]
