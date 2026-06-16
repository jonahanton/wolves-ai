import { gridX, samplesToBars, samplesToCurve, type WdlShape } from "@/lib/distribution";
import { type LiveFixture, type LiveState, liveIsFresh } from "@/lib/live";
import type { PlayedResultRow } from "@/lib/results";
import type { MatchWdlDraws } from "@/lib/sidecars";
import type { MatchProbs, Slot } from "@/lib/snapshot";
import { type RowColours, chartColour, resolveWdlColours, teamCode } from "@/lib/team-colours";

export type FixtureStatus = "upcoming" | "live" | "completed";

export interface WdlMeans {
  home: number;
  draw: number;
  away: number;
}

export interface CandidateTeam {
  teamId: string;
  code: string;
  prob: number;
  colour: string;
}

export interface SlotSideView {
  label: string;
  candidates: CandidateTeam[];
}

export interface KnockoutSlot {
  home: SlotSideView;
  away: SlotSideView;
}

export interface FixtureRow {
  match: number;
  stage: string;
  kickoff: string;
  city: string | null;
  dayKey: string;
  dayLabel: string;
  status: FixtureStatus;
  knockout: boolean;
  homeId: string | null;
  awayId: string | null;
  homeCode: string;
  awayCode: string;
  homeName: string;
  awayName: string;
  homeGoals: number | null;
  awayGoals: number | null;
  minute: number | null;
  bar: WdlMeans | null;
  shape: WdlShape | null;
  colours: RowColours;
  slot: KnockoutSlot | null;
}

export interface DayGroup {
  dayKey: string;
  label: string;
  rows: FixtureRow[];
  isToday: boolean;
}

export interface StageSection {
  key: string;
  label: string;
  layout: "days" | "flat";
  days: DayGroup[];
  rows: FixtureRow[];
}

const GRID = gridX(1, 48);
const MAX_CANDIDATES = 3;
const EASTERN = "America/New_York";

const STAGE_ORDER = ["group", "r32", "r16", "qf", "sf", "third_place", "final"] as const;
const STAGE_LABEL: Record<string, string> = {
  group: "Groups",
  r32: "Round of 32",
  r16: "Round of 16",
  qf: "Quarter-finals",
  sf: "Semi-finals",
  third_place: "Third-place play-off",
  final: "Final",
};

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
    home: { curve: samplesToCurve(cell.p_home, GRID), bars: samplesToBars(cell.p_home) },
    draw: { curve: samplesToCurve(cell.p_draw, GRID), bars: samplesToBars(cell.p_draw) },
    away: { curve: samplesToCurve(cell.p_away, GRID), bars: samplesToBars(cell.p_away) },
  };
}

function candidateSide(side: { label: string; candidates: { team_id: string; prob: number }[] }, names: Record<string, string>): SlotSideView {
  return {
    label: side.label,
    candidates: side.candidates.slice(0, MAX_CANDIDATES).map((c) => ({
      teamId: c.team_id,
      code: codeOf(c.team_id, names),
      prob: c.prob,
      colour: chartColour(c.team_id),
    })),
  };
}

function buildRow(
  match: MatchProbs,
  live: LiveFixture | null,
  result: PlayedResultRow | null,
  slot: Slot | null,
  draws: MatchWdlDraws | null,
  names: Record<string, string>,
): FixtureRow {
  const knockout = match.stage !== "group";
  const status: FixtureStatus = live ? "live" : result ? "completed" : "upcoming";
  const resolved = Boolean(result || live);
  // A knockout tie with no played or live teams is genuinely undetermined: never imply a pairing.
  const tbc = knockout && !resolved;
  const homeId = tbc ? null : (live?.homeId ?? match.home_id ?? null);
  const awayId = tbc ? null : (live?.awayId ?? match.away_id ?? null);

  const probs =
    status === "live" && live?.forecast
      ? { home: live.forecast.pHome, draw: live.forecast.pDraw ?? 0, away: live.forecast.pAway }
      : { home: match.p_home, draw: match.p_draw ?? 0, away: match.p_away };
  const hasSpread = status !== "live" && Boolean(draws?.matches[String(match.match)]);

  return {
    match: match.match,
    stage: match.stage,
    kickoff: match.date,
    city: match.city ?? null,
    dayKey: dayKey(match.date),
    dayLabel: dayLabel(match.date),
    status,
    knockout,
    homeId,
    awayId,
    homeCode: codeOf(homeId, names),
    awayCode: codeOf(awayId, names),
    homeName: homeId ? (names[homeId] ?? homeId) : "TBC",
    awayName: awayId ? (names[awayId] ?? awayId) : "TBC",
    homeGoals: live?.homeGoals ?? result?.homeGoals ?? null,
    awayGoals: live?.awayGoals ?? result?.awayGoals ?? null,
    minute: status === "live" ? (live?.minute ?? null) : null,
    bar: tbc ? null : probs,
    shape: hasSpread ? shapeFor(draws, match.match) : null,
    colours: resolveWdlColours(homeId, awayId),
    slot:
      tbc && slot
        ? {
            home: candidateSide(slot.home, names),
            away: candidateSide(slot.away, names),
          }
        : null,
  };
}

function groupDays(rows: FixtureRow[], todayKey: string): DayGroup[] {
  const byDay = new Map<string, DayGroup>();
  for (const row of rows) {
    const group = byDay.get(row.dayKey) ?? { dayKey: row.dayKey, label: row.dayLabel, rows: [], isToday: row.dayKey === todayKey };
    group.rows.push(row);
    byDay.set(row.dayKey, group);
  }
  const days = [...byDay.values()].sort((a, b) => a.dayKey.localeCompare(b.dayKey));
  for (const day of days) day.rows.sort((a, b) => a.kickoff.localeCompare(b.kickoff) || a.match - b.match);
  return days;
}

function openGroupDayKey(days: DayGroup[], todayKey: string): string | null {
  const today = days.find((d) => d.dayKey === todayKey && d.rows.length > 0);
  if (today) return today.dayKey;
  const future = days.find((d) => d.dayKey >= todayKey && d.rows.length > 0);
  if (future) return future.dayKey;
  return days.length > 0 ? days[days.length - 1].dayKey : null;
}

export function buildFixtures(input: {
  matches: MatchProbs[];
  slots: Slot[];
  draws: MatchWdlDraws | null;
  results: PlayedResultRow[];
  live: LiveState | null;
  teamNames: Record<string, string>;
  nowIso: string;
}): { sections: StageSection[]; openGroupDay: string | null; openStage: string | null } {
  const liveByMatch = new Map<number, LiveFixture>();
  // A stale poll cannot be trusted to a live minute, so live rows fall back to the pre-game shape.
  const fresh = liveIsFresh(input.live, Date.parse(input.nowIso));
  for (const fixture of fresh ? (input.live?.fixtures ?? []) : []) {
    if (fixture.match !== null && fixture.status === "live") liveByMatch.set(fixture.match, fixture);
  }
  const resultByMatch = new Map(input.results.map((r) => [r.match, r]));
  const slotByMatch = new Map(input.slots.map((s) => [s.match, s]));
  const todayKey = dayKey(input.nowIso);

  const byStage = new Map<string, FixtureRow[]>();
  for (const match of input.matches) {
    const row = buildRow(
      match,
      liveByMatch.get(match.match) ?? null,
      resultByMatch.get(match.match) ?? null,
      slotByMatch.get(match.match) ?? null,
      input.draws,
      input.teamNames,
    );
    (byStage.get(match.stage) ?? byStage.set(match.stage, []).get(match.stage)!).push(row);
  }

  const sections: StageSection[] = [];
  let openGroupDay: string | null = null;
  for (const key of STAGE_ORDER) {
    const rows = byStage.get(key);
    if (!rows || rows.length === 0) continue;
    if (key === "group") {
      const days = groupDays(rows, todayKey);
      openGroupDay = openGroupDayKey(days, todayKey);
      sections.push({ key, label: STAGE_LABEL[key], layout: "days", days, rows: [] });
    } else {
      rows.sort((a, b) => a.kickoff.localeCompare(b.kickoff) || a.match - b.match);
      sections.push({ key, label: STAGE_LABEL[key], layout: "flat", days: [], rows });
    }
  }
  return { sections, openGroupDay, openStage: openStageKey(sections) };
}

// The live stage if any game is in play, else the earliest stage with an unplayed
// fixture, else the last stage; so the default-open section is the one in focus now.
function openStageKey(sections: StageSection[]): string | null {
  const allRows = (s: StageSection) => (s.layout === "days" ? s.days.flatMap((d) => d.rows) : s.rows);
  const live = sections.find((s) => allRows(s).some((r) => r.status === "live"));
  if (live) return live.key;
  const pending = sections.find((s) => allRows(s).some((r) => r.status !== "completed"));
  if (pending) return pending.key;
  return sections.length > 0 ? sections[sections.length - 1].key : null;
}
