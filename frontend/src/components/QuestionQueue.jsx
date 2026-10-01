import { categoryLabel, reasonLabel, timeAgo } from "../display.js";

export function Badges({ q }) {
  return (
    <span className="badges">
      {q.is_urgent && <span className="badge badge-urgent">Urgent</span>}
      {q.is_sensitive && (
        <span className="badge badge-sensitive">
          Sensitive
          {q.sensitivity_category && q.sensitivity_category !== "none" && ` · ${categoryLabel(q.sensitivity_category)}`}
        </span>
      )}
      <span className={`badge ${q.escalated ? "badge-reason" : "badge-answered"}`}>{reasonLabel(q)}</span>
      {q.resolved && <span className="badge badge-resolved">Resolved</span>}
    </span>
  );
}

export default function QuestionQueue({ questions, view, onViewChange, selectedId, onSelect, loading }) {
  return (
    <section className="queue" aria-label="Questions">
      <div className="segmented" role="group" aria-label="Filter questions">
        <button
          type="button"
          className={view === "needs_review" ? "active" : ""}
          aria-pressed={view === "needs_review"}
          onClick={() => onViewChange("needs_review")}
        >
          Needs review
        </button>
        <button
          type="button"
          className={view === "all" ? "active" : ""}
          aria-pressed={view === "all"}
          onClick={() => onViewChange("all")}
        >
          All questions
        </button>
      </div>

      {loading && questions.length === 0 ? (
        <p className="empty">Loading…</p>
      ) : questions.length === 0 ? (
        <p className="empty">
          {view === "needs_review" ? "Nothing needs review 🎉" : "No questions yet."}
        </p>
      ) : (
        <ul className="queue-list">
          {questions.map((q) => (
            <li key={q.id}>
              <button
                type="button"
                className={`queue-row priority-${q.escalated && !q.resolved ? q.priority : "none"} ${
                  q.id === selectedId ? "selected" : ""
                }`}
                onClick={() => onSelect(q.id)}
              >
                <Badges q={q} />
                <span className="queue-question">{q.question}</span>
                <span className="queue-time">{timeAgo(q.created_at)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
