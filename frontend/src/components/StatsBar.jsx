import { REASONS } from "../display.js";

export default function StatsBar({ stats }) {
  if (!stats) return <div className="stats stats-loading" />;
  const pct = stats.total ? Math.round((stats.answered / stats.total) * 100) : 0;

  return (
    <section className="stats" aria-label="Summary">
      <div className="stat">
        <span className="stat-value">{stats.total}</span>
        <span className="stat-label">Questions asked</span>
      </div>
      <div className="stat">
        <span className="stat-value">{pct}%</span>
        <span className="stat-label">Answered automatically</span>
      </div>
      <div className="stat">
        <span className="stat-value">{stats.escalated}</span>
        <span className="stat-label">Sent to staff</span>
        <ul className="stat-breakdown">
          {Object.entries(stats.by_reason)
            .filter(([, n]) => n > 0)
            .map(([reason, n]) => (
              <li key={reason}>
                {REASONS[reason]?.label ?? reason}: {n}
              </li>
            ))}
        </ul>
      </div>
      <div className="stat stat-highlight">
        <span className="stat-value">{stats.unresolved}</span>
        <span className="stat-label">Needs review</span>
      </div>
    </section>
  );
}
