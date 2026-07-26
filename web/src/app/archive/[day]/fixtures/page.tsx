import type { Metadata } from "next";
import { ArchiveFixturesPage } from "@/components/archive/archive-fixtures-page";
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
    section: "fixtures",
    canonical: `/archive/${archive.day.day}/fixtures/`,
  });
}

export default async function ArchiveFixturesRoute({ params }: PageProps) {
  return <ArchiveFixturesPage {...(await loadArchiveDay((await params).day))} />;
}
