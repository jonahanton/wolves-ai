import { LandingForecast } from "@/components/landing/landing-forecast";
import { ErrorState } from "@/components/shell/error-state";
import { FestivalBand } from "@/components/walls/festival-band";
import { orNull } from "@/lib/api";
import { agentReasoning, deriveHero, titleBoard } from "@/lib/derive";
import type { ChartTeamInput } from "@/lib/forecast-series";
import { formatUpdated } from "@/lib/format";
import { loadImpact } from "@/lib/impact";
import { rankedLedger } from "@/lib/ledger";
import { loadLatestSnapshot, loadSnapshot } from "@/lib/load-snapshot";
import { loadMarketReach } from "@/lib/market-reach";
import { loadResults } from "@/lib/results";
import { loadSnapshotIndex, loadTeamHistory } from "@/lib/runs";

const SERIES_COLOURS = ["oklch(0.6 0.06 250)", "oklch(0.965 0.008 95 / 0.34)", "oklch(0.965 0.008 95 / 0.25)", "oklch(0.965 0.008 95 / 0.22)"];

export default async function LandingPage() {
  const [result, indexResult, marketReachResult, resultsResult] = await Promise.all([
    loadLatestSnapshot(),
    loadSnapshotIndex(),
    loadMarketReach(),
    loadResults(),
  ]);
  if (!result.ok) return <ErrorState error={result.error} context="World Cup Superforecaster" />;
  const snapshot = result.data;
  const now = new Date();

  // The page speaks for the agent's full forecast; live runs may be newer.
  const agentRef = orNull(indexResult)?.snapshots.find((ref) => ref.kind === "agent");
  const agentSnapshot =
    snapshot.run.kind === "agent" || !agentRef
      ? snapshot
      : (orNull(await loadSnapshot(agentRef.runId)) ?? snapshot);

  const hero = deriveHero(agentSnapshot);
  const focusId = agentSnapshot.focus.team_id;
  const names = Object.fromEntries(agentSnapshot.teams.map((t) => [t.team_id, t.name]));

  const agentBoard = titleBoard(agentSnapshot, 4);
  const chartTeamIds = [...new Set([...agentBoard.map((row) => row.teamId), focusId])];
  const [impactResult, ...histories] = await Promise.all([
    loadImpact(chartTeamIds),
    ...chartTeamIds.map((teamId) => loadTeamHistory(teamId)),
  ] as const);
  const chartTeams: ChartTeamInput[] = chartTeamIds.map((teamId, i) => ({
    teamId,
    name: names[teamId] ?? teamId,
    featured: teamId === focusId,
    colour: teamId === focusId ? "oklch(0.69 0.19 25)" : SERIES_COLOURS[i % SERIES_COLOURS.length],
    history: orNull(histories[i])?.points ?? [],
  }));

  return (
    <>
      <LandingForecast
        now={now.getTime()}
        leader={hero.leader}
        focus={hero.focus}
        runLabel={formatUpdated(agentSnapshot.run.created_at)}
        teams={chartTeams}
        marketReach={orNull(marketReachResult)?.points ?? []}
        results={orNull(resultsResult)?.results ?? []}
        initialImpact={orNull(impactResult)}
        names={names}
        focusId={focusId}
        reasoning={agentReasoning(agentSnapshot)}
        evidence={rankedLedger(agentSnapshot, 5)}
      />
      <div className="max-h-[clamp(200px,30vh,340px)] overflow-hidden">
        <FestivalBand family="euros" tag="Euros 2024 · the Wolves" />
      </div>
    </>
  );
}
