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
  // Bars and labels read only at a settled frame; they stay hidden across a replay.
  playing?: boolean;
  // False snaps the stroke without a transition (the rewind to kickoff).
  animate?: boolean;
  morphMs?: number;
  // Linear morph for the continuous drift between keyframes.
  linearMorph?: boolean;
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
  samples: number;
  colour: string;
}

export function WdlCurves({ shape, colours, homeCode, awayCode, showDraw, playing = false, animate = true, morphMs, linearMorph = false }: WdlCurvesProps) {
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

  const active = shape;
  const lanes = useMemo<Lane[]>(() => {
    const all: Lane[] = [
      { id: "home", label: `${homeCode} win`, mean: barMean(active.home.bars), ...active.home, colour: colours.home },
      { id: "draw", label: "Draw", mean: barMean(active.draw.bars), ...active.draw, colour: colours.draw },
      { id: "away", label: `${awayCode} win`, mean: barMean(active.away.bars), ...active.away, colour: colours.away },
    ];
    return showDraw ? all : all.filter((l) => l.id !== "draw");
  }, [active, colours, homeCode, awayCode, showDraw]);
  const peak = useMemo(() => curvePeak(lanes.map((l) => l.curve)), [lanes]);

  const x = useMemo(() => scaleLinear().domain([0, 1]).range([PAD_X, Math.max(PAD_X, width - PAD_X)]), [width]);
  const y = useMemo(() => scaleLinear().domain([0, peak * Y_HEADROOM]).range([HEIGHT, TOP]), [peak]);
  const ticks = useMemo(() => x.ticks(TICKS), [x]);
  const labels = useMemo(() => layoutLabels(lanes, x, width), [lanes, x, width]);

  return (
    <div ref={ref} className="relative">
      <svg width={width} height={HEIGHT} className="block overflow-visible">
        <g style={{ opacity: playing || !bloomed ? 0 : 1, transition: "opacity 260ms ease-out" }}>
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
                  onMouseEnter={(e) => setHover(wdlBarHover(e, b, lane.label, lane.colour, lane.samples))}
                  onMouseMove={(e) => setHover(wdlBarHover(e, b, lane.label, lane.colour, lane.samples))}
                  onMouseLeave={() => setHover(null)}
                />
              );
            })}
          </g>
        ))}
        {lanes.map((lane) => {
          const mx = x(lane.mean);
          return <line key={lane.id} x1={mx} x2={mx} y1={TOP - 4} y2={HEIGHT} stroke={lane.colour} strokeWidth={1} strokeDasharray="2 3" strokeOpacity={0.7} />;
        })}
        {labels.map((l) => (
          <g key={l.id}>
            {Math.abs(l.x - l.markerX) > 1 && (
              <line x1={l.markerX} x2={l.x} y1={TOP - 6} y2={TOP - 9} stroke={l.colour} strokeWidth={1} strokeOpacity={0.5} />
            )}
            <text x={l.x} y={TOP - 11} textAnchor={l.anchor} fill={l.colour} fontFamily="var(--font-display)" fontSize={12.5} fontWeight={600}>
              {l.text}
            </text>
          </g>
        ))}
        </g>
        {lanes.map((lane) => (
          <MorphPath
            key={lane.id}
            points={bloomed ? lane.curve : flatten(lane.curve)}
            x={x}
            y={y}
            height={HEIGHT}
            colour={lane.colour}
            width={width}
            animate={bloomed && animate}
            durationMs={morphMs}
            linear={linearMorph}
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
          Win probability &rarr;
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

interface LabelLayout {
  id: string;
  text: string;
  colour: string;
  markerX: number;
  x: number;
  anchor: "start" | "middle" | "end";
}

const CHAR_PX = 7.4;
const LABEL_GAP = 12;

// Place each peak label at its mean, then nudge colliding labels rightward so they
// never overlap; a leader line keeps each label tied to its marker once nudged.
function layoutLabels(lanes: Lane[], x: (v: number) => number, width: number): LabelLayout[] {
  const items = lanes
    .map((lane) => {
      const text = `${lane.label} ${formatPctBare(lane.mean)}%`;
      return { id: lane.id, text, colour: lane.colour, markerX: x(lane.mean), halfWidth: (text.length * CHAR_PX) / 2 };
    })
    .sort((a, b) => a.markerX - b.markerX);

  let cursor = 0;
  const placed = items.map((it) => {
    const centre = Math.max(cursor + it.halfWidth, it.markerX);
    cursor = centre + it.halfWidth + LABEL_GAP;
    return { ...it, centre };
  });
  const overflow = placed.length > 0 ? Math.max(0, placed[placed.length - 1].centre + placed[placed.length - 1].halfWidth - width) : 0;

  return placed.map((it) => {
    const centre = it.centre - overflow;
    const anchor: LabelLayout["anchor"] = centre - it.halfWidth < 0 ? "start" : centre + it.halfWidth > width ? "end" : "middle";
    const xPos = anchor === "start" ? Math.max(0, centre - it.halfWidth) : anchor === "end" ? Math.min(width, centre + it.halfWidth) : centre;
    return { id: it.id, text: it.text, colour: it.colour, markerX: it.markerX, x: xPos, anchor };
  });
}
