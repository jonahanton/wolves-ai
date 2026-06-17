import { type ApiResult, backendGet } from "@/lib/api";

export type LiveStatus = "scheduled" | "live" | "finished" | "abandoned";
export type PollStatus = "ok" | "failed";
export type ForecastSource = "pre_match" | "in_match" | "settled";

export interface LiveForecast {
  source: ForecastSource;
  pHome: number;
  pAway: number;
  pDraw?: number | null;
  modalScore?: string | null;
}

interface RawLiveForecast {
  source: ForecastSource;
  p_home: number;
  p_away: number;
  p_draw?: number | null;
  modal_score?: string | null;
}

export interface LiveFixture {
  externalId: number;
  match: number | null;
  status: LiveStatus;
  kickoff: string;
  city?: string | null;
  minute?: number | null;
  homeId?: string | null;
  awayId?: string | null;
  homeName: string;
  awayName: string;
  homeGoals?: number | null;
  awayGoals?: number | null;
  homeReds?: number;
  awayReds?: number;
  forecast?: LiveForecast | null;
  message?: string | null;
}

interface RawLiveFixture {
  external_id: number;
  match: number | null;
  status: LiveStatus;
  kickoff: string;
  city?: string | null;
  minute?: number | null;
  home_id?: string | null;
  away_id?: string | null;
  home_name: string;
  away_name: string;
  home_goals?: number | null;
  away_goals?: number | null;
  home_reds?: number;
  away_reds?: number;
  forecast?: RawLiveForecast | null;
  message?: string | null;
}

export interface LiveState {
  schemaVersion: number;
  generatedAt: string;
  fetchedAt: string;
  staleAfter: string;
  source: string;
  pollStatus: PollStatus;
  message?: string | null;
  liveMatchCount: number;
  fixtures: LiveFixture[];
}

interface RawLiveState {
  schema_version: number;
  generated_at: string;
  fetched_at: string;
  stale_after: string;
  source: string;
  poll_status: PollStatus;
  message?: string | null;
  live_match_count: number;
  fixtures: RawLiveFixture[];
}

export async function loadLiveState(): Promise<ApiResult<LiveState>> {
  const result = await backendGet<RawLiveState>("/live");
  if (!result.ok) return result;
  return { ok: true, data: mapLiveState(result.data) };
}

export function liveIsFresh(live: LiveState | null, now: number = Date.now()): boolean {
  return live?.pollStatus === "ok" && Date.parse(live.staleAfter) >= now;
}

function mapLiveState(raw: RawLiveState): LiveState {
  return {
    schemaVersion: raw.schema_version,
    generatedAt: raw.generated_at,
    fetchedAt: raw.fetched_at,
    staleAfter: raw.stale_after,
    source: raw.source,
    pollStatus: raw.poll_status,
    message: raw.message,
    liveMatchCount: raw.live_match_count,
    fixtures: raw.fixtures.map(mapFixture),
  };
}

function mapFixture(raw: RawLiveFixture): LiveFixture {
  return {
    externalId: raw.external_id,
    match: raw.match,
    status: raw.status,
    kickoff: raw.kickoff,
    city: raw.city,
    minute: raw.minute,
    homeId: raw.home_id,
    awayId: raw.away_id,
    homeName: raw.home_name,
    awayName: raw.away_name,
    homeGoals: raw.home_goals,
    awayGoals: raw.away_goals,
    homeReds: raw.home_reds,
    awayReds: raw.away_reds,
    forecast: raw.forecast ? mapForecast(raw.forecast) : null,
    message: raw.message,
  };
}

function mapForecast(raw: RawLiveForecast): LiveForecast {
  return {
    source: raw.source,
    pHome: raw.p_home,
    pAway: raw.p_away,
    pDraw: raw.p_draw,
    modalScore: raw.modal_score,
  };
}
