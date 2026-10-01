# Backend Plan

Status: **All 8 steps done 2026-10-01.** 123 tests passing (no network);
calibrated (#21); model chosen (#22); live run passed against real Gemini.
Open: the answer text isn't mechanically checked beyond the model's own
claimed_facts list — see the proposal raised after the live run.

This plan covers how and in what order the backend gets built. *What*
each file contains (functions, schema, constants, API contract) is
defined in `docs/architecture.md` (Backend section); this plan doesn't
repeat it. The frontend is done and verified against the mock
(`npm run dev:mock`), so the API contract is now fixed: the backend must
match `frontend/src/mockApi.js` response shapes exactly.

---

## 1. Check against the spec

| Requirement (source) | Where it's met | OK? |
|---|---|---|
| Pipeline order: retrieve → out-of-scope → classify → generate → adherence → combine → threshold → log (CLAUDE.md) | `pipeline.py`, one function, steps in that order | ✅ |
| Out-of-scope makes no LLM calls (CLAUDE.md #2) | Return before `classify()`; a test asserts zero generate calls | ✅ |
| Structured output only, never parse free text (non-negotiable) | `gemini.generate_structured` returns `response.parsed`; raises if None | ✅ |
| Adherence is mechanical, not an LLM (non-negotiable) | `adherence.py`, pure Python, no imports from `gemini.py` | ✅ |
| Sensitive (category ≠ none, or normalized score ≥ 0.70) always escalates (non-negotiable, #18) | `sensitivity.is_sensitive` + tests at confidence 1.0 and at the 0.70 boundary | ✅ |
| Combined = 0.35·semantic + 0.65·adherence; one 0.80 confidence threshold | `config.py` constants, `pipeline.py` | ✅ |
| Urgency is static keywords, no date resolution (non-negotiable, #5) | `urgency.py`, regex only | ✅ |
| Every question logged, including escalations and errors (CLAUDE.md step 8) | `insert_log` in a `finally`-style path; test per branch | ✅ |
| Escalation response carries only the message (#8) | `AskResponse`: `answer=null`, `sources=[]` when escalated | ✅ |
| Triage priority order (CLAUDE.md) | `triage.py`, same order as the mock's `sortQueue` | ✅ |
| Model ids from `.env`, confirmed rather than assumed (CLAUDE.md) | `config.py` env + `scripts/list_models.py` run before trusting them | ✅ |
| Calibrate before trusting thresholds (CLAUDE.md) | `scripts/calibrate_embeddings.py`; placeholders until run | ✅ |
| Render free tier, re-seed on boot (#11) | `seed_if_empty()` at startup | ✅ |

**No conflicts found.** Defaults I'm adding (none of them conflict with the spec):
- **One retry on Gemini 429/5xx** (about 2 s backoff) before treating
  the call as `system_error`. Free-tier rate limits are the most likely
  failure during a demo, and without a retry a short spike would make
  every question in it escalate.
- **Python version**: local is 3.14. Render gets `PYTHON_VERSION`
  pinned to match at deploy time (checked then, not assumed now).
- **`.env` currently has only `GEMINI_API_KEY`.** The model ids fall
  back to the defaults in `config.py` until `list_models.py` confirms
  them; I'll add the confirmed ids to `.env.example` (your `.env` is
  yours to edit).

## 2. Build order
1. **Environment**: `.venv`, `requirements.txt` (fastapi,
   uvicorn[standard], google-genai, pydantic, python-dotenv, pytest,
   httpx). Install, then **read the installed `google-genai` source**
   for the exact `embed_content` / `generate_content` / `response.parsed`
   signatures rather than relying on memory.
2. **`scripts/list_models.py`**: write it now, but **run it at the start of
   step 8** (testing stage, per the user). It's a one-off dev check, not
   used by the app. Until then the code uses the `config.py` defaults.
3. **Pure modules + their tests first** (no API needed): `config.py`,
   `urgency.py`, `adherence.py`, `triage.py` → `test_urgency.py`,
   `test_adherence.py`, `test_triage.py`.
4. **Data layer**: `db.py`, `schemas.py`, `gemini.py`, `seed.py`, `kb.py`.
5. **Pipeline**: `retrieval.py`, `sensitivity.py`, `generation.py`,
   `pipeline.py` → `test_pipeline.py` with Gemini monkeypatched.
6. **API**: `routes/ask.py`, `routes/operator.py`, `main.py` (startup
   seed, `/api` routers, serve `frontend/dist` with SPA fallback) →
   `test_api.py`; response shapes compared field by field with `mockApi.js`.
7. **Calibration**: `scripts/calibrate_embeddings.py` against the real
   embedding model → write `SIMILARITY_FLOOR` / `SIMILARITY_CEILING`
   into `config.py`, and record the numbers in the decision log.
8. **Live run**: run `scripts/list_models.py` to confirm model ids (stop
   and report if the defaults aren't available) → free ports 8000/5173 → `uvicorn` + `npm run dev`
   (mocks off) → walk through the frontend-plan verification list
   against the real backend.

## 3. Verification
- `pytest tests/ -v` all green; no test touches the network.
- Live: the five Brightwheel example questions + an off-topic one + a
  custody one, checking each against expectations:
  - Veterans Day, infant tuition, tour, lunch → answered with sources
  - fever, custody → `sensitive_forced`
  - off-topic → `out_of_scope` with no LLM calls (checked in the log row:
    no category or scores beyond semantic)
- Add-to-KB loop: an out-of-scope question → add an answer → ask again
  → now answered.
- Any expectation that fails is reported as it is, not tuned away
  silently. Threshold changes go in the decision log.

## 4. Carried over from the frontend
- ~~`QuestionDetail.jsx` showed "Needs 0.90 to answer" on sensitive
  questions~~ — fixed 2026-10-01 with decision #18: sensitive questions
  show "Sensitive — always sent to staff".
- The KB delete-confirmation click-through wasn't re-run after the
  user moved on; I'll re-verify it in the step 8 live walk-through.
