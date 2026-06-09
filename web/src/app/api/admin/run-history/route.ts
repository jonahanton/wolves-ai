import { NextResponse } from "next/server";
import { adminRoute } from "@/lib/server/api";
import { listRuns } from "@/lib/server/run-history";

export async function GET(): Promise<NextResponse> {
  return adminRoute(async () => NextResponse.json({ runs: await listRuns() }));
}
