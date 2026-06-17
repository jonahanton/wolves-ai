"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";
import { FixtureDay } from "@/components/fixtures/fixture-day";
import { FixtureRow } from "@/components/fixtures/fixture-row";
import type { FixtureRow as Row, StageSection as Section } from "@/lib/fixtures";
import type { Impact } from "@/lib/impact";

interface StageSectionProps {
  section: Section;
  impact: Impact | null;
  open: boolean;
  onToggle: () => void;
  openDay: string | null;
  onToggleDay: (dayKey: string) => void;
  muted?: boolean;
}

export function StageSection({ section, impact, open, onToggle, openDay, onToggleDay, muted = false }: StageSectionProps) {
  const [everOpened, setEverOpened] = useState(false);
  if (open && !everOpened) setEverOpened(true);
  return (
    <section className={muted ? "mt-3 first:mt-0" : "mt-8 first:mt-0"}>
      <button type="button" onClick={onToggle} aria-expanded={open} className="flex w-full items-center gap-2.5 py-2 text-left">
        <h2
          className={
            muted
              ? "font-display text-[13px] font-semibold tracking-[-0.01em] text-cream-dim"
              : "font-display text-[15px] font-bold tracking-[-0.01em] text-cream"
          }
        >
          {section.label}
        </h2>
        <span className={`ml-1 h-px flex-1 ${muted ? "" : "bg-hairline"}`} />
        <ChevronDown
          size={muted ? 14 : 16}
          className="shrink-0 text-cream-faint transition-transform duration-300 motion-reduce:transition-none"
          style={{ transform: open ? "rotate(180deg)" : "none" }}
        />
      </button>
      <div className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none" style={{ gridTemplateRows: open ? "1fr" : "0fr" }}>
        <div className="overflow-hidden" inert={!open}>
          {everOpened &&
            (section.layout === "days" ? (
              <div className="pt-1">
                {section.days.map((day) => (
                  <FixtureDay key={day.dayKey} day={day} open={openDay === day.dayKey} onToggle={() => onToggleDay(day.dayKey)} impact={impact} />
                ))}
              </div>
            ) : (
              <FlatRows rows={section.rows} impact={impact} />
            ))}
        </div>
      </div>
    </section>
  );
}

function FlatRows({ rows, impact }: { rows: Row[]; impact: Impact | null }) {
  return (
    <ul>
      {rows.map((row, i) => {
        const newDay = i === 0 || rows[i - 1].dayKey !== row.dayKey;
        return (
          <li key={row.match}>
            {newDay && (
              <p className={`font-mono text-[11px] uppercase tracking-[0.07em] text-cream-dim ${i === 0 ? "pb-1 pt-1" : "pb-1 pt-3.5"}`}>
                {row.dayLabel}
              </p>
            )}
            <ul>
              <FixtureRow row={row} impact={impact} />
            </ul>
          </li>
        );
      })}
    </ul>
  );
}
