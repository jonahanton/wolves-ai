import { MOOD_VARIANTS } from "@/components/mascot/variants";
import { WolfMascot, type WolfMood } from "@/components/mascot/wolf-mascot";
import { formatUpdated } from "@/lib/format";
import type { RunMeta } from "@/lib/snapshot";

interface RunHeaderProps {
  run: RunMeta;
  mood: WolfMood;
}

export function RunHeader({ run, mood }: RunHeaderProps) {
  return (
    <header className="flex items-start justify-between gap-3 pt-2">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Today</h1>
        <p className="mt-0.5 text-sm text-muted-foreground">
          Updated {formatUpdated(run.created_at)} &middot; {run.n_sims.toLocaleString("en-GB")} sims
        </p>
        <p className="mt-0.5 font-mono text-[11px] text-muted-foreground/70">{run.run_id}</p>
      </div>
      <WolfMascot mood={mood} variant={MOOD_VARIANTS[mood]} size={54} />
    </header>
  );
}
