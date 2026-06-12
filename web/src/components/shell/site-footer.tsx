import { orNull } from "@/lib/api";
import { loadLatestSnapshot } from "@/lib/load-snapshot";

export async function SiteFooter() {
  const snapshot = orNull(await loadLatestSnapshot());

  const provenance = snapshot
    ? [
        snapshot.run.run_id,
        snapshot.champion ? `${snapshot.champion.id} · dataset ${snapshot.champion.dataset_id.slice(0, 8)}` : null,
        snapshot.agent ? `artifact ${snapshot.agent.artifact_id}` : null,
        `${snapshot.run.n_sims.toLocaleString("en-GB")} sims`,
      ]
        .filter(Boolean)
        .join(" · ")
    : "no published run";

  return (
    <footer className="border-t border-hairline">
      <div className="wrap flex flex-wrap justify-between gap-x-6 gap-y-2 py-7 pb-14 font-mono text-[12px] text-cream-faint">
        <span>The Wolves · est. Euros 2024</span>
        <span>{provenance}</span>
      </div>
    </footer>
  );
}
