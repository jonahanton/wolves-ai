"use client";

import { WdlStrip } from "@/components/charts/wdl-strip";
import { useLiveState } from "@/hooks/use-live-state";
import type { LiveState } from "@/lib/live";

interface MatchLivePanelProps {
  initial: LiveState | null;
  match: number;
  homeName: string;
  awayName: string;
}

export function MatchLivePanel({ initial, match, homeName, awayName }: MatchLivePanelProps) {
  const state = useLiveState(initial);
  const fixture = state?.fixtures.find((f) => f.match === match);
  if (!fixture || fixture.status === "scheduled") return null;

  const score = `${fixture.home_goals ?? 0}–${fixture.away_goals ?? 0}`;
  const finished = fixture.status === "finished";

  return (
    <section className="wrap border-t border-hairline py-14">
      <div className="kicker mb-[18px]">
        {finished ? (
          "Full time"
        ) : (
          <>
            <span className="mr-2 inline-block h-[7px] w-[7px] animate-pulse rounded-pill bg-red align-middle motion-reduce:animate-none" />
            Live · {fixture.minute !== null && fixture.minute !== undefined ? `${fixture.minute}'` : "in play"}
          </>
        )}
      </div>
      <h2 className="statement">
        {homeName} <b className="font-mono font-medium">{score}</b> {awayName}
      </h2>
      {(fixture.home_reds > 0 || fixture.away_reds > 0) && (
        <p className="mt-3 font-mono text-[13px] text-red">
          reds: {homeName} {fixture.home_reds} · {awayName} {fixture.away_reds}
        </p>
      )}
      {fixture.forecast && !finished && (
        <div className="mt-8">
          <WdlStrip
            win={fixture.forecast.p_home}
            draw={fixture.forecast.p_draw ?? null}
            lose={fixture.forecast.p_away}
            winLabel={homeName}
            loseLabel={awayName}
          />
          <p className="mt-4 font-mono text-[13px] text-cream-faint">
            in-match model · re-priced every poll
            {fixture.forecast.modal_score ? ` · most likely ${fixture.forecast.modal_score}` : ""}
          </p>
        </div>
      )}
    </section>
  );
}
