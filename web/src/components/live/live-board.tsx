"use client";

import Link from "next/link";
import { useLiveState } from "@/hooks/use-live-state";
import { formatKickoffTime, formatPct } from "@/lib/format";
import { isStale, type LiveFixture, type LiveState, topTitleMovers } from "@/lib/live";

interface LiveBoardProps {
  initial: LiveState;
  focusId: string;
  names: Record<string, string>;
}

export function LiveBoard({ initial, focusId, names }: LiveBoardProps) {
  const state = useLiveState(initial) ?? initial;
  const live = state.fixtures.filter((f) => f.status === "live");
  const scheduled = state.fixtures.filter((f) => f.status === "scheduled");
  const finished = state.fixtures.filter((f) => f.status === "finished" || f.status === "abandoned");
  const movers = topTitleMovers(state, 4);

  return (
    <div className="max-w-[880px]">
      {state.poll_status === "failed" && (
        <Banner text={`Last poll failed${state.message ? `: ${state.message}` : ""}. Showing the previous state.`} />
      )}
      {state.poll_status === "ok" && isStale(state) && (
        <Banner text={`Stale: nothing fresh since ${formatKickoffTime(state.fetched_at)}.`} />
      )}

      {live.map((fixture) => (
        <FixtureRow key={fixture.external_id} fixture={fixture} focusId={focusId} live />
      ))}
      {scheduled.map((fixture) => (
        <FixtureRow key={fixture.external_id} fixture={fixture} focusId={focusId} />
      ))}
      {finished.map((fixture) => (
        <FixtureRow key={fixture.external_id} fixture={fixture} focusId={focusId} />
      ))}
      {state.fixtures.length === 0 && <p className="lede">No fixtures in today&apos;s window.</p>}

      {movers.length > 0 && (
        <div className="mt-10">
          <div className="mb-3 font-mono text-[12px] uppercase tracking-[0.14em] text-cream-faint">
            Title race today, pp
          </div>
          {movers.map(([teamId, delta]) => (
            <div key={teamId} className="flex justify-between border-b border-hairline py-2.5 font-mono text-[15px]">
              <span className="text-cream-dim">{names[teamId] ?? teamId}</span>
              <span className={delta > 0 ? "text-green" : "text-red"}>
                {delta > 0 ? "+" : "−"}
                {Math.abs(delta).toFixed(1)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Banner({ text }: { text: string }) {
  return (
    <div className="mb-6 border border-hairline px-4 py-3 font-mono text-[13px] text-gold">{text}</div>
  );
}

interface FixtureRowProps {
  fixture: LiveFixture;
  focusId: string;
  live?: boolean;
}

function FixtureRow({ fixture, focusId, live = false }: FixtureRowProps) {
  const involvesFocus = fixture.home_id === focusId || fixture.away_id === focusId;
  const score =
    fixture.home_goals !== null && fixture.home_goals !== undefined
      ? `${fixture.home_goals}–${fixture.away_goals}`
      : null;

  const body = (
    <>
      <div className="flex items-baseline justify-between gap-3">
        <span className={`text-[clamp(18px,2.6vw,22px)] ${involvesFocus ? "font-medium text-red" : ""}`}>
          {fixture.home_name} {score ? <b className="font-mono font-medium text-cream">{score}</b> : "v"}{" "}
          {fixture.away_name}
        </span>
        <span className="whitespace-nowrap font-mono text-[13px] text-cream-faint">
          {live && fixture.minute !== null && fixture.minute !== undefined ? (
            <span className="text-red">{fixture.minute}&apos;</span>
          ) : fixture.status === "finished" ? (
            "FT"
          ) : fixture.status === "abandoned" ? (
            "ABD"
          ) : (
            formatKickoffTime(fixture.kickoff)
          )}
        </span>
      </div>
      {fixture.forecast && fixture.status !== "finished" && (
        <div className="mt-1.5 font-mono text-[12.5px] text-cream-faint">
          {fixture.home_name} {formatPct(fixture.forecast.p_home)}
          {fixture.forecast.p_draw !== null && fixture.forecast.p_draw !== undefined
            ? ` · draw ${formatPct(fixture.forecast.p_draw)}`
            : ""}{" "}
          · {fixture.away_name} {formatPct(fixture.forecast.p_away)}
          {fixture.forecast.modal_score ? ` · likely ${fixture.forecast.modal_score}` : ""}
        </div>
      )}
    </>
  );

  if (fixture.match === null) {
    return <div className="border-b border-hairline py-4">{body}</div>;
  }
  return (
    <Link href={`/match/${fixture.match}`} className="block border-b border-hairline py-4">
      {body}
    </Link>
  );
}
