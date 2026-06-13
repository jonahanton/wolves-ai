import { orNull } from "@/lib/api";
import { loadSnapshot } from "@/lib/load-snapshot";
import type { SnapshotRef } from "@/lib/runs";
import type { Snapshot } from "@/lib/snapshot";

// A full agent run publishes a distributions block; the lighter intermediate
// agent runs do not, and are excluded from the headline timeline.
export async function loadFullRunIds(index: SnapshotRef[]): Promise<Set<string>> {
  const agentRefs = index.filter((ref) => ref.kind === "agent");
  const snapshots = await Promise.all(
    agentRefs.map(async (ref) => ({ ref, snapshot: orNull(await loadSnapshot(ref.runId)) })),
  );
  const ids = new Set<string>();
  for (const { ref, snapshot } of snapshots) {
    if ((snapshot as Snapshot | null)?.distributions) ids.add(ref.runId);
  }
  return ids;
}
