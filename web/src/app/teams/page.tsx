import type { Metadata } from "next";
import { ArchiveTeamsPage } from "@/components/archive/archive-teams-page";
import { loadDefaultArchiveDay } from "@/lib/archive/load";
import { archiveMetadata } from "@/lib/archive/metadata";

export async function generateMetadata(): Promise<Metadata> {
  const { day } = await loadDefaultArchiveDay();
  return archiveMetadata(day, { section: "teams", canonical: "/teams/" });
}

export default async function TeamsPage() {
  return <ArchiveTeamsPage {...(await loadDefaultArchiveDay())} />;
}
