"use client";

import { useMemo, useState } from "react";
import { PillToggle } from "@/components/charts/pill-toggle";
import { ForecastChart } from "@/components/landing/forecast-chart";
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

const SOURCES: { key: Source; label: string }[] = [
  { key: "wolves", label: "The Wolves" },
  { key: "market", label: "The market" },
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
    parts.push(`${formatDeltaPts(champion.fromResultsPp)} since ${since}`);
  }
  if (Math.abs(champion.fromIngamePp) >= 0.05) {
    const fixture = impact.fixtures.find((f) => f.homeId === focusId || f.awayId === focusId);
    const score =
      fixture && fixture.homeGoals !== null
        ? ` ${fixture.homeGoals}-${fixture.awayGoals}${fixture.minute !== null ? ` ${fixture.minute}′` : ""}`
        : "";
    parts.push(`est. ${formatDeltaPts(champion.fromIngamePp)} in-game${score}`);
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

  return (
    <div className="wrap relative pt-[clamp(64px,11svh,120px)] pb-[clamp(48px,8vh,90px)]">
        <Kicker>World Cup winner · run {runLabel}</Kicker>
        <h1 className="statement statement-hero mt-2">
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
        <div className="mt-3 font-mono text-[11px] uppercase tracking-[0.12em] text-cream-faint">
          Euros 2024 · the Wolves
        </div>

        <div className="mt-[clamp(34px,6vh,56px)]">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
            <span className="font-mono text-[13px] uppercase tracking-[0.14em] text-cream-dim">
              Chance of {outcomeMeta.phrase}
            </span>
            <PillToggle options={SOURCES} value={source} onChange={setSource} ariaLabel="Forecast source" />
          </div>
          <div className="mb-4">
            <PillToggle
              options={OUTCOMES.map((o) => ({ key: o.key, label: o.label }))}
              value={outcome}
              onChange={setOutcome}
              ariaLabel="Outcome"
            />
          </div>
          <ForecastChart
            data={data}
            source={source}
            outcome={outcome}
            ariaLabel={`Chance of ${outcomeMeta.phrase} over time, ${source === "wolves" ? "the Wolves' forecast" : "the market"}`}
          />
          <div className="mt-3 flex flex-wrap justify-between gap-2 font-mono text-[11.5px] text-cream-faint">
            <span>
              {source === "wolves"
                ? singleRun
                  ? "one full forecast published · the line grows with each run"
                  : "◆ full agent forecasts · dotted = engine estimate on the agent's scale"
                : "de-vigged bookmaker consensus · stages below the title are inverse-implied"}
            </span>
            {source === "wolves" && !singleRun && <span>hover a point for that day&apos;s results</span>}
          </div>
        </div>

        {props.reasoning && (
          <WhySection reasoning={props.reasoning} runLabel={runLabel} evidence={props.evidence} />
        )}

        {live && impact && (
          <div className="mt-[clamp(44px,7vh,72px)]">
            <Kicker>Live now</Kicker>
            <div className="mt-5">
              <LiveImpact impact={impact} focusId={focusId} />
            </div>
            <p className="mt-4 max-w-[640px] font-mono text-[11.5px] leading-relaxed text-cream-faint">
              Estimates hold the current scores to full time in the deterministic engine and move the agent&apos;s
              published numbers by the same amount in log odds. The agent itself has not re-forecast.
            </p>
          </div>
        )}
    </div>
  );
}
