"use client";

import { ChevronRight } from "lucide-react";
import { useState } from "react";
import { FixtureSlotDetail } from "@/components/fixtures/fixture-slot-detail";
import { WdlCurves } from "@/components/fixtures/wdl-curves";
import type { FixtureRow as Row } from "@/lib/fixtures";
import { formatKickoffTimeEastern, formatPctBare } from "@/lib/format";
import { chartColour } from "@/lib/team-colours";

interface FixtureRowProps {
  row: Row;
}

function Outcome({ label, pct }: { label: string; pct: number }) {
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="font-display text-[12px] text-cream-faint">{label}</span>
      <span className="font-semibold tabular-nums text-cream">{formatPctBare(pct)}%</span>
    </span>
  );
}

function TeamCode({ code, teamId, tbc }: { code: string; teamId?: string | null; tbc?: boolean }) {
  const colour = tbc || !teamId ? "var(--color-cream-faint)" : chartColour(teamId);
  return (
    <span className="font-display text-[15px] font-semibold" style={{ color: colour }}>
      {code}
    </span>
  );
}

export function FixtureRow({ row }: FixtureRowProps) {
  const [open, setOpen] = useState(false);
  const [everOpened, setEverOpened] = useState(false);
  const tbc = row.slot !== null;
  const completed = row.status === "completed";
  const expandable = !completed && (row.shape !== null || tbc);
  const score = row.homeGoals !== null && row.awayGoals !== null ? `${row.homeGoals}-${row.awayGoals}` : null;
  const toggle = () => {
    if (!expandable) return;
    setEverOpened(true);
    setOpen((value) => !value);
  };

  return (
    <li className={`border-b border-hairline/50 last:border-b-0 ${completed ? "opacity-70" : ""}`}>
      {tbc ? (
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          className="flex w-full items-center py-2.5 text-left"
        >
          <span className="grid w-[9.5rem] shrink-0 grid-cols-[1fr_3.2rem_1fr] items-baseline gap-2">
            <span className="text-left">
              <TeamCode code={row.slot?.home.label ?? "TBC"} tbc />
            </span>
            <span className="text-center font-mono text-[13px] tabular-nums text-cream-dim">
              {formatKickoffTimeEastern(row.kickoff)}
            </span>
            <span className="text-right">
              <TeamCode code={row.slot?.away.label ?? "TBC"} tbc />
            </span>
          </span>
          <span className="ml-auto font-display text-[14px] font-semibold uppercase tracking-[0.06em] text-cream-dim">
            TBC
          </span>
        </button>
      ) : (
        <button
          type="button"
          onClick={toggle}
          aria-expanded={expandable ? open : undefined}
          disabled={!expandable}
          className="flex w-full flex-wrap items-center gap-x-3 gap-y-1.5 py-2.5 text-left"
        >
          <span className="order-1 grid w-[9.5rem] shrink-0 grid-cols-[1fr_3.2rem_1fr] items-baseline gap-2">
            <span className="text-left">
              <TeamCode code={row.homeCode} teamId={row.homeId} />
            </span>
            <span className={`text-center font-mono text-[13px] tabular-nums ${completed ? "text-cream" : "text-cream-dim"}`}>
              {score ?? formatKickoffTimeEastern(row.kickoff)}
            </span>
            <span className="text-right">
              <TeamCode code={row.awayCode} teamId={row.awayId} />
            </span>
          </span>
          {!completed && row.bar && (
            <span className="order-3 flex w-full items-baseline justify-start gap-5 font-mono text-[13.5px] tabular-nums sm:order-2 sm:ml-auto sm:w-auto sm:gap-4">
              <Outcome label={row.homeCode} pct={row.bar.home} />
              {!row.knockout && <Outcome label="Draw" pct={row.bar.draw} />}
              <Outcome label={row.awayCode} pct={row.bar.away} />
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
        <div
          className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none"
          style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
        >
          <div className="overflow-hidden" inert={!open}>
            {everOpened && (
              <div className="-mx-1.5 mb-3 mt-1.5 rounded-lg border border-hairline bg-night-2 px-4 pb-5 pt-4 shadow-[inset_0_1px_0_oklch(1_0_0/0.04)]">
                {tbc && row.slot ? (
                  <FixtureSlotDetail slot={row.slot} />
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
