import type { Impact, ImpactResult, ImpactStage } from "@/lib/impact";
import type { LiveFixture, LiveState } from "@/lib/live";
import { liveIsFresh } from "@/lib/live";
import { teamCode } from "@/lib/team-colours";

export type DigestTone = "live" | "results" | "quiet" | "stale";

export type DigestToken =
  | { kind: "text"; text: string }
  | { kind: "team"; teamId: string | null; code: string }
  | { kind: "shimmer"; text: string };

export interface CompactLiveDigest {
  tone: DigestTone;
  tokens: DigestToken[];
}

export interface ImpactMover {
  teamId: string;
  code: string;
  deltaPp: number;
  resultsPp: number;
  ingamePp: number;
  agentPct: number;
  estimatedPct: number;
  floorPp: number;
}

export type TimelineEntry =
  | {
      kind: "result";
      time: string;
      homeId: string | null;
      awayId: string | null;
      homeCode: string;
      awayCode: string;
      homeGoals: number;
      awayGoals: number;
      corrected: boolean;
    }
  | {
      kind: "live";
      time: string;
      homeId: string | null;
      awayId: string | null;
      homeCode: string;
      awayCode: string;
      homeGoals: number | null;
      awayGoals: number | null;
      minute: number | null;
    };

function liveScoreText(fixture: LiveFixture, names: Map<string, string>): string {
  const home = codeFor(fixture.homeId, fixture.homeName, names);
  const away = codeFor(fixture.awayId, fixture.awayName, names);
  const minute = fixture.minute === null || fixture.minute === undefined ? "" : ` ${fixture.minute}'`;
  return `${home} ${scoreline(fixture.homeGoals, fixture.awayGoals)} ${away}${minute}`;
}

export function compactLiveDigest(live: LiveState | null, impact: Impact | null): CompactLiveDigest {
  const names = nameLookup(live);
  const liveFixtures = (live?.fixtures ?? []).filter((fixture) => fixture.status === "live");
  const count = impact?.resultsSinceAgent.length ?? 0;
  const at = impact ? ` (which ran @ ${timeLabel(impact.agentCreatedAt)} ET` : " (";

  if (liveFixtures.length > 0) {
    const tokens: DigestToken[] =
      liveFixtures.length > 1
        ? [{ kind: "shimmer", text: `${liveFixtures.length} live games` }]
        : [{ kind: "shimmer", text: liveScoreText(liveFixtures[0], names) }];
    if (count > 0) {
      tokens.push({ kind: "text", text: ` + ${count} since last forecast` });
    }
    return { tone: "live", tokens };
  }

  if (count > 0) {
    const recent = mostRecentResult(impact);
    const tokens: DigestToken[] = [{ kind: "text", text: `${count} result${count === 1 ? "" : "s"} since last forecast${at}` }];
    if (recent) {
      tokens.push({ kind: "text", text: ", most recent " });
      tokens.push(teamToken(recent.homeId, names));
      tokens.push({ kind: "text", text: ` ${recent.homeGoals}-${recent.awayGoals} ` });
      tokens.push(teamToken(recent.awayId, names));
    }
    tokens.push({ kind: "text", text: ")" });
    return { tone: "results", tokens };
  }

  if (live && !liveIsFresh(live)) {
    return { tone: "stale", tokens: [{ kind: "text", text: `Live scores last checked ${timeLabel(live.fetchedAt)} ET` }] };
  }

  const next = nextScheduledFixture(live);
  const tokens: DigestToken[] = [{ kind: "text", text: "No games since last forecast" }];
  const parts: DigestToken[] = [];
  if (impact) parts.push({ kind: "text", text: `last forecast ${timeLabel(impact.agentCreatedAt)} ET` });
  if (next) {
    if (parts.length > 0) parts.push({ kind: "text", text: ", " });
    parts.push({ kind: "text", text: "next game " });
    parts.push(teamToken(next.homeId, names));
    parts.push({ kind: "text", text: " v " });
    parts.push(teamToken(next.awayId, names));
    parts.push({ kind: "text", text: ` ${timeLabel(next.kickoff)} ET` });
  }
  if (parts.length > 0) {
    tokens.push({ kind: "text", text: " (" }, ...parts, { kind: "text", text: ")" });
  }
  return { tone: "quiet", tokens };
}

function nextScheduledFixture(live: LiveState | null): LiveFixture | null {
  const scheduled = (live?.fixtures ?? [])
    .filter((fixture) => fixture.status === "scheduled")
    .sort((a, b) => Date.parse(a.kickoff) - Date.parse(b.kickoff));
  return scheduled[0] ?? null;
}

export function panelTimeline(live: LiveState | null, impact: Impact | null): TimelineEntry[] {
  const names = nameLookup(live);
  const kickoffs = new Map<number, string>();
  for (const fixture of live?.fixtures ?? []) {
    if (fixture.match !== null) kickoffs.set(fixture.match, fixture.kickoff);
  }
  const results = (impact?.resultsSinceAgent ?? []).map((result) => {
    const kickoff = kickoffs.get(result.match);
    return {
      sort: kickoff ? Date.parse(kickoff) : result.match,
      entry: {
        kind: "result" as const,
        time: kickoff ? dateTimeLabel(kickoff) : "",
        homeId: result.homeId,
        awayId: result.awayId,
        homeCode: codeFor(result.homeId, null, names),
        awayCode: codeFor(result.awayId, null, names),
        homeGoals: result.homeGoals,
        awayGoals: result.awayGoals,
        corrected: result.kind === "corrected",
      },
    };
  });
  const liveEntries = (live?.fixtures ?? [])
    .filter((fixture) => fixture.status === "live")
    .map((fixture) => ({
      sort: Number.MAX_SAFE_INTEGER,
      entry: {
        kind: "live" as const,
        time: dateTimeLabel(fixture.kickoff),
        homeId: fixture.homeId ?? null,
        awayId: fixture.awayId ?? null,
        homeCode: codeFor(fixture.homeId, fixture.homeName, names),
        awayCode: codeFor(fixture.awayId, fixture.awayName, names),
        homeGoals: fixture.homeGoals ?? null,
        awayGoals: fixture.awayGoals ?? null,
        minute: fixture.minute ?? null,
      },
    }));
  return [...results, ...liveEntries].sort((a, b) => a.sort - b.sort).map((wrapped) => wrapped.entry);
}

function nameLookup(live: LiveState | null): Map<string, string> {
  const names = new Map<string, string>();
  for (const fixture of live?.fixtures ?? []) {
    if (fixture.homeId) names.set(fixture.homeId, fixture.homeName);
    if (fixture.awayId) names.set(fixture.awayId, fixture.awayName);
  }
  return names;
}

function codeFor(teamId: string | null | undefined, name: string | null | undefined, names: Map<string, string>): string {
  const resolved = name ?? (teamId ? names.get(teamId) : null);
  if (resolved) return teamCode(resolved);
  if (!teamId) return "TBC";
  return teamCode(teamId.replace(/[-_]/g, " "));
}

function teamToken(teamId: string | null | undefined, names: Map<string, string>): DigestToken {
  return { kind: "team", teamId: teamId ?? null, code: codeFor(teamId, null, names) };
}

function mostRecentResult(impact: Impact | null): ImpactResult | null {
  const results = impact?.resultsSinceAgent ?? [];
  return results.length > 0 ? results[results.length - 1] : null;
}

export function topTitleMovers(impact: Impact | null, limit = 3): ImpactMover[] {
  if (!impact) return [];
  return Object.entries(impact.teams)
    .map(([teamId, team]) => mover(teamId, team.title))
    .filter((row) => Math.abs(row.deltaPp) >= row.floorPp)
    .sort((a, b) => Math.abs(b.deltaPp) - Math.abs(a.deltaPp))
    .slice(0, limit);
}

export function resultLabel(result: ImpactResult): string {
  return `${teamLabel(result.homeId)} ${result.homeGoals}-${result.awayGoals} ${teamLabel(result.awayId)}`;
}

function mover(teamId: string, stage: ImpactStage): ImpactMover {
  return {
    teamId,
    code: teamCode(teamId.replace(/[-_]/g, " ")),
    deltaPp: stage.fromResultsPp + stage.fromIngamePp,
    resultsPp: stage.fromResultsPp,
    ingamePp: stage.fromIngamePp,
    agentPct: stage.agent * 100,
    estimatedPct: stage.estimated * 100,
    floorPp: stage.displayFloorPp,
  };
}

function scoreline(home: number | null | undefined, away: number | null | undefined): string {
  return home === null || home === undefined || away === null || away === undefined ? "v" : `${home}-${away}`;
}

function teamLabel(teamId: string | null): string {
  if (!teamId) return "TBC";
  return teamId
    .split(/[-_]/)
    .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join(" ");
}

function timeLabel(value: string): string {
  return new Date(value).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/New_York",
  });
}

export function dateTimeLabel(value: string): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/New_York",
  }).formatToParts(new Date(value));
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return `${get("day")}/${get("month")} ${get("hour")}:${get("minute")}`;
}
