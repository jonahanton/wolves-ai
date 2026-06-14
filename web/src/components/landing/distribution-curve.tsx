"use client";

import { scaleLinear } from "d3-scale";
import { ChevronRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { ChartTooltip } from "@/components/charts/chart-tooltip";
import { MechanismNote } from "@/components/landing/mechanism-note";
import { MorphPath } from "@/components/landing/morph-path";
import {
  type Bar,
  type CampCurve,
  campCurves,
  campOffsets,
  campPalette,
  combinedCurve,
  type DistroPoint,
  gridX,
  histogramBars,
  humaniseKey,
  laneMax,
  ourCall,
  peakDensity,
  resampleCurve,
} from "@/lib/distribution";
import { barHover, type HoverInfo } from "@/lib/distribution-hover";
import type { ScenarioWeightOut } from "@/lib/snapshot";
import type { CellShape } from "@/lib/sidecars";

export interface CampMeta {
  key: string;
  label: string;
  summary: string;
  prob: number;
}

interface DistributionCurveProps {
  cell: CellShape;
  xMax: number;
  weights: ScenarioWeightOut[];
  campMeta: Map<string, CampMeta>;
  colour: string;
  why: string | undefined;
}

const COMBINED_H = 64;
const LANE_CURVE_H = 28;
const LANE_LABEL_BAND = 18;
const PAD_X = 4;
const AXIS_H = 26;
const TICKS = 6;
const GRID_SAMPLES = 96;
const Y_HEADROOM = 1.1;
const LABEL_PAD = 20;

// Marker text sits in a group at the mean; centre it on the line, but anchor to
// an edge when the mean is within a label-width of the plot bounds so it can't clip.
function labelAnchor(markerX: number, width: number): "start" | "middle" | "end" {
  if (markerX < LABEL_PAD) return "start";
  if (markerX > width - LABEL_PAD) return "end";
  return "middle";
}

function labelDx(markerX: number, width: number): number {
  if (markerX < LABEL_PAD) return -markerX + 2;
  if (markerX > width - LABEL_PAD) return width - markerX - 2;
  return 0;
}
const SLIDE = "transition-transform duration-[460ms] ease-[cubic-bezier(0.25,1,0.5,1)] motion-reduce:transition-none";

const AXIS_TEXT = "oklch(0.965 0.008 95 / 0.5)";
const TICK_MARK = "oklch(0.965 0.008 95 / 0.22)";
const MARKER = "oklch(0.965 0.008 95 / 0.45)";

export function DistributionCurve({ cell, xMax, weights, campMeta, colour, why }: DistributionCurveProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState<HoverInfo | null>(null);
  const [open, setOpen] = useState(false);

  const call = useMemo(() => ourCall(cell), [cell]);
  const grid = useMemo(() => gridX(xMax, GRID_SAMPLES), [xMax]);
  const combinedGrid = useMemo(() => resampleCurve(combinedCurve(cell), grid), [cell, grid]);
  const camps = useMemo(
    () =>
      campCurves(cell, weights)
        .filter((c) => c.weight > 0)
        .sort((a, b) => b.weight - a.weight),
    [cell, weights],
  );
  const palette = useMemo(() => campPalette(camps.map((c) => c.key)), [camps]);
  const offsets = useMemo(() => campOffsets(camps), [camps]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.round(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const x = useMemo(
    () => scaleLinear().domain([0, xMax]).range([PAD_X, Math.max(PAD_X, width - PAD_X)]),
    [xMax, width],
  );
  const ticks = useMemo(() => x.ticks(TICKS), [x]);
  const split = camps.length > 1;

  return (
    <div ref={ref} className="relative">
      <Combined cell={cell} grid={combinedGrid} colour={colour} x={x} width={width} call={call} onHover={setHover} />

      <svg width={width} height={AXIS_H} className="mt-2 block" aria-hidden>
        {ticks.map((t) => {
          const px = x(t);
          const anchor = px < 12 ? "start" : px > width - 12 ? "end" : "middle";
          return (
            <g key={t} transform={`translate(${px},0)`}>
              <line y1={0} y2={5} stroke={TICK_MARK} />
              <text y={18} textAnchor={anchor} fill={AXIS_TEXT} fontFamily="var(--font-mono)" fontSize={12}>
                {Math.round(t * 100)}%
              </text>
            </g>
          );
        })}
      </svg>

      {why && <p className="mt-3 font-display text-[13px] leading-relaxed text-cream-dim">{why}</p>}

      {split && (
        <>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="mt-3 flex w-full items-center gap-1.5 text-left font-display text-[13px] font-semibold text-cream"
          >
            <ChevronRight size={15} className="shrink-0 transition-transform duration-300" style={{ transform: open ? "rotate(90deg)" : "none" }} />
            Why this shape?
            <span className="font-normal text-cream-faint">
              A {camps.length}-component mixture density, weighted{" "}
              {camps.map((c) => `${Math.round(c.weight * 100)}%`).join(" / ")}
            </span>
          </button>

          <div className="grid transition-[grid-template-rows] duration-300 ease-out" style={{ gridTemplateRows: open ? "1fr" : "0fr" }}>
            <div className="overflow-hidden">
              <div className="mt-3 flex flex-col gap-2">
                {camps.map((camp, i) => (
                  <Lane
                    key={camp.key}
                    camp={camp}
                    grid={resampleCurve(camp.points, grid)}
                    meta={campMeta.get(camp.key)}
                    hue={palette[camp.key]}
                    offset={offsets[i]}
                    x={x}
                    width={width}
                    onHover={setHover}
                  />
                ))}
              </div>
              <MechanismNote />
            </div>
          </div>
        </>
      )}

      {hover && (
        <ChartTooltip x={hover.clientX} y={hover.clientY}>
          <div className="max-w-[240px] font-display text-[12.5px]">
            <div className="font-semibold tabular-nums" style={{ color: hover.hue }}>
              {hover.range}
            </div>
            <div className="mt-1 leading-snug text-cream-dim">{hover.share}</div>
            {hover.title && <div className="mt-1 font-display text-[11px] text-cream-faint">{hover.title}</div>}
          </div>
        </ChartTooltip>
      )}
    </div>
  );
}

interface CombinedProps {
  cell: CellShape;
  grid: DistroPoint[];
  colour: string;
  x: ReturnType<typeof scaleLinear<number, number>>;
  width: number;
  call: number;
  onHover: (h: HoverInfo | null) => void;
}

function Combined({ cell, grid, colour, x, width, call, onHover }: CombinedProps) {
  const h = COMBINED_H;
  const peak = peakDensity(cell);
  const y = scaleLinear().domain([0, (peak || 1) * Y_HEADROOM]).range([h, 0]);
  const bars = histogramBars(cell);
  const callX = x(call);

  return (
    <svg width={width} height={h + 16} className="mt-3 block overflow-visible">
      <g transform="translate(0,16)">
        {width > 0 && call > 0 && (
          <g className={SLIDE} style={{ transform: `translateX(${callX}px)` }}>
            <line x1={0} x2={0} y1={-12} y2={h} stroke={MARKER} strokeWidth={1} strokeDasharray="2 3" />
            <text x={labelDx(callX, width)} y={-16} textAnchor={labelAnchor(callX, width)} fill={colour} fontFamily="var(--font-mono)" fontSize={14} fontWeight={700} letterSpacing="0.04em">
              {`${(call * 100).toFixed(1)}%`}
            </text>
          </g>
        )}
        <HistogramBars bars={bars} peak={peak} x={x} y={y} height={h} hue={colour} title="" onHover={onHover} />
        <MorphPath points={grid} x={x} y={y} height={h} colour={colour} width={width} />
      </g>
    </svg>
  );
}

interface LaneProps {
  camp: CampCurve;
  grid: DistroPoint[];
  meta: CampMeta | undefined;
  hue: string;
  offset: number;
  x: ReturnType<typeof scaleLinear<number, number>>;
  width: number;
  onHover: (h: HoverInfo | null) => void;
}

function Lane({ camp, grid, meta, hue, offset, x, width, onHover }: LaneProps) {
  const peak = laneMax(camp);
  const y = scaleLinear().domain([0, peak * Y_HEADROOM]).range([LANE_CURVE_H, 0]);
  const pct = Math.round(camp.weight * 100);
  const label = meta?.label ?? humaniseKey(camp.key);
  const meanX = meta?.prob != null ? x(meta.prob) : 0;

  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <div className="flex items-baseline gap-2">
          <span className="font-display text-[13px] font-semibold" style={{ color: hue }}>
            {label}
          </span>
          {meta?.summary && <span className="font-display text-[12px] leading-snug text-cream-faint">{meta.summary}</span>}
        </div>
        <div className="flex shrink-0 items-center gap-2.5">
          <div className="flex h-[9px] w-24 overflow-hidden rounded-[2px] bg-cream/10">
            <div style={{ width: `${pct}%`, marginLeft: `${offset * 100}%`, backgroundColor: hue }} />
          </div>
          <span className="font-display text-[12.5px] font-semibold tabular-nums" style={{ color: hue }}>
            {pct}%
          </span>
        </div>
      </div>
      <div className="relative mt-0.5">
        <svg width={width} height={LANE_CURVE_H + LANE_LABEL_BAND} className="block">
          {width > 0 && meanX > 0 && (
            <g className={SLIDE} style={{ transform: `translateX(${meanX}px)` }}>
              <text x={labelDx(meanX, width)} y={12} textAnchor={labelAnchor(meanX, width)} fill={hue} fontFamily="var(--font-display)" fontSize={12} fontWeight={600}>
                {`${((meta?.prob ?? 0) * 100).toFixed(0)}%`}
              </text>
              <line x1={0} x2={0} y1={LANE_LABEL_BAND} y2={LANE_CURVE_H + LANE_LABEL_BAND} stroke={hue} strokeWidth={1} strokeDasharray="2 3" strokeOpacity={0.7} />
            </g>
          )}
          <g transform={`translate(0,${LANE_LABEL_BAND})`}>
            <HistogramBars bars={camp.bars} peak={peak} x={x} y={y} height={LANE_CURVE_H} hue={hue} title={label} onHover={onHover} />
            <MorphPath points={grid} x={x} y={y} height={LANE_CURVE_H} colour={hue} width={width} />
          </g>
        </svg>
      </div>
    </div>
  );
}

interface HistogramBarsProps {
  bars: Bar[];
  peak: number;
  x: ReturnType<typeof scaleLinear<number, number>>;
  y: ReturnType<typeof scaleLinear<number, number>>;
  height: number;
  hue: string;
  title: string;
  onHover: (h: HoverInfo | null) => void;
}

const MIN_OPACITY = 0.28;
const MAX_OPACITY = 0.92;

function HistogramBars({ bars, peak, x, y, height, hue, title, onHover }: HistogramBarsProps) {
  return (
    <>
      {bars.map((b, i) => {
        const bx = x(b.x0);
        const bw = Math.max(0.5, x(b.x1) - bx - 1);
        const t = peak > 0 ? b.y / peak : 0;
        return (
          <rect
            key={i}
            x={bx}
            y={y(b.y)}
            width={bw}
            height={height - y(b.y)}
            fill={hue}
            fillOpacity={MIN_OPACITY + (MAX_OPACITY - MIN_OPACITY) * t}
            onMouseEnter={(e) => onHover(barHover(e, b, title, hue))}
            onMouseMove={(e) => onHover(barHover(e, b, title, hue))}
            onMouseLeave={() => onHover(null)}
          />
        );
      })}
    </>
  );
}
