import Link from "next/link";
import { ErrorState } from "@/components/shell/error-state";
import { Kicker } from "@/components/shell/kicker";
import { River } from "@/components/charts/river";
import { formatPct } from "@/lib/format";
import { loadLatestSnapshot } from "@/lib/load-snapshot";
import { riverGeometry } from "@/lib/river";
import type { Slot } from "@/lib/snapshot";

const STAGE_LABELS: Record<string, string> = {
  r32: "Last 32",
  r16: "Last 16",
  qf: "Quarter-finals",
  sf: "Semi-finals",
  third_place: "Third place",
  final: "The final",
};

const STAGE_SEQUENCE = ["r32", "r16", "qf", "sf", "final"];

export default async function BracketPage() {
  const result = await loadLatestSnapshot();
  if (!result.ok) return <ErrorState error={result.error} context="Bracket" />;
  const snapshot = result.data;
  const names = new Map(snapshot.teams.map((t) => [t.team_id, t.name]));
  const focusId = snapshot.focus.team_id;

  const desktop = riverGeometry(snapshot, { teamCount: 10, height: 600 });
  const mobile = riverGeometry(snapshot, { teamCount: 6, height: 520, width: 720, compact: true });

  const rounds = STAGE_SEQUENCE.map((stage) => ({
    stage,
    label: STAGE_LABELS[stage],
    slots: snapshot.slots.filter((slot) => slot.stage === stage).sort((a, b) => a.match - b.match),
  })).filter((round) => round.slots.length > 0);

  return (
    <>
      <section className="wrap pt-20 pb-10">
        <Kicker>The bracket · run {snapshot.run.run_id}</Kicker>
        <h1 className="statement statement-hero">
          {snapshot.run.n_sims.toLocaleString("en-GB")} futures,
          <br />
          <b className="font-medium">one river.</b>
        </h1>
        <p className="lede mt-[18px]">
          Every band is probability mass flowing through the draw: who survives each round, and how much of the
          tournament still belongs to the field. Deterministic engine, never the agent.
        </p>
      </section>

      <section className="wrap pb-14">
        <div className="hidden md:block">
          <River geometry={desktop} id="river-d" />
        </div>
        <div className="md:hidden">
          <River geometry={mobile} id="river-m" />
        </div>
      </section>

      <section className="wrap border-t border-hairline py-14">
        <Kicker>Round by round · most likely occupants</Kicker>
        <div className="-mx-[clamp(20px,4vw,44px)] flex snap-x snap-mandatory gap-5 overflow-x-auto px-[clamp(20px,4vw,44px)] pb-4 lg:mx-0 lg:grid lg:grid-cols-5 lg:gap-6 lg:overflow-visible lg:px-0">
          {rounds.map((round) => (
            <div key={round.stage} className="w-[290px] flex-none snap-start lg:w-auto">
              <div className="mb-3 font-mono text-[12px] uppercase tracking-[0.14em] text-cream-dim">
                {round.label}
              </div>
              <div className="space-y-3">
                {round.slots.map((slot) => (
                  <SlotCard key={slot.match} slot={slot} names={names} focusId={focusId} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

interface SlotCardProps {
  slot: Slot;
  names: Map<string, string>;
  focusId: string;
}

function SlotCard({ slot, names, focusId }: SlotCardProps) {
  return (
    <Link href={`/match/${slot.match}`} className="block border border-hairline p-4">
      <div className="mb-2.5 flex justify-between font-mono text-[11px] uppercase tracking-[0.1em] text-cream-faint">
        <span>match {slot.match}</span>
        <span>{slot.city.split("/")[0]}</span>
      </div>
      <SlotSide candidates={slot.home.candidates} names={names} focusId={focusId} />
      <div className="my-2 font-mono text-[11px] text-cream-faint">v</div>
      <SlotSide candidates={slot.away.candidates} names={names} focusId={focusId} />
    </Link>
  );
}

interface SlotSideProps {
  candidates: { team_id: string; prob: number }[];
  names: Map<string, string>;
  focusId: string;
}

function SlotSide({ candidates, names, focusId }: SlotSideProps) {
  const top = [...candidates].sort((a, b) => b.prob - a.prob).slice(0, 2);
  return (
    <div className="space-y-1">
      {top.map((candidate) => (
        <div key={candidate.team_id} className="flex items-baseline justify-between gap-3">
          <span className={`text-[15px] ${candidate.team_id === focusId ? "font-medium text-red" : ""}`}>
            {names.get(candidate.team_id) ?? candidate.team_id}
          </span>
          <span className="font-mono text-[12.5px] text-cream-faint">{formatPct(candidate.prob)}</span>
        </div>
      ))}
    </div>
  );
}
