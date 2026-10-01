# Decision Log

Running log of design decisions and why they were made. `docs/CLAUDE.md`
states the *current* decisions; this file explains *why*. Append whenever
a decision is made or changed — numbers are stable (CLAUDE.md refers to
them), so changed decisions get a dated "Revised" note, not a renumber.

Status: **Decided** unless marked **OPEN**.

---

### 1. Depth lane over Breadth or Novelty — 2026-10-01
The assignment offers Breadth, Depth, or Novelty. Chose **Depth**: a
smaller set of intents handled extremely well (edge cases, policy logic,
escalation). The audience is anxious parents and busy operators — a
front desk that is *trustworthy* on the questions it answers, and
honest about the ones it can't, is more valuable (and more fundable)
than one that answers everything with uneven reliability. Evaluated on
scope, persuasiveness, empathy, uniqueness — not feature count.

### 2. Pipeline order, with an out-of-scope short-circuit — 2026-10-01
Retrieve → out-of-scope check → classify sensitivity → generate + extract
claimed facts → mechanical adherence check → combine confidence →
threshold/escalate → log. If retrieval finds nothing above the similarity
floor, skip both LLM calls and escalate immediately: with no relevant
source there is nothing to ground an answer in, and spending two calls
(on a free-tier quota) to reach the same conclusion is waste.

### 3. Adherence check is mechanical, not an LLM grading itself — 2026-10-01
The generation call must list every specific factual claim it made
(times, dollar amounts, ages, phone numbers, named policies). Each claim
is checked by token overlap against the retrieved source text. Asking a
second LLM call "is this answer grounded?" is circular — the same failure
modes that produce a hallucination also produce a confident "yes, it's
grounded". Token overlap is dumb but independent, and numbers (the
claims parents act on: times, fees, temperatures) must match exactly.

### 4. Confidence, sensitivity, and urgency are separate signals — 2026-10-01
- Confidence = did we ground this correctly (semantic + adherence).
- Sensitivity = is the topic inherently high-stakes.
- Urgency = is it time-critical.

A system can be fully confident about a sensitive topic (still escalate)
or unsure about a mundane one (escalate for a different reason). Merging
them into one score hides *why* something was escalated, which is
exactly what an operator needs to triage. Operator triage priority:
sensitive+urgent → urgent → sensitive → low-confidence only.

### 5. Urgency is static keyword matching; no date resolution — 2026-10-01
Urgency is triggered by keywords ("today", "right now", "pick up early",
…), not an LLM call and not dynamic date resolution. Resolving "Friday"
to a calendar date and re-flipping urgency as it approaches is real
value but a separate system (timezones, re-evaluation over time) —
flagged as a "next iteration" item for the write-up. Keywords are
predictable, testable, and cost no quota.

### 6. Force-escalation categories and thresholds — 2026-10-01
- `health`, `safety`, `allergies`, `custody_legal` always force score=5
  and escalate. These are too high-stakes to leave to a graded score —
  a wrong answer about a fever or an authorized pickup has real-world
  consequences that a wrong answer about nap time does not.
- `emotional_social` is sensitive but graded, not forced.
  **Revised 2026-10-01 → see #18:** all sensitive questions escalate;
  the 0.90 sensitive threshold is removed.
- Combined confidence = `0.35 * semantic + 0.65 * adherence`. Adherence
  weighted higher: catching an unsupported claim matters more than
  fine-grading retrieval quality.
- Thresholds: 0.80 standard, 0.90 when the topic is sensitive.
- The 0.80/0.90 bars are only meaningful once the semantic score is
  calibrated to the embedding model (see #7).

### 7. Gemini (free tier) over OpenAI; structured output only — 2026-10-01
OpenAI requires a paid key — not viable for a take-home meant to run on
free-tier tools. Gemini Flash via AI Studio's free tier has a generous
quota and reliable structured JSON output (`response_schema` with a
Pydantic model), which this system depends on more than anything else:
both generation and sensitivity classification return typed objects;
no free-text parsing, ever. Embeddings use Gemini's embedding model.
Raw cosine values from any embedding model aren't a 0-1 confidence, so
the semantic floor/ceiling are calibrated with
`scripts/calibrate_embeddings.py` against real on/off-topic questions.
Model ids live in `.env` so a renamed model doesn't require a code change.

### 8. Every escalation shows the parent only "staff has been notified" — 2026-10-01
Out-of-scope, below-threshold, and sensitive escalations all show the
same message. A sensitive question does **not** get the generated
answer or a handbook excerpt alongside it, even if one exists. Rationale:
for high-stakes topics, a partially-right automated answer next to a
"staff will follow up" note invites the parent to act on the automated
part; a single clear message keeps the human in the loop.
- **Known consequence, revisit deliberately:** a genuine emergency
  ("having an allergic reaction right now") also only sees "staff has been
  notified". Whether sensitive+urgent should add "call 911 / call the
  center" is an open product question — not built.

### 9. The loop closes through the knowledge base, not a reply to the parent — 2026-10-01
The parent's part is asking questions; there's no reply channel back to
them in this prototype. The operator reviews escalated/unanswerable
questions and either marks them resolved or adds an answer to the KB
(creating/editing a handbook chunk, re-embedded on save). That makes the
next parent's identical question answerable — the system improves from
its own failures, which is the assignment's "easy to improve over time".
All scores and the would-have-been answer are logged for escalated
questions so the operator can see *why* it escalated.

### 10. KB editing and question review are separate operator sections — 2026-10-01
They're different jobs: review is triage ("what needs me now?"), KB
editing is maintenance ("is the source of truth right?"). Combining
them clutters both. The bridge between them is the "Add to KB" action
from a question.

### 11. Hosting: Render free tier, SQLite is ephemeral — OPEN — 2026-10-01
Deploying to Render. The free tier has no persistent disk and spins down
when idle, so the SQLite DB (KB edits + question log) resets on every
restart/redeploy. Mitigation: the handbook is re-seeded from
`data/handbook.json` (and re-embedded) on boot, so the demo always
starts in a working state — but operator edits and logs don't survive.
- Option A (current): free tier, accept resets for demo purposes.
- Option B: cheap paid instance + persistent disk, SQLite on the disk.
- Decision pending: the user will confirm whether the free tier is
  viable for the demo.

### 12. React frontend instead of server-rendered pages — 2026-10-01
**Revises** the earlier plan of server-rendered pages. React (Vite) is
the framework the author is most comfortable with; not being a frontend
specialist, building in a familiar framework is the faster and less
risky path within the timebox. Deployed as a static build served by
FastAPI (API under `/api/*`), so it's still one Render service and one
URL with no CORS configuration.

### 13. Mock handbook designed to exercise the pipeline — 2026-10-01
Little Acorns' handbook (`data/handbook.json`) is fictional and written
so the assignment's example questions are answerable *or* deliberately
escalate:
- Explicitly states the center is **open** on Veterans Day (a common
  wrong guess — good test of grounding).
- The forgotten-lunch backup meal is the **same every day**, so "what's
  lunch today?" is answerable without the system needing to know
  today's date (consistent with #5).
- Fever/illness, allergies, and custody chunks exist so those questions
  retrieve well — and still escalate by category (#6).
- Fictional 555 phone numbers, no real people.

### 14. `question_log` gains `is_urgent`, `escalation_reason`, `sensitivity_rationale` — 2026-10-01
The original schema couldn't express two things the operator triage
needs: whether a question was urgent (priority order puts urgency
first) and *why* it escalated (out-of-scope vs. forced-sensitive vs.
low confidence vs. system error call for different operator actions).
`sensitivity_rationale` is stored because the classifier already
returns it and it's the operator's best one-line "why is this flagged".
Recomputing these at read time would mean re-running keyword checks
and guessing the reason from scores — storing them is simpler and
records what the pipeline actually decided. Approved by the user.

### 15. Frontend built first against a dev-only mock API — 2026-10-01
The frontend is being built before the backend. Rather than writing it
blind against the contract, `frontend/src/mockApi.js` implements the
API contract in memory (same function names and response shapes as
`api.js`), switched on only by `VITE_USE_MOCKS=true` in dev. This lets
every UI state (answered, each escalation reason, empty queue, errors)
be checked in a browser now. The production build never uses it; once
the backend exists, the real API replaces it with no component changes.
The mock's "decisions" are canned by keyword and say nothing about how
the real pipeline behaves.

### 16. Frontend implementation choices — 2026-10-01
- JavaScript (JSX), not TypeScript; plain CSS with variables, no UI
  library — smallest toolchain for a timeboxed prototype, and the API
  contract in `architecture.md` is the type reference.
- React 19 + Vite + `react-router-dom` (current versions at build time;
  `architecture.md` originally said React 18).
- Operator dashboard is also mobile-usable (stacked list → detail), since
  center owners are often on their phones.

### 17. No staff follow-up with the asking parent — out of scope — 2026-10-01
Parents are anonymous, so an escalated question can't be routed back
to the person who asked. That means "closing the loop" (#9) benefits the
*next* parent, not the one who escalated — including for sensitive
questions like a fever. Collecting contact details and building a
follow-up channel isn't feasible in the timebox and isn't in scope.
Operator options per escalated question: **add an answer to the KB**
(also resolves it), **mark resolved**, or **leave it** in the queue.
Named as a known limitation / next iteration in the write-up.

### 18. Sensitive always escalates; sensitivity flag threshold 0.70 — 2026-10-01
**Revises #6.** If a question is marked sensitive, it is escalated —
full stop. There is no separate (stricter) confidence bar for sensitive
topics; the 0.90 threshold is removed.

A question is marked sensitive when **either**:
- its category is anything other than `none` (`health`, `safety`,
  `allergies`, `custody_legal`, `emotional_social`), **or**
- its normalized sensitivity score `(score - 1) / 4` is ≥ **0.70**
  (score 4 or 5 on the classifier's 1–5 scale).

Rationale: the bar is set low on purpose to pull in borderline
questions. A false positive costs an operator a minute; a false
negative means an anxious parent gets an automated answer to something
a person should handle. We prefer false positives.

Non-sensitive questions keep the single 0.80 combined-confidence
threshold. `sensitivity_score` therefore now affects decisions
(previously informational only — architecture item D).

### 19. Python package is `backend/`, not `app/` — 2026-10-01
Renamed so the repo's two halves read at a glance: `backend/` (FastAPI)
and `frontend/` (React). `app` is FastAPI-tutorial convention but says
nothing to an engineer navigating the repo cold. Entry point is now
`uvicorn backend.main:app`; imports are `backend.<module>`.

### 20. TOP_K = 2 (was 3) — 2026-10-01
The user prioritized accuracy. Fewer retrieved excerpts means less
loosely-related text for the model to blend into an answer, and claimed
facts are checked against fewer, closer sources. 2 rather than 1 so
two-topic questions ("pick up early today + is there a backup lunch?")
can still be answered; with 1, the second half's facts would go unmatched
and the question would escalate (safe, but it sends staff questions the
bot could have handled). TOP_K is a ceiling — `relevant()` still drops
any retrieved chunk below the similarity floor. Revisit after
calibration shows how often a second chunk actually clears the floor.
**Live data point (2026-10-01):** for "Can I pick up early today, and is
there a backup lunch?" the early-pickup chunk (`dropoff-pickup`, 0.679)
ranked 3rd, a near-tie behind `authorized-pickup` (0.683), so TOP_K = 2
cut it and the answer described *who* may pick up instead of *how* to
pick up early. Every claim was true (adherence 1.0) — an incomplete
answer, not a wrong one. TOP_K = 3 would include it. **User confirmed: keep 2** —
accuracy over coverage; incomplete-but-true is the acceptable failure.

### 21. Calibrated retrieval: floor 0.64, semantic 0 at 0.50, ceiling 0.77 — 2026-10-01
`scripts/calibrate_embeddings.py` on `gemini-embedding-001` @ 768 dims,
17 on-topic and 10 off-topic questions:
- Retrieval ranked the correct chunk first for **17/17** on-topic questions.
- On-topic best matches: 0.663–0.778 (median 0.726). Off-topic:
  0.503–0.624 (median 0.583). Clean separation → **floor 0.64**. The old
  placeholder (0.55) would have let 5 off-topic questions through (bus,
  weather, summer camp, Spanish immersion, piano).
- Gap is only ~0.04, and the closest off-topic questions are plausible
  daycare questions (bus, summer camp). Errors at the floor fail safe
  (escalate), but this is the number most worth re-checking as the
  handbook grows.
- The second-best chunk often clears 0.64 and is always topically related
  (medicine→illness, tuition→billing), supporting TOP_K = 2 (#20).

**Semantic scale is no longer anchored at the floor.** The planned
`(cos − floor) / (ceiling − floor)` made questions just above the floor
score ≈ 0, capping combined confidence at ~0.71 even with every fact
verified: 6/17 on-topic questions — including the brief's own "Are you
open on Veterans Day?" — would have escalated with perfect answers. The
floor is a yes/no relevance gate; the scale now runs from **0 at 0.50**
(where clearly unrelated questions land) to **1 at 0.77** (90th
percentile on-topic). Weakest on-topic (0.663) → semantic 0.60 →
combined 0.86 when facts verify. Adherence (0.65 weight) still decides:
an unsupported fact still sinks the answer. Chosen by the user over
anchoring at the floor or at 0.58 (which put Veterans Day exactly on the
bar). A regression test pins this.

### 22. LLM: `gemini-3.5-flash-lite`; embeddings: `gemini-embedding-001` — 2026-10-01
Probed with real calls before committing (listing a model ≠ being able
to use it):
- `gemini-2.5-flash` (the original default): **404 — "no longer
  available to new users"**, though it appears in the model list.
- `gemini-3.5`/`3.6`/`3.7`/`3.8-flash` and `gemini-flash-latest`:
  **503 "high demand"**, twice each, on this free-tier key.
- `gemini-3.5-flash-lite`: responded in 0.79s with correct structured
  output. Chosen by the user. Lite models reason less, but answers here
  are short and grounded, and the mechanical adherence check catches
  unsupported claims regardless of model.
- `gemini-embedding-2`: returned **one vector for two inputs** (merges a
  batch), which would break batched seeding; `gemini-embedding-001`
  returns one per input. Kept 001.
- `scripts/list_models.py --probe` now makes one tiny call to each
  configured model so this is checked, not assumed.
- Full Flash remains an easy upgrade (`GEMINI_MODEL` in `.env`) if free-
  tier capacity improves; it should be re-probed first.

### 23. Numbers in the answer text are checked mechanically; model writes digits — 2026-10-01
Found in the live run: the adherence check only verified the facts the
model *chose to list*. In "Can I pick up early today, and is there a
backup lunch?" it listed `$6` and `10:00 AM` but also wrote an unlisted
(unchecked) sentence; in the lunch answer it wrote "six dollars" / "ten
in the morning" while listing `$6` / `10:00 AM`.

Fix (user's choice, both mechanical — no second LLM call):
1. **Answer-number check.** Every number in the answer *text* (times,
   prices, phone numbers, ages, temperatures) must appear somewhere in
   the retrieved excerpts. Each one that doesn't is added to
   `unmatched_facts` and counts as a failed fact in the adherence score.
   Numbers are the details parents remember and act on ($6, 10:00 AM),
   so they need the highest confidence.
2. **Digits instruction.** Generation must write numbers in digits exactly
   as the handbook does, never spelled out — otherwise "six dollars" is
   invisible to check 1. Chosen over a stricter every-sentence-must-match
   check, which would also escalate harmless pleasantries ("Let us know if
   you have other questions!"); the user judged the instruction more
   organic.

Known limits: (a) if the model ignores the digits instruction, a
spelled-out number still evades the check — verified live after the
change; (b) a number the *parent* typed and the model echoes back (e.g.
"until 6:30") is flagged if the handbook doesn't contain it — a
conservative false positive; (c) non-numeric unlisted claims are still
only covered by the model's own claimed_facts list.

### 24. Render Blueprint: one free native Python service — 2026-10-01
`render.yaml` defines a single `runtime: python`, `plan: free` web
service. Verified against Render's docs rather than assumed:
- Node/npm are preinstalled in every native runtime, so the same build
  can run `npm ci && npm run build` for the React app — no Docker needed
  (the architecture's fallback plan is unnecessary).
- `.python-version` pins 3.14 to match local (Render supports it).
- Build uses `npm ci --include=dev` because Vite is a devDependency.
- `GEMINI_API_KEY` is `sync: false` (prompted in the dashboard, never in
  the repo); model ids are set explicitly to the probed values (#22).
- `healthCheckPath: /api/health`; `autoDeployTrigger: commit`.
Free-tier consequences (still decision #11, OPEN): ephemeral SQLite and
spin-down when idle — the first request after idle waits for a cold
boot, which also re-seeds the handbook (one batched embedding call).
