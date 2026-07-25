"use client";

import React, { useCallback, useRef, useState } from "react";
import {
  motion,
  AnimatePresence,
  useReducedMotion,
  useMotionValue,
  useSpring,
  type HTMLMotionProps,
} from "framer-motion";

type Tag = "div" | "button" | "a" | "section" | "li" | "aside" | "header" | "nav" | "article";

const MOTION_TAGS = {
  div: motion.div,
  button: motion.button,
  a: motion.a,
  section: motion.section,
  li: motion.li,
  aside: motion.aside,
  header: motion.header,
  nav: motion.nav,
  article: motion.article,
} as const;

export interface GlassPanelProps {
  as?: Tag;
  className?: string;
  bodyClassName?: string;
  children?: React.ReactNode;
  interactive?: boolean;
  sweep?: boolean;
  lift?: boolean;
  focusCard?: boolean;
  tone?: "brass" | "wine";
  popover?: React.ReactNode;
  popoverClassName?: string;
  popoverPlacement?: "top" | "bottom";
  style?: React.CSSProperties;
}

type MotionExtra = Omit<
  HTMLMotionProps<"div">,
  keyof GlassPanelProps | "ref"
>;

export function GlassPanel({
  as = "div",
  className = "",
  bodyClassName = "",
  children,
  interactive = true,
  sweep = true,
  lift = false,
  focusCard = lift,
  tone = "brass",
  popover,
  popoverClassName = "",
  popoverPlacement = "bottom",
  style,
  ...rest
}: GlassPanelProps & MotionExtra) {
  const reduced = useReducedMotion();
  const elRef = useRef<HTMLElement | null>(null);
  const frame = useRef(0);
  const coords = useRef({ x: 50, y: 50 });
  const [sweepId, setSweepId] = useState(0);
  const [hovered, setHovered] = useState(false);
  const [popoverPos, setPopoverPos] = useState<{ top: number; left: number } | null>(null);

  const paint = useCallback(() => {
    frame.current = 0;
    const el = elRef.current;
    if (!el) return;
    el.style.setProperty("--gx", `${coords.current.x}%`);
    el.style.setProperty("--gy", `${coords.current.y}%`);
  }, []);

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (reduced || !interactive) return;
      const el = elRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      coords.current = {
        x: ((e.clientX - r.left) / r.width) * 100,
        y: ((e.clientY - r.top) / r.height) * 100,
      };
      if (!frame.current) frame.current = requestAnimationFrame(paint);
    },
    [reduced, interactive, paint]
  );

  const onPointerEnter = useCallback(() => {
    const el = elRef.current;
    if (el && interactive && !reduced) el.style.setProperty("--glow", "1");
    if (!reduced && sweep) setSweepId((n) => n + 1);
    if (popover && el) {
      const rect = el.getBoundingClientRect();
      setPopoverPos({
        top: popoverPlacement === "bottom" ? rect.bottom + 8 : rect.top - 8,
        left: rect.left + rect.width / 2,
      });
      setHovered(true);
    }
  }, [interactive, reduced, sweep, popover, popoverPlacement]);

  const onPointerLeave = useCallback(() => {
    const el = elRef.current;
    if (el) el.style.setProperty("--glow", "0");
    if (popover) setHovered(false);
  }, [popover]);

  const Component = MOTION_TAGS[as] as typeof motion.div;
  const hoverAnim = lift && !reduced ? { y: -3, scale: 1.02 } : undefined;

  return (
    <Component
      ref={elRef as React.Ref<HTMLDivElement>}
      className={`glass ${className}`}
      data-glass-lift={lift ? "" : undefined}
      data-glass-card={focusCard ? "" : undefined}
      data-tone={tone === "wine" ? "wine" : undefined}
      style={style}
      onPointerMove={onPointerMove}
      onPointerEnter={onPointerEnter}
      onPointerLeave={onPointerLeave}
      whileHover={hoverAnim}
      transition={{ type: "spring", stiffness: 380, damping: 26, mass: 0.6 }}
      {...rest}
    >
      {(interactive || sweep) && !reduced && (
        <span className="glass-clip" aria-hidden="true">
          {interactive && <span className="glass-spec" />}
          {sweep && <span key={sweepId} className="glass-sweep glass-sweep-run" />}
        </span>
      )}
      <div className={`glass-body ${bodyClassName}`}>{children}</div>

      {popover && popoverPos && (
        <AnimatePresence>
          {hovered && (
            <motion.div
              className={`pointer-events-none fixed z-[9999] w-max max-w-xs ${popoverClassName}`}
              style={{
                top: popoverPos.top,
                left: popoverPos.left,
                transform: popoverPlacement === "bottom" ? "translateX(-50%)" : "translate(-50%, -100%)",
              }}
              initial={reduced ? { opacity: 0 } : { opacity: 0, y: popoverPlacement === "bottom" ? -6 : 6, scale: 0.96 }}
              animate={reduced ? { opacity: 1 } : { opacity: 1, y: 0, scale: 1 }}
              exit={reduced ? { opacity: 0 } : { opacity: 0, y: popoverPlacement === "bottom" ? -4 : 4, scale: 0.97 }}
              transition={{ duration: 0.16, ease: [0.2, 0.9, 0.2, 1] }}
            >
              <div className="glass rounded-[12px] border border-[var(--color-brass)]/40 bg-[var(--color-surface-elevated)] p-3 text-xs text-[var(--color-ink)] shadow-2xl shadow-black/60 backdrop-blur-xl">
                {popover}
              </div>
              <span
                className={`absolute left-1/2 h-2.5 w-2.5 -translate-x-1/2 rotate-45 border-[var(--color-brass)]/40 bg-[var(--color-surface-elevated)] ${
                  popoverPlacement === "bottom"
                    ? "bottom-full translate-y-1/2 border-l border-t"
                    : "top-full -translate-y-1/2 border-b border-r"
                }`}
                aria-hidden="true"
              />
            </motion.div>
          )}
        </AnimatePresence>
      )}
    </Component>
  );
}

export function GlassCard(props: GlassPanelProps & MotionExtra) {
  return <GlassPanel lift focusCard {...props} />;
}

export function Magnetic({
  children,
  strength = 3,
  radius = 20,
  className = "",
  as = "div",
}: {
  children: React.ReactNode;
  strength?: number;
  radius?: number;
  className?: string;
  as?: "div" | "span";
}) {
  const reduced = useReducedMotion();
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const springX = useSpring(x, { stiffness: 350, damping: 22, mass: 0.5 });
  const springY = useSpring(y, { stiffness: 350, damping: 22, mass: 0.5 });

  const onPointerMove = (e: React.PointerEvent<HTMLElement>) => {
    if (reduced) return;
    const r = e.currentTarget.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const cy = r.top + r.height / 2;
    const dx = e.clientX - cx;
    const dy = e.clientY - cy;
    const dist = Math.hypot(dx, dy);
    const maxR = Math.max(r.width, r.height) / 2 + radius;
    if (dist <= maxR) {
      const pull = Math.sin((1 - dist / maxR) * (Math.PI / 2));
      x.set(dx * (strength / (maxR || 1)) * pull);
      y.set(dy * (strength / (maxR || 1)) * pull);
    }
  };

  const onPointerLeave = () => {
    x.set(0);
    y.set(0);
  };

  const Tag = as === "span" ? motion.span : motion.div;

  return (
    <Tag
      className={`inline-block ${className}`}
      onPointerMove={onPointerMove}
      onPointerLeave={onPointerLeave}
      style={{ x: springX, y: springY }}
    >
      {children}
    </Tag>
  );
}
