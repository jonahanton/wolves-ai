import { ProbBar } from "@/components/charts/prob-bar";
import { VenueChips } from "@/components/path/venue-chips";
import type { SpineStageView } from "@/lib/spine-view";

interface SpineCardProps {
  stage: SpineStageView;
  tilt: "l" | "r";
  featured?: boolean;
}

export function SpineCard({ stage, tilt, featured = false }: SpineCardProps) {
  return (
    <article className={`sticker p-3.5 sticker-tilt-${tilt} ${featured ? "foil" : ""}`}>
      <header className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">{stage.stageLabel}</h3>
        <span className="text-xs text-muted-foreground">
          {stage.city} &middot; {stage.dateLabel}
        </span>
      </header>
      <div className="mt-1">
        <VenueChips traits={stage.traits} />
      </div>
      <div className="mt-2 space-y-1.5">
        {stage.opponents.map((opponent, i) => (
          <ProbBar key={opponent.teamId} label={opponent.name} prob={opponent.prob} highlight={i === 0} />
        ))}
      </div>
      {stage.moreCount > 0 && <p className="mt-1.5 text-xs text-muted-foreground">+{stage.moreCount} more</p>}
    </article>
  );
}
