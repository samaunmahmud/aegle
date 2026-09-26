import { useState } from "react";
import type { MeasurementPoint } from "../api/types";

const W = 360;
const H = 150;
const PAD = { left: 48, right: 16, top: 16, bottom: 28 };

function formatValue(v: number, unit: string) {
  if (unit === "%") return `${v.toFixed(1)}%`;
  if (unit === "px") return `${Math.round(v).toLocaleString()} px`;
  return `${v.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${unit}`;
}

/**
 * One measurement across a patient's visits: single series, so no legend (the title names
 * it). Latest value labelled directly; hover any visit for its value; a table view for
 * screen readers and for exact values.
 */
export function MeasurementTrend({
  title,
  points,
  currentStudyId,
}: {
  title: string;
  points: MeasurementPoint[];
  currentStudyId: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);
  if (points.length === 0) return null;

  const unit = points[0].unit;
  const dates = points.map((p) => new Date(p.studyDate ?? p.receivedAt).getTime());
  const values = points.map((p) => p.value);
  const t0 = Math.min(...dates);
  const t1 = Math.max(...dates);
  const vMax = Math.max(...values) * 1.1 || 1;
  const x = (t: number) => PAD.left + (t1 === t0 ? 0.5 : (t - t0) / (t1 - t0)) * (W - PAD.left - PAD.right);
  const y = (v: number) => PAD.top + (1 - v / vMax) * (H - PAD.top - PAD.bottom);
  const ticks = [0, 0.5, 1].map((f) => f * vMax);
  const label = (i: number) =>
    new Date(dates[i]).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "2-digit" });
  const first = values[0];
  const last = values[values.length - 1];
  const change = first > 0 ? ((last - first) / first) * 100 : null;

  return (
    <div className="trend">
      <div className="trend-header">
        <div>
          <div className="stat-label">{title}</div>
          <div className="trend-latest">
            {formatValue(last, unit)}
            {change != null && points.length > 1 && (
              <span className="cell-secondary">
                {" "}
                {change <= 0 ? "▼" : "▲"} {Math.abs(change).toFixed(0)}% since first visit
              </span>
            )}
          </div>
        </div>
        <button className="link-button small" onClick={() => setShowTable((s) => !s)}>
          {showTable ? "Chart" : "Table"}
        </button>
      </div>

      {showTable ? (
        <table className="data-table">
          <thead>
            <tr>
              <th>Visit</th>
              <th>{title}</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p, i) => (
              <tr key={p.studyId + p.name}>
                <td>
                  {label(i)}
                  {p.studyId === currentStudyId ? " (this study)" : ""}
                </td>
                <td className="numeric">{formatValue(p.value, p.unit)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width="100%"
          role="img"
          aria-label={`${title} over ${points.length} visits, latest ${formatValue(last, unit)}`}
          onMouseLeave={() => setHover(null)}
        >
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} className="trend-grid" />
              <text x={PAD.left - 6} y={y(t) + 3} className="trend-axis" textAnchor="end">
                {unit === "px" ? `${Math.round(t / 1000)}k` : t.toFixed(0)}
              </text>
            </g>
          ))}
          <text x={PAD.left} y={H - 8} className="trend-axis">
            {label(0)}
          </text>
          {points.length > 1 && (
            <text x={W - PAD.right} y={H - 8} className="trend-axis" textAnchor="end">
              {label(points.length - 1)}
            </text>
          )}
          <polyline
            points={points.map((_, i) => `${x(dates[i])},${y(values[i])}`).join(" ")}
            className="trend-line"
          />
          {points.map((p, i) => (
            <g key={p.studyId + p.name} onMouseEnter={() => setHover(i)}>
              <circle cx={x(dates[i])} cy={y(values[i])} r={14} fill="transparent" />
              <circle
                cx={x(dates[i])}
                cy={y(values[i])}
                r={p.studyId === currentStudyId ? 5 : 4}
                className={p.studyId === currentStudyId ? "trend-dot current" : "trend-dot"}
              />
            </g>
          ))}
          {hover != null && (
            <g pointerEvents="none">
              <line
                x1={x(dates[hover])}
                x2={x(dates[hover])}
                y1={PAD.top}
                y2={H - PAD.bottom}
                className="trend-crosshair"
              />
              <foreignObject
                x={Math.min(x(dates[hover]) + 8, W - 130)}
                y={Math.max(0, y(values[hover]) - 40)}
                width={124}
                height={40}
              >
                <div className="trend-tooltip">
                  <div>{label(hover)}</div>
                  <strong>{formatValue(values[hover], unit)}</strong>
                </div>
              </foreignObject>
            </g>
          )}
        </svg>
      )}
      <div className="cell-secondary">Comparable only between photos taken at the same distance and zoom.</div>
    </div>
  );
}
