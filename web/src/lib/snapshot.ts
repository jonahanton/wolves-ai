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

export interface RoundOpponents {
  round: string;
  match: number;
  city: string;
  date: string;
  reach_prob: number;
  opponents: Candidate[];
}

export interface FocusTeamPath {
  finish: Finish;
  prob: number;
  r32_match: number;
  city: string;
  date: string;
  opponents: Candidate[];
  onward?: RoundOpponents[];
}

export interface ModalStep {
  round: string;
  match: number;
  city: string;
  date: string;
  opponent_id: string;
  opponent_prob: number;
}

export interface CityProb {
  city: string;
  prob: number;
}

export interface LockDate {
  date: string;
  prob_locked: number;
  locked_city_probs: Record<string, number>;
}

export interface WhatIfOutcome {
  outcome: string;
  prob: number;
  finish_probs: Record<string, number>;
  r32_city_probs: Record<string, number>;
}

export interface WhatIfFixture {
  match: number;
  date: string;
  city: string;
  opponent_id: string;
  outcomes: WhatIfOutcome[];
}

export interface FocusTeamBlock {
  team_id: string;
  group: string;
  finish_probs: Record<string, number>;
  reach_probs: Record<string, number>;
  paths: FocusTeamPath[];
  modal_path?: ModalStep[];
  city_probs?: Record<string, CityProb[]>;
  lock_dates?: LockDate[];
  what_if?: WhatIfFixture[];
}

export interface RunMeta {
  run_id: string;
  created_at: string;
  as_of?: string;
  n_sims: number;
  engine_version: string;
  kind: string;
}

export interface TeamInfo {
  team_id: string;
  name: string;
  group: string;
  elo: number;
  rating?: number;
  value_eur_m?: number | null;
  champion_prob?: number;
  reach_probs?: Record<string, number>;
}

export interface GroupTeamStanding {
  team_id: string;
  finish_probs: Record<string, number>;
  expected_points: number;
}

export interface GroupBlock {
  group: string;
  teams: GroupTeamStanding[];
}

export interface MatchProbs {
  match: number;
  stage: string;
  date: string;
  city: string;
  home_id: string;
  away_id: string;
  p_home: number;
  p_away: number;
  p_draw?: number | null;
  p_decided_90?: number | null;
  p_pairing?: number | null;
  modal_score?: string | null;
}

export interface NarrativeBlock {
  headline?: string;
  focus_story: string;
  slot_rationales: Record<string, string>;
  travel_memo: string;
}

export interface LedgerEntryOut {
  id: string;
  claim: string;
  source_url: string;
  title: string | null;
  status: string;
  mechanism: string;
  proposed_delta: number;
  expiry: string | null;
  team_id: string | null;
  relevance: number | null;
  source_tier: number | null;
  retrieved_at: string | null;
  retrieval_id: string | null;
  created_at: string;
}

export interface ScenarioWeightOut {
  name: string;
  weight: number;
  scenario_id: string | null;
  ledger_ids: string[];
  rationale?: string;
}

export interface WorldOut {
  name: string;
  weight: number;
  perturbations: Record<string, unknown>[];
  title_probs?: Record<string, number>;
}

export interface QuantFindingOut {
  node_id: string;
  summary: string;
  headline_value: number | null;
  findings: string[];
}

export interface GovernorOut {
  scale: number;
  effective_d: number;
}

export interface AttributionOut {
  bracket_pp: Record<string, number>;
  refit_pp: Record<string, number>;
  residual_pp: Record<string, number>;
}

export interface CalibrationSummary {
  matches_scored: number;
  brier: Record<string, number>;
  log_loss: Record<string, number>;
  adjustment_pnl: number | null;
  governor_scale: number;
}

export interface AgentBlock {
  narrative: NarrativeBlock;
  artifact_id: string;
  ledger_entries: LedgerEntryOut[];
  scenario_weights: ScenarioWeightOut[];
  worlds: WorldOut[];
  quant_findings?: QuantFindingOut[];
  escalations: string[];
  market_justification: string;
  change_justification: string;
  inconsistency_note: string;
  attribution: AttributionOut | null;
  governor: GovernorOut | null;
  calibration: CalibrationSummary | null;
}

export interface ChampionBlock {
  id: string;
  version: string;
  dataset_id: string;
  half_life_days?: number | null;
  blend_weight?: number;
  results_overlaid?: number;
}

export interface TeamInterval {
  team_id: string;
  lo: number;
  hi: number;
}

export interface MarketsBlock {
  model_probs?: Record<string, number>;
  market_probs?: Record<string, number>;
  blend_probs?: Record<string, number>;
  model_weight?: number;
}

export interface Snapshot {
  schema_version: number;
  run: RunMeta;
  focus: FocusTeamBlock;
  slots: Slot[];
  teams: TeamInfo[];
  groups?: GroupBlock[];
  matches?: MatchProbs[];
  agent?: AgentBlock | null;
  champion?: ChampionBlock | null;
  intervals?: TeamInterval[];
  markets?: MarketsBlock | null;
}

export function teamNames(snapshot: Snapshot): Map<string, string> {
  return new Map(snapshot.teams.map((t) => [t.team_id, t.name]));
}
