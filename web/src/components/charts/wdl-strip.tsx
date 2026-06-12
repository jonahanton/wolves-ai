import { formatPct } from "@/lib/format";

interface WdlStripProps {
  win: number;
  draw: number | null;
  lose: number;
  winLabel?: string;
  loseLabel?: string;
}

export function WdlStrip({ win, draw, lose, winLabel = "win", loseLabel = "lose" }: WdlStripProps) {
  const total = win + (draw ?? 0) + lose;
  const pct = (v: number) => `${((v / total) * 100).toFixed(1)}%`;
  return (
    <div>
      <div className="flex h-1 max-w-[880px] overflow-hidden rounded-pill bg-hairline">
        <span className="bg-red" style={{ width: pct(win) }} />
        {draw !== null && <span className="bg-cream-faint" style={{ width: pct(draw) }} />}
        <span className="bg-slate" style={{ width: pct(lose) }} />
      </div>
      <div className="mt-2.5 flex max-w-[880px] justify-between font-mono text-[13px] text-cream-faint">
        <span>
          {winLabel} {formatPct(win)}
        </span>
        {draw !== null && <span>draw {formatPct(draw)}</span>}
        <span>
          {loseLabel} {formatPct(lose)}
        </span>
      </div>
    </div>
  );
}
