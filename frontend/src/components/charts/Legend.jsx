export default function Legend({ series, shape = "line" }) {
  if (series.length < 2) return null;
  return (
    <ul className="legend">
      {series.map((item) => (
        <li key={item.key}>
          <span className={`legend-key ${shape}`} style={{ background: item.color }} />
          {item.label}
        </li>
      ))}
    </ul>
  );
}
