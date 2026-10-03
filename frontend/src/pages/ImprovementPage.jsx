import RankingWeights from "../components/RankingWeights.jsx";
import RunSelector from "../components/RunSelector.jsx";
import UpdatesTable from "../components/UpdatesTable.jsx";
import WeightHistoryChart from "../components/WeightHistoryChart.jsx";
import { navigate } from "../hooks/useHashRoute.js";
import { useLoad } from "../hooks/useLoad.js";
import { api } from "../services/api.js";

export default function ImprovementPage({ run = null }) {
  const setRun = (value) => navigate(value ? `improvement/${encodeURIComponent(value)}` : "improvement");
  const runs = useLoad(() => api.experiments().catch(() => []), []);
  const history = useLoad(() => api.improvementHistory(run ?? undefined), [run]);

  return (
    <div className="page">
      <div className="page-head">
        <h1 className="headline-lg">Improvement history</h1>
        <p className="body-md muted">
          How the ranking weights moved after each self-evaluation and each piece of user feedback.
        </p>
      </div>
      <RunSelector runs={runs.data || []} value={run} onChange={setRun} />
      {history.error && <p className="error">{history.error.message}</p>}
      {history.data && (
        <div className={history.loading ? "stack-gap refreshing" : "stack-gap"}>
          <div className="two-col">
            <section className="card">
              <WeightHistoryChart snapshots={history.data.snapshots} />
            </section>
            <RankingWeights history={history.data} scope={run} />
          </div>
          <UpdatesTable snapshots={history.data.snapshots} />
        </div>
      )}
    </div>
  );
}
