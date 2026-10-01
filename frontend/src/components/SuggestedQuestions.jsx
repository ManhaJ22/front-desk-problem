// The five example questions from the Brightwheel brief.
const SUGGESTIONS = [
  "Are you open on Veterans Day?",
  "What is the tuition for infants?",
  "My child has a fever, can they come in?",
  "I forgot to pack lunch. Can you provide lunch today and what is it?",
  "How can I schedule a tour?",
];

export default function SuggestedQuestions({ onPick, disabled }) {
  return (
    <div className="suggestions" aria-label="Suggested questions">
      {SUGGESTIONS.map((s) => (
        <button key={s} type="button" className="chip" onClick={() => onPick(s)} disabled={disabled}>
          {s}
        </button>
      ))}
    </div>
  );
}
