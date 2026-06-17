import type { PlayedResultRow } from "@/lib/results";
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

export interface FixtureResultView {
  t: number;
  label: string;
}

export interface ChartImpactPoint {
  teamId: string;
  fromResultsPp: number;
  fromIngamePp: number;
  displayFloorPp: number;
}

export interface ForecastChartData {
  teams: TeamLine[];
  results: FixtureResultView[];
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

export function assembleChartData(
  teams: ChartTeamInput[],
  results: PlayedResultRow[],
  names: Record<string, string>,
): ForecastChartData {
  const lines = teams.map((team) => ({
    teamId: team.teamId,
    name: team.name,
    colour: team.colour,
    featured: team.featured,
    tier: team.tier,
    points: championLine(team.history),
  }));
  return { teams: lines, results: resultViews(results, names) };
}

const RESULT_KNOWN_AFTER_MS = 2 * 3_600_000;

function resultViews(results: PlayedResultRow[], names: Record<string, string>): FixtureResultView[] {
  return results.map((row) => ({
    t: Date.parse(row.date) + RESULT_KNOWN_AFTER_MS,
    label: `${teamName(row.homeId, names)} ${row.homeGoals}-${row.awayGoals} ${teamName(row.awayId, names)}`,
  }));
}

function teamName(teamId: string | null, names: Record<string, string>): string {
  if (teamId === null) return "TBC";
  return names[teamId] ?? teamId;
}
