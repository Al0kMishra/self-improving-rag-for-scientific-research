export default function Tooltip({ x, y, width, title, rows }) {
  const left = Math.min(Math.max(x + 12, 0), width - 180);
  return (
    <div className="tooltip" style={{ left, top: Math.max(y - 12, 0) }} role="status">
      <div className="tooltip-title">{title}</div>
      {rows.map((row) => (
        <div className="tooltip-row" key={row.key}>
          <span className="line-key" style={{ background: row.color }} />
          <strong>{row.value}</strong>
          <span className="muted">{row.label}</span>
        </div>
      ))}
    </div>
  );
}
