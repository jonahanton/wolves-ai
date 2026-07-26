import type { TeamHistoryPoint } from "@/lib/runs";

export interface ChartPoint {
  t: number;
  value: number;
  runId?: string;
}

export type TeamTier = "top" | "rest";

export interface TeamLine {
  teamId: string;
  name: string;
  colour: string;
  featured: boolean;
  tier: TeamTier;
  points: ChartPoint[];
}

export interface ForecastChartData {
  teams: TeamLine[];
}

export interface ChartTeamInput {
  teamId: string;
  name: string;
  colour: string;
  featured: boolean;
  tier: TeamTier;
  history: TeamHistoryPoint[];
}

// Run ids carry the start instant (agent-YYYYMMDD-HHMMSS); asOf is only a day.
function runTime(runId: string, asOf: string): number {
  const stamp = /^agent-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})$/.exec(runId);
  if (!stamp) return Date.parse(asOf);
  const [, y, mo, d, h, mi, sec] = stamp;
  return Date.parse(`${y}-${mo}-${d}T${h}:${mi}:${sec}Z`);
}

function championLine(history: TeamHistoryPoint[]): ChartPoint[] {
  return history
    .filter((p) => p.runId.startsWith("agent-"))
    .map((p) => ({ t: runTime(p.runId, p.asOf), value: p.championProb, runId: p.runId }))
    .sort((a, b) => a.t - b.t);
}

export function assembleChartData(teams: ChartTeamInput[]): ForecastChartData {
  const lines = teams.map((team) => ({
    teamId: team.teamId,
    name: team.name,
    colour: team.colour,
    featured: team.featured,
    tier: team.tier,
    points: championLine(team.history),
  }));
  return { teams: lines };
}
