import type { TeamHistoryPoint } from "@/lib/runs";

export interface SeriesPoint {
  x: number;
  y: number;
  agent: boolean;
}

export interface SeriesGeometry {
  teamId: string;
  name: string;
  featured: boolean;
  points: SeriesPoint[];
  marketPoints: { x: number; y: number }[];
  label: string;
  labelY: number;
  colour: string;
}

export interface ChartFrame {
  width: number;
  height: number;
  left: number;
  right: number;
  top: number;
  bottom: number;
  gridlines: { y: number; label: string }[];
}

export type ChartVariant = "desktop" | "mobile";

const FRAMES: Record<ChartVariant, Omit<ChartFrame, "gridlines">> = {
  desktop: { width: 880, height: 320, left: 52, right: 180, top: 28, bottom: 36 },
  mobile: { width: 420, height: 300, left: 38, right: 104, top: 24, bottom: 30 },
};

export interface TeamSeries {
  teamId: string;
  name: string;
  featured: boolean;
  colour: string;
  points: TeamHistoryPoint[];
}

export function chartGeometry(
  series: TeamSeries[],
  variant: ChartVariant = "desktop",
): { frame: ChartFrame; lines: SeriesGeometry[] } {
  const FRAME = FRAMES[variant];
  const all = series.flatMap((s) => s.points.map((p) => p.championProb));
  const maxProb = Math.max(0.05, ...all) * 1.25;
  const runIds = [...new Set(series.flatMap((s) => s.points.map((p) => `${p.asOf}|${p.runId}`)))].sort();
  const xFor = new Map(runIds.map((id, i) => [id, i]));
  const span = Math.max(1, runIds.length - 1);

  const plotW = FRAME.width - FRAME.left - FRAME.right;
  const plotH = FRAME.height - FRAME.top - FRAME.bottom;
  const x = (i: number) => FRAME.left + (i / span) * plotW;
  const y = (p: number) => FRAME.top + (1 - p / maxProb) * plotH;

  const stepPct = maxProb > 0.2 ? 5 : maxProb > 0.08 ? 2 : 1;
  const gridlines = [];
  for (let pct = stepPct; pct / 100 < maxProb; pct += stepPct) {
    gridlines.push({ y: y(pct / 100), label: `${pct}` });
  }

  const lines = series.map((s) => {
    const points = s.points.map((p) => ({
      x: x(xFor.get(`${p.asOf}|${p.runId}`) ?? 0),
      y: y(p.championProb),
      agent: p.runId.startsWith("agent-"),
    }));
    const marketPoints = s.featured
      ? s.points
          .filter((p) => p.marketProb !== null && p.marketProb !== undefined)
          .map((p) => ({ x: x(xFor.get(`${p.asOf}|${p.runId}`) ?? 0), y: y(p.marketProb as number) }))
      : [];
    return {
      teamId: s.teamId,
      name: s.name,
      featured: s.featured,
      colour: s.colour,
      label: s.points.length
        ? `${abbreviate(s.name)} ${(s.points[s.points.length - 1].championProb * 100).toFixed(1)}`
        : abbreviate(s.name),
      labelY: points.length ? points[points.length - 1].y : 0,
      points,
      marketPoints,
    };
  });
  separateLabels(lines, variant === "mobile" ? 18 : 21);

  return { frame: { ...FRAME, gridlines }, lines };
}

export function trimToPublished(points: TeamHistoryPoint[], publishedRunId: string): TeamHistoryPoint[] {
  const index = points.findIndex((p) => p.runId === publishedRunId);
  return index >= 0 ? points.slice(0, index + 1) : points;
}

function separateLabels(lines: { labelY: number; points: SeriesPoint[] }[], gap: number): void {
  const placed = lines.filter((line) => line.points.length).sort((a, b) => a.labelY - b.labelY);
  for (let i = 1; i < placed.length; i++) {
    if (placed[i].labelY - placed[i - 1].labelY < gap) {
      placed[i].labelY = placed[i - 1].labelY + gap;
    }
  }
}

export function polyline(points: SeriesPoint[]): string {
  return points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
}

function abbreviate(name: string): string {
  return name.replace(/[^A-Za-z]/g, "").slice(0, 3).toUpperCase();
}
