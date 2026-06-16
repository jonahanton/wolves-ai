import { FixturesList } from "@/components/fixtures/fixtures-list";
import { ErrorState } from "@/components/shell/error-state";
import { orNull } from "@/lib/api";
import { loadImpact } from "@/lib/impact";
import { loadLatestSnapshot, loadSnapshot } from "@/lib/load-snapshot";
import { loadLiveState } from "@/lib/live";
import { loadResults } from "@/lib/results";
import { loadSnapshotIndex } from "@/lib/runs";
import { type BracketSamples, loadSidecar, type MatchWdlDraws } from "@/lib/sidecars";

export default async function FixturesPage() {
  const [result, indexResult, resultsResult, liveResult] = await Promise.all([
    loadLatestSnapshot(),
    loadSnapshotIndex(),
    loadResults(),
    loadLiveState(),
  ]);
  if (!result.ok) return <ErrorState error={result.error} />;
  const snapshot = result.data;

  const index = orNull(indexResult)?.snapshots ?? [];
  const agentRef = index.find((ref) => ref.kind === "agent");
  const agentSnapshot =
    snapshot.run.kind === "agent" || !agentRef
      ? snapshot
      : (orNull(await loadSnapshot(agentRef.runId)) ?? snapshot);

  const runId = agentSnapshot.run.run_id;
  const [draws, brackets, impact] = await Promise.all([
    loadSidecar<MatchWdlDraws>(runId, "match-wdl-draws"),
    loadSidecar<BracketSamples>(runId, "bracket-samples"),
    loadImpact(),
  ]);
  const teamNames = Object.fromEntries(agentSnapshot.teams.map((t) => [t.team_id, t.name]));

  return (
    <main className="wrap py-[clamp(28px,5vh,56px)]">
      <FixturesList
        matches={agentSnapshot.matches ?? []}
        draws={orNull(draws)}
        brackets={orNull(brackets)}
        results={orNull(resultsResult)?.results ?? []}
        initialLive={orNull(liveResult)}
        impact={orNull(impact)}
        teamNames={teamNames}
      />
    </main>
  );
}
