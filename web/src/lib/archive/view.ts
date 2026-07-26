import type { ArchiveDayPayload } from "@/lib/archive/contracts";
import type { PlayedResultRow } from "@/lib/results";
import type { RunRecord } from "@/lib/runs";

export function archiveResults(payload: ArchiveDayPayload): PlayedResultRow[] {
  return payload.results.map((result) => ({
    match: result.match,
    date: result.date,
    stage: result.stage,
    homeId: result.home_id,
    awayId: result.away_id,
    homeGoals: result.home_goals,
    awayGoals: result.away_goals,
    winner: result.winner,
  }));
}

export function archiveRunRecords(payload: ArchiveDayPayload): RunRecord[] {
  return payload.forecast_history.flatMap(({ record }) =>
    record
      ? [{
          runId: record.run_id,
          createdAt: record.created_at,
          s3Key: "",
          status: record.status,
          cost: record.cost,
          durationS: record.duration_s,
          kind: record.kind,
        }]
      : [],
  );
}
