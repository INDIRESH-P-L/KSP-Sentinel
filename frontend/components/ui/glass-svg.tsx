"use client";

import React from "react";
import { GLASS_SERIES, WHITE } from "@/lib/palette";

/**
 * Shared SVG "lit glass sphere" primitives.
 *
 * Any datum drawn as a circle in this console (network nodes, scatter bubbles)
 * is rendered as a shaded sphere rather than a flat disc: an outer bloom, a
 * body lit from the upper-left by an off-centre radial gradient, a specular
 * highlight cap, and a saturated rim. That shading is what reads as depth —
 * there is no WebGL involved, so it stays inspectable and server-renderable.
 */

/** Turn a hex colour into an id-safe suffix (`#e8cb8e` -> `e8cb8e`). */
const gradId = (color: string) => `ksp-glass-${color.replace("#", "")}`;

/** Every hue a sphere can take across the app (nodes, scatter bubbles) — one
 * gradient is emitted each. All drawn from the Karnataka emblem palette
 * (maroon / brass / ivory / graphite), no cool hues. */
export const GLASS_PALETTE = [...GLASS_SERIES];

/**
 * Gradients + bloom filter shared by every sphere in one SVG.
 *
 * Render exactly once per `<svg>`. Ids are global to the document, so two SVGs
 * on screen at once emit duplicate ids — harmless here because the definitions
 * are byte-identical and `url(#…)` resolves to the first match.
 */
export function GlassDefs({ colors = GLASS_PALETTE }: { colors?: string[] }) {
  return (
    <defs>
      {colors.map((c) => (
        <radialGradient key={c} id={gradId(c)} cx="34%" cy="28%" r="82%">
          <stop offset="0%" stopColor={WHITE} stopOpacity={0.92} />
          <stop offset="34%" stopColor={c} stopOpacity={0.82} />
          <stop offset="100%" stopColor={c} stopOpacity={0.3} />
        </radialGradient>
      ))}
      <filter id="ksp-node-glow" x="-70%" y="-70%" width="240%" height="240%">
        <feGaussianBlur stdDeviation={5} />
      </filter>
    </defs>
  );
}

/**
 * One lit glass sphere.
 *
 * `alpha` is how the 3D scenes fade distant geometry (atmospheric depth cue);
 * `dim` is the interaction state applied to everything outside a selection's
 * neighbourhood. `dim` wins when both are set.
 */
export function GlassSphere({
  cx, cy, r, color, active = false, dim = false, alpha = 1, onClick, children,
}: {
  cx: number; cy: number; r: number; color: string;
  active?: boolean; dim?: boolean; alpha?: number;
  onClick?: () => void;
  children?: React.ReactNode;
}) {
  return (
    <g
      onClick={onClick}
      className={onClick ? "cursor-pointer" : undefined}
      style={{ opacity: dim ? 0.2 : alpha, transition: "opacity 200ms ease" }}
    >
      {/* Bloom — sits behind the body so the sphere appears to emit light. */}
      <circle cx={cx} cy={cy} r={r + 3} fill={color} opacity={active ? 0.55 : 0.3} filter="url(#ksp-node-glow)" />
      {/* Body, lit from upper-left. */}
      <circle
        cx={cx} cy={cy} r={r}
        fill={`url(#${gradId(color)})`}
        stroke="rgba(255,255,255,0.55)" strokeWidth={active ? 1.3 : 0.7}
      />
      {/* Specular cap. */}
      <ellipse
        cx={cx - r * 0.3} cy={cy - r * 0.34} rx={r * 0.5} ry={r * 0.3}
        fill="rgba(255,255,255,0.65)" opacity={0.7}
      />
      {/* Saturated rim, so the silhouette survives against a dark backdrop. */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeOpacity={active ? 0.95 : 0.5} strokeWidth={0.9} />
      {active && <circle cx={cx} cy={cy} r={r + 7} fill="none" stroke="#fff" strokeWidth={1} opacity={0.5} />}
      {children}
    </g>
  );
}
