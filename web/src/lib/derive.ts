import type { TeamInfo } from "@/lib/snapshot";

export interface BoardRow {
  teamId: string;
  name: string;
  prob: number;
}

export function titleBoard(snapshot: { teams: TeamInfo[] }, limit: number): BoardRow[] {
  return snapshot.teams
    .filter((t) => t.champion_prob !== undefined)
    .sort((a, b) => (b.champion_prob ?? 0) - (a.champion_prob ?? 0))
    .slice(0, limit)
    .map((team) => ({ teamId: team.team_id, name: team.name, prob: team.champion_prob ?? 0 }));
}
