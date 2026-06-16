"use client";

import { oneInN } from "@/lib/distribution";
import type { BoardRow } from "@/lib/derive";
import { useCountUp } from "@/hooks/use-count-up";
import type { ImpactStage } from "@/lib/impact";
import { chartColour } from "@/lib/team-colours";

interface ChampionStatProps {
  row: BoardRow;
  impact?: ImpactStage;
}

const LONGSHOT = 0.005;

export function ChampionStat({ row, impact }: ChampionStatProps) {
  const freq = oneInN(row.prob);
  const colour = chartColour(row.teamId);
  const denominator = useCountUp(freq?.denominator ?? 1, 1);
  const pct = useCountUp(row.prob * 100);
  const longshot = row.prob < LONGSHOT;
  const movement = impact ? impact.fromResultsPp + impact.fromIngamePp : 0;
  const showMovement = impact && Math.abs(movement) >= impact.displayFloorPp;

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
          {row.name} are world champions{" "}
          <span className="font-normal tabular-nums text-cream-dim">({pct.toFixed(1)}%)</span>
        </span>
      </div>
      {showMovement && (
        <div className="mt-1 font-display text-[12.5px] font-medium text-cream-faint">
          Running estimate{" "}
          <span className="font-mono tabular-nums" style={{ color: colour }}>
            {(impact.estimated * 100).toFixed(1)}%
          </span>
          , {movement > 0 ? "+" : ""}
          {movement.toFixed(1)}pp since the full forecast
        </div>
      )}
    </div>
  );
}
