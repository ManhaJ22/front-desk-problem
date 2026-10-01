// One chat bubble. Kinds: "parent", "answer", "escalated", "error".
// "escalated" renders only its message (no verified answer). An "answer" may carry a staff
// note when a sensitive question was also sent to staff (decision log #37).
export default function ChatMessage({ message }) {
  const { kind, text, sources = [], note } = message;

  if (kind === "parent") {
    return <div className="bubble bubble-parent">{text}</div>;
  }

  if (kind === "escalated") {
    return (
      <div className="bubble bubble-escalated">
        <span className="bubble-label">Sent to staff</span>
        {text}
      </div>
    );
  }

  if (kind === "error") {
    return <div className="bubble bubble-error">{text}</div>;
  }

  return (
    <div className="bubble bubble-answer">
      {text}
      {sources.length > 0 && (
        <div className="sources">
          {sources.map((s) => (
            <span key={s.id} className="source-tag">
              From the handbook: {s.title}
            </span>
          ))}
        </div>
      )}
      {note && <p className="bubble-note">{note}</p>}
    </div>
  );
}
