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
import { loadDistributions } from "@/lib/sidecars";
import { chartColour } from "@/lib/team-colours";

const CHART_TEAM_COUNT = 7;

export default async function LandingPage() {
  const [result, indexResult, resultsResult] = await Promise.all([
    loadLatestSnapshot(),
    loadSnapshotIndex(),
    loadResults(),
  ]);
  if (!result.ok) return <ErrorState error={result.error} />;
  const snapshot = result.data;

  // The page speaks for the agent's full forecast; live runs may be newer.
  const index = orNull(indexResult)?.snapshots ?? [];
  const agentRef = index.find((ref) => ref.kind === "agent");
  const agentSnapshot =
    snapshot.run.kind === "agent" || !agentRef
      ? snapshot
      : (orNull(await loadSnapshot(agentRef.runId)) ?? snapshot);

  const focusId = agentSnapshot.focus.team_id;
  const names = Object.fromEntries(
    agentSnapshot.teams.map((t) => [t.team_id, t.name]),
  );

  const fullBoard = titleBoard(agentSnapshot, agentSnapshot.teams.length);
  const board = fullBoard.slice(0, CHART_TEAM_COUNT);
  const leaderId = board[0]?.teamId ?? focusId;
  const topIds = new Set([...board.map((row) => row.teamId), focusId]);
  const allIds = agentSnapshot.teams
    .filter((t) => t.champion_prob !== undefined)
    .sort((a, b) => (b.champion_prob ?? 0) - (a.champion_prob ?? 0))
    .map((t) => t.team_id);

  const [fullRunIds, distributions, ...histories] = await Promise.all([
    loadFullRunIds(index),
    loadDistributions(agentSnapshot.run.run_id),
    ...allIds.map((teamId) => loadTeamHistory(teamId)),
  ] as const);

  const sidecar = orNull(distributions);
  const championCells = Object.fromEntries(
    Object.entries(sidecar?.teams ?? {})
      .map(([teamId, stages]) => [teamId, stages.champion] as const)
      .filter(([, cell]) => cell !== undefined),
  );
  const cellUppers = Object.values(championCells)
    .filter((c) => c.bin_edges.length > 0)
    .map((c) => c.bin_edges[c.bin_edges.length - 1]);
  const xMax = cellUppers.length > 0 ? Math.max(...cellUppers) : 1;
  const weights = agentSnapshot.agent?.scenario_weights ?? [];
  const camps = (agentSnapshot.agent?.camps ?? [])
    .slice()
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
  const drivers = agentSnapshot.distributions?.drivers ?? {};
  const stories = agentSnapshot.agent?.narrative.team_stories ?? {};

  const chartTeams: ChartTeamInput[] = allIds.map((teamId, i) => ({
    teamId,
    name: names[teamId] ?? teamId,
    featured: teamId === leaderId,
    tier: topIds.has(teamId) ? "top" : "rest",
    colour: chartColour(teamId),
    history: (orNull(histories[i])?.points ?? []).filter((p) =>
      fullRunIds.has(p.runId),
    ),
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
        fullBoard={fullBoard}
        championCells={championCells}
        xMax={xMax}
        weights={weights}
        camps={camps}
        drivers={drivers}
        stories={stories}
      />
      <div className="max-h-[clamp(120px,18vh,200px)] overflow-hidden">
        <FestivalBand family="euros" tag="Euros 2024 · the Wolves" />
      </div>
    </>
  );
}
