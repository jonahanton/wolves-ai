import { ENGLAND } from "@/lib/schedule";
import type { Snapshot } from "@/lib/snapshot";

export interface GroupTeamRow {
  teamId: string;
  name: string;
  isEngland: boolean;
  expectedPoints: number;
  winGroup: number;
  runnerUp: number;
  thirdQualified: number;
}

export interface GroupView {
  group: string;
  teams: GroupTeamRow[];
}

export function buildGroupsView(snapshot: Snapshot, names: Map<string, string>): GroupView[] {
  return (snapshot.groups ?? [])
    .map((block) => ({
      group: block.group,
      teams: [...block.teams]
        .sort((a, b) => b.expected_points - a.expected_points)
        .map((team) => ({
          teamId: team.team_id,
          name: names.get(team.team_id) ?? team.team_id,
          isEngland: team.team_id === ENGLAND,
          expectedPoints: team.expected_points,
          winGroup: team.finish_probs.win_group ?? 0,
          runnerUp: team.finish_probs.runner_up ?? 0,
          thirdQualified: team.finish_probs.third_qualified ?? 0,
        })),
    }))
    .sort((a, b) => a.group.localeCompare(b.group));
}
