"use client";

import { ChevronDown, Clock3 } from "lucide-react";
import { useRouter } from "next/navigation";
import { formatRunStampEastern } from "@/lib/format";
import type { ArchiveDay } from "@/lib/archive/contracts";

interface ArchiveDateControlProps {
  days: ArchiveDay[];
  selectedDay: ArchiveDay;
  section: "home" | "fixtures" | "teams" | "forecast";
}

function archivePath(day: string, section: ArchiveDateControlProps["section"]): string {
  const suffix = section === "home" ? "" : `/${section}`;
  return `/archive/${day}${suffix}`;
}

function formatArchiveDay(day: string): string {
  return new Date(`${day}T12:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function ArchiveDateControl({ days, selectedDay, section }: ArchiveDateControlProps) {
  const router = useRouter();
  const visibleDays = days.slice(1);
  return (
    <aside className="mb-5 flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-hairline pb-3 text-cream-faint">
      <label
        className="relative flex items-center gap-2 rounded-full border border-hairline/70 bg-night-2 px-3 py-1.5 transition-colors hover:border-cream/40"
        title="Choose archive date"
      >
        <Clock3 aria-hidden size={14} className="shrink-0 text-cream-dim" />
        <select
          aria-label="Archive date"
          value={selectedDay.day}
          onChange={(event) => router.push(archivePath(event.target.value, section))}
          className="appearance-none bg-transparent pr-5 font-display text-[12.5px] font-semibold tracking-[0.01em] text-cream outline-none"
        >
          {selectedDay.day === days[0]?.day && (
            <option value={selectedDay.day} hidden>
              {formatArchiveDay(selectedDay.day)}
            </option>
          )}
          {visibleDays.map((day) => (
            <option key={day.day} value={day.day}>
              {formatArchiveDay(day.day)}
            </option>
          ))}
        </select>
        <ChevronDown aria-hidden size={13} className="pointer-events-none absolute right-3 text-cream-faint" />
      </label>
      <span aria-live="polite" className="font-mono text-[10.5px]">
        Forecast published {formatRunStampEastern(selectedDay.forecast_created_at)} ET
      </span>
    </aside>
  );
}
