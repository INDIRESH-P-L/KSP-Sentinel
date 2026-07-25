import React from "react";

/**
 * KSP Sentinel emblem watermark — a stylised Gandaberunda (the twin-headed
 * bird of the Karnataka State emblem), rendered symmetrically as a
 * graphite/brass duotone.
 *
 * Mounted ONCE in the root layout so it sits, fixed, behind every screen
 * (dashboard, map, forecast, network, search, copilot, reports, admin, login).
 * It is deliberately faint (opacity ~6%) on internal screens and swells into a
 * larger, brighter hero (~15%) on the login/landing screen — driven entirely
 * by the `data-authed="false"` flag the Shell writes to <html>, so there is a
 * single shared component, never a per-page copy.
 *
 * Purely decorative: pointer-events:none, aria-hidden, and — because it lives
 * behind the glass panels — it stays faintly visible through their blur without
 * ever touching text contrast.
 */

/** One feather teardrop, tip toward -y from the origin. */
const FEATHER = "M0 0 C4 -9 4.5 -32 0 -46 C-4.5 -32 -4 -9 0 0 Z";

type Feather = { rot: number; len: number; px: number; py: number; op: number };

/** Fan of primaries for one (right-side) wing, sweeping up-and-out. */
function wingFeathers(): Feather[] {
  const N = 7;
  return Array.from({ length: N }, (_, i) => {
    const t = i / (N - 1);
    return {
      rot: 24 + t * 78, // 24° (up-right) → 102° (out-right, dipping)
      len: 0.68 + Math.sin(Math.PI * (0.22 + 0.6 * t)) * 0.5,
      px: 104 + t * 24,
      py: 82 - 4 * (1 - t),
      op: 0.9 - t * 0.16,
    };
  });
}

/** Fan of tail feathers, centred, spreading downward. */
function tailFeathers(): Feather[] {
  const N = 7;
  return Array.from({ length: N }, (_, i) => {
    const t = i / (N - 1);
    return {
      rot: 180 + (t - 0.5) * 60,
      len: 0.62 + (1 - Math.abs(t - 0.5) * 2) * 0.5,
      px: 100,
      py: 126,
      op: 0.8,
    };
  });
}

function Feathers({ data }: { data: Feather[] }) {
  return (
    <>
      {data.map((f, i) => (
        <path
          key={i}
          d={FEATHER}
          transform={`translate(${f.px} ${f.py}) rotate(${f.rot}) scale(0.92 ${f.len})`}
          fill="url(#ksp-emblem-duo)"
          stroke="var(--color-brass-bright)"
          strokeOpacity={0.5}
          strokeWidth={1.1}
          opacity={f.op}
        />
      ))}
    </>
  );
}

/** The right half of the crest (head, neck, wing). Mirrored for the left. */
function CrestHalf() {
  return (
    <g>
      <Feathers data={wingFeathers()} />
      {/* Neck ribbon rising from the body to the outward-turned head. */}
      <path
        d="M103 84 C102 66 109 55 120 51 C126 49 128 54 123 58 C114 62 110 71 109 84 Z"
        fill="url(#ksp-emblem-duo)"
        stroke="var(--color-brass-bright)"
        strokeOpacity={0.45}
        strokeWidth={1.1}
      />
      {/* Head. */}
      <circle cx={122} cy={49} r={6.4} fill="url(#ksp-emblem-duo)" stroke="var(--color-brass-bright)" strokeOpacity={0.5} strokeWidth={1.1} />
      {/* Beak, pointing outward. */}
      <path d="M127 46 L137 41.5 L129 52 Z" fill="var(--color-brass)" opacity={0.85} />
      {/* Eye — knocked out in graphite. */}
      <circle cx={121} cy={48} r={1.15} fill="var(--color-graphite)" />
      {/* Three-point crest. */}
      <path d="M117 43 L118.5 38 L120 43 Z M120 42 L121.5 36.5 L123 42 Z M123 43 L124.5 38.5 L126 43 Z" fill="var(--color-brass)" opacity={0.8} />
    </g>
  );
}

export default function EmblemWatermark({ className = "" }: { className?: string }) {
  return (
    <div className={`emblem-watermark ${className}`} aria-hidden="true">
      <svg viewBox="0 0 200 200" className="emblem-float h-full w-full" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="ksp-emblem-duo" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--color-brass-bright)" />
            <stop offset="60%" stopColor="var(--color-brass)" />
            <stop offset="100%" stopColor="var(--color-brass-dim)" />
          </linearGradient>
        </defs>

        {/* ---- Seal rings + tick ring ----
             Strokes are heavier than a print seal would use: the crest is read
             through stacked panel blurs, which eat hairlines entirely. */}
        <circle cx={100} cy={100} r={95} fill="none" stroke="var(--color-brass-bright)" strokeOpacity={0.6} strokeWidth={2.4} />
        <circle cx={100} cy={100} r={88} fill="none" stroke="var(--color-brass)" strokeOpacity={0.4} strokeWidth={1.4} />
        <g stroke="var(--color-brass)" strokeOpacity={0.45} strokeWidth={1.6}>
          {Array.from({ length: 36 }, (_, i) => {
            const a = (i / 36) * Math.PI * 2;
            const r1 = 88.5;
            const r2 = 94;
            return (
              <line
                key={i}
                x1={100 + Math.cos(a) * r1}
                y1={100 + Math.sin(a) * r1}
                x2={100 + Math.cos(a) * r2}
                y2={100 + Math.sin(a) * r2}
              />
            );
          })}
        </g>

        {/* ---- Top finial (trident crown) ---- */}
        <path
          d="M100 12 L103 24 L100 21 L97 24 Z M92 20 L94 27 M108 20 L106 27"
          fill="var(--color-brass-bright)"
          stroke="var(--color-brass-bright)"
          strokeWidth={1.6}
          opacity={0.85}
        />

        {/* ---- Twin heads + wings (right, then mirrored to left) ---- */}
        <CrestHalf />
        <g transform="translate(200 0) scale(-1 1)">
          <CrestHalf />
        </g>

        {/* ---- Central body ---- */}
        <path
          d="M100 66 C110 74 111 96 106 118 C104 126 96 126 94 118 C89 96 90 74 100 66 Z"
          fill="url(#ksp-emblem-duo)"
          stroke="var(--color-brass-bright)"
          strokeOpacity={0.5}
          strokeWidth={1.3}
        />
        {/* Chest lotus/star. */}
        <g stroke="var(--color-brass-bright)" strokeOpacity={0.6} strokeWidth={1.3} fill="none">
          {Array.from({ length: 8 }, (_, i) => {
            const a = (i / 8) * Math.PI * 2;
            return <line key={i} x1={100} y1={94} x2={100 + Math.cos(a) * 6} y2={94 + Math.sin(a) * 6} />;
          })}
          <circle cx={100} cy={94} r={2.4} fill="var(--color-brass)" fillOpacity={0.5} stroke="none" />
        </g>

        {/* ---- Tail ---- */}
        <Feathers data={tailFeathers()} />

        {/* ---- Talons ---- */}
        <g stroke="var(--color-brass-bright)" strokeOpacity={0.6} strokeWidth={1.7} strokeLinecap="round">
          <path d="M95 124 L91 132 M95 124 L95 133 M95 124 L99 132" fill="none" />
          <path d="M105 124 L101 132 M105 124 L105 133 M105 124 L109 132" fill="none" />
        </g>
      </svg>
    </div>
  );
}
