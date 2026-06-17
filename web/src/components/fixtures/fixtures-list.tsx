"use client";

import { useMemo, useState } from "react";
import { StageSection } from "@/components/fixtures/stage-section";
import { useLivePoll } from "@/hooks/use-live-poll";
import { buildFixtures } from "@/lib/fixtures";
import type { Impact } from "@/lib/impact";
import type { LiveState } from "@/lib/live";
import type { PlayedResultRow } from "@/lib/results";
import type { MatchWdlDraws } from "@/lib/sidecars";
import type { MatchProbs, Slot } from "@/lib/snapshot";

interface FixturesListProps {
  matches: MatchProbs[];
  slots: Slot[];
  draws: MatchWdlDraws | null;
  results: PlayedResultRow[];
  initialLive: LiveState | null;
  initialImpact: Impact | null;
  teamNames: Record<string, string>;
}

export function FixturesList({ matches, slots, draws, results, initialLive, initialImpact, teamNames }: FixturesListProps) {
  const { live, impact } = useLivePoll({ live: initialLive, impact: initialImpact });
  const { sections, openGroupDay, openStage } = useMemo(
    () => buildFixtures({ matches, slots, draws, results, live, teamNames, nowIso: new Date().toISOString() }),
    [matches, slots, draws, results, live, teamNames],
  );
  const [openDay, setOpenDay] = useState<string | null>(openGroupDay);
  const [openStageKey, setOpenStageKey] = useState<string | null>(openStage);

  return (
    <div className="mx-auto max-w-[680px] px-1">
      {sections.map((section) => (
        <StageSection
          key={section.key}
          section={section}
          impact={impact}
          open={openStageKey === section.key}
          onToggle={() => setOpenStageKey((current) => (current === section.key ? null : section.key))}
          openDay={openDay}
          onToggleDay={(key) => setOpenDay((current) => (current === key ? null : key))}
        />
      ))}
    </div>
  );
}
