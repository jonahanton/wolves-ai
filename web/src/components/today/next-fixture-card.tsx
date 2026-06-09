import { formatKickoff } from "@/lib/format";
import type { GroupMatch } from "@/lib/schedule";

interface NextFixtureCardProps {
  fixture: GroupMatch;
  names: Map<string, string>;
}

export function NextFixtureCard({ fixture, names }: NextFixtureCardProps) {
  const home = names.get(fixture.home) ?? fixture.home;
  const away = names.get(fixture.away) ?? fixture.away;
  return (
    <section className="sticker foil sticker-tilt-l p-4" aria-label="England's next fixture">
      <p className="text-[11px] font-semibold tracking-widest text-gold uppercase">Next for England</p>
      <p className="mt-1.5 text-lg font-semibold tracking-tight">
        {home} <span className="text-muted-foreground">v</span> {away}
      </p>
      <p className="mt-0.5 text-sm text-muted-foreground">
        Group {fixture.group} &middot; {formatKickoff(fixture.date)} &middot; {fixture.city}
      </p>
    </section>
  );
}
