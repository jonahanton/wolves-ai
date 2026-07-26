import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { RouteProgress } from "@/components/shell/route-progress";
import { SiteNav } from "@/components/shell/site-nav";
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

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://wolvesworldcup.com";
const TITLE = "WWC26 Superforecaster";
const DESCRIPTION =
  "An archive of the Wolves' World Cup 2026 forecast history.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: TITLE,
  description: DESCRIPTION,
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    siteName: TITLE,
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#1c1a17",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en-GB"
      className={`${albert.variable} ${plexMono.variable} ${fraunces.variable} ${hanken.variable}`}
    >
      <body>
        <RouteProgress />
        <div className="sticky top-0 z-30 bg-night/90">
          <SiteNav />
        </div>
        {children}
      </body>
    </html>
  );
}
