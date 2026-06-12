"use client";

import { bisector } from "d3-array";
import { easeCubicInOut } from "d3-ease";
import { scaleLinear, scaleTime } from "d3-scale";
import { select } from "d3-selection";
import { area as d3Area, curveMonotoneX, line as d3Line } from "d3-shape";
import "d3-transition";
import { useEffect, useMemo, useRef, useState } from "react";
import { ChartTooltip } from "@/components/charts/chart-tooltip";
import {
  type ChartPoint,
  type ForecastChartData,
  type Outcome,
  resultsBetween,
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
const MARGIN = { top: 30, right: 108, bottom: 38, left: 46 };
const MOBILE_MARGIN = { top: 28, right: 80, bottom: 34, left: 38 };
const MOBILE_BREAK = 560;
const DAY_MS = 86_400_000;

const GRID = "oklch(0.965 0.008 95 / 0.07)";
const GRID_BASE = "oklch(0.965 0.008 95 / 0.14)";
const AXIS_TEXT = "oklch(0.965 0.008 95 / 0.5)";
const GUIDE = "oklch(0.965 0.008 95 / 0.24)";
const NIGHT = "oklch(0.175 0.014 65)";
const GOLD = "oklch(0.8 0.13 78)";

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

function formatStamp(t: number): string {
  return new Date(t).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/London",
  });
}

function timeOf(t: number): string {
  return new Date(t).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/London" });
}

function londonDay(d: Date): string {
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "Europe/London" });
}

// One date per day, the hour underneath. The divider and section already carry
// the context; the axis only needs to stay honest about when each point landed.
function tickLabel(d: Date, previous: Date | undefined): { date: string; time: string | null } {
  const midnight = d.getHours() === 0 && d.getMinutes() === 0;
  const newDay = !previous || londonDay(previous) !== londonDay(d);
  return { date: newDay ? londonDay(d) : "", time: midnight ? null : timeOf(+d) };
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
  const empty = lines.length === 0;
  const height = empty ? 200 : width < MOBILE_BREAK ? 360 : 500;

  const { x, y, hoverTimes } = useMemo(() => {
    const points = lines.flatMap((team) => [...team.points, ...team.estimate]);
    const times = points.map((p) => p.t);
    const lo = times.length ? Math.min(...times) : 0;
    const hi = times.length ? Math.max(...times) : DAY_MS;
    const pad = Math.max((hi - lo) * 0.035, DAY_MS / 16);
    const xScale = scaleTime()
      .domain([lo - pad, hi + pad])
      .range([margin.left, Math.max(margin.left + 1, width - margin.right)]);
    const values = points.map((p) => p.value);
    const maxValue = Math.max(0.04, ...values);
    const minValue = values.length ? Math.min(...values) : 0;
    const span = Math.max(maxValue - minValue, 0.012);
    const yLo = Math.max(0, minValue - span * 0.38);
    const yScale = scaleLinear()
      .domain([yLo, maxValue + span * 0.26])
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
    const defs = svg.append("defs");
    const grad = defs.append("linearGradient").attr("id", "featuredArea").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 1);
    grad.append("stop").attr("offset", 0).attr("stop-color", "oklch(0.69 0.19 25)").attr("stop-opacity", 0.18);
    grad.append("stop").attr("offset", 1).attr("stop-color", "oklch(0.69 0.19 25)").attr("stop-opacity", 0);
    svg.append("g").attr("class", "gridlines");
    svg.append("g").attr("class", "y-axis");
    svg.append("g").attr("class", "x-axis");
    svg.append("g").attr("class", "areas");
    svg.append("g").attr("class", "series");
    svg.append("g").attr("class", "estimates");
    svg.append("g").attr("class", "markers");
    svg.append("g").attr("class", "labels");
    svg.append("g").attr("class", "annotations");
    svg.append("g").attr("class", "hover-layer");
    scaffoldedRef.current = true;
  }, []);

  useEffect(() => {
    if (!svgRef.current || !scaffoldedRef.current || width === 0) return;
    const svg = select(svgRef.current);
    if (lines.length === 0) {
      svg.selectAll("g > *").remove();
      return;
    }
    const crossfade = previousSourceRef.current !== source;
    previousSourceRef.current = source;

    const plotRight = width - margin.right;
    const baseY = height - margin.bottom;
    const yTicks = y.ticks(width < MOBILE_BREAK ? 4 : 5).filter((tick) => tick >= y.domain()[0]);

    svg
      .select<SVGGElement>(".gridlines")
      .selectAll<SVGLineElement, number>("line")
      .data(yTicks, (d) => String(d))
      .join(
        (enter) =>
          enter
            .append("line")
            .attr("x1", margin.left)
            .attr("x2", plotRight)
            .attr("stroke", (d) => (d <= y.domain()[0] + 1e-9 ? GRID_BASE : GRID))
            .attr("y1", (d) => y(d))
            .attr("y2", (d) => y(d)),
        (update) =>
          update.call((u) =>
            u
              .transition()
              .duration(DURATION)
              .ease(easeCubicInOut)
              .attr("x2", plotRight)
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
      .attr("x", margin.left - 10)
      .attr("text-anchor", "end")
      .attr("dominant-baseline", "middle")
      .attr("font-family", "var(--font-spline-mono)")
      .attr("font-size", 11)
      .attr("fill", AXIS_TEXT)
      .attr("y", (d) => y(d))
      .text((d) => `${Math.round(d * 100)}%`);

    const xTicks = x.ticks(width < MOBILE_BREAK ? 4 : 6);
    const xAxis = svg
      .select<SVGGElement>(".x-axis")
      .selectAll<SVGGElement, Date>("g.tick")
      .data(xTicks, (d) => String(+d))
      .join((enter) => {
        const g = enter.append("g").attr("class", "tick");
        g.append("text").attr("class", "t-time");
        g.append("text").attr("class", "t-date");
        return g;
      });
    xAxis.attr("transform", (d) => `translate(${x(d)},0)`);
    xAxis.each(function (d, i) {
      const { date, time } = tickLabel(d, xTicks[i - 1]);
      const g = select(this);
      g.select<SVGTextElement>(".t-time")
        .attr("y", baseY + 18)
        .attr("text-anchor", "middle")
        .attr("font-family", "var(--font-spline-mono)")
        .attr("font-size", 11)
        .attr("fill", AXIS_TEXT)
        .text(time ?? "");
      g.select<SVGTextElement>(".t-date")
        .attr("y", baseY + (time ? 32 : 18))
        .attr("text-anchor", "middle")
        .attr("font-family", "var(--font-spline-mono)")
        .attr("font-size", 10.5)
        .attr("letter-spacing", "0.04em")
        .attr("fill", "oklch(0.965 0.008 95 / 0.6)")
        .text(date);
    });

    const lineGen = d3Line<ChartPoint>()
      .x((p) => x(p.t))
      .y((p) => y(p.value))
      .curve(curveMonotoneX);
    const areaGen = d3Area<ChartPoint>()
      .x((p) => x(p.t))
      .y0(baseY)
      .y1((p) => y(p.value))
      .curve(curveMonotoneX);

    // The featured team's visible path runs through its forecasts then onto the
    // running estimate; the area carries that whole line so red has real weight.
    const visiblePath = (team: ActiveLine): ChartPoint[] =>
      team.estimate.length > 1 ? [...team.points.slice(0, -1), ...team.estimate] : team.points;
    const areaSeries = lines.filter((team) => team.featured && visiblePath(team).length > 1);
    svg
      .select<SVGGElement>(".areas")
      .selectAll<SVGPathElement, ActiveLine>("path")
      .data(areaSeries, (d) => d.teamId)
      .join(
        (enter) => enter.append("path").attr("fill", "url(#featuredArea)").attr("d", (d) => areaGen(visiblePath(d))),
        (update) =>
          update.call((u) =>
            u.transition().duration(DURATION).ease(easeCubicInOut).attr("d", (d) => areaGen(visiblePath(d))),
          ),
        (exit) => exit.remove(),
      );

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
      .attr("stroke-linecap", "round")
      .attr("stroke-linejoin", "round")
      .attr("stroke-width", (d) => (d.featured ? 2.6 : 1.5))
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
        .attr("stroke-width", (d) => (d.featured ? 2.6 : 1.5))
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
      .attr("stroke-linecap", "round")
      .attr("stroke-width", (d) => (d.featured ? 2.4 : 1.6))
      .attr("stroke-dasharray", (d) => (d.featured ? "0.1 6.5" : "0.1 5.5"))
      .attr("stroke", (d) => d.colour)
      .attr("d", (d) => lineGen(d.estimate))
      .attr("opacity", (d) => (d.featured ? 1 : 0.8));
    estimatePaths
      .transition()
      .duration(DURATION)
      .ease(easeCubicInOut)
      .attr("opacity", (d) => (d.featured ? 1 : 0.85))
      .attr("d", (d) => lineGen(d.estimate));
    estimatePaths.exit().remove();

    interface Marker {
      key: string;
      cx: number;
      cy: number;
      colour: string;
      featured: boolean;
      kind: "run" | "capture" | "estimate";
    }
    const markers: Marker[] = lines.flatMap((team) => [
      ...team.points.map((p) => ({
        key: `${team.teamId}|${p.t}`,
        cx: x(p.t),
        cy: y(p.value),
        colour: team.colour,
        featured: team.featured,
        kind: source === "wolves" ? ("run" as const) : ("capture" as const),
      })),
      ...team.estimate.slice(-1).map((p) => ({
        key: `${team.teamId}|est`,
        cx: x(p.t),
        cy: y(p.value),
        colour: team.colour,
        featured: team.featured,
        kind: "estimate" as const,
      })),
    ]);
    const markersG = svg.select<SVGGElement>(".markers");
    const haloData = markers.filter((m) => m.kind === "run" || (m.kind === "estimate" && m.featured));
    markersG
      .selectAll<SVGCircleElement, Marker>("circle.halo")
      .data(haloData, (d) => d.key)
      .join(
        (enter) => enter.append("circle").attr("class", "halo").attr("cx", (d) => d.cx).attr("cy", (d) => d.cy),
        (update) =>
          update.call((u) =>
            u.transition().duration(DURATION).ease(easeCubicInOut).attr("cx", (d) => d.cx).attr("cy", (d) => d.cy),
          ),
        (exit) => exit.remove(),
      )
      .attr("r", (d) => (d.featured ? 9.5 : 7))
      .attr("fill", (d) => d.colour)
      .attr("opacity", (d) => (d.featured ? 0.16 : 0.1));
    markersG
      .selectAll<SVGPathElement, Marker>("path.mark")
      .data(markers, (d) => d.key)
      .join(
        (enter) =>
          enter.append("path").attr("class", "mark").attr("transform", (d) => `translate(${d.cx},${d.cy})`).attr("opacity", 1),
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
        if (d.kind === "run") {
          const r = d.featured ? 5.4 : 4.2;
          return `M0,${-r} L${r},0 L0,${r} L${-r},0 Z`;
        }
        const r = d.kind === "estimate" ? (d.featured ? 3.4 : 2.8) : 2.6;
        return `M0,${-r} A${r},${r} 0 1,0 0.001,${-r} Z`;
      })
      .attr("fill", (d) => (d.kind === "estimate" && !d.featured ? NIGHT : d.colour))
      .attr("stroke", (d) => (d.kind === "estimate" ? (d.featured ? NIGHT : d.colour) : NIGHT))
      .attr("stroke-width", (d) => (d.kind === "estimate" ? (d.featured ? 1.4 : 1.6) : 1.2));

    interface EndLabel {
      teamId: string;
      text: string;
      colour: string;
      featured: boolean;
      labelY: number;
      lastX: number;
    }
    const labels: EndLabel[] = lines
      .map((team) => {
        const last = team.estimate.at(-1) ?? team.points.at(-1);
        if (!last) return null;
        return {
          teamId: team.teamId,
          text: `${abbreviate(team.name)}  ${formatValue(last.value)}`,
          colour: team.featured ? team.colour : "oklch(0.965 0.008 95 / 0.6)",
          featured: team.featured,
          labelY: y(last.value),
          lastX: x(last.t),
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
        (enter) => enter.append("text").attr("fill", (d) => d.colour).attr("x", (d) => d.lastX + 12).attr("y", (d) => d.labelY),
        (update) =>
          update.call((u) =>
            u
              .transition()
              .duration(DURATION)
              .ease(easeCubicInOut)
              .attr("fill", (d) => d.colour)
              .attr("x", (d) => d.lastX + 12)
              .attr("y", (d) => d.labelY),
          ),
      )
      .attr("font-family", "var(--font-spline-mono)")
      .attr("font-size", width < MOBILE_BREAK ? 11 : 12.5)
      .attr("font-weight", (d) => (d.featured ? 500 : 400))
      .attr("dominant-baseline", "middle")
      .text((d) => d.text);

    const anchors = lines.filter((team) => team.estimate.length > 1).map((team) => team.estimate[0].t);
    const annotationsG = svg.select<SVGGElement>(".annotations");
    annotationsG.selectAll("*").remove();
    if (anchors.length) {
      const anchorT = Math.max(...anchors);
      const anchorX = x(anchorT);
      annotationsG
        .append("line")
        .attr("x1", anchorX)
        .attr("x2", anchorX)
        .attr("y1", margin.top - 6)
        .attr("y2", baseY)
        .attr("stroke", "oklch(0.8 0.13 78 / 0.45)")
        .attr("stroke-dasharray", "2 5");
      annotationsG
        .append("circle")
        .attr("cx", anchorX)
        .attr("cy", margin.top - 6)
        .attr("r", 2.6)
        .attr("fill", GOLD);
      const caption = annotationsG
        .append("text")
        .attr("y", margin.top - 13)
        .attr("font-family", "var(--font-spline-mono)")
        .attr("font-size", 10.5)
        .attr("letter-spacing", "0.12em");
      if (anchorX - margin.left > 116) {
        caption
          .append("tspan")
          .attr("x", anchorX - 9)
          .attr("text-anchor", "end")
          .attr("fill", "oklch(0.965 0.008 95 / 0.5)")
          .text("AI FORECAST");
      }
      caption
        .append("tspan")
        .attr("x", anchorX + 9)
        .attr("text-anchor", "start")
        .attr("fill", GOLD)
        .text("RUNNING ESTIMATE");
      annotationsG
        .append("text")
        .attr("x", anchorX + 6)
        .attr("y", baseY - 6)
        .attr("text-anchor", "start")
        .attr("font-family", "var(--font-spline-mono)")
        .attr("font-size", 10)
        .attr("letter-spacing", "0.06em")
        .attr("fill", "oklch(0.965 0.008 95 / 0.4)")
        .text(`published ${formatDay(anchorT)}`);
    }
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
      .attr("stroke", GUIDE)
      .attr("stroke-dasharray", "2 3");
    for (const team of lines) {
      const point = team.points.find((p) => p.t === hover.t) ?? team.estimate.find((p) => p.t === hover.t) ?? null;
      if (!point) continue;
      layer
        .append("circle")
        .attr("cx", x(point.t))
        .attr("cy", y(point.value))
        .attr("r", 4)
        .attr("fill", NIGHT)
        .attr("stroke", team.colour)
        .attr("stroke-width", 1.8);
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
        stamp: formatStamp(hover.t),
        rows: lines.flatMap((team) => {
          const run = team.points.find((p) => p.t === hover.t);
          const estimate = team.estimate.find((p) => p.t === hover.t);
          const point = run ?? estimate;
          if (!point) return [];
          return [
            {
              teamId: team.teamId,
              name: team.name,
              colour: team.featured ? "oklch(0.69 0.19 25)" : "oklch(0.965 0.008 95 / 0.82)",
              value: point.value,
              estimated: !run,
              runId: run?.runId,
            },
          ];
        }),
      }
    : null;
  const anchorTimes = hover ? [...new Set(lines.flatMap((team) => team.points.map((p) => p.t)))].sort() : [];
  const previousAnchor = hover
    ? anchorTimes.filter((t) => (anchorTimes.includes(hover.t) ? t < hover.t : t <= hover.t)).at(-1)
    : undefined;
  const hoveredResults =
    hover && previousAnchor !== undefined ? resultsBetween(data.results, previousAnchor, hover.t) : [];
  const breakdown = data.breakdown[outcome];
  const hoveredBreakdown = hover && breakdown && breakdown.t === hover.t ? breakdown.text : null;

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
      {empty && width > 0 && (
        <p className="absolute inset-0 flex items-center font-mono text-[13px] text-cream-faint">
          {source === "market" ? "no market prices held yet" : "no published forecasts yet"}
        </p>
      )}
      {hover && hovered && hovered.rows.length > 0 && (
        <ChartTooltip x={hover.clientX} y={hover.clientY}>
          <div className="font-mono text-[11px] uppercase tracking-[0.12em] text-cream-faint">{hovered.stamp}</div>
          <div className="mt-0.5 font-mono text-[10.5px] uppercase tracking-[0.12em] text-gold">
            {source === "market"
              ? "Market prices"
              : hovered.rows.some((row) => row.estimated)
                ? "Running estimate"
                : `Full AI forecast${hovered.rows[0]?.runId ? ` · ${hovered.rows[0].runId}` : ""}`}
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
          {hoveredBreakdown && <div className="mt-2 font-mono text-[11.5px] text-cream-faint">{hoveredBreakdown}</div>}
          {hoveredResults.length > 0 && (
            <div className="mt-2.5 border-t border-hairline pt-2">
              <div className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-cream-faint">
                New results since the last {source === "market" ? "capture" : "run"}
              </div>
              {hoveredResults.map((row) => (
                <div key={`${row.t}-${row.label}`} className="mt-1 font-mono text-[12px] text-cream-dim">
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
