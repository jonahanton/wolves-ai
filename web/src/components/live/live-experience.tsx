"use client";

import Link from "next/link";
import { LiveImpact } from "@/components/live/live-impact";
import { Kicker } from "@/components/shell/kicker";
import { useImpact } from "@/hooks/use-impact";
import { useLiveState } from "@/hooks/use-live-state";
import { formatKickoffTime, formatPct } from "@/lib/format";
import { isStale, type LiveFixture, type LiveState } from "@/lib/live";
import type { Impact } from "@/lib/impact";

interface LiveExperienceProps {
  initialLive: LiveState;
  initialImpact: Impact | null;
  names: Record<string, string>;
  focusId: string;
}

const COUNT_WORDS: Record<number, string> = {
  1: "One game on.",
  2: "Two games on.",
  3: "Three games on.",
  4: "Four games on.",
};

export function LiveExperience({ initialLive, initialImpact, names, focusId }: LiveExperienceProps) {
  const live = useLiveState(initialLive) ?? initialLive;
  const impact = useImpact(initialImpact);
  const anyLive = live.live_match_count > 0;
  const hasImpact = impact !== null && impact.fixtures.length > 0;
  const slate = live.fixtures.filter((f) => f.status !== "live");

  return (
    <section className="wrap py-[clamp(28px,6vh,72px)]">
      <Kicker>
        {anyLive && (
          <span className="mr-2 inline-block h-[7px] w-[7px] animate-pulse rounded-pill bg-red align-middle motion-reduce:animate-none" />
        )}
        Live · {live.source}
      </Kicker>
      <h1 className="statement">
        {anyLive ? (
          <>
            {COUNT_WORDS[live.live_match_count] ?? `${live.live_match_count} games on.`}
            <br />
            <b className="font-medium">The bracket is moving.</b>
          </>
        ) : (
          <>
            Today&apos;s slate.
            <br />
            <b className="font-medium">Kick-offs and forecasts.</b>
          </>
        )}
      </h1>

      {live.poll_status === "failed" && (
        <Banner text={`Last poll failed${live.message ? `: ${live.message}` : ""}. Showing the previous state.`} />
      )}
      {live.poll_status === "ok" && isStale(live) && (
        <Banner text={`Stale: nothing fresh since ${formatKickoffTime(live.fetched_at)}.`} />
      )}

      {hasImpact && impact && (
        <div className="mt-[clamp(28px,5vh,52px)]">
          <LiveImpact impact={impact} focusId={focusId} />
          <p className="mt-7 max-w-[640px] font-mono text-[11.5px] leading-relaxed text-cream-faint">
            The running estimate holds the current score to full time and shifts the published forecast by the same
            amount. The AI has not re-forecast.
          </p>
        </div>
      )}

      {slate.length > 0 && (
        <div className="mt-[clamp(36px,6vh,64px)] max-w-[760px]">
          <div className="mb-3 font-mono text-[12px] uppercase tracking-[0.14em] text-cream-faint">
            {hasImpact ? "Rest of the day" : "Today"}
          </div>
          {slate.map((fixture) => (
            <SlateRow key={fixture.external_id} fixture={fixture} focusId={focusId} names={names} />
          ))}
        </div>
      )}
    </section>
  );
}

function Banner({ text }: { text: string }) {
  return <div className="mt-8 border border-hairline px-4 py-3 font-mono text-[13px] text-gold">{text}</div>;
}

interface SlateRowProps {
  fixture: LiveFixture;
  focusId: string;
  names: Record<string, string>;
}

function SlateRow({ fixture, focusId, names }: SlateRowProps) {
  const involvesFocus = fixture.home_id === focusId || fixture.away_id === focusId;
  const finished = fixture.status === "finished" || fixture.status === "abandoned";
  const score =
    fixture.home_goals !== null && fixture.home_goals !== undefined
      ? `${fixture.home_goals}–${fixture.away_goals}`
      : null;

  const body = (
    <>
      <div className="flex items-baseline justify-between gap-3">
        <span className={`text-[clamp(16px,2.2vw,19px)] ${involvesFocus ? "font-medium text-red" : "text-cream-dim"}`}>
          {names[fixture.home_id ?? ""] ?? fixture.home_name}{" "}
          {score ? <b className="font-mono font-medium text-cream tabular-nums">{score}</b> : "v"}{" "}
          {names[fixture.away_id ?? ""] ?? fixture.away_name}
        </span>
        <span className="whitespace-nowrap font-mono text-[13px] text-cream-faint">
          {fixture.status === "finished" ? "FT" : fixture.status === "abandoned" ? "ABD" : formatKickoffTime(fixture.kickoff)}
        </span>
      </div>
      {fixture.forecast && !finished && (
        <div className="mt-1.5 font-mono text-[12.5px] text-cream-faint">
          {fixture.home_name} {formatPct(fixture.forecast.p_home)}
          {fixture.forecast.p_draw !== null && fixture.forecast.p_draw !== undefined
            ? ` · draw ${formatPct(fixture.forecast.p_draw)}`
            : ""}{" "}
          · {fixture.away_name} {formatPct(fixture.forecast.p_away)}
        </div>
      )}
    </>
  );

  if (fixture.match === null) return <div className="border-b border-hairline py-3.5">{body}</div>;
  return (
    <Link href={`/match/${fixture.match}`} className="block border-b border-hairline py-3.5">
      {body}
    </Link>
  );
}
