// Mirrors the backend /results WireModel; this wire is camelCase.
import { type ApiResult, backendGet } from "@/lib/api";

export interface PlayedResultRow {
  match: number;
  date: string;
  stage: string;
  homeId: string | null;
  awayId: string | null;
  homeGoals: number;
  awayGoals: number;
  winner: string | null;
}

export async function loadResults(): Promise<ApiResult<{ results: PlayedResultRow[] }>> {
  return backendGet<{ results: PlayedResultRow[] }>("/results");
}
