import { Sparkline } from "@/components/charts/sparkline";
import { formatPct, frequencyFrame } from "@/lib/format";
import type { EnglandBlock } from "@/lib/snapshot";

const FINISH_ROWS: [string, string][] = [
  ["win_group", "Win Group L"],
  ["runner_up", "Finish second"],
  ["third_qualified", "Through in third"],
];

const REACH_COLUMNS: [string, string][] = [
  ["r16", "Last 16"],
  ["qf", "Quarters"],
  ["sf", "Semis"],
  ["final", "Final"],
  ["champion", "Champions"],
];

interface FinishSummaryProps {
  england: EnglandBlock;
}

export function FinishSummary({ england }: FinishSummaryProps) {
  const champion = england.reach_probs.champion ?? 0;
  return (
    <section className="rounded-xl border bg-card p-4" aria-label="How England finish">
      <h2 className="font-semibold">How do we get out of Group L?</h2>
      <div className="mt-3 space-y-1.5">
        {FINISH_ROWS.map(([key, label]) => (
          <div key={key} className="flex items-baseline justify-between text-sm">
            <span>{label}</span>
            <span className="tabular-nums font-medium">{formatPct(england.finish_probs[key] ?? 0)}</span>
          </div>
        ))}
      </div>
      <div className="mt-4 flex justify-between border-t pt-3 text-center">
        {REACH_COLUMNS.map(([key, label]) => (
          <div key={key} className="flex flex-col">
            <span className="text-base font-semibold tabular-nums">{formatPct(england.reach_probs[key] ?? 0)}</span>
            <span className="text-[11px] text-muted-foreground">{label}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center justify-between border-t pt-3">
        <p className="text-xs text-muted-foreground">
          England lift the trophy in {frequencyFrame(champion) ?? "no sims"}
        </p>
        <Sparkline values={[champion]} width={56} height={18} />
      </div>
    </section>
  );
}
