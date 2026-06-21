// Mirrors the backend WireModel routes; this wire is camelCase.
import { cache } from "react";
import { type ApiResult, backendGet } from "@/lib/api";

export interface RunRecord {
  runId: string;
  createdAt: string;
  s3Key: string;
  status: "completed" | "failed";
  cost: number;
  durationS: number;
  kind: string;
}

export interface SnapshotRef {
  runId: string;
  asOf: string;
  kind: string;
  key: string;
  hasDistributions: boolean;
}

export interface TeamHistoryPoint {
  runId: string;
  asOf: string;
  championProb: number;
  reachProbs: Record<string, number>;
  marketProb?: number | null;
  blendProb?: number | null;
}

export interface TeamHistory {
  teamId: string;
  points: TeamHistoryPoint[];
}

export async function loadRunRecords(): Promise<ApiResult<{ runs: RunRecord[] }>> {
  return backendGet<{ runs: RunRecord[] }>("/runs");
}

export const loadSnapshotIndex = cache(async (): Promise<ApiResult<{ snapshots: SnapshotRef[] }>> => {
  return backendGet<{ snapshots: SnapshotRef[] }>("/snapshots", { revalidate: 45, retry: true });
});

export async function loadTeamHistory(teamId: string, limit = 30): Promise<ApiResult<TeamHistory>> {
  return backendGet<TeamHistory>(`/teams/${encodeURIComponent(teamId)}/history?limit=${limit}`, {
    revalidate: 300,
    retry: true,
  });
}

export async function loadTeamHistories(teamIds: string[], limit = 30): Promise<ApiResult<{ histories: TeamHistory[] }>> {
  const ids = teamIds.map((id) => encodeURIComponent(id)).join(",");
  return backendGet<{ histories: TeamHistory[] }>(`/teams/histories?ids=${ids}&limit=${limit}`, {
    revalidate: 300,
    retry: true,
  });
}
