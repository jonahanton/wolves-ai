// Mirrors the backend WireModel routes (camelCase on the wire:
// alias_generator=to_camel in backend/wolves_backend/models.py).
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

export async function loadSnapshotIndex(): Promise<ApiResult<{ snapshots: SnapshotRef[] }>> {
  return backendGet<{ snapshots: SnapshotRef[] }>("/snapshots");
}

export async function loadTeamHistory(teamId: string, limit = 30): Promise<ApiResult<TeamHistory>> {
  return backendGet<TeamHistory>(`/teams/${encodeURIComponent(teamId)}/history?limit=${limit}`);
}
