import type { Metadata } from "next";
import { ArchiveLandingPage } from "@/components/archive/archive-landing-page";
import { loadDefaultArchiveDay } from "@/lib/archive/load";
import { archiveMetadata } from "@/lib/archive/metadata";

export async function generateMetadata(): Promise<Metadata> {
  const { day } = await loadDefaultArchiveDay();
  return archiveMetadata(day, { section: "home", canonical: "/" });
}

export default async function LandingPage() {
  const archive = await loadDefaultArchiveDay();
  return <ArchiveLandingPage {...archive} />;
}
