import { ForecastRun } from "@/components/forecast/forecast-run";
import { ErrorState } from "@/components/shell/error-state";
import { FestivalBand } from "@/components/walls/festival-band";
import { orNull } from "@/lib/api";
import { titleBoard } from "@/lib/derive";
import {
  cleanStories,
  cleanWorkings,
  featuredMovers,
  readingList,
  runMeta,
  tournamentPhase,
} from "@/lib/forecast";
import { loadSnapshot } from "@/lib/load-snapshot";
import { loadRunRecords } from "@/lib/runs";
import { type CellShape, loadDistributions } from "@/lib/sidecars";

interface PageProps {
  params: Promise<{ runId: string }>;
}

export default async function ForecastRunPage({ params }: PageProps) {
  const { runId } = await params;
  const [snapshotResult, distributionsResult, recordsResult] = await Promise.all([
    loadSnapshot(runId),
    loadDistributions(runId),
    loadRunRecords(),
  ]);
  if (!snapshotResult.ok) return <ErrorState error={snapshotResult.error} />;
  const snapshot = snapshotResult.data;
  const agent = snapshot.agent;
  if (!agent) return <ErrorState error={{ category: "not_found" }} />;

  const names = Object.fromEntries(snapshot.teams.map((t) => [t.team_id, t.name]));
  const fullBoard = titleBoard(snapshot, snapshot.teams.length);
  const reachProbs = Object.fromEntries(
    snapshot.teams.filter((t) => t.reach_probs).map((t) => [t.team_id, t.reach_probs ?? {}]),
  );

  const sidecar = orNull(distributionsResult);
  const championCells: Record<string, CellShape> = Object.fromEntries(
    Object.entries(sidecar?.teams ?? {})
      .map(([teamId, stages]) => [teamId, stages.champion] as const)
      .filter(([, cell]) => cell !== undefined),
  );
  const cellUppers = Object.values(championCells)
    .filter((c) => c.bin_edges.length > 0)
    .map((c) => c.bin_edges[c.bin_edges.length - 1]);
  const xMax = cellUppers.length > 0 ? Math.max(...cellUppers) : 1;

  const camps = (agent.camps ?? []).slice().sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
  const weights = agent.scenario_weights ?? [];
  const drivers = snapshot.distributions?.drivers ?? {};
  const stories = cleanStories(agent.narrative.team_stories ?? {});

  const championProbs = Object.fromEntries(
    snapshot.teams.filter((t) => t.champion_prob !== undefined).map((t) => [t.team_id, t.champion_prob ?? 0]),
  );
  const stageByMatch = new Map((snapshot.matches ?? []).map((m) => [m.match, m.stage]));
  const playedStages = (snapshot.result_set?.results ?? []).map((r) => stageByMatch.get(r.match) ?? "group");

  const sources = readingList(agent);
  const records = orNull(recordsResult)?.runs ?? null;
  const record = records?.find((r) => r.runId === runId) ?? null;

  return (
    <>
      <main className="wrap py-[clamp(28px,5vh,56px)]">
        <ForecastRun
          runStamp={snapshot.run.created_at}
          phase={tournamentPhase(snapshot.run.created_at, snapshot.matches ?? [], playedStages)}
          headline={agent.narrative.headline ?? ""}
          board={fullBoard}
          reachProbs={reachProbs}
          names={names}
          movers={featuredMovers(agent, snapshot.markets, championProbs, names)}
          championCells={championCells}
          xMax={xMax}
          camps={camps}
          weights={weights}
          drivers={drivers}
          stories={stories}
          sources={sources}
          workings={cleanWorkings(agent)}
          meta={runMeta(record?.durationS ?? null, record?.cost ?? null)}
        />
      </main>
      <div className="max-h-[clamp(120px,18vh,200px)] overflow-hidden">
        <FestivalBand family="euros" tag="Euros 2024 · the Wolves" />
      </div>
    </>
  );
}
