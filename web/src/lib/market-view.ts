import { type ApiResult, backendGet } from "@/lib/api";
import type { Snapshot } from "@/lib/snapshot";

export interface DivergenceRow {
  teamId: string;
  name: string;
  ours: number;
  market: number;
  gapPp: number;
}

export function divergenceRows(snapshot: Snapshot, minGapPp: number): DivergenceRow[] {
  const market = snapshot.markets?.market_probs ?? {};
  return snapshot.teams
    .filter((team) => team.champion_prob !== undefined && market[team.team_id] !== undefined)
    .map((team) => ({
      teamId: team.team_id,
      name: team.name,
      ours: team.champion_prob ?? 0,
      market: market[team.team_id],
      gapPp: ((team.champion_prob ?? 0) - market[team.team_id]) * 100,
    }))
    .filter((row) => Math.abs(row.gapPp) >= minGapPp)
    .sort((a, b) => Math.abs(b.gapPp) - Math.abs(a.gapPp));
}

export interface OddsPoint {
  captured_at: string;
  outright_bookmakers: Record<string, number>;
  outright_polymarket: Record<string, number>;
}

export interface OddsDay {
  date: string;
  points: OddsPoint[];
}

export async function loadOddsDay(date: string): Promise<ApiResult<OddsDay>> {
  return backendGet<OddsDay>(`/odds/${encodeURIComponent(date)}`);
}

export async function loadOddsDates(): Promise<ApiResult<{ dates: string[] }>> {
  return backendGet<{ dates: string[] }>("/odds/dates");
}

export interface OddsSeries {
  labels: string[];
  bookmakers: (number | null)[];
  polymarket: (number | null)[];
}

export function teamOddsSeries(days: OddsDay[], teamId: string): OddsSeries {
  const labels: string[] = [];
  const bookmakers: (number | null)[] = [];
  const polymarket: (number | null)[] = [];
  for (const day of days) {
    for (const point of day.points) {
      labels.push(point.captured_at);
      bookmakers.push(point.outright_bookmakers[teamId] ?? null);
      polymarket.push(point.outright_polymarket[teamId] ?? null);
    }
  }
  return { labels, bookmakers, polymarket };
}
