import { useCallback, useEffect, useState } from "react";
import * as api from "../api.js";
import StatsBar from "../components/StatsBar.jsx";
import QuestionQueue from "../components/QuestionQueue.jsx";
import QuestionDetail from "../components/QuestionDetail.jsx";
import KnowledgeBase from "../components/KnowledgeBase.jsx";

export default function OperatorDashboard() {
  const [tab, setTab] = useState("questions");
  const [view, setView] = useState("needs_review");
  const [questions, setQuestions] = useState([]);
  const [chunks, setChunks] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [q, c, s] = await Promise.all([api.listQuestions(view), api.listChunks(), api.getStats()]);
      setQuestions(q);
      setChunks(c);
      setStats(s);
    } catch {
      setError("Couldn't load the dashboard. Check that the server is running, then refresh.");
    } finally {
      setLoading(false);
    }
  }, [view]);

  useEffect(() => {
    load();
  }, [load]);

  // Keep the selected question visible even after it leaves the
  // "Needs review" list (e.g. right after resolving it).
  const [selectedSnapshot, setSelectedSnapshot] = useState(null);
  const selected = questions.find((q) => q.id === selectedId) ?? (selectedSnapshot?.id === selectedId ? selectedSnapshot : null);

  function select(id) {
    setSelectedId(id);
    setSelectedSnapshot(questions.find((q) => q.id === id) ?? null);
  }

  async function resolve(id) {
    const updated = await api.resolveQuestion(id);
    setSelectedSnapshot(updated);
    await load();
  }

  async function addToKb(id, data) {
    const { question } = await api.addToKb(id, data);
    setSelectedSnapshot(question);
    await load();
  }

  return (
    <div className="ops-page">
      <header className="ops-header">
        <div className="ops-title">
          <span className="logo" aria-hidden="true">🌰</span>
          <div>
            <h1>Little Acorns</h1>
            <p className="subtitle">Front Desk · Staff dashboard</p>
          </div>
        </div>
        <div className="ops-header-actions">
          <button type="button" className="btn" onClick={load} disabled={loading}>
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </header>

      {error && <p className="form-error banner">{error}</p>}

      <StatsBar stats={stats} />

      <nav className="tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "questions"}
          className={tab === "questions" ? "active" : ""}
          onClick={() => setTab("questions")}
        >
          Questions
          {stats?.unresolved > 0 && <span className="tab-count">{stats.unresolved}</span>}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "kb"}
          className={tab === "kb" ? "active" : ""}
          onClick={() => setTab("kb")}
        >
          Knowledge base
        </button>
      </nav>

      {tab === "questions" ? (
        <div className={`split ${selected ? "has-selection" : ""}`}>
          <QuestionQueue
            questions={questions}
            view={view}
            onViewChange={(v) => {
              setView(v);
              setSelectedId(null);
            }}
            selectedId={selectedId}
            onSelect={select}
            loading={loading}
          />
          {selected ? (
            <QuestionDetail
              key={selected.id}
              question={selected}
              chunks={chunks}
              onResolve={resolve}
              onAddToKb={addToKb}
              onBack={() => setSelectedId(null)}
            />
          ) : (
            <div className="detail detail-empty">
              <p className="muted">Select a question to see why it was sent to staff.</p>
            </div>
          )}
        </div>
      ) : (
        <KnowledgeBase
          chunks={chunks}
          onCreate={async (data) => {
            await api.createChunk(data);
            await load();
          }}
          onUpdate={async (id, data) => {
            await api.updateChunk(id, data);
            await load();
          }}
          onDelete={async (id) => {
            await api.deleteChunk(id);
            await load();
          }}
        />
      )}
    </div>
  );
}
