import { duration } from "../services/format.js";

export default function LatencyRow({ latency }) {
  const parts = [
    ["Retrieval", latency.retrieval_ms],
    ["Generation", latency.generation_ms],
    ["Evaluation", latency.evaluation_ms],
    ["Total", latency.total_ms],
  ];
  return (
    <div className="stat-row">
      {parts.map(([label, value]) => (
        <div className="stat" key={label}>
          <span className="body-sm muted">{label}</span>
          <strong>{duration(value)}</strong>
        </div>
      ))}
    </div>
  );
}
