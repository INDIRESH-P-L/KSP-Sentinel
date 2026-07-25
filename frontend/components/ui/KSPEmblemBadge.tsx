import React from "react";

export function KSPEmblemBadge({ className = "" }: { className?: string }) {
  return (
    <div className={`relative flex items-center gap-2.5 rounded-full border border-[var(--color-brass)]/40 bg-[var(--color-surface-elevated)] px-4 py-1.5 shadow-md backdrop-blur-md transition-all duration-300 hover:border-[var(--color-brass-bright)] hover:shadow-lg ${className}`}>
      {/* Emblem SVG */}
      <div className="relative flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-[var(--color-brass)]/60 bg-gradient-to-b from-[var(--color-brass)]/30 to-[var(--color-maroon)]/40 p-1 shadow-inner">
        <svg viewBox="0 0 200 200" className="h-full w-full drop-shadow-[0_0_4px_rgba(232,203,142,0.8)]" xmlns="http://www.w3.org/2000/svg">
          <circle cx="100" cy="100" r="92" fill="none" stroke="var(--color-brass-bright)" strokeWidth="4" />
          <circle cx="100" cy="100" r="82" fill="none" stroke="var(--color-brass)" strokeWidth="2" />
          {/* Twin heads & wings */}
          <path d="M100 60 C115 45, 140 45, 150 70 C140 80, 120 75, 100 95 C80 75, 60 80, 50 70 C60 45, 85 45, 100 60 Z" fill="var(--color-brass-bright)" opacity="0.9" />
          <path d="M100 40 L106 54 L100 50 L94 54 Z" fill="var(--color-brass-bright)" />
          <circle cx="100" cy="100" r="14" fill="var(--color-maroon)" stroke="var(--color-brass-bright)" strokeWidth="2" />
          <circle cx="100" cy="100" r="5" fill="var(--color-brass-bright)" />
        </svg>
      </div>

      {/* Emblem Text */}
      <div className="flex flex-col text-center">
        <div className="flex items-center gap-1.5 text-[11px] font-black tracking-[0.14em] text-[var(--color-brass-bright)] uppercase">
          <span>KARNATAKA STATE POLICE</span>
        </div>
        <span className="text-[9px] font-bold tracking-[0.08em] text-[var(--color-ink-muted)]">
          ಕರ್ನಾಟಕ ರಾಜ್ಯ ಪೊಲೀಸ್ • SERVICE & SECURITY
        </span>
      </div>
    </div>
  );
}
