import { NextResponse } from "next/server";
import { orNull } from "@/lib/api";
import { loadAgentImpact } from "@/lib/impact";
import { loadLiveState } from "@/lib/live";

export async function GET() {
  const [live, impact] = await Promise.all([loadLiveState(), loadAgentImpact()]);
  return NextResponse.json({
    live: orNull(live),
    impact: orNull(impact),
  });
}
