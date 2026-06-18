"use client";

import { easeCubicInOut } from "d3-ease";
import { scaleLinear } from "d3-scale";
import { curveMonotoneX, line as d3Line } from "d3-shape";
import { useEffect, useMemo, useRef, useState } from "react";
import { Accent, ChartHeading } from "@/components/teams/chart-heading";
import { ChartTooltip } from "@/components/charts/chart-tooltip";
import { EstimateToggle } from "@/components/shell/estimate-toggle";
import type { TeamImpact } from "@/lib/impact";
import { type ExitStageBar, exitStageBars, meanStageIndex, modeBar, settledBar } from "@/lib/reach";
import { teamCode } from "@/lib/team-colours";

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

interface StageShiftProps {
  colour: string;
  active: boolean;
  agent: ExitStageBar;
  estimate: ExitStageBar;
  shownNoun: string;
}

function Arrowed({ colour, from, to }: { colour: string; from: string; to: string }) {
  return (
    <span className="whitespace-nowrap font-semibold" style={{ color: colour }}>
      <span className="text-cream-faint">{from}</span>
      <span className="mx-0.5">&rarr;</span>
      {to}
    </span>
  );
}

// One leg of the heading: morphs the noun if the typical round changed, else the %.
function StageShift({ colour, active, agent, estimate, shownNoun }: StageShiftProps) {
  if (!active) {
    return (
      <>
        <Accent colour={colour}>{shownNoun}</Accent> (<Accent colour={colour}>{pct(agent.p)}</Accent>)
      </>
    );
  }
  if (agent.key !== estimate.key) {
    return (
      <>
        <Arrowed colour={colour} from={agent.noun} to={estimate.noun} /> (<Accent colour={colour}>{pct(estimate.p)}</Accent>)
      </>
    );
  }
  return (
    <>
      <Accent colour={colour}>{shownNoun}</Accent> (<Arrowed colour={colour} from={pct(agent.p)} to={pct(estimate.p)} />)
    </>
  );
}

export function ExitStageHistogram({ reachProbs, colour, teamName, impact }: ExitStageHistogramProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState<Hover | null>(null);
  const [showEstimate, setShowEstimate] = useState(false);
  const [blend, setBlend] = useState(0);

  const agentBars = useMemo(() => exitStageBars(reachProbs), [reachProbs]);
  const estimateBars = useMemo<ExitStageBar[]>(
    () => agentBars.map((b) => ({ ...b, p: Math.max(0, impact?.exit[b.key]?.estimated ?? b.p) })),
    [agentBars, impact],
  );
  const hasEstimate = useMemo(
    () =>
      agentBars.some((b) => {
        const stage = impact?.exit[b.key];
        return stage && Math.abs(stage.fromResultsPp + stage.fromIngamePp) >= stage.displayFloorPp;
      }),
    [agentBars, impact],
  );

  const bars = useMemo<ExitStageBar[]>(
    () => agentBars.map((b, i) => ({ ...b, p: b.p + (estimateBars[i].p - b.p) * blend })),
    [agentBars, estimateBars, blend],
  );
  const settled = useMemo(() => settledBar(bars), [bars]);
  const meanIndex = useMemo(() => meanStageIndex(bars), [bars]);
  const mode = useMemo(() => modeBar(bars), [bars]);
  const active = blend > 0.001;

  const agentMeanBar = useMemo(() => agentBars[Math.round(meanStageIndex(agentBars))], [agentBars]);
  const agentMode = useMemo(() => modeBar(agentBars), [agentBars]);
  const estMeanBar = useMemo(() => estimateBars[Math.round(meanStageIndex(estimateBars))], [estimateBars]);
  const estMode = useMemo(() => modeBar(estimateBars), [estimateBars]);

  // Track the live blend so a mid-flight toggle eases from where it is.
  const blendRef = useRef(blend);
  useEffect(() => {
    blendRef.current = blend;
  }, [blend]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.round(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const target = showEstimate ? 1 : 0;
    const reduce =
      typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const duration = reduce ? 0 : 520;
    let raf = 0;
    let start = 0;
    const from = blendRef.current;
    const tick = (ts: number) => {
      if (!start) start = ts;
      const k = duration === 0 ? 1 : Math.min(1, (ts - start) / duration);
      setBlend(from + (target - from) * easeCubicInOut(k));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [showEstimate]);

  const plotLeft = AXIS_W;
  const inner = Math.max(0, width - plotLeft - PAD_R);
  const step = bars.length > 0 ? inner / bars.length : 0;
  const barW = Math.max(2, step);
  // The full "Champion"/"Groups" labels collide once a column is this narrow.
  const compactAxis = step < 54;
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
  // Adjacent mean and mode captions collide on one line; stack the mean caption
  // a row higher so the pair stays legible without running off the chart edge.
  const stackMarkers = showMarkers && modeIndex !== meanRoundIndex && Math.abs(modeIndex - meanRoundIndex) === 1;

  return (
    <div ref={ref} className="relative">
      <div className="mb-3 flex items-start justify-between gap-3">
        <ChartHeading>
          {settled ? (
            <>
              <Accent colour={colour}>{teamName}</Accent> are settled at <Accent colour={colour}>{mode.noun}</Accent>.
            </>
          ) : (
            <>
              On average <Accent colour={colour}>{teamName}</Accent> exit in{" "}
              <StageShift colour={colour} active={active} agent={agentMeanBar} estimate={estMeanBar} shownNoun={meanBar?.noun ?? ""} />.
              Their most common exit is{" "}
              <StageShift colour={colour} active={active} agent={agentMode} estimate={estMode} shownNoun={mode.noun} />.
            </>
          )}
        </ChartHeading>
        {hasEstimate && (
          <EstimateToggle
            on={showEstimate}
            onToggle={() => setShowEstimate((v) => !v)}
            colour={colour}
            code={teamCode(teamName)}
          />
        )}
      </div>

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
          const captionAnchor = cx < 70 ? "start" : cx > width - 70 ? "end" : "middle";
          const captionY = y(b.p) - (stackMarkers && isMean ? 32 : 20);
          const showPct = b.p > 0 && !isMode && (isSettled || b.key === "champion");
          return (
            <g key={b.key}>
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
                  y={captionY}
                  textAnchor={captionAnchor}
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
                {compactAxis ? b.short : b.label}
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
          </div>
        </ChartTooltip>
      )}
    </div>
  );
}
