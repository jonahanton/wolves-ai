"use client";

import { useState } from "react";
import { PillToggle } from "@/components/charts/pill-toggle";
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
    <div className="space-y-10">
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
    <article className="max-w-[720px]">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h3 className="font-mono text-[clamp(20px,3vw,26px)] font-medium tabular-nums">
          {fixture.homeName} {fixture.homeGoals ?? 0}-{fixture.awayGoals ?? 0} {fixture.awayName}
        </h3>
        {fixture.minute !== null && (
          <span className="font-mono text-[14px] text-red">
            {fixture.minute}&#8242;
            <span className="ml-1.5 inline-block h-[7px] w-[7px] animate-pulse rounded-pill bg-red align-middle motion-reduce:animate-none" />
          </span>
        )}
      </div>
      {fixture.pHome !== null && fixture.pAway !== null && (
        <div className="mt-4">
          <WdlStrip
            win={fixture.pHome}
            draw={fixture.pDraw}
            lose={fixture.pAway}
            winLabel={fixture.homeName}
            loseLabel={fixture.awayName}
          />
        </div>
      )}
      {playable.length > 1 && (
        <div className="mt-5">
          <PillToggle
            options={playable.map((side) => ({ key: side.key, label: side.label }))}
            value={teamId}
            onChange={setTeamId}
            ariaLabel="Team to inspect"
          />
        </div>
      )}
      {stages ? (
        <div className="mt-5 border-t border-hairline">
          {HEADLINE_ROWS.map((row) =>
            stages[row.key] ? (
              <ImpactRow key={row.key} stage={stages[row.key]} phrase={`${teamLabel} ${row.phrase}`} />
            ) : null,
          )}
          <details className="group border-b border-hairline py-3">
            <summary className="cursor-pointer list-none font-mono text-[12px] uppercase tracking-[0.14em] text-cream-faint transition-colors hover:text-cream-dim">
              <span className="mr-2 inline-block transition-transform group-open:rotate-90">›</span>
              The full ladder
            </summary>
            <div className="mt-2">
              {LADDER_ROWS.map((row) =>
                stages[row.key] ? (
                  <ImpactRow
                    key={row.key}
                    stage={stages[row.key]}
                    phrase={`${teamLabel} ${row.phrase}`}
                    minor
                  />
                ) : null,
              )}
            </div>
          </details>
        </div>
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
    <div
      className={`flex flex-wrap items-baseline justify-between gap-x-6 gap-y-0.5 py-3 ${minor ? "" : "border-b border-hairline"}`}
    >
      <span className={`${minor ? "text-[14px]" : "text-[15.5px]"} text-cream-dim`}>
        <span className={`mr-2.5 font-mono tabular-nums ${deltaClass}`}>
          {delta === 0 ? "·" : `${formatDeltaPts(delta)}pt`}
        </span>
        {phrase}
      </span>
      <span className="font-mono text-[13px] tabular-nums text-cream-faint">
        {formatPct1(start)} &#8594; <b className="font-medium text-cream-dim">{formatPct1(stage.estimated)}</b>
      </span>
    </div>
  );
}
