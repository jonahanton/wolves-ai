import { DeltaBadge } from "@/components/ui/delta-badge";
import { PctValue } from "@/components/ui/pct-value";
import type { DeltaChip } from "@/lib/derive";

interface WhatMovedProps {
  hydrated: boolean;
  chips: DeltaChip[] | null;
}

export function WhatMoved({ hydrated, chips }: WhatMovedProps) {
  return (
    <section aria-label="What moved">
      <h2 className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">What moved</h2>
      {!hydrated && <div className="h-8 w-2/3 animate-pulse rounded-lg bg-secondary" />}
      {hydrated && chips === null && (
        <p className="text-sm text-muted-foreground">
          First snapshot on this device. Movement appears after the next run.
        </p>
      )}
      {hydrated && chips?.length === 0 && (
        <p className="text-sm text-muted-foreground">Nothing meaningful moved overnight.</p>
      )}
      {chips && chips.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {chips.map((chip) => (
            <span
              key={chip.key}
              className="inline-flex items-center gap-1.5 rounded-lg border bg-card px-2.5 py-1.5 text-sm"
            >
              <span className="font-medium">{chip.label}</span>
              <PctValue prob={chip.prob} className="font-normal text-muted-foreground" />
              <DeltaBadge deltaPts={chip.deltaPts} />
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
