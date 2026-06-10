import { TournamentBoard } from "@/components/tournament/tournament-board";
import { buildBracketView } from "@/lib/bracket-view";
import { buildGroupsView } from "@/lib/groups-view";
import { loadLatestSnapshot } from "@/lib/load-snapshot";
import { buildOddsView } from "@/lib/odds-view";
import { teamNames } from "@/lib/snapshot";
import { buildTeamSheetViews } from "@/lib/team-sheet-view";

export const dynamic = "force-dynamic";

export default async function BracketPage() {
  const snapshot = await loadLatestSnapshot();
  const names = teamNames(snapshot);

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 p-4">
      <TournamentBoard
        bracket={buildBracketView(snapshot, names)}
        odds={buildOddsView(snapshot, names)}
        groups={buildGroupsView(snapshot, names)}
        teamSheets={buildTeamSheetViews(snapshot, names)}
      />
    </main>
  );
}
