import { type ApiResult, backendGet } from "@/lib/api";

export interface BracketSampleMatch {
  match: number;
  stage: string;
  home: string;
  away: string;
  winner: string;
}

export interface BracketSample {
  world: string;
  matches: BracketSampleMatch[];
}

export interface BracketSamples {
  samples: BracketSample[];
}

export interface OpponentProb {
  opponent: string;
  p: number;
}

export interface PairingMatrices {
  rounds: Record<string, Record<string, OpponentProb[]>>;
}

export interface MatchWdl {
  p_home: number[];
  p_draw: number[];
  p_away: number[];
}

export interface MatchWdlDraws {
  matches: Record<string, MatchWdl>;
}

export type SidecarName = "bracket-samples" | "pairing-matrices" | "match-wdl-draws";

export async function loadSidecar<T>(runId: string, name: SidecarName): Promise<ApiResult<T>> {
  return backendGet<T>(`/snapshots/${encodeURIComponent(runId)}/sidecars/${name}`);
}
