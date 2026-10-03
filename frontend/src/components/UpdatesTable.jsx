import { dateTime, decimal, signed } from "../services/format.js";

function Slopes({ details }) {
  if (!details?.slopes) return <span className="muted">n/a</span>;
  return (
    <span>
      sem {signed(details.slopes.semantic, 2)} · rec {signed(details.slopes.recency, 2)} · fb{" "}
      {signed(details.slopes.feedback, 2)}
    </span>
  );
}

export default function UpdatesTable({ snapshots }) {
  const rows = [...snapshots].reverse();
  return (
    <section className="card">
      <h2 className="headline-sm">Update log</h2>
      <p className="body-sm muted">
        Slopes measure how much higher each score was on evidence judged relevant than on irrelevant evidence.
        Positive slopes pull the weights toward that component.
      </p>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>When</th>
              <th>Trigger</th>
              <th>Query</th>
              <th>α</th>
              <th>β</th>
              <th>γ</th>
              <th>Slopes</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((snapshot) => (
              <tr key={snapshot.id}>
                <td>{dateTime(snapshot.created_at)}</td>
                <td>{snapshot.trigger}</td>
                <td>{snapshot.query_id ? <a href={`#/query/${snapshot.query_id}`}>#{snapshot.query_id}</a> : "n/a"}</td>
                <td>{decimal(snapshot.alpha, 3)}</td>
                <td>{decimal(snapshot.beta, 3)}</td>
                <td>{decimal(snapshot.gamma, 3)}</td>
                <td>
                  <Slopes details={snapshot.details} />
                </td>
                <td className="note-cell">{snapshot.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
