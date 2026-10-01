import { useState } from "react";
import { KB_CATEGORIES } from "../api.js";
import { timeAgo } from "../display.js";
import ChunkEditor from "./ChunkEditor.jsx";

export default function KnowledgeBase({ chunks, onCreate, onUpdate, onDelete }) {
  const [editingId, setEditingId] = useState(null); // chunk id, "new", or null
  const [confirmId, setConfirmId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function run(fn) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      setEditingId(null);
      setConfirmId(null);
    } catch {
      setError("That didn't save. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const known = new Set(KB_CATEGORIES);
  const categories = [...KB_CATEGORIES, ...new Set(chunks.map((c) => c.category).filter((c) => !known.has(c)))];
  const groups = categories
    .map((cat) => [cat, chunks.filter((c) => c.category === cat)])
    .filter(([, list]) => list.length > 0);

  return (
    <section className="kb" aria-label="Knowledge base">
      <div className="kb-head">
        <p className="muted">
          This is the assistant's source of truth. It only answers from what's written here.
        </p>
        {editingId !== "new" && (
          <button type="button" className="btn btn-primary" onClick={() => setEditingId("new")}>
            + Add entry
          </button>
        )}
      </div>

      {error && <p className="form-error">{error}</p>}

      {editingId === "new" && (
        <div className="card">
          <ChunkEditor
            submitLabel="Add entry"
            saving={busy}
            onSave={(data) => run(() => onCreate(data))}
            onCancel={() => setEditingId(null)}
          />
        </div>
      )}

      {groups.length === 0 && <p className="empty">The handbook is empty.</p>}

      {groups.map(([cat, list]) => (
        <div key={cat} className="kb-group">
          <h3 className="kb-category">{cat}</h3>
          {list.map((c) => (
            <div key={c.id} className="card">
              {editingId === c.id ? (
                <ChunkEditor
                  initial={c}
                  saving={busy}
                  onSave={(data) => run(() => onUpdate(c.id, data))}
                  onCancel={() => setEditingId(null)}
                />
              ) : (
                <>
                  <div className="card-head">
                    <h4>{c.title}</h4>
                    <span className="muted small">Updated {timeAgo(c.updated_at)}</span>
                  </div>
                  <p className="card-content">{c.content}</p>
                  {confirmId === c.id ? (
                    <div className="actions confirm">
                      <span>Delete this entry? The assistant will stop using it.</span>
                      <button
                        type="button"
                        className="btn btn-danger"
                        onClick={() => run(() => onDelete(c.id))}
                        disabled={busy}
                      >
                        Delete
                      </button>
                      <button type="button" className="btn" onClick={() => setConfirmId(null)} disabled={busy}>
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div className="actions">
                      <button type="button" className="btn" onClick={() => setEditingId(c.id)}>
                        Edit
                      </button>
                      <button type="button" className="btn btn-link" onClick={() => setConfirmId(c.id)}>
                        Delete
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      ))}
    </section>
  );
}
