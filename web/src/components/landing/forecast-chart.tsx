"use client";

import { bisector } from "d3-array";
import { easeCubicInOut } from "d3-ease";
import { scaleLinear, scaleTime } from "d3-scale";
import { select } from "d3-selection";
import { line as d3Line } from "d3-shape";
import "d3-transition";
import { useEffect, useMemo, useRef, useState } from "react";
import { ChartTooltip } from "@/components/charts/chart-tooltip";
import {
  type ChartPoint,
  type ForecastChartData,
  type Outcome,
  resultsAround,
  type Source,
  type TeamLine,
} from "@/lib/forecast-series";

interface ForecastChartProps {
  data: ForecastChartData;
  source: Source;
  outcome: Outcome;
  ariaLabel: string;
}

interface ActiveLine {
  teamId: string;
  name: string;
  colour: string;
  featured: boolean;
  points: ChartPoint[];
  estimate: ChartPoint[];
}

interface HoverState {
  clientX: number;
  clientY: number;
  t: number;
}

const DURATION = 400;
const HEIGHT = 320;
const MARGIN = { top: 16, right: 96, bottom: 30, left: 44 };
const MOBILE_MARGIN = { top: 14, right: 74, bottom: 28, left: 36 };
const MOBILE_BREAK = 560;
const DAY_MS = 86_400_000;

const HAIRLINE = "oklch(0.965 0.008 95 / 0.1)";
const AXIS_TEXT = "oklch(0.965 0.008 95 / 0.42)";

function activeLines(data: ForecastChartData, source: Source, outcome: Outcome): ActiveLine[] {
  return data.teams
    .map((team: TeamLine) => ({
      teamId: team.teamId,
      name: team.name,
      colour: team.colour,
      featured: team.featured,
      points: source === "wolves" ? team.wolves[outcome] : team.market[outcome],
      estimate: source === "wolves" ? team.estimate[outcome] : [],
    }))
    .filter((team) => team.points.length > 0);
}

function abbreviate(name: string): string {
  return name.replace(/[^A-Za-z]/g, "").slice(0, 3).toUpperCase();
}

function formatValue(value: number): string {
  return (value * 100).toFixed(1);
}

function formatDay(t: number): string {
  return new Date(t).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "Europe/London" });
}

function formatTick(d: Date, first: boolean): string {
  const intraday = d.getHours() !== 0 || d.getMinutes() !== 0;
  if (!intraday) return formatDay(+d);
  const time = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });
  return first ? `${formatDay(+d)} ${time}` : time;
}

export function ForecastChart({ data, source, outcome, ariaLabel }: ForecastChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const scaffoldedRef = useRef(false);
  const previousSourceRef = useRef(source);
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState<HoverState | null>(null);

  const lines = useMemo(() => activeLines(data, source, outcome), [data, source, outcome]);

  const margin = width < MOBILE_BREAK ? MOBILE_MARGIN : MARGIN;
  const height = HEIGHT;

  const { x, y, hoverTimes } = useMemo(() => {
    const points = lines.flatMap((team) => [...team.points, ...team.estimate]);
    const times = points.map((p) => p.t);
    const lo = times.length ? Math.min(...times) : 0;
    const hi = times.length ? Math.max(...times) : DAY_MS;
    const pad = Math.max((hi - lo) * 0.04, DAY_MS / 3);
    const xScale = scaleTime()
      .domain([lo - pad, hi + pad])
      .range([margin.left, Math.max(margin.left + 1, width - margin.right)]);
    const maxValue = Math.max(0.04, ...points.map((p) => p.value)) * 1.25;
    const yScale = scaleLinear()
      .domain([0, maxValue])
      .range([height - margin.bottom, margin.top]);
    const uniqueTimes = [...new Set(times)].sort((a, b) => a - b);
    return { x: xScale, y: yScale, hoverTimes: uniqueTimes };
  }, [lines, width, margin, height]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const measured = entries[0].contentRect.width;
      if (measured > 0) setWidth(measured);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!svgRef.current || scaffoldedRef.current) return;
    const svg = select(svgRef.current);
    svg.append("g").attr("class", "gridlines");
    svg.append("g").attr("class", "x-axis");
    svg.append("g").attr("class", "y-axis");
    svg.append("g").attr("class", "series");
    svg.append("g").attr("class", "estimates");
    svg.append("g").attr("class", "markers");
    svg.append("g").attr("class", "labels");
    svg.append("g").attr("class", "hover-layer");
    scaffoldedRef.current = true;
  }, []);

  useEffect(() => {
    if (!svgRef.current || !scaffoldedRef.current || width === 0) return;
    const svg = select(svgRef.current);
    const crossfade = previousSourceRef.current !== source;
    previousSourceRef.current = source;

    const yTicks = y.ticks(4).filter((tick) => tick > 0);
    svg
      .select<SVGGElement>(".gridlines")
      .selectAll<SVGLineElement, number>("line")
      .data(yTicks, (d) => String(d))
      .join(
        (enter) =>
          enter
            .append("line")
            .attr("x1", margin.left)
            .attr("x2", width - margin.right)
            .attr("stroke", HAIRLINE)
            .attr("y1", (d) => y(d))
            .attr("y2", (d) => y(d)),
        (update) =>
          update.call((u) =>
            u
              .transition()
              .duration(DURATION)
              .ease(easeCubicInOut)
              .attr("x2", width - margin.right)
              .attr("y1", (d) => y(d))
              .attr("y2", (d) => y(d)),
          ),
        (exit) => exit.remove(),
      );

    svg
      .select<SVGGElement>(".y-axis")
      .selectAll<SVGTextElement, number>("text")
      .data(yTicks, (d) => String(d))
      .join("text")
      .attr("x", margin.left - 8)
      .attr("text-anchor", "end")
      .attr("dominant-baseline", "middle")
      .attr("font-family", "var(--font-spline-mono)")
      .attr("font-size", 11)
      .attr("fill", AXIS_TEXT)
      .attr("y", (d) => y(d))
      .text((d) => `${Math.round(d * 100)}%`);

    const xTicks = x.ticks(width < MOBILE_BREAK ? 3 : 5);
    svg
      .select<SVGGElement>(".x-axis")
      .selectAll<SVGTextElement, Date>("text")
      .data(xTicks, (d) => String(+d))
      .join("text")
      .attr("y", height - margin.bottom + 20)
      .attr("text-anchor", "middle")
      .attr("font-family", "var(--font-spline-mono)")
      .attr("font-size", 11)
      .attr("fill", AXIS_TEXT)
      .attr("x", (d) => x(d))
      .text((d, i) => formatTick(d, i === 0));

    const lineGen = d3Line<ChartPoint>()
      .x((p) => x(p.t))
      .y((p) => y(p.value));

    const seriesG = svg.select<SVGGElement>(".series");
    const paths = seriesG
      .selectAll<SVGPathElement, ActiveLine>("path")
      .data(
        lines.filter((team) => team.points.length > 1),
        (d) => d.teamId,
      );
    paths
      .enter()
      .append("path")
      .attr("fill", "none")
      .attr("stroke-width", (d) => (d.featured ? 2.2 : 1.6))
      .attr("stroke", (d) => d.colour)
      .attr("d", (d) => lineGen(d.points))
      .attr("opacity", 1);
    if (crossfade) {
      paths
        .attr("opacity", 0)
        .attr("d", (d) => lineGen(d.points))
        .transition()
        .duration(DURATION)
        .ease(easeCubicInOut)
        .attr("opacity", 1);
    } else {
      paths
        .transition()
        .duration(DURATION)
        .ease(easeCubicInOut)
        .attr("stroke", (d) => d.colour)
        .attr("opacity", 1)
        .attr("d", (d) => lineGen(d.points));
    }
    paths.exit().remove();

    const estimateG = svg.select<SVGGElement>(".estimates");
    const estimatePaths = estimateG
      .selectAll<SVGPathElement, ActiveLine>("path")
      .data(
        lines.filter((team) => team.estimate.length > 1),
        (d) => d.teamId,
      );
    estimatePaths
      .enter()
      .append("path")
      .attr("fill", "none")
      .attr("stroke-width", 1.4)
      .attr("stroke-dasharray", "2 5")
      .attr("stroke", (d) => d.colour)
      .attr("d", (d) => lineGen(d.estimate))
      .attr("opacity", 0.9);
    estimatePaths
      .transition()
      .duration(DURATION)
      .ease(easeCubicInOut)
      .attr("opacity", 0.9)
      .attr("d", (d) => lineGen(d.estimate));
    estimatePaths.exit().remove();

    interface Marker {
      key: string;
      cx: number;
      cy: number;
      colour: string;
      kind: "run" | "capture" | "estimate";
    }
    const markers: Marker[] = lines.flatMap((team) => [
      ...team.points.map((p) => ({
        key: `${team.teamId}|${p.t}`,
        cx: x(p.t),
        cy: y(p.value),
        colour: team.featured ? "oklch(0.8 0.13 78)" : team.colour,
        kind: source === "wolves" ? ("run" as const) : ("capture" as const),
      })),
      ...team.estimate.slice(-1).map((p) => ({
        key: `${team.teamId}|est`,
        cx: x(p.t),
        cy: y(p.value),
        colour: team.colour,
        kind: "estimate" as const,
      })),
    ]);
    svg
      .select<SVGGElement>(".markers")
      .selectAll<SVGPathElement, Marker>("path")
      .data(markers, (d) => d.key)
      .join(
        (enter) =>
          enter
            .append("path")
            .attr("transform", (d) => `translate(${d.cx},${d.cy})`)
            .attr("opacity", 1),
        (update) =>
          update.call((u) =>
            u
              .transition()
              .duration(DURATION)
              .ease(easeCubicInOut)
              .attr("opacity", 1)
              .attr("transform", (d) => `translate(${d.cx},${d.cy})`),
          ),
        (exit) => exit.remove(),
      )
      .attr("d", (d) => {
        if (d.kind === "run") return "M0,-4.4 L4.4,0 L0,4.4 L-4.4,0 Z";
        return "M0,-2.6 A2.6,2.6 0 1,0 0.001,-2.6 Z";
      })
      .attr("fill", (d) => (d.kind === "estimate" ? "oklch(0.175 0.014 65)" : d.colour))
      .attr("stroke", (d) => d.colour)
      .attr("stroke-width", (d) => (d.kind === "estimate" ? 1.4 : 0));

    interface EndLabel {
      teamId: string;
      text: string;
      colour: string;
      featured: boolean;
      labelY: number;
      lastX: number;
      estimated: boolean;
    }
    const labels: EndLabel[] = lines
      .map((team) => {
        const last = team.estimate.at(-1) ?? team.points.at(-1);
        if (!last) return null;
        return {
          teamId: team.teamId,
          text: `${abbreviate(team.name)} ${formatValue(last.value)}`,
          colour: team.featured ? team.colour : "oklch(0.965 0.008 95 / 0.55)",
          featured: team.featured,
          labelY: y(last.value),
          lastX: x(last.t),
          estimated: team.estimate.length > 1,
        };
      })
      .filter((label): label is EndLabel => label !== null)
      .sort((a, b) => a.labelY - b.labelY);
    const gap = width < MOBILE_BREAK ? 16 : 18;
    for (let i = 1; i < labels.length; i++) {
      if (labels[i].labelY - labels[i - 1].labelY < gap) labels[i].labelY = labels[i - 1].labelY + gap;
    }
    svg
      .select<SVGGElement>(".labels")
      .selectAll<SVGTextElement, EndLabel>("text")
      .data(labels, (d) => d.teamId)
      .join(
        (enter) =>
          enter
            .append("text")
            .attr("fill", (d) => d.colour)
            .attr("x", (d) => d.lastX + 10)
            .attr("y", (d) => d.labelY),
        (update) =>
          update.call((u) =>
            u
              .transition()
              .duration(DURATION)
              .ease(easeCubicInOut)
              .attr("fill", (d) => d.colour)
              .attr("x", (d) => d.lastX + 10)
              .attr("y", (d) => d.labelY),
          ),
      )
      .attr("font-family", "var(--font-spline-mono)")
      .attr("font-size", width < MOBILE_BREAK ? 11 : 12)
      .attr("font-weight", (d) => (d.featured ? 500 : 400))
      .attr("dominant-baseline", "middle")
      .text((d) => (d.estimated ? `${d.text} est.` : d.text));
  }, [lines, source, x, y, width, height, margin]);

  useEffect(() => {
    if (!svgRef.current || !scaffoldedRef.current) return;
    const layer = select(svgRef.current).select<SVGGElement>(".hover-layer");
    layer.selectAll("*").remove();
    if (!hover) return;
    layer
      .append("line")
      .attr("x1", x(hover.t))
      .attr("x2", x(hover.t))
      .attr("y1", margin.top)
      .attr("y2", height - margin.bottom)
      .attr("stroke", "oklch(0.965 0.008 95 / 0.25)")
      .attr("stroke-dasharray", "3 3");
    for (const team of lines) {
      const point =
        team.points.find((p) => p.t === hover.t) ?? team.estimate.find((p) => p.t === hover.t) ?? null;
      if (!point) continue;
      layer
        .append("circle")
        .attr("cx", x(point.t))
        .attr("cy", y(point.value))
        .attr("r", 3.6)
        .attr("fill", "none")
        .attr("stroke", team.colour)
        .attr("stroke-width", 1.4);
    }
  }, [hover, lines, x, y, margin, height]);

  function onPointerMove(event: React.PointerEvent<SVGRectElement>) {
    if (!hoverTimes.length || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const t = x.invert(event.clientX - rect.left).getTime();
    const index = bisector((time: number) => time).center(hoverTimes, t);
    setHover({ clientX: event.clientX, clientY: event.clientY, t: hoverTimes[index] });
  }

  const hovered = hover
    ? {
        day: new Date(hover.t).toISOString().slice(0, 10),
        rows: lines.flatMap((team) => {
          const run = team.points.find((p) => p.t === hover.t);
          const estimate = team.estimate.find((p) => p.t === hover.t);
          const point = run ?? estimate;
          if (!point) return [];
          return [
            {
              teamId: team.teamId,
              name: team.name,
              colour: team.featured ? "oklch(0.69 0.19 25)" : "oklch(0.965 0.008 95 / 0.78)",
              value: point.value,
              estimated: !run,
              runId: run?.runId,
            },
          ];
        }),
      }
    : null;
  const hoveredResults = hovered ? resultsAround(data.results, hovered.day) : [];

  return (
    <div ref={containerRef} className="relative">
      <svg
        ref={svgRef}
        role="img"
        aria-label={ariaLabel}
        width={width || undefined}
        height={height}
        viewBox={width ? `0 0 ${width} ${height}` : undefined}
        className="block w-full"
      >
        <rect
          x={margin.left}
          y={margin.top}
          width={Math.max(0, width - margin.left - margin.right)}
          height={height - margin.top - margin.bottom}
          fill="transparent"
          onPointerMove={onPointerMove}
          onPointerLeave={() => setHover(null)}
        />
      </svg>
      {hover && hovered && hovered.rows.length > 0 && (
        <ChartTooltip x={hover.clientX} y={hover.clientY}>
          <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-cream-faint">
            {formatDay(hover.t)}
            {hovered.rows.some((row) => row.estimated) && " · estimated"}
          </div>
          <div className="mt-2 space-y-1">
            {hovered.rows.map((row) => (
              <div key={row.teamId} className="flex items-baseline justify-between gap-4">
                <span className="text-[13px]" style={{ color: row.colour }}>
                  {row.name}
                </span>
                <span className="font-mono text-[13px] text-cream">
                  {formatValue(row.value)}%{row.estimated && <span className="text-cream-faint"> est.</span>}
                </span>
              </div>
            ))}
          </div>
          {hoveredResults.length > 0 && (
            <div className="mt-2.5 border-t border-hairline pt-2">
              <div className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-cream-faint">Results</div>
              {hoveredResults.map((row) => (
                <div key={`${row.date}-${row.label}`} className="mt-1 font-mono text-[12px] text-cream-dim">
                  {row.label}
                </div>
              ))}
            </div>
          )}
        </ChartTooltip>
      )}
    </div>
  );
}
