import RankingWeights from "../components/RankingWeights.jsx";
import SystemStatus from "../components/SystemStatus.jsx";
import { useLoad } from "../hooks/useLoad.js";
import { api } from "../services/api.js";

export default function SystemPage() {
  const status = useLoad(() => api.systemStatus(), []);
  const history = useLoad(() => api.improvementHistory(), []);

  return (
    <div className="page">
      <div className="page-head">
        <h1 className="headline-lg">System</h1>
        <p className="body-md muted">Component health, stored data and configuration.</p>
      </div>
      {status.error && <p className="error">Backend unreachable: {status.error.message}</p>}
      <div className="two-col">
        {status.data && <SystemStatus status={status.data} />}
        {history.data && <RankingWeights history={history.data} />}
      </div>
    </div>
  );
}
