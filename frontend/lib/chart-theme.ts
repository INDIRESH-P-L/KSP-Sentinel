/**
 * Shared Recharts styling.
 *
 * Recharts renders axes, tooltips and grids into SVG, where CSS custom
 * properties from the Tailwind theme aren't reachable as prop values — so the
 * handful of colours the charts need are mirrored here as literals. Keep these
 * in sync with the tokens in `app/globals.css` (the "Karnataka Command" palette:
 * graphite / maroon / brass / ivory).
 */

/** var(--color-ink-faint) — axis ticks and captions. */
export const AXIS_INK = "#8f8474";
/** var(--color-ink-muted) — tooltip labels. */
export const LABEL_INK = "#c4b9a4";
/** var(--color-ink) — tooltip body / ivory text. */
export const BODY_INK = "#f2ece0";
/** var(--color-base) — knocks dots out of the line they sit on. */
export const BASE_INK = "#0e0c0b";

/* ---- Emblem palette (literals for SVG) ---- */
export const GRAPHITE = "#0e0c0b";
export const MAROON = "#6e1622";
export const MAROON_BRIGHT = "#98202f";
export const MAROON_DEEP = "#470c13";
export const WINE = "#7c2438";
export const BRASS = "#c2a164";
export const BRASS_BRIGHT = "#e8cb8e";
export const BRASS_DIM = "#8a6b3b";
export const IVORY = "#f2ece0";

/* ---- Functional (muted, warm) ---- */
export const OK = "#8b9c6a";
export const WARN = "#c9a24a";
export const DANGER = "#b03a3a";

/* ---- Legacy aliases (kept so unmigrated charts keep importing; remapped to
   the emblem palette — no cool hues remain). ---- */
export const ACCENT_CYAN = BRASS_BRIGHT;
export const ACCENT_BLUE = MAROON_BRIGHT;
export const ACCENT_PURPLE = WINE;
export const RED = DANGER;

/** Warm, faint gridlines (gold-tinted). */
export const GRID_STROKE = "rgba(226,201,150,0.07)";

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
