import { formatPct } from "@/lib/format";
import type { WhatIfFixture } from "@/lib/snapshot";
import { whatIfDeltas } from "@/lib/team-view";

const OUTCOME_LABELS: Record<string, string> = { win: "Win", draw: "Draw", lose: "Lose" };

interface WhatIfPanelProps {
  fixture: WhatIfFixture;
  opponentName: string;
}

export function WhatIfPanel({ fixture, opponentName }: WhatIfPanelProps) {
  const deltas = whatIfDeltas(fixture);
  return (
    <div className="max-w-[880px]">
      <p className="lede mb-5">
        One result, three tournaments. What the {opponentName} game does to the bracket, versus today&apos;s number.
      </p>
      <div className="grid gap-px sm:grid-cols-3">
        {deltas.map((delta) => (
          <div key={delta.outcome} className="border border-hairline p-5">
            <div className="flex items-baseline justify-between">
              <span className="text-[19px] font-medium">{OUTCOME_LABELS[delta.outcome] ?? delta.outcome}</span>
              <span className="font-mono text-[12.5px] text-cream-faint">{formatPct(delta.prob)}</span>
            </div>
            <div className="mt-4 space-y-1.5 font-mono text-[14px]">
              <div className="flex justify-between">
                <span className="text-cream-faint">group win</span>
                <span className={delta.winGroupDeltaPp >= 0 ? "text-green" : "text-red"}>
                  {signed(delta.winGroupDeltaPp)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-cream-faint">title</span>
                <span className={delta.championDeltaPp >= 0 ? "text-green" : "text-red"}>
                  {signed(delta.championDeltaPp)}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function signed(pp: number): string {
  return `${pp >= 0 ? "+" : "−"}${Math.abs(pp).toFixed(1)}pp`;
}
