import { BoardRowItem } from "@/components/charts/board-row";
import { SeriesChart } from "@/components/charts/series-chart";
import { HeroVideo } from "@/components/landing/hero-video";
import { LandingHero } from "@/components/landing/landing-hero";
import { MachineSection } from "@/components/landing/machine-section";
import { MarketSection } from "@/components/landing/market-section";
import { RoadSection } from "@/components/landing/road-section";
import { ErrorState } from "@/components/shell/error-state";
import { Kicker } from "@/components/shell/kicker";
import { PhotoWall } from "@/components/walls/photo-wall";
import { FestivalBand } from "@/components/walls/festival-band";
import { orNull } from "@/lib/api";
import { deriveHero, titleBoard } from "@/lib/derive";
import { formatUpdated } from "@/lib/format";
import { loadLiveState } from "@/lib/live";
import { loadLatestSnapshot } from "@/lib/load-snapshot";
import { loadRunRecords, loadSnapshotIndex, loadTeamHistory } from "@/lib/runs";
import type { TeamSeries } from "@/lib/series";

const SERIES_COLOURS = ["oklch(0.8 0.11 150)", "oklch(0.965 0.008 95 / 0.34)", "oklch(0.965 0.008 95 / 0.25)", "oklch(0.965 0.008 95 / 0.22)"];

export default async function LandingPage() {
  const [result, liveResult, indexResult, recordsResult] = await Promise.all([
    loadLatestSnapshot(),
    loadLiveState(),
    loadSnapshotIndex(),
    loadRunRecords(),
  ]);
  if (!result.ok) return <ErrorState error={result.error} context="World Cup Superforecaster" />;
  const snapshot = result.data;

  const hero = deriveHero(snapshot);
  const board = titleBoard(snapshot, 6);
  const focusId = snapshot.focus.team_id;
  const names = Object.fromEntries(snapshot.teams.map((t) => [t.team_id, t.name]));

  const chartTeams = [...new Set([...board.slice(0, 4).map((row) => row.teamId), focusId])];
  const histories = await Promise.all(chartTeams.map((teamId) => loadTeamHistory(teamId)));
  const series: TeamSeries[] = chartTeams.map((teamId, i) => ({
    teamId,
    name: names[teamId] ?? teamId,
    featured: teamId === focusId,
    colour: teamId === focusId ? "oklch(0.69 0.19 25)" : SERIES_COLOURS[i % SERIES_COLOURS.length],
    points: orNull(histories[i])?.points ?? [],
  }));

  const restHero = (
    <section className="relative">
      <HeroVideo />
      <div className="wrap relative pt-[clamp(90px,18svh,170px)] pb-[clamp(56px,9vh,100px)]">
        <Kicker>World Cup Superforecaster · run {formatUpdated(snapshot.run.created_at)}</Kicker>
        <h1 className="statement statement-hero">
          {hero.lead}
          <br />
          <b className="font-medium text-red">{hero.focusLine}</b>
        </h1>
        <p className="lede mt-[18px]">
          Tens of thousands of simulated tournaments a day, an AI superforecaster reading the news, the market
          keeping us honest.
        </p>
        <div className="mt-3 font-mono text-[11px] uppercase tracking-[0.12em] text-cream-faint">
          Euros 2024 · the Wolves
        </div>
        <div className="mt-[clamp(30px,5vh,52px)]">
          <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
            <span className="font-mono text-[13px] uppercase tracking-[0.14em] text-cream-dim">
              Chance of winning the World Cup
            </span>
            <span className="font-mono text-[12px] text-cream-faint">
              ◆ <b className="text-cream-dim">agent run</b> · the published number
            </span>
          </div>
          <SeriesChart series={series} ariaLabel="Title probability over published runs" />
        </div>
      </div>
    </section>
  );

  return (
    <>
      <LandingHero initialLive={orNull(liveResult)} focusId={focusId} names={names} restHero={restHero} />

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
            <a href="/teams" className="border-b border-hairline pb-0.5">
              all 48 teams
            </a>
          </div>
        </div>
      </section>

      <RoadSection snapshot={snapshot} now={new Date()} />

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
