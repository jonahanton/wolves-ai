import { cookies } from "next/headers";
import { AdminConsole } from "@/components/admin/admin-console";
import { AdminUnlock } from "@/components/admin/admin-unlock";
import { Kicker } from "@/components/shell/kicker";
import { orNull } from "@/lib/api";
import { loadRunRecords } from "@/lib/runs";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8080";

async function adminGet<T>(path: string, token: string): Promise<T | null> {
  try {
    const response = await fetch(new URL(path, BACKEND_URL), {
      headers: { authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export default async function AdminPage() {
  const jar = await cookies();
  const token = jar.get("wolves-admin")?.value;

  if (!token) {
    return (
      <section className="wrap py-20">
        <Kicker>Admin</Kicker>
        <h1 className="statement">
          The control room
          <br />
          <b className="font-medium">is locked.</b>
        </h1>
        <div className="mt-10">
          <AdminUnlock />
        </div>
      </section>
    );
  }

  const [schedule, active, records] = await Promise.all([
    adminGet<{ enabled: boolean; cron: string }>("/admin/schedule", token),
    adminGet<{ tasks: { taskArn: string; lastStatus: string; startedAt: string | null }[] }>(
      "/admin/runs/active",
      token,
    ),
    loadRunRecords(),
  ]);

  return (
    <section className="wrap py-20">
      <Kicker>Admin · forensics live in Logfire</Kicker>
      <h1 className="statement">
        The control room.
      </h1>
      <div className="mt-10">
        <AdminConsole schedule={schedule} active={active?.tasks ?? null} records={orNull(records)?.runs ?? []} />
      </div>
    </section>
  );
}
