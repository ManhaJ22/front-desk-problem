import { useState } from "react";
import { categoryLabel, fmtScore, reasonDetail, timeAgo } from "../display.js";
import { Badges } from "./QuestionQueue.jsx";
import ChunkEditor from "./ChunkEditor.jsx";

function Score({ label, value, hint }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="score">
      <div className="score-head">
        <span>{label}</span>
        <span className="score-value">{fmtScore(value)}</span>
      </div>
      <div className="meter" aria-hidden="true">
        <div className="meter-fill" style={{ width: `${pct}%` }} />
      </div>
      {hint && <span className="score-hint">{hint}</span>}
    </div>
  );
}

export default function QuestionDetail({ question: q, chunks, onResolve, onAddToKb, onBack }) {
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const titleOf = (id) => chunks.find((c) => c.id === id)?.title ?? `${id} (deleted)`;
  const unmatched = new Set(q.unmatched_facts);
  // Sensitive questions always escalate (decision log #18), whatever the score.
  const sensitive = q.is_sensitive;
  const actionable = q.escalated && !q.resolved;

  async function run(fn) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      setAdding(false);
    } catch {
      setError("That didn't save. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="detail">
      <button type="button" className="btn btn-link back" onClick={onBack}>
        ← All questions
      </button>

      <Badges q={q} />
      <blockquote className="detail-question">{q.question}</blockquote>
      <p className="muted">
        Asked {timeAgo(q.created_at)}
        {q.escalated && <> · {reasonDetail(q)}</>}
      </p>

      <section>
        <h3>{q.answer_shown ? "What the parent saw" : "What the assistant would have said"}</h3>
        {q.answer ? (
          <p className="detail-answer">{q.answer}</p>
        ) : (
          <p className="muted">No answer was generated.</p>
        )}
        {q.escalated && (
          <p className="muted small">
            {q.answer_shown
              ? "The answer was fully verified, so the parent saw it along with a note that staff were notified."
              : 'The parent only saw the "staff has been notified" message.'}
          </p>
        )}
      </section>

      {q.claimed_facts.length > 0 && (
        <section>
          <h3>Facts checked against the handbook</h3>
          <ul className="facts">
            {q.claimed_facts.map((f) => (
              <li key={f} className={unmatched.has(f) ? "fact-miss" : "fact-ok"}>
                <span aria-hidden="true">{unmatched.has(f) ? "✗" : "✓"}</span>
                <span className="visually-hidden">{unmatched.has(f) ? "Not found:" : "Found:"}</span> {f}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h3>Confidence</h3>
        <div className="scores">
          <Score label="Retrieval match" value={q.semantic_score} />
          <Score label="Facts supported" value={q.adherence_score} />
          <Score
            label="Combined"
            value={q.combined_score}
            hint={
              sensitive
                ? !q.escalated
                  ? "Sensitive — answered from a staff-written entry"
                  : q.answer_shown
                    ? "Sensitive — answered and sent to staff"
                    : "Sensitive — sent to staff"
                : q.threshold_used != null
                  ? `Needs ${fmtScore(q.threshold_used)} to answer`
                  : null
            }
          />
        </div>
      </section>

      {q.sensitivity_category && (
        <section>
          <h3>Sensitivity</h3>
          <p>
            {categoryLabel(q.sensitivity_category)} · {q.sensitivity_score}/5
            {q.sensitivity_rationale && <span className="muted"> — {q.sensitivity_rationale}</span>}
          </p>
        </section>
      )}

      <section>
        <h3>Handbook sections used</h3>
        {q.retrieved_chunk_ids.length ? (
          <ul className="plain-list">
            {q.retrieved_chunk_ids.map((id) => (
              <li key={id}>{titleOf(id)}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">None matched.</p>
        )}
      </section>

      {actionable && (
        <section className="detail-actions">
          {error && <p className="form-error">{error}</p>}
          {adding ? (
            <ChunkEditor
              initial={{ category: "faq", title: q.question, content: "" }}
              submitLabel="Add to handbook & resolve"
              saving={busy}
              note={
                sensitive
                  ? "This is a sensitive question. Once it's in the handbook as a staff-written entry, the assistant can answer it next time — but only if every fact in its answer comes from staff-written entries."
                  : "Next time a parent asks this, the assistant can answer from this entry."
              }
              onSave={(data) => run(() => onAddToKb(q.id, data))}
              onCancel={() => setAdding(false)}
            />
          ) : (
            <>
              <div className="actions">
                <button type="button" className="btn btn-primary" onClick={() => setAdding(true)}>
                  Add answer to handbook
                </button>
                <button type="button" className="btn" onClick={() => run(() => onResolve(q.id))} disabled={busy}>
                  {busy ? "Saving…" : "Mark resolved"}
                </button>
              </div>
              <p className="muted small">Or leave it here — it stays in Needs review.</p>
            </>
          )}
        </section>
      )}
    </article>
  );
}
