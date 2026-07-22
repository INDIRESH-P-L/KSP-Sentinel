/**
 * Shared Recharts styling.
 *
 * Recharts renders axes, tooltips and grids into SVG, where CSS custom
 * properties from the Tailwind theme aren't reachable as prop values — so the
 * handful of colours the charts need are mirrored here as literals. Keep these
 * in sync with the tokens in `app/globals.css`.
 */

/** var(--color-ink-faint) — axis ticks and captions. */
export const AXIS_INK = "#636366";
/** var(--color-ink-muted) — tooltip labels. */
export const LABEL_INK = "#A1A1A6";
/** var(--color-ink) — tooltip body. */
export const BODY_INK = "#FFFFFF";
/** var(--color-base) — knocks dots out of the line they sit on. */
export const BASE_INK = "#0F1419";

export const ACCENT_CYAN = "#00D9FF";
export const ACCENT_BLUE = "#3b82f6";
export const ACCENT_PURPLE = "#7C3AED";
export const OK = "#34C759";
export const WARN = "#FF9500";
export const DANGER = "#DC143C";
export const RED = "#FF3B30";

export const GRID_STROKE = "rgba(255,255,255,0.05)";

/** Popover styling for every `<Tooltip>`, matching the elevated panel token. */
export const TOOLTIP_STYLE: React.CSSProperties = {
  background: "#141b2b",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 12,
  color: BODY_INK,
  fontSize: 12,
};

/** Spread onto `<XAxis>`/`<YAxis>` so tick figures render in JetBrains Mono. */
export const MONO_TICK = {
  tick: { fill: AXIS_INK, fontFamily: "var(--font-mono)" },
} as const;
