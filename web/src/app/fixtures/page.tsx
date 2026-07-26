import type { Metadata } from "next";
import { ArchiveFixturesPage } from "@/components/archive/archive-fixtures-page";
import { loadDefaultArchiveDay } from "@/lib/archive/load";
import { archiveMetadata } from "@/lib/archive/metadata";

export async function generateMetadata(): Promise<Metadata> {
  const { day } = await loadDefaultArchiveDay();
  return archiveMetadata(day, { section: "fixtures", canonical: "/fixtures/" });
}

export default async function FixturesPage() {
  return <ArchiveFixturesPage {...(await loadDefaultArchiveDay())} />;
}
