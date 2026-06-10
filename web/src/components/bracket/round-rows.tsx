import { formatPct } from "@/lib/format";
import type { RoundView, SideView, SlotView } from "@/lib/bracket-view";

function sideSummary(side: SideView): string {
  const top = side.candidates[0];
  return top ? `${top.name} ${formatPct(top.prob)}` : side.description;
}

interface RoundRowsProps {
  rounds: RoundView[];
  onSelect: (slot: SlotView) => void;
}

export function RoundRows({ rounds, onSelect }: RoundRowsProps) {
  return (
    <div className="space-y-5">
      {rounds.map((round) => (
        <section key={round.stage} aria-label={round.stageLabel}>
          <h2 className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            {round.stageLabel}
          </h2>
          <div className="divide-y rounded-xl border bg-card">
            {round.slots.map((slot) => (
              <button
                key={slot.match}
                type="button"
                onClick={() => onSelect(slot)}
                className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left text-sm"
              >
                <span className="truncate">
                  {sideSummary(slot.home)} <span className="text-muted-foreground">v</span>{" "}
                  {sideSummary(slot.away)}
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {slot.city} &middot; {slot.dateLabel}
                </span>
              </button>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
