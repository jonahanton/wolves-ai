"use client";

import { scaleLinear } from "d3-scale";
import { useEffect, useMemo, useRef, useState } from "react";
import { MorphPath } from "@/components/landing/morph-path";
import type { DistroPoint } from "@/lib/distribution";
import type { WdlShape } from "@/lib/fixtures";
import type { RowColours } from "@/lib/team-colours";

interface WdlCurvesProps {
  shape: WdlShape;
  colours: RowColours;
}

const HEIGHT = 110;
const PAD_X = 4;
const AXIS_H = 22;
const TICKS = 5;
const Y_HEADROOM = 1.12;
const AXIS_TEXT = "oklch(0.965 0.008 95 / 0.5)";
const TICK_MARK = "oklch(0.965 0.008 95 / 0.22)";

function peakOf(curves: DistroPoint[][]): number {
  return Math.max(...curves.flat().map((p) => p.y), 1e-9);
}

// Seed flat so the first paint is a baseline; the curve then blooms up via MorphPath.
function flatten(points: DistroPoint[]): DistroPoint[] {
  return points.map((p) => ({ x: p.x, y: 0 }));
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
    const id = window.requestAnimationFrame(() => setBloomed(true));
    return () => window.cancelAnimationFrame(id);
  }, []);

  const lanes = useMemo(
    () => [
      { id: "home", points: shape.home, colour: colours.home },
      { id: "draw", points: shape.draw, colour: colours.draw },
      { id: "away", points: shape.away, colour: colours.away },
    ],
    [shape, colours],
  );
  const peak = useMemo(() => peakOf(lanes.map((l) => l.points)), [lanes]);

  const x = useMemo(
    () => scaleLinear().domain([0, 1]).range([PAD_X, Math.max(PAD_X, width - PAD_X)]),
    [width],
  );
  const y = useMemo(() => scaleLinear().domain([0, peak * Y_HEADROOM]).range([HEIGHT, 0]), [peak]);
  const ticks = useMemo(() => x.ticks(TICKS), [x]);

  return (
    <div ref={ref} className="relative">
      <svg width={width} height={HEIGHT} className="block overflow-visible">
        {lanes.map((lane) => (
          <MorphPath
            key={lane.id}
            points={bloomed ? lane.points : flatten(lane.points)}
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
