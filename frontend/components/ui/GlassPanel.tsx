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

/**
 * Liquid-glass surface — the single primitive behind every card, sidebar,
 * modal, tooltip and dropdown in the console. Models iOS-26 "Liquid Glass":
 *
 *  1. Cursor-reactive highlight — a soft brass specular pool that tracks the
 *     pointer inside the surface (CSS `--gx/--gy`, written in a rAF tick).
 *  2. Depth layering — the `.glass` blur + rim + ambient shadow stack.
 *  3. Hover pop — lift (translateY + scale) with intensified rim/shadow, plus
 *     an optional contextual glass popover (`popover`).
 *  4. Specular sweep — a diagonal light streak that runs once on mount and
 *     again on hover.
 *
 * All pointer work writes CSS variables directly to the node inside
 * requestAnimationFrame — never React state — so movement can't re-render the
 * tree. Everything degrades under prefers-reduced-motion.
 *
 * `Magnetic` (below) provides feature 4's sibling — magnetic micro-movement for
 * buttons/icons. The ambient page spotlight (6) and depth-of-field on inactive
 * siblings (7) live in CursorGlow.tsx and the `.glass-focus` CSS group.
 */

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
  /** Classes for the inner content wrapper (`.glass-body`) — e.g. flex layout. */
  bodyClassName?: string;
  children?: React.ReactNode;
  /** Cursor-reactive specular highlight. Default true. */
  interactive?: boolean;
  /** One-shot diagonal light sweep on mount + hover. Default true. */
  sweep?: boolean;
  /** Hover-pop lift (translateY + scale + rim/shadow intensify). Default false. */
  lift?: boolean;
  /** Tag with data-glass-card so a `.glass-focus` parent can depth-blur siblings. */
  focusCard?: boolean;
  /** Wine (maroon-family) hover accent instead of brass — for AI affordances. */
  tone?: "brass" | "wine";
  /** Contextual glass popover revealed on hover (mini breakdown, description…). */
  popover?: React.ReactNode;
  popoverClassName?: string;
  /** Which side the popover appears on. Default "top". */
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
  popoverPlacement = "top",
  style,
  ...rest
}: GlassPanelProps & MotionExtra) {
  const reduced = useReducedMotion();
  const elRef = useRef<HTMLElement | null>(null);
  const frame = useRef(0);
  const coords = useRef({ x: 50, y: 50 });
  const [sweepId, setSweepId] = useState(0);
  const [hovered, setHovered] = useState(false);

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
    if (popover) setHovered(true);
  }, [interactive, reduced, sweep, popover]);

  const onPointerLeave = useCallback(() => {
    const el = elRef.current;
    if (el) el.style.setProperty("--glow", "0");
    if (popover) setHovered(false);
  }, [popover]);

  const Component = MOTION_TAGS[as] as typeof motion.div;
  const hoverAnim = lift && !reduced ? { y: -3, scale: 1.02 } : undefined;

  return (
    <Component
      // motion refs are compatible with a plain element ref
      ref={elRef as React.Ref<HTMLDivElement>}
      className={`glass ${lift ? "" : ""} ${className}`}
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

      {popover && (
        <AnimatePresence>
          {hovered && (
            <motion.div
              className={`pointer-events-none absolute left-1/2 z-50 w-max max-w-xs -translate-x-1/2 ${
                popoverPlacement === "bottom" ? "top-[calc(100%+10px)]" : "bottom-[calc(100%+10px)]"
              } ${popoverClassName}`}
              initial={reduced ? { opacity: 0 } : { opacity: 0, y: popoverPlacement === "bottom" ? -6 : 6, scale: 0.96 }}
              animate={reduced ? { opacity: 1 } : { opacity: 1, y: 0, scale: 1 }}
              exit={reduced ? { opacity: 0 } : { opacity: 0, y: popoverPlacement === "bottom" ? -4 : 4, scale: 0.97 }}
              transition={{ duration: 0.16, ease: [0.2, 0.9, 0.2, 1] }}
            >
              <div className="glass glass-body rounded-[12px] px-3.5 py-2.5 text-xs shadow-[var(--shadow-pop)]">
                {popover}
              </div>
              {/* arrow */}
              <span
                className={`absolute left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 bg-[var(--color-elevated)] ${
                  popoverPlacement === "bottom"
                    ? "bottom-full translate-y-1/2 border-l border-t border-[var(--glass-border)]"
                    : "top-full -translate-y-1/2 border-b border-r border-[var(--glass-border)]"
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

/** Card preset — hover-pop lift + depth-of-field participation on by default. */
export function GlassCard(props: GlassPanelProps & MotionExtra) {
  return <GlassPanel lift focusCard {...props} />;
}

/**
 * Magnetic micro-movement for buttons/icons. A transparent sensor ring (radius
 * px larger than the child, via padding + negative margin) catches the pointer
 * while it's within ~`radius`px; the inner child then eases `strength`px toward
 * the pointer on a spring — never an instant snap. Springs are Framer motion
 * values, so no React re-render occurs during movement. Inert under
 * prefers-reduced-motion.
 */
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
  const ref = useRef<HTMLDivElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 260, damping: 18, mass: 0.4 });
  const sy = useSpring(y, { stiffness: 260, damping: 18, mass: 0.4 });

  const onMove = useCallback(
    (e: React.PointerEvent) => {
      const el = ref.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const clamp = (v: number) => Math.max(-1, Math.min(1, v));
      x.set(clamp((e.clientX - cx) / (r.width / 2)) * strength);
      y.set(clamp((e.clientY - cy) / (r.height / 2)) * strength);
    },
    [strength, x, y]
  );

  const onLeave = useCallback(() => {
    x.set(0);
    y.set(0);
  }, [x, y]);

  if (reduced) {
    const Tag = as;
    return <Tag className={className}>{children}</Tag>;
  }

  const Wrapper = as === "span" ? motion.span : motion.div;
  return (
    <Wrapper
      ref={ref}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      style={{ x: sx, y: sy, padding: radius, margin: -radius, display: "inline-flex" }}
      className={className}
    >
      {children}
    </Wrapper>
  );
}
