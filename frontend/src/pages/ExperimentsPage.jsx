import { useEffect } from "react";
import CycleCharts from "../components/CycleCharts.jsx";
import MetricsComparison from "../components/MetricsComparison.jsx";
import RunSelector from "../components/RunSelector.jsx";
import { navigate } from "../hooks/useHashRoute.js";
import { useLoad } from "../hooks/useLoad.js";
import { api } from "../services/api.js";
import { dateTime } from "../services/format.js";

export default function ExperimentsPage({ run = null }) {
  const runs = useLoad(() => api.experiments().catch(() => []), []);
  const setRun = (value) => navigate(value ? `experiments/${encodeURIComponent(value)}` : "experiments/live");

  useEffect(() => {
    if (run === null && runs.data?.length) setRun(runs.data[0].experiment_run);
  }, [runs.data, run]);

  const scope = run && run !== "live" ? run : null;
  const metrics = useLoad(() => api.metrics(scope ?? undefined), [scope]);
  const cycles = useLoad(
    () => (scope ? api.experimentCycles(scope).catch(() => null) : Promise.resolve(null)),
    [scope]
  );
  const selected = runs.data?.find((item) => item.experiment_run === scope);

  return (
    <div className="page">
      <div className="page-head">
        <h1 className="headline-lg">Experiments</h1>
        <p className="body-md muted">
          Baseline RAG against self-improving RAG on the evaluation question set, measured by the self-evaluator.
          Every number on this page is read from stored query records.
        </p>
      </div>
      <RunSelector runs={runs.data || []} value={scope} onChange={setRun} />
      {runs.data && runs.data.length === 0 && !scope && (
        <section className="card notice-card">
          <p className="body-md">
            No experiment runs are listed yet. Run the experiment script in <code>evaluation/</code> (see the README)
            to produce per-cycle results. Until then this page shows live usage.
          </p>
        </section>
      )}
      {selected && (
        <p className="body-sm muted">
          Started {dateTime(selected.created_at)} · {selected.completed} of {selected.queries} queries completed ·{" "}
          {selected.cycles} training cycle{selected.cycles === 1 ? "" : "s"}
        </p>
      )}
      <div className="stack-gap">
        {metrics.error && <p className="error">{metrics.error.message}</p>}
        {metrics.data && (
          <section className={metrics.loading ? "card refreshing" : "card"}>
            <MetricsComparison modes={metrics.data.modes} />
          </section>
        )}
        {scope && cycles.data === null && !cycles.loading && (
          <p className="body-sm muted">Per-cycle results are not available for this run.</p>
        )}
        {cycles.data && cycles.data.cycles.length > 0 && <CycleCharts data={cycles.data} />}
      </div>
    </div>
  );
}
