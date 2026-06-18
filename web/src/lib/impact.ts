import { cache } from "react";
import { type ApiResult, backendGet } from "@/lib/api";
import { loadLatestSnapshot, loadSnapshot } from "@/lib/load-snapshot";
import { loadSnapshotIndex } from "@/lib/runs";

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
  wdlDraws: LiveWdlDraws | null;
  wdlKeyframes: WdlKeyframe[];
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

const IMPACT_TEAM_COUNT = 8;

export async function loadImpact(teamIds?: string[]): Promise<ApiResult<Impact>> {
  const query = teamIds && teamIds.length > 0 ? `?teams=${teamIds.join(",")}` : "";
  return backendGet<Impact>(`/impact${query}`);
}

// One impact request per render, shared by the layout lip and the landing chart:
// resolve the agent run, then ask for a fixed top-champions set so both callers
// dedupe to a single per-request sim instead of two with divergent team lists.
export const loadAgentImpact = cache(async (): Promise<ApiResult<Impact>> => {
  const teams = await agentImpactTeams();
  return loadImpact(teams);
});

async function agentImpactTeams(): Promise<string[]> {
  const latest = await loadLatestSnapshot();
  if (!latest.ok) return [];
  let snapshot = latest.data;
  if (snapshot.run.kind !== "agent") {
    const index = await loadSnapshotIndex();
    const agentRef = index.ok ? index.data.snapshots.find((ref) => ref.kind === "agent") : undefined;
    if (agentRef) {
      const agent = await loadSnapshot(agentRef.runId);
      if (agent.ok) snapshot = agent.data;
    }
  }
  const ranked = snapshot.teams
    .filter((team) => team.champion_prob !== undefined)
    .sort((a, b) => (b.champion_prob ?? 0) - (a.champion_prob ?? 0))
    .map((team) => team.team_id);
  const focus = snapshot.focus.team_id;
  const top = ranked.slice(0, IMPACT_TEAM_COUNT);
  return top.includes(focus) ? top : [...top, focus];
}

export function impactForAgent(impact: Impact | null, runId: string): Impact | null {
  return impact?.agentRunId === runId ? impact : null;
}
