// Mirrors the engine's ImpliedReachSeries served verbatim; this wire is snake_case.
import { type ApiResult, backendGet } from "@/lib/api";

export interface ImpliedReachPoint {
  date: string;
  captured_at: string;
  outright: Record<string, number>;
  teams: Record<string, Record<string, number>>;
}

export async function loadMarketReach(): Promise<ApiResult<{ points: ImpliedReachPoint[] }>> {
  return backendGet<{ points: ImpliedReachPoint[] }>("/market/reach");
}
