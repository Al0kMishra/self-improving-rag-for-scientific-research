import { useState } from "react";

export default function ChartFrame({ title, subtitle, legend, table, children }) {
  const [showTable, setShowTable] = useState(false);
  return (
    <figure className="chart">
      <figcaption className="chart-head">
        <div>
          <div className="chart-title">{title}</div>
          {subtitle && <div className="body-sm muted">{subtitle}</div>}
        </div>
        {table && (
          <button type="button" className="btn-ghost" onClick={() => setShowTable((value) => !value)}>
            {showTable ? "Show chart" : "Show table"}
          </button>
        )}
      </figcaption>
      {legend}
      {showTable ? <div className="table-wrap">{table}</div> : children}
    </figure>
  );
}
