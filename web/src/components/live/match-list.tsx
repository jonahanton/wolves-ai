import { MatchForecast } from "@/components/live/match-forecast";
import { WolfMascot } from "@/components/mascot/wolf-mascot";
import { formatKickoff, formatMatchDate } from "@/lib/format";
import type { LiveFixtureView } from "@/lib/live-view";
import { cn } from "@/lib/utils";

function TeamName({ id, name, onSelect }: { id: string | null; name: string; onSelect: (id: string) => void }) {
  if (!id) return <span className="font-medium">{name}</span>;
  return (
    <button
      type="button"
      onClick={() => onSelect(id)}
      className={cn("font-medium underline-offset-2 hover:underline", id === "england" && "text-gold")}
    >
      {name}
    </button>
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
        <div className="sticker flex items-center gap-3 p-4">
          <WolfMascot mood="happy" variant="juggle" size={48} />
          <div>
            <p className="font-medium">Nothing kicking off yet.</p>
            <p className="text-sm text-muted-foreground">
              The group stage starts {day ? formatMatchDate(`${day}T12:00:00Z`) : "on 11 Jun"}.
            </p>
          </div>
        </div>
      )}
      {fixtures.length > 0 && (
        <div className="mt-4">
          <h2 className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            {preTournament ? "Opening matchday" : "Today's matches"}
          </h2>
          <div className="divide-y rounded-xl border bg-card">
            {fixtures.map((fixture) => (
              <div key={fixture.match} className="px-3.5 py-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="min-w-0 truncate">
                    <TeamName id={fixture.homeId} name={fixture.homeName} onSelect={onSelectTeam} />{" "}
                    <span className="text-muted-foreground">v</span>{" "}
                    <TeamName id={fixture.awayId} name={fixture.awayName} onSelect={onSelectTeam} />
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatKickoff(fixture.date)} &middot; {fixture.city}
                  </span>
                </div>
                <MatchForecast fixture={fixture} />
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
