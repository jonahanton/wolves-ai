import { ForecastIndex } from "@/components/forecast/forecast-index";
import { ArchiveDateControl } from "@/components/shell/archive-date-control";
import { FestivalBand } from "@/components/walls/festival-band";
import type { ArchiveDay, ArchiveDayPayload, ArchiveManifest } from "@/lib/archive/contracts";
import { archiveRunRecords } from "@/lib/archive/view";
import { forecastIndexRows } from "@/lib/forecast";

interface ArchiveForecastPageProps {
  manifest: ArchiveManifest;
  day: ArchiveDay;
  payload: ArchiveDayPayload;
}

export function ArchiveForecastPage({ manifest, day, payload }: ArchiveForecastPageProps) {
  const names = Object.fromEntries(payload.selected_snapshot.teams.map((team) => [team.team_id, team.name]));
  return (
    <>
      <main className="wrap py-[clamp(28px,5vh,56px)]">
        <ArchiveDateControl days={manifest.days} selectedDay={day} section="forecast" />
        <ForecastIndex rows={forecastIndexRows(payload.forecast_history, archiveRunRecords(payload))} names={names} />
      </main>
      <div className="max-h-[clamp(120px,18vh,200px)] overflow-hidden">
        <FestivalBand family="euros" tag="Euros 2024 · the Wolves" />
      </div>
    </>
  );
}
