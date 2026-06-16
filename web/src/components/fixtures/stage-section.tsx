"use client";

import { FixtureDay } from "@/components/fixtures/fixture-day";
import { FixtureRow } from "@/components/fixtures/fixture-row";
import type { FixtureRow as Row, StageSection as Section } from "@/lib/fixtures";
import type { Impact } from "@/lib/impact";

interface StageSectionProps {
  section: Section;
  impact: Impact | null;
  openDay: string | null;
  onToggleDay: (dayKey: string) => void;
}

export function StageSection({ section, impact, openDay, onToggleDay }: StageSectionProps) {
  return (
    <section className="mt-7 first:mt-0">
      <h2 className="mb-1.5 font-display text-[12px] font-semibold uppercase tracking-[0.08em] text-cream-faint">
        {section.label}
      </h2>
      {section.layout === "days" ? (
        <div>
          {section.days.map((day) => (
            <FixtureDay
              key={day.dayKey}
              day={day}
              open={openDay === day.dayKey}
              onToggle={() => onToggleDay(day.dayKey)}
              impact={impact}
            />
          ))}
        </div>
      ) : (
        <FlatRows rows={section.rows} impact={impact} />
      )}
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
              <p className={`font-mono text-[10.5px] tabular-nums text-cream-faint ${i === 0 ? "pb-1 pt-1.5" : "border-t border-hairline/50 pb-1 pt-3"}`}>
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
