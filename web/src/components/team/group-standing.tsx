import Link from "next/link";
import { formatPct } from "@/lib/format";
import type { StandingRow } from "@/lib/team-view";

interface GroupStandingProps {
  group: string;
  rows: StandingRow[];
  teamId: string;
  names: Map<string, string>;
}

export function GroupStanding({ group, rows, teamId, names }: GroupStandingProps) {
  return (
    <div className="max-w-[760px]">
      <div className="grid grid-cols-[1fr_auto_auto_auto] gap-x-5 border-b border-hairline pb-2 font-mono text-[11.5px] uppercase tracking-[0.12em] text-cream-faint">
        <span>Group {group}</span>
        <span>win grp</span>
        <span>qualify</span>
        <span>exp pts</span>
      </div>
      {rows.map((row) => (
        <Link
          key={row.teamId}
          href={`/teams/${row.teamId}`}
          className={`grid grid-cols-[1fr_auto_auto_auto] gap-x-5 border-b border-hairline py-3 ${
            row.teamId === teamId ? "text-cream" : "text-cream-dim"
          }`}
        >
          <span className={row.teamId === teamId ? "font-medium" : ""}>{names.get(row.teamId) ?? row.teamId}</span>
          <span className="font-mono text-[14px]">{formatPct(row.winGroup)}</span>
          <span className="font-mono text-[14px]">{formatPct(row.qualified)}</span>
          <span className="font-mono text-[14px]">{row.expectedPoints.toFixed(1)}</span>
        </Link>
      ))}
    </div>
  );
}
