import { useEffect, useRef, useState } from "react";
import { ask, CENTER_PHONE } from "../api.js";
import ChatMessage from "../components/ChatMessage.jsx";
import SuggestedQuestions from "../components/SuggestedQuestions.jsx";

const MAX_LEN = 500;
const HISTORY_TURNS = 6; // last 3 exchanges sent as context (decision log #45)
const SHORT_STAFF_NOTE = "Our staff have this one too.";

// Chat bubbles -> the turns the backend uses to understand follow-ups. Errors aren't sent.
function toHistory(messages) {
  return messages
    .filter((m) => m.kind !== "error")
    .map((m) => ({ role: m.kind === "parent" ? "parent" : "assistant", text: m.text }))
    .slice(-HISTORY_TURNS);
}
const ERROR_TEXT = `Sorry, something went wrong — please try again or call ${CENTER_PHONE}.`;

export default function ParentChat() {
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  // The input is disabled while sending; refocus once it's enabled again.
  useEffect(() => {
    if (!sending && messages.length > 0) inputRef.current?.focus();
  }, [sending, messages.length]);

  async function send(text) {
    const question = text.trim();
    if (!question || sending) return;
    const history = toHistory(messages); // before adding the new question
    // Full staff note once per conversation; later turns get a short version (decision log #46).
    const noteShownBefore = messages.some((m) => m.note);
    setMessages((m) => [...m, { kind: "parent", text: question }]);
    setDraft("");
    setSending(true);
    try {
      const res = await ask(question, history);
      setMessages((m) => [
        ...m,
        res.answer
          ? // Answered, or a sensitive question with a verified answer + staff note (decision log #37).
            {
              kind: "answer",
              text: res.answer,
              sources: res.sources,
              note: res.escalated ? (noteShownBefore ? SHORT_STAFF_NOTE : res.message) : null,
            }
          : { kind: "escalated", text: res.message },
      ]);
    } catch {
      setMessages((m) => [...m, { kind: "error", text: ERROR_TEXT }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="parent-page">
      <header className="parent-header">
        <span className="logo" aria-hidden="true">🌰</span>
        <div>
          <h1>Little Acorns</h1>
          <p className="subtitle">Front Desk</p>
        </div>
      </header>

      <main className="chat" aria-live="polite">
        <div className="bubble bubble-answer welcome">
          Hi! I can answer questions about hours, tuition, meals, and center policies,
          straight from the Little Acorns family handbook. If I'm not sure, or it's
          something our staff should handle, I'll pass your question along to them.
        </div>

        {messages.length === 0 && <SuggestedQuestions onPick={send} disabled={sending} />}

        {messages.map((m, i) => (
          <ChatMessage key={i} message={m} />
        ))}

        {sending && (
          <div className="bubble bubble-answer typing" role="status">
            Checking the handbook…
          </div>
        )}
        <div ref={endRef} />
      </main>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          send(draft);
        }}
      >
        <label htmlFor="question" className="visually-hidden">
          Your question
        </label>
        <input
          id="question"
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          maxLength={MAX_LEN}
          placeholder="Ask a question…"
          autoComplete="off"
          disabled={sending}
        />
        <button type="submit" className="btn btn-primary" disabled={sending || !draft.trim()}>
          Send
        </button>
        {draft.length > MAX_LEN - 100 && (
          <span className="char-count">
            {draft.length}/{MAX_LEN}
          </span>
        )}
      </form>
    </div>
  );
}
