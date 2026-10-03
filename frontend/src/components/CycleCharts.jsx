import { useState } from "react";
import { METRICS, MODE_SERIES, WEIGHT_SERIES, decimal, duration, percent } from "../services/format.js";
import ChartFrame from "./charts/ChartFrame.jsx";
import Legend from "./charts/Legend.jsx";
import LineChart from "./charts/LineChart.jsx";

function cycleLabel(entry) {
  return entry.phase === "test" ? "test" : `cycle ${entry.cycle}`;
}

function cycleKey(entry) {
  return `${entry.phase}-${entry.cycle}`;
}

function cyclePoints(cycles, valueOf) {
  const ordered = [...cycles].sort((a, b) =>
    a.phase === b.phase ? a.cycle - b.cycle : a.phase === "train" ? -1 : 1
  );
  const points = new Map();
  ordered.forEach((entry) => {
    const key = cycleKey(entry);
    const point = points.get(key) || { label: cycleLabel(entry) };
    point[entry.mode] = valueOf(entry);
    points.set(key, point);
  });
  return [...points.values()];
}

function SeriesTable({ points, series, format }) {
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Cycle</th>
          {series.map((item) => (
            <th key={item.key}>{item.label}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {points.map((point) => (
          <tr key={point.label}>
            <td>{point.label}</td>
            {series.map((item) => (
              <td key={item.key}>{point[item.key] === undefined ? "n/a" : format(point[item.key])}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function CycleCharts({ data }) {
  const [metric, setMetric] = useState("overall");
  const metricLabel = METRICS.find((item) => item.key === metric).label;
  const metricPoints = cyclePoints(data.cycles, (entry) => entry.means[metric]);
  const latencyPoints = cyclePoints(data.cycles, (entry) => entry.mean_latency_ms);
  const slowest = Math.max(1, ...latencyPoints.flatMap((p) => MODE_SERIES.map((s) => p[s.key] || 0)));
  const latencyMax = Math.ceil(slowest / 20000) * 20000;
  const weightPoints = data.weights.map((entry) => ({ label: `cycle ${entry.cycle}`, ...entry }));
  const changePoints = data.retrieval_change.map((entry) => ({
    label: `cycle ${entry.cycle}`,
    overlap: entry.mean_topk_jaccard_vs_previous,
  }));
  const overlapSeries = [{ key: "overlap", label: "Top-k overlap", color: "var(--series-proposed)" }];

  return (
    <div className="stack-gap">
      <section className="card">
        <div className="chip-filter" role="radiogroup" aria-label="Metric">
          {METRICS.map((item) => (
            <button
              key={item.key}
              type="button"
              role="radio"
              aria-checked={metric === item.key}
              className={metric === item.key ? "segment active" : "segment"}
              onClick={() => setMetric(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <ChartFrame
          title={`${metricLabel} across feedback cycles`}
          subtitle="Training cycles repeat the question set; the test point uses held-out questions with learning frozen. A mode appears only at the cycles where it was measured."
          legend={<Legend series={MODE_SERIES} />}
          table={<SeriesTable points={metricPoints} series={MODE_SERIES} format={(v) => percent(v, 1)} />}
        >
          <LineChart points={metricPoints} series={MODE_SERIES} yFormat={(v) => percent(v)} ariaLabel={metricLabel} />
        </ChartFrame>
      </section>

      <div className="two-col">
        <section className="card">
          <ChartFrame
            title="Ranking weights at the end of each cycle"
            legend={<Legend series={WEIGHT_SERIES} />}
            table={<SeriesTable points={weightPoints} series={WEIGHT_SERIES} format={(v) => decimal(v, 3)} />}
          >
            {weightPoints.length ? (
              <LineChart points={weightPoints} series={WEIGHT_SERIES} yFormat={(v) => decimal(v)} ariaLabel="Weights per cycle" />
            ) : (
              <p className="body-md muted empty-chart">No weight snapshots for this run.</p>
            )}
          </ChartFrame>
        </section>
        <section className="card">
          <ChartFrame
            title="Retrieval change between cycles"
            subtitle="Mean Jaccard overlap of each question's top-k evidence with the previous cycle; lower means retrieval changed more"
            table={<SeriesTable points={changePoints} series={overlapSeries} format={(v) => decimal(v)} />}
          >
            {changePoints.length ? (
              <LineChart points={changePoints} series={overlapSeries} yFormat={(v) => decimal(v)} ariaLabel="Top-k overlap" />
            ) : (
              <p className="body-md muted empty-chart">Needs at least two cycles.</p>
            )}
          </ChartFrame>
        </section>
      </div>

      <section className="card">
        <ChartFrame
          title="Mean latency per cycle"
          subtitle="End-to-end time per query, including generation and self-evaluation"
          legend={<Legend series={MODE_SERIES} />}
          table={<SeriesTable points={latencyPoints} series={MODE_SERIES} format={duration} />}
        >
          <LineChart
            points={latencyPoints}
            series={MODE_SERIES}
            yMax={latencyMax}
            yFormat={(v) => `${Math.round(v / 1000)} s`}
            ariaLabel="Latency per cycle"
          />
        </ChartFrame>
      </section>
    </div>
  );
}
