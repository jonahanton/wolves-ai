import { chartGeometry, polyline, type TeamSeries } from "@/lib/series";

interface SeriesChartProps {
  series: TeamSeries[];
  ariaLabel: string;
}

export function SeriesChart({ series, ariaLabel }: SeriesChartProps) {
  const { frame, lines } = chartGeometry(series);
  const singlePoint = lines.every((line) => line.points.length <= 1);

  return (
    <svg viewBox={`0 0 ${frame.width} ${frame.height}`} role="img" aria-label={ariaLabel} className="w-full">
      {frame.gridlines.map((grid) => (
        <g key={grid.y}>
          <line
            x1={frame.left}
            y1={grid.y}
            x2={frame.width - frame.right + 28}
            y2={grid.y}
            className="stroke-hairline"
            strokeWidth="1"
          />
          <text x="0" y={grid.y + 5} className="fill-cream-faint font-mono text-[15px]">
            {grid.label}%
          </text>
        </g>
      ))}
      {lines.map((line) => {
        const last = line.points[line.points.length - 1];
        if (!last) return null;
        return (
          <g key={line.teamId}>
            {line.points.length > 1 && (
              <polyline
                fill="none"
                points={polyline(line.points)}
                stroke={line.colour}
                strokeWidth={line.featured ? 2.2 : 1.6}
              />
            )}
            {line.points
              .filter((p) => p.agent)
              .map((p, i) => (
                <path key={i} d={`M${p.x},${p.y - 6} l5.5,6 -5.5,6 -5.5,-6z`} fill={line.colour} />
              ))}
            <circle cx={last.x} cy={last.y} r={line.featured ? 3.5 : 3} fill={line.colour} />
            <text
              x={last.x + 12}
              y={line.labelY + 5}
              fill={line.colour}
              className={`font-mono ${line.featured ? "text-[18px] font-medium" : "text-[16px]"}`}
            >
              {line.label}
            </text>
          </g>
        );
      })}
      {singlePoint && (
        <text
          x={frame.left}
          y={frame.height - 8}
          className="fill-cream-faint font-mono text-[13px]"
        >
          first published run · the line begins tomorrow
        </text>
      )}
    </svg>
  );
}
