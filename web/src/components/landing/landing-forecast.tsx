"use client";

import { useMemo, useState } from "react";
import { ChampionStat } from "@/components/landing/champion-stat";
import { ForecastChart } from "@/components/landing/forecast-chart";
import { HeroVideo } from "@/components/landing/hero-video";
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
}

export function LandingForecast(props: LandingForecastProps) {
  const { runLabel, teams, results, names, leaderId, board } = props;
  const [selectedTeamId, setSelectedTeamId] = useState(leaderId);

  const data = useMemo(() => assembleChartData(teams, results, names), [teams, results, names]);
  const selectedRow = board.find((row) => row.teamId === selectedTeamId) ?? board[0];

  return (
    <HeroVideo>
      <div className="wrap">
        <h1 className="hero-title text-cream">Forecasting the winner of the World Cup</h1>
        <div className="mt-[clamp(6px,1vh,10px)] border-t border-hairline pt-[clamp(4px,0.7vh,7px)]">
          <span className="font-display text-[12px] font-medium tracking-[0.01em] text-cream-faint">
            Last full run {runLabel} ET
          </span>
        </div>

        <div className="mt-[clamp(8px,1.4vh,16px)]">
          <ForecastChart
            data={data}
            selectedTeamId={selectedTeamId}
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
