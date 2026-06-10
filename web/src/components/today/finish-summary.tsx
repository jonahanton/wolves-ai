import { PctValue } from "@/components/ui/pct-value";
import { formatPct, frequencyFrame } from "@/lib/format";
import type { FocusTeamBlock } from "@/lib/snapshot";

const REACH_COLUMNS: [string, string][] = [
  ["r16", "Last 16"],
  ["qf", "Quarters"],
  ["sf", "Semis"],
  ["final", "Final"],
  ["champion", "Champions"],
];

interface FinishSummaryProps {
  focus: FocusTeamBlock;
  name: string;
}

export function FinishSummary({ focus, name }: FinishSummaryProps) {
  const champion = focus.reach_probs.champion ?? 0;
  const finishRows: [string, string][] = [
    ["win_group", `Win Group ${focus.group}`],
    ["runner_up", "Finish second"],
    ["third_qualified", "Through in third"],
  ];
  return (
    <section className="rounded-xl border bg-card p-3" aria-label={`How ${name} finish`}>
      <h2 className="font-semibold">How do we get out of Group {focus.group}?</h2>
      <div className="mt-3 space-y-1.5">
        {finishRows.map(([key, label]) => (
          <div key={key} className="flex items-baseline justify-between text-sm">
            <span>{label}</span>
            <span className="font-medium">{formatPct(focus.finish_probs[key] ?? 0)}</span>
          </div>
        ))}
      </div>
      <div className="mt-4 flex justify-between border-t pt-3 text-center">
        {REACH_COLUMNS.map(([key, label]) => (
          <div key={key} className="flex flex-col">
            <PctValue prob={focus.reach_probs[key] ?? 0} className="text-base" />
            <span className="text-[11px] text-muted-foreground">{label}</span>
          </div>
        ))}
      </div>
      <p className="mt-3 border-t pt-3 text-xs text-muted-foreground">
        {name} lift the trophy in {frequencyFrame(champion) ?? "no sims"}
      </p>
    </section>
  );
}
