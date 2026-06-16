import type { Impact, ImpactResult, ImpactStage, TeamImpact } from "@/lib/impact";
import type { LiveState } from "@/lib/live";
import { liveIsFresh } from "@/lib/live";

export interface CompactLiveDigest {
  label: string;
  tone: "live" | "results" | "quiet" | "stale";
}

export interface ImpactMover {
  teamId: string;
  deltaPp: number;
  resultsPp: number;
  ingamePp: number;
}

export function compactLiveDigest(live: LiveState | null, impact: Impact | null): CompactLiveDigest {
  const liveFixtures = (live?.fixtures ?? []).filter((fixture) => fixture.status === "live");
  const featured = liveFixtures[0];
  if (featured) {
    const minute = featured.minute === null || featured.minute === undefined ? "" : `${featured.minute}' `;
    const score = scoreline(featured.homeGoals, featured.awayGoals);
    const prefix = liveFixtures.length > 1 ? `LIVE ${liveFixtures.length} matches ` : `LIVE ${minute}`;
    return { label: `${prefix}${featured.homeName} ${score} ${featured.awayName}`.replace(/\s+/g, " "), tone: "live" };
  }
  const count = impact?.resultsSinceAgent.length ?? 0;
  if (count > 0) {
    return { label: `${count} result${count === 1 ? "" : "s"} since the full forecast`, tone: "results" };
  }
  if (live && !liveIsFresh(live)) {
    return { label: `Live scores last checked ${timeLabel(live.fetchedAt)}`, tone: "stale" };
  }
  return { label: "No matches since the full forecast", tone: "quiet" };
}

export function topTitleMovers(impact: Impact | null, limit = 3): ImpactMover[] {
  if (!impact) return [];
  return Object.entries(impact.teams)
    .map(([teamId, team]) => mover(teamId, team.title))
    .filter((row) => Math.abs(row.deltaPp) >= Math.abs(impact.teams[row.teamId].title.displayFloorPp))
    .sort((a, b) => Math.abs(b.deltaPp) - Math.abs(a.deltaPp))
    .slice(0, limit);
}

export function stageDelta(stage: ImpactStage | undefined): number | null {
  if (!stage) return null;
  const delta = stage.fromResultsPp + stage.fromIngamePp;
  return Math.abs(delta) >= stage.displayFloorPp ? delta : null;
}

export function resultLabel(result: ImpactResult): string {
  return `${teamLabel(result.homeId)} ${result.homeGoals}-${result.awayGoals} ${teamLabel(result.awayId)}`;
}

interface FixtureLabelInput {
  homeName: string;
  awayName: string;
  homeGoals?: number | null;
  awayGoals?: number | null;
}

export function fixtureLabel(fixture: FixtureLabelInput): string {
  return `${fixture.homeName} ${scoreline(fixture.homeGoals, fixture.awayGoals)} ${fixture.awayName}`;
}

export function teamDisplayName(teamId: string): string {
  return teamLabel(teamId);
}

export function teamImpactDelta(team: TeamImpact | undefined, metric: string): number | null {
  if (!team) return null;
  if (metric === "champion") return stageDelta(team.title);
  return stageDelta(team.reach[metric as keyof TeamImpact["reach"]]);
}

function mover(teamId: string, stage: ImpactStage): ImpactMover {
  return {
    teamId,
    deltaPp: stage.fromResultsPp + stage.fromIngamePp,
    resultsPp: stage.fromResultsPp,
    ingamePp: stage.fromIngamePp,
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
