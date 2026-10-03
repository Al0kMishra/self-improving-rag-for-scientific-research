import { useState } from "react";
import { METRICS, percent } from "../services/format.js";

const REASON_KEYS = {
  retrieval_precision: "retrieval",
  retrieval_relevance: "retrieval",
  groundedness: "groundedness",
  citation_accuracy: "citation_accuracy",
  answer_relevance: "answer_relevance",
  evidence_coverage: "evidence_coverage",
  overall: "summary",
};

function Meter({ label, value, reason }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="meter">
      <button type="button" className="meter-head" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <span>{label}</span>
        <strong>{percent(value)}</strong>
      </button>
      <div className="meter-track" aria-hidden="true">
        <div className="meter-fill" style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
      </div>
      {open && reason && <p className="body-sm muted meter-reason">{reason}</p>}
    </div>
  );
}

export default function EvaluationPanel({ evaluation, error }) {
  if (!evaluation) {
    return (
      <section className="card">
        <h2 className="headline-sm">Self-evaluation</h2>
        <p className="body-md muted">{error || "This answer has not been evaluated."}</p>
      </section>
    );
  }
  return (
    <section className="card">
      <h2 className="headline-sm">Self-evaluation</h2>
      <p className="body-sm muted">Judged by {evaluation.evaluator_model}. Select a score to read the reasoning.</p>
      {METRICS.map((metric) => (
        <Meter
          key={metric.key}
          label={metric.label}
          value={evaluation[metric.key]}
          reason={evaluation.reasoning?.[REASON_KEYS[metric.key]]}
        />
      ))}
    </section>
  );
}
