export const METRICS = [
  { key: "retrieval_precision", label: "Retrieval precision" },
  { key: "retrieval_relevance", label: "Retrieval relevance" },
  { key: "groundedness", label: "Groundedness" },
  { key: "citation_accuracy", label: "Citation accuracy" },
  { key: "answer_relevance", label: "Answer relevance" },
  { key: "evidence_coverage", label: "Evidence coverage" },
  { key: "overall", label: "Overall" },
];

export const WEIGHT_SERIES = [
  { key: "alpha", label: "α semantic", color: "var(--series-alpha)" },
  { key: "beta", label: "β recency", color: "var(--series-beta)" },
  { key: "gamma", label: "γ feedback", color: "var(--series-gamma)" },
];

export const MODE_SERIES = [
  { key: "baseline", label: "Baseline RAG", color: "var(--series-baseline)" },
  { key: "proposed", label: "Self-improving RAG", color: "var(--series-proposed)" },
];

export function percent(value, digits = 0) {
  if (value === null || value === undefined) return "n/a";
  return `${(value * 100).toFixed(digits)}%`;
}

export function decimal(value, digits = 2) {
  if (value === null || value === undefined) return "n/a";
  return value.toFixed(digits);
}

export function signed(value, digits = 3) {
  if (value === null || value === undefined) return "n/a";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

export function duration(ms) {
  if (ms === null || ms === undefined) return "n/a";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.floor(ms / 60000)} min ${Math.round((ms % 60000) / 1000)} s`;
}

export function dateTime(value) {
  if (!value) return "";
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function year(value) {
  return value ? new Date(value).getFullYear() : "";
}

export function authorsShort(authors) {
  if (!authors || !authors.length) return "";
  return authors.length > 2 ? `${authors[0]} et al.` : authors.join(" and ");
}
