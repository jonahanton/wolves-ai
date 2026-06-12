import { LiveBoard } from "@/components/live/live-board";
import { ErrorState } from "@/components/shell/error-state";
import { Kicker } from "@/components/shell/kicker";
import { matchesOn, nextFixtureFor } from "@/lib/derive";
import { formatKickoff, formatMatchDate } from "@/lib/format";
import { loadLiveState } from "@/lib/live";
import { loadLatestSnapshot } from "@/lib/load-snapshot";

const COUNT_WORDS: Record<number, string> = { 1: "One game on.", 2: "Two games on.", 3: "Three games on.", 4: "Four games on." };

export default async function LivePage() {
  const [liveResult, snapshotResult] = await Promise.all([loadLiveState(), loadLatestSnapshot()]);

  if (!liveResult.ok) {
    if (!snapshotResult.ok) return <ErrorState error={liveResult.error} context="Live" />;
    const snapshot = snapshotResult.data;
    const next = nextFixtureFor(snapshot, snapshot.focus.team_id, new Date());
    const day = next ? next.date.slice(0, 10) : null;
    const names = new Map(snapshot.teams.map((t) => [t.team_id, t.name]));
    return (
      <section className="wrap py-20">
        <Kicker>Live</Kicker>
        <h1 className="statement">
          Nothing on right now.
          <br />
          <b className="font-medium">The engine waits.</b>
        </h1>
        {day && (
          <div className="mt-10 max-w-[880px]">
            <div className="mb-3 font-mono text-[12px] uppercase tracking-[0.14em] text-cream-faint">
              Next: {formatMatchDate(`${day}T12:00:00Z`)}
            </div>
            {matchesOn(snapshot, day).map((match) => (
              <div key={match.match} className="flex justify-between border-b border-hairline py-3.5">
                <span className="text-[17px]">
                  {names.get(match.home_id) ?? match.home_id} v {names.get(match.away_id) ?? match.away_id}
                </span>
                <span className="font-mono text-[13px] text-cream-faint">{formatKickoff(match.date)}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    );
  }

  const live = liveResult.data;
  const names = snapshotResult.ok
    ? Object.fromEntries(snapshotResult.data.teams.map((t) => [t.team_id, t.name]))
    : {};
  const focusId = snapshotResult.ok ? snapshotResult.data.focus.team_id : "england";
  const anyLive = live.live_match_count > 0;

  return (
    <section className="wrap py-20">
      <Kicker>
        {anyLive && (
          <span className="mr-2 inline-block h-[7px] w-[7px] animate-pulse rounded-pill bg-red align-middle" />
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
      <div className="mt-10">
        <LiveBoard initial={live} focusId={focusId} names={names} />
      </div>
    </section>
  );
}
