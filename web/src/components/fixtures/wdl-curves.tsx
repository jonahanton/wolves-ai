"use client";

import { scaleLinear } from "d3-scale";
import { useEffect, useMemo, useRef, useState } from "react";
import { ChartTooltip } from "@/components/charts/chart-tooltip";
import { MorphPath } from "@/components/landing/morph-path";
import { type Bar, curvePeak, type DistroPoint, type WdlShape } from "@/lib/distribution";
import { formatPctBare } from "@/lib/format";
import type { RowColours } from "@/lib/team-colours";
import { type WdlHover, wdlBarHover } from "@/lib/wdl-hover";

interface WdlCurvesProps {
  shape: WdlShape;
  colours: RowColours;
  homeCode: string;
  awayCode: string;
  showDraw: boolean;
}

const HEIGHT = 104;
const TOP = 22;
const PAD_X = 4;
const AXIS_H = 30;
const TICKS = 5;
const Y_HEADROOM = 1.2;
const MIN_OPACITY = 0.16;
const MAX_OPACITY = 0.62;
const AXIS_TEXT = "oklch(0.965 0.008 95 / 0.62)";
const AXIS_LINE = "oklch(0.965 0.008 95 / 0.3)";
const TICK_MARK = "oklch(0.965 0.008 95 / 0.22)";

function flatten(points: DistroPoint[]): DistroPoint[] {
  return points.map((p) => ({ x: p.x, y: 0 }));
}

interface Lane {
  id: string;
  label: string;
  mean: number;
  curve: DistroPoint[];
  bars: Bar[];
  colour: string;
}

export function WdlCurves({ shape, colours, homeCode, awayCode, showDraw }: WdlCurvesProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [bloomed, setBloomed] = useState(false);
  const [hover, setHover] = useState<WdlHover | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.round(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (width === 0) return;
    const id = window.requestAnimationFrame(() => setBloomed(true));
    return () => window.cancelAnimationFrame(id);
  }, [width]);

  const lanes = useMemo<Lane[]>(() => {
    const all: Lane[] = [
      { id: "home", label: `${homeCode} win`, mean: barMean(shape.home.bars), ...shape.home, colour: colours.home },
      { id: "draw", label: "Draw", mean: barMean(shape.draw.bars), ...shape.draw, colour: colours.draw },
      { id: "away", label: `${awayCode} win`, mean: barMean(shape.away.bars), ...shape.away, colour: colours.away },
    ];
    return showDraw ? all : all.filter((l) => l.id !== "draw");
  }, [shape, colours, homeCode, awayCode, showDraw]);
  const peak = useMemo(() => curvePeak(lanes.map((l) => l.curve)), [lanes]);

  const x = useMemo(() => scaleLinear().domain([0, 1]).range([PAD_X, Math.max(PAD_X, width - PAD_X)]), [width]);
  const y = useMemo(() => scaleLinear().domain([0, peak * Y_HEADROOM]).range([HEIGHT, TOP]), [peak]);
  const ticks = useMemo(() => x.ticks(TICKS), [x]);

  return (
    <div ref={ref} className="relative">
      <svg width={width} height={HEIGHT} className="block overflow-visible">
        {lanes.map((lane) => (
          <g key={lane.id}>
            {lane.bars.map((b, i) => {
              const bx = x(b.x0);
              const bw = Math.max(0.5, x(b.x1) - bx - 0.75);
              const t = peak > 0 ? b.y / peak : 0;
              return (
                <rect
                  key={i}
                  x={bx}
                  y={y(b.y)}
                  width={bw}
                  height={HEIGHT - y(b.y)}
                  fill={lane.colour}
                  fillOpacity={MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * t}
                  onMouseEnter={(e) => setHover(wdlBarHover(e, b, lane.label, lane.colour))}
                  onMouseMove={(e) => setHover(wdlBarHover(e, b, lane.label, lane.colour))}
                  onMouseLeave={() => setHover(null)}
                />
              );
            })}
          </g>
        ))}
        {lanes.map((lane) => {
          const mx = x(lane.mean);
          const anchor = mx < 30 ? "start" : mx > width - 30 ? "end" : "middle";
          return (
            <g key={lane.id}>
              <line x1={mx} x2={mx} y1={TOP - 4} y2={HEIGHT} stroke={lane.colour} strokeWidth={1} strokeDasharray="2 3" strokeOpacity={0.7} />
              <text x={mx} y={TOP - 9} textAnchor={anchor} fill={lane.colour} fontFamily="var(--font-display)" fontSize={13} fontWeight={600}>
                {lane.label} {formatPctBare(lane.mean)}%
              </text>
            </g>
          );
        })}
        {lanes.map((lane) => (
          <MorphPath
            key={lane.id}
            points={bloomed ? lane.curve : flatten(lane.curve)}
            x={x}
            y={y}
            height={HEIGHT}
            colour={lane.colour}
            width={width}
          />
        ))}
      </svg>
      <svg width={width} height={AXIS_H} className="mt-0.5 block overflow-visible" aria-hidden>
        <line x1={PAD_X} x2={width - PAD_X} y1={0.5} y2={0.5} stroke={AXIS_LINE} />
        {ticks.map((t) => {
          const px = x(t);
          const anchor = px < 14 ? "start" : px > width - 14 ? "end" : "middle";
          return (
            <g key={t} transform={`translate(${px},0)`}>
              <line y1={0} y2={5} stroke={TICK_MARK} />
              <text y={18} textAnchor={anchor} fill={AXIS_TEXT} fontFamily="var(--font-mono)" fontSize={12}>
                {Math.round(t * 100)}%
              </text>
            </g>
          );
        })}
        <text x={width - PAD_X} y={29} textAnchor="end" fill={AXIS_TEXT} fontFamily="var(--font-display)" fontSize={11} letterSpacing="0.04em">
          win probability &rarr;
        </text>
      </svg>
      {hover && (
        <ChartTooltip x={hover.clientX} y={hover.clientY}>
          <div className="font-display text-[12.5px]">
            <div className="font-semibold tabular-nums" style={{ color: hover.hue }}>
              {hover.label} {hover.range}
            </div>
            <div className="mt-0.5 text-cream-dim">{hover.share}</div>
          </div>
        </ChartTooltip>
      )}
    </div>
  );
}

function barMean(bars: Bar[]): number {
  let m = 0;
  for (const b of bars) m += ((b.x0 + b.x1) / 2) * b.y * (b.x1 - b.x0);
  return m;
}
