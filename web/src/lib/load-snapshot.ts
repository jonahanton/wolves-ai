import { type ApiResult, backendGet } from "@/lib/api";
import type { Snapshot } from "@/lib/snapshot";

export async function loadLatestSnapshot(): Promise<ApiResult<Snapshot>> {
  return backendGet<Snapshot>("/snapshots/latest");
}

export async function loadSnapshot(runId: string): Promise<ApiResult<Snapshot>> {
  return backendGet<Snapshot>(`/snapshots/${encodeURIComponent(runId)}`);
}
