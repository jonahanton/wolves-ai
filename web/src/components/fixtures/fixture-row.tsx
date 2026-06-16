"use client";

import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { WdlCurves } from "@/components/fixtures/wdl-curves";
import { ExitStageHistogram } from "@/components/teams/exit-stage-histogram";
import type { FixtureRow as Row } from "@/lib/fixtures";
import { formatKickoffTimeEastern, formatPctBare } from "@/lib/format";
import type { Impact } from "@/lib/impact";
import { chartColour } from "@/lib/team-colours";

interface FixtureRowProps {
  row: Row;
  impact: Impact | null;
  reachProbs: Record<string, Record<string, number>>;
}

function Outcome({ label, pct }: { label: string; pct: number }) {
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="font-display text-[11px] text-cream-faint">{label}</span>
      <span className="font-semibold tabular-nums text-cream">{formatPctBare(pct)}%</span>
    </span>
  );
}

function TeamCode({ code, teamId, live, tbc }: { code: string; teamId?: string | null; live?: boolean; tbc?: boolean }) {
  const colour = tbc || !teamId ? "var(--color-cream-faint)" : chartColour(teamId);
  return (
    <span className={`font-display text-[13.5px] font-semibold ${live ? "shimmer-red" : ""}`} style={live ? undefined : { color: colour }}>
      {code}
    </span>
  );
}

export function FixtureRow({ row, impact, reachProbs }: FixtureRowProps) {
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
          <span className="grid w-[8.5rem] shrink-0 grid-cols-[1fr_3rem_1fr] items-baseline gap-2">
            <span className="text-left">
              <TeamCode code={row.slot?.home.label ?? "TBC"} tbc />
            </span>
            <span className="text-center font-mono text-[12px] tabular-nums text-cream-dim">{formatKickoffTimeEastern(row.kickoff)}</span>
            <span className="text-right">
              <TeamCode code={row.slot?.away.label ?? "TBC"} tbc />
            </span>
          </span>
          <span className="ml-auto font-display text-[13px] font-semibold uppercase tracking-[0.06em] text-cream-dim">TBC</span>
        </button>
      ) : (
        <button
          type="button"
          onClick={() => expandable && setOpen((v) => !v)}
          aria-expanded={expandable ? open : undefined}
          disabled={!expandable}
          className="flex w-full items-center gap-3 py-2.5 text-left"
        >
          <span className="grid w-[8.5rem] shrink-0 grid-cols-[1fr_3rem_1fr] items-baseline gap-2">
            <span className="text-left">
              <TeamCode code={row.homeCode} teamId={row.homeId} live={live} />
            </span>
            <span className={`text-center font-mono text-[12px] tabular-nums ${live ? "shimmer-red font-semibold" : completed ? "text-cream" : "text-cream-dim"}`}>
              {live ? (score ?? "-") : (score ?? formatKickoffTimeEastern(row.kickoff))}
            </span>
            <span className="text-right">
              <TeamCode code={row.awayCode} teamId={row.awayId} live={live} />
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
          {expandable && (
            <ChevronRight
              size={14}
              className="shrink-0 text-cream-faint transition-transform duration-300 motion-reduce:transition-none"
              style={{ transform: open ? "rotate(90deg)" : "none" }}
            />
          )}
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
                  <ReachStrip row={row} impact={impact} reachProbs={reachProbs} />
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

function ReachStrip({ row, impact, reachProbs }: { row: Row; impact: Impact | null; reachProbs: Record<string, Record<string, number>> }) {
  const score = row.homeGoals !== null && row.awayGoals !== null ? `${row.homeGoals}-${row.awayGoals}` : null;
  const sides = [
    { id: row.homeId, name: row.homeName },
    { id: row.awayId, name: row.awayName },
  ].filter((s): s is { id: string; name: string } => s.id !== null && Boolean(reachProbs[s.id]));

  if (impact?.liveMode !== "in_match_distribution" || sides.length === 0) {
    return <p className="font-display text-[12px] text-cream-faint">No material shift in either team&apos;s run from the game state.</p>;
  }
  return (
    <div className="space-y-6">
      <p className="font-display text-[12px] text-cream-faint">
        Estimated impact of{" "}
        <span className="font-semibold" style={{ color: chartColour(row.homeId ?? "") }}>{row.homeCode}</span>{" "}
        {score && <span className="font-mono font-semibold tabular-nums text-cream-dim">{score}</span>}{" "}
        <span className="font-semibold" style={{ color: chartColour(row.awayId ?? "") }}>{row.awayCode}</span>
        {row.minute !== null && <span className="ml-1.5 font-mono font-semibold tabular-nums text-cream-dim">{row.minute}&apos;</span>}
      </p>
      {sides.map((s) => (
        <ExitStageHistogram
          key={s.id}
          reachProbs={reachProbs[s.id]}
          colour={chartColour(s.id)}
          teamName={s.name}
          impact={impact.teams[s.id] ?? null}
        />
      ))}
    </div>
  );
}
