"use client";

import { easeCubicInOut, easeCubicOut } from "d3-ease";
import { scaleLinear } from "d3-scale";
import { select } from "d3-selection";
import { area as d3Area, curveMonotoneX, line as d3Line } from "d3-shape";
import "d3-transition";
import { useEffect, useMemo, useRef, useState } from "react";
import { ChartTooltip } from "@/components/charts/chart-tooltip";
import {
  type ChartPoint,
  type ForecastChartData,
  groupResultTicks,
  type TeamLine,
} from "@/lib/forecast-series";
import { teamCode } from "@/lib/team-colours";

interface ForecastChartProps {
  data: ForecastChartData;
  selectedTeamId: string;
  othersCount: number;
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
const MARGIN = { top: 22, right: 78, bottom: 36, left: 14 };
const MOBILE_MARGIN = { top: 18, right: 64, bottom: 34, left: 10 };
const MOBILE_BREAK = 560;
const RESULT_LANE_START_PX = 5;
const RESULT_LANE_PX = 16;

const AXIS_TEXT = "oklch(0.965 0.008 95 / 0.42)";
const TICK_MARK = "oklch(0.965 0.008 95 / 0.3)";
const GRID_LINE = "oklch(0.965 0.008 95 / 0.1)";
const GUIDE = "oklch(0.965 0.008 95 / 0.24)";
const RESULT_TICK = "oklch(0.965 0.008 95 / 0.5)";
const MIN_LABEL_GAP = 44;

function formatValue(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatTick(t: number): string {
  return new Date(t).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    timeZone: "America/New_York",
  });
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

function labelledRunTimes(runTimes: number[], position: (time: number) => number): Set<number> {
  const first = runTimes[0];
  const last = runTimes.at(-1);
  if (first === undefined || last === undefined) return new Set();
  const labels = new Set([first, last]);
  let previousX = position(first);
  const finalX = position(last);
  for (const time of runTimes.slice(1, -1)) {
    const currentX = position(time);
    if (currentX - previousX >= MIN_LABEL_GAP && finalX - currentX >= MIN_LABEL_GAP) {
      labels.add(time);
      previousX = currentX;
    }
  }
  return labels;
}

export function ForecastChart({
  data,
  selectedTeamId,
  othersCount,
  onSelectTeam,
  ariaLabel,
}: ForecastChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const scaffoldedRef = useRef(false);
  const introRef = useRef(false);
  const [intro, setIntro] = useState(false);
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState<HoverState | null>(null);

  const allLines = useMemo(
    () => data.teams.filter((team) => team.points.length > 0),
    [data.teams],
  );
  const topLines = useMemo(
    () =>
      allLines.filter(
        (team) => team.tier === "top" || team.teamId === selectedTeamId,
      ),
    [allLines, selectedTeamId],
  );
  const tailLines = useMemo(
    () =>
      allLines.filter(
        (team) => team.tier === "rest" && team.teamId !== selectedTeamId,
      ),
    [allLines, selectedTeamId],
  );
  const lines = topLines;

  const envelope = useMemo(() => {
    if (tailLines.length === 0) return [];
    const byTime = new Map<number, { lo: number; hi: number }>();
    for (const team of tailLines) {
      for (const p of team.points) {
        const cur = byTime.get(p.t);
        if (!cur) byTime.set(p.t, { lo: p.value, hi: p.value });
        else
          byTime.set(p.t, {
            lo: Math.min(cur.lo, p.value),
            hi: Math.max(cur.hi, p.value),
          });
      }
    }
    return [...byTime.entries()]
      .map(([t, v]) => ({ t, ...v }))
      .sort((a, b) => a.t - b.t);
  }, [tailLines]);

  const empty = lines.length === 0;
  const height = empty ? 180 : width < MOBILE_BREAK ? 300 : 392;
  const mobile = width < MOBILE_BREAK;

  const resultTickGroups = useMemo(() => groupResultTicks(data.results ?? []), [data.results]);
  const hasResults = resultTickGroups.length > 0;
  const resultSpanEnd = useMemo(
    () => (hasResults ? Math.max(...resultTickGroups.map((result) => result.t)) : 0),
    [resultTickGroups, hasResults],
  );
  const margin = mobile ? MOBILE_MARGIN : MARGIN;

  const { x, posScale, y, runTimes, lastRunTime } = useMemo(() => {
    const linePoints = lines.flatMap((team) => team.points);
    const times = linePoints.map((p) => p.t);
    const uniqueTimes = [...new Set(times)].sort((a, b) => a - b);
    const n = uniqueTimes.length;
    // Runs are spaced by order, not by elapsed time, so an irregular agent
    // cadence still reads as an even cadence on the axis.
    const indexOf = new Map(uniqueTimes.map((t, i) => [t, i]));
    const pad = 0.35;
    const scale = scaleLinear()
      .domain([-pad, Math.max(1, n - 1) + pad])
      .range([margin.left, Math.max(margin.left + 1, width - margin.right)]);
    const frac = (t: number) => {
      if (n === 0) return 0;
      const exact = indexOf.get(t);
      if (exact !== undefined) return exact;
      if (t <= uniqueTimes[0]) return 0;
      if (t >= uniqueTimes[n - 1]) return n - 1;
      const hiI = uniqueTimes.findIndex((u) => u >= t);
      const span = uniqueTimes[hiI] - uniqueTimes[hiI - 1];
      return hiI - 1 + (span ? (t - uniqueTimes[hiI - 1]) / span : 0);
    };
    const xScale = (t: number) => scale(frac(t));
    const maxValue = Math.max(0.04, ...linePoints.map((p) => p.value));
    const yScale = scaleLinear()
      .domain([0, maxValue * 1.06])
      .range([height - margin.bottom, margin.top]);
    return {
      x: xScale,
      posScale: scale,
      y: yScale,
      runTimes: uniqueTimes,
      lastRunTime: n ? uniqueTimes[n - 1] : null,
    };
  }, [lines, width, margin, height]);

  const liveX = useMemo(() => {
    return (t: number) => {
      if (lastRunTime === null || t <= lastRunTime || !hasResults) return x(t);
      const lastX = x(lastRunTime);
      const span = Math.max(1, resultSpanEnd - lastRunTime);
      const progress = Math.min(1, Math.max(0, (t - lastRunTime) / span));
      return lastX + RESULT_LANE_START_PX + progress * RESULT_LANE_PX;
    };
  }, [x, lastRunTime, hasResults, resultSpanEnd]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const measured = Math.round(entries[0].contentRect.width);
      if (measured > 0) setWidth((current) => (current === measured ? current : measured));
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!svgRef.current || scaffoldedRef.current) return;
    const svg = select(svgRef.current);
    const defs = svg.append("defs");
    const fade = defs
      .append("linearGradient")
      .attr("id", "history-fade")
      .attr("x1", "0")
      .attr("x2", "1")
      .attr("y1", "0")
      .attr("y2", "0");
    fade.append("stop").attr("offset", "0%").attr("stop-color", "var(--color-night)").attr("stop-opacity", 0.62);
    fade.append("stop").attr("offset", "55%").attr("stop-color", "var(--color-night)").attr("stop-opacity", 0);
    svg.append("g").attr("class", "x-axis");
    svg.append("g").attr("class", "baseline");
    svg.append("g").attr("class", "result-ticks");
    svg.append("g").attr("class", "envelope");
    svg.append("g").attr("class", "series");
    svg.append("g").attr("class", "history-fade");
    svg.append("g").attr("class", "ends");
    svg.append("g").attr("class", "hover-layer");
    scaffoldedRef.current = true;
  }, []);

  useEffect(() => {
    if (!svgRef.current || !scaffoldedRef.current || width === 0 || empty)
      return;
    const svg = select(svgRef.current);
    const baseY = height - margin.bottom;
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
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
    const showLabel = labelledRunTimes(runTimes, x);
    xAxis
      .select<SVGTextElement>(".tick-label")
      .attr("text-anchor", "middle")
      .attr("y", baseY + 24)
      .attr("font-family", "var(--font-display)")
      .attr("font-size", 14)
      .attr("font-weight", 600)
      .attr("letter-spacing", "0.01em")
      .attr("fill", AXIS_TEXT)
      .text((d) => (showLabel.has(d) ? formatTick(d) : ""));

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

    const resultTicks = svg
      .select<SVGGElement>(".result-ticks")
      .selectAll<SVGGElement, { t: number; label: string }>("g.tick")
      .data(resultTickGroups, (d) => String(d.t))
      .join((enter) => {
        const g = enter.append("g").attr("class", "tick").attr("opacity", 0);
        g.append("line");
        g.append("title");
        g.transition().duration(DURATION).attr("opacity", 1);
        return g;
      });
    resultTicks.attr("transform", (d) => `translate(${liveX(d.t)},0)`);
    resultTicks
      .select("line")
      .attr("y1", baseY - 5)
      .attr("y2", baseY + 5)
      .attr("stroke", RESULT_TICK)
      .attr("stroke-width", 1.4);
    resultTicks.select("title").text((d) => d.label);

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
          update.call((u) =>
            u
              .transition()
              .duration(DURATION)
              .ease(easeCubicInOut)
              .attr("d", (d) => areaGen(d)),
          ),
        (exit) =>
          exit.call((x2) =>
            x2
              .transition()
              .duration(DURATION)
              .ease(easeCubicInOut)
              .attr("opacity", 0)
              .remove(),
          ),
      );

    const lineGen = d3Line<ChartPoint>()
      .x((p) => x(p.t))
      .y((p) => y(p.value))
      .curve(curveMonotoneX);

    const focusLines = lines.filter((team) => team.points.length > 1);
    const paths = svg
      .select<SVGGElement>(".series")
      .selectAll<SVGPathElement, TeamLine>("path")
      .data(focusLines, (d) => d.teamId)
      .join(
        (enter) =>
          enter
            .append("path")
            .attr("fill", "none")
            .attr("d", (d) => lineGen(d.points)),
        (update) =>
          update.call((u) =>
            u
              .transition()
              .duration(DURATION)
              .ease(easeCubicInOut)
              .attr("d", (d) => lineGen(d.points)),
          ),
        (exit) => exit.remove(),
      )
      .attr("stroke-linecap", "round")
      .attr("stroke-linejoin", "round")
      .attr("stroke", (d) =>
        d.teamId === selectedTeamId
          ? d.colour
          : `color-mix(in oklab, ${d.colour} 78%, var(--color-night))`,
      )
      .attr("stroke-width", (d) => (d.teamId === selectedTeamId ? 3.4 : 2.1))
      .attr("opacity", (d) => (d.teamId === selectedTeamId ? 1 : 0.55))
      .style("cursor", "pointer")
      .style("filter", (d) =>
        d.teamId === selectedTeamId
          ? `drop-shadow(0 0 6px ${d.colour})`
          : "none",
      )
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
          // Clear on interrupt too, else a competing d transition freezes the dash.
          .on("end interrupt", function () {
            select(this).attr("stroke-dasharray", null).attr("stroke-dashoffset", null);
          });
      };
      paths.each(function () {
        draw(this);
      });
    }

    // Pull the eye to "now": veil older history under a left-to-right night fade.
    svg
      .select<SVGGElement>(".history-fade")
      .selectAll<SVGRectElement, number>("rect")
      .data([0])
      .join("rect")
      .attr("x", margin.left)
      .attr("y", margin.top)
      .attr("width", Math.max(0, (lastRunTime !== null ? x(lastRunTime) : width - margin.right) - margin.left))
      .attr("height", baseY - margin.top)
      .attr("fill", "url(#history-fade)")
      .attr("pointer-events", "none");

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
      return [
        {
          teamId: team.teamId,
          cx: x(last.t),
          cy: y(last.value),
          colour: team.colour,
          selected: team.teamId === selectedTeamId,
        },
      ];
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
            u
              .transition()
              .duration(DURATION)
              .ease(easeCubicInOut)
              .attr("cx", (d) => d.cx)
              .attr("cy", (d) => d.cy),
          ),
        (exit) => exit.remove(),
      )
      .attr("r", (d) => (d.selected ? 5.4 : 4.6))
      .attr("fill", (d) => d.colour)
      .call((sel) =>
        playIntro
          ? sel
              .transition()
              .delay(DRAW_MS * 0.6)
              .duration(200)
              .ease(easeCubicOut)
              .attr("opacity", 1)
          : sel.attr("opacity", 1),
      );
  }, [
    lines,
    envelope,
    selectedTeamId,
    lastRunTime,
    onSelectTeam,
    x,
    y,
    liveX,
    width,
    height,
    margin,
    empty,
    runTimes,
    resultTickGroups,
  ]);

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
      {
        value: string;
        anchorY: number;
        anchorX: number;
        teams: {
          teamId: string;
          code: string;
          colour: string;
          emphasised: boolean;
          raw: number;
        }[];
      }
    >();
    for (const team of topLines) {
      const last = team.points.at(-1);
      if (!last) continue;
      const value = formatValue(last.value);
      const group = byValue.get(value) ?? {
        value,
        anchorY: y(last.value),
        anchorX: x(last.t),
        teams: [],
      };
      group.teams.push({
        teamId: team.teamId,
        code: teamCode(team.name),
        colour: team.colour,
        emphasised: team.teamId === selectedTeamId,
        raw: last.value,
      });
      byValue.set(value, group);
    }
    for (const group of byValue.values())
      group.teams.sort((a, b) => b.raw - a.raw);
    const teamGroups = [...byValue.values()].map((g) => ({
      ...g,
      kind: "team" as const,
    }));

    const othersGroup =
      envelope.length > 0
        ? [
            {
              kind: "others" as const,
              anchorY: y(envelope.at(-1)!.hi),
              anchorX: x(envelope.at(-1)!.t),
              value: "",
              teams: [],
            },
          ]
        : [];

    const rows = [...teamGroups, ...othersGroup].sort(
      (a, b) => a.anchorY - b.anchorY,
    );
    // Half-height of each label so neighbours separate by exactly what they need:
    // the selected team is tallest, the rest are smaller and pack tighter.
    const mob = width < MOBILE_BREAK;
    const halfHeight = (i: number) => {
      const r = rows[i];
      if (r.kind === "others") return mob ? 9 : 10;
      const teamsHalf = r.teams.reduce(
        (sum, t) => sum + (t.emphasised ? (mob ? 22 : 26) : mob ? 15 : 17),
        0,
      );
      return teamsHalf + Math.max(0, r.teams.length - 1) * 4;
    };
    const gapBefore = (i: number) => halfHeight(i - 1) + halfHeight(i) + 6;

    const top = margin.top;
    const bottom = height - margin.bottom - 8;
    for (let i = 1; i < rows.length; i++) {
      const minY = rows[i - 1].anchorY + gapBefore(i);
      if (rows[i].anchorY < minY) rows[i].anchorY = minY;
    }
    for (let i = rows.length - 1; i >= 0; i--) {
      const maxY =
        i === rows.length - 1 ? bottom : rows[i + 1].anchorY - gapBefore(i + 1);
      if (rows[i].anchorY > maxY) rows[i].anchorY = maxY;
    }
    if (rows.length) rows[0].anchorY = Math.max(rows[0].anchorY, top);
    return rows;
  }, [topLines, selectedTeamId, x, y, width, empty, envelope, height, margin]);

  function onPointerMove(event: React.PointerEvent<SVGRectElement>) {
    if (!runTimes.length || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const pos = posScale.invert(event.clientX - rect.left);
    const index = Math.max(0, Math.min(runTimes.length - 1, Math.round(pos)));
    setHover({
      clientX: event.clientX,
      clientY: event.clientY,
      t: runTimes[index],
    });
  }

  const hovered = hover
    ? {
        stamp: formatStamp(hover.t),
        rows: topLines.flatMap((team) => {
          const point = team.points.find((p) => p.t === hover.t);
          if (!point) return [];
          return [
            {
              teamId: team.teamId,
              code: teamCode(team.name),
              colour: team.colour,
              value: point.value,
            },
          ];
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
        if (group.kind === "others") {
          return (
            <span
              key="others"
              className="pointer-events-none absolute -translate-y-1/2 font-display text-[12px] font-semibold tracking-[0.01em] text-cream-faint transition-opacity duration-300"
              style={{
                left: group.anchorX + 13,
                top: group.anchorY,
                opacity: intro ? 1 : 0,
              }}
            >
              +{othersCount} others
            </span>
          );
        }
        const emphasised = group.teams.some((t) => t.emphasised);
        return (
          <div
            key={group.value + group.teams[0].teamId}
            className="absolute flex -translate-y-1/2 flex-col items-start gap-y-2 text-left leading-none transition-opacity duration-300"
            style={{
              left: group.anchorX + 13,
              top: group.anchorY,
              opacity: intro ? (emphasised ? 1 : 0.7) : 0,
              zIndex: emphasised ? 3 : 1,
              textShadow:
                "0 0 5px var(--color-night), 0 0 5px var(--color-night), 0 0 9px var(--color-night)",
            }}
          >
            {group.teams.map((team) => (
              <button
                key={team.teamId}
                type="button"
                onClick={() => onSelectTeam(team.teamId)}
                className="flex flex-col items-start gap-y-0.5 transition-opacity hover:opacity-100"
                style={{ color: team.colour }}
              >
                <span
                  className={`font-display font-bold leading-none tracking-[0.01em] ${team.emphasised ? "text-[15px]" : "text-[12px]"}`}
                >
                  {team.code}
                </span>
                <span
                  className={`font-display font-extrabold tabular-nums tracking-[-0.02em] ${team.emphasised ? "text-[clamp(20px,2.2vw,27px)]" : "text-[clamp(15px,1.6vw,18px)]"}`}
                >
                  {group.value}
                </span>
              </button>
            ))}
          </div>
        );
      })}
      {empty && width > 0 && (
        <p className="absolute inset-0 flex items-center font-display text-[14px] text-cream-faint">
          no published forecasts yet
        </p>
      )}
      {hover && hovered && hovered.rows.length > 0 && (
        <ChartTooltip x={hover.clientX} y={hover.clientY}>
          <div className="font-display text-[11px] font-semibold text-cream-faint">
            {hovered.stamp}
          </div>
          <div className="mt-1.5 space-y-0.5">
            {hovered.rows.map((row) => (
              <div
                key={row.teamId}
                className="flex items-baseline justify-between gap-5"
              >
                <span
                  className="font-display text-[13px] font-bold tracking-[0.01em]"
                  style={{ color: row.colour }}
                >
                  {row.code}
                </span>
                <span
                  className="font-display text-[13px] font-extrabold tabular-nums"
                  style={{ color: row.colour }}
                >
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
