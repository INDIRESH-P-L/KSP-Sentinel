"use client";

import React from "react";
import { rgbTriple, OK, WARN, DANGER, BRASS, WINE } from "@/lib/palette";

/** Bold uppercase screen header, lifted off the backdrop by a warm brass glow. */
export function SectionTitle({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <h1
      className={`text-[28px] font-extrabold uppercase leading-none tracking-[-0.01em] text-[var(--color-ink)] ${className}`}
      style={{ textShadow: "0 0 18px rgba(232,203,142,0.34)" }}
    >
      {children}
    </h1>
  );
}

/** Small bold uppercase label for panel headers. */
export function PanelLabel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <h3 className={`text-[11px] font-bold uppercase tracking-[0.1em] text-[var(--color-ink-muted)] ${className}`}>
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

/**
 * A figure the operator reads off the console — always monospaced so digits keep
 * their column between refreshes.
 */
export function Stat({
  children, className = "", style,
}: { children: React.ReactNode; className?: string; style?: React.CSSProperties }) {
  return <span className={`mono ${className}`} style={style}>{children}</span>;
}

// Derived from the canonical palette rather than transcribed. These were literal
// RGB triples with the matching hex in a trailing comment -- one colour written two
// ways, kept in step by hand.
const PILL_TONES = {
  ok: rgbTriple(OK),
  warn: rgbTriple(WARN),
  danger: rgbTriple(DANGER),
  info: rgbTriple(BRASS),
  violet: rgbTriple(WINE),
} as const;

export type PillTone = keyof typeof PILL_TONES | "neutral";

/** Colored status/delta pill — tinted fill, matching hairline, matching text. */
export function Pill({
  children, tone = "neutral", className = "",
}: {
  children: React.ReactNode;
  tone?: PillTone;
  className?: string;
}) {
  const base = "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[10px] font-bold";
  if (tone === "neutral") {
    return (
      <span className={`${base} border-[var(--color-hairline)] bg-white/[0.03] text-[var(--color-ink-muted)] ${className}`}>
        {children}
      </span>
    );
  }
  const rgb = PILL_TONES[tone];
  return (
    <span
      className={`${base} ${className}`}
      style={{
        borderColor: `rgba(${rgb},0.3)`,
        background: `rgba(${rgb},0.1)`,
        color: `rgb(${rgb})`,
      }}
    >
      {children}
    </span>
  );
}

/**
 * Radial progress dial. The arc carries a drop-shadow in its own hue so the
 * ring reads as emissive rather than painted, matching the console's other
 * lit surfaces.
 */
export function Gauge({
  value, label, color, size = 64,
}: { value: number; label: string; color: string; size?: number }) {
  const r = 26;
  const circumference = 2 * Math.PI * r;
  const dash = (Math.max(0, Math.min(100, value)) / 100) * circumference;
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ height: size, width: size }}>
        <svg viewBox="0 0 64 64" className="h-full w-full -rotate-90">
          <circle cx="32" cy="32" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="6" />
          <circle
            cx="32" cy="32" r={r} fill="none"
            stroke={color} strokeWidth="6" strokeLinecap="round"
            strokeDasharray={`${dash} ${circumference}`}
            style={{ transition: "stroke-dasharray 700ms ease", filter: `drop-shadow(0 0 4px ${color}88)` }}
          />
        </svg>
        <span className="mono absolute inset-0 flex items-center justify-center text-[13px] font-bold text-[var(--color-ink)]">
          {value}%
        </span>
      </div>
      <span className="text-center text-[10px] font-medium leading-tight text-[var(--color-ink-faint)]">{label}</span>
    </div>
  );
}

/** Full-panel loading state — a cyan sweep over the status line. */
export function Loading({ label = "Loading command datafeeds…" }: { label?: string }) {
  return (
    <div className="flex h-full min-h-64 flex-col items-center justify-center gap-4">
      <div className="relative h-[3px] w-40 overflow-hidden rounded-full bg-white/[0.06]">
        <div className="scan absolute inset-y-0 w-1/3 rounded-full bg-[var(--color-accent-cyan)] shadow-[0_0_12px_var(--color-accent-cyan)]" />
      </div>
      <div className="text-xs font-bold uppercase tracking-[0.14em] text-[var(--color-accent-cyan)]">{label}</div>
    </div>
  );
}
