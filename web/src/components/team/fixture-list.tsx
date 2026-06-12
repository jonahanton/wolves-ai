import Link from "next/link";
import { WdlStrip } from "@/components/charts/wdl-strip";
import { formatKickoff } from "@/lib/format";
import type { MatchProbs } from "@/lib/snapshot";

interface FixtureListProps {
  fixtures: MatchProbs[];
  teamId: string;
  names: Map<string, string>;
}

export function FixtureList({ fixtures, teamId, names }: FixtureListProps) {
  return (
    <div className="max-w-[880px]">
      {fixtures.map((fixture) => {
        const isHome = fixture.home_id === teamId;
        const opponentId = isHome ? fixture.away_id : fixture.home_id;
        return (
          <Link key={fixture.match} href={`/match/${fixture.match}`} className="block border-b border-hairline py-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="text-[clamp(17px,2.4vw,21px)]">
                v {names.get(opponentId) ?? "winner of the group phase"}
                <span className="ml-3 text-[14px] text-cream-faint">{fixture.city}</span>
              </span>
              <span className="font-mono text-[12.5px] text-cream-faint">
                {formatKickoff(fixture.date)}
                {fixture.modal_score ? ` · likely ${fixture.modal_score}` : ""}
              </span>
            </div>
            <div className="mt-2.5">
              <WdlStrip
                win={isHome ? fixture.p_home : fixture.p_away}
                draw={fixture.p_draw ?? null}
                lose={isHome ? fixture.p_away : fixture.p_home}
              />
            </div>
          </Link>
        );
      })}
      {fixtures.length === 0 && <p className="lede">No remaining fixtures in the published bracket.</p>}
    </div>
  );
}
