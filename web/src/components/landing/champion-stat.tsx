"use client";

import { oneInN } from "@/lib/distribution";
import type { BoardRow } from "@/lib/derive";
import { useCountUp } from "@/hooks/use-count-up";
import { chartColour } from "@/lib/team-colours";

interface ChampionStatProps {
  row: BoardRow;
}

const LONGSHOT = 0.005;
// Rounds to 100.0%: the title is settled, so a "1 in N" ratio would be nonsense.
const DECIDED = 0.9995;

export function ChampionStat({ row }: ChampionStatProps) {
  const freq = oneInN(row.prob);
  const colour = chartColour(row.teamId);
  const denominator = useCountUp(freq?.denominator ?? 1, 1);
  const longshot = row.prob < LONGSHOT;

  if (row.prob >= DECIDED) {
    return (
      <div className="text-center font-display text-[clamp(24px,3vw,38px)] font-extrabold tracking-[-0.02em]">
        <span style={{ color: colour }}>{row.name}</span>{" "}
        <span className="text-cream">are world champions</span>
      </div>
    );
  }

  if (longshot) {
    return (
      <div className="text-center font-display text-[clamp(18px,2vw,26px)] font-semibold tracking-[-0.01em] text-cream">
        We see no realistic chance of <span style={{ color: colour }}>{row.name}</span> winning the World Cup
      </div>
    );
  }

  return (
    <div className="text-center">
      <div className="flex flex-wrap items-center justify-center gap-x-[clamp(12px,1.6vw,22px)] gap-y-2">
        <span
          className="font-display text-[clamp(42px,5.4vw,68px)] font-extrabold leading-[0.9] tracking-[-0.04em] tabular-nums"
          style={{ color: colour }}
        >
          1 <span className="font-bold">in</span> {Math.round(denominator)}
        </span>
        <span className="font-display text-[clamp(18px,2vw,26px)] font-semibold tracking-[-0.01em] text-cream">
          {row.name} are world champions
        </span>
      </div>
    </div>
  );
}
