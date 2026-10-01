// Thin wrappers over the backend API contract (docs/architecture.md).
// With VITE_USE_MOCKS=true (`npm run dev:mock`) every call goes to
// mockApi.js instead — dev only, never set in production builds.

export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";

// Mirrors app/config.py. Keep in sync.
export const KB_CATEGORIES = [
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
];
export const CENTER_PHONE = "(555) 014-2200";

async function mock() {
  return import("./mockApi.js");
}

async function request(method, path, body) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    throw new Error(`${method} ${path} failed: ${res.status}`);
  }
  return res.status === 204 ? null : res.json();
}

export async function ask(question) {
  if (USE_MOCKS) return (await mock()).ask(question);
  return request("POST", "/ask", { question });
}

export async function listQuestions(view = "needs_review") {
  if (USE_MOCKS) return (await mock()).listQuestions(view);
  return request("GET", `/operator/questions?view=${encodeURIComponent(view)}`);
}

export async function resolveQuestion(id) {
  if (USE_MOCKS) return (await mock()).resolveQuestion(id);
  return request("POST", `/operator/questions/${id}/resolve`);
}

export async function addToKb(id, chunk) {
  if (USE_MOCKS) return (await mock()).addToKb(id, chunk);
  return request("POST", `/operator/questions/${id}/add-to-kb`, chunk);
}

export async function listChunks() {
  if (USE_MOCKS) return (await mock()).listChunks();
  return request("GET", "/operator/kb");
}

export async function createChunk(chunk) {
  if (USE_MOCKS) return (await mock()).createChunk(chunk);
  return request("POST", "/operator/kb", chunk);
}

export async function updateChunk(id, chunk) {
  if (USE_MOCKS) return (await mock()).updateChunk(id, chunk);
  return request("PUT", `/operator/kb/${encodeURIComponent(id)}`, chunk);
}

export async function deleteChunk(id) {
  if (USE_MOCKS) return (await mock()).deleteChunk(id);
  return request("DELETE", `/operator/kb/${encodeURIComponent(id)}`);
}

export async function getStats() {
  if (USE_MOCKS) return (await mock()).getStats();
  return request("GET", "/operator/stats");
}
