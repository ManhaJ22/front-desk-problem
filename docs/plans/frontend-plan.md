# Frontend Plan

Status: **Built and verified against the mock API, 2026-10-01.** Still to do: the live
check against the real backend, and the forced-score hint fix (see `backend-plan.md` §4). Parent follow-up is out of
scope (decision #17): operator actions are Add to KB, Mark resolved, or
leave it.

This plan covers how and in what order the frontend gets built. *What*
each file contains is defined in `docs/architecture.md` (Frontend section
and API contract); this plan doesn't repeat it, except where it adds
detail.

---

## 1. Check against the spec

| Requirement (source) | How the frontend meets it | OK? |
|---|---|---|
| Parent can ask a question (assignment) | Text input plus chips for the 5 Brightwheel example questions | ✅ |
| Answer is specific and feels trustworthy (assignment) | Answer bubble with "From the handbook: <title>" tags (architecture K) | ✅ |
| Every escalation shows the parent **only** "staff has been notified" (CLAUDE.md, decision #8) | The escalation bubble renders `message` and nothing else. No answer, scores, or excerpt, whatever `escalation_reason` is (the parent API doesn't return a reason) | ✅ |
| Mobile-friendly (assignment) | Mobile-first CSS; parent view fits a 375px width; operator view stacks list then detail on narrow screens (decision #16) | ✅ |
| Operator can edit the source of truth (assignment) | Knowledge Base tab: add, edit, delete chunks | ✅ |
| Operator sees what's asked and where it struggled (assignment) | Questions tab with *Needs review* and *All* views, StatsBar with escalations by reason, detail panel with scores and ✓/✗ facts | ✅ |
| Easy to improve over time (assignment, decision #9) | "Add answer to KB" from any question → new chunk + resolved | ✅ |
| KB editing and question review are **separate** sections (non-negotiable) | Two tabs; the only link between them is the Add-to-KB action | ✅ |
| Triage priority sensitive+urgent > urgent > sensitive > neither (CLAUDE.md) | The backend sorts (`triage.sort_queue`); the frontend keeps the server's order and shows the urgent/sensitive badges | ✅ |
| Signals kept separate (CLAUDE.md) | Urgent, sensitive, and confidence are shown as separate badges and scores, never as one combined indicator | ✅ |
| No auth (out of scope) | `/operator` is open; no login screen | ✅ |

**No conflicts found.** Two things are worth seeing before the build.
Neither one blocks it:
- **Network-error copy.** When the API can't be reached, the parent sees
  "Sorry, something went wrong — please try again or call (555) 014-2200."
  This isn't an escalation (nothing was logged and staff weren't
  notified), so it says so honestly rather than reusing the "staff has
  been notified" message.
- **Example chips include escalating questions.** The fever chip will
  always produce the staff-notified message. I'm keeping it: it shows an
  evaluator the escalation path in one tap.

## 2. Dev-only mock API (decision #15)
- `VITE_USE_MOCKS=true npm run dev` → `api.js` calls go to `mockApi.js`.
- `mockApi.js` holds questions and KB chunks in memory, seeded with
  about 6 example questions (one for each escalation reason, plus
  answered ones; one sensitive+urgent) and a few chunks taken from
  `data/handbook.json`.
- The mock's `ask()` uses a canned keyword table to return each kind
  of outcome on demand:
  `fever / allergic / custody` → `sensitive_forced`;
  `veterans / tuition / tour / lunch` → answered with sources;
  `weather on mars`-style misses → `out_of_scope`;
  `sibling` → `below_threshold`; `__error` → throws. A 600 ms delay so the
  loading state is visible.
- New questions asked in the mock show up in the operator queue, so
  the whole loop can be clicked through end to end.
- Never imported in production: `api.js` checks the env flag; the
  Render build doesn't set it.

## 3. Build order
1. **Scaffold**: `package.json` (react, react-dom, react-router-dom,
   vite, @vitejs/plugin-react, latest versions at install time);
   `vite.config.js` with the `/api` proxy; `index.html` with the viewport
   meta; `main.jsx`; `App.jsx` routes.
2. **`api.js` + `mockApi.js`**: every endpoint in the architecture
   contract, with matching response shapes.
3. **`styles.css`**: CSS variables (warm neutral background, one accent
   color, a calm escalation color that isn't error red, badge colors),
   base type scale, layout helpers, a 640px parent column and a wide
   operator layout.
4. **Parent view**: `ParentChat`, `ChatMessage`, `SuggestedQuestions`.
   States: empty (welcome line + chips), sending (input disabled +
   "Checking the handbook…"), answered, escalated, network error.
   Auto-scroll to the newest message; Enter sends; 500-character limit
   with a counter near the limit.
5. **Operator shell**: `OperatorDashboard` with `StatsBar`, the
   Questions | Knowledge Base tabs, and a Refresh button.
6. **Questions tab**: `QuestionQueue` (view toggle, rows with badges +
   plain-English reason, an empty state "Nothing needs review 🎉"),
   `QuestionDetail` (everything listed in the architecture,
   Resolve / Add-to-KB actions, the forced-category note (N)).
7. **Knowledge Base tab**: `KnowledgeBase` grouped by category,
   `ChunkEditor` reused for add, edit, and Add-to-KB; delete asks for
   confirmation in the page itself (no `window.confirm`).
8. **Polish pass**: keyboard focus styles, `aria-live` on the chat log,
   labels on inputs, a check at a 375px width.

## 4. Display labels (escalation_reason → operator copy)
| Value | Operator label | Detail line |
|---|---|---|
| `out_of_scope` | Not in handbook | Nothing in the handbook matched closely enough. |
| `sensitive_forced` | Sensitive topic | Always sent to staff: <category, or "sensitivity score n/5">. |
| `below_threshold` | Low confidence | Combined <x.xx> was below the 0.80 bar. |
| `partial_answer` | Handbook gap | Answered what the handbook covers; the rest needs staff (#42). |
| `system_error` | System error | The AI service failed; the question was escalated to be safe. |
| (null) | Answered | — |

## 5. Verification
- `npm run build` succeeds with no warnings.
- With mocks on: open `/` and `/operator` in Chrome at desktop width
  and at 375px; click through answered → escalated (each reason) →
  network error → shows in queue → Add to KB → appears in the KB tab →
  resolved disappears from *Needs review*.
- Confirm the escalation bubble never shows answer text, even though
  the mock response for `sensitive_forced` includes a would-have-been
  answer in the operator data.
- After the backend exists: run with mocks off against `uvicorn` and
  repeat the walk-through.
