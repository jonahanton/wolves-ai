import type { Metadata } from "next";
import { ArchiveTeamsPage } from "@/components/archive/archive-teams-page";
import { loadArchiveDay, loadArchiveManifest } from "@/lib/archive/load";
import { archiveMetadata } from "@/lib/archive/metadata";

interface PageProps {
  params: Promise<{ day: string }>;
}

export const dynamicParams = false;

export async function generateStaticParams(): Promise<{ day: string }[]> {
  return (await loadArchiveManifest()).days.map((day) => ({ day: day.day }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const archive = await loadArchiveDay((await params).day);
  return archiveMetadata(archive.day, {
    section: "teams",
    canonical: `/archive/${archive.day.day}/teams/`,
  });
}

export default async function ArchiveTeamsRoute({ params }: PageProps) {
  return <ArchiveTeamsPage {...(await loadArchiveDay((await params).day))} />;
}
