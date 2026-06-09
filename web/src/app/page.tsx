import { DailyStory } from "@/components/today/daily-story";
import { FinishSummary } from "@/components/today/finish-summary";
import { NextFixtureCard } from "@/components/today/next-fixture-card";
import { RunHeader } from "@/components/today/run-header";
import { WhatMoved } from "@/components/today/what-moved";
import { englandStory } from "@/lib/agent-fields";
import { summariseSnapshot } from "@/lib/derive";
import { loadLatestSnapshot } from "@/lib/load-snapshot";
import { nextEnglandFixture } from "@/lib/schedule";
import { teamNames } from "@/lib/snapshot";

export const dynamic = "force-dynamic";

export default async function TodayPage() {
  const snapshot = await loadLatestSnapshot();
  const names = teamNames(snapshot);
  const fixture = nextEnglandFixture(new Date());
  const mood = (snapshot.england.finish_probs.win_group ?? 0) >= 0.5 ? "happy" : "neutral";

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 p-4">
      <RunHeader run={snapshot.run} mood={mood} />
      <WhatMoved summary={summariseSnapshot(snapshot)} />
      {fixture && <NextFixtureCard fixture={fixture} names={names} />}
      <FinishSummary england={snapshot.england} />
      <DailyStory story={englandStory(snapshot)} />
    </main>
  );
}
