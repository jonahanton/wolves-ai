import { MatchList } from "@/components/live/match-list";
import { ScoreEntry } from "@/components/live/score-entry";
import { PageHeader } from "@/components/shell/page-header";
import { loadLatestSnapshot } from "@/lib/load-snapshot";
import { groupStageStart, nextMatchday } from "@/lib/schedule";
import { teamNames } from "@/lib/snapshot";

export const dynamic = "force-dynamic";

export default async function LivePage() {
  const snapshot = await loadLatestSnapshot();
  const names = teamNames(snapshot);
  const now = new Date();
  const preTournament = now < new Date(groupStageStart);
  const matchday = nextMatchday(now);
  const first = matchday?.matches[0];

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 p-4">
      <PageHeader title="Live" subtitle="Matchday tracking and what-ifs" />
      <MatchList preTournament={preTournament} matchday={matchday} names={names} />
      {first && (
        <ScoreEntry home={names.get(first.home) ?? first.home} away={names.get(first.away) ?? first.away} />
      )}
    </main>
  );
}
