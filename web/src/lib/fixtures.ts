import { type DistroPoint, gridX, samplesToCurve, wdlBoundarySpread } from "@/lib/distribution";
import { type LiveFixture, type LiveState, liveIsFresh } from "@/lib/live";
import type { PlayedResultRow } from "@/lib/results";
import type { BracketSamples, MatchWdlDraws } from "@/lib/sidecars";
import type { MatchProbs } from "@/lib/snapshot";
import { type RowColours, resolveWdlColours, teamCode } from "@/lib/team-colours";

export type FixtureStatus = "upcoming" | "live" | "completed";

export interface WdlBar {
  home: number;
  draw: number;
  away: number;
  sigmaHomeDraw: number;
  sigmaDrawAway: number;
}

export interface WdlShape {
  home: DistroPoint[];
  draw: DistroPoint[];
  away: DistroPoint[];
}

export interface PairingOption {
  homeId: string;
  awayId: string;
  homeCode: string;
  awayCode: string;
  pPairing: number;
  pHome: number;
  pAway: number;
  colours: RowColours;
}

export interface FixtureRow {
  match: number;
  stage: string;
  kickoff: string;
  status: FixtureStatus;
  knockout: boolean;
  homeId: string | null;
  awayId: string | null;
  homeCode: string;
  awayCode: string;
  homeGoals: number | null;
  awayGoals: number | null;
  minute: number | null;
  bar: WdlBar;
  shape: WdlShape | null;
  colours: RowColours;
  hasSpread: boolean;
  pairings: PairingOption[] | null;
}

export interface DayGroup {
  dayKey: string;
  label: string;
  rows: FixtureRow[];
  isToday: boolean;
}

const GRID = gridX(1, 48);
const MAX_PAIRINGS = 4;
const EASTERN = "America/New_York";

function dayKey(iso: string): string {
  return new Date(iso).toLocaleDateString("en-CA", { timeZone: EASTERN });
}

function dayLabel(iso: string): string {
  return new Date(iso).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: EASTERN,
  });
}

function codeOf(id: string | null, names: Record<string, string>): string {
  if (!id) return "TBC";
  return teamCode(names[id] ?? id);
}

function shapeFor(draws: MatchWdlDraws | null, match: number): WdlShape | null {
  const cell = draws?.matches[String(match)];
  if (!cell) return null;
  return {
    home: samplesToCurve(cell.p_home, GRID),
    draw: samplesToCurve(cell.p_draw, GRID),
    away: samplesToCurve(cell.p_away, GRID),
  };
}

function barFor(probs: { home: number; draw: number; away: number }, draws: MatchWdlDraws | null, match: number): WdlBar {
  const cell = draws?.matches[String(match)];
  const spread = cell ? wdlBoundarySpread(cell) : { sigmaHomeDraw: 0, sigmaDrawAway: 0 };
  return { ...probs, ...spread };
}

function pairingsFor(
  brackets: BracketSamples | null,
  match: number,
  names: Record<string, string>,
): PairingOption[] | null {
  if (!brackets) return null;
  const counts = new Map<string, { home: string; away: string; n: number; homeWins: number; awayWins: number }>();
  let total = 0;
  for (const sample of brackets.samples) {
    const entry = sample.matches.find((m) => m.match === match);
    if (!entry) continue;
    total += 1;
    const key = `${entry.home}|${entry.away}`;
    const row = counts.get(key) ?? { home: entry.home, away: entry.away, n: 0, homeWins: 0, awayWins: 0 };
    row.n += 1;
    if (entry.winner === entry.home) row.homeWins += 1;
    else if (entry.winner === entry.away) row.awayWins += 1;
    counts.set(key, row);
  }
  if (total === 0) return null;
  return [...counts.values()]
    .sort((a, b) => b.n - a.n)
    .slice(0, MAX_PAIRINGS)
    .map((row) => ({
      homeId: row.home,
      awayId: row.away,
      homeCode: codeOf(row.home, names),
      awayCode: codeOf(row.away, names),
      pPairing: row.n / total,
      pHome: row.n > 0 ? row.homeWins / row.n : 0,
      pAway: row.n > 0 ? row.awayWins / row.n : 0,
      colours: resolveWdlColours(row.home, row.away),
    }));
}

function buildRow(
  match: MatchProbs,
  live: LiveFixture | null,
  result: PlayedResultRow | null,
  draws: MatchWdlDraws | null,
  brackets: BracketSamples | null,
  names: Record<string, string>,
): FixtureRow {
  const knockout = match.stage !== "group";
  const status: FixtureStatus = live ? "live" : result ? "completed" : "upcoming";
  const homeId = live?.homeId ?? match.home_id ?? null;
  const awayId = live?.awayId ?? match.away_id ?? null;
  const resolved = Boolean(result || live);
  const pairings = knockout && !resolved ? pairingsFor(brackets, match.match, names) : null;

  const probs =
    status === "live" && live?.forecast
      ? { home: live.forecast.pHome, draw: live.forecast.pDraw ?? 0, away: live.forecast.pAway }
      : { home: match.p_home, draw: match.p_draw ?? 0, away: match.p_away };

  const hasSpread = status !== "live" && Boolean(draws?.matches[String(match.match)]);

  return {
    match: match.match,
    stage: match.stage,
    kickoff: match.date,
    status,
    knockout,
    homeId,
    awayId,
    homeCode: codeOf(homeId, names),
    awayCode: codeOf(awayId, names),
    homeGoals: live?.homeGoals ?? result?.homeGoals ?? null,
    awayGoals: live?.awayGoals ?? result?.awayGoals ?? null,
    minute: status === "live" ? (live?.minute ?? null) : null,
    bar: barFor(probs, hasSpread ? draws : null, match.match),
    shape: hasSpread ? shapeFor(draws, match.match) : null,
    colours: resolveWdlColours(homeId, awayId),
    hasSpread,
    pairings,
  };
}

function pickOpenIndex(days: DayGroup[], todayKey: string): number {
  const todayIndex = days.findIndex((d) => d.dayKey === todayKey && d.rows.length > 0);
  if (todayIndex >= 0) return todayIndex;
  const future = days.findIndex((d) => d.dayKey > todayKey && d.rows.length > 0);
  if (future >= 0) return future;
  for (let i = days.length - 1; i >= 0; i -= 1) {
    if (days[i].rows.length > 0) return i;
  }
  return 0;
}

export function buildFixtureDays(input: {
  matches: MatchProbs[];
  draws: MatchWdlDraws | null;
  brackets: BracketSamples | null;
  results: PlayedResultRow[];
  live: LiveState | null;
  teamNames: Record<string, string>;
  nowIso: string;
}): { days: DayGroup[]; openIndex: number } {
  const liveByMatch = new Map<number, LiveFixture>();
  // A stale poll cannot be trusted to a live minute, so live rows fall back to the pre-game shape.
  const fresh = liveIsFresh(input.live, Date.parse(input.nowIso));
  for (const fixture of fresh ? (input.live?.fixtures ?? []) : []) {
    if (fixture.match !== null && fixture.status === "live") liveByMatch.set(fixture.match, fixture);
  }
  const resultByMatch = new Map(input.results.map((r) => [r.match, r]));

  const byDay = new Map<string, DayGroup>();
  const todayKey = dayKey(input.nowIso);
  for (const match of input.matches) {
    const row = buildRow(
      match,
      liveByMatch.get(match.match) ?? null,
      resultByMatch.get(match.match) ?? null,
      input.draws,
      input.brackets,
      input.teamNames,
    );
    const key = dayKey(match.date);
    const group = byDay.get(key) ?? { dayKey: key, label: dayLabel(match.date), rows: [], isToday: key === todayKey };
    group.rows.push(row);
    byDay.set(key, group);
  }

  const days = [...byDay.values()].sort((a, b) => a.dayKey.localeCompare(b.dayKey));
  for (const day of days) day.rows.sort((a, b) => a.kickoff.localeCompare(b.kickoff) || a.match - b.match);
  return { days, openIndex: pickOpenIndex(days, todayKey) };
}
