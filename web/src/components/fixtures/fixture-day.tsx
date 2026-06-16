"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { FixtureRow } from "@/components/fixtures/fixture-row";
import type { DayGroup } from "@/lib/fixtures";
import type { Impact } from "@/lib/impact";

interface FixtureDayProps {
  day: DayGroup;
  open: boolean;
  onToggle: () => void;
  impact: Impact | null;
}

export function FixtureDay({ day, open, onToggle, impact }: FixtureDayProps) {
  const [everOpened, setEverOpened] = useState(false);
  if (open && !everOpened) setEverOpened(true);
  return (
    <section className="border-b border-hairline/40 last:border-b-0">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-baseline gap-2 py-2.5 text-left"
      >
        <span className="font-mono text-[11px] uppercase tracking-[0.07em] text-cream-dim">{day.label}</span>
        {day.isToday && <span className="font-mono text-[10.5px] uppercase tracking-[0.07em] text-gold">Today</span>}
        <span className="ml-auto font-mono text-[10.5px] tabular-nums text-cream-faint">{day.rows.length}</span>
        <ChevronDown
          size={13}
          className="shrink-0 text-cream-faint transition-transform duration-300 motion-reduce:transition-none"
          style={{ transform: open ? "rotate(180deg)" : "none" }}
        />
      </button>
      <div
        className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none"
        style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden" inert={!open}>
          {everOpened && (
            <ul className="pb-2">
              {day.rows.map((row) => (
                <FixtureRow key={row.match} row={row} impact={impact} />
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
