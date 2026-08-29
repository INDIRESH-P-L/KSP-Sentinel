/**
 * The "Karnataka Command" palette — single source of truth for colour literals.
 *
 * Why literals exist at all
 * -------------------------
 * `app/globals.css` defines every colour as a Tailwind v4 `@theme` token, and markup
 * should use those (`text-[var(--color-brass)]`, `bg-surface`, …). But three consumers
 * cannot read a CSS custom property as a value:
 *
 *   * Recharts — axis/tooltip/grid colours are React props, not CSS.
 *   * MapLibre — paint properties are evaluated in the GL style, not the DOM.
 *   * Inline SVG gradients — `<stop stop-color>` needs a resolved colour.
 *
 * So a mirror is unavoidable. What was avoidable is having SEVEN of them: the same
 * hex strings were re-declared independently in chart-theme.ts, glass-svg.tsx,
 * primitives.tsx, MapContainer.tsx, NetworkView.tsx, DashboardView.tsx and
 * preview/page.tsx, with a comment in each asking the next reader to remember to
 * update all the others. That is not a design system, it is seven design systems that
 * happen to agree today — and they had already drifted (a `#4287f5` blue for station
 * markers and a `#00d9ff` cyan for graph edges, in a palette whose defining rule is
 * that no cool hue appears anywhere).
 *
 * Everything now imports from here. This file is the ONLY place a colour literal is
 * written, and it must stay in step with the `@theme` block in app/globals.css.
 */

/* ---- Core surfaces ---- */
export const BASE = "#0e0c0b";
export const SURFACE = "#17130f";
export const SURFACE_2 = "#1e1913";
export const ELEVATED = "#241d15";

/* ---- Emblem palette ---- */
export const GRAPHITE = "#0e0c0b";
export const MAROON = "#6e1622";
export const MAROON_BRIGHT = "#98202f";
export const MAROON_DEEP = "#470c13";
export const WINE = "#7c2438";
export const BRASS = "#c2a164";
export const BRASS_BRIGHT = "#e8cb8e";
export const BRASS_DIM = "#8a6b3b";
export const IVORY = "#f2ece0";

/* ---- Text ---- */
export const INK = "#f2ece0";
export const INK_MUTED = "#c4b9a4";
export const INK_FAINT = "#8f8474";

/* ---- Functional (muted, warm — never a second brand accent) ---- */
export const OK = "#8b9c6a";
export const WARN = "#c9a24a";
export const DANGER = "#b03a3a";

/**
 * On-dark text tints of the functional colours.
 *
 * OK / WARN / DANGER above are calibrated as FILLS — dots, chips, bar segments —
 * against the graphite ground. Used as text they sit too close to the background to
 * clear WCAG AA at body size, so each has a lighter tint reserved for type.
 *
 * These existed already, but as ad-hoc literals scattered across five files, and the
 * danger tint had drifted into two near-identical values (#c96a6a in band chips and
 * hover states, #d08585 in error banners) used for the same job. One value each.
 */
export const OK_TEXT = "#a3b380";
export const WARN_TEXT = "#d4b366";
export const DANGER_TEXT = "#d08585";

/**
 * Frosted-glass rod gradient (DashboardView bars).
 * Ivory-white specular at the cap, deep maroon at the foot.
 */
export const ROD_SPECULAR = "#fbf0d6";
export const ROD_SHEEN = "#fff8e6";
export const ROD_FOOT = "#25090e";

/** Pure white, for SVG specular highlights and marker rims only — never as a surface. */
export const WHITE = "#ffffff";

/* ---- Hairlines ---- */
export const HAIRLINE = "rgba(226,201,150,0.13)";
export const HAIRLINE_STRONG = "rgba(226,201,150,0.22)";

/**
 * Ordered series colours for categorical charts and graph clusters.
 *
 * Gold → maroon, distinguished by VALUE (light to dark) rather than hue, so the set
 * stays inside the emblem palette and remains separable for viewers with colour
 * vision deficiency — hue-based categorical scales do not.
 */
export const SERIES = [
  BRASS_BRIGHT,
  MAROON_BRIGHT,
  BRASS,
  WINE,
  BRASS_DIM,
  MAROON,
  MAROON_DEEP,
] as const;

/** Graph cluster colours: depth of oxblood, not different hues. */
export const GANG_SERIES = [MAROON_BRIGHT, MAROON, WINE, MAROON_DEEP, "#a8434f"] as const;

/** Edge strokes: neighbours of the selection light up gold, the rest recede. */
export const EDGE_LIT = "rgba(232,203,142,0.82)";
export const EDGE_IDLE = "rgba(196,185,164,0.13)";

/** Warm, faint chart gridlines (gold-tinted). */
export const GRID_STROKE = "rgba(226,201,150,0.07)";


/**
 * `"#c2a164"` -> `"194,161,100"`.
 *
 * Tailwind arbitrary values and inline styles build tinted fills as
 * `rgb(<triple> / 0.1)`, which needs the channels separately. Those triples used to
 * be hand-written next to a comment naming the hex they were meant to match -- two
 * representations of one colour, kept in step by eye. Derived now, so they cannot
 * disagree.
 */
export function rgbTriple(hex: string): string {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
  return `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`;
}

/**
 * Every colour a glass sphere can take (graph nodes, scatter bubbles).
 * Ordered light -> dark so adjacent entries stay separable by value, not hue.
 */
export const GLASS_SERIES = [
  BRASS_BRIGHT, BRASS, MAROON_BRIGHT, MAROON, WINE,
  WARN, OK, MAROON_DEEP, IVORY, BRASS_DIM,
] as const;
