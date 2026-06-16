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
  reachProbs: Record<string, Record<string, number>>;
  open: boolean;
  onToggle: () => void;
  openDay: string | null;
  onToggleDay: (dayKey: string) => void;
}

function sectionCount(section: Section): number {
  return section.layout === "days" ? section.days.reduce((n, d) => n + d.rows.length, 0) : section.rows.length;
}

export function StageSection({ section, impact, reachProbs, open, onToggle, openDay, onToggleDay }: StageSectionProps) {
  const [everOpened, setEverOpened] = useState(false);
  if (open && !everOpened) setEverOpened(true);
  return (
    <section className="mt-8 first:mt-0">
      <button type="button" onClick={onToggle} aria-expanded={open} className="flex w-full items-center gap-2.5 py-2 text-left">
        <h2 className="font-display text-[15px] font-bold tracking-[-0.01em] text-cream">{section.label}</h2>
        <span className="font-mono text-[11px] tabular-nums text-cream-faint">{sectionCount(section)}</span>
        <span className="ml-1 h-px flex-1 bg-hairline" />
        <ChevronDown
          size={16}
          className="shrink-0 text-cream-dim transition-transform duration-300 motion-reduce:transition-none"
          style={{ transform: open ? "rotate(180deg)" : "none" }}
        />
      </button>
      <div className="grid transition-[grid-template-rows] duration-300 ease-out motion-reduce:transition-none" style={{ gridTemplateRows: open ? "1fr" : "0fr" }}>
        <div className="overflow-hidden" inert={!open}>
          {everOpened &&
            (section.layout === "days" ? (
              <div className="pt-1">
                {section.days.map((day) => (
                  <FixtureDay
                    key={day.dayKey}
                    day={day}
                    open={openDay === day.dayKey}
                    onToggle={() => onToggleDay(day.dayKey)}
                    impact={impact}
                    reachProbs={reachProbs}
                  />
                ))}
              </div>
            ) : (
              <FlatRows rows={section.rows} impact={impact} reachProbs={reachProbs} />
            ))}
        </div>
      </div>
    </section>
  );
}

function FlatRows({ rows, impact, reachProbs }: { rows: Row[]; impact: Impact | null; reachProbs: Record<string, Record<string, number>> }) {
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
              <FixtureRow row={row} impact={impact} reachProbs={reachProbs} />
            </ul>
          </li>
        );
      })}
    </ul>
  );
}
