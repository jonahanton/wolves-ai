import type { LedgerEntryOut } from "@/lib/snapshot";
import { sourceHost, statusMark, tierLabel } from "@/lib/ledger";

interface LedgerListProps {
  entries: LedgerEntryOut[];
  showTiers?: boolean;
}

export function LedgerList({ entries, showTiers = false }: LedgerListProps) {
  return (
    <div className="max-w-[760px] border-t border-hairline">
      {entries.map((entry) => (
        <div
          key={entry.id}
          className="flex justify-between gap-4 border-b border-hairline py-3.5 text-[15.5px] font-light text-cream-dim"
        >
          <span className="line-clamp-2">
            {entry.claim} — {sourceHost(entry.source_url)}
            {showTiers && tierLabel(entry.source_tier) && (
              <span className="ml-2 rounded-pill border border-hairline px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-[0.1em] text-cream-faint">
                {tierLabel(entry.source_tier)}
              </span>
            )}
          </span>
          <span className="whitespace-nowrap font-mono text-[12px] text-cream-faint">
            {entry.id} {statusMark(entry.status)}
          </span>
        </div>
      ))}
    </div>
  );
}
