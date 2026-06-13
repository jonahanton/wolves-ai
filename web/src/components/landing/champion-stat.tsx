"use client";

import { oneInN } from "@/lib/distribution";
import type { BoardRow } from "@/lib/derive";
import { useCountUp } from "@/hooks/use-count-up";
import { chartColour } from "@/lib/team-colours";

interface ChampionStatProps {
  row: BoardRow;
}

const LONGSHOT = 0.005;

export function ChampionStat({ row }: ChampionStatProps) {
  const freq = oneInN(row.prob);
  const colour = chartColour(row.teamId);
  const denominator = useCountUp(freq?.denominator ?? 1, 1);
  const pct = useCountUp(row.prob * 100);
  const longshot = row.prob < LONGSHOT;

  if (longshot) {
    return (
      <div className="text-center font-display text-[clamp(18px,2vw,26px)] font-semibold tracking-[-0.01em] text-cream">
        We see no realistic chance of <span style={{ color: colour }}>{row.name}</span> winning the World Cup
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-center gap-x-[clamp(12px,1.6vw,22px)] gap-y-2 text-center">
      <span
        className="font-display text-[clamp(42px,5.4vw,68px)] font-extrabold leading-[0.9] tracking-[-0.04em] tabular-nums"
        style={{ color: colour }}
      >
        1 <span className="font-bold">in</span> {Math.round(denominator)}
      </span>
      <span className="font-display text-[clamp(18px,2vw,26px)] font-semibold tracking-[-0.01em] text-cream">
        {row.name} are world champions{" "}
        <span className="font-normal tabular-nums text-cream-dim">({pct.toFixed(1)}%)</span>
      </span>
    </div>
  );
}
