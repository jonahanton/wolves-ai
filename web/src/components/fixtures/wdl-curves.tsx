"use client";

import { scaleLinear } from "d3-scale";
import { useEffect, useMemo, useRef, useState } from "react";
import { MorphPath } from "@/components/landing/morph-path";
import { type Bar, curvePeak, type DistroPoint, type WdlShape } from "@/lib/distribution";
import type { RowColours } from "@/lib/team-colours";

interface WdlCurvesProps {
  shape: WdlShape;
  colours: RowColours;
}

const HEIGHT = 96;
const PAD_X = 4;
const AXIS_H = 22;
const TICKS = 5;
const Y_HEADROOM = 1.15;
const MIN_OPACITY = 0.16;
const MAX_OPACITY = 0.6;
const AXIS_TEXT = "oklch(0.965 0.008 95 / 0.5)";
const TICK_MARK = "oklch(0.965 0.008 95 / 0.22)";

function flatten(points: DistroPoint[]): DistroPoint[] {
  return points.map((p) => ({ x: p.x, y: 0 }));
}

function mean(bars: Bar[]): number {
  let m = 0;
  for (const b of bars) m += ((b.x0 + b.x1) / 2) * b.y * (b.x1 - b.x0);
  return m;
}

export function WdlCurves({ shape, colours }: WdlCurvesProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [bloomed, setBloomed] = useState(false);

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

  const lanes = useMemo(
    () => [
      { id: "home", ...shape.home, colour: colours.home },
      { id: "draw", ...shape.draw, colour: colours.draw },
      { id: "away", ...shape.away, colour: colours.away },
    ],
    [shape, colours],
  );
  const peak = useMemo(() => curvePeak(lanes.map((l) => l.curve)), [lanes]);

  const x = useMemo(() => scaleLinear().domain([0, 1]).range([PAD_X, Math.max(PAD_X, width - PAD_X)]), [width]);
  const y = useMemo(() => scaleLinear().domain([0, peak * Y_HEADROOM]).range([HEIGHT, 0]), [peak]);
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
                />
              );
            })}
          </g>
        ))}
        {lanes.map((lane) => {
          const mx = x(mean(lane.bars));
          return (
            <line key={lane.id} x1={mx} x2={mx} y1={0} y2={HEIGHT} stroke={lane.colour} strokeWidth={1} strokeDasharray="2 3" strokeOpacity={0.6} />
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
      <svg width={width} height={AXIS_H} className="mt-1 block" aria-hidden>
        {ticks.map((t) => {
          const px = x(t);
          const anchor = px < 12 ? "start" : px > width - 12 ? "end" : "middle";
          return (
            <g key={t} transform={`translate(${px},0)`}>
              <line y1={0} y2={5} stroke={TICK_MARK} />
              <text y={17} textAnchor={anchor} fill={AXIS_TEXT} fontFamily="var(--font-mono)" fontSize={11}>
                {Math.round(t * 100)}%
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
