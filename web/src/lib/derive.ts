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

export interface HeroStatement {
  lead: string;
  focusLine: string;
}

export function deriveHero(snapshot: Snapshot): HeroStatement {
  const leader = titleBoard(snapshot, 1)[0];
  const focusId = snapshot.focus.team_id;
  const focusName = snapshot.teams.find((t) => t.team_id === focusId)?.name ?? focusId;

  const ours = titleProb(snapshot, focusId);
  const market = snapshot.markets?.market_probs?.[focusId] ?? null;
  const gapPp = ours !== null && market !== null ? (ours - market) * 100 : null;

  let focusLine = `${focusName} holding.`;
  if (gapPp !== null && gapPp <= -1.5) focusLine = `${focusName} priced below the market.`;
  else if (gapPp !== null && gapPp >= 1.5) focusLine = `${focusName} backed above the market.`;

  return {
    lead: leader ? `${possessive(leader.name)} to lose.` : "The field is open.",
    focusLine,
  };
}

function possessive(name: string): string {
  return name.endsWith("s") ? `${name}'` : `${name}'s`;
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
