import { NextResponse } from "next/server";

// Auth.js magic links land in Phase 5; until then admin access is denied
// unless the explicit dev bypass flag is set.
export function isAdmin(): boolean {
  return process.env.ADMIN_DEV_BYPASS === "true";
}

export function requireAdmin(): NextResponse | null {
  if (isAdmin()) return null;
  return NextResponse.json({ error: "forbidden" }, { status: 403 });
}
