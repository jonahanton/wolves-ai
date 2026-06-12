import Link from "next/link";
import { Kicker } from "@/components/shell/kicker";
import { formatUpdated } from "@/lib/format";
import type { RunRecord, SnapshotRef } from "@/lib/runs";

interface MachineSectionProps {
  snapshots: SnapshotRef[];
  records: RunRecord[];
  nSims: number;
}

export function MachineSection({ snapshots, records, nSims }: MachineSectionProps) {
  const recordById = new Map(records.map((record) => [record.runId, record]));
  const rows = snapshots.slice(0, 4);

  return (
    <section className="wrap border-t border-hairline py-[clamp(60px,10vh,120px)]">
      <Kicker>The machine</Kicker>
      <h2 className="statement">
        {nSims.toLocaleString("en-GB")} futures, <b className="font-medium">every morning.</b>
      </h2>
      <p className="lede mt-[18px]">
        A deterministic engine refits on every result. The superforecaster reads the news, argues in scenarios and
        cites every claim. Every published number traces to a run.
      </p>
      <div className="mt-[clamp(24px,4vh,40px)] max-w-[840px] border-t border-hairline">
        {rows.map((ref) => {
          const record = recordById.get(ref.runId);
          return (
            <Link
              key={ref.runId}
              href={`/runs/${ref.runId}`}
              className="grid grid-cols-[1fr_auto_auto] items-baseline gap-4 border-b border-hairline py-[15px] font-mono text-[14px] text-cream-dim"
            >
              <span className="truncate">{ref.runId}</span>
              <span className="text-[11.5px] uppercase tracking-[0.1em] text-cream-faint">{ref.kind}</span>
              <span>{record ? `$${record.cost.toFixed(2)}` : formatUpdated(ref.asOf)}</span>
            </Link>
          );
        })}
        {rows.length === 0 && (
          <div className="py-[15px] font-mono text-[14px] text-cream-faint">no published runs yet</div>
        )}
      </div>
    </section>
  );
}
