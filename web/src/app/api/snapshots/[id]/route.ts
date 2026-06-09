import { NextResponse } from "next/server";
import { isValidRunId, readSnapshot } from "@/lib/server/snapshot-source";

interface RouteContext {
  params: Promise<{ id: string }>;
}

export async function GET(_request: Request, context: RouteContext): Promise<NextResponse> {
  const { id } = await context.params;
  if (!isValidRunId(id)) {
    return NextResponse.json({ error: "invalid run id" }, { status: 400 });
  }
  const snapshot = await readSnapshot(id);
  if (snapshot === null) {
    return NextResponse.json({ error: "snapshot not found" }, { status: 404 });
  }
  return new NextResponse(snapshot, { headers: { "content-type": "application/json" } });
}
