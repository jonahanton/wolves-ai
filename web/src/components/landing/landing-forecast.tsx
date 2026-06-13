"use client";

import { useMemo, useState } from "react";
import { ChampionStat } from "@/components/landing/champion-stat";
import { ForecastChart } from "@/components/landing/forecast-chart";
import { HeroVideo } from "@/components/landing/hero-video";
import { TeamSelector } from "@/components/landing/team-selector";
import type { BoardRow } from "@/lib/derive";
import { assembleChartData, type ChartTeamInput } from "@/lib/forecast-series";
import type { PlayedResultRow } from "@/lib/results";

interface LandingForecastProps {
  runLabel: string;
  teams: ChartTeamInput[];
  results: PlayedResultRow[];
  names: Record<string, string>;
  leaderId: string;
  board: BoardRow[];
  fullBoard: BoardRow[];
}

export function LandingForecast(props: LandingForecastProps) {
  const { runLabel, teams, results, names, leaderId, board, fullBoard } = props;
  const [selectedTeamId, setSelectedTeamId] = useState(leaderId);

  const data = useMemo(() => assembleChartData(teams, results, names), [teams, results, names]);
  const selectedRow = fullBoard.find((row) => row.teamId === selectedTeamId) ?? fullBoard[0];
  const overflow = fullBoard.filter((row) => !board.some((b) => b.teamId === row.teamId));
  const othersCount = overflow.filter((row) => row.teamId !== selectedTeamId).length;

  return (
    <HeroVideo>
      <div className="wrap">
        <h1 className="hero-title text-cream">Forecasting the winner of the World Cup</h1>
        <div className="mt-[clamp(6px,1vh,10px)] flex items-center justify-between gap-4 border-t border-hairline pt-[clamp(4px,0.7vh,7px)]">
          <span className="font-display text-[12px] font-medium tracking-[0.01em] text-cream-faint">
            Last full run {runLabel} ET
          </span>
          <TeamSelector
            segments={board}
            overflow={overflow}
            selectedTeamId={selectedTeamId}
            onSelect={setSelectedTeamId}
          />
        </div>

        <div className="mt-[clamp(8px,1.4vh,16px)]">
          <ForecastChart
            data={data}
            selectedTeamId={selectedTeamId}
            othersCount={othersCount}
            onSelectTeam={setSelectedTeamId}
            ariaLabel="Chance of winning the World Cup over time"
          />
        </div>

        <div className="mt-[clamp(18px,3vh,40px)] flex justify-center">
          {selectedRow && <ChampionStat row={selectedRow} />}
        </div>
      </div>
    </HeroVideo>
  );
}
