"use client";

import { useMemo } from "react";
import {
  type CampMeta,
  DistributionCurve,
} from "@/components/landing/distribution-curve";
import { campMeans, ourCall } from "@/lib/distribution";
import type {
  CampOut,
  ScenarioWeightOut,
  TeamDriver,
  TeamStoryOut,
} from "@/lib/snapshot";
import type { CellShape } from "@/lib/sidecars";

interface EpistemicDistributionProps {
  cell: CellShape;
  teamName: string;
  colour: string;
  xMax: number;
  weights: ScenarioWeightOut[];
  camps: CampOut[];
  driver: TeamDriver | undefined;
  story: TeamStoryOut | undefined;
}

export function EpistemicDistribution(props: EpistemicDistributionProps) {
  const { cell, teamName, colour, xMax, weights, camps, story } = props;

  const callPct = useMemo(() => `${(ourCall(cell) * 100).toFixed(1)}%`, [cell]);
  const means = useMemo(() => campMeans(cell, weights), [cell, weights]);
  const campMeta = useMemo(
    () =>
      new Map<string, CampMeta>(
        camps.map((c) => [
          c.key,
          {
            key: c.key,
            label: c.label ?? c.key,
            summary: c.summary ?? "",
            prob: means[c.key] ?? 0,
          },
        ]),
      ),
    [camps, means],
  );

  return (
    <div>
      <div className="border-b border-hairline pb-3">
        {story?.summary && (
          <p className="font-display text-[clamp(16px,1.9vw,20px)] font-semibold leading-snug text-cream">
            {story.summary}
          </p>
        )}
        <p className="mt-2 font-display text-[13px] leading-snug text-cream-dim">
          <span
            className="tabular-nums font-semibold"
            style={{ color: colour }}
          >
            {callPct}
          </span>{" "}
          is the weighted average of{" "}
          <span className="font-semibold" style={{ color: colour }}>
            {teamName}
          </span>
          &rsquo;s chance of winning the World Cup across 200 simulated draws.
        </p>
      </div>

      <div className="mb-8 mt-5">
        <DistributionCurve
          cell={cell}
          xMax={xMax}
          weights={weights}
          campMeta={campMeta}
          colour={colour}
          why={story?.why}
        />
      </div>
    </div>
  );
}
