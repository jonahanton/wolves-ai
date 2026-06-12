"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { ToggleTabs } from "@/components/charts/toggle-tabs";
import { ForecastChart } from "@/components/landing/forecast-chart";
import { HeroVideo } from "@/components/landing/hero-video";
import { WhySection } from "@/components/landing/why-section";
import { Kicker } from "@/components/shell/kicker";
import { useImpact } from "@/hooks/use-impact";
import type { TitleRank } from "@/lib/derive";
import {
  assembleChartData,
  type ChartTeamInput,
  type Outcome,
  OUTCOMES,
  type Source,
} from "@/lib/forecast-series";
import { formatDeltaPts, formatPct1 } from "@/lib/format";
import type { Impact } from "@/lib/impact";
import type { ImpliedReachPoint } from "@/lib/market-reach";
import type { PlayedResultRow } from "@/lib/results";
import type { LedgerEntryOut } from "@/lib/snapshot";

interface LandingForecastProps {
  now: number;
  leader: TitleRank | null;
  focus: TitleRank | null;
  runLabel: string;
  teams: ChartTeamInput[];
  marketReach: ImpliedReachPoint[];
  results: PlayedResultRow[];
  initialImpact: Impact | null;
  names: Record<string, string>;
  focusId: string;
  reasoning: string | null;
  evidence: LedgerEntryOut[];
}

const SOURCES: { key: Source; label: React.ReactNode }[] = [
  {
    key: "wolves",
    label: (
      <>
        <span className="sm:hidden">Wolves</span>
        <span className="hidden sm:inline">Wolves forecast</span>
      </>
    ),
  },
  { key: "market", label: "Market" },
];

function ordinal(rank: number): string {
  const tail = rank % 10;
  const teens = rank % 100;
  if (teens >= 11 && teens <= 13) return `${rank}th`;
  return `${rank}${tail === 1 ? "st" : tail === 2 ? "nd" : tail === 3 ? "rd" : "th"}`;
}

function focusFragment(impact: Impact | null, focusId: string): string | null {
  const champion = impact?.teams[focusId]?.champion;
  if (!impact || !champion) return null;
  const parts: string[] = [];
  if (Math.abs(champion.fromResultsPp) >= 0.05) {
    const since = new Date(impact.agentAsOf).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
    parts.push(`${formatDeltaPts(champion.fromResultsPp)}pt since ${since}`);
  }
  if (Math.abs(champion.fromIngamePp) >= 0.05) {
    const fixture = impact.fixtures.find((f) => f.homeId === focusId || f.awayId === focusId);
    const score =
      fixture && fixture.homeGoals !== null
        ? ` ${fixture.homeGoals}-${fixture.awayGoals}${fixture.minute !== null ? ` ${fixture.minute}′` : ""}`
        : "";
    parts.push(`est. ${formatDeltaPts(champion.fromIngamePp)}pt in-game${score}`);
  }
  return parts.length ? parts.join(" · ") : null;
}

export function LandingForecast(props: LandingForecastProps) {
  const { now, leader, focus, runLabel, teams, marketReach, results, initialImpact, names, focusId } = props;
  const impact = useImpact(initialImpact);
  const [source, setSource] = useState<Source>("wolves");
  const [outcome, setOutcome] = useState<Outcome>("champion");

  const data = useMemo(
    () => assembleChartData(teams, marketReach, impact, results, names, now),
    [teams, marketReach, impact, results, names, now],
  );
  const fragment = focusFragment(impact, focusId);
  const outcomeMeta = OUTCOMES.find((o) => o.key === outcome) ?? OUTCOMES[0];
  const singleRun = source === "wolves" && Math.max(...data.teams.map((t) => t.wolves[outcome].length), 0) <= 1;
  const live = (impact?.fixtures.length ?? 0) > 0;
  const runLabelNb = runLabel.replace(/ /g, " ");

  const caption =
    source === "wolves"
      ? singleRun
        ? "one full AI forecast so far · a new point lands with every run; the dotted line estimates between them"
        : "◆ full AI forecasts · the dotted line is our running estimate between them"
      : "bookmaker prices with the margin removed · stages below the winner are implied from those prices";

  return (
    <>
      <HeroVideo />

      <section className="relative">
        <div className="wrap pt-[clamp(14px,2.5vh,28px)] pb-[clamp(32px,5vh,56px)]">
          <div className="flex items-baseline justify-between gap-x-8">
            <Kicker className="mb-0!">World Cup winner</Kicker>
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-cream-faint">Run {runLabelNb}</span>
          </div>
          <h1 className="mt-3 mb-5 text-[clamp(24px,3.6vw,38px)] font-light tracking-[-0.015em] text-cream">
            Chance of {outcomeMeta.phrase}
          </h1>
          <ForecastChart
            data={data}
            source={source}
            outcome={outcome}
            ariaLabel={`Chance of ${outcomeMeta.phrase} over time, ${source === "wolves" ? "the Wolves forecast" : "the market"}`}
          />
          <div className="mt-5 flex flex-wrap items-center justify-between gap-x-8 gap-y-4 border-t border-hairline pt-4">
            <ToggleTabs
              options={OUTCOMES.map((o) => ({
                key: o.key,
                label: (
                  <>
                    <span className="sm:hidden">{o.short}</span>
                    <span className="hidden sm:inline">{o.label}</span>
                  </>
                ),
              }))}
              value={outcome}
              onChange={setOutcome}
              ariaLabel="Outcome"
            />
            <ToggleTabs options={SOURCES} value={source} onChange={setSource} ariaLabel="Forecast source" />
          </div>
          <div className="mt-4 font-mono text-[11.5px] text-cream-faint">{caption}</div>
        </div>
      </section>

      <section className="relative border-t border-hairline">
        <div className="wrap py-[clamp(30px,5vh,56px)]">
          <Kicker className="mb-[clamp(12px,1.8vh,18px)]!">Where it stands</Kicker>
          <div className="max-w-[600px]">
            {leader ? (
              <>
                <ScoreRow name={leader.name} value={formatPct1(leader.prob)} />
                {focus && focus.teamId !== leader.teamId && (
                  <ScoreRow name={focus.name} rank={ordinal(focus.rank)} value={formatPct1(focus.prob)} featured />
                )}
              </>
            ) : (
              <h1 className="statement">The field is open.</h1>
            )}
          </div>
          {(fragment || live) && (
            <div className="mt-[clamp(14px,2.2vh,22px)] flex flex-wrap items-baseline gap-x-5 gap-y-2">
              {fragment && (
                <span className="font-mono text-[clamp(12.5px,1.7vw,14.5px)] tabular-nums text-cream-dim">{fragment}</span>
              )}
              {live && (
                <Link
                  href="/live"
                  className="group inline-flex items-center gap-2 font-mono text-[12px] uppercase tracking-[0.14em] text-red transition-colors hover:text-cream"
                >
                  <span className="inline-block h-[6px] w-[6px] animate-pulse rounded-pill bg-red motion-reduce:animate-none" />
                  Live now
                  <span className="transition-transform group-hover:translate-x-0.5">&#8594;</span>
                </Link>
              )}
            </div>
          )}
        </div>
      </section>

      {props.reasoning && (
        <section className="relative border-t border-hairline py-[clamp(44px,7vh,84px)]">
          <div className="wrap">
            <WhySection reasoning={props.reasoning} runLabel={runLabel} evidence={props.evidence} />
          </div>
        </section>
      )}
    </>
  );
}

interface ScoreRowProps {
  name: string;
  value: string;
  rank?: string;
  featured?: boolean;
}

function ScoreRow({ name, value, rank, featured = false }: ScoreRowProps) {
  return (
    <div className="flex items-baseline justify-between gap-5 border-b border-hairline py-[clamp(7px,1.2vh,12px)] last:border-b-0">
      <span
        className={`flex items-baseline gap-3 text-[clamp(30px,5.4vw,54px)] font-light tracking-[-0.02em] ${featured ? "text-red" : "text-cream"}`}
      >
        {name}
        {rank && (
          <span className="font-mono text-[clamp(11px,1.5vw,14px)] uppercase tracking-[0.12em] text-cream-faint">
            {rank}
          </span>
        )}
      </span>
      <span
        className={`shrink-0 text-[clamp(28px,4.8vw,48px)] font-light tabular-nums tracking-[-0.01em] ${featured ? "text-red" : "text-cream"}`}
      >
        {value}
      </span>
    </div>
  );
}
