import type { Metadata } from "next";
import "./globals.css";
import Shell from "@/components/layout/Shell";

export const metadata: Metadata = {
  title: "KSP Sentinel - Crime Intelligence & Predictive Policing Platform",
  description: "AI-Powered Predictive Policing Command Center for the Karnataka State Police (KSP)",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased dark">
      <body className="min-h-full flex flex-col bg-slate-950 text-slate-100">
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
