import { gridX, samplesToBars, samplesToCurve, type WdlShape } from "@/lib/distribution";
import type { LiveWdlDraws, WdlKeyframe } from "@/lib/impact";
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
  dayKey: string;
  dayLabel: string;
  status: FixtureStatus;
  knockout: boolean;
  homeId: string | null;
  awayId: string | null;
  homeCode: string;
  awayCode: string;
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
// A knockout pairing the sim reaches in (essentially) every world is mathematically
// locked: the bracket maths leaves no other matchup, so we name the teams rather than
// the bracket slots. The tiny slack absorbs Monte Carlo noise on tie-break edges.
const PAIRING_LOCKED = 0.999;
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
  return wdlShape(cell.p_home, cell.p_draw, cell.p_away);
}

export function liveWdlShape(draws: LiveWdlDraws | null): WdlShape | null {
  if (!draws || draws.pHome.length === 0) return null;
  return wdlShape(draws.pHome, draws.pDraw, draws.pAway);
}

export interface WdlFrame {
  minute: number;
  homeGoals: number;
  awayGoals: number;
  shape: WdlShape;
}

// Goal-stepped keyframes when the backend supplies them; otherwise a single live
// frame from the current spread, so the curve survives a backend/frontend skew.
export function liveWdlFrames(
  fixture: { wdlKeyframes: WdlKeyframe[]; wdlDraws: LiveWdlDraws | null } | null,
  minute: number | null,
  homeGoals: number | null,
  awayGoals: number | null,
): WdlFrame[] {
  const keyframes = (fixture?.wdlKeyframes ?? []).filter((k) => k.wdl.pHome.length > 0);
  if (keyframes.length > 0) {
    return keyframes.map((k) => ({
      minute: k.minute,
      homeGoals: k.homeGoals,
      awayGoals: k.awayGoals,
      shape: wdlShape(k.wdl.pHome, k.wdl.pDraw, k.wdl.pAway),
    }));
  }
  const live = liveWdlShape(fixture?.wdlDraws ?? null);
  if (!live) return [];
  return [
    {
      minute: minute ?? 0,
      homeGoals: homeGoals ?? 0,
      awayGoals: awayGoals ?? 0,
      shape: live,
    },
  ];
}

function wdlShape(home: number[], draw: number[], away: number[]): WdlShape {
  return {
    home: { curve: samplesToCurve(home, GRID), bars: samplesToBars(home), samples: home.length },
    draw: { curve: samplesToCurve(draw, GRID), bars: samplesToBars(draw), samples: draw.length },
    away: { curve: samplesToCurve(away, GRID), bars: samplesToBars(away), samples: away.length },
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
  // A locked pairing is set even before kickoff, so it reads as a normal upcoming fixture.
  const locked = knockout && (match.p_pairing ?? 0) >= PAIRING_LOCKED;
  // A knockout tie that is neither played, live nor locked is genuinely undetermined: never imply a pairing.
  const tbc = knockout && !resolved && !locked;
  const homeId = tbc ? null : (live?.homeId ?? match.home_id ?? null);
  const awayId = tbc ? null : (live?.awayId ?? match.away_id ?? null);

  const probs =
    status === "live" && live?.forecast
      ? { home: live.forecast.pHome, draw: live.forecast.pDraw ?? 0, away: live.forecast.pAway }
      : { home: match.p_home, draw: match.p_draw ?? 0, away: match.p_away };
  // Live rows keep the pre-match spread as the kickoff frame the live curve animates from.
  const hasSpread = !tbc && Boolean(draws?.matches[String(match.match)]);

  return {
    match: match.match,
    stage: match.stage,
    kickoff: match.date,
    dayKey: dayKey(match.date),
    dayLabel: dayLabel(match.date),
    status,
    knockout,
    homeId,
    awayId,
    homeCode: codeOf(homeId, names),
    awayCode: codeOf(awayId, names),
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

// A played match that has dropped out of the forward-looking forecast feed: render
// it as its result alone, with no bar, shape or expand.
function resultRow(result: PlayedResultRow, names: Record<string, string>): FixtureRow {
  return {
    match: result.match,
    stage: result.stage,
    kickoff: result.date,
    dayKey: dayKey(result.date),
    dayLabel: dayLabel(result.date),
    status: "completed",
    knockout: result.stage !== "group",
    homeId: result.homeId,
    awayId: result.awayId,
    homeCode: codeOf(result.homeId, names),
    awayCode: codeOf(result.awayId, names),
    homeGoals: result.homeGoals,
    awayGoals: result.awayGoals,
    minute: null,
    bar: null,
    shape: null,
    colours: resolveWdlColours(result.homeId, result.awayId),
    slot: null,
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

function buildSections(byStage: Map<string, FixtureRow[]>, todayKey: string): { sections: StageSection[]; openGroupDay: string | null } {
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
  return { sections, openGroupDay };
}

export interface FixturesView {
  sections: StageSection[];
  pastSections: StageSection[];
  openGroupDay: string | null;
  openStage: string | null;
  pastOpenGroupDay: string | null;
  pastOpenStage: string | null;
}

export function buildFixtures(input: {
  matches: MatchProbs[];
  slots: Slot[];
  draws: MatchWdlDraws | null;
  results: PlayedResultRow[];
  live: LiveState | null;
  teamNames: Record<string, string>;
  nowIso: string;
}): FixturesView {
  const liveByMatch = new Map<number, LiveFixture>();
  // A stale poll cannot be trusted to a live minute, so live rows fall back to the pre-game shape.
  const fresh = liveIsFresh(input.live, Date.parse(input.nowIso));
  for (const fixture of fresh ? (input.live?.fixtures ?? []) : []) {
    if (fixture.match !== null && fixture.status === "live") liveByMatch.set(fixture.match, fixture);
  }
  const resultByMatch = new Map(input.results.map((r) => [r.match, r]));
  const slotByMatch = new Map(input.slots.map((s) => [s.match, s]));
  const todayKey = dayKey(input.nowIso);

  const presentByStage = new Map<string, FixtureRow[]>();
  const pastByStage = new Map<string, FixtureRow[]>();
  // A finished match on an earlier day is history; everything today or later stays in focus.
  const place = (row: FixtureRow) => {
    const target = row.status === "completed" && row.dayKey < todayKey ? pastByStage : presentByStage;
    (target.get(row.stage) ?? target.set(row.stage, []).get(row.stage)!).push(row);
  };
  const forecastMatches = new Set(input.matches.map((m) => m.match));
  for (const match of input.matches) {
    place(
      buildRow(
        match,
        liveByMatch.get(match.match) ?? null,
        resultByMatch.get(match.match) ?? null,
        slotByMatch.get(match.match) ?? null,
        input.draws,
        input.teamNames,
      ),
    );
  }
  // Played matches drop out of the forecast feed once settled; surface their results too.
  for (const result of input.results) {
    if (!forecastMatches.has(result.match)) place(resultRow(result, input.teamNames));
  }

  const present = buildSections(presentByStage, todayKey);
  const past = buildSections(pastByStage, todayKey);
  return {
    sections: present.sections,
    pastSections: past.sections,
    openGroupDay: present.openGroupDay,
    openStage: openStageKey(present.sections),
    pastOpenGroupDay: past.openGroupDay,
    pastOpenStage: openStageKey(past.sections),
  };
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
