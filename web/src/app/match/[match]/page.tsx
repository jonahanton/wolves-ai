import { notFound } from "next/navigation";
import { WdlStrip } from "@/components/charts/wdl-strip";
import { WormChart } from "@/components/charts/worm-chart";
import { MatchLivePanel } from "@/components/match/match-live-panel";
import { ErrorState } from "@/components/shell/error-state";
import { Kicker } from "@/components/shell/kicker";
import { WhatIfPanel } from "@/components/team/what-if-panel";
import { orNull } from "@/lib/api";
import { formatKickoff, formatPct } from "@/lib/format";
import { LedgerList } from "@/components/runs/ledger-list";
import { rankedLedger } from "@/lib/ledger";
import { loadLiveHistory, loadLiveState } from "@/lib/live";
import { loadLatestSnapshot } from "@/lib/load-snapshot";
import { wormGeometry } from "@/lib/worm";

interface MatchPageProps {
  params: Promise<{ match: string }>;
}

export default async function MatchPage({ params }: MatchPageProps) {
  const { match: matchParam } = await params;
  const matchNumber = Number(matchParam);
  if (!Number.isInteger(matchNumber) || matchNumber < 1 || matchNumber > 104) notFound();

  const [result, liveResult] = await Promise.all([loadLatestSnapshot(), loadLiveState()]);
  if (!result.ok) return <ErrorState error={result.error} context="Match" />;
  const snapshot = result.data;

  const match = (snapshot.matches ?? []).find((m) => m.match === matchNumber);
  if (!match) notFound();

  const names = new Map(snapshot.teams.map((t) => [t.team_id, t.name]));
  const homeName = names.get(match.home_id) ?? match.home_id;
  const awayName = names.get(match.away_id) ?? match.away_id;
  const focusId = snapshot.focus.team_id;
  const isGroup = match.stage === "group";
  const involvesFocus = match.home_id === focusId || match.away_id === focusId;

  const whatIf = involvesFocus
    ? (snapshot.focus.what_if ?? []).find((fixture) => fixture.match === matchNumber)
    : undefined;
  const caseEntries = [
    ...rankedLedger(snapshot, 3, match.home_id),
    ...rankedLedger(snapshot, 3, match.away_id),
  ].slice(0, 5);

  const day = match.date.slice(0, 10);
  const history = orNull(await loadLiveHistory(day));
  const worm = history ? wormGeometry(history, matchNumber) : null;

  return (
    <>
      <section className="wrap pt-20 pb-12">
        <Kicker>
          {isGroup ? `Group ${snapshot.teams.find((t) => t.team_id === match.home_id)?.group ?? ""}` : match.stage} ·{" "}
          {match.city} · {formatKickoff(match.date)}
        </Kicker>
        <h1 className="statement statement-hero">
          <b className={`font-medium ${match.home_id === focusId ? "text-red" : ""}`}>{homeName}</b> v{" "}
          <b className={`font-medium ${match.away_id === focusId ? "text-red" : ""}`}>{awayName}</b>
        </h1>
        <div className="mt-8 max-w-[880px]">
          <WdlStrip
            win={match.p_home}
            draw={match.p_draw ?? null}
            lose={match.p_away}
            winLabel={homeName}
            loseLabel={awayName}
          />
          <div className="mt-4 flex flex-wrap gap-x-8 gap-y-1 font-mono text-[13px] text-cream-faint">
            {match.modal_score && <span>most likely {match.modal_score}</span>}
            {!isGroup && match.p_decided_90 !== null && match.p_decided_90 !== undefined && (
              <span>decided in 90: {formatPct(match.p_decided_90)}</span>
            )}
            {match.p_pairing !== null && match.p_pairing !== undefined && (
              <span>this pairing: {formatPct(match.p_pairing)}</span>
            )}
          </div>
        </div>
      </section>

      <MatchLivePanel initial={orNull(liveResult)} match={matchNumber} homeName={homeName} awayName={awayName} />

      {worm && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>How it has run</Kicker>
          <WormChart geometry={worm} homeName={homeName} awayName={awayName} />
        </section>
      )}

      {whatIf && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>What it decides</Kicker>
          <WhatIfPanel fixture={whatIf} opponentName={match.home_id === focusId ? awayName : homeName} />
        </section>
      )}

      {caseEntries.length > 0 && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>The case file</Kicker>
          <LedgerList entries={caseEntries} />
        </section>
      )}
    </>
  );
}
