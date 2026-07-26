"use client";

import { ChevronDown, Clock3 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ForecastLoader } from "@/components/shell/forecast-loader";
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

function formatTeleportDay(day: string): string {
  return new Date(`${day}T12:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  });
}

export function ArchiveDateControl({ days, selectedDay, section }: ArchiveDateControlProps) {
  const router = useRouter();
  const [pendingDay, setPendingDay] = useState<string | null>(null);
  const navigationTimer = useRef<number | null>(null);
  const visibleDays = days.slice(1);
  useEffect(
    () => () => {
      if (navigationTimer.current) window.clearTimeout(navigationTimer.current);
    },
    [],
  );
  const selectDay = (day: string) => {
    if (day === selectedDay.day) return;
    setPendingDay(day);
    navigationTimer.current = window.setTimeout(
      () => router.push(archivePath(day, section)),
      650,
    );
  };
  return (
    <>
      <aside className="mb-5 flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-hairline pb-3 text-cream-faint">
        <label
          className="relative flex items-center gap-2 rounded-full border border-hairline/70 bg-night-2 px-3 py-1.5 transition-colors hover:border-cream/40"
          title="Choose archive date"
        >
          <Clock3 aria-hidden size={14} className="shrink-0 text-cream-dim" />
          <select
            aria-label="Archive date"
            aria-busy={pendingDay !== null}
            disabled={pendingDay !== null}
            value={selectedDay.day}
            onChange={(event) => selectDay(event.target.value)}
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
      {pendingDay && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-night/85 px-6 backdrop-blur-md">
          <div
            className="w-full max-w-md px-10"
            style={{
              background:
                "radial-gradient(ellipse at center, var(--color-night-2) 0%, oklch(0.255 0.024 255 / 0.68) 48%, transparent 76%)",
            }}
          >
            <ForecastLoader
              label={`Teleporting to ${formatTeleportDay(pendingDay)}…`}
              prominent
            />
          </div>
        </div>
      )}
    </>
  );
}
