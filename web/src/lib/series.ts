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

export const FRAME: ChartFrame = {
  width: 880,
  height: 320,
  left: 52,
  right: 180,
  top: 28,
  bottom: 36,
  gridlines: [],
};

export interface TeamSeries {
  teamId: string;
  name: string;
  featured: boolean;
  colour: string;
  points: TeamHistoryPoint[];
}

export function chartGeometry(series: TeamSeries[]): { frame: ChartFrame; lines: SeriesGeometry[] } {
  const all = series.flatMap((s) => s.points.map((p) => p.championProb));
  const maxProb = Math.max(0.05, ...all) * 1.25;
  const runIds = [...new Set(series.flatMap((s) => s.points.map((p) => `${p.asOf}|${p.runId}`)))].sort();
  const xFor = new Map(runIds.map((id, i) => [id, i]));
  const span = Math.max(1, runIds.length - 1);

  const plotW = FRAME.width - FRAME.left - FRAME.right;
  const plotH = FRAME.height - FRAME.top - FRAME.bottom;
  const x = (i: number) => FRAME.left + (i / span) * plotW;
  const y = (p: number) => FRAME.top + (1 - p / maxProb) * plotH;

  const step = maxProb > 0.15 ? 0.05 : 0.025;
  const gridlines = [];
  for (let g = step; g < maxProb; g += step) {
    gridlines.push({ y: y(g), label: `${Math.round(g * 100)}` });
  }

  const lines = series.map((s) => {
    const points = s.points.map((p) => ({
      x: x(xFor.get(`${p.asOf}|${p.runId}`) ?? 0),
      y: y(p.championProb),
      agent: p.runId.startsWith("agent-"),
    }));
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
    };
  });
  separateLabels(lines);

  return { frame: { ...FRAME, gridlines }, lines };
}

const LABEL_GAP = 21;

function separateLabels(lines: { labelY: number; points: SeriesPoint[] }[]): void {
  const placed = lines.filter((line) => line.points.length).sort((a, b) => a.labelY - b.labelY);
  for (let i = 1; i < placed.length; i++) {
    if (placed[i].labelY - placed[i - 1].labelY < LABEL_GAP) {
      placed[i].labelY = placed[i - 1].labelY + LABEL_GAP;
    }
  }
}

export function polyline(points: SeriesPoint[]): string {
  return points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
}

function abbreviate(name: string): string {
  return name.replace(/[^A-Za-z]/g, "").slice(0, 3).toUpperCase();
}
