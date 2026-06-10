import { LiveBoard } from "@/components/live/live-board";
import { ScoreEntry } from "@/components/live/score-entry";
import { PageHeader } from "@/components/shell/page-header";
import { buildLiveFixtures } from "@/lib/live-view";
import { loadLatestSnapshot } from "@/lib/load-snapshot";
import { groupStageStart, nextMatchday } from "@/lib/schedule";
import { teamNames } from "@/lib/snapshot";
import { buildTeamSheetViews } from "@/lib/team-sheet-view";

export const dynamic = "force-dynamic";

export default async function LivePage() {
  const snapshot = await loadLatestSnapshot();
  const names = teamNames(snapshot);
  const now = new Date();
  const preTournament = now < new Date(groupStageStart);
  const matchday = nextMatchday(now);
  const fixtures = matchday ? buildLiveFixtures(snapshot, matchday.matches, names) : [];
  const first = fixtures[0];

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 p-4">
      <PageHeader title="Live" subtitle="Matchday tracking and what-ifs" />
      <LiveBoard
        preTournament={preTournament}
        day={matchday?.day ?? null}
        fixtures={fixtures}
        teamSheets={buildTeamSheetViews(snapshot, names)}
      />
      {first && <ScoreEntry home={first.homeName} away={first.awayName} />}
    </main>
  );
}
