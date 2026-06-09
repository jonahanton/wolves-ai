import { ProbBar } from "@/components/road/prob-bar";
import type { EnglandPath } from "@/lib/snapshot";

const FINISH_LABELS: Record<string, string> = {
  win_group: "Win Group L",
  runner_up: "Finish second",
  third: "Squeak through third",
};

interface PathCardProps {
  path: EnglandPath;
  names: Map<string, string>;
}

export function PathCard({ path, names }: PathCardProps) {
  const date = new Date(path.date).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  return (
    <section className="rounded-xl border bg-card p-4">
      <header className="mb-3 flex items-baseline justify-between">
        <div>
          <h2 className="font-semibold">{FINISH_LABELS[path.finish] ?? path.finish}</h2>
          <p className="text-sm text-muted-foreground">
            R32 in {path.city}, {date}
          </p>
        </div>
        <span className="text-2xl font-semibold tabular-nums text-gold">{Math.round(path.prob * 100)}%</span>
      </header>
      <div className="space-y-1.5">
        {path.opponents.slice(0, 4).map((o, i) => (
          <ProbBar key={o.team_id} label={names.get(o.team_id) ?? o.team_id} prob={o.prob} highlight={i === 0} />
        ))}
      </div>
    </section>
  );
}
