import { NextResponse } from "next/server";
import { requireAdmin } from "@/lib/server/admin-auth";

export async function adminRoute(handler: () => Promise<NextResponse>): Promise<NextResponse> {
  const denied = requireAdmin();
  if (denied) return denied;
  try {
    return await handler();
  } catch (error) {
    const message = error instanceof Error ? error.message : "upstream failure";
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
