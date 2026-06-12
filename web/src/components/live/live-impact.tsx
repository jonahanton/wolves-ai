"use client";

import { useState } from "react";
import { ToggleTabs } from "@/components/charts/toggle-tabs";
import { WdlStrip } from "@/components/charts/wdl-strip";
import { formatDeltaPts, formatPct1 } from "@/lib/format";
import type { Impact, ImpactFixture, StageImpact } from "@/lib/impact";

interface LiveImpactProps {
  impact: Impact;
  focusId: string;
}

const HEADLINE_ROWS = [
  { key: "r32", phrase: "qualify from the group" },
  { key: "champion", phrase: "win the World Cup" },
] as const;

const LADDER_ROWS = [
  { key: "r16", phrase: "reach the last 16" },
  { key: "qf", phrase: "reach the quarter-finals" },
  { key: "sf", phrase: "reach the semi-finals" },
  { key: "final", phrase: "reach the final" },
] as const;

function fixtureKey(fixture: ImpactFixture): string {
  return `${fixture.match ?? fixture.homeName}-${fixture.awayName}`;
}

export function LiveImpact({ impact, focusId }: LiveImpactProps) {
  return (
    <div className="space-y-[clamp(32px,5vh,52px)]">
      {impact.fixtures.map((fixture) => (
        <FixtureImpact key={fixtureKey(fixture)} fixture={fixture} impact={impact} focusId={focusId} />
      ))}
    </div>
  );
}

interface FixtureImpactProps {
  fixture: ImpactFixture;
  impact: Impact;
  focusId: string;
}

function FixtureImpact({ fixture, impact, focusId }: FixtureImpactProps) {
  const sides = [
    { key: fixture.homeId ?? "home", label: fixture.homeName },
    { key: fixture.awayId ?? "away", label: fixture.awayName },
  ];
  const playable = sides.filter((side) => impact.teams[side.key]);
  const [teamId, setTeamId] = useState(
    playable.find((side) => side.key === focusId)?.key ?? playable[0]?.key ?? sides[0].key,
  );
  const stages = impact.teams[teamId];
  const teamLabel = sides.find((side) => side.key === teamId)?.label ?? teamId;

  return (
    <article className="max-w-[760px] border-t border-hairline pt-[clamp(22px,3.5vh,34px)]">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h2 className="text-[clamp(23px,3.6vw,32px)] font-light tracking-[-0.01em]">
          {fixture.homeName}{" "}
          <b className="font-mono font-medium tabular-nums text-cream">
            {fixture.homeGoals ?? 0}&#8211;{fixture.awayGoals ?? 0}
          </b>{" "}
          {fixture.awayName}
        </h2>
        {fixture.minute !== null && (
          <span className="font-mono text-[14px] text-red">
            {fixture.minute}&#8242;
            <span className="ml-1.5 inline-block h-[7px] w-[7px] animate-pulse rounded-pill bg-red align-middle motion-reduce:animate-none" />
          </span>
        )}
      </div>
      {fixture.pHome !== null && fixture.pAway !== null && (
        <div className="mt-5">
          <WdlStrip
            win={fixture.pHome}
            draw={fixture.pDraw}
            lose={fixture.pAway}
            winLabel={fixture.homeName}
            loseLabel={fixture.awayName}
          />
        </div>
      )}
      {stages ? (
        <>
          <div className="mt-7 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
            <span className="font-mono text-[11.5px] uppercase tracking-[0.14em] text-cream-faint">
              If the score holds, the estimate moves
            </span>
            {playable.length > 1 && (
              <ToggleTabs
                options={playable.map((side) => ({ key: side.key, label: side.label }))}
                value={teamId}
                onChange={setTeamId}
                ariaLabel="Team to inspect"
              />
            )}
          </div>
          <div className="mt-4 border-t border-hairline">
            {HEADLINE_ROWS.map((row) =>
              stages[row.key] ? (
                <ImpactRow key={row.key} stage={stages[row.key]} phrase={`${teamLabel} to ${row.phrase}`} />
              ) : null,
            )}
            <details className="group">
              <summary className="cursor-pointer list-none border-b border-hairline py-3.5 font-mono text-[12px] uppercase tracking-[0.14em] text-cream-faint transition-colors hover:text-cream-dim">
                <span className="mr-2 inline-block transition-transform group-open:rotate-90">&#8250;</span>
                The full ladder
              </summary>
              {LADDER_ROWS.map((row) =>
                stages[row.key] ? (
                  <ImpactRow key={row.key} stage={stages[row.key]} phrase={`${teamLabel} to ${row.phrase}`} minor />
                ) : null,
              )}
            </details>
          </div>
        </>
      ) : (
        <p className="mt-5 text-[14.5px] text-cream-faint">No published forecast for either side.</p>
      )}
    </article>
  );
}

interface ImpactRowProps {
  stage: StageImpact;
  phrase: string;
  minor?: boolean;
}

function ImpactRow({ stage, phrase, minor = false }: ImpactRowProps) {
  const delta = stage.fromIngamePp;
  const start = stage.estimated - delta / 100;
  const deltaClass = delta > 0 ? "text-green" : delta < 0 ? "text-red" : "text-cream-faint";
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1 border-b border-hairline py-3.5">
      <span className={`${minor ? "text-[14.5px] text-cream-dim" : "text-[16px] text-cream"}`}>{phrase}</span>
      <span className="flex items-baseline gap-3 font-mono tabular-nums">
        <span className={`text-[13px] ${deltaClass}`}>{delta === 0 ? "no change" : `${formatDeltaPts(delta)}pt`}</span>
        <span className="text-[13px] text-cream-faint">
          {formatPct1(start)} &#8594; <b className="font-medium text-cream">{formatPct1(stage.estimated)}</b>
        </span>
      </span>
    </div>
  );
}
