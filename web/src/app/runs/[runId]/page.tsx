import { notFound } from "next/navigation";
import { ErrorState } from "@/components/shell/error-state";
import { Kicker } from "@/components/shell/kicker";
import { ClampedProse } from "@/components/runs/clamped-prose";
import { LedgerList } from "@/components/runs/ledger-list";
import { WorldsList } from "@/components/runs/worlds-list";
import { backendGetText, orNull } from "@/lib/api";
import { formatPct1, formatUpdated } from "@/lib/format";
import { rankedLedger } from "@/lib/ledger";
import { loadSnapshot } from "@/lib/load-snapshot";
import { titleMoves } from "@/lib/run-diff";
import { loadRunRecords, loadSnapshotIndex } from "@/lib/runs";
import type { Snapshot } from "@/lib/snapshot";

interface RunPageProps {
  params: Promise<{ runId: string }>;
}

export default async function RunPage({ params }: RunPageProps) {
  const { runId } = await params;
  if (!/^[A-Za-z0-9._-]{1,80}$/.test(runId)) notFound();

  const [result, indexResult, recordsResult] = await Promise.all([
    loadSnapshot(runId),
    loadSnapshotIndex(),
    loadRunRecords(),
  ]);
  if (!result.ok) {
    if (result.error.category === "not_found") notFound();
    return <ErrorState error={result.error} context="Runs" />;
  }
  const snapshot = result.data;
  const record = (orNull(recordsResult)?.runs ?? []).find((r) => r.runId === runId);

  const refs = orNull(indexResult)?.snapshots ?? [];
  const position = refs.findIndex((ref) => ref.runId === runId);
  const previousRef = position >= 0 ? refs[position + 1] : undefined;
  const previous = previousRef ? orNull(await loadSnapshot(previousRef.runId)) : null;
  const moves = previous ? titleMoves(snapshot, previous, 3) : [];

  const journal = orNull(await backendGetText(`/runs/${encodeURIComponent(runId)}/journal`));

  const agent = snapshot.agent;
  const names = new Map(snapshot.teams.map((t) => [t.team_id, t.name]));
  const focusId = snapshot.focus.team_id;
  const focusName = names.get(focusId) ?? focusId;

  return (
    <>
      <section className="wrap pt-20 pb-12">
        <Kicker>
          {snapshot.run.kind.replace("_", " ")} run · {formatUpdated(snapshot.run.created_at)}
          {record ? ` · $${record.cost.toFixed(2)}` : ""}
        </Kicker>
        <h1 className="statement statement-hero break-words">
          <b className="font-medium">{runId}</b>
        </h1>
        <p className="lede mt-[18px]">{headline(snapshot, moves, focusName)}</p>
      </section>

      {moves.length > 0 && previousRef && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>What moved · v {previousRef.runId}</Kicker>
          {previous && previous.run.kind !== snapshot.run.kind && (
            <p className="mb-6 max-w-[56ch] font-mono text-[12.5px] text-cream-faint">
              different loop than the previous run ({snapshot.run.kind.replace("_", " ")} v{" "}
              {previous.run.kind.replace("_", " ")}); moves reflect methodology as well as news
            </p>
          )}
          <div className="flex flex-wrap gap-x-[clamp(30px,6vw,64px)] gap-y-6">
            {moves.map((move) => (
              <div key={move.teamId}>
                <span
                  className={`block font-mono text-[clamp(30px,5vw,52px)] tracking-[-0.02em] ${
                    move.deltaPp > 0 ? "text-green" : "text-red"
                  }`}
                >
                  {move.deltaPp > 0 ? "+" : "−"}
                  {Math.abs(move.deltaPp).toFixed(1)}
                </span>
                <span className="mt-1.5 block font-mono text-[12px] uppercase tracking-[0.14em] text-cream-faint">
                  {move.name} · {(move.from * 100).toFixed(1)} → {(move.to * 100).toFixed(1)}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {agent && agent.worlds.length > 0 && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>The worlds it priced</Kicker>
          <WorldsList agent={agent} names={names} focusId={focusId} />
        </section>
      )}

      {agent && agent.quant_findings && agent.quant_findings.length > 0 && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>One day of news, weighed</Kicker>
          <div className="grid max-w-[880px] gap-px sm:grid-cols-2">
            {agent.quant_findings.map((finding) => (
              <div key={finding.node_id} className="border border-hairline p-5">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-mono text-[12px] uppercase tracking-[0.1em] text-cream-faint">
                    {finding.node_id}
                  </span>
                  {finding.headline_value !== null && (
                    <span className="font-mono text-[17px] text-gold">{finding.headline_value}</span>
                  )}
                </div>
                <p className="mt-2 text-[14.5px] font-light text-cream-dim">{finding.summary}</p>
                {finding.findings.length > 0 && (
                  <ul className="mt-2.5 space-y-1 text-[13.5px] font-light text-cream-faint">
                    {finding.findings.slice(0, 3).map((line, i) => (
                      <li key={i} className="line-clamp-2">
                        · {line}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {agent && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>Evidence ledger · {agent.ledger_entries.length} claims</Kicker>
          <LedgerList entries={rankedLedger(snapshot, 12)} showTiers />
        </section>
      )}

      {agent && (agent.market_justification || agent.change_justification || agent.escalations.length > 0) && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>The argument, on the record</Kicker>
          <div className="max-w-[68ch] space-y-6 text-[15.5px] font-light leading-[1.65] text-cream-dim">
            {agent.market_justification && <ClampedProse title="v the market" text={agent.market_justification} />}
            {agent.change_justification && <ClampedProse title="v yesterday" text={agent.change_justification} />}
            {agent.inconsistency_note && <ClampedProse title="inconsistency" text={agent.inconsistency_note} />}
            {agent.escalations.length > 0 && (
              <div>
                <div className="mb-2 font-mono text-[12px] uppercase tracking-[0.14em] text-gold">
                  escalations steelmanned
                </div>
                <ul className="space-y-1.5">
                  {agent.escalations.map((escalation, i) => (
                    <li key={i} className="line-clamp-3">
                      · {escalation}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      )}

      {agent?.governor && agent.governor.scale < 1 && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>Trust governor</Kicker>
          <p className="lede">
            Trailing record shrank the agent&apos;s deviation: scale {agent.governor.scale.toFixed(2)}, effective d{" "}
            {agent.governor.effective_d.toFixed(2)}.
          </p>
        </section>
      )}

      {typeof journal === "string" && journal.length > 0 && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>The journal</Kicker>
          <ClampedProse title="appended during the run" text={journal} mono />
        </section>
      )}
    </>
  );
}

function headline(snapshot: Snapshot, moves: { name: string; deltaPp: number }[], focusName: string): string {
  if (moves.length > 0) {
    const top = moves[0];
    return `${top.name} ${top.deltaPp > 0 ? "up" : "down"} ${Math.abs(top.deltaPp).toFixed(1)}pp on the day.`;
  }
  const leader = [...snapshot.teams].sort((a, b) => (b.champion_prob ?? 0) - (a.champion_prob ?? 0))[0];
  return leader
    ? `${leader.name} lead the published board at ${formatPct1(leader.champion_prob ?? 0)}; ${focusName} watched closely.`
    : "The first published run.";
}


