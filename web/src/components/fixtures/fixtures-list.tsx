"use client";

import { useMemo, useState } from "react";
import { FixtureDay } from "@/components/fixtures/fixture-day";
import { useLivePoll } from "@/hooks/use-live-poll";
import { buildFixtureDays } from "@/lib/fixtures";
import type { Impact } from "@/lib/impact";
import type { LiveState } from "@/lib/live";
import type { PlayedResultRow } from "@/lib/results";
import type { BracketSamples, MatchWdlDraws } from "@/lib/sidecars";
import type { MatchProbs } from "@/lib/snapshot";

interface FixturesListProps {
  matches: MatchProbs[];
  draws: MatchWdlDraws | null;
  brackets: BracketSamples | null;
  results: PlayedResultRow[];
  initialLive: LiveState | null;
  impact: Impact | null;
  teamNames: Record<string, string>;
}

export function FixturesList({
  matches,
  draws,
  brackets,
  results,
  initialLive,
  impact,
  teamNames,
}: FixturesListProps) {
  const live = useLivePoll(initialLive);
  const { days, openIndex } = useMemo(
    () =>
      buildFixtureDays({
        matches,
        draws,
        brackets,
        results,
        live,
        teamNames,
        nowIso: new Date().toISOString(),
      }),
    [matches, draws, brackets, results, live, teamNames],
  );
  const [openDay, setOpenDay] = useState<string | null>(days[openIndex]?.dayKey ?? null);

  return (
    <div className="mx-auto max-w-[680px]">
      {days.map((day) => (
        <FixtureDay
          key={day.dayKey}
          day={day}
          open={openDay === day.dayKey}
          onToggle={() => setOpenDay((current) => (current === day.dayKey ? null : day.dayKey))}
          impact={impact}
        />
      ))}
    </div>
  );
}
