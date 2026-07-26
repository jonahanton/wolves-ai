"use client";

import { ChevronRight } from "lucide-react";
import { forwardRef, useState } from "react";
import { ExitStageHistogram } from "@/components/teams/exit-stage-histogram";
import { OpponentDraw } from "@/components/teams/opponent-draw";
import type { BoardRow } from "@/lib/derive";
import { formatPct1 } from "@/lib/format";
import type { PlayedResultRow } from "@/lib/results";
import type { PairingMatrices } from "@/lib/sidecars";
import { chartColour } from "@/lib/team-colours";

interface TeamRowProps {
  rank: number;
  row: BoardRow;
  value: number;
  open: boolean;
  onToggle: () => void;
  reachProbs: Record<string, number>;
  rounds: PairingMatrices["rounds"];
  results: PlayedResultRow[];
  names: Record<string, string>;
}

export const TeamRow = forwardRef<HTMLLIElement, TeamRowProps>(function TeamRow(
  { rank, row, value, open, onToggle, reachProbs, rounds, results, names },
  ref,
) {
  const colour = chartColour(row.teamId);
  const [view, setView] = useState<"outcomes" | "opponents">("outcomes");
  const [everOpened, setEverOpened] = useState(false);
  if (open && !everOpened) setEverOpened(true);

  const views = [
    {
      key: "outcomes" as const,
      label: `${row.name}'s outcomes`,
    },
    { key: "opponents" as const, label: `${row.name}'s opponents` },
  ];

  return (
    <li ref={ref} className="border-b border-hairline last:border-b-0">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-3 py-2.5 text-left"
      >
        <span className="w-5 shrink-0 text-right font-mono text-[12px] tabular-nums text-cream-faint">
          {rank}
        </span>
        <span className="w-[clamp(96px,16vw,150px)] shrink-0 truncate font-display text-[14px] font-semibold text-cream">
          {row.name}
        </span>
        <span className="flex max-w-[640px] flex-1 items-center gap-3">
          <span className="relative h-[8px] flex-1 overflow-hidden rounded-[2px] bg-cream/8">
            <span
              className="absolute inset-y-0 left-0 rounded-[2px] transition-[width] duration-[460ms] ease-[cubic-bezier(0.25,1,0.5,1)] motion-reduce:transition-none"
              style={{
                width: `${Math.min(100, value * 100)}%`,
                backgroundColor: colour,
                opacity: 0.85,
              }}
            />
          </span>
          <span
            className="w-12 shrink-0 text-right font-mono text-[12.5px] font-medium tabular-nums"
            style={{ color: colour }}
          >
            {formatPct1(value)}
          </span>
        </span>
        <ChevronRight
          size={15}
          className="shrink-0 text-cream-faint transition-transform duration-300 motion-reduce:transition-none"
          style={{ transform: open ? "rotate(90deg)" : "none" }}
        />
      </button>

      <div
        className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none"
        style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden" inert={!open}>
          {everOpened && (
            <div className="pb-6 pt-1">
              <div className="mb-4 flex flex-wrap items-center gap-x-[clamp(14px,2vw,26px)] gap-y-4 border-b border-hairline pb-2.5">
                {views.map((v) => {
                  const active = v.key === view;
                  return (
                    <button
                      key={v.key}
                      type="button"
                      onClick={() => setView(v.key)}
                      aria-pressed={active}
                      className="relative -my-2 py-2 text-left font-display text-[14px] font-semibold tracking-[-0.01em] text-cream transition-opacity hover:opacity-100"
                      style={{ opacity: active ? 1 : 0.4 }}
                    >
                      <span className="relative pb-1">
                        {v.label}
                        {active && (
                          <span
                            className="absolute inset-x-0 bottom-0 h-[2px] rounded-full"
                            style={{ backgroundColor: colour }}
                          />
                        )}
                      </span>
                    </button>
                  );
                })}
              </div>
              <div className="mx-auto max-w-[640px]">
                {view === "outcomes" ? (
                  <ExitStageHistogram
                    reachProbs={reachProbs}
                    colour={colour}
                    teamName={row.name}
                  />
                ) : (
                  <OpponentDraw
                    teamId={row.teamId}
                    teamName={row.name}
                    colour={colour}
                    rounds={rounds}
                    reachProbs={reachProbs}
                    results={results}
                    names={names}
                  />
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </li>
  );
});
