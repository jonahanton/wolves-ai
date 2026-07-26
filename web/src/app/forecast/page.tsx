import type { Metadata } from "next";
import { ArchiveForecastPage } from "@/components/archive/archive-forecast-page";
import { loadDefaultArchiveDay } from "@/lib/archive/load";
import { archiveMetadata } from "@/lib/archive/metadata";

export async function generateMetadata(): Promise<Metadata> {
  const { day } = await loadDefaultArchiveDay();
  return archiveMetadata(day, { section: "forecast", canonical: "/forecast/" });
}

export default async function ForecastIndexPage() {
  return <ArchiveForecastPage {...(await loadDefaultArchiveDay())} />;
}
