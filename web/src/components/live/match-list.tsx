import { WolfMascot } from "@/components/mascot/wolf-mascot";
import { formatKickoff, formatMatchDate } from "@/lib/format";
import type { GroupMatch } from "@/lib/schedule";

interface MatchListProps {
  preTournament: boolean;
  matchday: { day: string; matches: GroupMatch[] } | null;
  names: Map<string, string>;
}

export function MatchList({ preTournament, matchday, names }: MatchListProps) {
  const name = (id: string) => names.get(id) ?? id;

  return (
    <section aria-label="Matches">
      {preTournament && (
        <div className="sticker sticker-tilt-r flex items-center gap-3 p-4">
          <WolfMascot mood="happy" size={48} />
          <div>
            <p className="font-medium">Nothing kicking off yet.</p>
            <p className="text-sm text-muted-foreground">
              The group stage starts {matchday ? formatMatchDate(`${matchday.day}T12:00:00Z`) : "on 11 Jun"}.
            </p>
          </div>
        </div>
      )}
      {matchday && (
        <div className="mt-4">
          <h2 className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            {preTournament ? "Opening matchday" : "Today's matches"}
          </h2>
          <div className="divide-y rounded-xl border bg-card">
            {matchday.matches.map((match) => (
              <div key={match.match} className="flex items-center justify-between gap-3 px-3.5 py-2.5 text-sm">
                <span className="truncate font-medium">
                  {name(match.home)} <span className="font-normal text-muted-foreground">v</span>{" "}
                  {name(match.away)}
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatKickoff(match.date)} &middot; {match.city}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
