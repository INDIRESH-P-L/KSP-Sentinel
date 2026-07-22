"use client";

import React from "react";
import { GlassDefs, GlassSphere } from "@/components/ui/glass-svg";
import { AXIS_INK, LABEL_INK, ACCENT_CYAN, OK, WARN, RED } from "@/lib/chart-theme";

export type ScatterPoint = {
  x: number;
  y: number;
  label?: string;
  /** Relative magnitude in 0…1 (e.g. population) driving bubble radius. */
  weight?: number;
};

/** Bubble hue encodes the y value: cool where it's low, hot where it's high. */
const SCATTER_PALETTE = [OK, WARN, RED];

const W = 680;
const H = 340;
const PAD = { l: 50, r: 22, t: 18, b: 46 };
const IW = W - PAD.l - PAD.r;
const IH = H - PAD.t - PAD.b;
const GRID_FRACTIONS = [0, 0.25, 0.5, 0.75, 1];

/** Centred empty/degenerate-state message filling the chart's slot. */
function Notice({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full items-center justify-center px-6 text-center text-xs leading-relaxed text-[var(--color-ink-faint)]">
      {children}
    </div>
  );
}

/** Ordinary least squares — returns the fitted line's endpoints across `domain`. */
function fitLine(points: ScatterPoint[], domain: [number, number]) {
  const n = points.length;
  if (n < 2) return null;
  const meanX = points.reduce((s, p) => s + p.x, 0) / n;
  const meanY = points.reduce((s, p) => s + p.y, 0) / n;
  const varX = points.reduce((s, p) => s + (p.x - meanX) ** 2, 0);
  if (varX === 0) return null;
  const cov = points.reduce((s, p) => s + (p.x - meanX) * (p.y - meanY), 0);
  const slope = cov / varX;
  const intercept = meanY - slope * meanX;
  return {
    x1: domain[0], y1: slope * domain[0] + intercept,
    x2: domain[1], y2: slope * domain[1] + intercept,
  };
}

/** Pad a min/max pair outward by 8% so bubbles never touch the plot edge. */
function domainOf(values: number[]): [number, number] {
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || 1;
  return [lo - span * 0.08, hi + span * 0.08];
}

/** Four evenly spaced, rounded ticks across a domain. */
function ticksOf([lo, hi]: [number, number]) {
  return [0, 1 / 3, 2 / 3, 1].map((f) => Math.round(lo + (hi - lo) * f));
}

/**
 * Bubble scatter drawn as lit glass spheres.
 *
 * Hand-rolled rather than Recharts because each mark is a shaded sphere (see
 * `GlassSphere`) and the fitted trend line glows — neither is expressible
 * through Recharts' `<Scatter>` shape API without rebuilding the axis layer
 * anyway.
 */
export default function GlassScatter({
  points, xLabel, yLabel, xUnit = "",
}: {
  points: ScatterPoint[];
  xLabel: string;
  yLabel: string;
  xUnit?: string;
}) {
  if (!points.length) {
    return <Notice>No district observations available.</Notice>;
  }

  // Placeholder feeds (every district sharing one hardcoded indicator value)
  // would stack every bubble on a single coordinate and draw an axis of
  // identical ticks — which reads as a broken chart rather than as flat data.
  const distinctPositions = new Set(points.map((p) => `${p.x}|${p.y}`)).size;
  if (distinctPositions < 2) {
    return (
      <Notice>
        All {points.length} districts report identical {xLabel.toLowerCase()} and {yLabel.toLowerCase()} values —
        there is no distribution to plot.
      </Notice>
    );
  }

  const xDomain = domainOf(points.map((p) => p.x));
  const yDomain = domainOf(points.map((p) => p.y));
  const X = (v: number) => PAD.l + ((v - xDomain[0]) / (xDomain[1] - xDomain[0])) * IW;
  const Y = (v: number) => PAD.t + IH - ((v - yDomain[0]) / (yDomain[1] - yDomain[0])) * IH;

  const trend = fitLine(points, xDomain);
  // Label every bubble only when the plot is sparse enough to stay legible.
  const showLabels = points.length <= 12;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full">
      <GlassDefs colors={SCATTER_PALETTE} />

      {/* Grid */}
      {GRID_FRACTIONS.map((f) => (
        <React.Fragment key={f}>
          <line
            x1={PAD.l} x2={W - PAD.r} y1={PAD.t + IH * f} y2={PAD.t + IH * f}
            stroke="rgba(255,255,255,0.05)" strokeDasharray="3 3"
          />
          <line
            x1={PAD.l + IW * f} x2={PAD.l + IW * f} y1={PAD.t} y2={PAD.t + IH}
            stroke="rgba(255,255,255,0.05)" strokeDasharray="3 3"
          />
        </React.Fragment>
      ))}

      {/* Fitted trend */}
      {trend && (
        <line
          x1={X(trend.x1)} y1={Y(trend.y1)} x2={X(trend.x2)} y2={Y(trend.y2)}
          stroke={ACCENT_CYAN} strokeWidth={2} strokeDasharray="6 5"
          style={{ filter: "drop-shadow(0 0 4px rgba(0,217,255,0.5))" }}
        />
      )}

      {/* Bubbles */}
      {points.map((p, i) => {
        const share = (p.y - yDomain[0]) / (yDomain[1] - yDomain[0]);
        const color = share > 0.66 ? RED : share > 0.33 ? WARN : OK;
        const r = 6 + (p.weight ?? 0.35) * 14;
        const cx = X(p.x);
        const cy = Y(p.y);
        return (
          <React.Fragment key={p.label ?? i}>
            <GlassSphere cx={cx} cy={cy} r={r} color={color} alpha={0.96}>
              <title>{`${p.label ?? "District"} — ${xLabel} ${p.x}${xUnit}, ${yLabel} ${p.y}`}</title>
            </GlassSphere>
            {showLabels && p.label && (
              <text
                x={cx} y={cy - r - 5} textAnchor="middle"
                fill="rgba(255,255,255,0.62)" fontSize={8.5} fontWeight={600}
              >
                {p.label}
              </text>
            )}
          </React.Fragment>
        );
      })}

      {/* Axes */}
      {ticksOf(xDomain).map((v) => (
        <text
          key={`x${v}`} x={X(v)} y={H - 26} textAnchor="middle"
          fill={AXIS_INK} fontSize={9} fontFamily="var(--font-mono)"
        >
          {v}{xUnit}
        </text>
      ))}
      {ticksOf(yDomain).map((v) => (
        <text
          key={`y${v}`} x={PAD.l - 8} y={Y(v) + 3} textAnchor="end"
          fill={AXIS_INK} fontSize={9} fontFamily="var(--font-mono)"
        >
          {v}
        </text>
      ))}
      <text x={PAD.l + IW / 2} y={H - 6} textAnchor="middle" fill={LABEL_INK} fontSize={10} fontWeight={600}>
        {xLabel} →
      </text>
      <text
        x={15} y={PAD.t + IH / 2} textAnchor="middle"
        fill={LABEL_INK} fontSize={10} fontWeight={600}
        transform={`rotate(-90 15 ${PAD.t + IH / 2})`}
      >
        {yLabel} →
      </text>
    </svg>
  );
}
