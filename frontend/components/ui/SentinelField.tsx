"use client";

import React, { useEffect, useRef, useState } from "react";

/**
 * The live district field behind the sign-in screen.
 *
 * Every login screen in existence is a card on a background. This one is an instrument:
 * it plots the 39 Karnataka districts at their real coordinates, in the real shape of
 * the state, coloured by the safety band each one currently sits in — and a sweep line
 * rotates over them like the radar the product is named for, igniting each district as
 * it passes.
 *
 * The data is real and it is fetched BEFORE authentication, which is only possible
 * because this product has a genuinely public endpoint (/api/public/district-safety,
 * the citizen-facing safety map). So the screen can honestly show the state of the
 * network while still refusing access to it — the system keeping watch in front of you
 * while it decides whether to let you in. That is specific to this architecture; it is
 * not a background that could be dropped onto any other product.
 *
 * Constraints this respects:
 *   * The form never waits on it. The fetch is fire-and-forget; if it fails or is slow,
 *     the field simply stays empty and sign-in is unaffected.
 *   * `prefers-reduced-motion` renders a single static frame — the full picture, no
 *     sweep, no pulsing.
 *   * Rendering stops entirely when the tab is hidden.
 *   * aria-hidden. It carries no information a screen-reader user needs to sign in, and
 *     the same figures are printed as text in the telemetry strip beside it.
 */

type District = {
  district_name: string;
  latitude: number;
  longitude: number;
  safety_category: "Low" | "Medium" | "High";
  trend: string;
};

export type FieldTelemetry = {
  districtCount: number;
  asOf: string | null;
};

const BAND_RGB: Record<string, [number, number, number]> = {
  Low: [139, 156, 106],     // OK
  Medium: [201, 162, 74],   // WARN
  High: [176, 58, 58],      // DANGER
};

// Karnataka's real bounding box, padded. Fixed rather than derived from the payload so
// the state holds the same shape and position even before the data lands (and if a
// district is ever missing from the response).
const BOUNDS = { minLat: 11.4, maxLat: 18.6, minLng: 73.9, maxLng: 78.7 };

/** Line colours for the mesh and sweep, per theme.
 *
 * The field was drawn only in champagne gold, which is correct on graphite and
 * effectively invisible on the parchment theme -- the district dots survived because
 * they carry their own band colour, but the mesh and the sweep vanished. Light mode
 * uses a deep bronze instead, at higher alpha to hold up against a bright ground. */
const INK = {
  dark:  { mesh: "226,201,150", sweep: "232,203,142", meshA: 0.05, sweepA: 0.10, edgeA: 0.20 },
  light: { mesh: "94,66,20",    sweep: "110,22,34",   meshA: 0.16, sweepA: 0.09, edgeA: 0.30 },
};

/** Resolves the active theme the same way app/globals.css does: an explicit
 *  `data-theme` stamp wins, otherwise the OS preference decides. */
function resolveTheme(): "dark" | "light" {
  if (typeof document === "undefined") return "dark";
  const stamped = document.documentElement.getAttribute("data-theme");
  if (stamped === "light" || stamped === "dark") return stamped;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

const SWEEP_PERIOD_MS = 7200;   // one revolution
const IGNITE_MS = 1600;         // how long a district stays lit after the sweep passes
const LINK_MAX_KM = 145;        // neighbours joined into the mesh

function kmBetween(a: District, b: District) {
  const dLat = (a.latitude - b.latitude) * 110.6;
  const dLng = (a.longitude - b.longitude) * 111.3 * Math.cos((a.latitude * Math.PI) / 180);
  return Math.hypot(dLat, dLng);
}

export default function SentinelField({
  onTelemetry,
}: {
  onTelemetry?: (t: FieldTelemetry) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [districts, setDistricts] = useState<District[]>([]);
  const districtsRef = useRef<District[]>([]);
  const telemetryRef = useRef(onTelemetry);
  useEffect(() => { telemetryRef.current = onTelemetry; }, [onTelemetry]);

  const [theme, setTheme] = useState<"dark" | "light">("dark");
  useEffect(() => {
    const sync = () => setTheme(resolveTheme());
    sync();
    // The Shell writes data-theme on <html> when the operator toggles, and the OS
    // preference can change under a session that never toggled. Both must repaint.
    const mo = new MutationObserver(sync);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    mq.addEventListener("change", sync);
    return () => { mo.disconnect(); mq.removeEventListener("change", sync); };
  }, []);

  // ---- data (never blocks the form) ----
  useEffect(() => {
    let cancelled = false;
    const base = process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ?? "";
    fetch(`${base}/api/public/district-safety`)
      .then((r) => (r.ok ? r.json() : null))
      .then((json) => {
        if (cancelled || !json?.districts) return;
        const rows: District[] = json.districts.filter(
          (d: District) => Number.isFinite(d.latitude) && Number.isFinite(d.longitude));
        setDistricts(rows);
        districtsRef.current = rows;
        // Count the rows actually plotted rather than trusting `district_count`, which
        // counts what the API assessed -- including any row dropped here for missing
        // coordinates. The figure printed beside the map should describe the map.
        telemetryRef.current?.({
          districtCount: rows.length,
          asOf: typeof json.data_as_of === "string" ? json.data_as_of : null,
        });
      })
      .catch(() => { /* the field stays empty; sign-in is unaffected */ });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => { districtsRef.current = districts; }, [districts]);

  // ---- render ----
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const ink = INK[theme];
    let raf = 0;
    let start = performance.now();
    const ignited = new Map<number, number>();   // district index -> time lit

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const { clientWidth: w, clientHeight: h } = canvas;
      canvas.width = Math.max(1, Math.floor(w * dpr));
      canvas.height = Math.max(1, Math.floor(h * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const draw = (now: number) => {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (w === 0 || h === 0) { raf = requestAnimationFrame(draw); return; }

      const rows = districtsRef.current;
      ctx.clearRect(0, 0, w, h);

      // Fit the state's bounding box into the canvas, preserving aspect so Karnataka
      // is not stretched into an unrecognisable blob.
      const bw = BOUNDS.maxLng - BOUNDS.minLng;
      const bh = BOUNDS.maxLat - BOUNDS.minLat;
      const pad = Math.min(w, h) * 0.1;
      const scale = Math.min((w - pad * 2) / bw, (h - pad * 2) / bh);
      const ox = (w - bw * scale) / 2;
      const oy = (h - bh * scale) / 2;
      const project = (lat: number, lng: number): [number, number] => [
        ox + (lng - BOUNDS.minLng) * scale,
        oy + (BOUNDS.maxLat - lat) * scale,   // latitude increases upward
      ];

      const pts = rows.map((d) => {
        const [x, y] = project(d.latitude, d.longitude);
        return { d, x, y };
      });

      const cx = w / 2;
      const cy = h / 2;
      const elapsed = now - start;
      const sweep = reduced ? -Math.PI / 2 : ((elapsed % SWEEP_PERIOD_MS) / SWEEP_PERIOD_MS) * Math.PI * 2 - Math.PI / 2;

      // ── mesh: join nearby districts, so the field reads as a network rather than
      // a scatter of dots. Faint enough to sit behind everything else.
      ctx.lineWidth = 1;
      for (let i = 0; i < pts.length; i++) {
        for (let j = i + 1; j < pts.length; j++) {
          const km = kmBetween(pts[i].d, pts[j].d);
          if (km > LINK_MAX_KM) continue;
          const strength = 1 - km / LINK_MAX_KM;
          ctx.strokeStyle = `rgba(${ink.mesh},${ink.meshA * strength})`;
          ctx.beginPath();
          ctx.moveTo(pts[i].x, pts[i].y);
          ctx.lineTo(pts[j].x, pts[j].y);
          ctx.stroke();
        }
      }

      // ── sweep wedge
      if (!reduced && pts.length) {
        const radius = Math.hypot(w, h);
        const grad = ctx.createConicGradient?.(sweep - 0.55, cx, cy);
        if (grad) {
          grad.addColorStop(0, `rgba(${ink.sweep},0)`);
          grad.addColorStop(0.055, `rgba(${ink.sweep},${ink.sweepA})`);
          grad.addColorStop(0.075, `rgba(${ink.sweep},${ink.sweepA * 0.2})`);
          grad.addColorStop(1, `rgba(${ink.sweep},0)`);
          ctx.fillStyle = grad;
          ctx.beginPath();
          ctx.arc(cx, cy, radius, 0, Math.PI * 2);
          ctx.fill();
        }
        // leading edge
        ctx.strokeStyle = `rgba(${ink.sweep},${ink.edgeA})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(cx + Math.cos(sweep) * radius, cy + Math.sin(sweep) * radius);
        ctx.stroke();
      }

      // ── districts
      pts.forEach((p, i) => {
        const angle = Math.atan2(p.y - cy, p.x - cx);
        if (!reduced) {
          // Ignite when the sweep crosses this district's bearing.
          let delta = sweep - angle;
          while (delta < -Math.PI) delta += Math.PI * 2;
          while (delta > Math.PI) delta -= Math.PI * 2;
          if (delta >= 0 && delta < 0.08) ignited.set(i, now);
        }

        const lit = reduced ? 0 : Math.max(0, 1 - (now - (ignited.get(i) ?? -1e9)) / IGNITE_MS);
        const [r, g, b] = BAND_RGB[p.d.safety_category] ?? [194, 161, 100];

        // expanding ring on ignition
        if (lit > 0.02) {
          ctx.strokeStyle = `rgba(${r},${g},${b},${0.34 * lit})`;
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.arc(p.x, p.y, 3 + (1 - lit) * 16, 0, Math.PI * 2);
          ctx.stroke();
        }

        // glow
        const glow = 0.16 + lit * 0.5;
        const halo = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, 9 + lit * 9);
        halo.addColorStop(0, `rgba(${r},${g},${b},${glow})`);
        halo.addColorStop(1, `rgba(${r},${g},${b},0)`);
        ctx.fillStyle = halo;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 9 + lit * 9, 0, Math.PI * 2);
        ctx.fill();

        // core
        ctx.fillStyle = `rgba(${r},${g},${b},${0.55 + lit * 0.45})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 1.9 + lit * 1.5, 0, Math.PI * 2);
        ctx.fill();
      });

      if (!reduced) raf = requestAnimationFrame(draw);
    };

    raf = requestAnimationFrame(draw);

    // Stop entirely when the tab is hidden -- a rotating sweep nobody is looking at is
    // pure battery cost.
    const onVisibility = () => {
      cancelAnimationFrame(raf);
      if (!document.hidden) {
        start = performance.now();
        raf = requestAnimationFrame(draw);
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener("visibilitychange", onVisibility);
      ro.disconnect();
    };
  }, [districts.length, theme]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="absolute inset-0 h-full w-full"
    />
  );
}
