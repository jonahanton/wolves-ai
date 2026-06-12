import { LiveExperience } from "@/components/live/live-experience";
import { ErrorState } from "@/components/shell/error-state";
import { Kicker } from "@/components/shell/kicker";
import { orNull } from "@/lib/api";
import { matchesOn, nextFixtureFor } from "@/lib/derive";
import { formatKickoff, formatMatchDate } from "@/lib/format";
import { loadImpact } from "@/lib/impact";
import { loadLiveState } from "@/lib/live";
import { loadLatestSnapshot } from "@/lib/load-snapshot";

export default async function LivePage() {
  const [liveResult, snapshotResult, impactResult] = await Promise.all([
    loadLiveState(),
    loadLatestSnapshot(),
    loadImpact(),
  ]);

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
          <div className="mt-10 max-w-[760px]">
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

  const names = snapshotResult.ok
    ? Object.fromEntries(snapshotResult.data.teams.map((t) => [t.team_id, t.name]))
    : {};
  const focusId = snapshotResult.ok ? snapshotResult.data.focus.team_id : "england";

  return (
    <LiveExperience initialLive={liveResult.data} initialImpact={orNull(impactResult)} names={names} focusId={focusId} />
  );
}
