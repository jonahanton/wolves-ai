"use client";

import { useMemo, useState } from "react";
import { PastResults } from "@/components/fixtures/past-results";
import { StageSection } from "@/components/fixtures/stage-section";
import { buildFixtures } from "@/lib/fixtures";
import type { PlayedResultRow } from "@/lib/results";
import type { MatchWdlDraws } from "@/lib/sidecars";
import type { MatchProbs, Slot } from "@/lib/snapshot";

interface FixturesListProps {
  matches: MatchProbs[];
  slots: Slot[];
  draws: MatchWdlDraws | null;
  results: PlayedResultRow[];
  cutoffIso: string;
  teamNames: Record<string, string>;
}

export function FixturesList({ matches, slots, draws, results, cutoffIso, teamNames }: FixturesListProps) {
  const { sections, pastSections, openGroupDay, openStage } = useMemo(
    () => buildFixtures({ matches, slots, draws, results, teamNames, cutoffIso }),
    [matches, slots, draws, results, teamNames, cutoffIso],
  );
  const [openDay, setOpenDay] = useState<string | null>(openGroupDay);
  const [openStageKey, setOpenStageKey] = useState<string | null>(openStage);

  return (
    <div className="mx-auto max-w-[680px] px-1">
      {pastSections.length > 0 && <PastResults sections={pastSections} />}
      {sections.map((section) => (
        <StageSection
          key={section.key}
          section={section}
          open={openStageKey === section.key}
          onToggle={() => setOpenStageKey((current) => (current === section.key ? null : section.key))}
          openDay={openDay}
          onToggleDay={(key) => setOpenDay((current) => (current === key ? null : key))}
        />
      ))}
    </div>
  );
}
