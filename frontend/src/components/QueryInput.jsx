import { useState } from "react";

const MODES = [
  { key: "proposed", label: "Self-improving" },
  { key: "baseline", label: "Baseline" },
];

export default function QueryInput({ onSubmit, onInspect, disabled, initialQuery = "" }) {
  const [query, setQuery] = useState(initialQuery);
  const [mode, setMode] = useState("proposed");
  const ready = query.trim().length >= 3 && !disabled;

  const submit = (event) => {
    event.preventDefault();
    if (ready) onSubmit({ query: query.trim(), mode });
  };

  return (
    <form onSubmit={submit}>
      <div className="search">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Ask a research question about AI/ML literature"
          aria-label="Research question"
          disabled={disabled}
        />
        <button className="btn-primary" type="submit" disabled={!ready}>
          Ask
        </button>
      </div>
      <div className="query-options">
        <div className="segmented" role="radiogroup" aria-label="Retrieval mode">
          {MODES.map((item) => (
            <button
              key={item.key}
              type="button"
              role="radio"
              aria-checked={mode === item.key}
              className={mode === item.key ? "segment active" : "segment"}
              onClick={() => setMode(item.key)}
              disabled={disabled}
            >
              {item.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="btn-ghost"
          disabled={!ready}
          onClick={() => onInspect({ query: query.trim(), mode })}
        >
          Inspect retrieval only
        </button>
      </div>
    </form>
  );
}
