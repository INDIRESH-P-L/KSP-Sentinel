import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import CursorGlow from "@/components/ui/CursorGlow";
import EmblemWatermark from "@/components/ui/EmblemWatermark";
import LocaleProvider from "@/components/i18n/LocaleProvider";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

// Every figure the operator reads off the console (KPIs, z-scores, coordinates,
// axis ticks) is set in mono so digits stay column-aligned between refreshes.
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "KSP Sentinel — Crime Intelligence & Predictive Policing Platform",
  description:
    "AI-Powered Predictive Policing Command Center for the Karnataka State Police (KSP)",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="dark" className={`${inter.variable} ${jetbrainsMono.variable} h-full`}>
      <body className="min-h-full antialiased">
        {/* Ambient environment — painted behind every screen (fixed, z-0). The
            emblem stays faintly visible through the glass panels' blur; the
            spotlight follows the cursor across the whole viewport. */}
        <CursorGlow />
        <EmblemWatermark />
        {/* All app content composites above the ambient layers. */}
        <LocaleProvider>
          <div className="relative z-10">{children}</div>
        </LocaleProvider>
      </body>
    </html>
  );
}
