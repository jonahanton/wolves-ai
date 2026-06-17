import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { LiveDigest } from "@/components/shell/live-digest";
import { RouteProgress } from "@/components/shell/route-progress";
import { SiteNav } from "@/components/shell/site-nav";
import { orNull } from "@/lib/api";
import { loadImpact } from "@/lib/impact";
import { loadLiveState } from "@/lib/live";
import "./globals.css";

const albert = localFont({
  src: [
    { path: "../fonts/albert-sans-300.woff2", weight: "300" },
    { path: "../fonts/albert-sans-400.woff2", weight: "400" },
    { path: "../fonts/albert-sans-500.woff2", weight: "500" },
    { path: "../fonts/albert-sans-600.woff2", weight: "600" },
  ],
  variable: "--font-albert",
  display: "swap",
});

const plexMono = localFont({
  src: [
    { path: "../fonts/ibm-plex-mono-400.woff2", weight: "400" },
    { path: "../fonts/ibm-plex-mono-500.woff2", weight: "500" },
  ],
  variable: "--font-plex-mono",
  display: "swap",
});

const fraunces = localFont({
  src: [
    {
      path: "../fonts/fraunces-latin.woff2",
      weight: "340 600",
      style: "normal",
    },
  ],
  variable: "--font-fraunces",
  display: "swap",
});

const hanken = localFont({
  src: [
    {
      path: "../fonts/hanken-grotesk-latin.woff2",
      weight: "400 800",
      style: "normal",
    },
  ],
  variable: "--font-hanken",
  display: "swap",
});

export const metadata: Metadata = {
  title: "WWC26",
  description: "Wolves World Cup 2026 Superforecaster",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#1c1a17",
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const [live, impact] = await Promise.all([loadLiveState(), loadImpact()]);

  return (
    <html
      lang="en-GB"
      className={`${albert.variable} ${plexMono.variable} ${fraunces.variable} ${hanken.variable}`}
    >
      <body>
        <RouteProgress />
        <SiteNav />
        <LiveDigest initialLive={orNull(live)} initialImpact={orNull(impact)} />
        <main>{children}</main>
      </body>
    </html>
  );
}
