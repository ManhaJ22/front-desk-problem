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
**Revised 2026-10-01 → see #45:** classification now runs first (it also rewrites follow-ups into standalone questions).
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
**Revised 2026-10-01 → see #44:** urgency is now judged in context by the existing classifier call; keywords are the fallback.
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
**Revised again → see #37:** sensitive questions with a fully verified answer now show it alongside the staff notice.
**Revised 2026-10-01 → see #25:** the message now also gives the front-office
phone number for anything urgent. Still no generated content on escalation.
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
**Closed 2026-10-01 → see #27:** moved to a paid instance with a persistent disk.
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

### 25. Escalate on need, not mention; phone number in escalation message; absence policy — 2026-10-01
**Revises #18 and #8.** Found in the deployed demo: "my child is sick can
I call her in sick?" → "Sent to staff" with nothing else. Three causes:
1. **Handbook gap** (mine): no policy for reporting an absence — one of
   the most common front-desk questions. The model correctly said "I'm
   not sure" with no claims. → Added an "Absences / Calling In Sick"
   section to `data/handbook.json`.
2. **Topic-triggered escalation**: the classifier tagged it `health` but
   scored it only 2/5 with the rationale "can mostly be processed
   routinely"; under #18 any non-`none` category forced escalation.
   → Two complementary changes:
   - The classifier now categorizes by **what the parent needs**:
     sensitive categories are for when a person's judgement is needed
     about a child's situation; reporting an absence or asking a general
     policy question that merely mentions illness is `none`.
   - Rule: sensitive = (category ≠ `none` **and** score ≥ 3) **or**
     normalized score ≥ 0.70 (score 4–5, any category). A low-scored
     category tag alone no longer forces escalation; a high score still
     does even if the category is `none`.
   Trade-off accepted: slightly more false-negative risk than #18 — a
   genuinely sensitive question the classifier scores 2 would now be
   answered (if grounded). Still leans toward false positives (3/5 is a
   low bar) and adherence still has to pass.
3. **Dead-end message**: the parent had no next step. → Escalation
   message is now "Thanks for your question. I've notified the Little
   Acorns staff about it. If it's urgent, call (555) 014-2200." Still no
   generated content on escalation (the core of #8 stands); this also
   partially addresses the emergency concern noted under #8.

### 26. A view switcher on both pages — 2026-10-01
The user found the deployed app "disconnected": the parent chat had no
way to reach the staff dashboard (by design — a real parent shouldn't
see a staff link), so the dashboard looked missing. For a prototype whose
point is showing *both* perspectives, discoverability wins over realism:
`App.jsx` now renders a "Parent chat | Staff dashboard" switcher at the
top of both pages (replacing the one-way "Parent view →" link). In a
real product these would be separate apps with separate auth.

### 27. Paid Render instance + persistent disk — closes #11 — 2026-10-01
The free tier proved unviable in the deployed demo: the instance
restarted (redeploy on push, or spin-down after ~15 min idle) and wiped
the SQLite file, so KB edits and the question log vanished — the user
saw "the knowledge base isn't updating, questions aren't saving".
- `render.yaml`: `plan: 0.5c-512mb` (cheapest paid plan in the Blueprint
  spec) + `disk` (1 GB at `/var/data`), `DB_PATH=/var/data/front_desk.db`.
  No code change. Chosen by the user over a free hosted database (rewrite
  `db.py` for a new driver) or accepting resets.
- Verified in Render's docs: disks require a paid instance; only the
  mount path persists; the build step can't see the disk (fine — seeding
  runs at startup).
Trade-offs: costs money (small); a redeploy now has a few seconds of
downtime (Render stops the old instance before starting the new one when
a disk is attached); the service can't be scaled horizontally; and
because seeding only runs on an empty table, later edits to
`data/handbook.json` no longer reach the deployed DB automatically —
handbook changes go through the dashboard (or a deliberate DB reset).
The paid instance also never sleeps, removing slow cold starts.
**Follow-up (same day):** data still reset after the plan upgrade. The
service had been created as a plain Web Service, not via New → Blueprint
(evidence: Render never prompted for the `sync: false` API key, causing
the first failed deploy), so `render.yaml` — including the `disk` and
`DB_PATH` — was never applied; upgrading the instance alone doesn't make
the filesystem persistent. Fix: add the disk (`/var/data`) and `DB_PATH`
in the dashboard (or recreate the service as a Blueprint).
`/api/health` now returns `db_path` so persistence can be verified from
outside.

### 28. Staff-written answers win over the sensitivity rule — 2026-10-01
Found in the deployed demo: the operator added a "Sick child" entry,
retrieval ranked it first (combined 0.94), yet "my child is sick, what
do I do?" still went to staff because the classifier scored it health
4/5 — architecture item N. The improvement loop silently didn't work for
sensitive topics, which read as "the KB isn't updating".

Rule now: a sensitive question is **answered** if (a) every claimed fact
is matched, (b) every match comes from a chunk with `source = staff`,
(c) no answer number is unsupported, and (d) combined confidence clears
0.80. Otherwise sensitive still escalates as before. Rationale: escalation
exists so a person makes the judgement call; once staff have written
that judgement into the KB, repeating the escalation helps nobody.
- `handbook_chunks.source`: `handbook` for seeded entries, `staff` for
  anything created **or edited** in the dashboard (editing a seeded entry
  is a staff judgement too). Migrated in place for existing DBs.
- Chosen by the user over "always escalate" and over "answer and still
  notify staff".
Trade-offs: staff text is now trusted for sensitive topics, so a careless
staff entry reaches parents directly (mitigation: entries are visible
and editable in the KB tab, marked "Staff-written"); an answer mixing
staff and seeded facts still escalates (conservative). Also noted: the
operator's entry ("doctor's note required") contradicted the seeded
Illness Policy ("24 hours fever-free") — the system has no conflict
detection between KB entries (see limitations).

### 29. Out-of-scope questions skip sensitivity classification — 2026-10-01
**Revised 2026-10-01 → see #38:** out-of-scope questions are now classified.
(Architecture item B; kept as specced, user didn't change it when asked.)
When nothing clears the similarity floor, no LLM call runs — including
the sensitivity classifier. The question still escalates, and urgency
(keywords, free) is still detected.
Trade-off: an off-handbook question that *is* sensitive is logged as not
sensitive, so it ranks lower in the operator's triage queue than it
should. Running the classifier on out-of-scope questions would fix the
ranking at one extra LLM call each — in tension with the "prefer false
positives" stance of #18.

### 30. Unverifiable answers escalate: zero claimed facts → adherence 0 — 2026-10-01
(Architecture item C.) If the model makes no checkable claim, nothing can
be verified, so adherence is 0 and the question escalates. This is also
how the system reacts when the model says "I'm not sure" (it's told to
return no facts then). Trade-off: a correct but fact-free answer
("Yes, we'd love to have you visit!") escalates.

### 31. Failure handling: one retry, then escalate; fail fast without a key — 2026-10-01
(Architecture item E + backend-plan defaults.)
- Gemini 429/5xx gets one retry after 2s; any remaining failure becomes
  `escalation_reason = system_error`. The parent sees the normal
  escalation message; the row is still logged with whatever ran before
  the failure.
- KB writes that can't re-embed return 503 and write nothing (a chunk
  and its embedding never disagree; the question stays unresolved).
- The app refuses to start without `GEMINI_API_KEY` — a misconfigured
  deploy crashes visibly instead of escalating every question (this is
  exactly how the first Render deploy failed, #24).
Trade-off: during a Gemini outage every question escalates; there is no
cached or degraded answering mode.

### 32. Generation runs even for sensitive questions — 2026-10-01
(Architecture item F.) The would-have-been answer is generated and
logged so the operator sees what the bot would have said, and #28 needs
it to decide whether staff entries cover the question. Trade-off: one
LLM call per sensitive question whose answer the parent usually never
sees.

### 33. Retrieval shape: one handbook entry = one chunk, 768 dims, shared context — 2026-10-01
- No automatic text splitting: each handbook entry (seeded or staff-
  written) is exactly one chunk, embedded as `title + content` with
  `gemini-embedding-001` at 768 dimensions (architecture item H — ample
  for ~20 chunks, smaller rows). Every write re-embeds before saving.
- Generation and the adherence check receive the **same** filtered
  context (`retrieval.relevant()`), so facts are checked against exactly
  what the model saw.
Trade-off: a long entry covering several topics gets one "blurred"
vector. Observed live: "What is your sunscreen policy?" escalates as out
of scope because sunscreen is one sentence inside the Medication entry.
Fix is editorial (one topic per entry) or automatic splitting for long
documents.

### 34. What the parent sees, and how staff add answers — 2026-10-01
- Answered questions show "From the handbook: <title>" only for chunks
  that backed a verified fact (architecture item K) — sources are
  evidence, not just "what was retrieved".
- "Add answer to handbook" from a question always creates a **new**
  staff entry (architecture item M); editing existing entries happens in
  the Knowledge base tab. Keeps each fix small and focused (#33).

### 35. No auth on the operator dashboard — 2026-10-01
(Architecture item J; CLAUDE.md out of scope.) Anyone with the URL can
read the question log and edit the knowledge base — and since #27 those
edits persist and, since #28, staff-written entries can answer
sensitive questions. Acceptable for a fictional-data demo; it is the
first thing a real deployment would need.

### 36. Testing strategy — 2026-10-01
- One test file per component (adherence, urgency, triage, sensitivity,
  retrieval, generation, data layer, pipeline, API); every backend change
  is tested in the same step (rule in CLAUDE.md). 148 tests, no network.
- Gemini is faked: a deterministic bag-of-words embedder and a generator
  that fails loudly on unexpected calls (proves out-of-scope makes no LLM
  calls).
- API tests compare response keys with the frontend mock's, so the two
  can't drift.
Trade-off: the fake embedder can't judge retrieval *quality* — that is
measured only by calibration (#21) and live runs against real Gemini,
which aren't automated (they'd need a key and quota in CI).

### 37. Sensitive + verified: show the answer AND notify staff — revises #8 — 2026-10-01
Found in the deployed demo: "my child is sick, what do I do?" had a fully
grounded would-have-been answer (absence reporting by 9:00 AM via the
app or (555) 014-2200, plus the fever / vomiting exclusion rules), yet
the parent only saw "staff has been notified". The user asked "why not
do both" — reversing their original #8 ("do not do anything else").

Rule now: when the *only* reason to escalate is sensitivity, and the
answer passed every mechanical check (all claimed facts matched, no
unsupported numbers, combined ≥ 0.80), the parent sees the answer with
its sources plus "I've also shared your question with the Little Acorns
staff. If it's urgent, call (555) 014-2200." The question still escalates
into the staff queue; `question_log.answer_shown` records that the
parent saw it.

Unchanged: out-of-scope, below-threshold, system-error, and sensitive
questions whose answer didn't fully verify show only the staff message —
an unverified answer is never shown (that would defeat #3 and #23).

Trade-offs: parents now get handbook policy on sensitive topics without a
human first — the original worry behind #8 (a parent acting on the
automated part). Mitigated by: only verified handbook content is shown,
the staff notice and phone number are always attached, and staff still
review every such question. The rationale shifted because a dead-end
"staff notified" proved worse for an anxious parent than a grounded,
clearly-sourced policy answer.

### 38. Out-of-scope questions are still classified for sensitivity — revises #29 / CLAUDE.md step 2 — 2026-10-01
Found in the deployed demo: "my child is currently experiencing bullying,
can we get counseling?" matched nothing in the handbook, so the
out-of-scope short-circuit skipped every LLM call — including the
sensitivity classifier. It escalated, but as plain "Not in handbook":
no sensitive badge, bottom triage tier. Sensitive topics are often
exactly the ones a handbook doesn't cover, so the short-circuit hid the
signal staff most need. (This was flagged as a trade-off twice during the
build and kept as specced until the user hit it.)

Rule now: out-of-scope questions run the classifier (one call) but still
skip generation (nothing to ground an answer in). The log keeps both
signals — `escalation_reason = out_of_scope` (why there's no answer) and
`is_sensitive` / category (how urgently to look) — and triage ranks by
sensitivity as usual. If the classification call fails, the question
still escalates as `out_of_scope` (not `system_error`): the classifier
is extra information here, not a requirement.

Trade-off: one LLM call per out-of-scope question, including greetings
and gibberish; the original "spend no calls on irrelevant questions"
saving is reduced from two calls to one.

### 39. Conversational tone in the generation prompt — 2026-10-01
The user rewrote the generation system prompt to sound like a warm person
at the front desk rather than a policy lookup: vary phrasing, plain
prose, and open with one brief acknowledgment ("I'm sorry to hear that")
only when the question is about a child being unwell, upset, or
struggling. Tone sits on top of unchanged hard rules: excerpts only,
digits exactly as written (the number check depends on it, #23), say
plainly when unsure, and the empathy line is excluded from
`claimed_facts` (it isn't a factual claim, so it can't fail adherence).
Trade-off: a warmer model has more room to add unlisted, non-numeric
filler — still only partially covered by verification (#23 limits).

### 40. Greetings and thanks handled before the pipeline — 2026-10-01
"hello" used to fall through retrieval, fail the floor, and land in the
staff queue as "Not in handbook" (#38 even spent a classifier call on
it). Now `backend/small_talk.py` replies to a message that is *only* a
greeting ("hi", "good morning", "hey there!") or thanks ("thank you so
much") with a friendly canned line — no retrieval, no LLM, no staff
notification — and logs it as answered.
Based on the user's `GREETING_PATTERNS` / `is_greeting`, with one fix:
matching is whole-word. The original prefix match (`startswith("hi")`
on ≤3 words) would have treated "high fever today" or "history of the
center?" as greetings — a sick-child message answered with "Hi there!".
A greeting followed by a real question ("hi, my child is sick") still
goes through the full pipeline.
Trade-offs: canned replies (no variety); exact phrase lists miss
creative small talk ("yo", "morning!!") — those fall back to the old
out-of-scope path, which fails safe.

### 41. Soft openers on sensitive escalations — 2026-10-01
When a sensitive question escalates *without* an answer shown, the
staff-notified message now opens with a short, category-specific line
(user's `SENSITIVITY_OPENERS`): health → "I'm sorry to hear your little
one isn't feeling well.", emotional_social → "I'm sorry to hear that —
that sounds hard.", allergies → "Thanks for flagging that — allergies
are something we take seriously."; safety and custody_legal get none
(an opener can read as presumptuous there). Not added when a verified
answer is shown (#37) — the generation prompt already opens with an
acknowledgment (#39), so it would double up.
Trade-off: the opener follows the classifier's *category*, not the
specific wording — a health-tagged question that isn't about illness
(e.g. medication paperwork scored 3+) would get "isn't feeling well".

### 42. Handbook gaps: share the related policy, escalate the gap — 2026-10-01
Found in the deployed demo: "my kid has a runny nose, can he come in? he
seems fine otherwise" got "I'm not sure" — correct but a dead end. The
handbook's Illness Policy names specific exclusions (fever 100.4°F+,
vomiting, diarrhea, pink eye) and says nothing about mild cold symptoms.
The user asked whether the model should "intuitively" apply the illness
policy. It can't do so honestly: "sick → stay home" over-applies the
policy (sends a well kid home on the bot's say-so) and "not listed → can
come" infers from silence — either way the bot would be making the
center's health call. Retrieval was fine (Illness Policy ranked 1st);
raising TOP_K would only add below-floor chunks.

Rule now: when the excerpts contain a closely related policy but don't
fully answer, the model shares what the policy actually says, states
clearly what it doesn't cover, and never concludes yes/no from what's
left out. It reports `fully_answers_question` as a **structured field**
(no free-text parsing). A verified partial answer is shown with the
system's staff note and escalates as `partial_answer` ("Handbook gap") so
the gap reaches the dashboard. The model is told never to claim it
contacted staff — the system adds that note only when it's true.
Without this field, a non-sensitive partial answer could pass every check,
be logged as answered, promise nothing, and hide the gap from staff.

Trade-offs: relies on the model's self-report of completeness (a model
that overclaims "fully answered" just behaves like before — answered, no
escalation; facts are still verified either way); more questions reach
the staff queue; the real fix for a recurring gap is still content (e.g.
add a mild-symptoms line to the Illness Policy via the dashboard).

### 43. New wording for message-only escalations — revises #25's text — 2026-10-01
Chosen by the user: "Thank you for your inquiry, sorry I am unable to answer the question, you can reach out to (555) 014-2200 to get your question answered!" — replacing "Thanks for your question. I've
notified the Little Acorns staff about it. If it's urgent, call (555)
014-2200." The "Sent to staff" label above the bubble is removed too.
Behaviour is unchanged: the question still escalates into the staff queue
and the phone number is still the next step.
Trade-offs: the parent is no longer told staff have the question, so they
may call about something staff are already looking at (duplicate effort,
but never a dead end); the sensitive openers (#41) now read e.g. "I'm
sorry to hear that — that sounds hard. Thank you for your inquiry, sorry I
am unable…", with two apologies in a row. The staff note under a shown
answer (#37, #42) still says staff were notified, which is true there.

### 44. Urgency judged in context, in the existing classifier call — revises #5 — 2026-10-01
Found in the deployed demo: "how is the weather today?" was flagged
**Urgent** because "today" is a keyword; meanwhile "No one can pick up my
child after school, can someone take care of him?" was *not* flagged
because "after school" isn't. Keywords can't tell "today" as small talk
from "today" as a same-day problem. The user asked for urgency that takes
full context.

Rule now: the sensitivity classifier (already one structured call per
question, including out-of-scope ones since #38) also returns `is_urgent`
and a one-line `urgency_reason`, defined as "needs staff attention today
because of a child or family situation" (same-day pickup problems, a
child unwell at the center, a safety issue now, a deadline today that
the parent can't meet). The static keyword list in `urgency.py` remains
only as a fallback when that call fails (or for small talk, which skips
it). `urgency_reason` is stored and shown on the dashboard.
- Kept from #5: no separate LLM call (zero added cost/latency) and no
  dynamic date resolution ("this Friday" is still not resolved).
- Changed from #5: urgency is now a model judgement, not a fixed rule —
  less predictable and only testable with a fake classifier; the keyword
  tests now cover the fallback.
Trade-offs: the classifier can be wrong in both directions; a failure
silently drops back to the cruder keyword behaviour.

### 45. Conversation context: follow-ups are rewritten as standalone questions — 2026-10-01
Every message used to be answered in isolation, so a follow-up like "Can
they be picked up by Uber?" (after "Can my child be picked up by another
parent? I'm stuck at work") reached retrieval with no idea who "they" are.

Design (zero extra LLM calls):
- The parent page sends the last 3 exchanges (6 turns) as `history` with
  each question. The server stays stateless; history is stored in the log
  row only so staff can see what the question meant.
- The classifier call — which already runs on every non-small-talk
  question (#38) — moves **before** retrieval and also returns
  `standalone_question`: the latest message rewritten to be
  self-contained using the conversation. Seeing the conversation also
  improves sensitivity and urgency ("stuck at work" + pickup → urgent).
- Retrieval and generation use the standalone question. Generation also
  sees the conversation for continuity, but is told it's never a source of
  facts; adherence still verifies every fact against retrieved chunks only.
- The dashboard shows "Asked as" vs "Interpreted as" plus the prior turns.
- If classification fails, the original message is used for retrieval and
  urgency falls back to keywords (in-scope questions still become
  `system_error`, as before, because sensitivity is unknown).
- The classifier sees prior *assistant* replies (which can quote handbook
  content) only as conversation context — it still never receives the
  retrieved chunks for the current question.

Trade-offs: retrieval now depends on the model's rewrite — a bad rewrite
retrieves the wrong policy (visible on the dashboard as Interpreted as);
history is client-supplied, so it's untrusted context (fine for a demo,
would need server-side sessions in production); only the last 3 exchanges
are kept; small talk still skips everything, so "thanks!" mid-conversation
doesn't consume context.

**Found while testing #45 (prompt fix for #42):** the rewritten Uber
follow-up produced a good partial answer ("our handbook doesn't mention
Uber drivers, but children are released only to authorized pick-ups…")
with **zero** `claimed_facts` — the model treated "partly covered" like
"not covered" — so it couldn't verify and wasn't shown, and the behaviour
was flaky across runs. The generation prompt now says partial answers must
still list every fact they state from the policy; 3/3 live runs then
showed the answer with its source and staff note.

---

## Known limitations and trade-offs (summary for the write-up)

Grouped; numbers point to the decisions above.

**Answer quality and grounding**
- Non-numeric claims are verified only if the model lists them in
  `claimed_facts`; numbers in the answer text are always checked (#23).
- A spelled-out number evades the number check if the model ignores the
  digits instruction (#23).
- A number the parent typed and the bot echoes ("until 6:30") is flagged
  if the handbook lacks it — conservative false positive (#23).
- TOP_K = 2 can leave half of a two-topic question unanswered
  (incomplete, not wrong) (#20).
- One-chunk-per-entry blurs multi-topic entries (sunscreen miss) (#33).
- Correct but fact-free answers escalate (#30).
- Lite model (`gemini-3.5-flash-lite`) — chosen for free-tier
  availability, not quality (#22).

**Escalation and sensitivity**
- Sensitivity is an LLM judgement; a sensitive question scored 2/5 can
  be answered if grounded (#25). Score 3+ escalates — staff will see
  questions the bot could have answered (accepted: false positives over
  false negatives, #18).
- Staff-written entries are trusted for sensitive topics (#28); no review
  step or conflict detection — e.g. a staff entry ("doctor's note
  required") contradicted the seeded Illness Policy ("24 hours
  fever-free") and nothing flagged it.
- Out-of-scope questions cost one LLM call (sensitivity) even when
  they're off-topic noise (#38).
- Small talk is matched against fixed phrase lists; creative greetings
  ("yo", "morning!!") still fall through to out-of-scope (#40).
- Nonsense input (e.g. keyboard smash like "asdfjkl;") is treated like
  any off-topic question: it fails the similarity floor and lands in the
  staff dashboard as "Not in handbook". Minor edge case — parents asking
  a daycare's front desk rarely send gibberish — but with more time we'd
  filter it before it reaches staff (e.g. a cheap mechanical check for
  too few real words, answered with a "Sorry, I didn't catch that"
  prompt instead of an escalation).
- Emergencies get the staff notice + phone number (and the handbook
  policy if it verifies, #37); no 911 / emergency routing.
- Sensitive policy answers reach parents before a human reviews them
  (verified handbook content only, staff still notified) (#37).
- No follow-up channel to the parent who asked; fixes help the *next*
  parent (#9, #17).
- Urgency is an LLM judgement (#44): can be wrong either way; the
  keyword fallback (used on classifier failure) is crude; still no date
  resolution ("this Friday").

**Operations and platform**
- Paid instance + disk: small cost, a few seconds of downtime per
  redeploy, no horizontal scaling (#27).
- `data/handbook.json` changes don't reach an existing deployed DB (seed
  only on empty) (#27).
- No auth on the dashboard (#35).
- Free-tier Gemini: full Flash models were overloaded (503); quota limits
  apply; outages turn every question into a system-error escalation (#22, #31).
- Retrieval thresholds calibrated on 27 hand-written questions with a
  ~0.04 gap between on- and off-topic — needs re-checking as the
  handbook grows (#21).
- Conversation memory is the last 3 exchanges, client-supplied; a bad
  standalone rewrite misdirects retrieval (#45).
- Retrieval quality isn't covered by automated tests (#36).
