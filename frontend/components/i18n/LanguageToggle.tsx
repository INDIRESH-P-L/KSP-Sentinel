"use client";

import React from "react";
import { Languages } from "lucide-react";
import { useLocale, LOCALE_LABELS } from "@/components/i18n/LocaleProvider";
import { Magnetic } from "@/components/ui/GlassPanel";

/**
 * Two-language switch for the topbar.
 *
 * A single toggle rather than a dropdown: with exactly two languages a menu is one
 * extra click for no benefit. The label always shows the language you would switch TO,
 * so the control states its outcome rather than its current state.
 *
 * Styled from the same tokens as the rest of the chrome — no new palette, no new
 * primitives.
 */
export default function LanguageToggle({ compact = false }: { compact?: boolean }) {
  const { locale, toggleLocale } = useLocale();
  const next = locale === "en" ? "kn" : "en";

  return (
    <Magnetic radius={8}>
      <button
        onClick={toggleLocale}
        title={`${LOCALE_LABELS[locale]} → ${LOCALE_LABELS[next]}`}
        aria-label={`Switch language to ${LOCALE_LABELS[next]}`}
        className="flex items-center gap-2 rounded-full border border-[var(--color-hairline)] px-3 py-1.5 text-[11px] font-semibold text-[var(--color-ink-muted)] transition-colors hover:border-[var(--color-brass)]/40 hover:text-[var(--color-ink)]"
      >
        <Languages className="h-3.5 w-3.5 shrink-0 text-[var(--color-brass)]" />
        {!compact && <span>{LOCALE_LABELS[next]}</span>}
      </button>
    </Magnetic>
  );
}
