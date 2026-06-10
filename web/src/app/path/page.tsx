import { PathSpine } from "@/components/path/path-spine";
import { TravelForkCard } from "@/components/path/travel-fork-card";
import { PageHeader } from "@/components/shell/page-header";
import { travelMemo } from "@/lib/agent-fields";
import { loadLatestSnapshot } from "@/lib/load-snapshot";
import { teamNames } from "@/lib/snapshot";
import { buildSpineViews } from "@/lib/spine-view";

export const dynamic = "force-dynamic";

export default async function PathPage() {
  const snapshot = await loadLatestSnapshot();
  const views = buildSpineViews(snapshot, teamNames(snapshot));

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 p-4">
      <PageHeader title="Path" subtitle="England's route through the knockouts" />
      <TravelForkCard england={snapshot.england} memo={travelMemo(snapshot)} />
      <PathSpine views={views} />
    </main>
  );
}
