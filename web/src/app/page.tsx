import { ErrorState } from "@/components/shell/error-state";
import { Kicker } from "@/components/shell/kicker";
import { deriveHero, titleBoard } from "@/lib/derive";
import { formatPct1, formatUpdated } from "@/lib/format";
import { loadLatestSnapshot } from "@/lib/load-snapshot";

export default async function LandingPage() {
  const result = await loadLatestSnapshot();
  if (!result.ok) return <ErrorState error={result.error} context="World Cup Superforecaster" />;
  const snapshot = result.data;

  const hero = deriveHero(snapshot);
  const board = titleBoard(snapshot, 6);
  const focusId = snapshot.focus.team_id;

  return (
    <>
      <section className="wrap pt-24 pb-16">
        <Kicker>World Cup Superforecaster · run {formatUpdated(snapshot.run.created_at)}</Kicker>
        <h1 className="statement statement-hero">
          {hero.lead}
          <br />
          <b className="font-medium text-red">{hero.focusLine}</b>
        </h1>
        <p className="lede mt-[18px]">
          Fifty thousand simulated tournaments a day, an AI superforecaster reading the news, the market keeping us
          honest.
        </p>
      </section>

      <section className="wrap border-t border-hairline py-16">
        <Kicker>The field</Kicker>
        <div className="max-w-[880px] border-t border-hairline">
          {board.map((row, index) => (
            <div
              key={row.teamId}
              className="grid grid-cols-[34px_1fr_auto_auto] items-baseline gap-x-5 border-b border-hairline py-4"
            >
              <span className="font-mono text-[13px] text-cream-faint">{String(index + 1).padStart(2, "0")}</span>
              <span className={`text-[clamp(19px,2.8vw,24px)] ${row.teamId === focusId ? "font-medium text-red" : ""}`}>
                {row.name}
              </span>
              <span className="font-mono text-[13px] text-cream-faint">
                {row.model !== null && row.market !== null
                  ? `${(row.model * 100).toFixed(1)} / ${(row.market * 100).toFixed(1)}`
                  : ""}
              </span>
              <span className="font-mono text-[clamp(19px,2.8vw,24px)]">{formatPct1(row.prob)}</span>
            </div>
          ))}
        </div>
        <div className="mt-4 flex max-w-[880px] justify-between font-mono text-[12.5px] text-cream-faint">
          <span>model / market</span>
          <span>blend</span>
        </div>
      </section>
    </>
  );
}
