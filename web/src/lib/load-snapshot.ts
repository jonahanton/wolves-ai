import fixture from "@/fixtures/snapshot.json";
import { readLatestSnapshot } from "@/lib/server/snapshot-source";
import type { Snapshot } from "@/lib/snapshot";

export async function loadLatestSnapshot(): Promise<Snapshot> {
  try {
    const raw = await readLatestSnapshot();
    if (raw !== null) return JSON.parse(raw) as unknown as Snapshot;
  } catch {
    // Fall through to the bundled fixture; a stale forecast beats an error page.
  }
  return fixture as unknown as Snapshot;
}
