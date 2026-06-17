import { ForecastIndex } from "@/components/forecast/forecast-index";
import { ErrorState } from "@/components/shell/error-state";
import { FestivalBand } from "@/components/walls/festival-band";
import { orNull } from "@/lib/api";
import { forecastIndexRows } from "@/lib/forecast";
import { loadSnapshot } from "@/lib/load-snapshot";
import { loadRunRecords, loadSnapshotIndex } from "@/lib/runs";
import type { Snapshot } from "@/lib/snapshot";

export default async function ForecastIndexPage() {
  const [indexResult, recordsResult] = await Promise.all([
    loadSnapshotIndex(),
    loadRunRecords(),
  ]);
  if (!indexResult.ok) return <ErrorState error={indexResult.error} />;

  const agentRefs = indexResult.data.snapshots.filter((ref) => ref.kind === "agent");
  const loaded = await Promise.all(agentRefs.map((ref) => loadSnapshot(ref.runId)));
  const snapshots = loaded
    .map(orNull)
    .filter((s): s is Snapshot => s !== null && s.distributions != null && s.agent != null);

  const names = Object.fromEntries(
    (snapshots[0]?.teams ?? []).map((t) => [t.team_id, t.name]),
  );
  const rows = forecastIndexRows(snapshots, orNull(recordsResult)?.runs ?? null);

  return (
    <>
      <main className="wrap py-[clamp(28px,5vh,56px)]">
        <ForecastIndex rows={rows} names={names} />
      </main>
      <div className="max-h-[clamp(120px,18vh,200px)] overflow-hidden">
        <FestivalBand family="euros" tag="Euros 2024 · the Wolves" />
      </div>
    </>
  );
}
