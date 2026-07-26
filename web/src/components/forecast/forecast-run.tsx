"use client";

import { ChevronLeft } from "lucide-react";
import Link from "next/link";
import { HeadlineMovers } from "@/components/forecast/headline-movers";
import { PredictionBoard } from "@/components/forecast/prediction-board";
import { ReadingList } from "@/components/forecast/reading-list";
import { ScenarioCases } from "@/components/forecast/scenario-cases";
import { TheNumbers } from "@/components/forecast/the-numbers";
import type { BoardRow } from "@/lib/derive";
import type { Mover, ReadingItem, Working } from "@/lib/forecast";
import { formatRunStampEastern } from "@/lib/format";
import type { CampOut, ScenarioWeightOut, TeamDriver, TeamStoryOut } from "@/lib/snapshot";
import type { CellShape } from "@/lib/sidecars";

interface ForecastRunProps {
  archiveDay: string;
  runStamp: string;
  phase: string | null;
  headline: string;
  board: BoardRow[];
  reachProbs: Record<string, Record<string, number>>;
  names: Record<string, string>;
  movers: Mover[];
  championCells: Record<string, CellShape>;
  xMax: number;
  camps: CampOut[];
  weights: ScenarioWeightOut[];
  drivers: Record<string, TeamDriver>;
  stories: Record<string, TeamStoryOut>;
  sources: ReadingItem[];
  workings: Working[];
  meta: string[];
}

function Section({ children }: { children: React.ReactNode }) {
  return (
    <>
      <div className="my-[clamp(28px,4.5vh,48px)] h-px bg-hairline" />
      {children}
    </>
  );
}

export function ForecastRun(props: ForecastRunProps) {
  const { board, names } = props;
  const hasScenarios = props.camps.length > 0 && board.some((row) => props.championCells[row.teamId]);

  return (
    <article className="mx-auto max-w-[680px]">
      <Link
        href={`/archive/${props.archiveDay}/forecast`}
        className="flex items-center gap-1 font-display text-[13px] font-medium text-cream-faint transition-colors hover:text-cream-dim"
      >
        <ChevronLeft size={14} className="shrink-0" />
        Forecasts
      </Link>

      <h1 className="mt-3 font-display text-[clamp(20px,3vw,28px)] font-semibold tracking-[-0.02em] text-cream">
        Forecast @ {formatRunStampEastern(props.runStamp)} ET
        {props.phase && <span className="text-cream-dim"> ({props.phase})</span>}
      </h1>
      {props.meta.length > 0 && (
        <p className="mt-1.5 font-mono text-[12px] tabular-nums text-cream-faint">{props.meta.join(" · ")}</p>
      )}

      {props.headline && (
        <p className="mt-[clamp(16px,2.5vh,28px)] font-display text-[clamp(14px,1.6vw,16.5px)] font-light leading-relaxed text-cream-dim">
          {props.headline}
        </p>
      )}

      {board.length > 0 && (
        <div className="mt-[clamp(28px,4vh,44px)]">
          <PredictionBoard board={board} reachProbs={props.reachProbs} names={names} />
        </div>
      )}

      {props.movers.length > 0 && (
        <Section>
          <HeadlineMovers movers={props.movers} />
        </Section>
      )}

      {hasScenarios && (
        <Section>
          <ScenarioCases
            board={board}
            names={names}
            championCells={props.championCells}
            xMax={props.xMax}
            camps={props.camps}
            weights={props.weights}
            drivers={props.drivers}
            stories={props.stories}
          />
        </Section>
      )}

      {props.sources.length > 0 && (
        <Section>
          <ReadingList sources={props.sources} />
        </Section>
      )}

      {props.workings.length > 0 && (
        <Section>
          <TheNumbers workings={props.workings} />
        </Section>
      )}
    </article>
  );
}
