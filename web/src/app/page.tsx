import { DailyStory } from "@/components/today/daily-story";
import { EvidenceFeed } from "@/components/today/evidence-feed";
import { FinishSummary } from "@/components/today/finish-summary";
import { MarketsCard } from "@/components/today/markets-card";
import { NextFixtureCard } from "@/components/today/next-fixture-card";
import { RunHeader } from "@/components/today/run-header";
import { TodayBoard } from "@/components/today/today-board";
import { englandStory, ledgerEntries } from "@/lib/agent-fields";
import { summariseSnapshot } from "@/lib/derive";
import { buildMarketsView } from "@/lib/markets";
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
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 p-4">
      <RunHeader run={snapshot.run} mood={mood} />
      <TodayBoard summary={summariseSnapshot(snapshot)} heroProb={snapshot.england.reach_probs.r32 ?? 0} />
      {fixture && <NextFixtureCard fixture={fixture} names={names} />}
      <FinishSummary england={snapshot.england} />
      <MarketsCard view={buildMarketsView(snapshot, names)} />
      <DailyStory story={englandStory(snapshot)} />
      <EvidenceFeed entries={ledgerEntries(snapshot)} />
    </main>
  );
}
