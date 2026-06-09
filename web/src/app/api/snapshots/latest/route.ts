import { NextResponse } from "next/server";
import { readLatestSnapshot } from "@/lib/server/snapshot-source";

export async function GET(): Promise<NextResponse> {
  const snapshot = await readLatestSnapshot();
  if (snapshot === null) {
    return NextResponse.json({ error: "no snapshot available" }, { status: 404 });
  }
  return new NextResponse(snapshot, { headers: { "content-type": "application/json" } });
}
