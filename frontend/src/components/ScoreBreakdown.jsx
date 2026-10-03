import { decimal } from "../services/format.js";

export default function ScoreBreakdown({ item, weights }) {
  const parts = [
    { key: "alpha", label: "semantic", value: weights.alpha * item.semantic_score, color: "var(--series-alpha)" },
    { key: "beta", label: "recency", value: weights.beta * item.recency_score, color: "var(--series-beta)" },
    { key: "gamma", label: "feedback", value: weights.gamma * item.feedback_score, color: "var(--series-gamma)" },
  ];
  const description = parts.map((part) => `${part.label} ${decimal(part.value)}`).join(", ");

  return (
    <div className="breakdown">
      <div className="stack" role="img" aria-label={`Final score ${decimal(item.final_score)}: ${description}`}>
        {parts.map((part) =>
          part.value > 0 ? (
            <span
              key={part.key}
              className="stack-part"
              style={{ width: `${part.value * 100}%`, background: part.color }}
              title={`${part.label}: ${decimal(part.value, 3)}`}
            />
          ) : null
        )}
      </div>
      <div className="breakdown-values body-sm">
        <strong>{decimal(item.final_score)}</strong>
        {parts.map((part) => (
          <span key={part.key} className="muted">
            <span className="swatch" style={{ background: part.color }} />
            {part.label} {decimal(part.value)}
          </span>
        ))}
      </div>
      <div className="breakdown-raw caption muted">
        cosine {decimal(item.similarity)} · semantic {decimal(item.semantic_score)} · recency{" "}
        {decimal(item.recency_score)} · feedback {decimal(item.feedback_score)}
      </div>
    </div>
  );
}
