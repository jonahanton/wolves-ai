"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import { ChampionStat } from "@/components/landing/champion-stat";
import { EpistemicDistribution } from "@/components/landing/epistemic-distribution";
import { ForecastChart } from "@/components/landing/forecast-chart";
import { HeroVideo } from "@/components/landing/hero-video";
import { TeamSelector } from "@/components/landing/team-selector";
import type { BoardRow } from "@/lib/derive";
import { assembleChartData, type ChartTeamInput } from "@/lib/forecast-series";
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
  leaderId: string;
  board: BoardRow[];
  fullBoard: BoardRow[];
  championCells: Record<string, CellShape>;
  xMax: number;
  weights: ScenarioWeightOut[];
  camps: CampOut[];
  drivers: Record<string, TeamDriver>;
  stories: Record<string, TeamStoryOut>;
}

export function LandingForecast(props: LandingForecastProps) {
  const {
    runLabel,
    teams,
    leaderId,
    board,
    fullBoard,
    championCells,
  } = props;
  const { xMax, weights, camps, drivers, stories } = props;
  const [selectedTeamId, setSelectedTeamId] = useState(leaderId);

  const data = useMemo(
    () => assembleChartData(teams),
    [teams],
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
              Archive forecast {runLabel} ET
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
              />
            </div>

            {hasDistribution && (
              <div className="hidden min-w-0 lg:block lg:border-l lg:border-hairline lg:pl-[clamp(20px,2.5vw,40px)]">
                {renderDistribution()}
              </div>
            )}
          </div>

          <div className="mt-[clamp(10px,1.6vh,20px)] flex justify-center">
            {selectedRow && <ChampionStat row={selectedRow} />}
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
