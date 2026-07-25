"use client";

import { useEffect, useRef } from "react";
import { animate, useReducedMotion } from "framer-motion";

/**
 * Count-up figure — eases from 0 to `value` on mount, writing the formatted
 * number straight to the DOM node inside Framer's animation loop (no React state
 * per frame). Set instantly under prefers-reduced-motion.
 */
export function CountUp({
  value,
  decimals = 0,
  duration = 1.1,
  prefix = "",
  suffix = "",
  locale = true,
  className = "",
  style,
}: {
  value: number;
  decimals?: number;
  duration?: number;
  prefix?: string;
  suffix?: string;
  locale?: boolean;
  className?: string;
  style?: React.CSSProperties;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduced = useReducedMotion();

  const fmt = (n: number) => {
    let s: string;
    if (decimals > 0) {
      s = n.toFixed(decimals);
      if (locale) {
        const [i, d] = s.split(".");
        s = `${Number(i).toLocaleString()}.${d}`;
      }
    } else {
      s = locale ? Math.round(n).toLocaleString() : String(Math.round(n));
    }
    return `${prefix}${s}${suffix}`;
  };

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reduced) {
      el.textContent = fmt(value);
      return;
    }
    const controls = animate(0, value, {
      duration,
      ease: [0.2, 0.8, 0.2, 1],
      onUpdate: (v) => {
        el.textContent = fmt(v);
      },
    });
    return () => controls.stop();
    // fmt closes over the format props; re-run if any change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, reduced, decimals, duration, prefix, suffix, locale]);

  return (
    <span ref={ref} className={className} style={style}>
      {fmt(reduced ? value : 0)}
    </span>
  );
}
