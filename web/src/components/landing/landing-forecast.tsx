"use client";

import { useEffect, useMemo, useState } from "react";
import { ToggleTabs } from "@/components/charts/toggle-tabs";
import { ForecastChart } from "@/components/landing/forecast-chart";
import { HeroVideo } from "@/components/landing/hero-video";
import { LiveImpact } from "@/components/landing/live-impact";
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

function LiveTabLabel() {
  return (
    <span className="inline-flex items-baseline gap-2">
      Live now
      <span className="inline-block h-[6px] w-[6px] animate-pulse rounded-pill bg-red motion-reduce:animate-none" />
    </span>
  );
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
  const [panel, setPanel] = useState<"why" | "live">("why");
  useEffect(() => {
    if (live) setPanel("live");
  }, [live]);
  const activePanel = live ? panel : "why";

  const caption =
    source === "wolves"
      ? singleRun
        ? "one full AI forecast published so far · a new point lands with every run"
        : "◆ full AI forecasts · the dotted line is our running estimate between them"
      : "bookmaker prices with the margin removed · stages below the winner are implied from those prices";

  return (
    <>
      <section className="relative">
        <HeroVideo />
        <div className="wrap relative pt-[clamp(44px,7svh,80px)] pb-[clamp(18px,2.5vh,30px)]">
          <Kicker>World Cup winner · run {runLabel.replace(/ /g, "\u00A0")}</Kicker>
          <h1 className="statement mt-2">
            {leader ? `${leader.name} ${formatPct1(leader.prob)}.` : "The field is open."}
            {focus && focus.teamId !== leader?.teamId && (
              <>
                <br />
                <b className="font-medium text-red">
                  {focus.name} {formatPct1(focus.prob)} · {ordinal(focus.rank)}.
                </b>
              </>
            )}
          </h1>
          {fragment && (
            <p className="mt-3 font-mono text-[clamp(13px,1.8vw,15px)] tabular-nums text-cream-dim">{fragment}</p>
          )}
        </div>
      </section>

      <section className="relative">
        <div className="wrap pt-[clamp(10px,1.5vh,20px)] pb-[clamp(44px,7vh,72px)]">
          <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-2 border-b border-hairline pb-1">
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
          <div className="mt-6 mb-2 font-mono text-[13px] uppercase tracking-[0.14em] text-cream-dim">
            Chance of {outcomeMeta.phrase}
          </div>
          <ForecastChart
            data={data}
            source={source}
            outcome={outcome}
            ariaLabel={`Chance of ${outcomeMeta.phrase} over time, ${source === "wolves" ? "the Wolves forecast" : "the market"}`}
          />
          <div className="mt-3 font-mono text-[11.5px] text-cream-faint">{caption}</div>
        </div>
      </section>

      <section className="relative border-t border-hairline py-[clamp(44px,7vh,84px)]">
        <div className="wrap">
          {live && (
            <div className="mb-8 border-b border-hairline pb-1">
              <ToggleTabs
                options={[
                  { key: "live" as const, label: <LiveTabLabel /> },
                  { key: "why" as const, label: "Why" },
                ]}
                value={activePanel}
                onChange={setPanel}
                ariaLabel="Section"
              />
            </div>
          )}

          {activePanel === "why" && props.reasoning && (
            <WhySection reasoning={props.reasoning} runLabel={runLabel} evidence={props.evidence} />
          )}

          {activePanel === "live" && impact && (
            <div>
              <LiveImpact impact={impact} focusId={focusId} />
              <p className="mt-4 max-w-[640px] font-mono text-[11.5px] leading-relaxed text-cream-faint">
                The running estimate holds the current scores to full time and shifts the published forecast
                by the same amount. The AI has not re-forecast.
              </p>
            </div>
          )}
        </div>
      </section>
    </>
  );
}
