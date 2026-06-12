import { formatUpdated } from "@/lib/format";
import type { OddsSeries } from "@/lib/market-view";

interface OddsStripProps {
  series: OddsSeries;
  publishedProb: number | null;
  teamName: string;
}

const W = 880;
const H = 220;
const PAD = { left: 52, right: 150, top: 20, bottom: 28 };

export function OddsStrip({ series, publishedProb, teamName }: OddsStripProps) {
  const values = [...series.bookmakers, ...series.polymarket, publishedProb].filter(
    (value): value is number => value !== null,
  );
  if (values.length < 2) return null;
  const lo = Math.min(...values) * 0.94;
  const hi = Math.max(...values) * 1.06;
  const span = Math.max(1, series.labels.length - 1);
  const x = (i: number) => PAD.left + (i / span) * (W - PAD.left - PAD.right);
  const y = (p: number) => PAD.top + (1 - (p - lo) / (hi - lo)) * (H - PAD.top - PAD.bottom);

  const line = (points: (number | null)[]) =>
    points
      .map((value, i) => (value === null ? null : `${x(i).toFixed(1)},${y(value).toFixed(1)}`))
      .filter(Boolean)
      .join(" ");

  const lastBook = lastValue(series.bookmakers);
  const lastPoly = lastValue(series.polymarket);

  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${teamName} market prices`} className="w-full">
        <polyline fill="none" points={line(series.bookmakers)} stroke="oklch(0.965 0.008 95 / 0.5)" strokeWidth="2" />
        <polyline
          fill="none"
          points={line(series.polymarket)}
          stroke="oklch(0.965 0.008 95 / 0.28)"
          strokeWidth="1.6"
          strokeDasharray="5 4"
        />
        {lastBook && (
          <text x={x(lastBook.index) + 10} y={y(lastBook.value) + 4} className="fill-cream-dim font-mono text-[14px]">
            books {(lastBook.value * 100).toFixed(1)}
          </text>
        )}
        {lastPoly && (
          <text x={x(lastPoly.index) + 10} y={y(lastPoly.value) + 22} className="fill-cream-faint font-mono text-[14px]">
            polymarket {(lastPoly.value * 100).toFixed(1)}
          </text>
        )}
        {publishedProb !== null && (
          <g>
            <line
              x1={PAD.left}
              y1={y(publishedProb)}
              x2={W - PAD.right + 24}
              y2={y(publishedProb)}
              stroke="oklch(0.69 0.19 25)"
              strokeWidth="1.4"
              strokeDasharray="3 5"
            />
            <text x={0} y={y(publishedProb) + 4} className="fill-red font-mono text-[14px]">
              us {(publishedProb * 100).toFixed(1)}
            </text>
          </g>
        )}
      </svg>
      <figcaption className="mt-2 font-mono text-[12px] text-cream-faint">
        {series.labels.length} captures · {formatUpdated(series.labels[0])} to{" "}
        {formatUpdated(series.labels[series.labels.length - 1])}
      </figcaption>
    </figure>
  );
}

function lastValue(points: (number | null)[]): { index: number; value: number } | null {
  for (let i = points.length - 1; i >= 0; i--) {
    const value = points[i];
    if (value !== null) return { index: i, value };
  }
  return null;
}
