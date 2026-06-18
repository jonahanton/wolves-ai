"use client";

import { bisector } from "d3-array";
import { easeCubicInOut, easeCubicOut } from "d3-ease";
import { scaleLinear, scaleTime } from "d3-scale";
import { select } from "d3-selection";
import { area as d3Area, curveMonotoneX, line as d3Line } from "d3-shape";
import "d3-transition";
import { useEffect, useMemo, useRef, useState } from "react";
import { ChartTooltip } from "@/components/charts/chart-tooltip";
import {
  type ChartImpactPoint,
  type ChartPoint,
  type ForecastChartData,
  type TeamLine,
} from "@/lib/forecast-series";
import { teamCode } from "@/lib/team-colours";

interface ForecastChartProps {
  data: ForecastChartData;
  selectedTeamId: string;
  othersCount: number;
  onSelectTeam: (teamId: string) => void;
  ariaLabel: string;
  impacts?: Record<string, ChartImpactPoint> | null;
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
const DAY_MS = 86_400_000;
const RESULT_LANE_START_PX = 5;
const RESULT_LANE_PX = 16;
const ESTIMATE_LANE_PX = 26;

const AXIS_TEXT = "oklch(0.965 0.008 95 / 0.42)";
const TICK_MARK = "oklch(0.965 0.008 95 / 0.3)";
const GRID_LINE = "oklch(0.965 0.008 95 / 0.1)";
const GUIDE = "oklch(0.965 0.008 95 / 0.24)";
const RESULT_TICK = "oklch(0.965 0.008 95 / 0.5)";

function formatValue(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

interface ImpactLegs {
  net: number;
  resultsPp: number;
  ingamePp: number;
}

function impactLegs(
  impacts: Record<string, ChartImpactPoint> | null,
  teamId: string,
): ImpactLegs | null {
  const impact = impacts?.[teamId];
  if (!impact) return null;
  const net = impact.fromResultsPp + impact.fromIngamePp;
  if (Math.abs(net) < impact.displayFloorPp) return null;
  return {
    net,
    resultsPp: impact.fromResultsPp,
    ingamePp: impact.fromIngamePp,
  };
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

export function ForecastChart({
  data,
  selectedTeamId,
  othersCount,
  onSelectTeam,
  ariaLabel,
  impacts = null,
}: ForecastChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const scaffoldedRef = useRef(false);
  const introRef = useRef(false);
  const estimateShownRef = useRef(false);
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

  const hasResults = (data.results?.length ?? 0) > 0;
  const resultSpanEnd = useMemo(
    () => (hasResults ? Math.max(...data.results.map((r) => r.t)) : 0),
    [data.results, hasResults],
  );
  const selectedTeam = lines.find((team) => team.teamId === selectedTeamId) ?? null;
  const selectedLegs = useMemo(
    () => (selectedTeam ? impactLegs(impacts, selectedTeamId) : null),
    [selectedTeam, impacts, selectedTeamId],
  );
  const deltaGutter = selectedLegs ? (mobile ? 58 : 74) : 0;
  const margin = useMemo(() => {
    const m = mobile ? MOBILE_MARGIN : MARGIN;
    return { ...m, right: m.right + deltaGutter };
  }, [mobile, deltaGutter]);

  const { x, y, runTimes, lastRunTime } = useMemo(() => {
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
    return {
      x: xScale,
      y: yScale,
      runTimes: uniqueTimes,
      lastRunTime: times.length ? hi : null,
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
    svg.append("g").attr("class", "x-axis");
    svg.append("g").attr("class", "baseline");
    svg.append("g").attr("class", "result-ticks");
    svg.append("g").attr("class", "envelope");
    svg.append("g").attr("class", "series");
    svg.append("g").attr("class", "live-estimate");
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
    // Thin labels so adjacent dates never overlap.
    const MIN_LABEL_GAP = 44;
    let lastLabelX = Number.NEGATIVE_INFINITY;
    const showLabel = new Set<number>();
    for (const t of runTimes) {
      if (x(t) - lastLabelX >= MIN_LABEL_GAP) {
        showLabel.add(t);
        lastLabelX = x(t);
      }
    }
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
      .data(data.results, (d) => `${d.t}-${d.label}`)
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
      .attr("stroke", (d) => d.colour)
      .attr("stroke-width", (d) => (d.teamId === selectedTeamId ? 3.4 : 1.8))
      .attr("opacity", (d) => (d.teamId === selectedTeamId ? 1 : 0.85))
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
          .on("end", function () {
            select(this).attr("stroke-dasharray", null);
          });
      };
      paths.each(function () {
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

    const estimateLayer = svg.select<SVGGElement>(".live-estimate");
    estimateLayer.selectAll("*").remove();
    const selectedLine = lines.find((team) => team.teamId === selectedTeamId);
    const selectedLast = selectedLine?.points.at(-1);
    if (selectedLegs && selectedLine && selectedLast && lastRunTime !== null) {
      const colour = selectedLine.colour;
      const ax = x(lastRunTime) + ESTIMATE_LANE_PX;
      const y0 = y(selectedLast.value);
      const y1 = y(selectedLast.value + selectedLegs.net / 100);
      const up = selectedLegs.net > 0;
      const head = 4.2;
      const tip = up ? y1 + head : y1 - head;
      const fadeEstimate = playIntro || !estimateShownRef.current;
      estimateShownRef.current = true;
      const g = estimateLayer.append("g").attr("opacity", fadeEstimate ? 0 : 1);
      g.append("line")
        .attr("x1", x(selectedLast.t))
        .attr("y1", y0)
        .attr("x2", ax)
        .attr("y2", y0)
        .attr("stroke", colour)
        .attr("stroke-width", 1)
        .attr("stroke-dasharray", "1 3")
        .attr("opacity", 0.45);
      g.append("line")
        .attr("x1", ax)
        .attr("y1", y0)
        .attr("x2", ax)
        .attr("y2", tip)
        .attr("stroke", colour)
        .attr("stroke-width", 2)
        .attr("stroke-linecap", "round");
      g.append("path")
        .attr("d", `M${ax - head},${tip} L${ax + head},${tip} L${ax},${y1} Z`)
        .attr("fill", colour);
      g.append("text")
        .attr("x", ax + 8)
        .attr("y", (y0 + y1) / 2)
        .attr("dominant-baseline", "middle")
        .attr("font-family", "var(--font-mono)")
        .attr("font-size", 11.5)
        .attr("font-weight", 700)
        .attr("fill", colour)
        .text(`${up ? "+" : ""}${selectedLegs.net.toFixed(1)}pp`);
      if (fadeEstimate)
        g.transition()
          .delay(playIntro ? DRAW_MS * 0.6 : 0)
          .duration(220)
          .ease(easeCubicOut)
          .attr("opacity", 1);
    }
  }, [
    lines,
    envelope,
    selectedTeamId,
    selectedLegs,
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
    data.results,
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
    const teamGap = width < MOBILE_BREAK ? 36 : 42;
    const othersGap = width < MOBILE_BREAK ? 22 : 26;
    const rowGap = (i: number) =>
      rows[i].kind === "others" ? othersGap : teamGap;
    const gapBefore = (i: number) => Math.max(rowGap(i - 1), rowGap(i));

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
    const t = x.invert(event.clientX - rect.left).getTime();
    const index = bisector((time: number) => time).center(runTimes, t);
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
                left: group.anchorX + 13 + deltaGutter,
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
            className="absolute flex -translate-y-1/2 items-stretch gap-x-2.5 text-left leading-none transition-opacity duration-300"
            style={{
              left: group.anchorX + 13 + deltaGutter,
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
                className="flex flex-col items-start gap-y-0 transition-opacity hover:opacity-100"
                style={{ color: team.colour }}
              >
                <span className="font-display text-[14px] font-bold leading-none tracking-[0.01em]">
                  {team.code}
                </span>
                <span className="font-display text-[clamp(20px,2.2vw,28px)] font-extrabold tabular-nums tracking-[-0.02em]">
                  {group.value}
                </span>
              </button>
            ))}
          </div>
        );
      })}
      {selectedLegs && selectedTeam && lastRunTime !== null && (
        <div
          className="pointer-events-none absolute z-10 whitespace-nowrap text-right transition-opacity duration-300"
          style={{
            right: Math.max(8, width - (x(lastRunTime) + ESTIMATE_LANE_PX - 6)),
            top: 2,
            opacity: intro ? 1 : 0,
          }}
        >
          <span
            className="block font-display text-[11px] font-bold leading-tight tracking-[0.01em]"
            style={{ color: selectedTeam.colour }}
          >
            {teamCode(selectedTeam.name)} est. shift
          </span>
          <span className="block font-display text-[10px] font-medium leading-tight tracking-[0.01em] text-cream-faint">
            from latest results
          </span>
        </div>
      )}
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
