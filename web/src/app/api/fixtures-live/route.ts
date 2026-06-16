import { NextResponse } from "next/server";
import { orNull } from "@/lib/api";
import { loadLiveState } from "@/lib/live";

export async function GET() {
  return NextResponse.json(orNull(await loadLiveState()));
}
