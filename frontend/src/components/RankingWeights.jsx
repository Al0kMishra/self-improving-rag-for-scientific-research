import { WEIGHT_SERIES, decimal } from "../services/format.js";

export default function RankingWeights({ history, used, scope }) {
  const { current, weight_min, weight_max, learning_rate, snapshots } = history;
  const updates = snapshots.filter((snapshot) => snapshot.trigger !== "init").length;
  return (
    <section className="card">
      <h2 className="headline-sm">Ranking weights</h2>
      <p className="body-sm muted">{scope ? `Current weights in ${scope}.` : "Current weights for live usage."}</p>
      <p className="body-sm muted">
        Final score = α·semantic + β·recency + γ·feedback. {updates} update{updates === 1 ? "" : "s"} so far,
        bounded to [{weight_min}, {weight_max}], learning rate {learning_rate}.
      </p>
      {WEIGHT_SERIES.map((series) => (
        <div className="weight" key={series.key}>
          <span>
            <span className="swatch" style={{ background: series.color }} />
            {series.label}
          </span>
          <div className="bar">
            <div style={{ width: `${current[series.key] * 100}%`, background: series.color }} />
          </div>
          <span>{decimal(current[series.key])}</span>
        </div>
      ))}
      {used && (
        <p className="body-sm muted">
          This answer was ranked with α {decimal(used.alpha)}, β {decimal(used.beta)}, γ {decimal(used.gamma)}.
        </p>
      )}
    </section>
  );
}
