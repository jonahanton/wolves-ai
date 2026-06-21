import { cache } from "react";
import { type ApiResult, backendGet } from "@/lib/api";
import type { Snapshot } from "@/lib/snapshot";

// Serve the previous forecast (flagged stale) through a brief backend outage.
let lastGood: Snapshot | null = null;

export const loadLatestSnapshot = cache(async (): Promise<ApiResult<Snapshot>> => {
  const result = await backendGet<Snapshot>("/snapshots/latest", { revalidate: 45, retry: true });
  if (result.ok) {
    lastGood = result.data;
    return result;
  }
  if (lastGood && result.error.category !== "not_found") {
    console.warn(`latest snapshot ${result.error.category}; serving stale lastGood`);
    return { ok: true, data: lastGood, stale: true };
  }
  console.warn(`latest snapshot ${result.error.category} and no stale fallback; landing page will error`);
  return result;
});

// A run-id snapshot is immutable, so cache it forever and dedupe within a request.
export const loadSnapshot = cache(async (runId: string): Promise<ApiResult<Snapshot>> => {
  return backendGet<Snapshot>(`/snapshots/${encodeURIComponent(runId)}`, { revalidate: false });
});
