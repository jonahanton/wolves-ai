import { formatPctBare } from "@/lib/format";
import { heatFill } from "@/lib/heat";
import type { OddsView } from "@/lib/odds-view";
import { TABLE_STAGES } from "@/lib/reach-stages";
import { cn } from "@/lib/utils";

const GRID = "grid grid-cols-[1.3rem_minmax(0,1fr)_repeat(4,2.6rem)] items-stretch";

interface OddsTableProps {
  view: OddsView;
  onSelectTeam: (teamId: string) => void;
}

export function OddsTable({ view, onSelectTeam }: OddsTableProps) {
  if (!view.hasReachData) {
    return (
      <section className="rounded-xl border bg-card p-3" aria-label="Champion odds">
        <p className="text-sm text-muted-foreground">Whole-tournament odds land with the next engine run.</p>
      </section>
    );
  }

  return (
    <section aria-label="Champion odds">
      <p className="mb-2 text-sm text-muted-foreground">
        How often each side reaches each round, deepest first.
      </p>
      <div className="overflow-hidden rounded-xl border bg-card">
        <div className={cn(GRID, "items-center border-b px-2.5 py-2")}>
          <span />
          <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">Team</span>
          {TABLE_STAGES.map((stage) => (
            <span
              key={stage.key}
              className="text-right text-[11px] font-semibold tracking-wide text-muted-foreground uppercase"
            >
              {stage.label}
            </span>
          ))}
        </div>
        <div className="divide-y">
          {view.rows.map((row, rank) => (
            <button
              key={row.teamId}
              type="button"
              onClick={() => onSelectTeam(row.teamId)}
              className={cn(GRID, "w-full px-2.5 text-left text-xs hover:bg-secondary/60")}
            >
              <span className="flex items-center text-muted-foreground">{rank + 1}</span>
              <span className={cn("flex min-w-0 items-center font-medium", row.isEngland && "text-gold")}>
                <span className="truncate">{row.name}</span>
              </span>
              {TABLE_STAGES.map((stage, i) => {
                const prob = row.reach[stage.key] ?? 0;
                return (
                  <span
                    key={stage.key}
                    className={cn(
                      "flex items-center justify-end px-1.5 py-2",
                      i === TABLE_STAGES.length - 1 ? "font-semibold" : "text-foreground/80",
                    )}
                    style={{ backgroundColor: heatFill(prob, row.isEngland) }}
                  >
                    {formatPctBare(prob)}
                  </span>
                );
              })}
            </button>
          ))}
        </div>
      </div>
      <p className="mt-2 px-1 text-xs text-muted-foreground">
        Each cell is the share of simulations (%) in which the team reaches that round; W is winning the lot.
        Tap a team for every round and its likely route.
      </p>
    </section>
  );
}
