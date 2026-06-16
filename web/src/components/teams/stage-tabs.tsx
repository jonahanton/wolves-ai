"use client";

import { Check } from "lucide-react";
import type { RoundBar, StreamRound } from "@/lib/opponents";

interface StageTabsProps {
  rounds: RoundBar[];
  selected: StreamRound;
  colour: string;
  onSelect: (round: StreamRound) => void;
  deltas?: Partial<Record<StreamRound, number | null>>;
}

export function StageTabs({ rounds, selected, colour, onSelect, deltas = {} }: StageTabsProps) {
  return (
    <div className="flex flex-wrap items-center gap-x-[clamp(12px,1.8vw,22px)] gap-y-1.5">
      {rounds.map((r) => {
        const active = r.round === selected;
        return (
          <button
            key={r.round}
            type="button"
            onClick={() => onSelect(r.round)}
            aria-pressed={active}
            className="relative flex items-center gap-1 pb-1 font-display text-[13px] font-semibold tracking-[0.01em] text-cream transition-opacity hover:opacity-100"
            style={{ opacity: active ? 1 : 0.45 }}
          >
            {r.played && <Check size={12} className="shrink-0 text-cream-dim" strokeWidth={3} />}
            {r.label}
            {deltas[r.round] !== null && deltas[r.round] !== undefined && (
              <span className="font-mono text-[10px] font-semibold tabular-nums text-cream-faint">
                {deltas[r.round]! > 0 ? "+" : ""}
                {deltas[r.round]!.toFixed(1)}
              </span>
            )}
            {active && <span className="absolute inset-x-0 bottom-0 h-[2px] rounded-full" style={{ backgroundColor: colour }} />}
          </button>
        );
      })}
    </div>
  );
}
