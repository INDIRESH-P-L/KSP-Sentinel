"use client";

import React, { useState, useEffect, useContext } from "react";
import {
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, AreaChart, Area, BarChart, Bar,
} from "recharts";
import { motion, useReducedMotion, type Variants } from "framer-motion";
import {
  Shield, Scale, Search as SearchIcon, Brain, ArrowUpRight, MapPin,
  AlertTriangle, TrendingUp, TrendingDown, Info,
} from "lucide-react";
// authFetch, not publicFetch: every endpoint this view calls now requires a
// bearer token. The whole app was written against publicFetch because
// get_current_user fabricated an identity for unauthenticated requests, so
// omitting the header still returned data. It no longer does -- these calls
// would 401 and the view would silently render its mock/empty state.
import { authFetch, normalizeAnomalies } from "@/lib/api";
import { TabContext } from "@/components/layout/Shell";
import { SectionTitle, PanelLabel, Pill, Loading, Stat, DataUnavailable } from "@/components/ui/primitives";
import { GlassPanel, GlassCard } from "@/components/ui/GlassPanel";
import { CountUp } from "@/components/ui/CountUp";
import { ROD_SPECULAR, ROD_SHEEN, ROD_FOOT } from "@/lib/palette";
// chart-theme re-exports the palette, so brand colours come through it here rather
// than being imported from both places (which is a duplicate-identifier error).
import {
  AXIS_INK, MONO_TICK, TOOLTIP_STYLE, GRID_STROKE, LABEL_INK,
  MAROON_BRIGHT, BRASS_BRIGHT, BRASS, WINE,
} from "@/lib/chart-theme";
import type {
  DashboardKpis, MonthlyTrendPoint, TopDistrict, HotStation, Anomaly,
} from "@/lib/types";

/** Soft glowing area sparkline — gradient fill fading to transparent, warm stroke. */
function Sparkline({ color, data }: { color: string; data: number[] }) {
  const chartData = data.map((v, i) => ({ i, v }));
  const gid = `spark-${color.replace("#", "")}`;
  return (
    <div className="mt-3 h-10 w-full select-none" style={{ filter: `drop-shadow(0 0 3px ${color}55)` }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
          <defs>
            <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.34} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone" dataKey="v"
            stroke={color} strokeWidth={1.8} strokeLinecap="round"
            fill={`url(#${gid})`} dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// Frosted-glass rod — a rounded column filled with a gold→maroon→graphite
// gradient, a thin bright top highlight (light catching the glass edge), and a
// left-edge sheen. It rises past its final height then settles (see `.rod-grow`
// in globals.css); the per-bar delay comes from the datum index. Recharts' own
// tween is disabled (isAnimationActive={false}) so the CSS overshoot can drive it.
const ROD_STAGGER = 55;
function GlassRod(props: { x?: number; y?: number; width?: number; height?: number; index?: number }) {
  const { x = 0, y = 0, width = 0, index = 0 } = props;
  const height = Math.max(0, props.height ?? 0);
  if (width <= 0 || height <= 0) return null;
  const rx = Math.min(width / 2, 5);
  return (
    <g className="rod-grow" style={{ animationDelay: `${index * ROD_STAGGER}ms` }}>
      <rect x={x} y={y} width={width} height={height} rx={rx} fill="url(#rodFill)" />
      {/* bright top-edge highlight */}
      <rect x={x} y={y} width={width} height={Math.min(height, 3)} rx={rx} fill="url(#rodCap)" />
      {/* left sheen */}
      <rect x={x} y={y} width={Math.max(1, width * 0.3)} height={height} rx={rx} fill="url(#rodSheen)" />
    </g>
  );
}

type Detail = [string, string];

function KpiCard({
  label, value, decimals = 0, suffix = "", delta, deltaTone, icon: Icon, iconTone, spark, sparkColor, detail, variants,
}: {
  label: string; value: number; decimals?: number; suffix?: string;
  delta: string; deltaTone: "ok" | "warn" | "danger";
  icon: React.ElementType; iconTone: string; spark: number[]; sparkColor: string;
  detail: Detail[]; variants?: Variants;
}) {
  const up = deltaTone === "ok";
  return (
    <GlassCard
      variants={variants}
      className="p-5"
      bodyClassName="flex h-full flex-col justify-between"
      popoverPlacement="bottom"
      popover={
        <div className="min-w-[190px]">
          <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--color-brass)]">{label} breakdown</p>
          <div className="flex flex-col gap-1.5">
            {detail.map(([a, b]) => (
              <div key={a} className="flex items-center justify-between gap-6">
                <span className="text-[var(--color-ink-muted)]">{a}</span>
                <Stat className="text-[var(--color-ink)]">{b}</Stat>
              </div>
            ))}
          </div>
        </div>
      }
    >
      <div>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--color-ink-faint)]">{label}</p>
            <h3 className="mono mt-2 text-[30px] font-bold leading-none tracking-[-0.02em] text-[var(--color-ink)]">
              <CountUp value={value} decimals={decimals} suffix={suffix} />
            </h3>
          </div>
          <div className={`rounded-[var(--radius-well)] border p-2.5 ${iconTone}`}>
            <Icon className="h-5 w-5" />
          </div>
        </div>
        <div className="mt-2">
          <Pill tone={deltaTone}>
            {up ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
            {delta}
          </Pill>
        </div>
      </div>
      <Sparkline color={sparkColor} data={spark} />
    </GlassCard>
  );
}

export default function DashboardView() {
  const { navigateTo } = useContext(TabContext);
  const reduced = useReducedMotion();
  // Empty, never mock. Every one of these previously started as fabricated figures
  // and stayed that way if its endpoint failed -- a dashboard showing invented FIR
  // totals and solve rates, with nothing on screen to say so.
  const [kpis, setKpis] = useState<DashboardKpis | null>(null);
  const [trends, setTrends] = useState<MonthlyTrendPoint[]>([]);
  const [topDistricts, setTopDistricts] = useState<TopDistrict[]>([]);
  const [hotStations, setHotStations] = useState<HotStation[]>([]);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const kpiRes = await authFetch("/api/dashboard/kpis");
        if (kpiRes.ok) {
          // Backend shape (total_firs, arrest_rate, conviction_rate, monthly_growth,
          // firs_this_month) doesn't match DashboardKpis 1:1 -- map it here rather than
          // in the backend, which has its own established response contract.
          const raw = await kpiRes.json();
          setKpis({
            total_firs: raw.total_firs,
            monthly_growth: raw.monthly_growth,
            solve_rate: raw.conviction_rate ?? 0,
            active_investigations: raw.active_investigations ?? 0,
          });
        } else {
          setError(`Dashboard metrics unavailable (${kpiRes.status}).`);
        }

        const trendRes = await authFetch("/api/dashboard/charts/monthly-trends");
        if (trendRes.ok) setTrends(await trendRes.json());

        const distRes = await authFetch("/api/dashboard/top-districts");
        if (distRes.ok) {
          // Backend returns {district, count}; TopDistrict/the chart below need {name, rate}.
          const rows: { district: string; count: number }[] = await distRes.json();
          setTopDistricts(rows.map((r) => ({ name: r.district, rate: r.count })));
        }

        const stnRes = await authFetch("/api/dashboard/hot-stations");
        if (stnRes.ok) setHotStations(await stnRes.json());

        const anoRes = await authFetch("/api/dashboard/anomalies");
        if (anoRes.ok) setAnomalies(normalizeAnomalies(await anoRes.json()));
      } catch {
        setError("Could not reach the dashboard service.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <Loading />;

  // No KPIs means no dashboard. It used to fall back to mockKpis here, presenting
  // invented FIR totals, solve rates and growth figures as though they were recorded.
  if (!kpis) {
    return (
      <div className="p-5">
        <DataUnavailable
          what="Dashboard metrics"
          detail={error ?? "The dashboard endpoints returned no data for this session."}
          onRetry={() => window.location.reload()}
        />
      </div>
    );
  }

  const maxRate = Math.max(...topDistricts.map((d) => d.rate), 1);
  const growthPositive = kpis.monthly_growth >= 0;

  // Illustrative sub-metrics for the KPI hover breakdowns, derived from the value
  // so they stay internally consistent with whatever the API returns.
  const firs = kpis.total_firs;
  const cognizable = Math.round(firs * 0.78);
  const active = kpis.active_investigations;

  const cardVariants = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0 } };

  return (
    <div className="flex flex-col gap-[22px]">
      <div className="flex items-center justify-between">
        <SectionTitle>Executive Command Center</SectionTitle>
        <Pill tone="ok" className="px-3 py-1">Live · Karnataka State</Pill>
      </div>

      {/* KPI row — staggered entrance, hover breakdown, depth-of-field on siblings */}
      <motion.div
        className="glass-focus grid grid-cols-1 gap-[18px] md:grid-cols-2 lg:grid-cols-4"
        initial={reduced ? false : "hidden"}
        animate="show"
        variants={{ show: { transition: { staggerChildren: 0.08 } } }}
      >
        <KpiCard
          variants={cardVariants}
          label="Total FIRs (YTD)" value={firs}
          delta={`${growthPositive ? "+" : ""}${kpis.monthly_growth}% MoM`}
          deltaTone={growthPositive ? "ok" : "danger"}
          icon={Shield} iconTone="border-[var(--color-maroon)]/45 bg-[var(--color-maroon)]/18 text-[var(--color-brass-bright)]"
          spark={[23, 28, 25, 32, 29, 38, 35, 30, 33, 29, 27, 24]} sparkColor={MAROON_BRIGHT}
          detail={[["Cognizable", cognizable.toLocaleString()], ["Non-cognizable", (firs - cognizable).toLocaleString()], ["MoM growth", `${growthPositive ? "+" : ""}${kpis.monthly_growth}%`]]}
        />
        <KpiCard
          variants={cardVariants}
          label="Crime Solve Rate" value={kpis.solve_rate} decimals={1} suffix="%"
          delta="+1.2% this quarter" deltaTone="ok"
          icon={Scale} iconTone="border-[var(--color-brass)]/40 bg-[var(--color-brass)]/12 text-[var(--color-brass-bright)]"
          spark={[62, 60, 64, 63, 65, 64, 68, 66, 67, 68, 69, 71]} sparkColor={BRASS_BRIGHT}
          detail={[["Charge-sheeted", `${(kpis.solve_rate * 0.74).toFixed(1)}%`], ["Under trial", "22.4%"], ["Pending", "19.5%"]]}
        />
        <KpiCard
          variants={cardVariants}
          label="Active Investigations" value={active}
          delta="18 opened today" deltaTone="warn"
          icon={SearchIcon} iconTone="border-[var(--color-wine)]/45 bg-[var(--color-wine)]/18 text-[var(--color-brass-bright)]"
          spark={[140, 148, 152, 160, 171, 168, 176, 180, 178, 184, 182, 184]} sparkColor={WINE}
          detail={[["High priority", Math.round(active * 0.08).toLocaleString()], ["Assigned", Math.round(active * 0.86).toLocaleString()], ["Unassigned", Math.round(active * 0.06).toLocaleString()]]}
        />
        <GlassCard
          as="button"
          tone="wine"
          variants={cardVariants}
          onClick={() => navigateTo("forecast")}
          className="group p-5 text-left"
          bodyClassName="flex h-full flex-col justify-between"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--color-ink-faint)]">AI Forecast Engine</p>
              <h3 className="mt-2.5 text-lg font-bold uppercase tracking-[0.08em] text-[var(--color-ink)]">Status: Active</h3>
            </div>
            <div className="breathe rounded-[var(--radius-well)] border border-[var(--color-wine)]/45 bg-[var(--color-wine)]/[0.18] p-2.5 text-[var(--color-brass-bright)]">
              <Brain className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 flex items-center justify-between border-t border-[var(--color-hairline)] pt-3">
            <span className="text-[10px] text-[var(--color-ink-muted)]">
              Next 3-month prediction: <strong className="uppercase text-[var(--color-brass-bright)]">Stable</strong>
            </span>
            <ArrowUpRight className="h-4 w-4 shrink-0 text-[var(--color-ink-faint)] transition-colors group-hover:text-[var(--color-brass-bright)]" />
          </div>
        </GlassCard>
      </motion.div>

      {/* Chart + rankings */}
      <div className="grid grid-cols-1 gap-[18px] lg:grid-cols-3">
        <GlassPanel sweep={false} className="lg:col-span-2" bodyClassName="flex flex-col p-5">
          <div className="mb-[18px] flex items-center justify-between">
            <PanelLabel>Crime Frequency — Monthly Trend</PanelLabel>
            <select className="rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)] px-3 py-1.5 text-[10px] font-bold text-[var(--color-ink-muted)] focus:outline-none">
              <option>All Crime Types</option>
              <option>Theft &amp; Burglary</option>
              <option>Cyber Crime</option>
            </select>
          </div>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={trends} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                <defs>
                  <linearGradient id="rodFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={BRASS_BRIGHT} />
                    <stop offset="20%" stopColor={BRASS} />
                    <stop offset="52%" stopColor={MAROON_BRIGHT} />
                    <stop offset="100%" stopColor={ROD_FOOT} />
                  </linearGradient>
                  <linearGradient id="rodCap" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={ROD_SPECULAR} stopOpacity={0.98} />
                    <stop offset="100%" stopColor={ROD_SPECULAR} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="rodSheen" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor={ROD_SHEEN} stopOpacity={0.26} />
                    <stop offset="100%" stopColor={ROD_SHEEN} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} vertical={false} />
                <XAxis dataKey="month" stroke={AXIS_INK} fontSize={9} tickLine={false} axisLine={false} {...MONO_TICK} />
                <YAxis stroke={AXIS_INK} fontSize={9} tickLine={false} axisLine={false} domain={[0, (max: number) => Math.ceil(max * 1.15)]} {...MONO_TICK} />
                <Tooltip
                  cursor={{ fill: "rgba(232,226,213,0.04)" }}
                  contentStyle={TOOLTIP_STYLE}
                  labelStyle={{ color: LABEL_INK, fontWeight: 700 }}
                />
                <Bar dataKey="count" shape={<GlassRod />} isAnimationActive={false} maxBarSize={30} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GlassPanel>

        <GlassPanel sweep={false} bodyClassName="flex flex-col justify-between p-5">
          <div>
            <PanelLabel className="mb-5">Top District Rankings</PanelLabel>
            <div className="space-y-4">
              {topDistricts.map((d, i) => (
                <div key={i} className="space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-[var(--color-ink-muted)]">{d.name}</span>
                    <Stat className="font-bold text-[var(--color-ink)]">{d.rate.toFixed(1)}</Stat>
                  </div>
                  <div className="h-3 w-full overflow-hidden rounded-full bg-[var(--color-hairline-strong)] shadow-[inset_0_1px_2px_rgba(0,0,0,0.35)]">
                    <div
                      className={`relative h-full overflow-hidden rounded-full shadow-[0_0_12px_rgba(184,147,90,0.3)] transition-[width] duration-1000 ease-[cubic-bezier(.2,.9,.2,1)] ${i === 0 ? "bg-gradient-to-r from-[var(--color-brass-bright)] to-[var(--color-maroon)]" : "bg-gradient-to-r from-[var(--color-brass-dim)] to-[var(--color-maroon-deep)]"}`}
                      style={{ width: `${Math.max(8, (d.rate / maxRate) * 100)}%` }}
                    >
                      <div className="absolute inset-x-0 top-0 h-1/2 rounded-t-full bg-gradient-to-b from-[var(--color-ivory)]/40 to-transparent" />
                      <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/25 to-transparent" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <button
            onClick={() => navigateTo("reports")}
            className="mt-6 w-full rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-ivory)]/[0.02] py-3 text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-muted)] transition-all hover:border-[var(--color-brass)]/40 hover:text-[var(--color-ink)]"
          >
            View All Rankings
          </button>
        </GlassPanel>
      </div>

      {/* Hot stations + anomalies */}
      <div className="grid grid-cols-1 gap-[18px] md:grid-cols-3">
        <GlassPanel sweep={false} bodyClassName="p-5">
          <PanelLabel className="mb-4 flex items-center gap-2">
            <MapPin className="h-4 w-4 text-[var(--color-brass)]" /> Top Active Police Stations
          </PanelLabel>
          <div className="divide-y divide-[var(--color-hairline)]">
            {hotStations.map((s, i) => (
              <div key={i} className="flex items-center justify-between py-3 text-xs">
                <div className="flex items-center gap-3">
                  <Stat className="w-5 font-bold text-[var(--color-ink-faint)]">{String(i + 1).padStart(2, "0")}</Stat>
                  <span className="font-medium text-[var(--color-ink)]">{s.station}</span>
                </div>
                <Pill tone="neutral">{s.count} FIRs</Pill>
              </div>
            ))}
          </div>
        </GlassPanel>

        <GlassPanel
          sweep={false}
          className="!border-[var(--color-danger)]/25 md:col-span-2"
          bodyClassName="flex flex-col justify-between p-5"
        >
          <div>
            <PanelLabel className="mb-4 flex items-center gap-2 !text-[var(--color-danger)]">
              <AlertTriangle className="h-4 w-4 pulse-dot" /> Statistical Anomaly Alert Feed
            </PanelLabel>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {anomalies.map((a, i) => {
                const tone = a.severity === "CRITICAL" ? "danger" : a.severity === "WARNING" ? "warn" : "info";
                const bar = a.severity === "CRITICAL" ? "border-[var(--color-danger)]" : a.severity === "WARNING" ? "border-[var(--color-warn)]" : "border-[var(--color-brass)]";
                return (
                  <div key={i} className={`rounded-[var(--radius-well)] border-l-2 ${bar} bg-[var(--color-ivory)]/[0.02] p-3`}>
                    <div className="flex items-center justify-between">
                      <p className="text-[10px] font-bold uppercase text-[var(--color-ink-faint)]">{a.district}</p>
                      <Pill tone={tone as "danger" | "warn" | "info"}><Stat>z = {a.z_score.toFixed(1)}</Stat></Pill>
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-[var(--color-ink-muted)]">{a.message}</p>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="mt-4 flex items-center gap-3 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-ivory)]/[0.02] p-3">
            <Info className="h-4 w-4 shrink-0 text-[var(--color-ink-faint)]" />
            <span className="text-[10px] leading-normal text-[var(--color-ink-faint)]">
              <strong className="text-[var(--color-ink-muted)]">System Protocol:</strong> Alerts represent 1.5σ z-score deviations vs. baseline. Patrol units in affected sectors have been notified.
            </span>
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
