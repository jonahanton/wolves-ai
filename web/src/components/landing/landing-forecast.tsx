"use client";

import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { useResolved } from "@/hooks/use-resolved";
import { ChampionStat } from "@/components/landing/champion-stat";
import { EpistemicDistribution } from "@/components/landing/epistemic-distribution";
import { ForecastChart } from "@/components/landing/forecast-chart";
import { HeroVideo } from "@/components/landing/hero-video";
import { TeamSelector } from "@/components/landing/team-selector";
import type { BoardRow } from "@/lib/derive";
import { formatRunStampEastern } from "@/lib/format";
import { assembleChartData, type ChartImpactPoint, type ChartTeamInput, type FixtureResultView } from "@/lib/forecast-series";
import type { Impact } from "@/lib/impact";
import { resultLabel } from "@/lib/impact-view";
import { nextAgentRunIso } from "@/lib/run-schedule";
import type {
  CampOut,
  ScenarioWeightOut,
  TeamDriver,
  TeamStoryOut,
} from "@/lib/snapshot";
import type { CellShape } from "@/lib/sidecars";
import { chartColour } from "@/lib/team-colours";

interface LandingForecastProps {
  runLabel: string;
  teams: ChartTeamInput[];
  names: Record<string, string>;
  leaderId: string;
  board: BoardRow[];
  fullBoard: BoardRow[];
  championCells: Record<string, CellShape>;
  xMax: number;
  weights: ScenarioWeightOut[];
  camps: CampOut[];
  drivers: Record<string, TeamDriver>;
  stories: Record<string, TeamStoryOut>;
  impactPromise: Promise<Impact | null>;
}

export function LandingForecast(props: LandingForecastProps) {
  const {
    runLabel,
    teams,
    names,
    leaderId,
    board,
    fullBoard,
    championCells,
  } = props;
  const { xMax, weights, camps, drivers, stories, impactPromise } = props;
  const [selectedTeamId, setSelectedTeamId] = useState(leaderId);
  const impact = useResolved(impactPromise, null);
  const [nextRun, setNextRun] = useState<string | null>(null);
  useEffect(() => {
    const tick = () => setNextRun(formatRunStampEastern(nextAgentRunIso(new Date())));
    tick();
    const id = window.setInterval(tick, 60_000);
    return () => window.clearInterval(id);
  }, []);

  const data = useMemo(
    () => ({ ...assembleChartData(teams, [], names), results: impactResultTicks(impact) }),
    [teams, names, impact],
  );
  const selectedRow =
    fullBoard.find((row) => row.teamId === selectedTeamId) ?? fullBoard[0];
  const selectedCell = championCells[selectedTeamId];
  const overflow = fullBoard.filter(
    (row) => !board.some((b) => b.teamId === row.teamId),
  );
  const othersCount = overflow.filter(
    (row) => row.teamId !== selectedTeamId,
  ).length;

  const hasDistribution = selectedCell && selectedRow;
  const colour = chartColour(selectedTeamId);
  const impacts = useMemo(() => chartImpacts(impact), [impact]);

  const renderDistribution = () =>
    hasDistribution ? (
      <EpistemicDistribution
        cell={selectedCell}
        teamName={selectedRow.name}
        colour={colour}
        xMax={xMax}
        weights={weights}
        camps={camps}
        driver={drivers[selectedTeamId]}
        story={stories[selectedTeamId]}
      />
    ) : null;

  return (
    <>
      <HeroVideo>
        <div className="wrap">
          <h1 className="hero-title text-cream">
            Forecasting the winner of the World Cup
          </h1>
          <div className="mt-[clamp(6px,1vh,10px)] flex flex-col gap-2 border-t border-hairline pt-[clamp(4px,0.7vh,7px)] sm:flex-row sm:items-center sm:justify-between sm:gap-4">
            <span className="font-display text-[12px] font-medium leading-snug tracking-[0.01em] text-cream-faint">
              Last run {runLabel} ET
              {nextRun && <span className="text-cream-faint/70"> · Next run {nextRun} ET</span>}
            </span>
            <TeamSelector
              segments={board}
              overflow={overflow}
              selectedTeamId={selectedTeamId}
              onSelect={setSelectedTeamId}
            />
          </div>

          <div
            className={clsx(
              "mt-[clamp(8px,1.4vh,16px)] grid grid-cols-1 gap-x-[clamp(20px,3vw,44px)]",
              hasDistribution
                ? "lg:grid-cols-[1.25fr_1fr]"
                : "lg:grid-cols-[minmax(0,56%)] lg:justify-center",
            )}
          >
            <div className="min-w-0">
              <ForecastChart
                data={data}
                selectedTeamId={selectedTeamId}
                othersCount={othersCount}
                onSelectTeam={setSelectedTeamId}
                ariaLabel="Chance of winning the World Cup over time"
                impacts={impacts}
              />
            </div>

            {hasDistribution && (
              <div className="hidden min-w-0 lg:block lg:border-l lg:border-hairline lg:pl-[clamp(20px,2.5vw,40px)]">
                {renderDistribution()}
              </div>
            )}
          </div>

          <div className="mt-[clamp(10px,1.6vh,20px)] flex justify-center">
            {selectedRow && <ChampionStat row={selectedRow} impact={impact?.teams[selectedTeamId]?.title} />}
          </div>
        </div>
      </HeroVideo>

      {hasDistribution && (
        <section className="wrap @container lg:hidden">
          <div
            aria-hidden
            className="h-[2px] rounded-full transition-colors duration-300"
            style={{ backgroundColor: colour }}
          />
          <div className="mt-[clamp(20px,3.5vh,40px)]">{renderDistribution()}</div>
        </section>
      )}
    </>
  );
}

function chartImpacts(impact: Impact | null): Record<string, ChartImpactPoint> | null {
  if (!impact) return null;
  const out: Record<string, ChartImpactPoint> = {};
  for (const [teamId, team] of Object.entries(impact.teams)) {
    const title = team.title;
    out[teamId] = {
      teamId,
      fromResultsPp: title.fromResultsPp,
      fromIngamePp: title.fromIngamePp,
      displayFloorPp: title.displayFloorPp,
    };
  }
  return out;
}

function impactResultTicks(impact: Impact | null): FixtureResultView[] {
  return (impact?.resultsSinceAgent ?? []).map((result) => ({
    t: Date.parse(result.fetchedAt ?? impact?.generatedAt ?? ""),
    label: resultLabel(result),
  }));
}
