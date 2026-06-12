// Mirrors the backend /impact WireModel; this wire is camelCase.
import { type ApiResult, backendGet } from "@/lib/api";

export interface StageImpact {
  agent: number;
  estimated: number;
  fromResultsPp: number;
  fromIngamePp: number;
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

export interface ImpactSeriesPoint {
  fetchedAt: string;
  teams: Record<string, Record<string, number>>;
}

export interface Impact {
  agentRunId: string;
  agentAsOf: string;
  agentCreatedAt: string;
  fittedRunId: string;
  nSims: number;
  teams: Record<string, Record<string, StageImpact>>;
  fixtures: ImpactFixture[];
  series: ImpactSeriesPoint[];
}

export async function loadImpact(teams?: string[]): Promise<ApiResult<Impact>> {
  const query = teams?.length ? `?teams=${encodeURIComponent(teams.join(","))}` : "";
  return backendGet<Impact>(`/impact${query}`);
}
