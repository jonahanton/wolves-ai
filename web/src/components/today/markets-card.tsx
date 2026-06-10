import { formatDeltaPts, formatPct } from "@/lib/format";
import type { MarketsView } from "@/lib/markets";

interface MarketsCardProps {
  view: MarketsView;
}

export function MarketsCard({ view }: MarketsCardProps) {
  return (
    <section className="rounded-xl border bg-card p-3" aria-label="Model versus market">
      <h2 className="font-semibold">Model v market</h2>
      <div className="mt-3 grid grid-cols-[1fr_auto_auto_auto] gap-x-4 gap-y-1.5 text-sm">
        <span className="text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">Team</span>
        <span className="text-right text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          Model
        </span>
        <span className="text-right text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          Market
        </span>
        <span className="text-right text-[11px] font-semibold tracking-wide text-muted-foreground uppercase">
          Edge
        </span>
        {view.rows.map((row) => (
          <RowCells key={row.teamId} row={row} />
        ))}
      </div>
      {!view.hasMarketData && (
        <p className="mt-3 border-t pt-3 text-xs text-muted-foreground">
          Market prices land with the next engine run.
        </p>
      )}
    </section>
  );
}

interface RowCellsProps {
  row: MarketsView["rows"][number];
}

function RowCells({ row }: RowCellsProps) {
  return (
    <>
      <span className={`truncate ${row.isFocus ? "font-medium text-gold" : ""}`}>{row.name}</span>
      <span className="text-right tabular-nums font-medium">{formatPct(row.modelProb)}</span>
      <span className="text-right tabular-nums text-muted-foreground">
        {row.marketProb === null ? "–" : formatPct(row.marketProb)}
      </span>
      <span className="text-right tabular-nums text-muted-foreground">
        {row.deltaPts === null ? "–" : formatDeltaPts(row.deltaPts)}
      </span>
    </>
  );
}
