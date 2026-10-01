# CLAUDE.md — Brightwheel AI Front Desk Prototype

This file is read automatically at the start of every Claude Code session
in this repo. It is the source of truth for scope, architecture, and
conventions. If something here conflicts with an ad-hoc instruction in a
session, prefer this file unless the user explicitly says they're changing
a decision — and if they do, update this file and `docs/decision-log.md`
in the same session.

## What this is

A take-home prototype for Brightwheel: a lightweight "AI Front Desk" for
a fictional daycare/pre-K, **Little Acorns Early Learning Center**. Two
perspectives: a parent-facing Q&A chat, and an operator/staff dashboard to
edit the knowledge base and review how the system is doing.

**Chosen lane: Depth.** A smaller set of intents handled extremely well
(edge cases, policy logic, escalation) rather than broad feature coverage.
Evaluated on scope/completeness, persuasiveness, user empathy, and
uniqueness — not on volume of features. See `docs/decision-log.md` for the
full reasoning behind every design choice below; this file states the
*current* decisions, the log explains *why*.

## Architecture (pipeline, in order)

1. **Retrieve** — embed the parent's question (Gemini's embedding model —
   see Tech Stack for exact model id), cosine-similarity against stored
   handbook chunk embeddings.
2. **Out-of-scope short-circuit** — if nothing clears the similarity
   floor, skip straight to an out-of-scope escalation message. Don't spend
   two more LLM calls on a question with no relevant source.
3. **Classify sensitivity** — one LLM call, structured output
   (`category`, `score` 1-5, one-sentence `rationale`). Categories:
   `health`, `safety`, `allergies`, `custody_legal`, `emotional_social`,
   `none`. The classifier categorizes by **what the parent needs**, not
   by which topic is mentioned: "my child has a fever, can she come in?"
   is `health`; "how do I call her in sick?" is routine logistics (`none`).
   A question is **sensitive** if its category is not `none` **and** its
   score is ≥ 3, **or** its normalized score (`(score - 1) / 4`) is
   ≥ **0.70** (score 4–5) whatever the category. **Sensitive questions
   always escalate**, regardless of anything downstream. The bar still
   leans toward false positives (staff see a question the bot could have
   answered) over false negatives (a sensitive question answered
   automatically). See decision log #18, revised by #25.
   **Exception — staff-written answers win (#28):** a sensitive question
   is answered if every claimed fact is verified against handbook entries
   that staff wrote or edited in the dashboard (`source = staff`) and the
   confidence bar passes — a person already made the judgement call.
   Sensitive questions grounded in the seeded handbook still escalate.
4. **Generate answer + extract claimed facts** — one LLM call, structured
   output (`answer`, `claimed_facts: list[str]`). The model must answer
   only from the retrieved excerpts and list every specific factual claim
   it made (times, dollar amounts, ages, phone numbers, named policies) as
   short strings, phrased close to the source wording.
5. **Adherence check (mechanical, not another LLM call)** — each claimed
   fact is checked via token-overlap matching against the actual retrieved
   source text. This is deliberately *not* an LLM grading its own answer —
   that would be circular. **The answer text itself is also scanned: every
   number in it (time, price, phone, age, temperature) must appear in the
   retrieved excerpts**, so a number the model didn't list as a claim can't
   slip through; each missing number counts as a failed fact. Generation
   is told to write numbers as digits exactly as the handbook does, so they
   are visible to this check (decision log #23). Produces an
   `adherence_score` and a list of `unmatched_facts`.
6. **Combine confidence** — `combined = 0.35 * semantic_score + 0.65 *
   adherence_score`. Adherence is weighted higher because catching an
   unsupported claim matters more than fine-grading retrieval quality.
7. **Threshold / escalate** — sensitive → escalate (step 3). Otherwise,
   combined confidence below 0.80 → escalation message instead of the
   generated answer.
8. **Log everything** — every question logged to `question_log`
   (answer, escalated, sensitive, category, all three scores, threshold
   used, claimed/unmatched facts) for the operator dashboard.

## Escalation behavior (what the parent sees, and what happens next)

- **Sensitive + fully verified answer → answer AND notify staff**
  (decision log #37, revising #8): if a question escalates only because
  it's sensitive, and its answer passed every check (all claimed facts
  matched, no unsupported numbers, combined confidence ≥ 0.80), the
  parent sees the answer with its handbook sources plus a note: "I've
  also shared your question with the Little Acorns staff. If it's urgent,
  call (555) 014-2200." The question still lands in the staff queue
  (`escalated = true`, `answer_shown = true`).
- **Every other escalation** — out-of-scope, below-threshold, system
  error, or sensitive with an answer that didn't fully verify — shows
  only the staff-notified message with the phone number (#25). An
  unverified answer is never shown.
- Sensitive questions fully backed by staff-written entries are simply
  answered, without notifying staff (#28).
- There is no reply channel back to the parent. The loop closes through
  the operator: they review the escalated question in the dashboard and
  either **mark it resolved** or **add an answer to the knowledge base**
  (which creates/edits a handbook chunk and re-embeds it), so the next
  parent who asks gets answered.
- The generated answer and all scores are still logged for escalated
  questions, so the operator can see what the system *would* have said.

## Why signals are kept separate (do not conflate these)

- **Confidence** = did the system understand/ground this correctly
  (semantic + adherence).
- **Sensitivity** = is this topic inherently high-stakes, independent of
  how well-grounded the answer is.
- **Urgency** = is this time-critical (keyword-triggered: "today," "right
  now," "pick up early" — intentionally NOT an LLM call, and intentionally
  NOT dynamic date-resolution; see decision log #5).

A system can be fully confident about a sensitive topic (should still
escalate) and fully unsure about a mundane one (should still escalate, for
a different reason). Never merge these into one score.

## Priority order for operator triage

1. Sensitive **and** urgent → top priority, always.
2. Urgent alone.
3. Sensitive alone.
4. Neither → falls back to confidence-based escalation.

## Data model

```sql
handbook_chunks(id, category, title, content, source, embedding, updated_at)
-- source: 'handbook' (seeded from data/handbook.json) | 'staff' (created or
--         edited in the operator dashboard) — decision log #28
question_log(
  id, created_at, question, answer, escalated, escalation_reason,
  is_sensitive, is_urgent, sensitivity_category, sensitivity_score,
  sensitivity_rationale, semantic_score, adherence_score,
  combined_score, threshold_used, retrieved_chunk_ids, claimed_facts,
  unmatched_facts, answer_shown, resolved
)
```

`escalation_reason` is one of `out_of_scope`, `sensitive_forced`,
`below_threshold`, `system_error` (NULL when answered). `answer_shown`
is true when the parent saw the generated answer (answered, or escalated
with a verified answer — #37). Full column types
are in `docs/architecture.md` (decision log #14).

## Tech stack

- **Backend**: Python + FastAPI, SQLite (`backend/db.py`)
- **LLM**: Google Gemini (free tier via AI Studio — no card, no paid key
  required). SDK is `google-genai` (`from google import genai`). Use
  `client.models.generate_content(..., config={"response_mime_type":
  "application/json", "response_schema": YourPydanticModel})` for BOTH
  generation+fact-extraction and sensitivity classification — this is
  Gemini's equivalent of OpenAI's structured-output `response_format`, and
  the same non-negotiable applies: never parse free text from the model.
  Model: **`gemini-3.5-flash-lite`** (decision log #22) — chosen because
  it was the only Flash-family model that actually responded on the free
  tier (`gemini-2.5-flash` → 404 for new keys; full 3.x Flash → 503 "high
  demand"). Model names/versions move fast; re-check with
  `python scripts/list_models.py --probe` rather than trusting a stale
  string. API key read from `GEMINI_API_KEY` in `.env`.
- **Retrieval**: `gemini-embedding-001` at 768 dims, cosine similarity
  (no vector DB needed at this scale). Not `gemini-embedding-2`: it merges
  a batch into a single vector. Calibrated with
  `scripts/calibrate_embeddings.py` (decision log #21): out-of-scope
  **floor 0.64**; `semantic_score` runs from **0 at cosine 0.50** to
  **1 at 0.77**. The semantic scale is deliberately *not* anchored at the
  floor — the floor is a yes/no relevance gate. Raw cosine values are not
  a 0-1 confidence and don't transfer between embedding models: re-run
  calibration if the embedding model or handbook changes substantially.

  Model ids come from `.env` (`GEMINI_MODEL`, `GEMINI_EMBEDDING_MODEL`)
  alongside `GEMINI_API_KEY`, so they can be corrected without code
  changes; `scripts/list_models.py --probe` checks they actually work
  (a listed model can still be unusable).

  **Why Gemini, not OpenAI:** OpenAI requires a paid key — not viable
  for a take-home meant to run on free-tier tools. Gemini Flash via AI
  Studio's free tier was the strongest free option found (generous
  quota, reliable structured JSON output — the property this system
  depends on most, since generation and sensitivity classification both
  rely on structured output rather than free-text parsing).
- **Frontend**: React (Vite) single-page app in `frontend/`. Parent chat
  at `/`, operator dashboard at `/operator` (client-side routing). In
  production FastAPI serves the built `frontend/dist` and the JSON API
  lives under `/api/*` — one Render service, one URL, no CORS. Chosen
  because it's the framework the author knows best (decision log #12).
- **Hosting**: Render, paid `0.5c-512mb` instance with a 1 GB persistent
  disk mounted at `/var/data`; SQLite lives at `/var/data/front_desk.db`
  (`DB_PATH`), so KB edits and the question log survive restarts and
  redeploys (decision log #27, closing #11). The handbook is seeded from
  `data/handbook.json` only when the table is empty — later edits to that
  file do NOT reach an existing deployed DB (edit via the dashboard, or
  reset the DB).

## Non-negotiables (don't "helpfully" change these without flagging it)

- Structured outputs only — no regex/free-text parsing of LLM output.
- Adherence checking stays mechanical (token-overlap), never a second LLM
  call grading the first — that's circular.
- Sensitive questions (category ≠ `none` with score ≥ 3, or normalized
  sensitivity score ≥ 0.70) always escalate — unless fully grounded in
  staff-written entries (#28).
- Urgency detection stays keyword-based and static — see "Out of scope"
  below before adding date resolution.
- Knowledge-base editing and question review stay in separate operator UI
  sections (not combined into one view).

## Out of scope for this prototype (deliberate, not an oversight)

- Dynamic/relative-date urgency resolution (e.g. resolving "Friday" to a
  calendar date and re-flipping urgency as it approaches). Flagged as a
  "next iteration" item for the write-up, not something to build now.
- Production-grade auth, multi-tenant support, real PII handling.
- Staff follow-up with the parent who asked. Parents are anonymous; an
  escalated question's operator options are: add an answer to the KB
  (also resolves it), mark it resolved, or leave it in the queue
  (decision log #17).

## Dev workflow

Development happens on Windows (PowerShell); production is Render (Linux).

- Run tests: `pytest tests/ -v`
- **Every backend change is verified by tests before moving on.** Each
  component (adherence, urgency, triage, sensitivity, retrieval,
  pipeline, API) has its own `tests/test_<component>.py`; when a module
  is added or changed, add/update its tests and run them in the same
  step. Never leave a backend change untested "for later".
- Start backend locally: `uvicorn backend.main:app --reload` (port 8000)
- Start frontend locally: `cd frontend; npm run dev` (Vite, port 5173,
  proxies `/api` to 8000)
- **Always kill all running server/test processes before starting a new
  one.** Ports stay bound after a run ends, and Claude Code will otherwise
  get stuck cycling through incrementing ports instead of reusing the
  freed one. Before starting or restarting a server, free the port
  (PowerShell; repeat for 5173 when restarting Vite):
  ```powershell
  Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
  ```
  and confirm the port is actually free before launching again. Same
  applies after a test run that spins up a live server — kill it
  explicitly rather than leaving it running "just in case."

## Project docs (keep these current)

- `docs/decision-log.md` — running log of design decisions and why they
  were made. **Append to this whenever a design decision is made or
  changed during a session** — don't wait to be asked.
- `docs/architecture.md` — file structure and what goes in each file
  (functions, schema, API contract). Update it *before* adding or
  restructuring files.
- `docs/prompts.md` — the user's private bookkeeping. **Ignore it**: don't
  read it for context and don't edit it.
- `data/handbook.json` — the mock Little Acorns handbook (seed data for
  `handbook_chunks`). Fictional; no real personal data.
- `docs/plans/backend-plan.md`, `docs/plans/frontend-plan.md` — current
  implementation plans. Update these when the plan changes, not just when
  it's finished.

## Appendix: original assignment (verbatim, from Brightwheel)

Everything above is the distilled, decided-on interpretation of this. If
anything above seems to conflict with this source text, flag it rather
than silently resolving it one way — it may mean a decision needs
revisiting, not that this appendix is stale.

> Thank you for your time and interest in brightwheel. This exercise is a
> chance for you to engage with the kinds of challenges we're solving. We
> are looking for engineers who can bridge the gap between "what is
> technically possible with AI" and "what is actually valuable for users."
>
> **Effort recommendation:** 3 hours
> **Time limit:** You have 3 business days to submit your exercise. We
> keep the window short to respect your time and to observe how you
> explore, iterate, and ship under scope constraints.
> **Format:** 1) Hosted URL for a prototype and 2) explanation as a doc
> (<1 page) or video (< 2 mins)
> **Tools:** We encourage you to use AI acceleration tools (Claude Code,
> Cursor, V0, Replit, etc.) and free-tier large language models of your
> choice to rapidly explore, iterate, and create prototype software. We
> are not looking for production-ready code; we are looking for a
> "working proof of concept" that demonstrates your vision, problem
> understanding, taste, and technical judgment. Please ensure your
> prototype is hosted either publicly or share credentials ahead of time.
>
> **Brightwheel Context**
> Brightwheel is the operating system for early education. While we don't
> expect a deep understanding of our market, we do expect you to learn
> about our customers: daycares/pre-Ks and the admin, teachers, and
> families they serve. Operators are busy small business owners and app
> users are anxious, deeply caring parents.
>
> **Problem Context: The "Front Desk" Bottleneck**
> School administrators spend hours every day answering very similar
> questions via phone, email, and text:
> - "Are you open on Veterans Day?"
> - "What is the tuition for infants?"
> - "My child has a fever, can they come in?"
> - "I forgot to pack lunch. Can you provide lunch today and what is it?"
> - "How can I schedule a tour?"
>
> Parents want fast, accurate answers. Operators are busy and can't always
> respond in real time. Handbooks are hard to search on a phone, and
> voicemail tags are frustrating. If brightwheel could provide an
> out-of-the-box AI Front Desk that correctly handles the majority of
> inquiries, it could save hours of admin time each week and meaningfully
> improve the parent experience.
>
> **Your Task: a functional "AI Front Desk" prototype**
> Build a lightweight, mobile-friendly experience with two perspectives:
>
> 1) Parent experience (front desk):
>    - Let a parent ask a question (text, voice, guided flow - your choice)
>    - Provide an answer that is specific to the center and feels
>      trustworthy
>    - When uncertain or the question is sensitive, handle it gracefully
>
> 2) Operator experience (control center):
>    - Give staff a way to provide or edit the source of truth
>    - Show what questions are being asked and where the system struggled
>    - Make it easy to improve the system over time (even if it's simple)
>
> Don't use real personal data. Feel free to invent a fictional center and
> policies.
>
> **Data / Grounding**
> Use any approach that fits your timebox:
> - Create a small structured dataset with policies and schedules
> - Build a tiny "handbook" page and ground answers from it
> - Optionally, use a public handbook as inspiration (no need to build
>   perfect ingestion). Example: Albuquerque handbook.
>
> We care more about response quality and trustworthiness than about
> document parsing.
>
> **How you can spend your time**
> You have creative freedom to pick one area of focus:
> - Breadth: Parent chat + operator view + simple knowledge editing
> - Depth: A smaller set of intents, handled extremely well (edge cases,
>   policy logic, escalation)
> - Novelty: A surprising interface or workflow based on real
>   parent/operator pain
>
> **What we'll evaluate**
> - Scope & completeness: Did you pick a realistic scope and finish it well?
> - Persuasiveness: Would this excite a team to fund and build for real?
> - User empathy: Does it reduce friction and make good decisions on
>   behalf of users?
> - Uniqueness: Any insight, craft, or implementation detail that stands
>   out?