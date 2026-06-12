import { formatPct1 } from "@/lib/format";
import type { AgentBlock } from "@/lib/snapshot";

interface WorldsListProps {
  agent: AgentBlock;
  names: Map<string, string>;
  focusId: string;
}

export function WorldsList({ agent, names, focusId }: WorldsListProps) {
  return (
    <div className="max-w-[880px]">
      {agent.worlds.map((world) => {
        const weight = agent.scenario_weights.find((w) => w.name === world.name);
        const conditionals = Object.entries(world.title_probs ?? {})
          .sort(([, a], [, b]) => b - a)
          .slice(0, 3);
        const focusProb = world.title_probs?.[focusId];
        return (
          <div key={world.name} className="border-b border-hairline py-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="font-mono text-[15px]">{world.name.replaceAll("_", " ")}</span>
              <span className="font-mono text-[15px] text-gold">{Math.round(world.weight * 100)}%</span>
            </div>
            <div className="mt-2 h-[3px] max-w-[320px] rounded-pill bg-hairline">
              <i
                className="block h-full rounded-pill bg-gold/70"
                style={{ width: `${(world.weight * 100).toFixed(0)}%` }}
              />
            </div>
            {weight?.rationale && (
              <p className="mt-2 line-clamp-3 max-w-[64ch] text-[14.5px] font-light text-cream-dim">
                {weight.rationale}
              </p>
            )}
            {conditionals.length > 0 && (
              <p className="mt-1.5 font-mono text-[12.5px] text-cream-faint">
                in this world ·{" "}
                {focusProb !== undefined && (
                  <span className="text-cream-dim">
                    {names.get(focusId) ?? focusId} {formatPct1(focusProb)} ·{" "}
                  </span>
                )}
                {conditionals
                  .filter(([teamId]) => teamId !== focusId)
                  .slice(0, 2)
                  .map(([teamId, prob]) => `${names.get(teamId) ?? teamId} ${formatPct1(prob)}`)
                  .join(" · ")}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
