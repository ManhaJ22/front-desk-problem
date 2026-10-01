// Display labels and formatters shared by the operator components.

export const REASONS = {
  out_of_scope: {
    label: "Not in handbook",
    detail: () => "Nothing in the handbook matched closely enough.",
  },
  sensitive_forced: {
    label: "Sensitive topic",
    detail: (q) =>
      q.sensitivity_category && q.sensitivity_category !== "none"
        ? `Always sent to staff: ${categoryLabel(q.sensitivity_category)}.`
        : `Always sent to staff: sensitivity score ${q.sensitivity_score}/5.`,
  },
  below_threshold: {
    label: "Low confidence",
    detail: (q) =>
      `Combined ${fmtScore(q.combined_score)} was below the ${fmtScore(q.threshold_used)} bar.`,
  },
  system_error: {
    label: "System error",
    detail: () => "The AI service failed; the question was escalated to be safe.",
  },
};

export function reasonLabel(q) {
  return q.escalation_reason ? REASONS[q.escalation_reason]?.label ?? q.escalation_reason : "Answered";
}

export function reasonDetail(q) {
  return q.escalation_reason ? REASONS[q.escalation_reason]?.detail(q) ?? "" : "";
}

const CATEGORY_LABELS = {
  health: "Health",
  safety: "Safety",
  allergies: "Allergies",
  custody_legal: "Custody / legal",
  emotional_social: "Emotional / social",
  none: "None",
};

export function categoryLabel(c) {
  return CATEGORY_LABELS[c] ?? c ?? "—";
}

export function fmtScore(x) {
  return x == null ? "—" : Number(x).toFixed(2);
}

export function timeAgo(iso) {
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} hr ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
