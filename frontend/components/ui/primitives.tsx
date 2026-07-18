"use client";

import React from "react";

/** Bold uppercase section header used across screens. */
export function SectionTitle({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <h1 className={`text-3xl font-extrabold uppercase tracking-tight text-[var(--color-ink)] ${className}`}>
      {children}
    </h1>
  );
}

/** Small bold uppercase label for panel headers. */
export function PanelLabel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <h3 className={`text-xs font-bold uppercase tracking-wider text-[var(--color-ink-muted)] ${className}`}>
      {children}
    </h3>
  );
}

/** Glass panel wrapper. */
export function Panel({
  children, className = "", hover = false,
}: { children: React.ReactNode; className?: string; hover?: boolean }) {
  return (
    <div className={`glass p-5 ${hover ? "glass-hover" : ""} ${className}`}>{children}</div>
  );
}

/** Colored status/delta pill. */
export function Pill({
  children, tone = "neutral", className = "",
}: {
  children: React.ReactNode;
  tone?: "ok" | "warn" | "danger" | "info" | "neutral";
  className?: string;
}) {
  const tones: Record<string, string> = {
    ok: "text-[var(--color-ok)] bg-[var(--color-ok)]/10 border-[var(--color-ok)]/25",
    warn: "text-[var(--color-warn)] bg-[var(--color-warn)]/10 border-[var(--color-warn)]/25",
    danger: "text-[var(--color-danger)] bg-[var(--color-danger)]/10 border-[var(--color-danger)]/25",
    info: "text-[var(--color-accent-blue)] bg-[var(--color-accent-blue)]/10 border-[var(--color-accent-blue)]/25",
    neutral: "text-[var(--color-ink-muted)] bg-white/[0.03] border-[var(--color-hairline)]",
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold ${tones[tone]} ${className}`}>
      {children}
    </span>
  );
}

/** Full-panel loading state. */
export function Loading({ label = "Loading command datafeeds…" }: { label?: string }) {
  return (
    <div className="flex h-full min-h-64 items-center justify-center">
      <div className="animate-pulse text-sm font-bold uppercase tracking-wider text-[var(--color-accent-cyan)]">{label}</div>
    </div>
  );
}
