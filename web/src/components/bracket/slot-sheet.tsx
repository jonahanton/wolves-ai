import { ProbBar } from "@/components/charts/prob-bar";
import { VenueChips } from "@/components/path/venue-chips";
import { BottomSheet } from "@/components/ui/sheet";
import type { SideView, SlotView } from "@/lib/bracket-view";

function SideDistribution({ side }: { side: SideView }) {
  return (
    <section className="py-3">
      <h3 className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {side.description}
      </h3>
      <div className="space-y-1.5">
        {side.candidates.map((candidate, i) => (
          <ProbBar key={candidate.teamId} label={candidate.name} prob={candidate.prob} highlight={i === 0} />
        ))}
      </div>
    </section>
  );
}

interface SlotSheetProps {
  slot: SlotView | null;
  onClose: () => void;
}

export function SlotSheet({ slot, onClose }: SlotSheetProps) {
  return (
    <BottomSheet
      open={slot !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={slot ? `Match ${slot.match} · ${slot.stageLabel}` : ""}
    >
      {slot && (
        <div className="pb-2">
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            {slot.city} &middot; {slot.dateLabel}
            <VenueChips traits={slot.traits} />
          </p>
          <div className="mt-1 divide-y">
            <SideDistribution side={slot.home} />
            <SideDistribution side={slot.away} />
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Probabilities are how often each team lands here across the latest simulation run. The agent&apos;s
            per-slot reasoning arrives with the daily runs.
          </p>
        </div>
      )}
    </BottomSheet>
  );
}
