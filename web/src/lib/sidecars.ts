import { cache } from "react";
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

export interface CellComponent {
  weight: number;
  mean: number;
  sd: number;
}

export interface CellShape {
  bin_edges: number[];
  histogram: number[];
  world_bins: Record<string, number[]>;
  components: Record<string, CellComponent>;
  our_call?: number | null;
  component_mean?: number | null;
}

export interface DistributionsSidecar {
  quantile_levels: number[];
  provenance: string;
  teams: Record<string, Record<string, CellShape>>;
}

export type SidecarName = "distributions" | "bracket-samples" | "pairing-matrices" | "match-wdl-draws";

// Sidecars are keyed by an immutable run id, so cache them forever and dedupe per request.
export const loadSidecar = cache(async <T>(runId: string, name: SidecarName): Promise<ApiResult<T>> => {
  return backendGet<T>(`/snapshots/${encodeURIComponent(runId)}/sidecars/${name}`, { revalidate: false, retry: true });
});

export async function loadDistributions(runId: string): Promise<ApiResult<DistributionsSidecar>> {
  return loadSidecar<DistributionsSidecar>(runId, "distributions");
}
