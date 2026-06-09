export interface Candidate {
  team_id: string;
  prob: number;
}

export interface SlotSide {
  label: string;
  candidates: Candidate[];
}

export interface Slot {
  match: number;
  stage: string;
  date: string;
  city: string;
  home: SlotSide;
  away: SlotSide;
}

export type Finish = "win_group" | "runner_up" | "third";

export interface EnglandPath {
  finish: Finish;
  prob: number;
  r32_match: number;
  city: string;
  date: string;
  opponents: Candidate[];
}

export interface EnglandBlock {
  team_id: string;
  group: string;
  finish_probs: Record<string, number>;
  reach_probs: Record<string, number>;
  paths: EnglandPath[];
}

export interface RunMeta {
  run_id: string;
  created_at: string;
  n_sims: number;
  engine_version: string;
  kind: string;
}

export interface TeamInfo {
  team_id: string;
  name: string;
  group: string;
  elo: number;
}

export interface Snapshot {
  schema_version: number;
  run: RunMeta;
  england: EnglandBlock;
  slots: Slot[];
  teams: TeamInfo[];
}

export function teamNames(snapshot: Snapshot): Map<string, string> {
  return new Map(snapshot.teams.map((t) => [t.team_id, t.name]));
}
