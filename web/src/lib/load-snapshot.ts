import fixture from "@/fixtures/snapshot.json";
import type { Snapshot } from "@/lib/snapshot";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8080";

export async function loadLatestSnapshot(): Promise<Snapshot> {
  try {
    const response = await fetch(`${BACKEND_URL}/snapshots/latest`, { cache: "no-store" });
    if (response.ok) return (await response.json()) as Snapshot;
  } catch {
    // Fall through to the bundled fixture; a stale forecast beats an error page.
  }
  return fixture as unknown as Snapshot;
}
