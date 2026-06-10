"use client";

import { useEffect, useState } from "react";
import { Sparkline } from "@/components/charts/sparkline";
import { DeltaBadge } from "@/components/ui/delta-badge";
import { PctValue } from "@/components/ui/pct-value";
import { useRollingValue } from "@/hooks/use-rolling-value";
import { cn } from "@/lib/utils";

const SHIMMER_KEY = "wolves:hero-shimmer";
const SPARKLINE_MIN_RUNS = 3;

interface TodayHeroProps {
  prob: number;
  previousProb: number | null;
  series: number[];
}

export function TodayHero({ prob, previousProb, series }: TodayHeroProps) {
  const value = useRollingValue(prob, previousProb);
  const [shimmer, setShimmer] = useState(false);

  useEffect(() => {
    let raf = 0;
    try {
      if (!window.sessionStorage.getItem(SHIMMER_KEY)) {
        window.sessionStorage.setItem(SHIMMER_KEY, "1");
        raf = requestAnimationFrame(() => setShimmer(true));
      }
    } catch {
      return;
    }
    return () => cancelAnimationFrame(raf);
  }, []);

  const deltaPts = previousProb === null ? 0 : Math.round((prob - previousProb) * 1000) / 10;

  return (
    <section aria-label="Headline forecast">
      <p className="font-display text-lg font-medium tracking-tight">England get out of Group L in</p>
      <div className="mt-1 flex items-end gap-3">
        <PctValue
          prob={value}
          className={cn(
            "inline-block font-display text-7xl leading-none tracking-tight text-gold",
            shimmer && "foil-once",
          )}
        />
        {deltaPts !== 0 && <DeltaBadge deltaPts={deltaPts} className="mb-1.5" />}
      </div>
      <p className="mt-1.5 text-sm text-muted-foreground">of simulations</p>
      {series.length >= SPARKLINE_MIN_RUNS && (
        <div className="mt-2 flex items-center gap-2">
          <Sparkline values={series} width={132} height={24} />
          <span className="text-xs text-muted-foreground">last {series.length} runs</span>
        </div>
      )}
    </section>
  );
}
