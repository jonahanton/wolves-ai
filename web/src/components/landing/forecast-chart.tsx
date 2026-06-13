"use client";

import { bisector } from "d3-array";
import { easeCubicInOut, easeCubicOut } from "d3-ease";
import { scaleLinear, scaleTime } from "d3-scale";
import { select } from "d3-selection";
import { area as d3Area, curveMonotoneX, line as d3Line } from "d3-shape";
import "d3-transition";
import { useEffect, useMemo, useRef, useState } from "react";
import { ChartTooltip } from "@/components/charts/chart-tooltip";
import { type ChartPoint, type ForecastChartData, type TeamLine } from "@/lib/forecast-series";

interface ForecastChartProps {
  data: ForecastChartData;
  selectedTeamId: string;
  onSelectTeam: (teamId: string) => void;
  ariaLabel: string;
}

interface HoverState {
  clientX: number;
  clientY: number;
  t: number;
}

const DURATION = 400;
const DRAW_MS = 560;
const MARGIN = { top: 22, right: 104, bottom: 36, left: 14 };
const MOBILE_MARGIN = { top: 18, right: 84, bottom: 34, left: 10 };
const MOBILE_BREAK = 560;
const DAY_MS = 86_400_000;

const AXIS_TEXT = "oklch(0.965 0.008 95 / 0.42)";
const TICK_MARK = "oklch(0.965 0.008 95 / 0.3)";
const GRID_LINE = "oklch(0.965 0.008 95 / 0.1)";
const GUIDE = "oklch(0.965 0.008 95 / 0.24)";
const FIELD_LINE = "oklch(0.965 0.008 95 / 0.1)";

function abbreviate(name: string): string {
  return name.replace(/[^A-Za-z]/g, "").slice(0, 3).toUpperCase();
}

function formatValue(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatTick(t: number): string {
  return new Date(t).toLocaleDateString("en-GB", { day: "2-digit", month: "2-digit", timeZone: "America/New_York" });
}

function formatStamp(t: number): string {
  return new Date(t).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/New_York",
  });
}

export function ForecastChart({ data, selectedTeamId, onSelectTeam, ariaLabel }: ForecastChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const scaffoldedRef = useRef(false);
  const introRef = useRef(false);
  const [intro, setIntro] = useState(false);
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState<HoverState | null>(null);

  const allLines = useMemo(() => data.teams.filter((team) => team.points.length > 0), [data.teams]);
  const topLines = useMemo(() => allLines.filter((team) => team.tier === "top"), [allLines]);
  const fieldLines = useMemo(() => allLines.filter((team) => team.tier === "field"), [allLines]);
  const tailLines = useMemo(() => allLines.filter((team) => team.tier === "tail"), [allLines]);
  const lines = useMemo(() => [...topLines, ...fieldLines], [topLines, fieldLines]);

  const envelope = useMemo(() => {
    if (tailLines.length === 0) return [];
    const byTime = new Map<number, { lo: number; hi: number }>();
    for (const team of tailLines) {
      for (const p of team.points) {
        const cur = byTime.get(p.t);
        if (!cur) byTime.set(p.t, { lo: p.value, hi: p.value });
        else byTime.set(p.t, { lo: Math.min(cur.lo, p.value), hi: Math.max(cur.hi, p.value) });
      }
    }
    return [...byTime.entries()].map(([t, v]) => ({ t, ...v })).sort((a, b) => a.t - b.t);
  }, [tailLines]);

  const margin = width < MOBILE_BREAK ? MOBILE_MARGIN : MARGIN;
  const empty = lines.length === 0;
  const height = empty ? 180 : width < MOBILE_BREAK ? 280 : 372;

  const { x, y, runTimes } = useMemo(() => {
    const linePoints = lines.flatMap((team) => team.points);
    const times = linePoints.map((p) => p.t);
    const lo = times.length ? Math.min(...times) : 0;
    const hi = times.length ? Math.max(...times) : DAY_MS;
    const pad = Math.max((hi - lo) * 0.04, DAY_MS / 12);
    const xScale = scaleTime()
      .domain([lo - pad, hi + pad])
      .range([margin.left, Math.max(margin.left + 1, width - margin.right)]);
    const maxValue = Math.max(0.04, ...linePoints.map((p) => p.value));
    const yScale = scaleLinear()
      .domain([0, maxValue * 1.06])
      .range([height - margin.bottom, margin.top]);
    const uniqueTimes = [...new Set(times)].sort((a, b) => a - b);
    return { x: xScale, y: yScale, runTimes: uniqueTimes };
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
    svg.append("g").attr("class", "x-axis");
    svg.append("g").attr("class", "baseline");
    svg.append("g").attr("class", "envelope");
    svg.append("g").attr("class", "field");
    svg.append("g").attr("class", "series");
    svg.append("g").attr("class", "ends");
    svg.append("g").attr("class", "hover-layer");
    scaffoldedRef.current = true;
  }, []);

  useEffect(() => {
    if (!svgRef.current || !scaffoldedRef.current || width === 0 || empty) return;
    const svg = select(svgRef.current);
    const baseY = height - margin.bottom;
    const reduce =
      typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const playIntro = !introRef.current && !reduce;
    if (!introRef.current) {
      introRef.current = true;
      if (playIntro) {
        window.setTimeout(() => setIntro(true), DRAW_MS * 0.55);
      } else {
        setIntro(true);
      }
    }

    const xAxis = svg
      .select<SVGGElement>(".x-axis")
      .selectAll<SVGGElement, number>("g.tick")
      .data(runTimes, (d) => String(d))
      .join((enter) => {
        const g = enter.append("g").attr("class", "tick");
        g.append("line").attr("class", "grid-line");
        g.append("line").attr("class", "tick-mark");
        g.append("text").attr("class", "tick-label");
        return g;
      });
    xAxis.attr("transform", (d) => `translate(${x(d)},0)`);
    xAxis
      .select<SVGLineElement>(".grid-line")
      .attr("y1", margin.top)
      .attr("y2", baseY)
      .attr("stroke", GRID_LINE)
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "2 4");
    xAxis
      .select<SVGLineElement>(".tick-mark")
      .attr("y1", baseY)
      .attr("y2", baseY + 7)
      .attr("stroke", TICK_MARK)
      .attr("stroke-width", 2);
    xAxis
      .select<SVGTextElement>(".tick-label")
      .attr("text-anchor", "middle")
      .attr("y", baseY + 24)
      .attr("font-family", "var(--font-display)")
      .attr("font-size", 14)
      .attr("font-weight", 600)
      .attr("letter-spacing", "0.01em")
      .attr("fill", AXIS_TEXT)
      .text((d) => formatTick(d));

    const baseline = svg.select<SVGGElement>(".baseline");
    baseline
      .selectAll<SVGLineElement, number>("line")
      .data([0])
      .join("line")
      .attr("x1", margin.left)
      .attr("x2", width - margin.right)
      .attr("y1", y(0))
      .attr("y2", y(0))
      .attr("stroke", "oklch(0.965 0.008 95 / 0.16)")
      .attr("stroke-width", 1);

    const areaGen = d3Area<{ t: number; lo: number; hi: number }>()
      .x((d) => x(d.t))
      .y0((d) => y(d.lo))
      .y1((d) => y(d.hi))
      .curve(curveMonotoneX);
    svg
      .select<SVGGElement>(".envelope")
      .selectAll<SVGPathElement, typeof envelope>("path")
      .data(envelope.length ? [envelope] : [])
      .join(
        (enter) =>
          enter
            .append("path")
            .attr("d", (d) => areaGen(d))
            .attr("fill", "oklch(0.965 0.008 95 / 0.06)")
            .attr("opacity", 0)
            .call((e) =>
              e
                .transition()
                .delay(playIntro ? DRAW_MS * 0.6 : 0)
                .duration(DURATION)
                .ease(easeCubicInOut)
                .attr("opacity", 1),
            ),
        (update) =>
          update.call((u) => u.transition().duration(DURATION).ease(easeCubicInOut).attr("d", (d) => areaGen(d))),
        (exit) => exit.call((x2) => x2.transition().duration(DURATION).ease(easeCubicInOut).attr("opacity", 0).remove()),
      );

    const lineGen = d3Line<ChartPoint>()
      .x((p) => x(p.t))
      .y((p) => y(p.value))
      .curve(curveMonotoneX);

    const isField = (team: TeamLine) => team.tier === "field" && team.teamId !== selectedTeamId;
    const fieldDrawn = lines.filter((team) => isField(team) && team.points.length > 1);
    const fieldPaths = svg
      .select<SVGGElement>(".field")
      .selectAll<SVGPathElement, TeamLine>("path")
      .data(fieldDrawn, (d) => d.teamId)
      .join(
        (enter) =>
          enter
            .append("path")
            .attr("fill", "none")
            .attr("d", (d) => lineGen(d.points))
            .attr("stroke-linecap", "round")
            .attr("stroke-linejoin", "round")
            .attr("stroke", FIELD_LINE)
            .attr("stroke-width", 1.3)
            .attr("opacity", playIntro ? 1 : 0)
            .call((e) => (playIntro ? e : e.transition().duration(DURATION).ease(easeCubicInOut).attr("opacity", 1))),
        (update) =>
          update.call((u) =>
            u.transition().duration(DURATION).ease(easeCubicInOut).attr("d", (d) => lineGen(d.points)).attr("opacity", 1),
          ),
        (exit) => exit.call((x2) => x2.transition().duration(DURATION).ease(easeCubicInOut).attr("opacity", 0).remove()),
      )
      .style("cursor", "pointer")
      .on("click", (_e, d) => onSelectTeam(d.teamId));

    const focusLines = lines.filter((team) => !isField(team) && team.points.length > 1);
    const paths = svg
      .select<SVGGElement>(".series")
      .selectAll<SVGPathElement, TeamLine>("path")
      .data(focusLines, (d) => d.teamId)
      .join(
        (enter) => enter.append("path").attr("fill", "none").attr("d", (d) => lineGen(d.points)),
        (update) =>
          update.call((u) =>
            u.transition().duration(DURATION).ease(easeCubicInOut).attr("d", (d) => lineGen(d.points)),
          ),
        (exit) => exit.remove(),
      )
      .attr("stroke-linecap", "round")
      .attr("stroke-linejoin", "round")
      .attr("stroke", (d) => d.colour)
      .attr("stroke-width", (d) => (d.teamId === selectedTeamId ? 3.4 : 1.8))
      .attr("opacity", (d) => (d.teamId === selectedTeamId ? 1 : 0.85))
      .style("cursor", "pointer")
      .style("filter", (d) => (d.teamId === selectedTeamId ? `drop-shadow(0 0 6px ${d.colour})` : "none"))
      .on("click", (_e, d) => onSelectTeam(d.teamId));

    if (playIntro) {
      const draw = (node: SVGPathElement) => {
        const len = node.getTotalLength();
        select(node)
          .attr("stroke-dasharray", `${len} ${len}`)
          .attr("stroke-dashoffset", len)
          .transition()
          .duration(DRAW_MS)
          .ease(easeCubicOut)
          .attr("stroke-dashoffset", 0)
          .on("end", function () {
            select(this).attr("stroke-dasharray", null);
          });
      };
      paths.each(function () {
        draw(this);
      });
      fieldPaths.each(function () {
        draw(this);
      });
    }

    interface End {
      teamId: string;
      cx: number;
      cy: number;
      colour: string;
      selected: boolean;
    }
    const ends: End[] = focusLines.flatMap((team) => {
      const last = team.points.at(-1);
      if (!last) return [];
      return [{ teamId: team.teamId, cx: x(last.t), cy: y(last.value), colour: team.colour, selected: team.teamId === selectedTeamId }];
    });
    svg
      .select<SVGGElement>(".ends")
      .selectAll<SVGCircleElement, End>("circle")
      .data(ends, (d) => d.teamId)
      .join(
        (enter) =>
          enter
            .append("circle")
            .attr("cx", (d) => d.cx)
            .attr("cy", (d) => d.cy)
            .attr("opacity", playIntro ? 0 : 1),
        (update) =>
          update.call((u) =>
            u.transition().duration(DURATION).ease(easeCubicInOut).attr("cx", (d) => d.cx).attr("cy", (d) => d.cy),
          ),
        (exit) => exit.remove(),
      )
      .attr("r", (d) => (d.selected ? 5.4 : 4.6))
      .attr("fill", (d) => d.colour)
      .call((sel) =>
        playIntro
          ? sel.transition().delay(DRAW_MS * 0.6).duration(200).ease(easeCubicOut).attr("opacity", 1)
          : sel.attr("opacity", 1),
      );
  }, [lines, envelope, selectedTeamId, onSelectTeam, x, y, width, height, margin, empty, runTimes]);

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
    for (const team of topLines) {
      const point = team.points.find((p) => p.t === hover.t);
      if (!point) continue;
      layer
        .append("circle")
        .attr("cx", x(point.t))
        .attr("cy", y(point.value))
        .attr("r", 4.2)
        .attr("fill", team.colour);
    }
  }, [hover, topLines, x, y, margin, height]);

  const endLabels = useMemo(() => {
    if (width === 0 || empty) return [];
    const byValue = new Map<
      string,
      { value: string; anchorY: number; anchorX: number; teams: { teamId: string; code: string; colour: string; emphasised: boolean; raw: number }[] }
    >();
    for (const team of topLines) {
      const last = team.points.at(-1);
      if (!last) continue;
      const value = formatValue(last.value);
      const group = byValue.get(value) ?? { value, anchorY: y(last.value), anchorX: x(last.t), teams: [] };
      group.teams.push({
        teamId: team.teamId,
        code: abbreviate(team.name),
        colour: team.colour,
        emphasised: team.teamId === selectedTeamId,
        raw: last.value,
      });
      byValue.set(value, group);
    }
    for (const group of byValue.values()) group.teams.sort((a, b) => b.raw - a.raw);
    const groups = [...byValue.values()].sort((a, b) => a.anchorY - b.anchorY);
    const gap = width < MOBILE_BREAK ? 40 : 46;
    for (let i = 1; i < groups.length; i++) {
      if (groups[i].anchorY - groups[i - 1].anchorY < gap) groups[i].anchorY = groups[i - 1].anchorY + gap;
    }
    return groups;
  }, [topLines, selectedTeamId, x, y, width, empty]);

  function onPointerMove(event: React.PointerEvent<SVGRectElement>) {
    if (!runTimes.length || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const t = x.invert(event.clientX - rect.left).getTime();
    const index = bisector((time: number) => time).center(runTimes, t);
    setHover({ clientX: event.clientX, clientY: event.clientY, t: runTimes[index] });
  }

  const othersLabelY = useMemo(() => {
    if (envelope.length === 0) return 0;
    const natural = y(envelope.at(-1)!.hi);
    const lastLabelY = endLabels.at(-1)?.anchorY ?? -Infinity;
    const gap = width < MOBILE_BREAK ? 26 : 30;
    return Math.max(natural, lastLabelY + gap);
  }, [envelope, endLabels, y, width]);

  const hovered = hover
    ? {
        stamp: formatStamp(hover.t),
        rows: topLines.flatMap((team) => {
          const point = team.points.find((p) => p.t === hover.t);
          if (!point) return [];
          return [{ teamId: team.teamId, code: abbreviate(team.name), colour: team.colour, value: point.value }];
        }),
      }
    : null;

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
      {endLabels.map((group) => {
        const emphasised = group.teams.some((t) => t.emphasised);
        return (
          <div
            key={group.value + group.teams[0].teamId}
            className="absolute flex -translate-y-1/2 items-stretch gap-x-2.5 text-left leading-none transition-opacity duration-300"
            style={{ left: group.anchorX + 13, top: group.anchorY, opacity: intro ? (emphasised ? 1 : 0.7) : 0 }}
          >
            {group.teams.map((team) => (
              <button
                key={team.teamId}
                type="button"
                onClick={() => onSelectTeam(team.teamId)}
                className="flex flex-col items-start gap-y-1 transition-opacity hover:opacity-100"
                style={{ color: team.colour }}
              >
                <span className="font-display text-[13px] font-bold tracking-[0.01em]">{team.code}</span>
                <span className="font-display text-[clamp(18px,1.9vw,24px)] font-extrabold tabular-nums tracking-[-0.02em]">
                  {group.value}
                </span>
              </button>
            ))}
          </div>
        );
      })}
      {envelope.length > 0 && width > 0 && (
        <span
          className="pointer-events-none absolute -translate-y-1/2 font-display text-[12px] font-semibold tracking-[0.01em] text-cream-faint transition-opacity duration-300"
          style={{ left: x(envelope.at(-1)!.t) + 13, top: othersLabelY, opacity: intro ? 1 : 0 }}
        >
          +{tailLines.length} others
        </span>
      )}
      {empty && width > 0 && (
        <p className="absolute inset-0 flex items-center font-display text-[14px] text-cream-faint">
          no published forecasts yet
        </p>
      )}
      {hover && hovered && hovered.rows.length > 0 && (
        <ChartTooltip x={hover.clientX} y={hover.clientY}>
          <div className="font-display text-[11px] font-semibold text-cream-faint">{hovered.stamp}</div>
          <div className="mt-1.5 space-y-0.5">
            {hovered.rows.map((row) => (
              <div key={row.teamId} className="flex items-baseline justify-between gap-5">
                <span className="font-display text-[13px] font-bold tracking-[0.01em]" style={{ color: row.colour }}>
                  {row.code}
                </span>
                <span className="font-display text-[13px] font-extrabold tabular-nums" style={{ color: row.colour }}>
                  {formatValue(row.value)}
                </span>
              </div>
            ))}
          </div>
        </ChartTooltip>
      )}
    </div>
  );
}
