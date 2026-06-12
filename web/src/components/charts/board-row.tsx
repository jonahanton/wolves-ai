import Link from "next/link";
import type { BoardRow } from "@/lib/derive";
import { formatPct1 } from "@/lib/format";

interface BoardRowItemProps {
  row: BoardRow;
  rank: number;
  featured: boolean;
  barMax: number;
}

export function BoardRowItem({ row, rank, featured, barMax }: BoardRowItemProps) {
  const width = `${Math.min(100, (row.prob / barMax) * 100).toFixed(1)}%`;
  return (
    <Link
      href={`/teams/${row.teamId}`}
      className="grid grid-cols-[34px_1fr_auto_auto] items-baseline gap-x-[clamp(12px,2.6vw,26px)] border-b border-hairline py-[17px]"
    >
      <span className="font-mono text-[13px] text-cream-faint">{String(rank).padStart(2, "0")}</span>
      <span className={`text-[clamp(19px,2.8vw,24px)] ${featured ? "font-medium text-red" : ""}`}>{row.name}</span>
      <span className="hidden font-mono text-[13px] text-cream-faint sm:block">
        {row.market !== null ? `mkt ${(row.market * 100).toFixed(1)}` : ""}
      </span>
      <span className="font-mono text-[clamp(19px,2.8vw,24px)]">{formatPct1(row.prob)}</span>
      <span className="relative col-span-full mt-2 h-[3px] rounded-pill bg-hairline">
        <i className={`absolute inset-y-0 left-0 rounded-pill ${featured ? "bg-red" : "bg-cream-dim"}`} style={{ width }} />
        {row.lo !== null && (
          <s className="absolute -top-[3.5px] h-[10px] w-[1.5px] bg-cream-faint" style={{ left: `${(row.lo / barMax) * 100}%` }} />
        )}
        {row.hi !== null && (
          <s className="absolute -top-[3.5px] h-[10px] w-[1.5px] bg-cream-faint" style={{ left: `${Math.min(100, (row.hi / barMax) * 100)}%` }} />
        )}
      </span>
    </Link>
  );
}
