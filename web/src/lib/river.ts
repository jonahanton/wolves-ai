import type { Snapshot } from "@/lib/snapshot";

const ROUND_TOTALS = [32, 16, 8, 4, 2, 1];
const STAGE_KEYS = ["r32", "r16", "qf", "sf", "final", "champion"] as const;
const STAGE_NAMES = ["R32", "R16", "QF", "SF", "Final", "Champion"];

export interface RiverBand {
  teamId: string | null;
  name: string;
  reach: number[];
  fill: string;
  core: string;
  bank: string;
  glow: boolean;
  labelY: number;
  path: string;
  corePath: string;
  bankPath: string;
}

export interface RiverStation {
  x: number;
  name: string;
  dates: string;
}

export interface RiverGeometry {
  width: number;
  height: number;
  bands: RiverBand[];
  stations: RiverStation[];
  focusRoad: { x: number; y: number; label: string }[];
}

interface RiverOptions {
  teamCount?: number;
  height?: number;
  width?: number;
  compact?: boolean;
}

export function riverGeometry(snapshot: Snapshot, options: RiverOptions = {}): RiverGeometry {
  const { teamCount = 10, height: H = 600, width: W = 1280, compact = false } = options;
  const mL = compact ? 108 : 142;
  const mR = compact ? 60 : 188;
  const mT = 46;
  const mB = 14;
  const nX = 6;
  const focusId = snapshot.focus.team_id;

  const ranked = snapshot.teams
    .filter((t) => t.reach_probs)
    .sort((a, b) => (b.reach_probs?.champion ?? 0) - (a.reach_probs?.champion ?? 0))
    .slice(0, teamCount);
  const leaderId = ranked[0]?.team_id;

  const named = ranked.map((t) => ({
    teamId: t.team_id as string | null,
    name: t.name,
    reach: STAGE_KEYS.map((key) => t.reach_probs?.[key] ?? 0),
  }));
  const field = {
    teamId: null,
    name: "the field",
    reach: ROUND_TOTALS.map((total, r) => total - named.reduce((sum, band) => sum + band.reach[r], 0)),
  };
  const bands = [...named, field];
  const nB = bands.length;

  const xs = Array.from({ length: nX }, (_, k) => mL + (k * (W - mL - mR)) / (nX - 1));
  const gaps = compact ? [6, 5, 3.5, 3, 2.5, 2.5] : [9, 7, 5, 3.5, 2.5, 2.5];
  const avail = H - mT - mB;
  const scale = (avail * 0.97 - gaps[0] * (nB - 1)) / 32;
  const heightFor = (p: number) => (p <= 0 ? 0 : p >= 0.02 ? Math.max(p * scale, 1.2) : p * scale);

  // Station order: named bands by next-round reach, the field as the lower bank.
  const slots: { top: number; bot: number }[][] = [];
  for (let r = 0; r < nX; r++) {
    const key = Math.min(r + 1, nX - 1);
    const order = bands
      .slice(0, nB - 1)
      .map((_, i) => i)
      .sort((a, b) => bands[b].reach[key] - bands[a].reach[key]);
    order.push(nB - 1);
    const heights = bands.map((band) => heightFor(band.reach[r]));
    const total = heights.reduce((a, b) => a + b, 0) + gaps[r] * (nB - 1);
    let y = mT + avail / 2 - total / 2;
    const station = new Array<{ top: number; bot: number }>(nB);
    for (const i of order) {
      station[i] = { top: y, bot: y + heights[i] };
      y += heights[i] + gaps[r];
    }
    slots.push(station);
  }

  const edge = (x1: number, y1: number, x2: number, y2: number) => {
    const dx = (x2 - x1) * 0.45;
    return `C${(x1 + dx).toFixed(1)},${y1.toFixed(1)} ${(x2 - dx).toFixed(1)},${y2.toFixed(1)} ${x2.toFixed(1)},${y2.toFixed(1)}`;
  };
  const ribbon = (tops: number[], bots: number[]) => {
    let d = `M${xs[0].toFixed(1)},${tops[0].toFixed(1)}`;
    for (let r = 0; r < nX - 1; r++) d += edge(xs[r], tops[r], xs[r + 1], tops[r + 1]);
    d += `L${xs[nX - 1].toFixed(1)},${bots[nX - 1].toFixed(1)}`;
    for (let r = nX - 1; r > 0; r--) d += edge(xs[r], bots[r], xs[r - 1], bots[r - 1]);
    return `${d}Z`;
  };
  const bankLine = (tops: number[]) => {
    let d = `M${xs[0].toFixed(1)},${tops[0].toFixed(1)}`;
    for (let r = 0; r < nX - 1; r++) d += edge(xs[r], tops[r], xs[r + 1], tops[r + 1]);
    return d;
  };

  const plain = named.filter((band) => band.teamId !== focusId && band.teamId !== leaderId);
  const pMin = Math.min(...plain.map((band) => band.reach[5]));
  const pMax = Math.max(...plain.map((band) => band.reach[5]));
  const creamOpacity = (reach: number) => 0.1 + 0.12 * (pMax > pMin ? (reach - pMin) / (pMax - pMin) : 0.5);

  const geometryBands: RiverBand[] = bands.map((band, i) => {
    const tops = slots.map((station) => station[i].top);
    const bots = slots.map((station) => station[i].bot);
    const coreTops = slots.map((station) => station[i].top + (station[i].bot - station[i].top) * 0.3);
    const coreBots = slots.map((station) => station[i].bot - (station[i].bot - station[i].top) * 0.3);
    const colours = bandColours(band.teamId, focusId, leaderId, creamOpacity(band.reach[5]));
    return {
      teamId: band.teamId,
      name: band.name,
      reach: band.reach,
      ...colours,
      labelY: (tops[0] + bots[0]) / 2 + 4.5,
      path: ribbon(tops, bots),
      corePath: ribbon(coreTops, coreBots),
      bankPath: bankLine(tops),
    };
  });

  const stations: RiverStation[] = STAGE_NAMES.map((name, r) => ({
    x: xs[r],
    name,
    dates: stageDates(snapshot, r),
  }));

  const focusBand = geometryBands.find((band) => band.teamId === focusId);
  const focusRoad = focusBand
    ? xs.map((x, r) => ({
        x,
        y: slots[r][bands.findIndex((band) => band.teamId === focusId)].bot + 14,
        label: (focusBand.reach[r] * 100).toFixed(1),
      }))
    : [];

  return { width: W, height: H, bands: geometryBands, stations, focusRoad };
}

function bandColours(teamId: string | null, focusId: string, leaderId: string | undefined, creamOp: number) {
  if (teamId === focusId) {
    return {
      fill: "oklch(0.69 0.19 25 / 0.9)",
      core: "oklch(0.75 0.18 25 / 0.5)",
      bank: "oklch(0.79 0.17 25 / 0.7)",
      glow: true,
    };
  }
  if (teamId !== null && teamId === leaderId) {
    return {
      fill: "oklch(0.8 0.11 150 / 0.4)",
      core: "oklch(0.84 0.12 150 / 0.24)",
      bank: "oklch(0.84 0.12 150 / 0.55)",
      glow: false,
    };
  }
  if (teamId === null) {
    return {
      fill: "oklch(0.965 0.008 95 / 0.12)",
      core: "oklch(0.965 0.008 95 / 0.06)",
      bank: "oklch(0.965 0.008 95 / 0.12)",
      glow: false,
    };
  }
  return {
    fill: `oklch(0.965 0.008 95 / ${creamOp.toFixed(3)})`,
    core: `oklch(0.965 0.008 95 / ${(creamOp * 0.55).toFixed(3)})`,
    bank: "oklch(0.965 0.008 95 / 0.26)",
    glow: false,
  };
}

function stageDates(snapshot: Snapshot, stationIndex: number): string {
  if (stationIndex === 5) {
    const final = snapshot.slots.find((slot) => slot.stage === "final");
    return final ? `${shortDate(final.date)} · ${final.city.split("/")[0]}` : "";
  }
  const stage = STAGE_KEYS[stationIndex];
  const dates = snapshot.slots.filter((slot) => slot.stage === stage).map((slot) => slot.date);
  if (dates.length === 0) return "";
  const sorted = dates.sort();
  const first = shortDate(sorted[0]);
  const last = shortDate(sorted[sorted.length - 1]);
  return first === last ? first : `${first} – ${last}`;
}

function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "Europe/London" });
}
