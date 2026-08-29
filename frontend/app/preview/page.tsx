"use client";

/*
 * DESIGN SHOWCASE — not production UI.
 *
 * This page exists to render the palette, glass surfaces, type scale and chart
 * treatments side by side so they can be compared. The colour literals below are
 * therefore the SUBJECT of the page, not incidental styling, and are deliberately
 * written out rather than imported from lib/palette.ts. Every other file in the app
 * imports from that module; this one shows what is in it.
 */

import React, { useState } from "react";
import { motion } from "framer-motion";
import {
  ShieldAlert, Sun, Moon, Search, Bell, Command, ChevronRight,
  LayoutDashboard, Map, TrendingUp, Share2, MousePointerClick,
} from "lucide-react";
import { GlassPanel, GlassCard, Magnetic } from "@/components/ui/GlassPanel";

/* Standalone design-system showcase for Build Step 1. Renders under the root
   layout only (no Shell / no login gate) so the tokens, GlassPanel, emblem
   watermark and cursor-glow can be reviewed in isolation before any real
   screen is touched. */

const SWATCHES: { name: string; token: string; hex: string; ink?: string }[] = [
  { name: "Graphite", token: "--color-graphite", hex: "#0e0c0b", ink: "#f2ece0" },
  { name: "Surface", token: "--color-surface-2", hex: "#1e1913", ink: "#f2ece0" },
  { name: "Oxblood", token: "--color-maroon", hex: "#6e1622", ink: "#f2ece0" },
  { name: "Maroon Lit", token: "--color-maroon-bright", hex: "#98202f", ink: "#f2ece0" },
  { name: "Wine", token: "--color-wine", hex: "#7c2438", ink: "#f2ece0" },
  { name: "Gold", token: "--color-brass", hex: "#c2a164", ink: "#0e0c0b" },
  { name: "Gold Lit", token: "--color-brass-bright", hex: "#e8cb8e", ink: "#0e0c0b" },
  { name: "Ivory", token: "--color-ink", hex: "#f2ece0", ink: "#0e0c0b" },
];

const FUNCTIONAL: { name: string; token: string; hex: string }[] = [
  { name: "OK", token: "--color-ok", hex: "#8b9c6a" },
  { name: "Warn", token: "--color-warn", hex: "#c9a24a" },
  { name: "Danger", token: "--color-danger", hex: "#b03a3a" },
];

const KPIS = [
  { label: "Total FIRs", value: "48,217", delta: "+4.2%", icon: LayoutDashboard,
    detail: [["Cognizable", "31,904"], ["Non-cognizable", "16,313"], ["This week", "1,204"]] },
  { label: "Solve Rate", value: "62.8%", delta: "+1.9%", icon: TrendingUp,
    detail: [["Charge-sheeted", "58.1%"], ["Under trial", "22.4%"], ["Pending", "19.5%"]] },
  { label: "Active Cases", value: "7,449", delta: "-0.7%", icon: Search,
    detail: [["High priority", "612"], ["Assigned", "6,102"], ["Unassigned", "735"]] },
  { label: "Network Links", value: "12,930", delta: "+8.1%", icon: Share2,
    detail: [["Gang cells", "184"], ["Repeat offenders", "2,371"], ["Cross-district", "489"]] },
];

const NAV = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "map", label: "Crime Map", icon: Map },
  { id: "forecast", label: "Forecast", icon: TrendingUp },
  { id: "network", label: "Network", icon: Share2 },
];

export default function PreviewPage() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [heroEmblem, setHeroEmblem] = useState(false);
  const [nav, setNav] = useState("dashboard");

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-theme", next);
  };

  const toggleHero = () => {
    const next = !heroEmblem;
    setHeroEmblem(next);
    // Drives the shared root <EmblemWatermark> into its login-hero treatment.
    document.documentElement.setAttribute("data-authed", next ? "false" : "true");
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-12 md:px-10">
      {/* ============ HEADER ============ */}
      <header className="mb-10 flex flex-wrap items-center justify-between gap-6">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-[var(--color-brass)]/40 bg-[var(--color-maroon)]/25 text-[var(--color-brass-bright)] shadow-[0_0_28px_rgba(184,147,90,0.25)]">
            <ShieldAlert className="h-7 w-7" />
          </div>
          <div>
            <p className="mono text-[11px] font-bold uppercase tracking-[0.3em] text-[var(--color-brass)]">
              KSP Sentinel · Step 1 Preview
            </p>
            <h1 className="text-[26px] font-extrabold uppercase leading-none tracking-tight text-[var(--color-ink)]">
              Liquid Glass Design System
            </h1>
            <p className="mt-1.5 text-sm text-[var(--color-ink-muted)]">
              Karnataka palette · cursor-reactive glass · emblem watermark · ambient spotlight
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Magnetic>
            <button
              onClick={toggleHero}
              className="glass-body flex items-center gap-2 rounded-full border border-[var(--color-hairline)] px-4 py-2.5 text-xs font-semibold text-[var(--color-ink-muted)] transition-colors hover:text-[var(--color-ink)]"
            >
              <ShieldAlert className="h-4 w-4 text-[var(--color-brass)]" />
              {heroEmblem ? "Ambient emblem" : "Login hero emblem"}
            </button>
          </Magnetic>
          <Magnetic>
            <button
              onClick={toggleTheme}
              className="glass-body flex h-10 w-10 items-center justify-center rounded-full border border-[var(--color-hairline)] text-[var(--color-ink-muted)] transition-colors hover:text-[var(--color-ink)]"
              title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            >
              {theme === "dark" ? <Sun className="h-4.5 w-4.5 text-[var(--color-brass-bright)]" /> : <Moon className="h-4.5 w-4.5" />}
            </button>
          </Magnetic>
        </div>
      </header>

      <p className="mb-10 flex items-center gap-2 text-sm text-[var(--color-ink-faint)]">
        <MousePointerClick className="h-4 w-4 text-[var(--color-brass)]" />
        Move your cursor across the panels — each lights from where you point, a spotlight trails the pointer, and the emblem glows faintly behind the glass.
      </p>

      {/* ============ PALETTE ============ */}
      <Section title="01 · Palette" caption="Derived from the Karnataka State emblem — no blue, teal, purple or pink.">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          {SWATCHES.map((s) => (
            <div key={s.name} className="overflow-hidden rounded-[14px] border border-[var(--color-hairline)]">
              <div className="flex h-20 items-end p-2.5" style={{ background: s.hex, color: s.ink }}>
                <span className="text-[11px] font-bold uppercase tracking-wide">{s.name}</span>
              </div>
              <div className="bg-[var(--color-surface-2)] px-2.5 py-1.5">
                <p className="mono text-[10px] text-[var(--color-ink-faint)]">{s.hex}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--color-ink-faint)]">Functional (muted, used small):</span>
          {FUNCTIONAL.map((f) => (
            <span key={f.name} className="inline-flex items-center gap-2 rounded-full border border-[var(--color-hairline)] bg-[var(--color-surface-2)] px-3 py-1">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: f.hex }} />
              <span className="mono text-[11px] text-[var(--color-ink-muted)]">{f.name} {f.hex}</span>
            </span>
          ))}
        </div>
      </Section>

      {/* ============ LIQUID GLASS SURFACE ============ */}
      <Section title="02 · Liquid glass surface" caption="Cursor-reactive specular highlight · top-edge rim · specular sweep (mount + hover) · depth shadow.">
        <GlassPanel className="p-8">
          <div className="flex flex-col items-start gap-4 md:flex-row md:items-center md:justify-between">
            <div className="max-w-md">
              <h3 className="text-lg font-bold text-[var(--color-ink)]">Lit from where you point</h3>
              <p className="mt-1.5 text-sm text-[var(--color-ink-muted)]">
                A soft brass highlight tracks your cursor inside the glass, a diagonal streak sweeps across on hover, and the whole surface reads as physically thick — blur, rim light and ambient shadow, not a flat translucent div.
              </p>
            </div>
            <div className="flex gap-3">
              <Magnetic>
                <button className="rounded-full bg-gradient-to-r from-[var(--color-maroon)] to-[var(--color-maroon-bright)] px-5 py-2.5 text-sm font-semibold text-[var(--color-ink)] shadow-[0_10px_28px_rgba(122,31,43,0.4)]">
                  Primary action
                </button>
              </Magnetic>
              <Magnetic>
                <button className="rounded-full border border-[var(--color-brass)]/40 bg-[var(--color-brass)]/10 px-5 py-2.5 text-sm font-semibold text-[var(--color-brass-bright)]">
                  Secondary
                </button>
              </Magnetic>
            </div>
          </div>
        </GlassPanel>
      </Section>

      {/* ============ HOVER-POP CARDS + DEPTH OF FIELD ============ */}
      <Section title="03 · Hover pop + depth of field" caption="Hover a card: it lifts, its glass intensifies, a contextual popover appears — and its siblings blur and dim (like the iOS app switcher).">
        <div className="glass-focus grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {KPIS.map((k) => {
            const Icon = k.icon;
            const down = k.delta.startsWith("-");
            return (
              <GlassCard
                key={k.label}
                className="p-5"
                popover={
                  <div className="min-w-[190px]">
                    <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--color-brass)]">{k.label} breakdown</p>
                    <div className="flex flex-col gap-1.5">
                      {k.detail.map(([a, b]) => (
                        <div key={a} className="flex items-center justify-between gap-6">
                          <span className="text-[var(--color-ink-muted)]">{a}</span>
                          <span className="mono text-[var(--color-ink)]">{b}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                }
              >
                <div className="mb-4 flex items-center justify-between">
                  <span className="flex h-9 w-9 items-center justify-center rounded-[10px] border border-[var(--color-brass)]/30 bg-[var(--color-brass)]/10 text-[var(--color-brass-bright)]">
                    <Icon className="h-4.5 w-4.5" />
                  </span>
                  <span
                    className="mono rounded-full border px-2 py-0.5 text-[10px] font-bold"
                    style={{
                      borderColor: down ? "rgba(178,59,59,0.35)" : "rgba(138,154,107,0.4)",
                      color: down ? "#c65a5a" : "#a3b380",
                      background: down ? "rgba(178,59,59,0.1)" : "rgba(138,154,107,0.1)",
                    }}
                  >
                    {k.delta}
                  </span>
                </div>
                <p className="mono text-[26px] font-bold leading-none text-[var(--color-ink)]">{k.value}</p>
                <p className="mt-1.5 text-xs font-medium uppercase tracking-wide text-[var(--color-ink-faint)]">{k.label}</p>
              </GlassCard>
            );
          })}
        </div>
      </Section>

      {/* ============ SEGMENTED CAPSULE NAV (teaser) ============ */}
      <Section title="04 · Segmented capsule nav" caption="Preview of Step 2 — a single capsule flows and reshapes between items (Framer Motion shared layoutId).">
        <GlassPanel className="inline-flex flex-wrap gap-1 p-1.5" sweep={false}>
          {NAV.map((n) => {
            const Icon = n.icon;
            const active = nav === n.id;
            return (
              <button
                key={n.id}
                onClick={() => setNav(n.id)}
                className={`relative flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-semibold transition-colors ${
                  active ? "text-[var(--color-ink)]" : "text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]"
                }`}
              >
                {active && (
                  <motion.span
                    layoutId="preview-capsule"
                    className="absolute inset-0 rounded-full border border-[var(--color-brass)]/40 bg-gradient-to-r from-[var(--color-maroon)]/70 to-[var(--color-wine)]/60 shadow-[0_6px_20px_rgba(122,31,43,0.4)]"
                    transition={{ type: "spring", stiffness: 420, damping: 34 }}
                  />
                )}
                <Icon className="relative z-10 h-4 w-4" />
                <span className="relative z-10">{n.label}</span>
              </button>
            );
          })}
        </GlassPanel>
      </Section>

      {/* ============ CHROME PREVIEW ============ */}
      <Section title="05 · Chrome + controls" caption="Command palette trigger, status pill, notifications — all on the new glass.">
        <GlassPanel className="flex flex-wrap items-center gap-4 p-4" sweep={false}>
          <button className="glass-body flex min-w-0 flex-1 items-center gap-3 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 px-4 py-2.5 text-left">
            <Search className="h-4 w-4 shrink-0 text-[var(--color-ink-faint)]" />
            <span className="truncate text-xs text-[var(--color-ink-faint)]">Search cases, reports, or AI insights…</span>
            <span className="mono ml-auto flex shrink-0 items-center gap-1 rounded-[5px] border border-[var(--color-hairline)] px-1.5 py-0.5 text-[9px] text-[var(--color-ink-faint)]">
              <Command className="h-2.5 w-2.5" />K
            </span>
          </button>
          <div className="flex items-center gap-2 rounded-full border border-[var(--color-ok)]/30 bg-[var(--color-ok)]/10 px-3.5 py-[6px]">
            <span className="relative flex h-[7px] w-[7px]">
              <span className="ping-ring absolute inline-flex h-full w-full rounded-full bg-[var(--color-ok)]" />
              <span className="relative inline-flex h-[7px] w-[7px] rounded-full bg-[var(--color-ok)]" />
            </span>
            <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--color-ok)]">Gateway Online</span>
          </div>
          <Magnetic>
            <button className="relative flex h-10 w-10 items-center justify-center rounded-full border border-[var(--color-hairline)] text-[var(--color-ink-muted)]">
              <Bell className="h-4.5 w-4.5" />
              <span className="pulse-dot absolute right-2 top-2 h-[7px] w-[7px] rounded-full bg-[var(--color-danger)]" />
            </button>
          </Magnetic>
          <div className="flex items-center gap-1 text-xs text-[var(--color-ink-faint)]">
            <span>Magnetic controls</span>
            <ChevronRight className="h-3.5 w-3.5" />
          </div>
        </GlassPanel>
      </Section>

      {/* ============ CHECKLIST ============ */}
      <Section title="06 · Step-1 checklist" caption="Everything below is live on this page.">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {[
            "Karnataka palette tokens (graphite / maroon / brass / ivory)",
            "GlassPanel — cursor-reactive specular highlight (rAF, no re-render)",
            "Depth layering — blur + top rim light + ambient shadow",
            "Hover pop — lift + glass intensify + contextual popover",
            "Magnetic micro-movement on buttons/icons (spring, not snap)",
            "Specular sweep on mount + hover",
            "Ambient page spotlight follows the cursor viewport-wide",
            "Depth-of-field — inactive sibling cards blur/dim on hover",
            "EmblemWatermark (Gandaberunda) fixed behind every screen",
            "prefers-reduced-motion disables all pointer/ambient effects",
          ].map((item) => (
            <div key={item} className="flex items-start gap-3 rounded-[12px] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/50 px-4 py-3">
              <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[var(--color-brass)] text-[10px] font-black text-[var(--color-graphite)]">✓</span>
              <span className="text-sm text-[var(--color-ink-muted)]">{item}</span>
            </div>
          ))}
        </div>
      </Section>

      <footer className="mt-14 border-t border-[var(--color-hairline)] pt-6 text-center text-xs text-[var(--color-ink-faint)]">
        Reduce-motion tip: enable your OS “reduce motion” setting and reload — the spotlight, sweeps, magnetic pull and depth-of-field all switch off, leaving a calm static glass.
      </footer>
    </div>
  );
}

function Section({ title, caption, children }: { title: string; caption: string; children: React.ReactNode }) {
  return (
    <section className="mb-12">
      <div className="mb-4">
        <h2 className="text-sm font-bold uppercase tracking-[0.18em] text-[var(--color-brass)]">{title}</h2>
        <p className="mt-1 text-sm text-[var(--color-ink-faint)]">{caption}</p>
      </div>
      {children}
    </section>
  );
}
