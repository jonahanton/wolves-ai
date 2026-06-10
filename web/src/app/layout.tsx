import type { Metadata, Viewport } from "next";
import { Geist_Mono } from "next/font/google";
import localFont from "next/font/local";
import { TabBar } from "@/components/shell/tab-bar";
import { ThemeProvider, themeInitScript } from "@/components/theme-provider";
import "./globals.css";

const sans = localFont({
  src: "../fonts/GeneralSans-Variable.woff2",
  variable: "--font-sans",
  weight: "200 700",
  display: "swap",
});

const display = localFont({
  src: "../fonts/ClashDisplay-Variable.woff2",
  variable: "--font-display",
  weight: "200 700",
  display: "swap",
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
