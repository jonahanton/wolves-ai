import { Lock } from "lucide-react";
import { WolfMascot } from "@/components/mascot/wolf-mascot";
import { ThemeToggle } from "@/components/more/theme-toggle";
import { PageHeader } from "@/components/shell/page-header";
import { isAdmin } from "@/lib/flags";
import { loadLatestSnapshot } from "@/lib/load-snapshot";

export const dynamic = "force-dynamic";

export default async function MorePage() {
  const snapshot = await loadLatestSnapshot();

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 p-4">
      <PageHeader title="More" subtitle="Settings and the small print" />

      <section className="rounded-xl border bg-card p-3" aria-label="Settings">
        <h2 className="font-semibold">Appearance</h2>
        <div className="mt-3">
          <ThemeToggle />
        </div>
      </section>

      <section className="rounded-xl border bg-card p-3" aria-label="About">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="font-semibold">About</h2>
            <p className="mt-1.5 text-sm text-muted-foreground">
              The Wolves&apos; World Cup Superforecaster. A Monte Carlo engine and a forecasting agent working
              out who England play, where, and how worried to be. Built for eleven friends going to the 2026
              World Cup.
            </p>
          </div>
          <WolfMascot mood="happy" size={48} />
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 border-t pt-3 text-xs text-muted-foreground">
          <dt>Engine</dt>
          <dd className="text-right font-mono">{snapshot.run.engine_version}</dd>
          <dt>Snapshot schema</dt>
          <dd className="text-right font-mono">v{snapshot.schema_version}</dd>
          <dt>Run kind</dt>
          <dd className="text-right font-mono">{snapshot.run.kind}</dd>
        </dl>
      </section>

      {isAdmin ? (
        <section className="rounded-xl border bg-card p-3" aria-label="Admin">
          <h2 className="font-semibold">Admin</h2>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Run controls, kill switch and spend tracking land with the runner.
          </p>
        </section>
      ) : (
        <p className="flex items-center gap-1.5 px-1 text-xs text-muted-foreground">
          <Lock size={12} /> Admin tools are reserved for the keeper of the wolves.
        </p>
      )}
    </main>
  );
}
