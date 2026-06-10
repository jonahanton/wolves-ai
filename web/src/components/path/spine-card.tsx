import { ProbBar } from "@/components/charts/prob-bar";
import type { SpineStageView } from "@/lib/spine-view";

interface SpineCardProps {
  stage: SpineStageView;
  featured?: boolean;
}

export function SpineCard({ stage, featured = false }: SpineCardProps) {
  return (
    <article className={`sticker p-3 ${featured ? "foil" : ""}`}>
      <header className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">{stage.stageLabel}</h3>
        <span className="text-xs text-muted-foreground">
          {stage.city} &middot; {stage.dateLabel}
        </span>
      </header>
      {stage.venueLabel && <p className="mt-0.5 text-xs text-muted-foreground">{stage.venueLabel}</p>}
      <div className="mt-2 space-y-1.5">
        {stage.opponents.map((opponent, i) => (
          <ProbBar key={opponent.teamId} label={opponent.name} prob={opponent.prob} highlight={i === 0} />
        ))}
      </div>
      {stage.moreCount > 0 && <p className="mt-1.5 text-xs text-muted-foreground">+{stage.moreCount} more</p>}
      <p className="mt-2 border-t border-dashed pt-2 text-xs text-muted-foreground">
        {stage.rationale ?? "The agent's read on this tie lands with the daily run."}
      </p>
    </article>
  );
}
