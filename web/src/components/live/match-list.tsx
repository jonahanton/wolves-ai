import { MatchForecast } from "@/components/live/match-forecast";
import { WolfMascot } from "@/components/mascot/wolf-mascot";
import { formatKickoffTime, formatMatchDate, formatPctBare } from "@/lib/format";
import type { LiveFixtureView } from "@/lib/live-view";
import { ENGLAND, groupStageStart } from "@/lib/schedule";
import { cn } from "@/lib/utils";

function TeamName({ id, name, onSelect }: { id: string | null; name: string; onSelect: (id: string) => void }) {
  if (!id) return <span className="truncate font-medium">{name}</span>;
  return (
    <button
      type="button"
      onClick={() => onSelect(id)}
      className={cn("truncate text-left font-medium underline-offset-2 hover:underline", id === ENGLAND && "text-gold")}
    >
      {name}
    </button>
  );
}

/* FotMob row contract: 56px tall, three rigid columns (status, stacked teams,
   fixed-width probability); state may change colour but never the geometry. */
function MatchRow({ fixture, onSelectTeam }: { fixture: LiveFixtureView; onSelectTeam: (id: string) => void }) {
  const forecast = fixture.forecast;
  return (
    <div className="grid h-14 grid-cols-[48px_minmax(0,1fr)_52px] items-center px-3">
      <div className="text-[11px] text-muted-foreground">{formatKickoffTime(fixture.date)}</div>
      <div className="flex min-w-0 flex-col gap-0.5 text-sm leading-tight">
        <TeamName id={fixture.homeId} name={fixture.homeName} onSelect={onSelectTeam} />
        <TeamName id={fixture.awayId} name={fixture.awayName} onSelect={onSelectTeam} />
      </div>
      <div className="flex flex-col gap-0.5 text-right text-sm leading-tight text-muted-foreground">
        <span>{forecast ? `${formatPctBare(forecast.pHome)}%` : ""}</span>
        <span>{forecast ? `${formatPctBare(forecast.pAway)}%` : ""}</span>
      </div>
    </div>
  );
}

interface MatchListProps {
  preTournament: boolean;
  day: string | null;
  fixtures: LiveFixtureView[];
  onSelectTeam: (teamId: string) => void;
}

export function MatchList({ preTournament, day, fixtures, onSelectTeam }: MatchListProps) {
  return (
    <section aria-label="Matches">
      {preTournament && (
        <div className="sticker flex items-center gap-3 p-3">
          <WolfMascot mood="happy" variant="juggle" size={48} />
          <div>
            <p className="font-medium">Nothing kicking off yet.</p>
            <p className="text-sm text-muted-foreground">
              The group stage starts {formatMatchDate(day ? `${day}T12:00:00Z` : groupStageStart)}.
            </p>
          </div>
        </div>
      )}
      {fixtures.length > 0 && (
        <div className="mt-6">
          <h2 className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            {preTournament ? "Opening matchday" : "Today's matches"}
          </h2>
          <div className="divide-y rounded-xl border bg-card">
            {fixtures.map((fixture) => (
              <div key={fixture.match}>
                <MatchRow fixture={fixture} onSelectTeam={onSelectTeam} />
                <MatchForecast fixture={fixture} />
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
