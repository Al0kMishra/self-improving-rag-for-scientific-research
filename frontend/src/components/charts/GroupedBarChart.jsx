import { useState } from "react";
import { useWidth } from "../../hooks/useWidth.js";
import Tooltip from "./Tooltip.jsx";

const MARGIN = { top: 12, right: 12, bottom: 44, left: 44 };
const BAR_MAX = 24;
const GAP = 2;

function barPath(x, y, width, height) {
  const radius = Math.min(4, width / 2, height);
  if (height <= 0) return "";
  return [
    `M${x},${y + height}`,
    `V${y + radius}`,
    `Q${x},${y} ${x + radius},${y}`,
    `H${x + width - radius}`,
    `Q${x + width},${y} ${x + width},${y + radius}`,
    `V${y + height}`,
    "Z",
  ].join(" ");
}

export default function GroupedBarChart({ categories, series, values, yMax = 1, yFormat, height = 240, ariaLabel }) {
  const [ref, width] = useWidth();
  const [active, setActive] = useState(null);
  const innerWidth = width - MARGIN.left - MARGIN.right;
  const innerHeight = height - MARGIN.top - MARGIN.bottom;
  const band = innerWidth / Math.max(1, categories.length);
  const barWidth = Math.min(BAR_MAX, (band * 0.7 - GAP * (series.length - 1)) / series.length);
  const groupWidth = barWidth * series.length + GAP * (series.length - 1);
  const y = (value) => MARGIN.top + innerHeight - (value / yMax) * innerHeight;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((step) => step * yMax);

  return (
    <div className="chart-body" ref={ref}>
      <svg width={width} height={height} role="img" aria-label={ariaLabel}>
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(tick)} y2={y(tick)} className="grid-line" />
            <text x={MARGIN.left - 8} y={y(tick)} className="axis-label" textAnchor="end" dominantBaseline="middle">
              {yFormat(tick)}
            </text>
          </g>
        ))}
        {categories.map((category, categoryIndex) => {
          const start = MARGIN.left + band * categoryIndex + (band - groupWidth) / 2;
          return (
            <g key={category.key}>
              {series.map((item, seriesIndex) => {
                const value = values[category.key]?.[item.key];
                if (value === null || value === undefined) return null;
                const barX = start + seriesIndex * (barWidth + GAP);
                const isActive = active && active.category === category.key && active.series === item.key;
                return (
                  <g key={item.key}>
                    <path
                      d={barPath(barX, y(value), barWidth, y(0) - y(value))}
                      fill={item.color}
                      className={isActive ? "bar-mark active" : "bar-mark"}
                    />
                    <rect
                      x={barX - GAP}
                      y={MARGIN.top}
                      width={barWidth + GAP * 2}
                      height={innerHeight}
                      fill="transparent"
                      tabIndex={0}
                      aria-label={`${category.label}, ${item.label}: ${yFormat(value)}`}
                      onPointerEnter={() => setActive({ category: category.key, series: item.key, x: barX, y: y(value) })}
                      onFocus={() => setActive({ category: category.key, series: item.key, x: barX, y: y(value) })}
                      onPointerLeave={() => setActive(null)}
                      onBlur={() => setActive(null)}
                    />
                  </g>
                );
              })}
              <text
                x={MARGIN.left + band * categoryIndex + band / 2}
                y={height - MARGIN.bottom + 16}
                className="axis-label"
                textAnchor="middle"
              >
                {category.short || category.label}
              </text>
            </g>
          );
        })}
        <line x1={MARGIN.left} x2={width - MARGIN.right} y1={y(0)} y2={y(0)} className="baseline" />
      </svg>
      {active && (
        <Tooltip
          x={active.x}
          y={active.y}
          width={width}
          title={categories.find((c) => c.key === active.category).label}
          rows={series
            .filter((item) => values[active.category]?.[item.key] !== null && values[active.category]?.[item.key] !== undefined)
            .map((item) => ({
              key: item.key,
              color: item.color,
              label: item.label,
              value: yFormat(values[active.category][item.key]),
            }))}
        />
      )}
    </div>
  );
}
