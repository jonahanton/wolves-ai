import { REACH_STAGES } from "@/lib/reach-stages";
import type { Snapshot } from "@/lib/snapshot";

export interface OddsRow {
  teamId: string;
  name: string;
  isFocus: boolean;
  reach: Record<string, number>;
  championProb: number;
}

export interface OddsView {
  rows: OddsRow[];
  hasReachData: boolean;
}

export function buildOddsView(snapshot: Snapshot, names: Map<string, string>): OddsView {
  const rows = snapshot.teams
    .map((team) => ({
      teamId: team.team_id,
      name: names.get(team.team_id) ?? team.team_id,
      isFocus: team.team_id === snapshot.focus.team_id,
      reach: Object.fromEntries(REACH_STAGES.map((stage) => [stage.key, team.reach_probs?.[stage.key] ?? 0])),
      championProb: team.champion_prob ?? team.reach_probs?.champion ?? 0,
    }))
    .sort((a, b) => b.championProb - a.championProb || a.name.localeCompare(b.name));
  return { rows, hasReachData: rows.some((row) => row.championProb > 0) };
}
