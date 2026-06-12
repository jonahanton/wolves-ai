import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8080";

const ADMIN_COOKIE = "wolves-admin";

export async function POST(request: Request): Promise<Response> {
  const body = (await request.json().catch(() => null)) as { token?: string } | null;
  const token = body?.token?.trim();
  if (!token || token.length > 200) {
    return NextResponse.json({ error: "token required" }, { status: 400 });
  }
  const probe = await fetch(new URL("/admin/schedule", BACKEND_URL), {
    headers: { authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  // Auth rejection is 401/403; other statuses mean the token passed and an
  // AWS adapter failed, which still proves the token.
  if (probe.status === 401 || probe.status === 403) {
    return NextResponse.json({ error: "not authorised" }, { status: 403 });
  }
  const jar = await cookies();
  jar.set(ADMIN_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: 60 * 60 * 24 * 45,
  });
  return NextResponse.json({ ok: true });
}

export async function DELETE(): Promise<Response> {
  const jar = await cookies();
  jar.delete(ADMIN_COOKIE);
  return NextResponse.json({ ok: true });
}
