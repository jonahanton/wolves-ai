import Link from "next/link";
import { ErrorState } from "@/components/shell/error-state";
import { Kicker } from "@/components/shell/kicker";
import { orNull } from "@/lib/api";
import { formatUpdated } from "@/lib/format";
import { loadRunRecords, loadSnapshotIndex } from "@/lib/runs";

interface RunsPageProps {
  searchParams: Promise<{ kind?: string }>;
}

const KINDS = ["agent", "daily", "live"] as const;

export default async function RunsPage({ searchParams }: RunsPageProps) {
  const [indexResult, recordsResult, params] = await Promise.all([
    loadSnapshotIndex(),
    loadRunRecords(),
    searchParams,
  ]);
  if (!indexResult.ok) return <ErrorState error={indexResult.error} context="Runs" />;

  const records = new Map((orNull(recordsResult)?.runs ?? []).map((record) => [record.runId, record]));
  const kind = params.kind;
  const snapshots = indexResult.data.snapshots.filter((ref) => !kind || ref.kind === kind);

  return (
    <section className="wrap py-20">
      <Kicker>The machine · every published run</Kicker>
      <h1 className="statement">
        Nothing ships
        <br />
        <b className="font-medium">without a run id.</b>
      </h1>
      <nav className="mt-8 flex gap-4 font-mono text-[12.5px] uppercase tracking-[0.12em]">
        <Link href="/runs" className={kind ? "text-cream-faint" : "text-gold"}>
          All
        </Link>
        {KINDS.map((k) => (
          <Link key={k} href={`/runs?kind=${k}`} className={kind === k ? "text-gold" : "text-cream-faint hover:text-cream-dim"}>
            {k}
          </Link>
        ))}
      </nav>
      <div className="mt-8 max-w-[880px] border-t border-hairline">
        {snapshots.map((ref) => {
          const record = records.get(ref.runId);
          return (
            <Link
              key={ref.runId}
              href={`/runs/${ref.runId}`}
              className={`grid items-baseline gap-x-4 border-b border-hairline py-4 font-mono text-[14px] ${records.size > 0 ? "grid-cols-[1fr_auto] sm:grid-cols-[1fr_auto_auto_auto]" : "grid-cols-[1fr_auto] sm:grid-cols-[1fr_auto_auto]"}`}
            >
              <span className="truncate text-[15px] text-cream">{ref.runId}</span>
              <span className="hidden text-[11.5px] uppercase tracking-[0.1em] text-cream-faint sm:block">
                {ref.kind}
              </span>
              <span className="hidden text-cream-faint sm:block">{formatUpdated(ref.asOf)}</span>
              {records.size > 0 && (
                <span className={record?.status === "failed" ? "text-red" : "text-cream-dim"}>
                  {record ? (record.status === "failed" ? "failed" : `$${record.cost.toFixed(2)}`) : ""}
                </span>
              )}
            </Link>
          );
        })}
        {snapshots.length === 0 && (
          <p className="py-4 font-mono text-[14px] text-cream-faint">no published runs of this kind</p>
        )}
      </div>

    </section>
  );
}
