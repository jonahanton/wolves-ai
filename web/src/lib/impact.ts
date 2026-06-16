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

export async function loadImpact(teamIds?: string[]): Promise<ApiResult<Impact>> {
  const query = teamIds && teamIds.length > 0 ? `?teams=${teamIds.join(",")}` : "";
  return backendGet<Impact>(`/impact${query}`);
}

export function impactForAgent(impact: Impact | null, runId: string): Impact | null {
  return impact?.agentRunId === runId ? impact : null;
}
