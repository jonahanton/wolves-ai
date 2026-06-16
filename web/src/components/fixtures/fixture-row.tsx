"use client";

import { useState } from "react";
import { WdlCurves } from "@/components/fixtures/wdl-curves";
import type { FixtureRow as Row } from "@/lib/fixtures";
import { teamReachShifts } from "@/lib/fixtures-reach";
import { formatKickoffTimeEastern, formatPctBare } from "@/lib/format";
import type { Impact } from "@/lib/impact";

interface FixtureRowProps {
  row: Row;
  impact: Impact | null;
}

function signed(pp: number): string {
  return `${pp > 0 ? "+" : ""}${pp.toFixed(1)}`;
}

function Outcome({ label, pct }: { label: string; pct: number }) {
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="font-display text-[11px] text-cream-faint">{label}</span>
      <span className="font-semibold tabular-nums text-cream">{formatPctBare(pct)}%</span>
    </span>
  );
}

function TeamCode({ code, colour, live, tbc }: { code: string; colour: string; live?: boolean; tbc?: boolean }) {
  return (
    <span
      className={`font-display text-[13.5px] font-semibold ${live ? "shimmer-red" : ""}`}
      style={live ? undefined : { color: tbc ? "var(--color-cream-faint)" : colour }}
    >
      {code}
    </span>
  );
}

export function FixtureRow({ row, impact }: FixtureRowProps) {
  const [open, setOpen] = useState(false);
  const [everOpened, setEverOpened] = useState(false);
  if (open && !everOpened) setEverOpened(true);
  const tbc = row.slot !== null;
  const live = row.status === "live";
  const completed = row.status === "completed";
  // A finished match is just its result: no forecast bar, no expand.
  const expandable = !completed && (row.shape !== null || live || tbc);
  const score = row.homeGoals !== null && row.awayGoals !== null ? `${row.homeGoals}-${row.awayGoals}` : null;

  return (
    <li className={`border-b border-hairline/50 last:border-b-0 ${completed ? "opacity-70" : ""}`}>
      {tbc ? (
        <button
          type="button"
          onClick={() => expandable && setOpen((v) => !v)}
          aria-expanded={open}
          className="flex w-full items-center py-2.5 text-left"
        >
          <span className="flex items-baseline gap-4">
            <TeamCode code={row.slot?.home.label ?? "TBC"} colour={row.colours.home} tbc />
            <span className="font-mono text-[12px] tabular-nums text-cream-dim">{formatKickoffTimeEastern(row.kickoff)}</span>
            <TeamCode code={row.slot?.away.label ?? "TBC"} colour={row.colours.away} tbc />
          </span>
          <span className="ml-auto font-display text-[13px] font-semibold uppercase tracking-[0.06em] text-cream-dim">TBC</span>
        </button>
      ) : (
        <button
          type="button"
          onClick={() => expandable && setOpen((v) => !v)}
          aria-expanded={expandable ? open : undefined}
          disabled={!expandable}
          className="flex w-full items-center py-2.5 text-left"
        >
          <span className="flex items-baseline gap-3.5">
            <span className="w-9 text-right">
              <TeamCode code={row.homeCode} colour={row.colours.home} live={live} />
            </span>
            <span className={`w-12 text-center font-mono text-[12px] tabular-nums ${live ? "shimmer-red font-semibold" : completed ? "text-cream" : "text-cream-dim"}`}>
              {live ? (score ?? "-") : (score ?? formatKickoffTimeEastern(row.kickoff))}
            </span>
            <span className="w-9 text-left">
              <TeamCode code={row.awayCode} colour={row.colours.away} live={live} />
            </span>
          </span>
          <span className="ml-auto flex items-baseline gap-4 font-mono text-[12.5px] tabular-nums">
            {live ? (
              <span className="shimmer-red font-semibold">{row.minute !== null ? `${row.minute}'` : "live"}</span>
            ) : completed ? null : row.bar ? (
              <>
                <Outcome label={row.homeCode} pct={row.bar.home} />
                {!row.knockout && <Outcome label="Draw" pct={row.bar.draw} />}
                <Outcome label={row.awayCode} pct={row.bar.away} />
              </>
            ) : null}
          </span>
        </button>
      )}

      {expandable && (
        <div className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none" style={{ gridTemplateRows: open ? "1fr" : "0fr" }}>
          <div className="overflow-hidden" inert={!open}>
            {everOpened && (
              <div className="-mx-3 mt-1 rounded-md bg-night-2/60 px-3 pb-5 pt-3.5">
                {tbc && row.slot ? (
                  <SlotDetail row={row} />
                ) : live ? (
                  <ReachStrip row={row} impact={impact} />
                ) : row.shape ? (
                  <WdlCurves
                    shape={row.shape}
                    colours={row.colours}
                    homeCode={row.homeCode}
                    awayCode={row.awayCode}
                    showDraw={!row.knockout}
                  />
                ) : null}
              </div>
            )}
          </div>
        </div>
      )}
    </li>
  );
}


function CandidateList({ label, candidates }: { label: string; candidates: { teamId: string; code: string; prob: number; colour: string }[] }) {
  return (
    <div className="grid grid-cols-[2rem_repeat(3,5.5rem)] items-baseline gap-x-2">
      <span className="font-mono text-[12px] text-cream-faint">{label}</span>
      {candidates.map((c) => (
        <span key={c.teamId} className="font-display text-[13.5px]">
          <span className="font-semibold text-cream">{c.code}</span>
          <span className="ml-1.5 font-mono text-[12px] tabular-nums text-cream-faint">{formatPctBare(c.prob)}%</span>
        </span>
      ))}
    </div>
  );
}

function SlotDetail({ row }: { row: Row }) {
  const slot = row.slot;
  if (!slot) return null;
  return (
    <div className="space-y-2">
      <CandidateList label={slot.home.label} candidates={slot.home.candidates} />
      <CandidateList label={slot.away.label} candidates={slot.away.candidates} />
    </div>
  );
}

function ReachStrip({ row, impact }: { row: Row; impact: Impact | null }) {
  const sides = [
    { id: row.homeId, code: row.homeCode },
    { id: row.awayId, code: row.awayCode },
  ].filter((s): s is { id: string; code: string } => s.id !== null);
  const groups =
    impact?.liveMode === "in_match_distribution"
      ? sides.map((s) => ({ ...s, shifts: teamReachShifts(impact, s.id, s.code) })).filter((g) => g.shifts.length > 0)
      : [];
  const heading = row.minute !== null ? `Given the game state at ${row.minute}'` : "Given the game state";

  if (groups.length === 0) {
    return <p className="font-display text-[12px] text-cream-faint">Given the game state, no material shift in either team&apos;s run.</p>;
  }
  return (
    <div>
      <p className="mb-2 font-display text-[12px] text-cream-faint">{heading}</p>
      <div className="space-y-2">
        {groups.map((g) => (
          <div key={g.id}>
            {g.shifts.map((shift, i) => (
              <div key={shift.stageLabel} className="grid grid-cols-[2.6rem_4.5rem_auto_3.5rem] items-baseline gap-2 font-display text-[12px] leading-tight">
                <span className="font-semibold text-cream">{i === 0 ? g.code : ""}</span>
                <span className="text-cream-dim">{shift.stageLabel}</span>
                <span className="font-mono text-[11px] tabular-nums text-cream-faint">
                  {shift.fromPct.toFixed(0)}% &rarr; {shift.toPct.toFixed(0)}%
                </span>
                <span className="text-right font-mono text-[11px] font-semibold tabular-nums text-cream">{signed(shift.deltaPp)}pp</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
