import type { Metadata } from "next";
import { ArchiveForecastRunPage } from "@/components/archive/archive-forecast-run-page";
import { archivedRun, archivedRunIds } from "@/lib/archive/load";
import { forecastRunMetadata } from "@/lib/archive/metadata";

interface PageProps {
  params: Promise<{ runId: string }>;
}

export const dynamicParams = false;

export async function generateStaticParams(): Promise<{ runId: string }[]> {
  return (await archivedRunIds()).map((runId) => ({ runId }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  return forecastRunMetadata((await params).runId);
}

export default async function ForecastRunPage({ params }: PageProps) {
  const run = await archivedRun((await params).runId);
  return <ArchiveForecastRunPage {...run} />;
}
