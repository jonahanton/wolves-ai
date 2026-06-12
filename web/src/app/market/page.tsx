import Link from "next/link";
import { OddsStrip } from "@/components/market/odds-strip";
import { ErrorState } from "@/components/shell/error-state";
import { Kicker } from "@/components/shell/kicker";
import { orNull } from "@/lib/api";
import { titleProb } from "@/lib/derive";
import { formatPct1 } from "@/lib/format";
import { LedgerList } from "@/components/runs/ledger-list";
import { WorldsList } from "@/components/runs/worlds-list";
import { rankedLedger } from "@/lib/ledger";
import { loadLatestSnapshot } from "@/lib/load-snapshot";
import { divergenceRows, loadOddsDates, loadOddsDay, teamOddsSeries } from "@/lib/market-view";

export default async function MarketPage() {
  const [result, datesResult] = await Promise.all([loadLatestSnapshot(), loadOddsDates()]);
  if (!result.ok) return <ErrorState error={result.error} context="Us v the market" />;
  const snapshot = result.data;

  if (!snapshot.markets?.market_probs) {
    return (
      <section className="wrap py-20">
        <Kicker>Us v the market</Kicker>
        <h1 className="statement">No market leg on this run.</h1>
        <p className="lede mt-[18px]">The published snapshot carries no market block; the comparison returns next run.</p>
      </section>
    );
  }

  const focusId = snapshot.focus.team_id;
  const focusName = snapshot.teams.find((t) => t.team_id === focusId)?.name ?? focusId;
  const ours = titleProb(snapshot, focusId);
  const market = snapshot.markets.market_probs[focusId] ?? null;
  const gapPp = ours !== null && market !== null ? (ours - market) * 100 : null;
  const rows = divergenceRows(snapshot, 1.0);
  const agent = snapshot.agent;

  const dates = orNull(datesResult)?.dates ?? [];
  const days = (await Promise.all(dates.slice(-7).map((date) => loadOddsDay(date))))
    .map(orNull)
    .filter((day): day is NonNullable<typeof day> => day !== null);
  const oddsSeries = teamOddsSeries(days, focusId);

  return (
    <>
      <section className="wrap pt-20 pb-12">
        <Kicker>Us v the market · run {snapshot.run.run_id}</Kicker>
        <h1 className="statement statement-hero">
          The market remembers.
          <br />
          <b className="font-medium">The model counts.</b>
        </h1>
        <div className="mt-[clamp(26px,4vh,44px)] flex gap-[clamp(30px,7vw,80px)]">
          <Figure value={ours} label={`our ${focusName}`} colour="text-red" />
          <Figure value={market} label="the market" colour="text-cream-dim" />
          {gapPp !== null && (
            <div>
              <span className="block font-mono text-[clamp(38px,6.4vw,64px)] tracking-[-0.02em] text-green">
                {gapPp > 0 ? "+" : "−"}
                {Math.abs(gapPp).toFixed(1)}
              </span>
              <span className="mt-2.5 block font-mono text-[12px] uppercase tracking-[0.14em] text-cream-faint">
                gap, pp
              </span>
            </div>
          )}
        </div>
      </section>

      <section className="wrap border-t border-hairline py-14">
        <Kicker>Where we differ · gaps over 1pp</Kicker>
        <div className="max-w-[760px]">
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-x-6 border-b border-hairline pb-2 font-mono text-[11.5px] uppercase tracking-[0.12em] text-cream-faint">
            <span>team</span>
            <span>us</span>
            <span>market</span>
            <span>gap</span>
          </div>
          {rows.map((row) => (
            <Link
              key={row.teamId}
              href={`/teams/${row.teamId}`}
              className="grid grid-cols-[1fr_auto_auto_auto] items-baseline gap-x-6 border-b border-hairline py-3"
            >
              <span className={row.teamId === focusId ? "font-medium text-red" : ""}>{row.name}</span>
              <span className="font-mono text-[14px]">{formatPct1(row.ours)}</span>
              <span className="font-mono text-[14px] text-cream-dim">{formatPct1(row.market)}</span>
              <span className={`font-mono text-[14px] ${row.gapPp > 0 ? "text-green" : "text-red"}`}>
                {row.gapPp > 0 ? "+" : "−"}
                {Math.abs(row.gapPp).toFixed(1)}
              </span>
            </Link>
          ))}
          {rows.length === 0 && <p className="lede py-3">No gaps above a point today; we are priced with the books.</p>}
        </div>
      </section>

      {agent && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>Why we differ</Kicker>
          {agent.market_justification && (
            <>
            <p className="line-clamp-[10] max-w-[60ch] whitespace-pre-line text-[clamp(16px,2vw,19px)] font-light leading-[1.6] text-cream-dim">
              {agent.market_justification}
            </p>
              <Link
                href={`/runs/${snapshot.run.run_id}`}
                className="mt-3 inline-block border-b border-hairline pb-0.5 font-mono text-[12.5px] text-cream-faint"
              >
                the full argument
              </Link>
            </>
          )}
          {agent.worlds.length > 0 && (
            <div className="mt-10">
              <div className="mb-3 font-mono text-[12px] uppercase tracking-[0.14em] text-cream-faint">
                The worlds we priced
              </div>
              <WorldsList
                agent={agent}
                names={new Map(snapshot.teams.map((t) => [t.team_id, t.name]))}
                focusId={focusId}
              />
            </div>
          )}
        </section>
      )}

      {oddsSeries.labels.length >= 2 && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>The price of {focusName}</Kicker>
          <OddsStrip series={oddsSeries} publishedProb={ours} teamName={focusName} />
        </section>
      )}

      {agent && rankedLedger(snapshot, 5).length > 0 && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>Evidence on file</Kicker>
          <LedgerList entries={rankedLedger(snapshot, 5)} />
        </section>
      )}
    </>
  );
}

interface FigureProps {
  value: number | null;
  label: string;
  colour: string;
}

function Figure({ value, label, colour }: FigureProps) {
  if (value === null) return null;
  return (
    <div>
      <span className={`block font-mono text-[clamp(38px,6.4vw,64px)] tracking-[-0.02em] ${colour}`}>
        {(value * 100).toFixed(1)}%
      </span>
      <span className="mt-2.5 block font-mono text-[12px] uppercase tracking-[0.14em] text-cream-faint">{label}</span>
    </div>
  );
}
