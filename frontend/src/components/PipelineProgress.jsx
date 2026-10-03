import { useEffect, useState } from "react";
import { duration } from "../services/format.js";

const STAGES = [
  "Analyse query and search arXiv",
  "Download PDFs and chunk full text",
  "Embed chunks and run vector search",
  "Rank by semantic, recency and feedback scores",
  "Generate a cited answer from the evidence",
  "Self-evaluate and update ranking weights",
];

export default function PipelineProgress({ startedAt, generates = true }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const stages = generates ? STAGES : STAGES.slice(0, 4);

  return (
    <section className="card progress" aria-live="polite">
      <div className="progress-head">
        <span className="spinner" aria-hidden="true" />
        <strong>Running the pipeline</strong>
        <span className="muted body-sm">{duration(now - startedAt)} elapsed</span>
      </div>
      <ol className="stages body-md">
        {stages.map((stage) => (
          <li key={stage}>{stage}</li>
        ))}
      </ol>
      <p className="body-sm muted">
        The server runs these steps in order and returns once all are done. First-time questions take longer
        because papers are downloaded and embedded.
      </p>
    </section>
  );
}
