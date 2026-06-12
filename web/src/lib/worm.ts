// Pure transform: a day's live history -> worm chart geometry for one match.
import type { LiveHistory, LiveHistoryFixture } from "@/lib/live";

export interface WormPoint {
  x: number;
  y: number;
  minute: number | null;
}

export interface WormGoal {
  x: number;
  y: number;
  score: string;
}

export interface WormGeometry {
  width: number;
  height: number;
  points: WormPoint[];
  goals: WormGoal[];
  midline: number;
}

const WIDTH = 880;
const HEIGHT = 260;
const PAD = { left: 52, right: 28, top: 18, bottom: 30 };

export function wormGeometry(history: LiveHistory, match: number): WormGeometry | null {
  const samples: { fixture: LiveHistoryFixture; at: number }[] = [];
  for (const point of history.points) {
    const fixture = point.fixtures.find((f) => f.match === match);
    if (fixture?.forecast && fixture.status !== "scheduled") {
      samples.push({ fixture, at: new Date(point.fetched_at).getTime() });
    }
  }
  if (samples.length < 2) return null;

  const t0 = samples[0].at;
  const t1 = samples[samples.length - 1].at;
  const plotW = WIDTH - PAD.left - PAD.right;
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const x = (t: number) => PAD.left + ((t - t0) / Math.max(1, t1 - t0)) * plotW;
  const y = (p: number) => PAD.top + (1 - p) * plotH;

  const points = samples.map((s) => ({
    x: x(s.at),
    y: y(s.fixture.forecast?.p_home ?? 0.5),
    minute: s.fixture.minute ?? null,
  }));

  const goals: WormGoal[] = [];
  for (let i = 1; i < samples.length; i++) {
    const prev = samples[i - 1].fixture;
    const current = samples[i].fixture;
    if ((current.home_goals ?? 0) !== (prev.home_goals ?? 0) || (current.away_goals ?? 0) !== (prev.away_goals ?? 0)) {
      goals.push({
        x: points[i].x,
        y: points[i].y,
        score: `${current.home_goals ?? 0}–${current.away_goals ?? 0}`,
      });
    }
  }

  return { width: WIDTH, height: HEIGHT, points, goals, midline: y(0.5) };
}

export function wormPath(points: WormPoint[]): string {
  return points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
}
