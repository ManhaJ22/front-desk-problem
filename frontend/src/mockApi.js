// DEV-ONLY in-memory fake of the backend API contract (decision log #15).
// Outcomes are canned by keyword so every UI state can be exercised; they
// say nothing about how the real pipeline decides.

const ESCALATION_MESSAGE =
  "Thank you for your inquiry, sorry I am unable to answer the question, you can reach out to (555) 014-2200 to get your question answered!";
const DELAY_MS = 600;

const wait = () => new Promise((r) => setTimeout(r, DELAY_MS));
const now = () => new Date().toISOString();
const minutesAgo = (m) => new Date(Date.now() - m * 60_000).toISOString();
const clone = (x) => structuredClone(x);

let chunks = [
  {
    id: "holidays",
    category: "calendar",
    title: "Holiday Closures",
    content:
      "Little Acorns is closed on New Year's Day, Martin Luther King Jr. Day, Memorial Day, Juneteenth, Independence Day, Labor Day, Thanksgiving Day and the Friday after, Christmas Eve, and Christmas Day. Little Acorns is OPEN on Veterans Day, Presidents' Day, Columbus Day / Indigenous Peoples' Day, and Good Friday, with normal hours of 7:00 AM to 6:00 PM.",
    source: "handbook",
    updated_at: minutesAgo(3000),
  },
  {
    id: "tuition",
    category: "tuition",
    title: "Monthly Tuition by Age Group",
    content:
      "Full-time monthly tuition: Infants (6 weeks to 12 months) $2,150; Toddlers (12 to 24 months) $1,950; Twos $1,750; Preschool $1,550; Pre-K $1,450.",
    source: "handbook",
    updated_at: minutesAgo(3000),
  },
  {
    id: "enrollment-tours",
    category: "enrollment",
    title: "Enrollment and Scheduling a Tour",
    content:
      "Tours are offered Tuesdays and Thursdays at 9:30 AM and 3:30 PM. To schedule a tour, call (555) 014-2200 or book online at littleacorns.example/tour.",
    source: "handbook",
    updated_at: minutesAgo(3000),
  },
  {
    id: "forgotten-lunch",
    category: "meals",
    title: "Forgotten Lunch / Backup Lunch",
    content:
      "If you forget to pack lunch, the center can provide a backup lunch for $6. Let the front office know by 10:00 AM. The backup lunch is the same every day: a sunflower-butter and jelly sandwich (or a cheese quesadilla), sliced apples, and milk.",
    source: "handbook",
    updated_at: minutesAgo(3000),
  },
  {
    id: "illness-exclusion",
    category: "health",
    title: "Illness and Fever Policy",
    content:
      "Children with a fever of 100.4°F or higher may not attend and must be fever-free for 24 hours without fever-reducing medication before returning.",
    source: "handbook",
    updated_at: minutesAgo(3000),
  },
  {
    id: "late-pickup",
    category: "daily",
    title: "Late Pick-up Fee",
    content:
      "The center closes at 6:00 PM. A late pick-up fee of $1 per minute per child is charged starting at 6:01 PM.",
    source: "handbook",
    updated_at: minutesAgo(3000),
  },
];

const BLANK_LOG = {
  answer: null,
  escalated: false,
  escalation_reason: null,
  is_sensitive: false,
  is_urgent: false,
  urgency_reason: null,
  sensitivity_category: null,
  sensitivity_score: null,
  sensitivity_rationale: null,
  semantic_score: null,
  adherence_score: null,
  combined_score: null,
  threshold_used: null,
  retrieved_chunk_ids: [],
  claimed_facts: [],
  unmatched_facts: [],
  answer_shown: false,
  resolved: false,
};

let nextId = 1;
const log = (fields) => ({ ...BLANK_LOG, id: nextId++, ...fields });

let questions = [
  log({
    created_at: minutesAgo(5),
    question: "My son threw up this morning, can he still come in today?",
    answer:
      "Children must stay home for vomiting and may return 24 hours after the last episode.",
    escalated: true,
    escalation_reason: "sensitive_forced",
    is_sensitive: true,
    is_urgent: true,
    urgency_reason: "The child is unwell and the parent needs to know whether to bring him in today.",
    sensitivity_category: "health",
    sensitivity_score: 5,
    sensitivity_rationale: "Asks whether a child who is currently ill can attend.",
    semantic_score: 0.91,
    adherence_score: 1,
    combined_score: 0.97,
    threshold_used: 0.8,
    retrieved_chunk_ids: ["illness-exclusion"],
    claimed_facts: ["return 24 hours after the last episode"],
  }),
  log({
    created_at: minutesAgo(12),
    question: "I'm running late today, can you keep her until 6:30?",
    answer: "The center closes at 6:00 PM and can stay open until 6:30 PM for late pickups.",
    escalated: true,
    escalation_reason: "below_threshold",
    is_urgent: true,
    sensitivity_category: "none",
    sensitivity_score: 1,
    sensitivity_rationale: "Routine logistics question.",
    semantic_score: 0.78,
    adherence_score: 0.5,
    combined_score: 0.6,
    threshold_used: 0.8,
    retrieved_chunk_ids: ["late-pickup"],
    claimed_facts: ["The center closes at 6:00 PM", "can stay open until 6:30 PM"],
    unmatched_facts: ["can stay open until 6:30 PM"],
  }),
  log({
    created_at: minutesAgo(40),
    question: "My daughter has been crying at drop-off every day lately. Is that normal?",
    answer: "Teachers use positive behavior guidance and will request a family conference if concerns continue.",
    escalated: true,
    escalation_reason: "sensitive_forced",
    is_sensitive: true,
    sensitivity_category: "emotional_social",
    sensitivity_score: 3,
    sensitivity_rationale: "Parent is worried about their child's emotional wellbeing.",
    semantic_score: 0.62,
    adherence_score: 0.5,
    combined_score: 0.54,
    threshold_used: 0.8,
    retrieved_chunk_ids: [],
    claimed_facts: ["positive behavior guidance", "request a family conference"],
    unmatched_facts: ["positive behavior guidance", "request a family conference"],
  }),
  log({
    created_at: minutesAgo(90),
    question: "Do you have a swim program in the summer?",
    escalated: true,
    escalation_reason: "out_of_scope",
    semantic_score: 0,
    retrieved_chunk_ids: [],
  }),
  log({
    created_at: minutesAgo(120),
    question: "Are you open on Veterans Day?",
    answer_shown: true,
    answer:
      "Yes! Little Acorns is open on Veterans Day with normal hours, 7:00 AM to 6:00 PM.",
    sensitivity_category: "none",
    sensitivity_score: 1,
    sensitivity_rationale: "Routine calendar question.",
    semantic_score: 0.95,
    adherence_score: 1,
    combined_score: 0.98,
    threshold_used: 0.8,
    retrieved_chunk_ids: ["holidays"],
    claimed_facts: ["OPEN on Veterans Day", "7:00 AM to 6:00 PM"],
  }),
];

// keyword → canned outcome. First match wins.
const CANNED = [
  { match: /fever|sick|threw up|vomit/, kind: "sensitive", category: "health", chunk: "illness-exclusion" },
  { match: /allerg|epipen|\bnuts?\b|peanut/, kind: "sensitive", category: "allergies", chunk: null },
  { match: /custody|restraining|ex-|court/, kind: "sensitive", category: "custody_legal", chunk: null },
  {
    match: /veteran/,
    kind: "answer",
    chunk: "holidays",
    answer: "Yes! Little Acorns is open on Veterans Day with normal hours, 7:00 AM to 6:00 PM.",
    facts: ["OPEN on Veterans Day", "7:00 AM to 6:00 PM"],
  },
  {
    match: /tuition|cost|how much/,
    kind: "answer",
    chunk: "tuition",
    answer: "Full-time tuition for infants (6 weeks to 12 months) is $2,150 per month.",
    facts: ["Infants (6 weeks to 12 months) $2,150"],
  },
  {
    match: /tour/,
    kind: "answer",
    chunk: "enrollment-tours",
    answer:
      "Tours run Tuesdays and Thursdays at 9:30 AM and 3:30 PM. You can call (555) 014-2200 or book online at littleacorns.example/tour.",
    facts: ["Tuesdays and Thursdays at 9:30 AM and 3:30 PM", "(555) 014-2200"],
  },
  {
    match: /lunch/,
    kind: "answer",
    chunk: "forgotten-lunch",
    answer:
      "Yes — we can provide a backup lunch for $6 if you let the front office know by 10:00 AM. It's a sunflower-butter and jelly sandwich (or a cheese quesadilla), sliced apples, and milk.",
    facts: ["backup lunch for $6", "by 10:00 AM", "sunflower-butter and jelly sandwich"],
  },
  { match: /sibling|discount/, kind: "low", chunk: "tuition" },
  { match: /__error/, kind: "error" },
];

const URGENT = /\b(today|tonight|right now|asap|urgent|emergency|this morning|this afternoon|pick ?up early|picking up early|early pickup|running late|on my way|immediately)\b/;

function chunkTitle(id) {
  return chunks.find((c) => c.id === id)?.title ?? id;
}

export async function ask(question) {
  await wait();
  const q = question.toLowerCase();
  const rule = CANNED.find((r) => r.match.test(q)) ?? { kind: "oos" };
  if (rule.kind === "error") throw new Error("mock network error");

  const base = { created_at: now(), question, is_urgent: URGENT.test(q) };
  let entry;
  if (rule.kind === "answer") {
    entry = log({
      ...base,
      answer_shown: true,
      answer: rule.answer,
      sensitivity_category: "none",
      sensitivity_score: 1,
      sensitivity_rationale: "Routine question.",
      semantic_score: 0.93,
      adherence_score: 1,
      combined_score: 0.98,
      threshold_used: 0.8,
      retrieved_chunk_ids: [rule.chunk],
      claimed_facts: rule.facts,
    });
  } else if (rule.kind === "sensitive") {
    entry = log({
      ...base,
      answer: "(would-have-been answer from the handbook)",
      escalated: true,
      escalation_reason: "sensitive_forced",
      is_sensitive: true,
      sensitivity_category: rule.category,
      sensitivity_score: 5,
      sensitivity_rationale: `Mentions a ${rule.category.replace("_", "/")} topic.`,
      semantic_score: 0.88,
      adherence_score: 1,
      combined_score: 0.96,
      threshold_used: 0.8,
      retrieved_chunk_ids: rule.chunk ? [rule.chunk] : [],
      claimed_facts: ["fever of 100.4°F or higher"],
    });
  } else if (rule.kind === "low") {
    entry = log({
      ...base,
      answer: "Families with two children get a 15% discount on both tuitions.",
      escalated: true,
      escalation_reason: "below_threshold",
      sensitivity_category: "none",
      sensitivity_score: 1,
      sensitivity_rationale: "Routine billing question.",
      semantic_score: 0.7,
      adherence_score: 0,
      combined_score: 0.25,
      threshold_used: 0.8,
      retrieved_chunk_ids: [rule.chunk],
      claimed_facts: ["15% discount on both tuitions"],
      unmatched_facts: ["15% discount on both tuitions"],
    });
  } else {
    entry = log({ ...base, escalated: true, escalation_reason: "out_of_scope", semantic_score: 0 });
  }
  questions.push(entry);

  if (entry.escalated) {
    return { log_id: entry.id, escalated: true, answer: null, message: ESCALATION_MESSAGE, sources: [] };
  }
  return {
    log_id: entry.id,
    escalated: false,
    answer: entry.answer,
    message: null,
    sources: entry.retrieved_chunk_ids.map((id) => ({ id, title: chunkTitle(id) })),
  };
}

function priority(q) {
  if (q.is_sensitive && q.is_urgent) return 1;
  if (q.is_urgent) return 2;
  if (q.is_sensitive) return 3;
  return 4;
}

// Same ordering as backend/triage.py sort_queue.
function sortQueue(rows) {
  return [...rows].sort(
    (a, b) =>
      Number(a.resolved) - Number(b.resolved) ||
      a.priority - b.priority ||
      (a.combined_score ?? -1) - (b.combined_score ?? -1) ||
      b.created_at.localeCompare(a.created_at)
  );
}

export async function listQuestions(view) {
  await wait();
  const rows = questions
    .filter((q) => view === "all" || (q.escalated && !q.resolved))
    .map((q) => ({ ...clone(q), priority: priority(q) }));
  return sortQueue(rows);
}

export async function resolveQuestion(id) {
  await wait();
  const q = questions.find((x) => x.id === id);
  if (!q) throw new Error("not found");
  q.resolved = true;
  return { ...clone(q), priority: priority(q) };
}

function slugify(title) {
  const base = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "chunk";
  let id = base;
  for (let n = 2; chunks.some((c) => c.id === id); n++) id = `${base}-${n}`;
  return id;
}

export async function createChunk({ category, title, content }) {
  await wait();
  const chunk = { id: slugify(title), category, title, content, source: "staff", updated_at: now() };
  chunks.push(chunk);
  return clone(chunk);
}

export async function addToKb(id, data) {
  const chunk = await createChunk(data);
  const question = await resolveQuestion(id);
  return { chunk, question };
}

export async function listChunks() {
  await wait();
  return clone(chunks);
}

export async function updateChunk(id, { category, title, content }) {
  await wait();
  const c = chunks.find((x) => x.id === id);
  if (!c) throw new Error("not found");
  Object.assign(c, { category, title, content, source: "staff", updated_at: now() });
  return clone(c);
}

export async function deleteChunk(id) {
  await wait();
  chunks = chunks.filter((c) => c.id !== id);
  return null;
}

export async function getStats() {
  await wait();
  const by_reason = { out_of_scope: 0, sensitive_forced: 0, below_threshold: 0, partial_answer: 0, system_error: 0 };
  for (const q of questions) if (q.escalation_reason) by_reason[q.escalation_reason]++;
  const escalated = questions.filter((q) => q.escalated).length;
  return {
    total: questions.length,
    answered: questions.length - escalated,
    escalated,
    unresolved: questions.filter((q) => q.escalated && !q.resolved).length,
    by_reason,
  };
}
