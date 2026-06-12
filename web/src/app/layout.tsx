import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { SiteFooter } from "@/components/shell/site-footer";
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

const splineMono = localFont({
  src: [
    { path: "../fonts/spline-sans-mono-400.woff2", weight: "400" },
    { path: "../fonts/spline-sans-mono-500.woff2", weight: "500" },
  ],
  variable: "--font-spline-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "The Wolves",
  description: "The Wolves' World Cup Superforecaster",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#1c1a17",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-GB" className={`${albert.variable} ${splineMono.variable}`}>
      <body className="flex min-h-svh flex-col">
        <SiteNav />
        <main className="flex-1">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
