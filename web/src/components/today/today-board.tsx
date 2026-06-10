"use client";

import { TodayHero } from "@/components/today/today-hero";
import { WhatMoved } from "@/components/today/what-moved";
import { useSnapshotHistory } from "@/hooks/use-snapshot-history";
import { computeDeltas, type SnapshotSummary } from "@/lib/derive";
import { metricSeries, previousSummary } from "@/lib/snapshot-history";

const HERO_METRIC = "reach:r32";

interface TodayBoardProps {
  summary: SnapshotSummary;
  heroProb: number;
}

export function TodayBoard({ summary, heroProb }: TodayBoardProps) {
  const entries = useSnapshotHistory(summary);
  const previous = entries ? previousSummary(entries, summary.runId) : null;

  return (
    <>
      <TodayHero
        prob={heroProb}
        previousProb={previous?.metrics[HERO_METRIC] ?? null}
        series={entries ? metricSeries(entries, HERO_METRIC) : []}
      />
      <WhatMoved hydrated={entries !== null} chips={previous ? computeDeltas(summary, previous) : null} />
    </>
  );
}
