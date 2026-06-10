import type { Metadata, Viewport } from "next";
import { Funnel_Display, Geist_Mono } from "next/font/google";
import localFont from "next/font/local";
import { TabBar } from "@/components/shell/tab-bar";
import { ThemeProvider, themeInitScript } from "@/components/theme-provider";
import "./globals.css";

// Switzer and Funnel Display both carry uniform-width digits, which the global
// tabular-nums rule depends on; swap fonts only for faces that keep that true.
const sans = localFont({
  src: "../fonts/Switzer-Variable.woff2",
  variable: "--font-sans",
  weight: "100 900",
  display: "swap",
});

const display = Funnel_Display({
  variable: "--font-display",
  subsets: ["latin"],
});

const mono = Geist_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "The Wolves' World Cup Superforecaster",
  description: "Forecasting WC26 knockout fixtures, during the groups",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${sans.variable} ${display.variable} ${mono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-full flex flex-col">
        <ThemeProvider>
          <div className="flex flex-1 flex-col pb-24">{children}</div>
          <TabBar />
        </ThemeProvider>
      </body>
    </html>
  );
}
