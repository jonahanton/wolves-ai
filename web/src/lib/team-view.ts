import type { GroupTeamStanding, Snapshot, WhatIfFixture } from "@/lib/snapshot";

export const STAGE_LABELS: Record<string, string> = {
  r32: "Last 32",
  r16: "Last 16",
  qf: "Quarter-final",
  sf: "Semi-final",
  final: "The final",
  champion: "Champions",
};

export const STAGE_ORDER = ["r32", "r16", "qf", "sf", "final", "champion"] as const;

export interface StaircaseStep {
  stage: string;
  label: string;
  prob: number;
}

export function staircase(reachProbs: Record<string, number>): StaircaseStep[] {
  return STAGE_ORDER.filter((stage) => reachProbs[stage] !== undefined).map((stage) => ({
    stage,
    label: STAGE_LABELS[stage],
    prob: reachProbs[stage],
  }));
}

export interface StandingRow {
  teamId: string;
  winGroup: number;
  qualified: number;
  expectedPoints: number;
}

export function groupStandings(snapshot: Snapshot, group: string): StandingRow[] {
  const block = (snapshot.groups ?? []).find((g) => g.group === group);
  if (!block) return [];
  return block.teams
    .map((team: GroupTeamStanding) => ({
      teamId: team.team_id,
      winGroup: team.finish_probs.win_group ?? 0,
      qualified:
        (team.finish_probs.win_group ?? 0) +
        (team.finish_probs.runner_up ?? 0) +
        (team.finish_probs.third_qualified ?? 0),
      expectedPoints: team.expected_points,
    }))
    .sort((a, b) => b.qualified - a.qualified);
}

export interface WhatIfDelta {
  outcome: string;
  prob: number;
  winGroupDeltaPp: number;
  qualifiedDeltaPp: number;
}

// Outcomes carry group-finish keys only; deltas are v the weighted baseline.
export function whatIfDeltas(fixture: WhatIfFixture): WhatIfDelta[] {
  const qualified = (probs: Record<string, number>) =>
    (probs.win_group ?? 0) + (probs.runner_up ?? 0) + (probs.third_qualified ?? 0);
  const groupBase = fixture.outcomes.reduce((sum, o) => sum + o.prob * (o.finish_probs.win_group ?? 0), 0);
  const qualifiedBase = fixture.outcomes.reduce((sum, o) => sum + o.prob * qualified(o.finish_probs), 0);
  return fixture.outcomes.map((outcome) => ({
    outcome: outcome.outcome,
    prob: outcome.prob,
    winGroupDeltaPp: ((outcome.finish_probs.win_group ?? 0) - groupBase) * 100,
    qualifiedDeltaPp: (qualified(outcome.finish_probs) - qualifiedBase) * 100,
  }));
}
