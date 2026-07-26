import { FixturesList } from "@/components/fixtures/fixtures-list";
import { ArchiveDateControl } from "@/components/shell/archive-date-control";
import type { ArchiveDay, ArchiveDayPayload, ArchiveManifest } from "@/lib/archive/contracts";
import { archiveResults } from "@/lib/archive/view";

interface ArchiveFixturesPageProps {
  manifest: ArchiveManifest;
  day: ArchiveDay;
  payload: ArchiveDayPayload;
}

export function ArchiveFixturesPage({ manifest, day, payload }: ArchiveFixturesPageProps) {
  const snapshot = payload.selected_snapshot;
  return (
    <main className="wrap py-[clamp(28px,5vh,56px)]">
      <ArchiveDateControl days={manifest.days} selectedDay={day} section="fixtures" />
      <FixturesList
        matches={snapshot.matches ?? []}
        slots={snapshot.slots ?? []}
        draws={payload.sidecars.match_wdl_draws}
        results={archiveResults(payload)}
        cutoffIso={payload.cutoff_at}
        teamNames={Object.fromEntries(snapshot.teams.map((team) => [team.team_id, team.name]))}
      />
    </main>
  );
}
