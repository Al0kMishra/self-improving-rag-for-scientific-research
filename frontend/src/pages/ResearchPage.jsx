import { useEffect, useState } from "react";
import AnswerView from "../components/AnswerView.jsx";
import EvaluationPanel from "../components/EvaluationPanel.jsx";
import EvidenceCard from "../components/EvidenceCard.jsx";
import FeedbackButtons from "../components/FeedbackButtons.jsx";
import LatencyRow from "../components/LatencyRow.jsx";
import PapersList from "../components/PapersList.jsx";
import PipelineProgress from "../components/PipelineProgress.jsx";
import QueryInput from "../components/QueryInput.jsx";
import RankingWeights from "../components/RankingWeights.jsx";
import RecentQueries from "../components/RecentQueries.jsx";
import { navigate } from "../hooks/useHashRoute.js";
import { useLoad } from "../hooks/useLoad.js";
import { api } from "../services/api.js";

function describeError(error) {
  if (error.status === 503) return "The LLM is not configured. Set LLM_API_KEY or LLM_BASE_URL in .env and restart.";
  if (error.status === 502) return `The pipeline failed: ${error.body?.error || error.message}`;
  return error.message;
}

function EvidenceSection({ title, items, weights, queryId, activeMarker, onHover, onFeedback, canFeedback }) {
  return (
    <section className="evidence-list">
      <h2 className="headline-sm">{title}</h2>
      {items.length === 0 && <p className="body-md muted">No excerpts were retrieved.</p>}
      {items.map((item) => (
        <EvidenceCard
          key={item.chunk_id}
          item={item}
          weights={weights}
          queryId={queryId}
          active={activeMarker === item.rank}
          onHover={onHover}
          onFeedback={onFeedback}
          canFeedback={canFeedback}
        />
      ))}
    </section>
  );
}

export default function ResearchPage({ queryId }) {
  const [result, setResult] = useState(null);
  const [preview, setPreview] = useState(null);
  const [running, setRunning] = useState(null);
  const [error, setError] = useState(null);
  const [activeMarker, setActiveMarker] = useState(null);
  const scope = result?.experiment_run ?? undefined;
  const history = useLoad(() => api.improvementHistory(scope), [scope]);
  const recent = useLoad(() => api.listQueries(10), []);

  useEffect(() => {
    if (!queryId) return;
    setPreview(null);
    setError(null);
    api
      .getQuery(queryId)
      .then(setResult)
      .catch((err) => setError(err.message));
  }, [queryId]);

  const refresh = () => {
    history.reload();
    recent.reload();
  };

  const ask = async (payload) => {
    setRunning({ startedAt: Date.now(), generates: true });
    setError(null);
    setPreview(null);
    try {
      const detail = await api.runQuery(payload);
      setResult(detail);
      navigate(`query/${detail.id}`);
    } catch (err) {
      if (err.status === 502 && err.body?.id) setResult(err.body);
      setError(describeError(err));
    } finally {
      setRunning(null);
      refresh();
    }
  };

  const inspect = async (payload) => {
    setRunning({ startedAt: Date.now(), generates: false });
    setError(null);
    try {
      setPreview(await api.retrieve(payload));
      setResult(null);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setRunning(null);
    }
  };

  const selectMarker = (number) => {
    setActiveMarker(number);
    document.getElementById(`evidence-${number}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const completed = result && result.status === "completed";

  return (
    <div className="page">
      <div className="column">
        <div className="hero">
          <h1 className="headline-display">What do you want to research?</h1>
          <p className="muted">Grounded, cited answers over live arXiv AI/ML literature</p>
        </div>
        <QueryInput
          key={result?.id ?? "new"}
          onSubmit={ask}
          onInspect={inspect}
          disabled={Boolean(running)}
          initialQuery={result?.text ?? ""}
        />
        {error && (
          <p className="error body-md" role="alert">
            {error}
          </p>
        )}
        {running && <PipelineProgress startedAt={running.startedAt} generates={running.generates} />}
      </div>

      {preview && !running && (
        <div className="research-grid">
          <div className="research-main">
            <section className="card">
              <h2 className="headline-sm">Retrieval preview</h2>
              <p className="body-sm muted">
                {preview.mode} mode · {preview.papers_found} papers from arXiv ({preview.full_text_papers.length} with
                full text) · {preview.candidates_considered} candidate excerpts · query: {preview.search_query}
              </p>
            </section>
            <EvidenceSection
              title="Top ranked evidence"
              items={preview.results}
              weights={preview.weights}
              onHover={setActiveMarker}
              activeMarker={activeMarker}
              canFeedback={false}
            />
          </div>
          <aside className="research-side">
            {history.data && <RankingWeights history={history.data} used={preview.weights} />}
          </aside>
        </div>
      )}

      {result && !running && (
        <div className="research-grid">
          <div className="research-main">
            <AnswerView result={result} activeMarker={activeMarker} onHover={setActiveMarker} onSelect={selectMarker}>
              {completed && (
                <FeedbackButtons queryId={result.id} label="Was this answer helpful?" onSent={refresh} />
              )}
            </AnswerView>
            <EvidenceSection
              title="Supporting evidence"
              items={result.retrieved}
              weights={result.weights}
              queryId={result.id}
              activeMarker={activeMarker}
              onHover={setActiveMarker}
              onFeedback={refresh}
              canFeedback={completed}
            />
          </div>
          <aside className="research-side">
            <EvaluationPanel evaluation={result.evaluation} error={result.error} />
            {history.data && (
              <RankingWeights history={history.data} used={result.weights} scope={result.experiment_run} />
            )}
            <section className="card">
              <h2 className="headline-sm">Latency</h2>
              <LatencyRow latency={result.latency} />
            </section>
            <PapersList retrieved={result.retrieved} />
          </aside>
        </div>
      )}

      <div className="column">
        {recent.data && <RecentQueries queries={recent.data} activeId={result?.id} />}
      </div>
    </div>
  );
}
