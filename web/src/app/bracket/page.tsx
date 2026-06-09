import { BracketBoard } from "@/components/bracket/bracket-board";
import { PageHeader } from "@/components/shell/page-header";
import { buildBracketView } from "@/lib/bracket-view";
import { loadLatestSnapshot } from "@/lib/load-snapshot";
import { teamNames } from "@/lib/snapshot";

export const dynamic = "force-dynamic";

export default async function BracketPage() {
  const snapshot = await loadLatestSnapshot();
  const view = buildBracketView(snapshot, teamNames(snapshot));

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 p-4">
      <PageHeader title="Bracket" subtitle="Every knockout slot, most likely occupants" />
      <BracketBoard view={view} />
    </main>
  );
}
