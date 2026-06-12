import Link from "next/link";
import { notFound } from "next/navigation";
import { SeriesChart } from "@/components/charts/series-chart";
import { SurvivalStaircase } from "@/components/charts/survival-staircase";
import { ErrorState } from "@/components/shell/error-state";
import { Kicker } from "@/components/shell/kicker";
import { FixtureList } from "@/components/team/fixture-list";
import { GroupStanding } from "@/components/team/group-standing";
import { WhatIfPanel } from "@/components/team/what-if-panel";
import { orNull } from "@/lib/api";
import { fixturesFor, nextFixtureFor, shortCity, titleProb } from "@/lib/derive";
import { formatPct1 } from "@/lib/format";
import { LedgerList } from "@/components/runs/ledger-list";
import { rankedLedger } from "@/lib/ledger";
import { loadLatestSnapshot } from "@/lib/load-snapshot";
import { loadTeamHistory } from "@/lib/runs";
import { groupStandings, staircase } from "@/lib/team-view";

interface TeamPageProps {
  params: Promise<{ teamId: string }>;
}

export default async function TeamPage({ params }: TeamPageProps) {
  const { teamId } = await params;
  const [result, historyResult] = await Promise.all([loadLatestSnapshot(), loadTeamHistory(teamId)]);
  if (!result.ok) return <ErrorState error={result.error} context="Teams" />;
  const snapshot = result.data;

  const team = snapshot.teams.find((t) => t.team_id === teamId);
  if (!team) notFound();

  const isFocus = teamId === snapshot.focus.team_id;
  const names = new Map(snapshot.teams.map((t) => [t.team_id, t.name]));
  const published = titleProb(snapshot, teamId);
  const market = snapshot.markets?.market_probs?.[teamId] ?? null;
  const gapPp = published !== null && market !== null ? (published - market) * 100 : null;

  const reach = isFocus ? snapshot.focus.reach_probs : (team.reach_probs ?? {});
  const fixtures = fixturesFor(snapshot, teamId);
  const next = nextFixtureFor(snapshot, teamId, new Date());
  const whatIf = isFocus
    ? (snapshot.focus.what_if ?? []).find((fixture) => fixture.match === next?.match)
    : undefined;
  const road = isFocus ? (snapshot.focus.modal_path ?? []) : [];
  const story = isFocus ? (snapshot.agent?.narrative.focus_story ?? null) : null;
  const ledger = rankedLedger(snapshot, 4, teamId);
  const history = orNull(historyResult);

  return (
    <>
      <section className="wrap pt-20 pb-12">
        <Kicker>
          Group {team.group} · run {snapshot.run.run_id}
        </Kicker>
        <h1 className="statement statement-hero">
          <b className={`font-medium ${isFocus ? "text-red" : ""}`}>{team.name}.</b>
          <br />
          {published !== null ? formatPct1(published) : "—"}
          {gapPp !== null && (
            <span className="text-cream-faint"> {gapDescription(gapPp)}</span>
          )}
        </h1>
        {market !== null && (
          <p className="lede mt-[18px]">
            The market has {team.name} at {(market * 100).toFixed(1)}%
            {gapPp !== null ? `; we publish ${(gapPp > 0 ? "+" : "−") + Math.abs(gapPp).toFixed(1)}pp ${gapPp > 0 ? "above" : "below"} it.` : "."}
          </p>
        )}
      </section>

      <section className="wrap border-t border-hairline py-14">
        <Kicker>Surviving the rounds</Kicker>
        <SurvivalStaircase steps={staircase(reach)} featured={isFocus} />
      </section>

      {road.length > 0 && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>The road, drawn</Kicker>
          <div className="max-w-[880px]">
            {road.map((step) => (
              <div
                key={step.round}
                className="grid grid-cols-[64px_1fr_auto] items-baseline gap-x-[clamp(14px,3vw,28px)] border-b border-hairline py-3.5"
              >
                <span className="font-mono text-[12px] uppercase tracking-[0.12em] text-cream-faint">{step.round}</span>
                <span className="text-[clamp(19px,2.8vw,26px)] font-light">
                  {shortCity(step.city)}
                  <span className="ml-3 text-[14px] text-cream-faint">
                    likely {names.get(step.opponent_id) ?? step.opponent_id}
                  </span>
                </span>
                <span className="font-mono text-[15px] text-cream-dim">{formatPct1(step.opponent_prob)}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {whatIf && next && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>What the next game decides</Kicker>
          <WhatIfPanel
            fixture={whatIf}
            opponentName={names.get((next.home_id === teamId ? next.away_id : next.home_id) ?? "") ?? "next"}
          />
        </section>
      )}

      <section className="wrap border-t border-hairline py-14">
        <Kicker>The group</Kicker>
        <GroupStanding group={team.group} rows={groupStandings(snapshot, team.group)} teamId={teamId} names={names} />
      </section>

      <section className="wrap border-t border-hairline py-14">
        <Kicker>Fixtures</Kicker>
        <FixtureList fixtures={fixtures} teamId={teamId} names={names} />
      </section>

      {(story || ledger.length > 0) && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>The case</Kicker>
          {story && (
            <p className="max-w-[52ch] text-[clamp(18px,2.4vw,22px)] font-light leading-[1.55]">&ldquo;{story}&rdquo;</p>
          )}
          {story && (
            <div className="mt-3.5 font-mono text-[12.5px] text-cream-faint">
              agent synthesis ·{" "}
              <Link href={`/runs/${snapshot.run.run_id}`} className="border-b border-hairline pb-0.5">
                {snapshot.run.run_id}
              </Link>
            </div>
          )}
          {ledger.length > 0 && (
            <div className="mt-7">
              <LedgerList entries={ledger} />
            </div>
          )}
        </section>
      )}

      {history && (
        <section className="wrap border-t border-hairline py-14">
          <Kicker>A number with a memory</Kicker>
          <SeriesChart
            series={[
              {
                teamId,
                name: team.name,
                featured: isFocus,
                colour: isFocus ? "oklch(0.69 0.19 25)" : "oklch(0.965 0.008 95 / 0.5)",
                points: history.points,
              },
            ]}
            ariaLabel={`${team.name} title probability over published runs`}
          />
        </section>
      )}
    </>
  );
}

function gapDescription(gapPp: number): string {
  if (gapPp <= -1.5) return "and drifting.";
  if (gapPp >= 1.5) return "and backed.";
  return "and holding.";
}
