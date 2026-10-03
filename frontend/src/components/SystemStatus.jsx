export default function SystemStatus({ status }) {
  const { retrieval, llm } = status;
  return (
    <section className="card">
      <h2 className="headline-sm">System status</h2>
      <p className="body-sm muted">
        v{status.version} · {status.environment} · {llm.provider}/{llm.model}
      </p>
      <ul className="components">
        {Object.entries(status.components).map(([name, component]) => (
          <li key={name}>
            <span className={`chip ${component.status}`}>{component.status.replace("_", " ")}</span>
            <strong>{name}</strong>
            <span className="muted">{component.detail}</span>
          </li>
        ))}
      </ul>
      <h3>Stored</h3>
      <div className="chips">
        {Object.entries(status.counts).map(([name, count]) => (
          <span className="chip" key={name}>{count} {name.replace("_", " ")}</span>
        ))}
      </div>
      <h3>arXiv categories</h3>
      <div className="chips">
        {retrieval.arxiv_categories.map((category) => (
          <span className="chip" key={category}>{category}</span>
        ))}
      </div>
      <h3>Retrieval</h3>
      <p className="body-md muted">
        Up to {retrieval.arxiv_max_results} papers, last {retrieval.arxiv_recency_days ?? "∞"} days,
        top {retrieval.top_k} of {retrieval.candidate_pool} chunks, {retrieval.embedding_model}
      </p>
    </section>
  );
}
