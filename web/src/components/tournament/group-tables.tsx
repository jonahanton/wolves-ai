import { formatPctBare } from "@/lib/format";
import type { GroupView } from "@/lib/groups-view";
import { cn } from "@/lib/utils";

const GRID = "grid grid-cols-[minmax(0,1fr)_2.4rem_2.2rem_2.2rem_2.2rem] items-center gap-x-2";

interface GroupTablesProps {
  groups: GroupView[];
  onSelectTeam: (teamId: string) => void;
}

export function GroupTables({ groups, onSelectTeam }: GroupTablesProps) {
  if (groups.length === 0) {
    return (
      <section className="rounded-xl border bg-card p-4" aria-label="Group forecasts">
        <p className="text-sm text-muted-foreground">Group forecasts land with the next engine run.</p>
      </section>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {groups.map((group) => (
        <section key={group.group} aria-label={`Group ${group.group}`}>
          <div className="overflow-hidden rounded-xl border bg-card">
            <div className={cn(GRID, "border-b px-3 py-2")}>
              <h2 className="text-sm font-semibold">Group {group.group}</h2>
              {["xPts", "1st", "2nd", "3rd+"].map((label) => (
                <span
                  key={label}
                  className="text-right text-[11px] font-semibold tracking-wide text-muted-foreground uppercase"
                >
                  {label}
                </span>
              ))}
            </div>
            <div className="divide-y">
              {group.teams.map((team) => (
                <button
                  key={team.teamId}
                  type="button"
                  onClick={() => onSelectTeam(team.teamId)}
                  className={cn(GRID, "w-full px-3 py-1.5 text-left text-xs hover:bg-secondary/60")}
                >
                  <span className={cn("truncate font-medium", team.isEngland && "text-gold")}>{team.name}</span>
                  <span className="text-right font-semibold tabular-nums">{team.expectedPoints.toFixed(1)}</span>
                  <span className="text-right tabular-nums text-muted-foreground">
                    {formatPctBare(team.winGroup)}
                  </span>
                  <span className="text-right tabular-nums text-muted-foreground">
                    {formatPctBare(team.runnerUp)}
                  </span>
                  <span className="text-right tabular-nums text-muted-foreground">
                    {formatPctBare(team.thirdQualified)}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </section>
      ))}
      <p className="px-1 text-xs text-muted-foreground">
        xPts is expected group-stage points. 1st, 2nd and 3rd+ are the chance (%) of winning the group,
        finishing second, or going through as one of the best thirds.
      </p>
    </div>
  );
}
