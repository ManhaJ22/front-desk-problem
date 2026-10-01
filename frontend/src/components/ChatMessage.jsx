// One chat bubble. Kinds: "parent", "answer", "escalated", "error".
// An escalated message renders ONLY its message text (decision log #8).
export default function ChatMessage({ message }) {
  const { kind, text, sources = [] } = message;

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
    </div>
  );
}
