// Mirrors the backend live models; this wire is snake_case, not camelCase.
import { type ApiResult, backendGet } from "@/lib/api";

export type LiveSource = "pre_match" | "in_match" | "settled";

export interface LiveForecast {
  source: LiveSource;
  p_home: number;
  p_away: number;
  p_draw?: number | null;
  modal_score?: string | null;
}

export type LiveFixtureStatus = "scheduled" | "live" | "finished" | "abandoned";

export interface LiveFixture {
  external_id: number;
  match: number | null;
  status: LiveFixtureStatus;
  kickoff: string;
  city?: string | null;
  minute?: number | null;
  home_id?: string | null;
  away_id?: string | null;
  home_name: string;
  away_name: string;
  home_goals?: number | null;
  away_goals?: number | null;
  home_reds: number;
  away_reds: number;
  forecast?: LiveForecast | null;
  message?: string | null;
}

export interface ScheduleDrift {
  match: number;
  scheduled_kickoff: string;
  provider_kickoff: string;
}

export interface LiveState {
  schema_version: number;
  generated_at: string;
  fetched_at: string;
  stale_after: string;
  source: string;
  poll_status: "ok" | "failed";
  message?: string | null;
  live_match_count: number;
  fixtures: LiveFixture[];
  title_probs: Record<string, number>;
  title_deltas_pp: Record<string, number>;
  schedule_drift: ScheduleDrift[];
}

export interface LiveHistoryPoint {
  fetched_at: string;
  fixtures: LiveHistoryFixture[];
}

export interface LiveHistoryFixture {
  external_id: number;
  match: number | null;
  status: LiveFixtureStatus;
  minute?: number | null;
  home_goals?: number | null;
  away_goals?: number | null;
  forecast?: LiveForecast | null;
}

export interface LiveHistory {
  date: string;
  points: LiveHistoryPoint[];
}

export async function loadLiveState(): Promise<ApiResult<LiveState>> {
  return backendGet<LiveState>("/live");
}

export async function loadLiveHistory(date: string): Promise<ApiResult<LiveHistory>> {
  return backendGet<LiveHistory>(`/live/history/${encodeURIComponent(date)}`);
}

export function isStale(state: LiveState, now: Date = new Date()): boolean {
  return now.getTime() > new Date(state.stale_after).getTime();
}
