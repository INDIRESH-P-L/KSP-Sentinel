"use client";

import { useEffect, useRef } from "react";
import { useReducedMotion } from "framer-motion";

/**
 * Ambient page-level spotlight that follows the cursor across the whole
 * viewport, behind every glass panel — so the environment itself feels lit as
 * you move, not just the surface you're pointing at.
 *
 * Mounted once in the root layout. The soft brass/ivory core is a fixed
 * radial-gradient layer whose centre (`--cx`/`--cy`) is written directly to the
 * DOM node inside a requestAnimationFrame tick — never through React state — so
 * pointer movement can't trigger re-renders even on the map / network screens
 * that already carry their own render load.
 *
 * Disabled entirely under prefers-reduced-motion (both here and in CSS).
 */
export default function CursorGlow() {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (reduced) return;
    const el = ref.current;
    if (!el) return;

    let frame = 0;
    let px = 0;
    let py = 0;
    let active = false;

    const paint = () => {
      frame = 0;
      el.style.setProperty("--cx", `${px}px`);
      el.style.setProperty("--cy", `${py}px`);
      if (!active) {
        active = true;
        el.setAttribute("data-active", "true");
      }
    };

    const onMove = (e: PointerEvent) => {
      px = e.clientX;
      py = e.clientY;
      if (!frame) frame = requestAnimationFrame(paint);
    };

    const onLeave = () => {
      active = false;
      el.removeAttribute("data-active");
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("pointerleave", onLeave);
    return () => {
      if (frame) cancelAnimationFrame(frame);
      window.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerleave", onLeave);
    };
  }, [reduced]);

  return <div ref={ref} className="cursor-glow" aria-hidden="true" />;
}
