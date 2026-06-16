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

function TeamCode({ code, colour, live }: { code: string; colour: string; live: boolean }) {
  return (
    <span className={`font-display text-[13.5px] font-semibold ${live ? "shimmer-red" : ""}`} style={live ? undefined : { color: colour }}>
      {code}
    </span>
  );
}

export function FixtureRow({ row, impact }: FixtureRowProps) {
  const [open, setOpen] = useState(false);
  const expandable = row.shape !== null || row.status === "live" || row.pairings !== null;
  const live = row.status === "live";
  const completed = row.status === "completed";
  const lead = row.pairings?.[0] ?? null;
  const score = row.homeGoals !== null && row.awayGoals !== null ? `${row.homeGoals}-${row.awayGoals}` : null;

  return (
    <li className={`border-b border-hairline/60 last:border-b-0 ${completed ? "opacity-70" : ""}`}>
      <button
        type="button"
        onClick={() => expandable && setOpen((v) => !v)}
        aria-expanded={expandable ? open : undefined}
        disabled={!expandable}
        className="grid w-full grid-cols-[3rem_2.6rem_minmax(0,1fr)_5.5rem] items-center gap-3 py-2.5 text-left"
      >
        <TeamCode code={row.homeCode} colour={row.colours.home} live={live} />
        <span className={`text-center font-mono text-[12px] tabular-nums ${live ? "shimmer-red font-semibold" : "text-cream-dim"}`}>
          {live && row.minute !== null ? `${row.minute}'` : (score ?? formatKickoffTimeEastern(row.kickoff))}
        </span>
        <span className="flex items-center gap-3">
          <TeamCode code={row.awayCode} colour={row.colours.away} live={live} />
          <span className="min-w-0 flex-1">
            <WdlBar bar={row.bar} colours={row.colours} showDraw={!row.knockout} />
          </span>
        </span>
        {lead ? (
          <span className="flex items-center justify-end gap-1.5 font-mono text-[11px] tabular-nums text-cream-faint">
            <span className="truncate">
              {lead.homeCode} v {lead.awayCode}
            </span>
            <span className="text-cream">{formatPctBare(lead.pPairing)}%</span>
          </span>
        ) : (
          <span className="flex items-center justify-end gap-1 font-mono text-[11px] tabular-nums text-cream-faint">
            <span style={{ color: row.colours.home }}>{formatPctBare(row.bar.home)}</span>
            {!row.knockout && <span>/{formatPctBare(row.bar.draw)}</span>}
            <span style={{ color: row.colours.away }}>/{formatPctBare(row.bar.away)}</span>
          </span>
        )}
      </button>

      {expandable && (
        <div className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none" style={{ gridTemplateRows: open ? "1fr" : "0fr" }}>
          <div className="overflow-hidden" inert={!open}>
            {open && (
              <div className="pb-5 pl-[5.6rem] pr-1 pt-1">
                {row.pairings ? (
                  <Pairings row={row} />
                ) : live ? (
                  <ReachStrip row={row} impact={impact} />
                ) : row.shape ? (
                  <>
                    <Legend row={row} />
                    <WdlCurves shape={row.shape} colours={row.colours} />
                  </>
                ) : null}
              </div>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

function Legend({ row }: { row: Row }) {
  return (
    <div className="mb-1 flex items-center gap-3 font-mono text-[10.5px] tabular-nums text-cream-faint">
      <span style={{ color: row.colours.home }}>{row.homeCode} win</span>
      <span style={{ color: row.colours.away }}>{row.awayCode} win</span>
      <span style={{ color: row.colours.draw }}>draw</span>
    </div>
  );
}

function Pairings({ row }: { row: Row }) {
  return (
    <div>
      <div className="mb-2 grid grid-cols-[5.4rem_3rem_auto] items-baseline gap-2 font-mono text-[10.5px] text-cream-faint">
        <span>likely pairing</span>
        <span>chance</span>
        <span>win split</span>
      </div>
      <ul className="space-y-1.5">
        {(row.pairings ?? []).map((p) => (
          <li key={`${p.homeId}|${p.awayId}`} className="grid grid-cols-[5.4rem_3rem_auto] items-baseline gap-2 font-display text-[12.5px]">
            <span className="flex gap-1.5">
              <span className="font-semibold" style={{ color: p.colours.home }}>{p.homeCode}</span>
              <span className="font-semibold" style={{ color: p.colours.away }}>{p.awayCode}</span>
            </span>
            <span className="font-mono text-[12px] tabular-nums text-cream">{formatPctBare(p.pPairing)}%</span>
            <span className="font-mono text-[11px] tabular-nums text-cream-faint">
              {formatPctBare(p.pHome)} / {formatPctBare(p.pAway)}
            </span>
          </li>
        ))}
      </ul>
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
