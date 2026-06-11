import { ProbBar } from "@/components/charts/prob-bar";
import { BottomSheet } from "@/components/ui/sheet";
import type { SideView, SlotView } from "@/lib/bracket-view";

function SideDistribution({ side, focusTeamId }: { side: SideView; focusTeamId: string }) {
  return (
    <section className="py-3">
      <h3 className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
        {side.description}
      </h3>
      <div className="space-y-1.5">
        {side.candidates.map((candidate, i) => (
          <ProbBar
            key={candidate.teamId}
            label={candidate.name}
            prob={candidate.prob}
            highlight={i === 0}
            gold={candidate.teamId === focusTeamId}
          />
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
          <p className="text-sm text-muted-foreground">
            {slot.city} &middot; {slot.dateLabel}
            {slot.venueLabel && <span className="block">{slot.venueLabel}</span>}
          </p>
          <div className="mt-1 divide-y">
            <SideDistribution side={slot.home} focusTeamId={slot.focusTeamId} />
            <SideDistribution side={slot.away} focusTeamId={slot.focusTeamId} />
          </div>
          <p className="mt-1 border-t border-dashed pt-3 text-sm">
            {slot.rationale ?? (
              <span className="text-xs text-muted-foreground">
                Probabilities are how often each team lands here across the latest simulation run. The
                agent&apos;s read on this tie lands with the daily run.
              </span>
            )}
          </p>
        </div>
      )}
    </BottomSheet>
  );
}
