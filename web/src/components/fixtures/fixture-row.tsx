"use client";

import { ChevronRight } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { WdlCurves } from "@/components/fixtures/wdl-curves";
import { type FixtureRow as Row, liveWdlFrames, type WdlFrame } from "@/lib/fixtures";
import { teamReachShifts } from "@/lib/fixtures-reach";
import { formatKickoffTimeEastern, formatPctBare } from "@/lib/format";
import type { Impact } from "@/lib/impact";
import { chartColour } from "@/lib/team-colours";

interface FixtureRowProps {
  row: Row;
  impact: Impact | null;
}

function Outcome({ label, pct }: { label: string; pct: number }) {
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="font-display text-[12px] text-cream-faint">{label}</span>
      <span className="font-semibold tabular-nums text-cream">{formatPctBare(pct)}%</span>
    </span>
  );
}

function TeamCode({ code, teamId, live, tbc }: { code: string; teamId?: string | null; live?: boolean; tbc?: boolean }) {
  const colour = tbc || !teamId ? "var(--color-cream-faint)" : chartColour(teamId);
  return (
    <span className={`font-display text-[15px] font-semibold ${live ? "shimmer-red" : ""}`} style={live ? undefined : { color: colour }}>
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
          <span className="grid w-[9.5rem] shrink-0 grid-cols-[1fr_3.2rem_1fr] items-baseline gap-2">
            <span className="text-left">
              <TeamCode code={row.slot?.home.label ?? "TBC"} tbc />
            </span>
            <span className="text-center font-mono text-[13px] tabular-nums text-cream-dim">{formatKickoffTimeEastern(row.kickoff)}</span>
            <span className="text-right">
              <TeamCode code={row.slot?.away.label ?? "TBC"} tbc />
            </span>
          </span>
          <span className="ml-auto font-display text-[14px] font-semibold uppercase tracking-[0.06em] text-cream-dim">TBC</span>
        </button>
      ) : (
        <button
          type="button"
          onClick={() => expandable && setOpen((v) => !v)}
          aria-expanded={expandable ? open : undefined}
          disabled={!expandable}
          className="flex w-full flex-wrap items-center gap-x-3 gap-y-1.5 py-2.5 text-left"
        >
          <span className="order-1 grid w-[9.5rem] shrink-0 grid-cols-[1fr_3.2rem_1fr] items-baseline gap-2">
            <span className="text-left">
              <TeamCode code={row.homeCode} teamId={row.homeId} live={live} />
            </span>
            <span className={`text-center font-mono text-[13px] tabular-nums ${live ? "shimmer-red font-semibold" : completed ? "text-cream" : "text-cream-dim"}`}>
              {live ? (score ?? "-") : (score ?? formatKickoffTimeEastern(row.kickoff))}
            </span>
            <span className="text-right">
              <TeamCode code={row.awayCode} teamId={row.awayId} live={live} />
            </span>
          </span>
          {!completed && (live || row.bar) && (
            <span className="order-3 flex w-full items-baseline justify-between font-mono text-[13.5px] tabular-nums sm:order-2 sm:ml-auto sm:w-auto sm:justify-start sm:gap-4">
              {live ? (
                <span className="shimmer-red font-semibold">{row.minute !== null ? `${row.minute}'` : "live"}</span>
              ) : row.bar ? (
                <>
                  <Outcome label={row.homeCode} pct={row.bar.home} />
                  {!row.knockout && <Outcome label="Draw" pct={row.bar.draw} />}
                  <Outcome label={row.awayCode} pct={row.bar.away} />
                </>
              ) : null}
            </span>
          )}
          {expandable && (
            <ChevronRight
              size={14}
              className="order-2 ml-auto shrink-0 text-cream-faint transition-transform duration-300 motion-reduce:transition-none sm:order-3 sm:ml-0"
              style={{ transform: open ? "rotate(90deg)" : "none" }}
            />
          )}
        </button>
      )}

      {expandable && (
        <div className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none" style={{ gridTemplateRows: open ? "1fr" : "0fr" }}>
          <div className="overflow-hidden" inert={!open}>
            {everOpened && (
              <div className="-mx-1.5 mt-1 rounded-md bg-night-2/60 px-4 pb-5 pt-4">
                {tbc && row.slot ? (
                  <SlotDetail row={row} />
                ) : live ? (
                  <LiveDetail row={row} impact={impact} />
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
    <div className="grid grid-cols-[2.2rem_repeat(3,5.5rem)] items-baseline gap-x-2">
      <span className="font-mono text-[13px] text-cream-faint">{label}</span>
      {candidates.map((c) => (
        <span key={c.teamId} className="font-display text-[14.5px]">
          <span className="font-semibold text-cream">{c.code}</span>
          <span className="ml-1.5 font-mono text-[12.5px] tabular-nums text-cream-faint">{formatPctBare(c.prob)}%</span>
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

type GoalSide = "home" | "away";

interface ReplayTick {
  minute: number;
  index: number;
  morphing: boolean;
  animate: boolean;
  beat: GoalSide | null;
  morphMs: number;
}

interface Replay extends Omit<ReplayTick, "morphMs"> {
  morphMs: number;
  playing: boolean;
  play: () => void;
}

const MS_PER_MINUTE = 78;
const MIN_RUN_MS = 4200;
const MAX_RUN_MS = 9500;
const GOAL_PAUSE_MS = 1500;
const GOAL_MORPH_MS = 360;
const DRIFT_MORPH_MS = 760;

function goalSide(curr: WdlFrame, prev: WdlFrame): GoalSide | null {
  if (curr.homeGoals > prev.homeGoals) return "home";
  if (curr.awayGoals > prev.awayGoals) return "away";
  return null;
}

// Run the match clock from kickoff to now. Between goals the curve is held (we
// have no intermediate keyframes, and a level scoreline barely drifts). When the
// clock reaches a goal minute the clock pauses, the scorer flashes and the curve
// jolts; the final same-score frame is a gentle drift, not a beat.
function useReplay(frames: WdlFrame[]): Replay {
  const target = frames.length > 0 ? frames[frames.length - 1].minute : 0;
  const [tick, setTick] = useState<ReplayTick | null>(null);
  const raf = useRef(0);

  useEffect(() => () => cancelAnimationFrame(raf.current), []);

  const play = useCallback(() => {
    cancelAnimationFrame(raf.current);
    if (frames.length < 2) return;
    const run = Math.min(MAX_RUN_MS, Math.max(MIN_RUN_MS, target * MS_PER_MINUTE));
    let prev = performance.now();
    let clock = 0;
    let pause = 0;
    let lastIndex = 0;
    let morphStart = 0;
    let morphMs = DRIFT_MORPH_MS;
    let beat: GoalSide | null = null;
    setTick({ minute: 0, index: 0, morphing: false, animate: false, beat: null, morphMs: DRIFT_MORPH_MS });

    const step = (now: number) => {
      const dt = now - prev;
      prev = now;
      if (pause > 0) {
        pause -= dt;
        const morphing = now - morphStart < morphMs;
        setTick({ minute: frames[lastIndex].minute, index: lastIndex, morphing, animate: true, beat, morphMs });
        raf.current = requestAnimationFrame(step);
        if (pause <= 0) beat = null;
        return;
      }
      clock += dt;
      const minute = Math.min(1, clock / run) * target;
      let index = 0;
      for (let i = 0; i < frames.length; i += 1) {
        if (frames[i].minute <= minute + 1e-6) index = i;
      }
      if (index !== lastIndex) {
        const side = goalSide(frames[index], frames[lastIndex]);
        lastIndex = index;
        morphStart = now;
        morphMs = side ? GOAL_MORPH_MS : DRIFT_MORPH_MS;
        if (side) {
          beat = side;
          pause = GOAL_PAUSE_MS;
          setTick({ minute: frames[index].minute, index, morphing: true, animate: true, beat, morphMs });
          raf.current = requestAnimationFrame(step);
          return;
        }
      }
      const morphing = now - morphStart < morphMs;
      setTick({ minute: Math.round(minute), index, morphing, animate: true, beat: null, morphMs });
      if (clock < run || morphing) raf.current = requestAnimationFrame(step);
      else setTick(null);
    };
    raf.current = requestAnimationFrame(step);
  }, [frames, target]);

  if (!tick) {
    const index = Math.max(0, frames.length - 1);
    return { index, minute: target, morphing: false, animate: true, beat: null, morphMs: DRIFT_MORPH_MS, playing: false, play };
  }
  return { ...tick, index: Math.min(tick.index, frames.length - 1), playing: true, play };
}

function LiveDetail({ row, impact }: { row: Row; impact: Impact | null }) {
  const fixture = impact?.fixtures.find((f) => f.match === row.match) ?? null;
  const frames = liveWdlFrames(fixture, row.minute, row.homeGoals, row.awayGoals);
  const { index, minute, morphing, animate, beat, morphMs, play } = useReplay(frames);
  const frame = frames[index] ?? null;
  const canReplay = frames.length >= 2;
  const beatCode = beat === "home" ? row.homeCode : beat === "away" ? row.awayCode : null;
  const beatId = beat === "home" ? row.homeId : beat === "away" ? row.awayId : null;
  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between gap-3">
        {frame && (
          <p className="flex items-baseline gap-1.5 font-display text-[13px] text-cream-faint">
            <span className="font-semibold" style={{ color: chartColour(row.homeId ?? "") }}>{row.homeCode}</span>
            <span className="font-mono font-semibold tabular-nums text-cream-dim">
              {frame.homeGoals}-{frame.awayGoals}
            </span>
            <span className="font-semibold" style={{ color: chartColour(row.awayId ?? "") }}>{row.awayCode}</span>
            <span className="ml-0.5 font-mono font-semibold tabular-nums text-cream-dim">{minute}&apos;</span>
            {beatCode && (
              <span
                key={`${index}-${beatCode}`}
                className="ml-1 animate-[goal-flash_1500ms_ease-out_forwards] font-display text-[11px] font-bold uppercase tracking-[0.08em]"
                style={{ color: chartColour(beatId ?? "") }}
              >
                Goal {beatCode}
              </span>
            )}
          </p>
        )}
        {canReplay && (
          <button
            type="button"
            onClick={play}
            className="shrink-0 rounded-full border border-hairline/70 px-3 py-1 font-display text-[11.5px] font-bold tracking-[0.01em] text-cream-dim transition-colors hover:border-cream/50 hover:text-cream"
          >
            Replay from kick-off
          </button>
        )}
      </div>
      {frame && (
        <WdlCurves
          shape={frame.shape}
          morphing={morphing}
          animate={animate}
          morphMs={morphMs}
          colours={row.colours}
          homeCode={row.homeCode}
          awayCode={row.awayCode}
          showDraw={!row.knockout}
        />
      )}
      <div className="border-t border-hairline/60 pt-4">
        <ReachStrip row={row} impact={impact} />
      </div>
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
      ? sides.map((s) => ({ ...s, shifts: teamReachShifts(impact, s.id) })).filter((g) => g.shifts.length > 0)
      : [];

  if (groups.length === 0) {
    return <p className="font-display text-[13px] text-cream-faint">No material shift in either team&apos;s run from the game state.</p>;
  }
  return (
    <div>
      <div className="space-y-3">
        {groups.map((g) => (
          <div key={g.id} className="space-y-1">
            {g.shifts.map((shift, i) => (
              <div key={shift.stageLabel} className="grid grid-cols-[2.8rem_5.5rem_auto] items-baseline gap-2 font-display text-[13.5px] leading-tight">
                <span className="font-semibold" style={{ color: i === 0 ? chartColour(g.id) : undefined }}>{i === 0 ? g.code : ""}</span>
                <span className="text-cream-dim">{shift.stageLabel}</span>
                <span className="font-mono text-[12.5px] tabular-nums text-cream-faint">
                  {shift.fromPct.toFixed(0)}% <span className="mx-0.5">&rarr;</span>
                  <span className="font-semibold text-cream">{shift.toPct.toFixed(0)}%</span>
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
