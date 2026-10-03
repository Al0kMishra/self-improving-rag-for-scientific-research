import { useState } from "react";
import { authorsShort, year } from "../services/format.js";
import FeedbackButtons from "./FeedbackButtons.jsx";
import ScoreBreakdown from "./ScoreBreakdown.jsx";

const RELEVANCE = { 1: "judged relevant", 0.5: "judged partial", 0: "judged irrelevant" };

export default function EvidenceCard({ item, weights, queryId, active, onHover, onFeedback, canFeedback }) {
  const [expanded, setExpanded] = useState(false);
  const long = item.text.length > 420;
  const text = expanded || !long ? item.text : `${item.text.slice(0, 420)}…`;
  const location = [item.section, item.page && `page ${item.page}`].filter(Boolean).join(" · ");

  return (
    <article
      id={`evidence-${item.rank}`}
      className={active ? "evidence active" : "evidence"}
      onMouseEnter={() => onHover(item.rank)}
      onMouseLeave={() => onHover(null)}
    >
      <header className="evidence-head">
        <span className="evidence-number">{item.rank}</span>
        <div className="evidence-title">
          <a href={item.paper.abs_url} target="_blank" rel="noreferrer">
            {item.paper.title}
          </a>
          <div className="body-sm muted">
            {authorsShort(item.paper.authors)} · {year(item.paper.published_at)} · arXiv:{item.paper.id}
            {location && ` · ${location}`}
          </div>
        </div>
      </header>
      <div className="chips">
        <span className="chip">{item.source === "pdf" ? "full text" : "abstract"}</span>
        {item.cited && <span className="chip ok">cited</span>}
        {item.judged_relevance !== null && item.judged_relevance !== undefined && (
          <span className="chip">{RELEVANCE[item.judged_relevance] ?? `relevance ${item.judged_relevance}`}</span>
        )}
      </div>
      <p className="evidence-text body-md">{text}</p>
      {long && (
        <button type="button" className="btn-link" onClick={() => setExpanded((value) => !value)}>
          {expanded ? "Show less" : "Show full excerpt"}
        </button>
      )}
      <ScoreBreakdown item={item} weights={weights} />
      {canFeedback && (
        <FeedbackButtons queryId={queryId} chunkId={item.chunk_id} label="Useful evidence?" onSent={onFeedback} />
      )}
    </article>
  );
}
