"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Radar, RefreshCw, MapPin, Gauge as GaugeIcon, TrendingUp, AlertTriangle } from "lucide-react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
// authFetch, not publicFetch: series analysis reads operational crime data.
import { authFetch } from "@/lib/api";
import { SectionTitle, PanelLabel, Pill, Loading } from "@/components/ui/primitives";
import { GlassPanel } from "@/components/ui/GlassPanel";
import SeriesMap from "@/components/map/SeriesMap";
import type { CrimeSeries, SeriesResponse } from "@/lib/types";

/**
 * Serial runs: which linked sets of offences form a series, and where each may continue.
 *
 * The layout follows how the question is actually asked. A supervisor allocating tonight's
 * patrols wants the answer first — is anything due, and where — so the forecast leads.
 * The evidence behind it (cadence, track fit, member cases) sits underneath for the
 * officer who has to justify acting on it, which is a different reader with a different
 * need. Neither is a footnote to the other.
 */

const STATE_TONE = {
  overdue: { tone: "danger" as const, label: "Overdue" },
  due_now: { tone: "danger" as const, label: "Window open" },
  upcoming: { tone: "warn" as const, label: "Upcoming" },
};

const TEMPO_COPY: Record<string, string> = {
  accelerating: "Offences are coming faster than earlier in the run",
  slowing: "Offences are spacing out compared with earlier in the run",
  steady: "Interval between offences is holding",
  unknown: "Not enough intervals to judge",
};

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined,
    { day: "numeric", month: "short", year: "numeric" });
}

function signatureText(sig: Record<string, string>) {
  const parts: string[] = [];
  if (sig.entry_method) parts.push(sig.entry_method.replace(/_/g, " "));
  if (sig.weapon_used) parts.push(sig.weapon_used);
  if (sig.time_of_day_pattern) parts.push(sig.time_of_day_pattern);
  if (sig.target_type) parts.push(sig.target_type);
  return parts.length ? parts.join(" · ") : "no shared MO fields";
}

export default function SeriesView() {
  const [data, setData] = useState<SeriesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const reduced = Boolean(useReducedMotion());

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await authFetch("/api/intelligence/series");
        if (!res.ok) throw new Error(`Series analysis unavailable (${res.status})`);
        const json: SeriesResponse = await res.json();
        if (cancelled) return;
        setData(json);
        setSelectedId((prev) =>
          prev && json.series.some((s) => s.series_id === prev)
            ? prev
            : json.series[0]?.series_id ?? null);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not load series.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [reload]);

  const selected = useMemo(
    () => data?.series.find((s) => s.series_id === selectedId) ?? null,
    [data, selectedId]);

  const rebuild = useCallback(async () => {
    setLoading(true);
    // Re-derives the MO match graph the series analysis reads. Without this a newly
    // registered case cannot join a run until the nightly job fires.
    await authFetch("/api/intelligence/mo-matches/run", { method: "POST" }).catch(() => {});
    setReload((r) => r + 1);
  }, []);

  if (loading && !data) return <Loading label="Assembling serial runs…" />;

  if (error) {
    return (
      <div className="p-6">
        <GlassPanel className="p-6">
          <p className="text-sm text-[var(--color-danger-text)]">{error}</p>
        </GlassPanel>
      </div>
    );
  }

  const series = data?.series ?? [];
  const active = series.filter((s) => s.forecast &&
    (s.forecast.state === "overdue" || s.forecast.state === "due_now")).length;

  return (
    <div className="flex flex-col gap-5 p-5">
      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <SectionTitle>Serial Runs</SectionTitle>
          <p className="mt-1 max-w-2xl text-sm text-[var(--color-ink-muted)]">
            Linked cases assembled into runs, each profiled for cadence and direction of
            travel. A forecast is issued only where the pattern supports one.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {active > 0 && (
            <Pill tone="danger">
              {active} run{active === 1 ? "" : "s"} due or overdue
            </Pill>
          )}
          <button
            type="button"
            onClick={rebuild}
            disabled={loading}
            className="flex items-center gap-2 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)] px-3 py-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-brass-bright)] transition-colors hover:border-[var(--color-brass)]/40 hover:bg-[var(--color-elevated)] disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "spin" : ""}`} />
            Re-scan
          </button>
        </div>
      </div>

      {series.length === 0 ? (
        <GlassPanel className="p-8 text-center">
          <Radar className="mx-auto mb-3 h-8 w-8 text-[var(--color-ink-faint)]" />
          <p className="text-sm text-[var(--color-ink-muted)]">
            No connected set of MO matches reached the minimum size for a run.
          </p>
          <p className="mt-1 text-xs text-[var(--color-ink-faint)]">
            Two linked cases are a pair, not a series. Re-scan after new cases are registered.
          </p>
        </GlassPanel>
      ) : (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
          {/* ── Run list ──────────────────────────────────────────────────── */}
          <div className="flex flex-col gap-3">
            <PanelLabel>Detected runs</PanelLabel>
            {series.map((s) => {
              const isSel = s.series_id === selectedId;
              const st = s.forecast ? STATE_TONE[s.forecast.state] : null;
              return (
                <button
                  key={s.series_id}
                  type="button"
                  onClick={() => setSelectedId(s.series_id)}
                  aria-pressed={isSel}
                  className={`rounded-[var(--radius-well)] border p-4 text-left transition-colors ${
                    isSel
                      ? "border-[var(--color-brass)]/50 bg-[var(--color-elevated)]"
                      : "border-[var(--color-hairline)] bg-[var(--color-surface)] hover:border-[var(--color-brass)]/30"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="mono text-xs text-[var(--color-brass-bright)]">
                      {s.series_id}
                    </span>
                    {st && <Pill tone={st.tone}>{st.label}</Pill>}
                  </div>
                  <p className="mt-2 text-sm font-semibold text-[var(--color-ink)]">
                    {s.case_count} cases · {s.district_count} districts
                  </p>
                  <p className="mt-1 truncate text-xs text-[var(--color-ink-faint)]">
                    {signatureText(s.signature)}
                  </p>
                  <div className="mt-2.5 flex items-center gap-2">
                    <div className="h-1 flex-1 overflow-hidden rounded-full bg-[var(--color-surface-2)]">
                      <div
                        className="h-full rounded-full bg-[var(--color-brass)]"
                        style={{ width: `${Math.round(s.confidence * 100)}%` }}
                      />
                    </div>
                    <span className="mono text-[10px] text-[var(--color-ink-faint)]">
                      {Math.round(s.confidence * 100)}%
                    </span>
                  </div>
                </button>
              );
            })}
          </div>

          {/* ── Detail ────────────────────────────────────────────────────── */}
          <div className="flex flex-col gap-5">
            <AnimatePresence mode="wait">
              {selected && (
                <motion.div
                  key={selected.series_id}
                  initial={reduced ? { opacity: 0 } : { opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="flex flex-col gap-5"
                >
                  {/* Forecast — the answer, first */}
                  {selected.forecast ? (
                    <GlassPanel className="p-5">
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                          <PanelLabel>Forecast window</PanelLabel>
                          <p className="mt-1.5 text-lg font-semibold text-[var(--color-ink)]">
                            {fmtDate(selected.forecast.window_start)} — {fmtDate(selected.forecast.window_end)}
                          </p>
                          <p className="mt-1 text-xs text-[var(--color-ink-faint)]">
                            ±{selected.forecast.window_half_width_days} days around the
                            expected interval
                            {selected.forecast.state === "upcoming" &&
                              ` · opens in ${selected.forecast.days_until_window} days`}
                            {selected.forecast.state === "overdue" &&
                              ` · ${selected.forecast.overdue_days} days past`}
                          </p>
                        </div>
                        <div className="text-right">
                          <PanelLabel>Search area</PanelLabel>
                          <p className="mono mt-1.5 text-lg font-semibold text-[var(--color-brass-bright)]">
                            {selected.forecast.search_radius_km} km
                          </p>
                          <p className="text-xs text-[var(--color-ink-faint)]">radius</p>
                        </div>
                      </div>
                      <p className="mt-3 border-t border-[var(--color-hairline)] pt-3 text-xs text-[var(--color-ink-muted)]">
                        <MapPin className="mr-1 inline h-3 w-3 align-[-1px]" />
                        {selected.forecast.basis}
                      </p>
                    </GlassPanel>
                  ) : (
                    <GlassPanel className="p-5">
                      <div className="flex items-start gap-3">
                        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-warn-text)]" />
                        <div>
                          <PanelLabel>No forecast issued</PanelLabel>
                          <p className="mt-1.5 text-sm text-[var(--color-ink-muted)]">
                            {selected.forecast_withheld_reason}
                          </p>
                        </div>
                      </div>
                    </GlassPanel>
                  )}

                  {/* Map */}
                  <GlassPanel className="overflow-hidden p-0">
                    <div className="h-[380px] w-full">
                      <SeriesMap series={selected} />
                    </div>
                    <p className="border-t border-[var(--color-hairline)] px-4 py-2 text-[10px] text-[var(--color-ink-faint)]">
                      Numbered markers follow the offence sequence; the dashed ring is the
                      forecast search area, not a location.
                    </p>
                  </GlassPanel>

                  {/* Evidence behind the forecast */}
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <GlassPanel className="p-4">
                      <PanelLabel>Cadence</PanelLabel>
                      <p className="mono mt-1.5 text-2xl font-semibold text-[var(--color-ink)]">
                        {selected.temporal.cadence_days ?? "—"}
                        <span className="ml-1 text-sm text-[var(--color-ink-faint)]">days</span>
                      </p>
                      <p className="mt-1 text-xs text-[var(--color-ink-faint)]">
                        ±{selected.temporal.irregularity_days} typical variation
                      </p>
                      <div className="mt-2 flex items-center gap-1.5">
                        <TrendingUp className="h-3 w-3 text-[var(--color-brass)]" />
                        <span className="text-xs text-[var(--color-ink-muted)]">
                          {TEMPO_COPY[selected.temporal.tempo]}
                        </span>
                      </div>
                    </GlassPanel>

                    <GlassPanel className="p-4">
                      <PanelLabel>Track</PanelLabel>
                      {selected.spatial.drift?.significant ? (
                        <>
                          <p className="mono mt-1.5 text-2xl font-semibold text-[var(--color-ink)]">
                            {selected.spatial.drift.speed_km_per_day}
                            <span className="ml-1 text-sm text-[var(--color-ink-faint)]">km/day</span>
                          </p>
                          <p className="mt-1 text-xs text-[var(--color-ink-faint)]">
                            travelling · fit R²={selected.spatial.drift.fit_r2}
                          </p>
                          <p className="mt-2 text-xs text-[var(--color-ink-muted)]">
                            Offences sit within {selected.spatial.drift.track_scatter_km} km of
                            the fitted track, across {selected.spatial.centroid_radius_km} km of ground.
                          </p>
                        </>
                      ) : (
                        <>
                          <p className="mt-1.5 text-2xl font-semibold text-[var(--color-ink)]">
                            Stationary
                          </p>
                          <p className="mt-1 text-xs text-[var(--color-ink-faint)]">
                            no significant direction of travel
                          </p>
                          <p className="mt-2 text-xs text-[var(--color-ink-muted)]">
                            Clustered within {selected.spatial.radius_km} km.
                          </p>
                        </>
                      )}
                    </GlassPanel>

                    <GlassPanel className="p-4">
                      <PanelLabel>Confidence</PanelLabel>
                      <p className="mono mt-1.5 text-2xl font-semibold text-[var(--color-brass-bright)]">
                        {Math.round(selected.confidence * 100)}%
                      </p>
                      <p className="mt-1 text-xs text-[var(--color-ink-faint)]">
                        from {selected.case_count} cases · regularity{" "}
                        {Math.round(selected.temporal.regularity * 100)}%
                      </p>
                      <p className="mt-2 text-xs text-[var(--color-ink-muted)]">
                        Run spans {selected.span_days} days from{" "}
                        {fmtDate(selected.first_offence)}.
                      </p>
                    </GlassPanel>
                  </div>

                  {/* Member cases */}
                  <GlassPanel className="p-5">
                    <PanelLabel>Cases in this run</PanelLabel>
                    <div className="mt-3 overflow-x-auto">
                      <table className="w-full min-w-[560px] text-sm">
                        <thead>
                          <tr className="border-b border-[var(--color-hairline)] text-left">
                            {["#", "FIR", "Date", "District", "Station", "Status"].map((h) => (
                              <th key={h} className="pb-2 pr-3 text-[10px] font-semibold uppercase tracking-wider text-[var(--color-ink-faint)]">
                                {h}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {selected.members.map((m, i) => (
                            <tr key={m.fir_id} className="border-b border-[var(--color-hairline)]/50">
                              <td className="mono py-2 pr-3 text-xs text-[var(--color-brass)]">{i + 1}</td>
                              <td className="mono py-2 pr-3 text-xs text-[var(--color-ink)]">{m.fir_number}</td>
                              <td className="mono py-2 pr-3 text-xs tabular-nums text-[var(--color-ink-muted)]">
                                {fmtDate(m.date)}
                              </td>
                              <td className="py-2 pr-3 text-xs text-[var(--color-ink-muted)]">{m.district_name ?? "—"}</td>
                              <td className="py-2 pr-3 text-xs text-[var(--color-ink-faint)]">{m.station ?? "—"}</td>
                              <td className="py-2 pr-3 text-xs text-[var(--color-ink-faint)]">{m.status}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </GlassPanel>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      )}

      {/* Advisory — always visible, never collapsed. */}
      {data?.advisory && (
        <div className="rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)] p-4">
          <div className="flex items-start gap-2.5">
            <GaugeIcon className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--color-ink-faint)]" />
            <p className="text-xs leading-relaxed text-[var(--color-ink-faint)]">
              {data.advisory}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
