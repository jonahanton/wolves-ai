import { cache } from "react";
import { type ApiResult, backendGet } from "@/lib/api";
import type { Snapshot } from "@/lib/snapshot";

export const loadLatestSnapshot = cache(async (): Promise<ApiResult<Snapshot>> => {
  return backendGet<Snapshot>("/snapshots/latest", { revalidate: 45 });
});

// A run-id snapshot is immutable, so cache it forever and dedupe within a request.
export const loadSnapshot = cache(async (runId: string): Promise<ApiResult<Snapshot>> => {
  return backendGet<Snapshot>(`/snapshots/${encodeURIComponent(runId)}`, { revalidate: false });
});
