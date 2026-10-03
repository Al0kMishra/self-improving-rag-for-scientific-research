import { useState } from "react";
import { useWidth } from "../../hooks/useWidth.js";
import Tooltip from "./Tooltip.jsx";

const MARGIN = { top: 12, right: 16, bottom: 28, left: 44 };

function segments(points, key) {
  const runs = [];
  let current = [];
  points.forEach((point, index) => {
    const value = point[key];
    if (value === null || value === undefined) {
      if (current.length) runs.push(current);
      current = [];
    } else {
      current.push([index, value]);
    }
  });
  if (current.length) runs.push(current);
  return runs;
}

export default function LineChart({ points, series, yMax = 1, yFormat, height = 220, ariaLabel }) {
  const [ref, width] = useWidth();
  const [active, setActive] = useState(null);
  const innerWidth = width - MARGIN.left - MARGIN.right;
  const innerHeight = height - MARGIN.top - MARGIN.bottom;
  const count = points.length;
  const x = (index) => MARGIN.left + (count <= 1 ? innerWidth / 2 : (index / (count - 1)) * innerWidth);
  const y = (value) => MARGIN.top + innerHeight - (value / yMax) * innerHeight;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((step) => step * yMax);
  const labelEvery = Math.max(1, Math.ceil(count / Math.max(2, Math.floor(innerWidth / 64))));

  const pick = (clientX, rect) => {
    if (!count) return;
    const relative = clientX - rect.left - MARGIN.left;
    const index = count <= 1 ? 0 : Math.round((relative / innerWidth) * (count - 1));
    setActive(Math.min(count - 1, Math.max(0, index)));
  };

  const onKeyDown = (event) => {
    if (event.key === "ArrowRight") setActive((value) => Math.min(count - 1, (value ?? -1) + 1));
    if (event.key === "ArrowLeft") setActive((value) => Math.max(0, (value ?? count) - 1));
  };

  return (
    <div className="chart-body" ref={ref}>
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={ariaLabel}
        tabIndex={0}
        onKeyDown={onKeyDown}
        onBlur={() => setActive(null)}
      >
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(tick)} y2={y(tick)} className="grid-line" />
            <text x={MARGIN.left - 8} y={y(tick)} className="axis-label" textAnchor="end" dominantBaseline="middle">
              {yFormat(tick)}
            </text>
          </g>
        ))}
        {points.map((point, index) =>
          index % labelEvery === 0 || index === count - 1 ? (
            <text key={index} x={x(index)} y={height - 8} className="axis-label" textAnchor="middle">
              {point.label}
            </text>
          ) : null
        )}
        {active !== null && (
          <line x1={x(active)} x2={x(active)} y1={MARGIN.top} y2={MARGIN.top + innerHeight} className="crosshair" />
        )}
        {series.map((item) =>
          segments(points, item.key).map((run, runIndex) => (
            <g key={`${item.key}-${runIndex}`}>
              {run.length > 1 && (
                <polyline
                  points={run.map(([index, value]) => `${x(index)},${y(value)}`).join(" ")}
                  fill="none"
                  stroke={item.color}
                  strokeWidth="2"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              )}
              {run.length === 1 && (
                <circle cx={x(run[0][0])} cy={y(run[0][1])} r="4" fill={item.color} className="dot" />
              )}
            </g>
          ))
        )}
        {active !== null &&
          series.map((item) => {
            const value = points[active][item.key];
            if (value === null || value === undefined) return null;
            return <circle key={item.key} cx={x(active)} cy={y(value)} r="4" fill={item.color} className="dot" />;
          })}
        <rect
          x={MARGIN.left}
          y={MARGIN.top}
          width={innerWidth}
          height={innerHeight}
          fill="transparent"
          onPointerMove={(event) => pick(event.clientX, event.currentTarget.ownerSVGElement.getBoundingClientRect())}
          onPointerLeave={() => setActive(null)}
        />
      </svg>
      {active !== null && points[active] && (
        <Tooltip
          x={x(active)}
          y={MARGIN.top}
          width={width}
          title={points[active].title || points[active].label}
          rows={series
            .filter((item) => points[active][item.key] !== null && points[active][item.key] !== undefined)
            .map((item) => ({ key: item.key, color: item.color, label: item.label, value: yFormat(points[active][item.key]) }))}
        />
      )}
    </div>
  );
}
