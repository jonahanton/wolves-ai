import { ProbBar } from "@/components/charts/prob-bar";
import { formatPct } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { SideView, SlotView } from "@/lib/bracket-view";

function Side({ side }: { side: SideView }) {
  const top = side.candidates[0];
  const more = side.candidates.length - 1;
  return (
    <div>
      <p className="text-[11px] text-muted-foreground">{side.description}</p>
      {top && (
        <div className="mt-1 flex items-center gap-2">
          <div className="flex-1">
            <ProbBar label={top.name} prob={top.prob} highlight gold={top.teamId === "england"} />
          </div>
          {more > 0 && <span className="shrink-0 text-[11px] text-muted-foreground">+{more} more</span>}
        </div>
      )}
    </div>
  );
}

interface SlotCardProps {
  slot: SlotView;
  onSelect: (slot: SlotView) => void;
}

export function SlotCard({ slot, onSelect }: SlotCardProps) {
  const england = slot.englandProb > 0;
  return (
    <button
      type="button"
      onClick={() => onSelect(slot)}
      className={cn(
        "sticker w-full p-3.5 text-left transition-transform duration-150 active:scale-[0.99]",
        england && "foil border-gold/60",
      )}
    >
      <header className="flex items-baseline justify-between gap-2">
        <h3 className={cn("text-sm font-semibold", england && "text-gold")}>
          Match {slot.match}
          {england && ` · England ${formatPct(slot.englandProb)}`}
        </h3>
        <span className="text-xs text-muted-foreground">
          {slot.city} &middot; {slot.dateLabel}
        </span>
      </header>
      <div className="mt-2 space-y-2.5">
        <Side side={slot.home} />
        <Side side={slot.away} />
      </div>
      {slot.rationale && (
        <p className="mt-2 line-clamp-2 border-t border-dashed pt-2 text-xs text-muted-foreground">
          {slot.rationale}
        </p>
      )}
    </button>
  );
}
