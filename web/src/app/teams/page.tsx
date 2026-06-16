import { TeamBoard } from "@/components/teams/team-board";
import { ErrorState } from "@/components/shell/error-state";
import { FestivalBand } from "@/components/walls/festival-band";
import { orNull } from "@/lib/api";
import { titleBoard } from "@/lib/derive";
import { formatRunStampEastern } from "@/lib/format";
import { impactForAgent, loadImpact } from "@/lib/impact";
import { loadLatestSnapshot, loadSnapshot } from "@/lib/load-snapshot";
import { loadResults } from "@/lib/results";
import { loadSnapshotIndex } from "@/lib/runs";
import { loadSidecar, type PairingMatrices } from "@/lib/sidecars";

export default async function TeamsPage() {
  const [result, indexResult, resultsResult] = await Promise.all([
    loadLatestSnapshot(),
    loadSnapshotIndex(),
    loadResults(),
  ]);
  if (!result.ok) return <ErrorState error={result.error} />;
  const snapshot = result.data;

  const index = orNull(indexResult)?.snapshots ?? [];
  const agentRef = index.find((ref) => ref.kind === "agent");
  const agentSnapshot =
    snapshot.run.kind === "agent" || !agentRef
      ? snapshot
      : (orNull(await loadSnapshot(agentRef.runId)) ?? snapshot);

  const pairing = orNull(await loadSidecar<PairingMatrices>(agentSnapshot.run.run_id, "pairing-matrices"));

  const names = Object.fromEntries(agentSnapshot.teams.map((t) => [t.team_id, t.name]));
  const reachProbs = Object.fromEntries(
    agentSnapshot.teams.filter((t) => t.reach_probs).map((t) => [t.team_id, t.reach_probs ?? {}]),
  );
  const board = titleBoard(agentSnapshot, agentSnapshot.teams.length);
  const impactIds = board.slice(0, 12).map((row) => row.teamId);
  const impact = impactForAgent(orNull(await loadImpact(impactIds)), agentSnapshot.run.run_id);

  return (
    <>
      <main className="wrap py-[clamp(28px,5vh,56px)]">
        <TeamBoard
          runLabel={formatRunStampEastern(agentSnapshot.run.created_at)}
          board={board}
          names={names}
          reachProbs={reachProbs}
          rounds={pairing?.rounds ?? {}}
          results={orNull(resultsResult)?.results ?? []}
          impact={impact}
        />
      </main>
      <div className="max-h-[clamp(120px,18vh,200px)] overflow-hidden">
        <FestivalBand family="euros" tag="Euros 2024 · the Wolves" />
      </div>
    </>
  );
}
