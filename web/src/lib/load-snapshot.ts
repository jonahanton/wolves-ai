import { readFile } from "fs/promises";
import path from "path";
import fixture from "@/fixtures/snapshot.json";
import type { Snapshot } from "@/lib/snapshot";

const SNAPSHOT_DIR = process.env.SNAPSHOT_DIR ?? path.join(process.cwd(), "..", "runs");

export async function loadLatestSnapshot(): Promise<Snapshot> {
  try {
    const raw = await readFile(path.join(SNAPSHOT_DIR, "latest.json"), "utf8");
    return JSON.parse(raw) as unknown as Snapshot;
  } catch {
    return fixture as unknown as Snapshot;
  }
}
