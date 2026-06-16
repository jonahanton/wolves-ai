"use client";

import { scaleLinear } from "d3-scale";
import { curveMonotoneX, line as d3Line } from "d3-shape";
import { useEffect, useMemo, useRef, useState } from "react";
import { Accent, ChartHeading } from "@/components/teams/chart-heading";
import { ChartTooltip } from "@/components/charts/chart-tooltip";
import type { TeamImpact } from "@/lib/impact";
import { type ExitStageBar, exitStageBars, meanStageIndex, modeBar, settledBar } from "@/lib/reach";

interface ExitStageHistogramProps {
  reachProbs: Record<string, number>;
  colour: string;
  teamName: string;
  impact: TeamImpact | null;
}

const HEIGHT = 132;
const TOP = 30;
const AXIS_H = 18;
const AXIS_W = 34;
const PAD_R = 4;
const MIN_OPACITY = 0.28;
const MAX_OPACITY = 0.92;
const TICK = "oklch(0.965 0.008 95 / 0.4)";
const Y_MAX = 1;

interface Hover {
  x: number;
  y: number;
  bar: ExitStageBar;
}

function pct(p: number): string {
  return `${(p * 100).toFixed(1)}%`;
}

export function ExitStageHistogram({ reachProbs, colour, teamName, impact }: ExitStageHistogramProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState<Hover | null>(null);

  const bars = useMemo(() => exitStageBars(reachProbs), [reachProbs]);
  const settled = useMemo(() => settledBar(bars), [bars]);
  const meanIndex = useMemo(() => meanStageIndex(bars), [bars]);
  const mode = useMemo(() => modeBar(bars), [bars]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.round(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const plotLeft = AXIS_W;
  const inner = Math.max(0, width - plotLeft - PAD_R);
  const step = bars.length > 0 ? inner / bars.length : 0;
  const barW = Math.max(2, step);
  const colX = (i: number): number => plotLeft + step * (i + 0.5);
  const y = scaleLinear().domain([0, Y_MAX]).range([TOP + HEIGHT, TOP]);

  const curve =
    settled || width === 0
      ? ""
      : (d3Line<ExitStageBar>()
          .x((_, i) => colX(i))
          .y((b) => y(b.p))
          .curve(curveMonotoneX)(bars) ?? "");

  const meanRoundIndex = Math.round(meanIndex);
  const meanBar = bars[meanRoundIndex];
  const modeIndex = bars.indexOf(mode);
  const showMarkers = !settled && width > 0;

  return (
    <div ref={ref} className="relative">
      <ChartHeading>
        {settled ? (
          <>
            <Accent colour={colour}>{teamName}</Accent> are settled at {mode.noun}.
          </>
        ) : (
          <>
            On average <Accent colour={colour}>{teamName}</Accent> exit in {meanBar?.noun} ({pct(meanBar?.p ?? 0)}). Their
            most common exit is {mode.noun} ({pct(mode.p)}).
          </>
        )}
      </ChartHeading>

      <svg
        width={width}
        height={TOP + HEIGHT + AXIS_H}
        className="block overflow-visible"
        role="img"
        aria-label={
          settled
            ? `${teamName} are settled at ${settled.phrase.toLowerCase()}`
            : `How far ${teamName} are forecast to go: most likely ${mode.phrase.toLowerCase()} (${pct(mode.p)}), on average ${meanBar?.phrase.toLowerCase()}`
        }
      >
        <text x={plotLeft - 6} y={y(1) + 3} textAnchor="end" fontFamily="var(--font-mono)" fontSize={9.5} fill={TICK}>
          100%
        </text>
        <text x={plotLeft - 6} y={y(0)} textAnchor="end" fontFamily="var(--font-mono)" fontSize={9.5} fill={TICK}>
          0%
        </text>
        {bars.map((b, i) => {
          const cx = colX(i);
          const h = y(0) - y(b.p);
          const t = b.p / Y_MAX;
          const dim = settled !== null && settled.key !== b.key;
          const isMode = showMarkers && i === modeIndex;
          const isMean = showMarkers && i === meanRoundIndex;
          const isSettled = settled !== null && settled.key === b.key;
          const tag = isMode && isMean ? "Mean · Mode" : isMode ? "Mode" : isMean ? "Mean" : "";
          const bracket = isMode && b.p > 0 ? `${b.label}, ${pct(b.p)}` : b.label;
          const caption = tag ? `${tag} (${bracket})` : "";
          const showPct = b.p > 0 && !isMode && (isSettled || b.key === "champion");
          const estimate = impact?.exit[b.key];
          const estimateDelta = estimate ? estimate.fromResultsPp + estimate.fromIngamePp : 0;
          const showEstimate = estimate && Math.abs(estimateDelta) >= estimate.displayFloorPp;
          return (
            <g key={b.key}>
              {showEstimate && (
                <rect
                  x={cx - barW / 2 + 1}
                  y={y(estimate.estimated)}
                  width={Math.max(0, barW - 2)}
                  height={Math.max(0, y(0) - y(estimate.estimated))}
                  fill="none"
                  stroke={colour}
                  strokeOpacity={0.58}
                  strokeWidth={1.4}
                  pointerEvents="none"
                />
              )}
              <rect
                x={cx - barW / 2}
                y={y(b.p)}
                width={barW}
                height={Math.max(0, h)}
                fill={colour}
                fillOpacity={dim ? 0.12 : MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * t}
                onMouseEnter={(e) => setHover({ x: e.clientX, y: e.clientY, bar: b })}
                onMouseMove={(e) => setHover({ x: e.clientX, y: e.clientY, bar: b })}
                onMouseLeave={() => setHover(null)}
              >
                <title>{`${b.phrase}: ${pct(b.p)}`}</title>
              </rect>
              {caption && (
                <text
                  x={cx}
                  y={y(b.p) - 20}
                  textAnchor={cx < 70 ? "start" : cx > width - 70 ? "end" : "middle"}
                  fontFamily="var(--font-mono)"
                  fontSize={12}
                  fontWeight={700}
                  fill={colour}
                >
                  {caption}
                </text>
              )}
              {showPct && (
                <text x={cx} y={y(b.p) - 6} textAnchor="middle" fontFamily="var(--font-mono)" fontSize={12.5} fontWeight={600} fill={colour}>
                  {pct(b.p)}
                </text>
              )}
              <text
                x={cx}
                y={TOP + HEIGHT + AXIS_H - 4}
                textAnchor="middle"
                fontFamily="var(--font-mono)"
                fontSize={10.5}
                fill="oklch(0.965 0.008 95 / 0.5)"
                opacity={dim ? 0.4 : 1}
              >
                {b.label}
              </text>
            </g>
          );
        })}
        {curve && (
          <path d={curve} fill="none" stroke={colour} strokeWidth={1.5} strokeOpacity={0.9} strokeLinejoin="round" pointerEvents="none" />
        )}
      </svg>

      {hover && (
        <ChartTooltip x={hover.x} y={hover.y}>
          <div className="font-display text-[12.5px]">
            <div className="font-semibold" style={{ color: colour }}>
              {hover.bar.phrase}
            </div>
            <div className="mt-1 tabular-nums text-cream-dim">{pct(hover.bar.p)} of simulations</div>
            {impact?.exit[hover.bar.key] &&
              Math.abs(impact.exit[hover.bar.key].fromResultsPp + impact.exit[hover.bar.key].fromIngamePp) >=
                impact.exit[hover.bar.key].displayFloorPp && (
                <div className="mt-1 tabular-nums text-cream-faint">
                  Now an estimated {pct(impact.exit[hover.bar.key].estimated)}
                </div>
              )}
          </div>
        </ChartTooltip>
      )}
    </div>
  );
}
