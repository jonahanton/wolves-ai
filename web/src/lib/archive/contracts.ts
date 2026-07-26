import type { BracketSamples, DistributionsSidecar, MatchWdlDraws, PairingMatrices } from "@/lib/sidecars";
import type { RunMeta, Snapshot, TeamInfo } from "@/lib/snapshot";

export interface ArchiveObject {
  path: string;
  sha256: string;
  bytes: number;
}

export interface ArchiveDay {
  day: string;
  cutoff_at: string;
  forecast_run_id: string;
  forecast_created_at: string;
  live_detail: "complete" | "unavailable" | "omitted";
  payload: ArchiveObject;
}

export interface ArchiveRun {
  run_id: string;
  created_at: string;
  archive_day: string;
  payload: ArchiveObject;
}

export interface ArchiveManifest {
  schema_hash: string;
  archived_through: string;
  archive_timezone: string;
  days: ArchiveDay[];
  runs: ArchiveRun[];
  final_day: string;
  default_route: string;
}

export interface ArchiveRunRecord {
  run_id: string;
  created_at: string;
  status: "completed" | "failed";
  cost: number | null;
  duration_s: number | null;
  kind: string;
}

export interface ArchiveForecastPoint {
  run: RunMeta;
  teams: TeamInfo[];
  record: ArchiveRunRecord | null;
}

export interface ArchivedResult {
  match: number;
  date: string;
  stage: string;
  home_id: string | null;
  away_id: string | null;
  home_goals: number;
  away_goals: number;
  winner: string | null;
  recorded_at: string;
}

export interface ArchiveDayPayload {
  schema_hash: string;
  day: string;
  cutoff_at: string;
  selected_snapshot: Snapshot;
  sidecars: {
    distributions: DistributionsSidecar;
    bracket_samples: BracketSamples;
    pairing_matrices: PairingMatrices;
    match_wdl_draws: MatchWdlDraws;
  };
  results: ArchivedResult[];
  forecast_history: ArchiveForecastPoint[];
  live_detail: "complete" | "unavailable" | "omitted";
}

export interface ArchiveRunPayload {
  schema_hash: string;
  snapshot: Snapshot;
  distributions: DistributionsSidecar;
  record: ArchiveRunRecord | null;
}

export class ArchiveLoadError extends Error {
  constructor(readonly category: "missing" | "corrupt") {
    super(category);
  }
}
