import { formatPctBare } from "@/lib/format";
import type { OddsView } from "@/lib/odds-view";
import { REACH_STAGES } from "@/lib/reach-stages";
import { cn } from "@/lib/utils";

const GRID = "grid grid-cols-[1.3rem_minmax(0,1fr)_repeat(6,2.1rem)] items-center gap-x-1";

interface OddsTableProps {
  view: OddsView;
  onSelectTeam: (teamId: string) => void;
}

export function OddsTable({ view, onSelectTeam }: OddsTableProps) {
  if (!view.hasReachData) {
    return (
      <section className="rounded-xl border bg-card p-4" aria-label="Champion odds">
        <p className="text-sm text-muted-foreground">Whole-tournament odds land with the next engine run.</p>
      </section>
    );
  }

  return (
    <section aria-label="Champion odds">
      <div className="overflow-hidden rounded-xl border bg-card">
        <div className={cn(GRID, "border-b px-2.5 py-2")}>
          <span />
          <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">Team</span>
          {REACH_STAGES.map((stage) => (
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
              className={cn(GRID, "w-full px-2.5 py-1.5 text-left text-xs hover:bg-secondary/60")}
            >
              <span className="tabular-nums text-muted-foreground">{rank + 1}</span>
              <span className={cn("truncate font-medium", row.isEngland && "text-gold")}>{row.name}</span>
              {row.reach.map((prob, i) => (
                <span
                  key={REACH_STAGES[i].key}
                  className={cn(
                    "text-right tabular-nums",
                    i === row.reach.length - 1 ? "font-semibold" : "text-muted-foreground",
                  )}
                >
                  {formatPctBare(prob)}
                </span>
              ))}
            </button>
          ))}
        </div>
      </div>
      <p className="mt-2 px-1 text-xs text-muted-foreground">
        Each column is the share of simulations (%) in which the team reaches that round. W is winning the
        lot. Tap a team for the full sheet.
      </p>
    </section>
  );
}
