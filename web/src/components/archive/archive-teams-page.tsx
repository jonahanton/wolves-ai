import { TeamBoard } from "@/components/teams/team-board";
import { ArchiveDateControl } from "@/components/shell/archive-date-control";
import { FestivalBand } from "@/components/walls/festival-band";
import type { ArchiveDay, ArchiveDayPayload, ArchiveManifest } from "@/lib/archive/contracts";
import { archiveResults } from "@/lib/archive/view";
import { titleBoard } from "@/lib/derive";
import { formatRunStampEastern } from "@/lib/format";

interface ArchiveTeamsPageProps {
  manifest: ArchiveManifest;
  day: ArchiveDay;
  payload: ArchiveDayPayload;
}

export function ArchiveTeamsPage({ manifest, day, payload }: ArchiveTeamsPageProps) {
  const snapshot = payload.selected_snapshot;
  const names = Object.fromEntries(snapshot.teams.map((team) => [team.team_id, team.name]));
  const reachProbs = Object.fromEntries(
    snapshot.teams.map((team) => [team.team_id, team.reach_probs ?? {}]),
  );
  return (
    <>
      <main className="wrap py-[clamp(28px,5vh,56px)]">
        <ArchiveDateControl days={manifest.days} selectedDay={day} section="teams" />
        <TeamBoard
          runLabel={formatRunStampEastern(snapshot.run.created_at)}
          board={titleBoard(snapshot, snapshot.teams.length)}
          names={names}
          reachProbs={reachProbs}
          rounds={payload.sidecars.pairing_matrices.rounds}
          results={archiveResults(payload)}
        />
      </main>
      <div className="max-h-[clamp(120px,18vh,200px)] overflow-hidden">
        <FestivalBand family="euros" tag="Euros 2024 · the Wolves" />
      </div>
    </>
  );
}
