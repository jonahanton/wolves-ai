import type { MatchProbs, Snapshot } from "@/lib/snapshot";

export interface BoardRow {
  teamId: string;
  name: string;
  prob: number;
  market: number | null;
  blend: number | null;
  lo: number | null;
  hi: number | null;
}

// Agents publish unblended: teams[].champion_prob is the published number.
export function titleProb(snapshot: Snapshot, teamId: string): number | null {
  return snapshot.teams.find((t) => t.team_id === teamId)?.champion_prob ?? null;
}

export function titleBoard(snapshot: Snapshot, limit: number): BoardRow[] {
  const intervals = new Map((snapshot.intervals ?? []).map((i) => [i.team_id, i]));
  return snapshot.teams
    .filter((t) => t.champion_prob !== undefined)
    .sort((a, b) => (b.champion_prob ?? 0) - (a.champion_prob ?? 0))
    .slice(0, limit)
    .map((team) => ({
      teamId: team.team_id,
      name: team.name,
      prob: team.champion_prob ?? 0,
      market: snapshot.markets?.market_probs?.[team.team_id] ?? null,
      blend: snapshot.markets?.blend_probs?.[team.team_id] ?? null,
      lo: intervals.get(team.team_id)?.lo ?? null,
      hi: intervals.get(team.team_id)?.hi ?? null,
    }));
}

export interface TitleRank {
  teamId: string;
  name: string;
  prob: number;
  rank: number;
}

export interface HeroStatement {
  leader: TitleRank | null;
  focus: TitleRank | null;
}

export function deriveHero(snapshot: Snapshot): HeroStatement {
  const ranked = snapshot.teams
    .filter((t) => t.champion_prob !== undefined)
    .sort((a, b) => (b.champion_prob ?? 0) - (a.champion_prob ?? 0))
    .map((team, index) => ({
      teamId: team.team_id,
      name: team.name,
      prob: team.champion_prob ?? 0,
      rank: index + 1,
    }));
  return {
    leader: ranked[0] ?? null,
    focus: ranked.find((team) => team.teamId === snapshot.focus.team_id) ?? null,
  };
}

// Older runs predate the plain-English headline; fall back to the story's opening.
export function agentReasoning(snapshot: Snapshot): string | null {
  const narrative = snapshot.agent?.narrative;
  if (!narrative) return null;
  if (narrative.headline?.trim()) return narrative.headline.trim();
  const opening = narrative.focus_story.split(/(?<=\.)\s+/).slice(0, 2).join(" ").trim();
  return opening || null;
}

export function shortCity(city: string): string {
  return city.split("/")[0].trim();
}

export function nextFixtureFor(snapshot: Snapshot, teamId: string, now: Date): MatchProbs | null {
  const future = (snapshot.matches ?? [])
    .filter((m) => (m.home_id === teamId || m.away_id === teamId) && new Date(m.date) >= now)
    .sort((a, b) => a.date.localeCompare(b.date));
  return future[0] ?? null;
}

export function fixturesFor(snapshot: Snapshot, teamId: string): MatchProbs[] {
  return (snapshot.matches ?? [])
    .filter((m) => m.home_id === teamId || m.away_id === teamId)
    .sort((a, b) => a.date.localeCompare(b.date));
}

export function matchesOn(snapshot: Snapshot, day: string): MatchProbs[] {
  return (snapshot.matches ?? []).filter((m) => m.date.startsWith(day)).sort((a, b) => a.date.localeCompare(b.date));
}
