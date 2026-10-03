import { METRICS, MODE_SERIES, duration, percent } from "../services/format.js";
import ChartFrame from "./charts/ChartFrame.jsx";
import GroupedBarChart from "./charts/GroupedBarChart.jsx";
import Legend from "./charts/Legend.jsx";

const SHORT = {
  retrieval_precision: "Precision",
  retrieval_relevance: "Relevance",
  groundedness: "Grounded",
  citation_accuracy: "Citations",
  answer_relevance: "Answer",
  evidence_coverage: "Coverage",
  overall: "Overall",
};

export default function MetricsComparison({ modes }) {
  const byMode = Object.fromEntries(modes.map((mode) => [mode.mode, mode]));
  const categories = METRICS.map((metric) => ({ ...metric, short: SHORT[metric.key] }));
  const values = Object.fromEntries(
    METRICS.map((metric) => [
      metric.key,
      Object.fromEntries(MODE_SERIES.map((series) => [series.key, byMode[series.key]?.means[metric.key] ?? null])),
    ])
  );
  const evaluated = modes.reduce((total, mode) => total + mode.evaluated, 0);

  const table = (
    <table className="data-table">
      <thead>
        <tr>
          <th>Metric</th>
          {MODE_SERIES.map((series) => (
            <th key={series.key}>{series.label}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {METRICS.map((metric) => (
          <tr key={metric.key}>
            <td>{metric.label}</td>
            {MODE_SERIES.map((series) => (
              <td key={series.key}>{percent(values[metric.key][series.key], 1)}</td>
            ))}
          </tr>
        ))}
        <tr>
          <td>Mean latency</td>
          {MODE_SERIES.map((series) => (
            <td key={series.key}>{duration(byMode[series.key]?.mean_latency_ms)}</td>
          ))}
        </tr>
        <tr>
          <td>Evaluated queries</td>
          {MODE_SERIES.map((series) => (
            <td key={series.key}>
              {byMode[series.key]?.evaluated ?? 0} of {byMode[series.key]?.queries ?? 0}
            </td>
          ))}
        </tr>
        <tr>
          <td>User feedback 👍 / 👎</td>
          {MODE_SERIES.map((series) => (
            <td key={series.key}>
              {byMode[series.key]?.positive_feedback ?? 0} / {byMode[series.key]?.negative_feedback ?? 0}
            </td>
          ))}
        </tr>
      </tbody>
    </table>
  );

  return (
    <ChartFrame
      title="Baseline vs self-improving RAG"
      subtitle={`Mean self-evaluation scores over ${evaluated} evaluated answers`}
      legend={<Legend series={MODE_SERIES} shape="rect" />}
      table={table}
    >
      {evaluated === 0 ? (
        <p className="body-md muted empty-chart">No evaluated answers in this scope yet.</p>
      ) : (
        <GroupedBarChart
          categories={categories}
          series={MODE_SERIES}
          values={values}
          yFormat={(v) => percent(v)}
          ariaLabel="Mean metric scores by mode"
        />
      )}
    </ChartFrame>
  );
}
