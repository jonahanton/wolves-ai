import type { WormGeometry } from "@/lib/worm";
import { wormPath } from "@/lib/worm";

interface WormChartProps {
  geometry: WormGeometry;
  homeName: string;
  awayName: string;
}

export function WormChart({ geometry, homeName, awayName }: WormChartProps) {
  const last = geometry.points[geometry.points.length - 1];
  return (
    <svg
      viewBox={`0 0 ${geometry.width} ${geometry.height}`}
      role="img"
      aria-label={`${homeName} win probability through the match`}
      className="w-full"
    >
      <line
        x1="52"
        y1={geometry.midline}
        x2={geometry.width - 28}
        y2={geometry.midline}
        className="stroke-hairline"
        strokeWidth="1"
        strokeDasharray="4 5"
      />
      <text x="0" y={geometry.midline + 4} className="fill-cream-faint font-mono text-[13px]">
        50%
      </text>
      <text x="52" y="14" className="fill-cream-faint font-mono text-[12px]">
        {homeName} win
      </text>
      <text x="52" y={geometry.height - 6} className="fill-cream-faint font-mono text-[12px]">
        {awayName} win
      </text>
      <path d={wormPath(geometry.points)} fill="none" stroke="oklch(0.69 0.19 25)" strokeWidth="2.2" />
      {geometry.goals.map((goal, i) => (
        <g key={i}>
          <line x1={goal.x} y1="18" x2={goal.x} y2={geometry.height - 28} className="stroke-cream-faint" strokeWidth="1" />
          <text x={goal.x + 5} y="28" className="fill-cream-dim font-mono text-[13px]">
            {goal.score}
          </text>
        </g>
      ))}
      <circle cx={last.x} cy={last.y} r="3.5" fill="oklch(0.69 0.19 25)" />
      {last.minute !== null && (
        <text x={last.x - 8} y={last.y - 10} className="fill-cream font-mono text-[14px]">
          {last.minute}&apos;
        </text>
      )}
    </svg>
  );
}
