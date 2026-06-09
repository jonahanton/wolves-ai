import { NextResponse } from "next/server";
import { adminRoute } from "@/lib/server/api";
import { runEngineNow } from "@/lib/server/engine-tasks";

export async function POST(): Promise<NextResponse> {
  return adminRoute(async () => NextResponse.json({ taskArn: await runEngineNow() }, { status: 202 }));
}
