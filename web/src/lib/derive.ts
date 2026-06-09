import type { Snapshot } from "@/lib/snapshot";

export interface SnapshotSummary {
  runId: string;
  createdAt: string;
  metrics: Record<string, number>;
}

export interface DeltaChip {
  key: string;
  label: string;
  prob: number;
  deltaPts: number;
}

const REACH_LABELS: Record<string, string> = {
  r16: "Reach last 16",
  qf: "Reach quarters",
  sf: "Reach semis",
  final: "Reach final",
  champion: "Win it all",
};

export function summariseSnapshot(snapshot: Snapshot): SnapshotSummary {
  const metrics: Record<string, number> = {};
  for (const [stage, prob] of Object.entries(snapshot.england.reach_probs)) {
    metrics[`reach:${stage}`] = prob;
  }
  for (const path of snapshot.england.paths) {
    metrics[`city:${path.city}`] = path.prob;
  }
  return { runId: snapshot.run.run_id, createdAt: snapshot.run.created_at, metrics };
}

function labelFor(key: string): string {
  const [kind, rest] = key.split(":", 2);
  if (kind === "reach") return REACH_LABELS[rest] ?? rest;
  return `R32 in ${rest}`;
}

export function computeDeltas(
  current: SnapshotSummary,
  previous: SnapshotSummary,
  { minPts = 0.5, limit = 4 }: { minPts?: number; limit?: number } = {},
): DeltaChip[] {
  const chips: DeltaChip[] = [];
  for (const [key, prob] of Object.entries(current.metrics)) {
    const before = previous.metrics[key];
    if (before === undefined) continue;
    const deltaPts = (prob - before) * 100;
    if (Math.abs(deltaPts) < minPts) continue;
    chips.push({ key, label: labelFor(key), prob, deltaPts });
  }
  return chips.sort((a, b) => Math.abs(b.deltaPts) - Math.abs(a.deltaPts)).slice(0, limit);
}
