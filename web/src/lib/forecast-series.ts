// Assembles the landing chart's series. The Wolves line is the agent's full
// forecasts only; the engine appears solely as the dotted estimate mapped onto
// the agent scale by the backend. The market line is the de-vigged outright
// and its inverse-implied stage probabilities. The two sources never share a line.
import type { Impact } from "@/lib/impact";
import type { ImpliedReachPoint } from "@/lib/market-reach";
import type { PlayedResultRow } from "@/lib/results";
import type { TeamHistoryPoint } from "@/lib/runs";

export type Outcome = "champion" | "final" | "sf" | "qf";
export type Source = "wolves" | "market";

export const OUTCOMES: { key: Outcome; label: string; short: string; phrase: string }[] = [
  { key: "champion", label: "Winner", short: "Winner", phrase: "winning the World Cup" },
  { key: "final", label: "Final", short: "Final", phrase: "reaching the final" },
  { key: "sf", label: "Semi-final", short: "SF", phrase: "reaching the semi-finals" },
  { key: "qf", label: "Quarter-final", short: "QF", phrase: "reaching the quarter-finals" },
];

export interface ChartPoint {
  t: number;
  value: number;
  runId?: string;
}

export interface TeamLine {
  teamId: string;
  name: string;
  colour: string;
  featured: boolean;
  wolves: Record<Outcome, ChartPoint[]>;
  market: Record<Outcome, ChartPoint[]>;
  estimate: Record<Outcome, ChartPoint[]>;
}

export interface FixtureResultView {
  t: number;
  label: string;
}

export interface EstimateBreakdown {
  t: number;
  text: string;
}

export interface ForecastChartData {
  teams: TeamLine[];
  results: FixtureResultView[];
  breakdown: Partial<Record<Outcome, EstimateBreakdown>>;
}

export interface ChartTeamInput {
  teamId: string;
  name: string;
  colour: string;
  featured: boolean;
  history: TeamHistoryPoint[];
}

function emptyOutcomes(): Record<Outcome, ChartPoint[]> {
  return { champion: [], final: [], sf: [], qf: [] };
}

function historyValue(point: TeamHistoryPoint, outcome: Outcome): number | null {
  if (outcome === "champion") return point.championProb;
  return point.reachProbs?.[outcome] ?? null;
}

// Run ids carry the start instant (agent-YYYYMMDD-HHMMSS); asOf is only a day.
function runTime(runId: string, asOf: string): number {
  const stamp = /^agent-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})$/.exec(runId);
  if (!stamp) return Date.parse(asOf);
  const [, y, mo, d, h, mi, sec] = stamp;
  return Date.parse(`${y}-${mo}-${d}T${h}:${mi}:${sec}Z`);
}

function wolvesLines(history: TeamHistoryPoint[]): Record<Outcome, ChartPoint[]> {
  const lines = emptyOutcomes();
  const agentPoints = history.filter((p) => p.runId.startsWith("agent-"));
  for (const outcome of OUTCOMES) {
    lines[outcome.key] = agentPoints.flatMap((p) => {
      const value = historyValue(p, outcome.key);
      return value === null ? [] : [{ t: runTime(p.runId, p.asOf), value, runId: p.runId }];
    });
  }
  return lines;
}

// Captures arrive at irregular real times (and the odd near-duplicate). Snapping
// to a regular grid and keeping the latest per slot gives an honest, even cadence.
const MARKET_SLOT_MS = 6 * 3_600_000;
const ESTIMATE_SLOT_MS = 3_600_000;

function regularCaptures(points: ImpliedReachPoint[]): ImpliedReachPoint[] {
  const bySlot = new Map<number, ImpliedReachPoint>();
  for (const point of [...points].sort((a, b) => Date.parse(a.captured_at) - Date.parse(b.captured_at))) {
    const slot = Math.round(Date.parse(point.captured_at) / MARKET_SLOT_MS) * MARKET_SLOT_MS;
    bySlot.set(slot, { ...point, captured_at: new Date(slot).toISOString() });
  }
  return [...bySlot.values()].sort((a, b) => Date.parse(a.captured_at) - Date.parse(b.captured_at));
}

function regularSeriesPoints(points: ChartPoint[]): ChartPoint[] {
  const bySlot = new Map<number, ChartPoint>();
  for (const point of [...points].sort((a, b) => a.t - b.t)) {
    bySlot.set(Math.round(point.t / ESTIMATE_SLOT_MS) * ESTIMATE_SLOT_MS, point);
  }
  return [...bySlot.values()].sort((a, b) => a.t - b.t);
}

function marketLines(teamId: string, points: ImpliedReachPoint[]): Record<Outcome, ChartPoint[]> {
  const lines = emptyOutcomes();
  for (const outcome of OUTCOMES) {
    lines[outcome.key] = points.flatMap((point) => {
      const value =
        outcome.key === "champion" ? point.outright[teamId] : point.teams[teamId]?.[outcome.key];
      return value === undefined ? [] : [{ t: Date.parse(point.captured_at), value }];
    });
  }
  return lines;
}

function estimateLines(
  teamId: string,
  wolves: Record<Outcome, ChartPoint[]>,
  impact: Impact | null,
  now: number,
): Record<Outcome, ChartPoint[]> {
  const lines = emptyOutcomes();
  const stages = impact?.teams[teamId];
  if (!impact || !stages) return lines;
  for (const outcome of OUTCOMES) {
    const anchor = wolves[outcome.key].at(-1);
    const stage = stages[outcome.key];
    if (!anchor || !stage) continue;
    const seriesPoints = regularSeriesPoints(
      impact.series.flatMap((point) => {
        const value = point.teams[teamId]?.[outcome.key];
        const t = Date.parse(point.fetchedAt);
        return value === undefined || t <= anchor.t ? [] : [{ t, value }];
      }),
    );
    const moved = Math.abs(stage.estimated - stage.agent) >= 0.0005;
    if (!seriesPoints.length && !moved) continue;
    lines[outcome.key] = [anchor, ...seriesPoints, { t: now, value: stage.estimated }];
  }
  return lines;
}

export function assembleChartData(
  teams: ChartTeamInput[],
  marketReach: ImpliedReachPoint[],
  impact: Impact | null,
  results: PlayedResultRow[],
  names: Record<string, string>,
  now: number,
): ForecastChartData {
  const captures = regularCaptures(marketReach);
  const lines = teams.map((team) => {
    const wolves = wolvesLines(team.history);
    return {
      teamId: team.teamId,
      name: team.name,
      colour: team.colour,
      featured: team.featured,
      wolves,
      market: marketLines(team.teamId, captures),
      estimate: estimateLines(team.teamId, wolves, impact, now),
    };
  });
  return {
    teams: lines,
    results: resultViews(results, names),
    breakdown: estimateBreakdowns(teams, impact, now),
  };
}

function signedPts(delta: number): string {
  const rounded = Math.round(delta * 10) / 10;
  return `${rounded > 0 ? "+" : ""}${rounded}pt`;
}

function estimateBreakdowns(
  teams: ChartTeamInput[],
  impact: Impact | null,
  now: number,
): Partial<Record<Outcome, EstimateBreakdown>> {
  const focus = teams.find((team) => team.featured);
  const stages = focus ? impact?.teams[focus.teamId] : undefined;
  if (!focus || !stages) return {};
  const breakdown: Partial<Record<Outcome, EstimateBreakdown>> = {};
  for (const outcome of OUTCOMES) {
    const stage = stages[outcome.key];
    if (!stage) continue;
    const parts: string[] = [];
    if (Math.abs(stage.fromResultsPp) >= 0.05) parts.push(`${signedPts(stage.fromResultsPp)} results`);
    if (Math.abs(stage.fromIngamePp) >= 0.05) parts.push(`${signedPts(stage.fromIngamePp)} in-game`);
    if (parts.length) breakdown[outcome.key] = { t: now, text: `${focus.name} ${parts.join(" · ")}` };
  }
  return breakdown;
}

// A result becomes news roughly two hours after kickoff.
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

export function resultsBetween(results: FixtureResultView[], from: number, to: number): FixtureResultView[] {
  return results.filter((row) => row.t > from && row.t <= to).sort((a, b) => a.t - b.t);
}
