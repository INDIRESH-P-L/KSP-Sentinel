/**
 * Shared Recharts styling.
 *
 * Colour literals are NOT declared here any more -- they come from `lib/palette.ts`,
 * the single source of truth, and are re-exported so existing imports of
 * `@/lib/chart-theme` keep working unchanged.
 */
export {
  GRAPHITE, MAROON, MAROON_BRIGHT, MAROON_DEEP, WINE,
  BRASS, BRASS_BRIGHT, BRASS_DIM, IVORY,
  OK, WARN, DANGER, GRID_STROKE,
} from "@/lib/palette";

import {
  BRASS_BRIGHT, MAROON_BRIGHT, WINE, DANGER, INK, INK_MUTED, INK_FAINT, BASE,
} from "@/lib/palette";

/** var(--color-ink-faint) -- axis ticks and captions. */
export const AXIS_INK = INK_FAINT;
/** var(--color-ink-muted) -- tooltip labels. */
export const LABEL_INK = INK_MUTED;
/** var(--color-ink) -- tooltip body / ivory text. */
export const BODY_INK = INK;
/** var(--color-base) -- knocks dots out of the line they sit on. */
export const BASE_INK = BASE;

/* ---- Legacy aliases (kept so unmigrated charts keep importing; remapped to the
   emblem palette -- no cool hues remain). ---- */
export const ACCENT_CYAN = BRASS_BRIGHT;
export const ACCENT_BLUE = MAROON_BRIGHT;
export const ACCENT_PURPLE = WINE;
export const RED = DANGER;

/** Popover styling for every `<Tooltip>`, matching the elevated panel token. */
export const TOOLTIP_STYLE: React.CSSProperties = {
  background: "rgba(36,29,21,0.94)",
  border: "1px solid rgba(226,201,150,0.18)",
  borderRadius: 12,
  color: BODY_INK,
  fontSize: 12,
  boxShadow: "0 20px 50px rgba(0,0,0,0.5)",
  backdropFilter: "blur(8px)",
};

/** Spread onto `<XAxis>`/`<YAxis>` so tick figures render in JetBrains Mono. */
export const MONO_TICK = {
  tick: { fill: AXIS_INK, fontFamily: "var(--font-mono)" },
} as const;
