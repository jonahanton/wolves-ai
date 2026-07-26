import { ForecastRun } from "@/components/forecast/forecast-run";
import { FestivalBand } from "@/components/walls/festival-band";
import type { ArchiveRunRecord } from "@/lib/archive/contracts";
import { titleBoard } from "@/lib/derive";
import { cleanStories, cleanWorkings, featuredMovers, readingList, runMeta, tournamentPhase } from "@/lib/forecast";
import type { Snapshot } from "@/lib/snapshot";
import type { DistributionsSidecar } from "@/lib/sidecars";

interface ArchiveForecastRunPageProps {
  day: string;
  snapshot: Snapshot;
  distributions: DistributionsSidecar;
  record: ArchiveRunRecord | null;
}

export function ArchiveForecastRunPage({ day, snapshot, distributions, record }: ArchiveForecastRunPageProps) {
  const agent = snapshot.agent;
  if (!agent) return null;
  const names = Object.fromEntries(snapshot.teams.map((team) => [team.team_id, team.name]));
  const fullBoard = titleBoard(snapshot, snapshot.teams.length);
  const reachProbs = Object.fromEntries(snapshot.teams.map((team) => [team.team_id, team.reach_probs ?? {}]));
  const championCells = Object.fromEntries(
    Object.entries(distributions.teams)
      .map(([teamId, stages]) => [teamId, stages.champion] as const)
      .filter(([, cell]) => cell !== undefined),
  );
  const cellUppers = Object.values(championCells)
    .filter((cell) => cell.bin_edges.length > 0)
    .map((cell) => cell.bin_edges[cell.bin_edges.length - 1]);
  const xMax = cellUppers.length > 0 ? Math.max(...cellUppers) : 1;
  const championProbs = Object.fromEntries(snapshot.teams.map((team) => [team.team_id, team.champion_prob ?? 0]));
  const stageByMatch = new Map<number, string>([
    ...(snapshot.matches ?? []).map((match) => [match.match, match.stage] as const),
    ...snapshot.slots.map((slot) => [slot.match, slot.stage] as const),
  ]);
  const playedStages = (snapshot.result_set?.results ?? []).map(
    (result) => stageByMatch.get(result.match) ?? "group",
  );
  return (
    <>
      <main className="wrap py-[clamp(28px,5vh,56px)]">
        <ForecastRun
          archiveDay={day}
          runStamp={snapshot.run.created_at}
          phase={tournamentPhase(snapshot.run.created_at, snapshot.matches ?? [], playedStages)}
          headline={agent.narrative.headline ?? ""}
          board={fullBoard}
          reachProbs={reachProbs}
          names={names}
          movers={featuredMovers(agent, snapshot.markets, championProbs, names)}
          championCells={championCells}
          xMax={xMax}
          camps={agent.camps ?? []}
          weights={agent.scenario_weights ?? []}
          drivers={snapshot.distributions?.drivers ?? {}}
          stories={cleanStories(agent.narrative.team_stories ?? {})}
          sources={readingList(agent)}
          workings={cleanWorkings(agent)}
          meta={runMeta(record?.duration_s ?? null, record?.cost ?? null)}
        />
      </main>
      <div className="max-h-[clamp(120px,18vh,200px)] overflow-hidden">
        <FestivalBand family="euros" tag="Euros 2024 · the Wolves" />
      </div>
    </>
  );
}
