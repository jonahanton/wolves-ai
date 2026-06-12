import Link from "next/link";
import { WdlStrip } from "@/components/charts/wdl-strip";
import { Kicker } from "@/components/shell/kicker";
import { type LiveFixture, type LiveState, topTitleMovers } from "@/lib/live";

interface LiveHeroProps {
  state: LiveState;
  fixture: LiveFixture;
  focusId: string;
  names: Record<string, string>;
}

export function LiveHero({ state, fixture, focusId, names }: LiveHeroProps) {
  const focusIsHome = fixture.home_id === focusId;
  const focusInvolved = focusIsHome || fixture.away_id === focusId;
  const forecast = fixture.forecast;
  const movers = topTitleMovers(state, 3);

  return (
    <section className="wrap pt-20 pb-14">
      <Kicker>
        <span className="mr-2 inline-block h-[7px] w-[7px] animate-pulse rounded-pill bg-red align-middle" /> Live ·{" "}
        {fixture.minute !== null && fixture.minute !== undefined ? `${fixture.minute}'` : "in play"} · {fixture.city ?? ""}
      </Kicker>
      <h1 className="statement statement-hero">
        <b className={`font-medium ${focusInvolved ? "text-red" : ""}`}>{fixture.home_name}</b>{" "}
        <span className="font-mono">
          {fixture.home_goals ?? 0}–{fixture.away_goals ?? 0}
        </span>{" "}
        <b className="font-medium">{fixture.away_name}</b>
      </h1>
      {forecast && (
        <div className="mt-8 max-w-[880px]">
          <WdlStrip
            win={focusIsHome || !focusInvolved ? forecast.p_home : forecast.p_away}
            draw={forecast.p_draw ?? null}
            lose={focusIsHome || !focusInvolved ? forecast.p_away : forecast.p_home}
            winLabel={focusIsHome || !focusInvolved ? fixture.home_name : fixture.away_name}
            loseLabel={focusIsHome || !focusInvolved ? fixture.away_name : fixture.home_name}
          />
        </div>
      )}
      {movers.length > 0 && (
        <div className="mt-8 flex flex-wrap gap-x-10 gap-y-4">
          {movers.map(([teamId, delta]) => (
            <div key={teamId}>
              <span className={`block font-mono text-[clamp(24px,4vw,38px)] ${delta > 0 ? "text-green" : "text-red"}`}>
                {delta > 0 ? "+" : "−"}
                {Math.abs(delta).toFixed(1)}
              </span>
              <span className="block font-mono text-[12px] uppercase tracking-[0.14em] text-cream-faint">
                {names[teamId] ?? teamId} title, pp
              </span>
            </div>
          ))}
        </div>
      )}
      <div className="mt-10 font-mono text-[13px] text-cream-dim">
        <Link href="/live" className="border-b border-hairline pb-0.5">
          all of today&apos;s games
        </Link>
      </div>
    </section>
  );
}
