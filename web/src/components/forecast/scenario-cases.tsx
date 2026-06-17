"use client";

import { useState } from "react";
import { SectionTitle } from "@/components/forecast/section-title";
import { EpistemicDistribution } from "@/components/landing/epistemic-distribution";
import { TeamSelector } from "@/components/landing/team-selector";
import type { BoardRow } from "@/lib/derive";
import { campPalette } from "@/lib/distribution";
import { chartColour } from "@/lib/team-colours";
import type { CampOut, ScenarioWeightOut, TeamDriver, TeamStoryOut } from "@/lib/snapshot";
import type { CellShape } from "@/lib/sidecars";

interface ScenarioCasesProps {
  board: BoardRow[];
  names: Record<string, string>;
  championCells: Record<string, CellShape>;
  xMax: number;
  camps: CampOut[];
  weights: ScenarioWeightOut[];
  drivers: Record<string, TeamDriver>;
  stories: Record<string, TeamStoryOut>;
}

const SEGMENTS = 4;

export function ScenarioCases(props: ScenarioCasesProps) {
  const { board, names, championCells, camps } = props;
  const withCell = board.filter((row) => championCells[row.teamId]);
  const [selectedTeamId, setSelectedTeamId] = useState(withCell[0]?.teamId ?? board[0]?.teamId ?? "");

  const segments = withCell.slice(0, SEGMENTS);
  const overflow = withCell.slice(SEGMENTS);
  const selectedRow = board.find((row) => row.teamId === selectedTeamId) ?? withCell[0];
  const cell = championCells[selectedTeamId];
  const palette = campPalette(camps.map((c) => c.key));

  if (!cell || !selectedRow) return null;

  return (
    <section>
      <SectionTitle hint="Each world is a distinct posterior over team strengths; the forecast is their weight-averaged mixture.">
        Different plausible worlds
      </SectionTitle>

      <ul className="space-y-1.5">
        {camps.map((camp) => (
          <li key={camp.key} className="flex items-baseline gap-2">
            <span aria-hidden className="h-1.5 w-1.5 shrink-0 translate-y-[-1px]" style={{ backgroundColor: palette[camp.key] }} />
            <span className="w-9 shrink-0 font-mono text-[12.5px] font-semibold tabular-nums text-cream-dim">
              {Math.round((camp.weight ?? 0) * 100)}%
            </span>
            <span className="min-w-0 font-display text-[13.5px] leading-snug text-cream">{camp.label ?? camp.key}</span>
          </li>
        ))}
      </ul>

      <div className="mt-[clamp(18px,3vh,30px)] flex items-center justify-between gap-4">
        <p className="font-display text-[13px] font-medium text-cream-faint">Distribution of winning the World Cup by team</p>
        <TeamSelector
          segments={segments}
          overflow={overflow}
          selectedTeamId={selectedTeamId}
          onSelect={setSelectedTeamId}
        />
      </div>

      <div className="mt-[clamp(12px,2vh,18px)]">
        <EpistemicDistribution
          cell={cell}
          teamName={names[selectedTeamId] ?? selectedRow.name}
          colour={chartColour(selectedTeamId)}
          xMax={props.xMax}
          weights={props.weights}
          camps={props.camps}
          driver={props.drivers[selectedTeamId]}
          story={props.stories[selectedTeamId]}
        />
      </div>
    </section>
  );
}
