"use client";

import { useMemo, useState } from "react";
import { MeanModeNote } from "@/components/teams/mean-mode-note";
import { MetricTabs } from "@/components/teams/metric-tabs";
import { TeamRow } from "@/components/teams/team-row";
import { useFlipReorder } from "@/hooks/use-flip-reorder";
import type { BoardRow } from "@/lib/derive";
import type { Impact } from "@/lib/impact";
import { METRICS, type MetricKey, metricValue } from "@/lib/metrics";
import type { PlayedResultRow } from "@/lib/results";
import type { PairingMatrices } from "@/lib/sidecars";

interface TeamBoardProps {
  runLabel: string;
  board: BoardRow[];
  names: Record<string, string>;
  reachProbs: Record<string, Record<string, number>>;
  rounds: PairingMatrices["rounds"];
  results: PlayedResultRow[];
  impact: Impact | null;
}

const DEFAULT_COUNT = 12;

export function TeamBoard({
  runLabel,
  board,
  names,
  reachProbs,
  rounds,
  results,
  impact,
}: TeamBoardProps) {
  const [openTeamId, setOpenTeamId] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [metric, setMetric] = useState<MetricKey>("champion");

  const column = METRICS.find((m) => m.key === metric)?.column ?? "";
  const setRef = useFlipReorder(`${metric}-${showAll}`);

  const ranked = useMemo(
    () =>
      board
        .map((row) => ({
          row,
          value: metricValue(metric, row.prob, reachProbs[row.teamId] ?? {}),
        }))
        .sort((a, b) => b.value - a.value),
    [board, metric, reachProbs],
  );
  const visible = showAll ? ranked : ranked.slice(0, DEFAULT_COUNT);

  return (
    <div>
      <h1 className="font-display text-[clamp(20px,2.4vw,28px)] font-semibold tracking-[-0.02em] text-cream">
        Predicted outcomes for each nation
      </h1>
      <p className="mt-2 font-display text-[12px] font-medium tracking-[0.01em] text-cream-faint">
        Accurate as of last full run {runLabel} ET (NYC)
      </p>

      <div className="mt-[clamp(16px,2.4vh,26px)]">
        <MetricTabs selected={metric} onSelect={setMetric} />
      </div>
      <div
        aria-hidden
        className="mt-[clamp(10px,1.4vh,16px)] h-px bg-hairline"
      />

      <div className="flex items-center gap-3 pb-1 pt-2">
        <span className="w-5 shrink-0" />
        <span className="w-[clamp(96px,16vw,150px)] shrink-0" />
        <span className="max-w-[640px] flex-1 text-right font-mono text-[10.5px] font-medium uppercase tracking-[0.04em] text-cream-faint">
          {column}
        </span>
        <span className="w-[15px] shrink-0" />
      </div>

      <ol className="mt-1">
        {visible.map(({ row, value }, i) => (
          <TeamRow
            key={row.teamId}
            ref={setRef(row.teamId)}
            rank={i + 1}
            row={row}
            value={value}
            open={openTeamId === row.teamId}
            onToggle={() =>
              setOpenTeamId((id) => (id === row.teamId ? null : row.teamId))
            }
            reachProbs={reachProbs[row.teamId] ?? {}}
            rounds={rounds}
            results={results}
            names={names}
            impact={impact?.teams[row.teamId] ?? null}
          />
        ))}
      </ol>

      {ranked.length > DEFAULT_COUNT && (
        <button
          type="button"
          onClick={() => setShowAll((v) => !v)}
          aria-expanded={showAll}
          className="mt-3 font-display text-[13px] font-semibold text-cream-faint transition-colors hover:text-cream"
        >
          {showAll ? "Show fewer" : `Show all ${ranked.length} teams`}
        </button>
      )}

      <MeanModeNote />
    </div>
  );
}
