import { cache } from "react";
import { type ApiResult, backendGet } from "@/lib/api";

export type ImpactLiveMode = "score_hold" | "in_match_distribution" | "none";
export type ImpactResultKind = "new" | "corrected";
export type ReachStage = "r32" | "r16" | "qf" | "sf" | "final";
export type ExitStage = "groups" | ReachStage | "champion";

export interface ImpactStage {
  agent: number;
  afterResults: number;
  estimated: number;
  fromResultsPp: number;
  fromIngamePp: number;
  displayFloorPp: number;
}

export interface TeamImpact {
  title: ImpactStage;
  reach: Record<ReachStage, ImpactStage>;
  exit: Record<ExitStage, ImpactStage>;
}

export interface ImpactFixture {
  match: number | null;
  homeId: string | null;
  awayId: string | null;
  homeName: string;
  awayName: string;
  homeGoals: number | null;
  awayGoals: number | null;
  minute: number | null;
  status: string;
  pHome: number | null;
  pDraw: number | null;
  pAway: number | null;
  homeShotsOn: number | null;
  awayShotsOn: number | null;
  homeTotalShots: number | null;
  awayTotalShots: number | null;
  homePossession: number | null;
  awayPossession: number | null;
  wdlDraws: LiveWdlDraws | null;
  wdlKeyframes: WdlKeyframe[];
  statTrack: StatPoint[];
}

export interface LiveWdlDraws {
  pHome: number[];
  pDraw: number[];
  pAway: number[];
}

export interface WdlKeyframe {
  minute: number;
  homeGoals: number;
  awayGoals: number;
  wdl: LiveWdlDraws;
}

export interface StatPoint {
  minute: number;
  homeShotsOn: number | null;
  awayShotsOn: number | null;
  homeTotalShots: number | null;
  awayTotalShots: number | null;
  homePossession: number | null;
  awayPossession: number | null;
}

export interface ImpactResult {
  match: number;
  homeId: string | null;
  awayId: string | null;
  homeGoals: number;
  awayGoals: number;
  winner: string | null;
  sourceFixtureId: number | null;
  fetchedAt: string | null;
  kind: ImpactResultKind;
}

export interface Impact {
  agentRunId: string;
  agentCreatedAt: string;
  agentAsOf: string;
  thenBasis: string;
  nowBasis: string;
  currentFitRunId: string;
  currentFitAsOf: string;
  datasetId: string;
  agentResultSetDigest: string;
  currentResultSetDigest: string;
  liveMode: ImpactLiveMode;
  nSims: number;
  seed: number;
  parameterUncertainty: boolean;
  generatedAt: string;
  resultsSinceAgent: ImpactResult[];
  fixtures: ImpactFixture[];
  teams: Record<string, TeamImpact>;
}

// The report is precomputed for every team and served as one cached artifact,
// so the lip and the chart share a single request with no team selection.
export const loadImpact = cache(async (): Promise<ApiResult<Impact>> => backendGet<Impact>("/impact"));

export const loadAgentImpact = loadImpact;

export function impactForAgent(impact: Impact | null, runId: string): Impact | null {
  return impact?.agentRunId === runId ? impact : null;
}
