import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import {
  type ArchiveDay,
  type ArchiveDayPayload,
  ArchiveLoadError,
  type ArchiveManifest,
  type ArchiveRunPayload,
} from "@/lib/archive/contracts";
import type { DistributionsSidecar } from "@/lib/sidecars";
import type { Snapshot } from "@/lib/snapshot";

const ARCHIVE_ROOT = process.env.STATIC_ARCHIVE_DIR
  ? path.resolve(/* turbopackIgnore: true */ process.env.STATIC_ARCHIVE_DIR)
  : path.join(/* turbopackIgnore: true */ process.cwd(), "public", "archive");

export async function loadArchiveManifest(): Promise<ArchiveManifest> {
  return readJson<ArchiveManifest>("manifest.json");
}

export async function loadArchiveDay(
  day: string,
): Promise<{ manifest: ArchiveManifest; day: ArchiveDay; payload: ArchiveDayPayload }> {
  const manifest = await loadArchiveManifest();
  const entry = manifest.days.find((candidate) => candidate.day === day);
  if (!entry) throw new ArchiveLoadError("missing");
  const body = await readVerifiedObject(entry.payload);
  const payload = parseJson<ArchiveDayPayload>(body);
  if (payload.schema_hash !== manifest.schema_hash || payload.day !== entry.day) {
    throw new ArchiveLoadError("corrupt");
  }
  return { manifest, day: entry, payload };
}

export async function loadDefaultArchiveDay(): Promise<{
  manifest: ArchiveManifest;
  day: ArchiveDay;
  payload: ArchiveDayPayload;
}> {
  const manifest = await loadArchiveManifest();
  return loadArchiveDay(manifest.final_day);
}

export async function archivedRun(runId: string): Promise<{
  day: string;
  snapshot: Snapshot;
  distributions: DistributionsSidecar;
  record: ArchiveRunPayload["record"];
}> {
  const manifest = await loadArchiveManifest();
  const entry = manifest.runs.find((candidate) => candidate.run_id === runId);
  if (!entry) throw new ArchiveLoadError("missing");
  const body = await readVerifiedObject(entry.payload);
  const payload = parseJson<ArchiveRunPayload>(body);
  if (payload.schema_hash !== manifest.schema_hash || payload.snapshot.run.run_id !== runId) {
    throw new ArchiveLoadError("corrupt");
  }
  return {
    day: entry.archive_day,
    snapshot: payload.snapshot,
    distributions: payload.distributions,
    record: payload.record,
  };
}

export async function archivedRunIds(): Promise<string[]> {
  const manifest = await loadArchiveManifest();
  return manifest.runs.map((run) => run.run_id);
}

async function readJson<T>(relativePath: string): Promise<T> {
  return parseJson<T>(await readArchiveFile(relativePath));
}

async function readArchiveFile(relativePath: string): Promise<Buffer> {
  const resolved = path.resolve(ARCHIVE_ROOT, relativePath);
  if (!resolved.startsWith(`${ARCHIVE_ROOT}${path.sep}`) && resolved !== ARCHIVE_ROOT) {
    throw new ArchiveLoadError("corrupt");
  }
  try {
    return await readFile(resolved);
  } catch {
    throw new ArchiveLoadError("missing");
  }
}

function parseJson<T>(body: Buffer): T {
  try {
    return JSON.parse(body.toString("utf-8")) as T;
  } catch {
    throw new ArchiveLoadError("corrupt");
  }
}

function digest(body: Buffer): string {
  return createHash("sha256").update(body).digest("hex");
}

async function readVerifiedObject(object: { path: string; sha256: string; bytes: number }): Promise<Buffer> {
  const body = await readArchiveFile(object.path);
  if (body.length !== object.bytes || digest(body) !== object.sha256) {
    throw new ArchiveLoadError("corrupt");
  }
  return body;
}
