import { WEIGHT_SERIES, dateTime, decimal } from "../services/format.js";
import ChartFrame from "./charts/ChartFrame.jsx";
import Legend from "./charts/Legend.jsx";
import LineChart from "./charts/LineChart.jsx";

export default function WeightHistoryChart({ snapshots }) {
  const points = snapshots.map((snapshot, index) => ({
    label: String(index),
    title: `Update ${index} · ${snapshot.trigger} · ${dateTime(snapshot.created_at)}`,
    alpha: snapshot.alpha,
    beta: snapshot.beta,
    gamma: snapshot.gamma,
  }));
  const table = (
    <table className="data-table">
      <thead>
        <tr>
          <th>Update</th>
          <th>Trigger</th>
          {WEIGHT_SERIES.map((series) => (
            <th key={series.key}>{series.label}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {snapshots.map((snapshot, index) => (
          <tr key={snapshot.id}>
            <td>{index}</td>
            <td>{snapshot.trigger}</td>
            {WEIGHT_SERIES.map((series) => (
              <td key={series.key}>{decimal(snapshot[series.key], 3)}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <ChartFrame
      title="Ranking weights over updates"
      subtitle="Each point is a stored snapshot; update 0 is the initial configuration"
      legend={<Legend series={WEIGHT_SERIES} />}
      table={table}
    >
      <LineChart points={points} series={WEIGHT_SERIES} yMax={1} yFormat={(v) => decimal(v)} ariaLabel="Weights over updates" />
    </ChartFrame>
  );
}
