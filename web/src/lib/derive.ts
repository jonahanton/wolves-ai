import type { MatchProbs, Snapshot } from "@/lib/snapshot";

export interface BoardRow {
  teamId: string;
  name: string;
  prob: number;
  model: number | null;
  market: number | null;
  lo: number | null;
  hi: number | null;
}

export function titleProb(snapshot: Snapshot, teamId: string): number | null {
  const blend = snapshot.markets?.blend_probs?.[teamId];
  if (blend !== undefined) return blend;
  return snapshot.teams.find((t) => t.team_id === teamId)?.champion_prob ?? null;
}

export function titleBoard(snapshot: Snapshot, limit: number): BoardRow[] {
  const names = new Map(snapshot.teams.map((t) => [t.team_id, t.name]));
  const intervals = new Map((snapshot.intervals ?? []).map((i) => [i.team_id, i]));
  const blend = snapshot.markets?.blend_probs;
  const ranked: (readonly [string, number])[] = blend
    ? Object.entries(blend).sort(([, a], [, b]) => b - a)
    : snapshot.teams
        .filter((t) => t.champion_prob !== undefined)
        .sort((a, b) => (b.champion_prob ?? 0) - (a.champion_prob ?? 0))
        .map((t) => [t.team_id, t.champion_prob ?? 0] as const);

  return ranked.slice(0, limit).map(([teamId, prob]) => ({
    teamId,
    name: names.get(teamId) ?? teamId,
    prob,
    model: snapshot.markets?.model_probs?.[teamId] ?? null,
    market: snapshot.markets?.market_probs?.[teamId] ?? null,
    lo: intervals.get(teamId)?.lo ?? null,
    hi: intervals.get(teamId)?.hi ?? null,
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
