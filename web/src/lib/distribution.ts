import type { ScenarioWeightOut } from "@/lib/snapshot";
import type { CellShape } from "@/lib/sidecars";

export interface Frequency {
  denominator: number;
  capped: boolean;
}

export function oneInN(p: number, cap = 100): Frequency | null {
  if (!(p > 0)) return null;
  const n = Math.round(1 / p);
  if (n >= cap) return { denominator: cap, capped: true };
  return { denominator: Math.max(2, n), capped: false };
}

export interface DistroPoint {
  x: number;
  y: number;
}

export interface CampCurve {
  key: string;
  weight: number;
  points: DistroPoint[];
  bars: Bar[];
}

function binCentres(edges: number[]): number[] {
  const centres: number[] = [];
  for (let i = 0; i < edges.length - 1; i += 1) centres.push((edges[i] + edges[i + 1]) / 2);
  return centres;
}

function withBaselineEnds(edges: number[], bins: number[]): DistroPoint[] {
  const centres = binCentres(edges);
  const inner = centres.map((x, i) => ({ x, y: bins[i] ?? 0 }));
  return [{ x: edges[0], y: 0 }, ...inner, { x: edges[edges.length - 1], y: 0 }];
}

export function combinedCurve(cell: CellShape): DistroPoint[] {
  return withBaselineEnds(cell.bin_edges, cell.histogram);
}

// A fixed x-grid shared by every team so resampled curves have identical point
// counts, letting the stroke paths morph by plain d-attr interpolation.
export function gridX(xMax: number, samples: number): number[] {
  const step = xMax / samples;
  return Array.from({ length: samples + 1 }, (_, i) => i * step);
}

// Linear-interpolate a monotone-in-x curve onto the shared grid; zero outside its extent.
export function resampleCurve(points: DistroPoint[], grid: number[]): DistroPoint[] {
  if (points.length < 2) return grid.map((x) => ({ x, y: 0 }));
  const lo = points[0].x;
  const hi = points[points.length - 1].x;
  let j = 0;
  return grid.map((x) => {
    if (x <= lo || x >= hi) return { x, y: 0 };
    while (j < points.length - 1 && points[j + 1].x < x) j += 1;
    const a = points[j];
    const b = points[Math.min(j + 1, points.length - 1)];
    const span = b.x - a.x;
    const t = span > 0 ? (x - a.x) / span : 0;
    return { x, y: a.y + t * (b.y - a.y) };
  });
}

export interface Bar {
  x0: number;
  x1: number;
  y: number;
}

export function histogramBars(cell: CellShape): Bar[] {
  const edges = cell.bin_edges;
  return cell.histogram.map((y, i) => ({ x0: edges[i], x1: edges[i + 1], y }));
}

// A world with no declared camp stands as its own camp, keyed by its world name.
function campOfWorld(weights: ScenarioWeightOut[]): Record<string, string> {
  const map: Record<string, string> = {};
  for (const w of weights) map[w.name] = w.camp && w.camp.length > 0 ? w.camp : w.name;
  return map;
}

// world_bins are pre-weight-scaled, so summing a camp's worlds gives its weighted curve.
export function campCurves(cell: CellShape, weights: ScenarioWeightOut[]): CampCurve[] {
  const camp = campOfWorld(weights);
  const bins = cell.bin_edges.length - 1;
  const summed: Record<string, number[]> = {};
  const weight: Record<string, number> = {};

  for (const world of Object.keys(cell.world_bins)) {
    const key = camp[world] ?? world;
    const source = cell.world_bins[world];
    const target = (summed[key] ??= new Array(bins).fill(0));
    for (let i = 0; i < bins; i += 1) target[i] += source[i] ?? 0;
    weight[key] = (weight[key] ?? 0) + (cell.components[world]?.weight ?? 0);
  }

  const edges = cell.bin_edges;
  return Object.keys(summed)
    .sort()
    .map((key) => ({
      key,
      weight: weight[key] ?? 0,
      points: withBaselineEnds(edges, summed[key]),
      bars: summed[key].map((y, i) => ({ x0: edges[i], x1: edges[i + 1], y })),
    }));
}

// Parameter draws behind each cell; the curve is the spread across these.
export const SAMPLES_PER_CELL = 200;

export function peakDensity(cell: CellShape): number {
  return Math.max(...cell.histogram, 0);
}

export function laneMax(camp: CampCurve): number {
  return Math.max(...camp.points.map((p) => p.y), 1e-9);
}

export function campOffsets(camps: CampCurve[]): number[] {
  const out: number[] = [];
  let cum = 0;
  for (const c of camps) {
    out.push(cum);
    cum += c.weight;
  }
  return out;
}

function quantile(cell: CellShape, q: number): number {
  const { bin_edges: edges, histogram } = cell;
  let cum = 0;
  for (let i = 0; i < histogram.length; i += 1) {
    const next = cum + histogram[i];
    if (next >= q) {
      const frac = histogram[i] > 0 ? (q - cum) / histogram[i] : 0;
      return edges[i] + frac * (edges[i + 1] - edges[i]);
    }
    cum = next;
  }
  return edges[edges.length - 1];
}

export function ourCall(cell: CellShape): number {
  return cell.our_call ?? quantile(cell, 0.5);
}

const CAMP_PALETTE = [
  "oklch(0.74 0.13 232)",
  "oklch(0.78 0.14 64)",
  "oklch(0.72 0.15 330)",
  "oklch(0.76 0.14 158)",
  "oklch(0.7 0.16 22)",
  "oklch(0.74 0.11 282)",
  "oklch(0.78 0.13 130)",
  "oklch(0.7 0.15 350)",
  "oklch(0.76 0.12 200)",
  "oklch(0.72 0.14 40)",
];

// Sorted-key assignment keeps a camp's hue stable when the selected team changes.
export function campPalette(keys: string[]): Record<string, string> {
  const palette: Record<string, string> = {};
  [...keys].sort().forEach((key, i) => {
    palette[key] = CAMP_PALETTE[i % CAMP_PALETTE.length];
  });
  return palette;
}

// Title-case a raw world key (model_base -> Model base) for a camp with no declared label.
export function humaniseKey(key: string): string {
  const cleaned = key.replace(/[_-]+/g, " ").trim();
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

