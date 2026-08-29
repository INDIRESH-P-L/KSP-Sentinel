"use client";

import React, { useEffect, useMemo, useState } from "react";
import { OK, WARN, DANGER } from "@/lib/palette";
import dynamic from "next/dynamic";
import { ShieldAlert, Search, TrendingUp, TrendingDown, Minus, Info, Phone, MapPin } from "lucide-react";
import { useTranslations } from "next-intl";
import { API_BASE } from "@/lib/api";
import LanguageToggle from "@/components/i18n/LanguageToggle";
import { GlassPanel, GlassCard } from "@/components/ui/GlassPanel";
import type { PublicDistrict } from "@/components/public/PublicSafetyMap";

/**
 * Public safety page — /public/safety
 *
 * Sits OUTSIDE the (app) route group, so it never mounts the authenticated Shell: no
 * sidebar, no internal navigation, no login. It still renders under the root layout, so
 * it inherits the same design system the console uses — glass panels, the Karnataka
 * palette and the emblem watermark behind everything.
 *
 * Data comes from GET /api/public/district-safety with a plain fetch, deliberately NOT
 * authFetch: this page must work for someone with no token, and pulling in the auth
 * wrapper would risk a 401 redirect on a page that has no login to redirect to.
 */

const PublicSafetyMap = dynamic(() => import("@/components/public/PublicSafetyMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full items-center justify-center text-xs text-[var(--color-ink-faint)]">
      Loading map…
    </div>
  ),
});

type Payload = {
  data_period: string;
  data_as_of: string;
  district_count: number;
  methodology: string;
  disclaimer: string;
  categories: string[];
  districts: PublicDistrict[];
};

const BAND_STYLE: Record<string, { dot: string; text: string; chip: string }> = {
  Low: { dot: OK, text: "text-[var(--color-ok-text)]", chip: "border-[var(--color-ok)]/40 bg-[var(--color-ok)]/10 text-[var(--color-ok-text)]" },
  Medium: { dot: WARN, text: "text-[var(--color-warn-text)]", chip: "border-[var(--color-warn)]/40 bg-[var(--color-warn)]/10 text-[var(--color-warn-text)]" },
  High: { dot: DANGER, text: "text-[var(--color-danger-text)]", chip: "border-[var(--color-danger)]/40 bg-[var(--color-danger)]/10 text-[var(--color-danger-text)]" },
};

function TrendIcon({ trend }: { trend: string }) {
  if (trend === "rising") return <TrendingUp className="h-3.5 w-3.5 text-[var(--color-danger-text)]" />;
  if (trend === "falling") return <TrendingDown className="h-3.5 w-3.5 text-[var(--color-ok-text)]" />;
  return <Minus className="h-3.5 w-3.5 text-[var(--color-ink-faint)]" />;
}

export default function PublicSafetyPage() {
  const t = useTranslations("publicSafety");
  const tBrand = useTranslations("brand");
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [band, setBand] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    // The page is public, so the emblem watermark shows its larger "hero" treatment,
    // the same flag the login screen sets.
    document.documentElement.setAttribute("data-authed", "false");
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/public/district-safety`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setData(await res.json());
      } catch {
        setError(t("unavailable"));
      }
    })();
  }, []);

  const districts = useMemo(() => {
    if (!data) return [];
    const q = query.trim().toLowerCase();
    return data.districts.filter(
      (d) => (!band || d.safety_category === band) && (!q || d.district_name.toLowerCase().includes(q))
    );
  }, [data, query, band]);

  const counts = useMemo(() => {
    const out: Record<string, number> = { Low: 0, Medium: 0, High: 0 };
    data?.districts.forEach((d) => { out[d.safety_category] = (out[d.safety_category] ?? 0) + 1; });
    return out;
  }, [data]);

  return (
    <div className="mx-auto max-w-6xl px-5 py-10 md:px-8">
      {/* ---------- Header ---------- */}
      <header className="mb-6 flex flex-wrap items-center justify-between gap-5">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-[var(--color-brass)]/40 bg-[var(--color-maroon)]/25 text-[var(--color-brass-bright)] shadow-[0_0_28px_rgba(194,161,100,0.25)]">
            <ShieldAlert className="h-7 w-7" />
          </div>
          <div>
            <p className="mono text-[10px] font-bold uppercase tracking-[0.28em] text-[var(--color-brass)]">
              {tBrand("org")}
            </p>
            <h1 className="text-[26px] font-extrabold uppercase leading-none tracking-tight text-[var(--color-ink)]">
              {t("title")}
            </h1>
            <p className="mt-1.5 text-sm text-[var(--color-ink-muted)]">
              {data ? t("subtitle", { period: data.data_period }) : "…"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
        <LanguageToggle />
        <a
          href="tel:112"
          className="flex items-center gap-2.5 rounded-full border border-[var(--color-danger)]/45 bg-[var(--color-danger)]/12 px-5 py-2.5 text-sm font-bold text-[var(--color-danger-text)] transition-colors hover:bg-[var(--color-danger)]/20"
        >
          <Phone className="h-4 w-4" /> {t("emergency")}
        </a>
        </div>
      </header>

      {/* ---------- Disclaimer: first thing, not buried ---------- */}
      <GlassPanel sweep={false} className="mb-6 !border-[var(--color-warn)]/25" bodyClassName="flex items-start gap-3 p-4">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-warn)]" />
        <p className="text-xs leading-relaxed text-[var(--color-ink-muted)]">
          {data?.disclaimer ??
            "General guidance compiled from historical police records. This is not a live emergency service — dial 112 in an emergency."}
        </p>
      </GlassPanel>

      {error && (
        <GlassPanel sweep={false} className="mb-6 !border-[var(--color-danger)]/30" bodyClassName="p-4">
          <p className="text-sm text-[var(--color-danger-text)]">{error}</p>
        </GlassPanel>
      )}

      {/* ---------- Legend + filters ---------- */}
      <GlassPanel sweep={false} className="mb-5" bodyClassName="flex flex-wrap items-center gap-3 p-4">
        <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-[var(--color-ink-faint)]">
          {t("safetyLevel")}
        </span>
        {["Low", "Medium", "High"].map((b) => {
          const active = band === b;
          return (
            <button
              key={b}
              onClick={() => setBand(active ? null : b)}
              className={`flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs font-semibold transition-all ${
                active ? BAND_STYLE[b].chip : "border-[var(--color-hairline)] text-[var(--color-ink-muted)] hover:border-[var(--color-hairline-strong)]"
              }`}
            >
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: BAND_STYLE[b].dot }} />
              {t(`band${b}` as never)}
              <span className="mono text-[10px] opacity-70">{counts[b] ?? 0}</span>
            </button>
          );
        })}
        <div className="ml-auto flex min-w-[210px] flex-1 items-center gap-2 rounded-full border border-[var(--color-hairline)] bg-[var(--color-ivory)]/[0.03] px-4 py-2 md:max-w-xs">
          <Search className="h-3.5 w-3.5 shrink-0 text-[var(--color-ink-faint)]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("findDistrict")}
            aria-label="Find your district"
            className="w-full bg-transparent text-xs text-[var(--color-ink)] placeholder-[var(--color-ink-faint)] focus:outline-none"
          />
        </div>
      </GlassPanel>

      {/* ---------- Map ---------- */}
      <GlassPanel sweep={false} className="mb-5 overflow-hidden p-2">
        <div className="h-[380px] w-full overflow-hidden rounded-[var(--radius-well)]">
          {data ? (
            <PublicSafetyMap districts={data.districts} selected={selected} onSelect={setSelected} />
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-[var(--color-ink-faint)]">
              {t("loadingMap")}
            </div>
          )}
        </div>
      </GlassPanel>

      {/* ---------- District cards ---------- */}
      <div className="glass-focus grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {districts.map((d) => {
          const s = BAND_STYLE[d.safety_category];
          return (
            <GlassCard
              key={d.district_name}
              as="button"
              onClick={() => setSelected(d.district_name === selected ? null : d.district_name)}
              className={`p-5 text-left ${selected === d.district_name ? "!border-[var(--color-brass)]/50" : ""}`}
              bodyClassName="flex h-full flex-col"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-bold uppercase tracking-wide text-[var(--color-ink)]">
                    {d.district_name}
                  </h3>
                  <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-[var(--color-ink-faint)]">
                    <TrendIcon trend={d.trend} />
                    <span>{t(`trend${d.trend.charAt(0).toUpperCase()}${d.trend.slice(1)}` as never)}</span>
                  </div>
                </div>
                <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase ${s.chip}`}>
                  {t(`band${d.safety_category}` as never)}
                </span>
              </div>
              <ul className="mt-3 flex flex-col gap-1.5 border-t border-[var(--color-hairline)] pt-3">
                {d.safety_tips.slice(0, 3).map((tip) => (
                  <li key={tip} className="flex gap-2 text-[11px] leading-snug text-[var(--color-ink-muted)]">
                    <span className="mt-1 h-1 w-1 shrink-0 rounded-full" style={{ background: s.dot }} />
                    {tip}
                  </li>
                ))}
              </ul>
            </GlassCard>
          );
        })}
      </div>

      {districts.length === 0 && data && (
        <p className="py-10 text-center text-sm text-[var(--color-ink-faint)]">
          {t("noMatch")}
        </p>
      )}

      {/* ---------- Footer ---------- */}
      <footer className="mt-10 border-t border-[var(--color-hairline)] pt-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <p className="max-w-2xl text-[11px] leading-relaxed text-[var(--color-ink-faint)]">
            {data?.methodology}
          </p>
          <div className="flex flex-col gap-1 text-[11px] text-[var(--color-ink-faint)]">
            <span className="flex items-center gap-1.5"><Phone className="h-3 w-3" /> {t("emergency")}</span>
            <span className="flex items-center gap-1.5"><Phone className="h-3 w-3" /> {t("cyberFraud")}</span>
            <span className="flex items-center gap-1.5"><MapPin className="h-3 w-3" /> {t("dataAsOf", { date: data?.data_as_of ?? "—" })}</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
