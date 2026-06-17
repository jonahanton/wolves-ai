"use client";

import { useState } from "react";
import { SectionTitle } from "@/components/forecast/section-title";
import type { Mover } from "@/lib/forecast";
import { chartColour, teamCode } from "@/lib/team-colours";

interface HeadlineMoversProps {
  movers: Mover[];
}

export function HeadlineMovers({ movers }: HeadlineMoversProps) {
  if (movers.length === 0) return null;
  return (
    <section>
      <SectionTitle>Where we differ from the market</SectionTitle>
      <ul className="space-y-3">
        {movers.map((mover) => (
          <MoverRow key={mover.teamId} mover={mover} />
        ))}
      </ul>
    </section>
  );
}

function MoverRow({ mover }: { mover: Mover }) {
  const [open, setOpen] = useState(false);
  const colour = chartColour(mover.teamId);
  const hasGap = mover.ourProb !== null && mover.marketProb !== null && mover.gapPp !== null;

  return (
    <li>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-baseline gap-2.5 text-left"
      >
        <span className="flex w-[3.4rem] shrink-0 items-baseline gap-1 font-display text-[13px] font-bold" style={{ color: colour }}>
          {teamCode(mover.name)}
          <span aria-hidden>{mover.direction === "up" ? "▲" : "▼"}</span>
        </span>
        <span className="min-w-0 flex-1 font-display text-[14px] font-semibold leading-snug text-cream">
          {mover.summary}
        </span>
      </button>

      {hasGap && (
        <p className="ml-[calc(3.4rem+0.625rem)] mt-1 flex flex-wrap items-baseline gap-x-3 font-mono text-[12px] tabular-nums">
          <span className="text-cream-dim">
            Our forecast <span className="font-semibold" style={{ color: colour }}>{(mover.ourProb! * 100).toFixed(1)}%</span>
          </span>
          <span className="text-cream-dim">
            Market <span className="font-semibold text-cream">{(mover.marketProb! * 100).toFixed(1)}%</span>
          </span>
          <span className="text-cream-faint">
            {mover.gapPp! >= 0 ? "+" : ""}{mover.gapPp!.toFixed(1)}pp {mover.direction === "up" ? "above" : "below"}
          </span>
        </p>
      )}

      <div
        className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none"
        style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden" inert={!open}>
          <p className="ml-[calc(3.4rem+0.625rem)] pt-1.5 font-display text-[13.5px] leading-relaxed text-cream-dim">
            {mover.why}
          </p>
        </div>
      </div>
    </li>
  );
}
