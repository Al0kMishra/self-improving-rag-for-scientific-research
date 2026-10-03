import { dateTime, percent } from "../services/format.js";

export default function RecentQueries({ queries, activeId }) {
  return (
    <section className="card">
      <h2 className="headline-sm">Recent queries</h2>
      {queries.length === 0 && <p className="body-md muted">No questions asked yet.</p>}
      <ul className="recent">
        {queries.map((item) => (
          <li key={item.id} className={item.id === activeId ? "active" : undefined}>
            <a href={`#/query/${item.id}`}>{item.text}</a>
            <div className="body-sm muted">
              {item.mode} · {item.status}
              {item.evaluation && ` · overall ${percent(item.evaluation.overall)}`}
              {item.experiment_run && ` · ${item.experiment_run}`} · {dateTime(item.created_at)}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
