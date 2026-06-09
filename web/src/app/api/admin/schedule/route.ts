import { NextResponse } from "next/server";
import { adminRoute } from "@/lib/server/api";
import { getScheduleState, setScheduleEnabled } from "@/lib/server/schedule";

export async function GET(): Promise<NextResponse> {
  return adminRoute(async () => NextResponse.json(await getScheduleState()));
}

export async function POST(request: Request): Promise<NextResponse> {
  return adminRoute(async () => {
    const body = (await request.json()) as { enabled?: unknown };
    if (typeof body.enabled !== "boolean") {
      return NextResponse.json({ error: "enabled must be a boolean" }, { status: 400 });
    }
    return NextResponse.json(await setScheduleEnabled(body.enabled));
  });
}
