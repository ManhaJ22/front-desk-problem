import { useState } from "react";
import { KB_CATEGORIES } from "../api.js";

// Form for creating/editing a handbook chunk. Used by both operator tabs.
export default function ChunkEditor({ initial, onSave, onCancel, saving, submitLabel = "Save", note }) {
  const [category, setCategory] = useState(initial?.category ?? "faq");
  const [title, setTitle] = useState(initial?.title ?? "");
  const [content, setContent] = useState(initial?.content ?? "");
  const valid = title.trim() && content.trim();

  return (
    <form
      className="editor"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid) onSave({ category, title: title.trim(), content: content.trim() });
      }}
    >
      {note && <p className="note">{note}</p>}
      <label>
        Category
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          {KB_CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </label>
      <label>
        Title
        <input value={title} onChange={(e) => setTitle(e.target.value)} required />
      </label>
      <label>
        Content
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          rows={6}
          placeholder="Write it the way the handbook would: specific times, amounts, and who to contact."
          required
        />
      </label>
      <div className="actions">
        <button type="submit" className="btn btn-primary" disabled={!valid || saving}>
          {saving ? "Saving…" : submitLabel}
        </button>
        <button type="button" className="btn" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
      </div>
    </form>
  );
}
