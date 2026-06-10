import { formatPctBare } from "@/lib/format";
import type { GroupTeamRow, GroupView } from "@/lib/groups-view";
import { heatFill } from "@/lib/heat";
import { cn } from "@/lib/utils";

const GRID = "grid grid-cols-[minmax(0,1fr)_2.4rem_2.4rem_2.4rem_2.4rem] items-stretch";

const PROB_COLUMNS: { label: string; value: (team: GroupTeamRow) => number }[] = [
  { label: "1st", value: (team) => team.winGroup },
  { label: "2nd", value: (team) => team.runnerUp },
  { label: "3rd+", value: (team) => team.thirdQualified },
];

interface GroupTablesProps {
  groups: GroupView[];
  onSelectTeam: (teamId: string) => void;
}

export function GroupTables({ groups, onSelectTeam }: GroupTablesProps) {
  if (groups.length === 0) {
    return (
      <section className="rounded-xl border bg-card p-3" aria-label="Group forecasts">
        <p className="text-sm text-muted-foreground">Group forecasts land with the next engine run.</p>
      </section>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-muted-foreground">Where each side most likely finishes, group by group.</p>
      {groups.map((group) => (
        <section key={group.group} aria-label={`Group ${group.group}`}>
          <div className="overflow-hidden rounded-xl border bg-card">
            <div className={cn(GRID, "items-center border-b px-3 py-2")}>
              <h2 className="text-sm font-semibold">Group {group.group}</h2>
              {["xPts", ...PROB_COLUMNS.map((column) => column.label)].map((label) => (
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
                  className={cn(GRID, "w-full px-3 text-left text-xs hover:bg-secondary/60")}
                >
                  <span className={cn("flex min-w-0 items-center font-medium", team.isEngland && "text-gold")}>
                    <span className="truncate">{team.name}</span>
                  </span>
                  <span className="flex items-center justify-end px-1 py-2 font-semibold">
                    {team.expectedPoints.toFixed(1)}
                  </span>
                  {PROB_COLUMNS.map((column) => {
                    const prob = column.value(team);
                    return (
                      <span
                        key={column.label}
                        className="flex items-center justify-end px-1 py-2 text-foreground/80"
                        style={{ backgroundColor: heatFill(prob, team.isEngland) }}
                      >
                        {formatPctBare(prob)}
                      </span>
                    );
                  })}
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
