import { NextResponse } from "next/server";

// Placeholder until real auth lands: deny everything unless the dev bypass
// flag is set, and never honour the flag in a production build.
export function isAdmin(): boolean {
  return process.env.NODE_ENV !== "production" && process.env.ADMIN_DEV_BYPASS === "true";
}

export function requireAdmin(): NextResponse | null {
  if (isAdmin()) return null;
  return NextResponse.json({ error: "forbidden" }, { status: 403 });
}
