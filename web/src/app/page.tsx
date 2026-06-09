import { PathCard } from "@/components/road/path-card";
import { loadLatestSnapshot } from "@/lib/load-snapshot";
import { teamNames } from "@/lib/snapshot";

export const dynamic = "force-dynamic";

const REACH_LABELS: [string, string][] = [
  ["r16", "Last 16"],
  ["qf", "Quarters"],
  ["sf", "Semis"],
  ["final", "Final"],
  ["champion", "Champions"],
];

export default async function Home() {
  const snapshot = await loadLatestSnapshot();
  const names = teamNames(snapshot);
  const updated = new Date(snapshot.run.created_at).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col gap-4 p-4 pb-10">
      <header className="pt-2">
        <h1 className="text-xl font-semibold tracking-tight">England&apos;s Road</h1>
        <p className="text-sm text-muted-foreground">
          {snapshot.run.n_sims.toLocaleString("en-GB")} sims, updated {updated}
        </p>
      </header>

      <div className="flex flex-col gap-3">
        {snapshot.england.paths.map((path) => (
          <PathCard key={path.finish} path={path} names={names} />
        ))}
      </div>

      <section className="rounded-xl border bg-card p-4">
        <h2 className="mb-3 font-semibold">How far do we go?</h2>
        <div className="flex justify-between text-center">
          {REACH_LABELS.map(([key, label]) => (
            <div key={key} className="flex flex-col">
              <span className="text-lg font-semibold tabular-nums">
                {Math.round((snapshot.england.reach_probs[key] ?? 0) * 100)}%
              </span>
              <span className="text-xs text-muted-foreground">{label}</span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
