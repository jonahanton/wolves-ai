import { LandingForecast } from "@/components/landing/landing-forecast";
import { ErrorState } from "@/components/shell/error-state";
import { FestivalBand } from "@/components/walls/festival-band";
import { orNull } from "@/lib/api";
import { titleBoard } from "@/lib/derive";
import type { ChartTeamInput } from "@/lib/forecast-series";
import { formatRunStampEastern } from "@/lib/format";
import { loadFullRunIds } from "@/lib/full-runs";
import { loadLatestSnapshot, loadSnapshot } from "@/lib/load-snapshot";
import { loadResults } from "@/lib/results";
import { loadSnapshotIndex, loadTeamHistory } from "@/lib/runs";
import { chartColour } from "@/lib/team-colours";

const CHART_TEAM_COUNT = 7;
const FIELD_FLOOR = 0.01;

export default async function LandingPage() {
  const [result, indexResult, resultsResult] = await Promise.all([
    loadLatestSnapshot(),
    loadSnapshotIndex(),
    loadResults(),
  ]);
  if (!result.ok) return <ErrorState error={result.error} context="World Cup Superforecaster" />;
  const snapshot = result.data;

  // The page speaks for the agent's full forecast; live runs may be newer.
  const index = orNull(indexResult)?.snapshots ?? [];
  const agentRef = index.find((ref) => ref.kind === "agent");
  const agentSnapshot =
    snapshot.run.kind === "agent" || !agentRef
      ? snapshot
      : (orNull(await loadSnapshot(agentRef.runId)) ?? snapshot);

  const focusId = agentSnapshot.focus.team_id;
  const names = Object.fromEntries(agentSnapshot.teams.map((t) => [t.team_id, t.name]));

  const board = titleBoard(agentSnapshot, CHART_TEAM_COUNT);
  const leaderId = board[0]?.teamId ?? focusId;
  const topIds = new Set([...board.map((row) => row.teamId), focusId]);
  const probOf = new Map(agentSnapshot.teams.map((t) => [t.team_id, t.champion_prob ?? 0]));
  const allIds = agentSnapshot.teams
    .filter((t) => (t.champion_prob ?? 0) > 0)
    .sort((a, b) => (b.champion_prob ?? 0) - (a.champion_prob ?? 0))
    .map((t) => t.team_id);

  const tierOf = (teamId: string): "top" | "field" | "tail" => {
    if (topIds.has(teamId)) return "top";
    return (probOf.get(teamId) ?? 0) >= FIELD_FLOOR ? "field" : "tail";
  };

  const [fullRunIds, ...histories] = await Promise.all([
    loadFullRunIds(index),
    ...allIds.map((teamId) => loadTeamHistory(teamId)),
  ] as const);

  const chartTeams: ChartTeamInput[] = allIds.map((teamId, i) => ({
    teamId,
    name: names[teamId] ?? teamId,
    featured: teamId === leaderId,
    tier: tierOf(teamId),
    colour: chartColour(teamId),
    history: (orNull(histories[i])?.points ?? []).filter((p) => fullRunIds.has(p.runId)),
  }));

  return (
    <>
      <LandingForecast
        runLabel={formatRunStampEastern(agentSnapshot.run.created_at)}
        teams={chartTeams}
        results={orNull(resultsResult)?.results ?? []}
        names={names}
        leaderId={leaderId}
        board={board}
      />
      <div className="max-h-[clamp(200px,30vh,340px)] overflow-hidden">
        <FestivalBand family="euros" tag="Euros 2024 · the Wolves" />
      </div>
    </>
  );
}
