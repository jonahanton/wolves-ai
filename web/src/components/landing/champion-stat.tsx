"use client";

import { oneInN } from "@/lib/distribution";
import type { BoardRow } from "@/lib/derive";
import { formatPct1 } from "@/lib/format";
import { chartColour } from "@/lib/team-colours";

interface ChampionStatProps {
  row: BoardRow;
}

export function ChampionStat({ row }: ChampionStatProps) {
  const freq = oneInN(row.prob);
  const colour = chartColour(row.teamId);
  return (
    <div className="flex flex-wrap items-center justify-center gap-x-[clamp(12px,1.6vw,22px)] gap-y-2 text-center">
      <span
        className="font-display text-[clamp(42px,5.4vw,68px)] font-extrabold leading-[0.9] tracking-[-0.04em] tabular-nums"
        style={{ color: colour }}
      >
        {freq ? (
          <>
            1 <span className="font-bold">in</span> {freq.denominator}
          </>
        ) : (
          "—"
        )}
      </span>
      <span className="font-display text-[clamp(18px,2vw,26px)] font-semibold tracking-[-0.01em] text-cream">
        Chance {row.name} are world champions{" "}
        <span className="font-normal tabular-nums text-cream-dim">({formatPct1(row.prob)})</span>
      </span>
    </div>
  );
}
