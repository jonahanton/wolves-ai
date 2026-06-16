import { NextResponse } from "next/server";
import { orNull } from "@/lib/api";
import { loadImpact } from "@/lib/impact";
import { loadLiveState } from "@/lib/live";

export async function GET() {
  const [live, impact] = await Promise.all([loadLiveState(), loadImpact()]);
  return NextResponse.json({ live: orNull(live), impact: orNull(impact) });
}
