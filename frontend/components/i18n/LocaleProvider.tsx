"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { NextIntlClientProvider } from "next-intl";
import en from "@/messages/en.json";
import kn from "@/messages/kn.json";

/**
 * Locale plumbing for the console.
 *
 *     Why provider-only, with no [locale] routes and no middleware.
 *     next.config.ts sets `output: "export"`, and a static export supports neither
 *     middleware (proxy) nor cookies -- both of which next-intl's routing setup relies
 *     on. Locale therefore lives in localStorage and is applied through
 *     NextIntlClientProvider directly.
 *
 *     That also happens to be the better fit here: the console is effectively one route
 *     driven by Shell state (auth session, active tab), so navigating to a /kn/ URL to
 *     change language would remount the Shell and throw that state away. Switching
 *     language now re-renders in place and keeps the officer exactly where they were.
 *
 * Kannada is intentionally partial (see messages/kn.json). English is deep-merged
 * underneath it, so any key Kannada does not define renders in English rather than
 * throwing a missing-message error or showing a raw key.
 */

type Locale = "en" | "kn";
const STORAGE_KEY = "ksp_locale";

type Messages = Record<string, unknown>;

/** Deep merge: `override` wins where present, `base` fills every gap. */
function deepMerge(base: Messages, override: Messages): Messages {
  const out: Messages = { ...base };
  for (const [key, value] of Object.entries(override)) {
    const existing = out[key];
    if (
      value && typeof value === "object" && !Array.isArray(value) &&
      existing && typeof existing === "object" && !Array.isArray(existing)
    ) {
      out[key] = deepMerge(existing as Messages, value as Messages);
    } else if (value !== undefined) {
      out[key] = value;
    }
  }
  return out;
}

const MESSAGES: Record<Locale, Messages> = {
  en: en as Messages,
  // English first, Kannada layered on top -> untranslated keys fall back to English.
  kn: deepMerge(en as Messages, kn as Messages),
};

export const LOCALE_LABELS: Record<Locale, string> = {
  en: "English",
  kn: "ಕನ್ನಡ",
};

const LocaleContext = createContext<{
  locale: Locale;
  setLocale: (l: Locale) => void;
  toggleLocale: () => void;
}>({ locale: "en", setLocale: () => {}, toggleLocale: () => {} });

export const useLocale = () => useContext(LocaleContext);

export default function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  // localStorage is unavailable during SSR/prerender, so the stored choice is read
  // post-mount. English is the first paint for everyone; a Kannada user sees one frame
  // of English, which is preferable to disabling prerendering for the whole console.
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "kn" || stored === "en") {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setLocaleState(stored);
    }
  }, []);

  // Keep <html lang> honest for screen readers and for font selection and line-breaking behaviour.
  useEffect(() => {
    document.documentElement.setAttribute("lang", locale);
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Private mode / storage disabled: the choice simply won't persist across reloads.
    }
  }, []);

  const toggleLocale = useCallback(() => {
    setLocale(locale === "en" ? "kn" : "en");
  }, [locale, setLocale]);

  const ctx = useMemo(() => ({ locale, setLocale, toggleLocale }), [locale, setLocale, toggleLocale]);

  return (
    <LocaleContext.Provider value={ctx}>
      <NextIntlClientProvider
        locale={locale}
        messages={MESSAGES[locale] as never}
        timeZone="Asia/Kolkata"
        now={undefined}
      >
        {children}
      </NextIntlClientProvider>
    </LocaleContext.Provider>
  );
}
