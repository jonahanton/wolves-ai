import type { Metadata } from "next";
import type { ArchiveDay } from "@/lib/archive/contracts";
import { formatRunStampEastern } from "@/lib/format";

export type ArchiveSection = "home" | "fixtures" | "teams" | "forecast";

const SECTION_LABELS: Record<ArchiveSection, string> = {
  home: "World Cup forecast",
  fixtures: "Fixtures and results",
  teams: "Team forecasts",
  forecast: "Forecast history",
};

export function archiveMetadata(
  day: ArchiveDay,
  { section, canonical }: { section: ArchiveSection; canonical: string },
): Metadata {
  const archiveDay = formatArchiveDay(day.day);
  const sectionLabel = SECTION_LABELS[section];
  const title = `${sectionLabel} · ${archiveDay}`;
  const published = formatRunStampEastern(day.forecast_created_at);
  const description = `${sectionLabel} as archived at the end of ${archiveDay}, using the forecast published ${published} ET.`;
  return {
    title,
    description,
    alternates: { canonical },
    openGraph: { title, description, url: canonical },
  };
}

export function forecastRunMetadata(runId: string): Metadata {
  const canonical = `/forecast/${runId}/`;
  const title = `Archived forecast · ${runId}`;
  const description = "A complete published Wolves' World Cup forecast from the tournament archive.";
  return {
    title,
    description,
    alternates: { canonical },
    openGraph: { title, description, url: canonical },
  };
}

function formatArchiveDay(day: string): string {
  return new Date(`${day}T12:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}
