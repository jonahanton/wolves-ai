import type { ArchiveDayPayload } from "@/lib/archive/contracts";
import type { PlayedResultRow } from "@/lib/results";
import type { RunRecord, TeamHistory } from "@/lib/runs";

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

export function archiveHistories(
  payload: ArchiveDayPayload,
  teamIds: string[],
): Map<string, TeamHistory> {
  const histories = new Map<string, TeamHistory>(
    teamIds.map((teamId) => [teamId, { teamId, points: [] }]),
  );
  for (const snapshot of payload.forecast_history) {
    for (const team of snapshot.teams) {
      const history = histories.get(team.team_id);
      if (!history) continue;
      history.points.push({
        runId: snapshot.run.run_id,
        asOf: snapshot.run.as_of ?? snapshot.run.created_at.slice(0, 10),
        championProb: team.champion_prob ?? 0,
        reachProbs: team.reach_probs ?? {},
      });
    }
  }
  return histories;
}
