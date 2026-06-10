import { formatPctBare } from "@/lib/format";
import type { ReachPoint } from "@/lib/team-sheet-view";

interface ReachCurveProps {
  reach: ReachPoint[];
  highlight?: boolean;
}

const WIDTH = 320;
const HEIGHT = 104;
const TOP = 18;
const BOTTOM = 20;
const SIDE = 16;

export function ReachCurve({ reach, highlight = false }: ReachCurveProps) {
  if (reach.length < 2) return null;
  const innerWidth = WIDTH - SIDE * 2;
  const innerHeight = HEIGHT - TOP - BOTTOM;
  const points = reach.map((point, i) => ({
    ...point,
    x: SIDE + (i * innerWidth) / (reach.length - 1),
    y: TOP + (1 - point.prob) * innerHeight,
  }));
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
  const stroke = highlight ? "var(--gold)" : "var(--muted-foreground)";

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="w-full" role="img" aria-label="Reach probability by round">
      <line x1={SIDE} y1={TOP + innerHeight} x2={WIDTH - SIDE} y2={TOP + innerHeight} stroke="var(--border)" />
      <path d={path} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinecap="round" />
      {points.map((point) => (
        <g key={point.label}>
          <circle cx={point.x} cy={point.y} r="2.4" fill={stroke} />
          <text x={point.x} y={point.y - 6} textAnchor="middle" fontSize="10" fill="var(--muted-foreground)">
            {formatPctBare(point.prob)}
          </text>
          <text x={point.x} y={HEIGHT - 4} textAnchor="middle" fontSize="11" fill="var(--muted-foreground)">
            {point.label}
          </text>
        </g>
      ))}
    </svg>
  );
}
