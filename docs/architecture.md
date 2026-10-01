# Architecture — Little Acorns AI Front Desk

The file structure and what each file contains. `docs/CLAUDE.md` is the
spec; this file is how the spec maps onto code. Nothing outside this
tree gets created without updating this file first.

---

## Calls to review (I picked a default for each; flag any you disagree with)

These are the places where the spec left room for interpretation. Each
one has a default in the sections below.

| # | Question | Default chosen |
|---|---|---|
| A | The CLAUDE.md schema has no column for urgency or escalation reason, but triage needs both | **Approved 2026-10-01**: added `is_urgent`, `escalation_reason` (and `sensitivity_rationale`) to `question_log`; CLAUDE.md updated (decision #14) |
| B | Out-of-scope questions and the sensitivity call | **Revised (#38):** out-of-scope questions ARE classified for sensitivity (one call); only generation is skipped. A failed classification leaves them out-of-scope, not system_error |
| C | The model returns zero `claimed_facts` | `adherence_score = 0.0` → always escalates. If the model makes no checkable claim, we can't verify the answer |
| D | What `sensitivity_score` (1–5) is used for | **Revised (#18, #25):** `is_sensitive` = (`category != "none"` **and** `score ≥ 3`) **or** `(score − 1)/4 ≥ 0.70`. Sensitive always escalates; no separate 0.90 bar |
| E | Gemini errors out (429 quota, timeout) | Escalate with `escalation_reason = "system_error"` and log the row. The parent sees the normal "staff notified" message |
| F | Generation still runs for force-escalated (sensitive) questions | Yes. CLAUDE.md says the would-have-been answer is logged for the operator. Only out-of-scope questions skip it |
| G | Frontend language and styling | JavaScript (JSX), not TypeScript; plain CSS, no UI library |
| H | Embedding size | 768 dimensions (`output_dimensionality=768`). Plenty for about 20 chunks, and smaller rows |
| I | Similarity floor and ceiling before calibration | **Done 2026-10-01 (#21):** floor 0.64, semantic zero 0.50, ceiling 0.77 for `gemini-embedding-001` @ 768 |
| J | Operator routes on a public URL | No auth (CLAUDE.md lists this as out of scope). Anyone with the URL can edit the KB in the demo |
| K | What a parent sees on an answered question | The answer, plus "From the handbook: <title>" for each chunk that backed at least one matched fact |
| L | Exact escalation wording | **Revised (#25):** "Thanks for your question. I've notified the Little Acorns staff about it. If it's urgent, call (555) 014-2200." Still promises no reply (there is no reply channel), but always gives a next step |
| M | "Add to KB" from a question | Always creates a **new** chunk. Existing chunks are edited in the Knowledge Base tab |
| N | Adding a KB answer for a sensitive question (fever, custody…) | **Revised (#28):** staff-written answers win — the question is answered next time if every fact is verified against staff-written entries. The editor note says so |

---

## File tree

```
front-desk-problem/
├── CLAUDE.md                     # one line: @docs/CLAUDE.md
├── .env.example                  # GEMINI_API_KEY, GEMINI_MODEL, GEMINI_EMBEDDING_MODEL
├── .gitignore
├── requirements.txt
├── pytest.ini                    # pythonpath = . so `pytest tests/` can import backend
├── render.yaml                   # Render Blueprint: one paid Python web service + persistent disk (#24, #27)
├── .python-version               # 3.14, so Render matches local
├── data/
│   └── handbook.json             # mock handbook, seed for handbook_chunks
├── backend/
│   ├── __init__.py
│   ├── main.py                   # FastAPI app, startup, static frontend
│   ├── config.py                 # env vars + every tunable constant
│   ├── db.py                     # SQLite schema + query helpers
│   ├── schemas.py                # Pydantic models (LLM outputs + API I/O)
│   ├── gemini.py                 # the ONLY module that talks to Gemini
│   ├── seed.py                   # load handbook.json → embed → insert
│   ├── kb.py                     # chunk create/update/delete + re-embed
│   ├── retrieval.py              # embed query, cosine, top-k, semantic score
│   ├── sensitivity.py            # classify call + is_sensitive rule
│   ├── generation.py             # answer + claimed_facts call
│   ├── adherence.py              # mechanical token-overlap check
│   ├── urgency.py                # static keyword detection
│   ├── triage.py                 # priority ordering for the operator queue
│   ├── pipeline.py               # orchestrates steps 1–8, logs
│   └── routes/
│       ├── __init__.py
│       ├── ask.py                # parent endpoint
│       └── operator.py           # operator endpoints
├── scripts/
│   ├── list_models.py
│   └── calibrate_embeddings.py
├── tests/
│   ├── conftest.py
│   ├── test_adherence.py
│   ├── test_urgency.py
│   ├── test_triage.py
│   ├── test_kb.py
│   ├── test_sensitivity.py
│   ├── test_retrieval.py
│   ├── test_generation.py
│   ├── test_pipeline.py
│   └── test_api.py
├── frontend/
│   ├── .env.mock                 # VITE_USE_MOCKS=true, loaded only by `npm run dev:mock`
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api.js
│       ├── mockApi.js            # dev-only fake backend (VITE_USE_MOCKS=true)
│       ├── display.js            # shared labels (reasons, categories) + formatters
│       ├── styles.css
│       ├── pages/
│       │   ├── ParentChat.jsx
│       │   └── OperatorDashboard.jsx
│       └── components/
│           ├── ChatMessage.jsx
│           ├── SuggestedQuestions.jsx
│           ├── StatsBar.jsx
│           ├── QuestionQueue.jsx
│           ├── QuestionDetail.jsx
│           ├── KnowledgeBase.jsx
│           └── ChunkEditor.jsx
└── docs/
    ├── CLAUDE.md
    ├── architecture.md           # this file
    ├── decision-log.md
    └── plans/
        ├── backend-plan.md
        └── frontend-plan.md
```

---

## Backend (`backend/`)

Stack: FastAPI, the standard-library `sqlite3` (no ORM), `google-genai`,
`python-dotenv`. Cosine similarity is written in plain Python (no numpy):
about 20 vectors × 768 dimensions is trivial.

### `config.py`
Reads `.env` once with `load_dotenv()`. Every number that changes behavior lives here.

| Name | Value | Notes |
|---|---|---|
| `GEMINI_API_KEY` | env | required at startup; the app fails fast if it's missing |
| `GEMINI_MODEL` | env, default `gemini-3.5-flash-lite` | confirm with `list_models.py --probe` (#22) |
| `GEMINI_EMBEDDING_MODEL` | env, default `gemini-embedding-001` | |
| `EMBEDDING_DIM` | `768` | (H) |
| `RETRY_STATUS_CODES` / `RETRY_DELAY_S` | `{429, 500, 502, 503, 504}` / `2` | one retry before `system_error` (backend-plan default) |
| `DB_PATH` | env, default `front_desk.db` | tests override it |
| `TOP_K` | `2` | max chunks given to the model, after which `relevant()` still applies the floor (decision #20) |
| `SIMILARITY_FLOOR` | `0.64` (calibrated) | raw cosine; best match below it → out of scope, no LLM calls (#21) |
| `SEMANTIC_ZERO` | `0.50` (calibrated) | raw cosine where `semantic_score` = 0; deliberately below the floor (#21) |
| `SIMILARITY_CEILING` | `0.77` (calibrated) | raw cosine that maps to `semantic_score` 1.0 (#21) |
| `SEMANTIC_WEIGHT` / `ADHERENCE_WEIGHT` | `0.35` / `0.65` | |
| `CONFIDENCE_THRESHOLD` | `0.80` | combined score needed to answer a non-sensitive question |
| `SENSITIVITY_THRESHOLD` | `0.70` | normalized sensitivity score at/above which a question is sensitive, any category (#18) |
| `SENSITIVE_CATEGORY_MIN_SCORE` | `3` | a non-`none` category counts as sensitive only at this raw score or above (#25) |
| `FACT_TOKEN_MATCH_RATIO` | `0.7` | see adherence |
| `ESCALATION_MESSAGE` | text from (L) | shown when no answer is shown |
| `SENSITIVE_ANSWER_NOTE` | "I've also shared your question with the Little Acorns staff. If it's urgent, call (555) 014-2200." | shown under a verified answer to a sensitive question (#37) |
| `KB_CATEGORIES` | `general, calendar, tuition, enrollment, health, meals, daily, safety, development, faq` | topic categories for chunks (not the same thing as sensitivity categories) |

### `db.py`
- `get_conn()` → a `sqlite3.Connection` with `row_factory = sqlite3.Row`. A new connection per call.
- `init_db()` → runs `CREATE TABLE IF NOT EXISTS`:

```sql
handbook_chunks(
  id TEXT PRIMARY KEY,           -- slug, e.g. "illness-exclusion"
  category TEXT NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'handbook',  -- 'handbook' (seeded) | 'staff' (dashboard create/edit) #28
  embedding TEXT NOT NULL,       -- JSON list[float]
  updated_at TEXT NOT NULL       -- ISO-8601 UTC
)
question_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  question TEXT NOT NULL,
  answer TEXT,                   -- generated answer (shown OR would-have-been); NULL if out_of_scope/system_error
  escalated INTEGER NOT NULL,    -- 0/1
  escalation_reason TEXT,        -- (A) out_of_scope | sensitive_forced | below_threshold | system_error | NULL
  is_sensitive INTEGER NOT NULL DEFAULT 0,
  is_urgent INTEGER NOT NULL DEFAULT 0,   -- (A)
  sensitivity_category TEXT,     -- NULL when classification didn't run
  sensitivity_score INTEGER,
  sensitivity_rationale TEXT,
  semantic_score REAL,
  adherence_score REAL,
  combined_score REAL,
  threshold_used REAL,
  retrieved_chunk_ids TEXT,      -- JSON list[str]
  claimed_facts TEXT,            -- JSON list[str]
  unmatched_facts TEXT,          -- JSON list[str]
  answer_shown INTEGER NOT NULL DEFAULT 0,  -- parent saw the generated answer (#37)
  resolved INTEGER NOT NULL DEFAULT 0
)
```
- Helper functions only (no business logic): `list_chunks()`, `get_chunk(id)`, `upsert_chunk(..., source)`, `delete_chunk(id)`, `count_chunks()`; `init_db()` also adds the `source` column to pre-#28 databases, `insert_log(dict) -> id`, `list_logs()`, `get_log(id)`, `mark_resolved(id)`.

### `schemas.py`
LLM output models (passed as `response_schema`):
- `SensitivityCategory(str, Enum)`: `health, safety, allergies, custody_legal, emotional_social, none`
- `SensitivityResult`: `category: SensitivityCategory`, `score: int` (1–5), `rationale: str`
- `GeneratedAnswer`: `answer: str`, `claimed_facts: list[str]`

API models: `AskRequest`, `AskResponse`, `Source`, `ChunkIn`, `ChunkOut`, `QuestionOut`, `AddToKbRequest`, `Stats` (fields under **API contract**).

### `gemini.py`
The only module that imports `google.genai`. Tests mock these two functions.
- `embed(texts: list[str], task_type: str) -> list[list[float]]`: one batched `embed_content` call; `task_type` is `"RETRIEVAL_DOCUMENT"` for chunks and `"RETRIEVAL_QUERY"` for questions; `output_dimensionality=EMBEDDING_DIM`.
- `generate_structured(prompt: str, system_instruction: str, schema: type[BaseModel]) -> BaseModel`: `generate_content` with `config={"response_mime_type": "application/json", "response_schema": schema, "temperature": 0, "system_instruction": ...}`, and returns `response.parsed`. Raises `GeminiError` if `parsed` is None. **Never** parses `response.text`.

### `seed.py`
- `seed_if_empty()`: if `count_chunks() == 0`, load `data/handbook.json`, embed all chunks in one call (text = `title + "\n\n" + content`), insert. Called at startup. On the Render free tier this runs on every cold boot (decision #11).

### `kb.py`
- `create_chunk(category, title, content) -> ChunkOut`: `source = staff` (#28); id = slugified title, with `-2`, `-3`… added on collision; embeds, then inserts.
- `update_chunk(id, category, title, content) -> ChunkOut`: re-embeds, updates `updated_at`, and sets `source = staff` (editing a seeded entry is a staff judgement, #28).
- `delete_chunk(id)`.
- Embedding text is always `title + "\n\n" + content` (same as seed).

### `retrieval.py`
- `cosine(a, b) -> float`
- `retrieve(question) -> list[RetrievedChunk]`: embeds the question, scores every chunk, returns the top `TOP_K` sorted descending. `RetrievedChunk = (id, title, content, cosine)`.
- `semantic_score(top_cosine) -> float` = `clamp((top − SEMANTIC_ZERO) / (CEILING − SEMANTIC_ZERO), 0, 1)`. Not anchored at the floor (#21).
- `is_out_of_scope(hits) -> bool` = no hits, or `hits[0].cosine < SIMILARITY_FLOOR`.
- `relevant(hits) -> list[RetrievedChunk]` = hits with cosine ≥ floor. The pipeline calls this once and passes the result to **both** generation and the adherence check, so facts are checked against exactly the excerpts the model saw.

### `sensitivity.py`
- `classify(question) -> SensitivityResult`: **question only** (no chunks) goes to the model. The system instruction defines each category with one example.
- `normalized(score) -> float` = `(score - 1) / 4` (1→0.0, 4→0.75, 5→1.0).
- `is_sensitive(result) -> bool` = `(result.category != "none" and result.score >= SENSITIVE_CATEGORY_MIN_SCORE) or normalized(result.score) >= SENSITIVITY_THRESHOLD` (decisions #18, #25). The system instruction categorizes by what the parent needs (a person's judgement about a child) rather than by topic mentioned. The raw 1–5 score is stored as the model returned it.

### `generation.py`
- `generate(question, chunks) -> GeneratedAnswer`. Receives the already-filtered `relevant(hits)`; each excerpt is labelled with its title. System instruction:
  - answer only from the excerpts; warm, short (2–4 sentences), plain language for a parent;
  - if the excerpts don't answer the question, say so and return `claimed_facts: []`;
  - list **every** specific claim (time, $ amount, age, temperature, phone number, named policy) as a short string worded as close to the source as possible;
  - write every number in digits exactly as the handbook does (`$6`, `10:00 AM`), never spelled out, so the answer-number check can see it (#23).

### `adherence.py` (mechanical, no LLM)
- `tokenize(text) -> list[str]`:
  - lowercase; regex `\d+(?:[.:,]\d+)*|[a-z]+`;
  - numbers: remove thousands commas (`2,150`→`2150`) and `:00` (`7:00`→`7`);
  - words: drop a fixed stopword list; drop a trailing `s` on words longer than 3 letters.
- `is_numeric(token)`: token starts with a digit.
- `fact_matches(fact, chunk_text) -> bool`: true if, **within a single chunk**, ≥ `FACT_TOKEN_MATCH_RATIO` of the fact's tokens appear **and every numeric token** appears. A fact whose words match but whose numbers differ ("$1,850" vs "$1,950") fails.
- `unsupported_numbers(answer, chunks) -> list[str]`: numeric tokens in the **answer text** that appear in none of the chunks (title + content), de-duplicated in order. Catches numbers the model wrote but didn't list as a claim (#23).
- `check(facts, chunks, answer="") -> AdherenceResult(score, matched: list[(fact, chunk_id)], unmatched: list[str])`. Each unsupported answer number is added to `unmatched` as `Answer says "<n>", which isn't in the handbook` and counts as a failed fact: `score = len(matched) / (len(facts) + len(unsupported_numbers))`. Zero facts → `0.0` (C).

### `urgency.py`
- `URGENT_PHRASES` (case-insensitive, whole-word/phrase): `today, tonight, right now, asap, urgent, emergency, this morning, this afternoon, pick up early, pickup early, picking up early, early pickup, running late, on my way, immediately`.
- `is_urgent(question) -> bool`. Static: no date parsing (decision #5).

### `triage.py`
- `priority(is_sensitive, is_urgent) -> int`: 1 = sensitive+urgent, 2 = urgent, 3 = sensitive, 4 = neither.
- `sort_queue(rows)`: unresolved before resolved, then `priority` ascending, then `combined_score` ascending (weakest first, NULL first), then newest first.

### `pipeline.py`
`answer_question(question) -> AskResponse`:

```
urgent = is_urgent(q)
try:
  hits = retrieve(q)
  if is_out_of_scope(hits):            → classify sensitivity (failure tolerated), escalate("out_of_scope"); no generation (#38)
  sens = classify(q)
  sensitive = is_sensitive(sens)        # category ≠ none OR normalized score ≥ 0.70 (D, #18)
  gen = generate(q, hits)               # runs even if sensitive (F)
  adh = check(gen.claimed_facts, hits)
  sem = semantic_score(hits[0].cosine)
  combined = 0.35*sem + 0.65*adh.score
  staff_backed = every claimed fact matched, every match in a source='staff' chunk, no bad numbers  (#28)
  if sensitive and not (staff_backed and combined >= 0.80): escalate("sensitive_forced")
  elif combined < 0.80:        escalate("below_threshold")
  else:                        answer
except GeminiError / API error:          escalate("system_error")  (E)
always: insert_log(...)
```
Returns: answered → `answer` + `sources` (chunks that backed a matched fact, K); escalated **only for sensitivity** with a fully verified answer (no unmatched facts/numbers, combined ≥ 0.80) → `answer` + `sources` + `message = SENSITIVE_ANSWER_NOTE`, logged `answer_shown = true` (#37); any other escalation → `answer = null`, `message = ESCALATION_MESSAGE`, `sources = []`.

### `routes/ask.py`, `routes/operator.py`, `main.py`
- Routers mounted under `/api`.
- `main.py`: on startup, `init_db()` then `seed_if_empty()`. If `frontend/dist` exists, serve `/assets/*` as static files and send any other non-`/api` GET to `index.html` (so client-side routes like `/operator` work). In dev, `dist` is absent and Vite serves the frontend.

### API contract

| Method & path | Request | Response |
|---|---|---|
| `GET /api/health` | — | `{"ok": true, "db_path": "<absolute path>"}` (confirms the DB is on the persistent disk, #27) |
| `POST /api/ask` | `{question: str}` (1–500 chars, trimmed) | `{log_id, escalated, answer: str\|null, message: str\|null, sources: [{id, title}]}`. Three shapes: answered (`answer`, no `message`); escalated with verified answer (`answer` + `sources` + `message` = staff note, #37); escalated (`message` only) |
| `GET /api/operator/questions?view=needs_review\|all` | default `needs_review` = escalated and unresolved | `[QuestionOut]`: every `question_log` column (JSON fields decoded) + `priority`, sorted by `triage.sort_queue` |
| `POST /api/operator/questions/{id}/resolve` | — | `QuestionOut` |
| `POST /api/operator/questions/{id}/add-to-kb` | `{category, title, content}` | `{chunk: ChunkOut, question: QuestionOut}` (also marks it resolved) |
| `GET /api/operator/kb` | — | `[ChunkOut]` = `{id, category, title, content, source, updated_at}` (no embedding) |
| `POST /api/operator/kb` | `{category, title, content}` | `ChunkOut` |
| `PUT /api/operator/kb/{id}` | `{category, title, content}` | `ChunkOut` |
| `DELETE /api/operator/kb/{id}` | — | `204` |
| `GET /api/operator/stats` | — | `{total, answered, escalated, unresolved, by_reason: {out_of_scope, sensitive_forced, below_threshold, system_error}}` |

---

## Scripts (`scripts/`)
- `list_models.py`: prints every model the key can see, marking generate vs embed. `--probe` makes one tiny call to each configured model, because listed ≠ usable (#22).
- `calibrate_embeddings.py`: embeds `handbook.json` directly (no DB needed) plus two hardcoded lists, about 15 on-topic and about 10 off-topic questions. Prints the top cosine for each question, then suggests `SIMILARITY_FLOOR` (the midpoint between the highest off-topic and the lowest on-topic score; warns if the two ranges overlap) and `SIMILARITY_CEILING` (90th percentile of on-topic scores). It only prints; a human copies the values into `config.py`.

## Tests (`tests/`)
No test calls Gemini; `backend.gemini.embed` and `generate_structured` are monkeypatched with fakes.
- `conftest.py`: temporary `DB_PATH`, fake embedder (deterministic bag-of-words vectors so retrieval behaves sensibly), fake generator fixtures.
- `test_adherence.py`: exact match, paraphrase, number mismatch fails, a fact stitched together from two chunks fails, zero facts → 0, number normalization (`7:00 AM` vs `7 AM`, `$2,150` vs `2150`); answer-number check: an unlisted number in the answer that's missing from the sources is unmatched and lowers the score, a number present in any chunk passes, spelled-out words aren't treated as numbers.
- `test_urgency.py`: each phrase triggers; near-misses don't trigger (e.g. "nowhere" doesn't match "now").
- `test_triage.py`: priority order 1–4 and the full sort order.
- `test_kb.py`: data layer: `init_db` is idempotent; `seed_if_empty` seeds every handbook chunk in one `RETRIEVAL_DOCUMENT` embed call and is a no-op the second time; `create_chunk` slugs titles and de-duplicates ids; `update_chunk` re-embeds and bumps `updated_at`; delete; chunk listings never expose embeddings; `insert_log`/`list_logs` round-trip JSON + booleans and filter `needs_review`; `mark_resolved`.
- `test_sensitivity.py`: `normalized()` maps 1→0.0 … 5→1.0; `is_sensitive()`: a non-`none` category is sensitive at score ≥ 3 but not at 1–2; any category is sensitive at score ≥ 4 (the 0.70 boundary); `classify()` passes the schema and question-only prompt to `generate_structured` (mocked).
- `test_retrieval.py`: `cosine()` basics; `retrieve()` returns top-`TOP_K` by cosine (embedder mocked); `semantic_score()` clamps at floor/ceiling; `is_out_of_scope()` boundary and empty KB; `relevant()` filters at the floor.
- `test_generation.py`: the prompt contains the question and every excerpt labelled by title; the call uses the `GeneratedAnswer` schema and the grounding rules in the system instruction (generator mocked).
- `test_pipeline.py` (orchestration, with the component modules' Gemini calls mocked): out-of-scope makes exactly one LLM call (classification, never generation) and records sensitivity; a classification failure on an out-of-scope question stays `out_of_scope`; sensitive questions escalate even at confidence 1.0; a category tag with score 2 (e.g. calling in sick) is answered if grounded; `threshold_used` is 0.80 on classified rows; below threshold escalates; a Gemini error escalates as `system_error`; every path writes a log row.
- `test_api.py`: request/response shapes for every endpoint; add-to-kb creates a chunk and resolves the question.

---

## Frontend (`frontend/`)
React 19 + Vite, `react-router-dom`, plain CSS (G). No state library; no data is kept in browser storage.
Detailed build plan: `docs/plans/frontend-plan.md`.

- `vite.config.js`: dev proxy `/api` → `http://localhost:8000`.
- `api.js`: small `fetch` wrappers, one per endpoint in the contract. Each throws on a non-2xx response.
  When `import.meta.env.VITE_USE_MOCKS === "true"`, every wrapper calls `mockApi.js` instead.
- `mockApi.js`: dev-only in-memory fake of the API contract (decision #15). Same function
  names and return shapes as `api.js`. Never enabled in the production build.
  Run with `npm run dev:mock` (= `vite --mode mock`, which loads `.env.mock`; works on Windows
  without env-var prefixes).
- `display.js`: escalation-reason labels + detail lines, sensitivity-category labels,
  `timeAgo()`, `fmtScore()`. Shared by the queue, detail, and stats components.
- `App.jsx`: routes `/` → `ParentChat`, `/operator` → `OperatorDashboard`, plus a view switcher bar ("Parent chat | Staff dashboard") shown at the top of both pages (#26).
- `styles.css`: mobile-first, max content width 640px for the parent view and wider for the operator view, CSS variables for colors.

**Parent view**
- `pages/ParentChat.jsx`: center name header; message list (kept in component state for the session only); text input with a 500-character limit; send is disabled while waiting, and a "Checking the handbook…" indicator shows.
- `components/SuggestedQuestions.jsx`: chips for the five Brightwheel example questions, shown until the first message is sent.
- `components/ChatMessage.jsx`: parent bubble / answer bubble with "From the handbook: <title>" tags / escalation bubble. The escalation bubble uses a calm, neutral style, not error red, and shows only `message`. When a response has both `answer` and `message` (sensitive + verified, #37), it renders as an answer bubble with sources and the staff note underneath.
- Network failure → "Sorry, something went wrong — please try again or call (555) 014-2200." This is the one place the frontend shows anything other than an answer or the escalation message.

**Operator view**
- `pages/OperatorDashboard.jsx`: `StatsBar` at the top, then two **separate tabs**: *Questions* | *Knowledge Base* (non-negotiable). A Refresh button, no polling.
- `components/StatsBar.jsx`: total, % answered, escalated by reason, unresolved.
- `components/QuestionQueue.jsx`: toggle between *Needs review* and *All*; each row shows priority badges (🔴 Urgent, 🟠 Sensitive + category), a reason label, the question text, and the time.
- `components/QuestionDetail.jsx`: the question; the escalation reason in plain English; the would-have-been answer; semantic, adherence, and combined scores against the threshold; claimed facts each marked ✓ (matched) or ✗ (unmatched); the sensitivity rationale; titles of the retrieved chunks. Actions: **Mark resolved**, **Add answer to KB** (opens a `ChunkEditor` with the title prefilled from the question and category `faq`). For a sensitive question the editor shows a note that it will still escalate (N), and the Combined score reads "Sensitive — always sent to staff" instead of a threshold.
- `components/KnowledgeBase.jsx`: list of chunks grouped by category; Add / Edit / Delete (delete asks for confirmation in the page itself, not with `window.confirm`).
- `components/ChunkEditor.jsx`: category select (`KB_CATEGORIES`), title, content textarea, Save/Cancel. Used by both tabs.

---

## Deploy (`render.yaml`)
One Python web service, paid `plan: 0.5c-512mb` with a 1 GB persistent disk at `/var/data`, defined as a Render Blueprint (decisions #24, #27).
- Build: `pip install -r requirements.txt && cd frontend && npm ci --include=dev && npm run build`. Node/npm are preinstalled in all Render native runtimes (verified in Render's docs 2026-10-01), so no Docker needed. `--include=dev` because Vite is a devDependency.
- Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
- Health check: `/api/health`.
- Python version: `.python-version` (`3.14`).
- Env vars: `GEMINI_MODEL`, `GEMINI_EMBEDDING_MODEL`, and `DB_PATH=/var/data/front_desk.db` are set in the YAML; `GEMINI_API_KEY` is `sync: false`, so Render prompts for it on first deploy and it never lives in the repo.
- Persistence: only `/var/data` survives restarts/redeploys; the build step can't see it (seeding runs at startup). A redeploy has a few seconds of downtime; no horizontal scaling. Seeding runs only on an empty table, so later `handbook.json` edits don't reach the deployed DB (#27).

`requirements.txt`: pinned `fastapi`, `uvicorn[standard]`, `google-genai`, `pydantic`, `python-dotenv`, plus `pytest`, `httpx`, `httpx2` for tests.
