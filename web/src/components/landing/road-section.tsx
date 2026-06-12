import { Kicker } from "@/components/shell/kicker";
import { WdlStrip } from "@/components/charts/wdl-strip";
import { nextFixtureFor, shortCity } from "@/lib/derive";
import { formatKickoff, formatMatchDate, formatPct1 } from "@/lib/format";
import type { Snapshot } from "@/lib/snapshot";

const ROUND_LABELS: Record<string, string> = {
  r32: "R32",
  r16: "R16",
  qf: "QF",
  sf: "SF",
  final: "Final",
};

interface RoadSectionProps {
  snapshot: Snapshot;
  now: Date;
}

export function RoadSection({ snapshot, now }: RoadSectionProps) {
  const { focus } = snapshot;
  const names = new Map(snapshot.teams.map((t) => [t.team_id, t.name]));
  const focusName = names.get(focus.team_id) ?? focus.team_id;
  const path = focus.modal_path ?? [];
  const finalStep = path[path.length - 1];
  const next = nextFixtureFor(snapshot, focus.team_id, now);
  const nextIsHome = next?.home_id === focus.team_id;
  const opponent = next ? (names.get((nextIsHome ? next.away_id : next.home_id) ?? "") ?? "tbc") : null;

  return (
    <section className="wrap relative border-t border-hairline py-[clamp(60px,10vh,120px)]">
      <Kicker>{focusName}&apos;s road</Kicker>
      <h2 className="statement">
        {path.length} wins from
        <br />
        <b className="font-medium">{finalStep ? shortCity(finalStep.city) : "the final"}.</b>
      </h2>
      <p className="mt-[clamp(28px,5vh,44px)] font-mono text-[12px] text-cream-faint">
        the modal path · %&nbsp;= chance of surviving each round
      </p>
      <div className="mt-2 max-w-[880px]">
        {path.map((step) => (
          <div
            key={step.round}
            className="grid grid-cols-[90px_1fr_auto] items-baseline gap-x-[clamp(14px,3vw,28px)] border-b border-hairline py-[17px]"
          >
            <span className="font-mono text-[12px] uppercase tracking-[0.12em] text-cream-faint">
              {ROUND_LABELS[step.round] ?? step.round} · {formatMatchDate(step.date)}
            </span>
            <span className="text-[clamp(24px,4vw,38px)] font-light tracking-[-0.01em]">
              {shortCity(step.city)}
              <span className="ml-3.5 text-[clamp(13px,1.7vw,16px)] font-light text-cream-faint">
                likely {names.get(step.opponent_id) ?? step.opponent_id}
              </span>
            </span>
            <span className="font-mono text-[clamp(17px,2.4vw,21px)]">
              {formatPct1(focus.reach_probs[nextRound(step.round)] ?? focus.reach_probs[step.round] ?? 0)}
            </span>
          </div>
        ))}
      </div>
      {next && (
        <>
          <div className="mt-[26px] flex max-w-[880px] flex-wrap items-baseline justify-between gap-3.5 text-[16px] text-cream-dim">
            <span>
              Next: <b className="font-medium text-cream">{focusName} v {opponent}</b> · {next.city} ·{" "}
              {formatKickoff(next.date)}
            </span>
            {next.modal_score && <span className="font-mono">most likely {next.modal_score}</span>}
          </div>
          <div className="mt-3.5">
            <WdlStrip
              win={nextIsHome ? next.p_home : next.p_away}
              draw={next.p_draw ?? null}
              lose={nextIsHome ? next.p_away : next.p_home}
            />
          </div>
        </>
      )}
    </section>
  );
}

// A step's survival chance is the next round's reach probability.
function nextRound(round: string): string {
  const order = ["r32", "r16", "qf", "sf", "final"];
  const index = order.indexOf(round);
  return index >= 0 && index < order.length - 1 ? order[index + 1] : "champion";
}
