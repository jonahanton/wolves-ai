import Link from "next/link";
import { BoardRowItem } from "@/components/charts/board-row";
import { HeroVideo } from "@/components/landing/hero-video";
import { LandingForecast } from "@/components/landing/landing-forecast";
import { MachineSection } from "@/components/landing/machine-section";
import { MarketSection } from "@/components/landing/market-section";
import { RoadSection } from "@/components/landing/road-section";
import { ErrorState } from "@/components/shell/error-state";
import { Kicker } from "@/components/shell/kicker";
import { PhotoWall } from "@/components/walls/photo-wall";
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
import { loadRunRecords, loadSnapshotIndex, loadTeamHistory } from "@/lib/runs";

const SERIES_COLOURS = ["oklch(0.8 0.11 150)", "oklch(0.965 0.008 95 / 0.34)", "oklch(0.965 0.008 95 / 0.25)", "oklch(0.965 0.008 95 / 0.22)"];

export default async function LandingPage() {
  const [result, indexResult, recordsResult, marketReachResult, resultsResult] = await Promise.all([
    loadLatestSnapshot(),
    loadSnapshotIndex(),
    loadRunRecords(),
    loadMarketReach(),
    loadResults(),
  ]);
  if (!result.ok) return <ErrorState error={result.error} context="World Cup Superforecaster" />;
  const snapshot = result.data;
  const now = new Date();

  // The hero and chart speak for the agent's full forecast; live runs may be newer.
  const agentRef = orNull(indexResult)?.snapshots.find((ref) => ref.kind === "agent");
  const agentSnapshot =
    snapshot.run.kind === "agent" || !agentRef
      ? snapshot
      : (orNull(await loadSnapshot(agentRef.runId)) ?? snapshot);

  const hero = deriveHero(agentSnapshot);
  const board = titleBoard(snapshot, 6);
  const focusId = snapshot.focus.team_id;
  const names = Object.fromEntries(snapshot.teams.map((t) => [t.team_id, t.name]));

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
      <section className="relative">
        <HeroVideo />
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
      </section>

      <section className="relative border-t border-hairline py-[clamp(60px,10vh,120px)]">
        <PhotoWall family="wc" />
        <div className="wrap relative z-[1]">
          <Kicker>The field · 96 years of this</Kicker>
          <h2 className="statement">
            Forty-eight teams.
            <br />
            <b className="font-medium">Six that matter.</b>
          </h2>
          <div className="mt-[clamp(28px,5vh,48px)] max-w-[880px] border-t border-hairline">
            {board.map((row, index) => (
              <BoardRowItem
                key={row.teamId}
                row={row}
                rank={index + 1}
                featured={row.teamId === focusId}
                barMax={Math.max(0.26, board[0].prob * 1.1)}
              />
            ))}
          </div>
          <div className="mt-4 flex max-w-[880px] justify-between font-mono text-[12.5px] text-cream-faint">
            <span className="hidden sm:inline">published number · mkt = de-vigged market</span>
            <span className="sm:hidden">published</span>
            <Link href="/teams" className="border-b border-hairline pb-0.5">
              all 48 teams
            </Link>
          </div>
        </div>
      </section>

      <RoadSection snapshot={snapshot} now={now} />

      <FestivalBand family="euros" tag="Euros 2024 · the Wolves" />

      <MarketSection snapshot={snapshot} />

      <MachineSection
        snapshots={orNull(indexResult)?.snapshots ?? []}
        records={orNull(recordsResult)?.runs ?? []}
        nSims={snapshot.run.n_sims}
      />
    </>
  );
}
