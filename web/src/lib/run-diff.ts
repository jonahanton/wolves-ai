import type { Snapshot } from "@/lib/snapshot";

export interface TitleMove {
  teamId: string;
  name: string;
  from: number;
  to: number;
  deltaPp: number;
}

export function titleMoves(current: Snapshot, previous: Snapshot, limit: number): TitleMove[] {
  const before = new Map(previous.teams.map((t) => [t.team_id, t.champion_prob ?? 0]));
  return current.teams
    .filter((t) => t.champion_prob !== undefined && before.has(t.team_id))
    .map((t) => ({
      teamId: t.team_id,
      name: t.name,
      from: before.get(t.team_id) ?? 0,
      to: t.champion_prob ?? 0,
      deltaPp: ((t.champion_prob ?? 0) - (before.get(t.team_id) ?? 0)) * 100,
    }))
    .filter((move) => Math.abs(move.deltaPp) >= 0.05)
    .sort((a, b) => Math.abs(b.deltaPp) - Math.abs(a.deltaPp))
    .slice(0, limit);
}
