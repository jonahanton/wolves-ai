import { ProbBar } from "@/components/charts/prob-bar";
import { formatMatchDate, frequencyFrame } from "@/lib/format";
import type { EnglandBlock } from "@/lib/snapshot";

interface TravelForkCardProps {
  england: EnglandBlock;
  memo: string | null;
}

export function TravelForkCard({ england, memo }: TravelForkCardProps) {
  const forks = [...england.paths].sort((a, b) => b.prob - a.prob);
  const outProb = Math.max(0, 1 - forks.reduce((sum, p) => sum + p.prob, 0));
  const top = forks[0];

  return (
    <section className="sticker foil p-3" aria-label="Where England's last 32 is played">
      <p className="text-[11px] font-semibold tracking-widest text-gold uppercase">The travel fork</p>
      <h2 className="mt-1 text-lg font-semibold tracking-tight">Where is our last-32 tie?</h2>
      <div className="mt-3 space-y-1.5">
        {forks.map((fork, i) => (
          <ProbBar
            key={fork.finish}
            label={`${fork.city} ${formatMatchDate(fork.date).replace(/^\w+ /, "")}`}
            prob={fork.prob}
            highlight={i === 0}
          />
        ))}
        <ProbBar label="Out in groups" prob={outProb} />
      </div>
      {memo ? (
        <p className="mt-3 border-t border-dashed pt-3 text-sm">{memo}</p>
      ) : (
        top && (
          <p className="mt-3 text-xs text-muted-foreground">
            {top.city} happens in {frequencyFrame(top.prob)}. The agent&apos;s booking memo lands with the
            daily run.
          </p>
        )
      )}
    </section>
  );
}
