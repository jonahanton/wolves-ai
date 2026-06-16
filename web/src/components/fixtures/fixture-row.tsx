"use client";

import { useState } from "react";
import { WdlBar } from "@/components/fixtures/wdl-bar";
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
  const tbc = row.slot !== null;
  const live = row.status === "live";
  const completed = row.status === "completed";
  // A finished match is just its result: no forecast bar, no expand.
  const expandable = !completed && (row.shape !== null || live || tbc);
  const score = row.homeGoals !== null && row.awayGoals !== null ? `${row.homeGoals}-${row.awayGoals}` : null;

  return (
    <li className={`border-b border-hairline/50 last:border-b-0 ${completed ? "opacity-70" : ""}`}>
      <button
        type="button"
        onClick={() => expandable && setOpen((v) => !v)}
        aria-expanded={expandable ? open : undefined}
        disabled={!expandable}
        className="grid w-full grid-cols-[2.9rem_2.6rem_minmax(0,1fr)_5.2rem] items-center gap-3 py-2.5 text-left"
      >
        <TeamCode code={tbc ? (row.slot?.home.label ?? "TBC") : row.homeCode} colour={row.colours.home} live={live} tbc={tbc} />
        <span className={`text-center font-mono text-[12px] tabular-nums ${live ? "shimmer-red font-semibold" : completed ? "text-cream" : "text-cream-dim"}`}>
          {live && row.minute !== null ? `${row.minute}'` : (score ?? formatKickoffTimeEastern(row.kickoff))}
        </span>
        <span className="flex items-center gap-3">
          <TeamCode code={tbc ? (row.slot?.away.label ?? "TBC") : row.awayCode} colour={row.colours.away} live={live} tbc={tbc} />
          <span className="min-w-0 flex-1">
            {!completed && row.bar && <WdlBar bar={row.bar} colours={row.colours} showDraw={!row.knockout} />}
          </span>
        </span>
        <span className="flex items-center justify-end gap-1 font-mono text-[11px] tabular-nums text-cream-faint">
          {completed ? null : tbc ? (
            <span className="font-display text-[12px] font-semibold uppercase tracking-[0.06em] text-cream-dim">TBC</span>
          ) : row.bar ? (
            <>
              <span style={{ color: row.colours.home }}>{formatPctBare(row.bar.home)}</span>
              {!row.knockout && <span>/{formatPctBare(row.bar.draw)}</span>}
              <span style={{ color: row.colours.away }}>/{formatPctBare(row.bar.away)}</span>
            </>
          ) : null}
        </span>
      </button>

      {expandable && (
        <div className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none" style={{ gridTemplateRows: open ? "1fr" : "0fr" }}>
          <div className="overflow-hidden" inert={!open}>
            {open && (
              <div className="pb-5 pl-[5.5rem] pr-1 pt-1">
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
    <div className="flex items-baseline gap-x-3.5">
      <span className="w-8 shrink-0 font-mono text-[12px] text-cream-faint">{label}</span>
      <span className="flex flex-wrap items-baseline gap-x-3.5 gap-y-1">
        {candidates.map((c) => (
          <span key={c.teamId} className="font-display text-[13.5px]">
            <span className="font-semibold text-cream">{c.code}</span>
            <span className="ml-1.5 font-mono text-[12px] tabular-nums text-cream-faint">{formatPctBare(c.prob)}%</span>
          </span>
        ))}
      </span>
    </div>
  );
}

function SlotDetail({ row }: { row: Row }) {
  const slot = row.slot;
  if (!slot) return null;
  return (
    <div className="space-y-2">
      <p className="font-mono text-[11px] text-cream-faint">most likely to fill each side</p>
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
