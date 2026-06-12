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

// Group standings carry the five-way finish keys, not the focus Finish union.
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
  championDeltaPp: number;
  winGroupDeltaPp: number;
}

// Deltas are versus the probability-weighted baseline across the fixture's
// outcomes, so the three rows sum to zero by construction.
export function whatIfDeltas(fixture: WhatIfFixture): WhatIfDelta[] {
  const baseline = (key: string) =>
    fixture.outcomes.reduce((sum, outcome) => sum + outcome.prob * (outcome.finish_probs[key] ?? 0), 0);
  const champBase = baseline("champion");
  const groupBase = baseline("win_group");
  return fixture.outcomes.map((outcome) => ({
    outcome: outcome.outcome,
    prob: outcome.prob,
    championDeltaPp: ((outcome.finish_probs.champion ?? 0) - champBase) * 100,
    winGroupDeltaPp: ((outcome.finish_probs.win_group ?? 0) - groupBase) * 100,
  }));
}
