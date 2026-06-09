import { readFile } from "fs/promises";
import path from "path";
import { GetObjectCommand, NoSuchKey } from "@aws-sdk/client-s3";
import { awsEnv, s3Client } from "@/lib/server/aws";

const RUN_ID_PATTERN = /^run-(\d{4})(\d{2})(\d{2})$/;
const LOCAL_SNAPSHOT_DIR = process.env.SNAPSHOT_DIR ?? path.join(process.cwd(), "..", "runs");

export function isValidRunId(id: string): boolean {
  return RUN_ID_PATTERN.test(id);
}

export async function readSnapshot(id: string): Promise<string | null> {
  const match = RUN_ID_PATTERN.exec(id);
  if (!match) return null;
  const [, year, month, day] = match;
  return readFrom(`snapshots/${year}/${month}/${day}/${id}.json`, `${id}.json`);
}

export async function readLatestSnapshot(): Promise<string | null> {
  return readFrom("latest.json", "latest.json");
}

async function readFrom(s3Key: string, localName: string): Promise<string | null> {
  if (awsEnv.bucket) {
    try {
      const result = await s3Client().send(new GetObjectCommand({ Bucket: awsEnv.bucket, Key: s3Key }));
      return (await result.Body?.transformToString()) ?? null;
    } catch (error) {
      if (error instanceof NoSuchKey) return null;
      throw error;
    }
  }
  try {
    return await readFile(path.join(LOCAL_SNAPSHOT_DIR, localName), "utf8");
  } catch {
    return null;
  }
}
