import type { SnapshotSummary } from "@/lib/derive";

const STORAGE_KEY = "wolves:snapshot-history";
const LIMIT = 12;

interface LegacyHistory {
  current: SnapshotSummary;
  previous: SnapshotSummary | null;
}

function isSummary(value: unknown): value is SnapshotSummary {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as SnapshotSummary).runId === "string" &&
    typeof (value as SnapshotSummary).metrics === "object"
  );
}

function parseEntries(raw: string): SnapshotSummary[] {
  const parsed: unknown = JSON.parse(raw);
  if (Array.isArray(parsed)) return parsed.filter(isSummary);
  // Pre-history format stored {current, previous}; fold it into the run list once.
  const legacy = parsed as Partial<LegacyHistory>;
  return [legacy.previous, legacy.current].filter((entry): entry is SnapshotSummary => isSummary(entry));
}

export function readSnapshotHistory(): SnapshotSummary[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? parseEntries(raw) : [];
  } catch {
    return [];
  }
}

export function appendSummary(entries: SnapshotSummary[], summary: SnapshotSummary): SnapshotSummary[] {
  return [...entries.filter((entry) => entry.runId !== summary.runId), summary].slice(-LIMIT);
}

export function writeSnapshotHistory(entries: SnapshotSummary[]): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Quota or privacy-mode failures degrade to a single-run history.
  }
}

export function previousSummary(entries: SnapshotSummary[], runId: string): SnapshotSummary | null {
  for (let i = entries.length - 1; i >= 0; i -= 1) {
    if (entries[i].runId !== runId) return entries[i];
  }
  return null;
}

export function metricSeries(entries: SnapshotSummary[], key: string): number[] {
  return entries
    .map((entry) => entry.metrics[key])
    .filter((value): value is number => typeof value === "number");
}
