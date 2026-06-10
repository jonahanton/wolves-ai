"use client";

import { useState } from "react";
import { SpineCard } from "@/components/path/spine-card";
import { Segmented } from "@/components/ui/segmented";
import { formatPct } from "@/lib/format";
import type { Finish } from "@/lib/snapshot";
import type { SpineView } from "@/lib/spine-view";

interface PathSpineProps {
  views: SpineView[];
}

export function PathSpine({ views }: PathSpineProps) {
  const [finish, setFinish] = useState<Finish>(views[0]?.finish ?? "win_group");
  const view = views.find((v) => v.finish === finish) ?? views[0];
  if (!view) return null;

  return (
    <section aria-label="England's central path">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-semibold">The road from Group L</h2>
        <Segmented
          options={views.map((v) => ({ value: v.finish, label: v.toggleLabel }))}
          value={view.finish}
          onChange={setFinish}
          className="w-44"
        />
      </div>
      <p className="mt-1.5 text-sm text-muted-foreground">
        {view.finishLabel}: {formatPct(view.prob)} of sims
      </p>
      <ol
        key={view.finish}
        className="mt-4 ml-2 space-y-4 border-l border-dashed border-[var(--border-strong)] pl-4 animate-[fade-up_150ms_var(--ease-out)]"
      >
        {view.stages.map((stage, i) => (
          <li key={stage.stage} className="relative">
            <span
              className="absolute top-6 -left-[21.5px] size-2.5 rounded-full border border-background bg-gold"
              aria-hidden
            />
            <SpineCard stage={stage} featured={i === 0} />
          </li>
        ))}
      </ol>
    </section>
  );
}
