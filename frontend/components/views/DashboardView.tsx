"use client";

import React, { useState, useEffect, useContext } from "react";
import {
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, AreaChart, Area, BarChart, Bar,
} from "recharts";
import {
  Shield, Scale, Search as SearchIcon, Brain, ArrowUpRight, MapPin,
  AlertTriangle, TrendingUp, TrendingDown, Info,
} from "lucide-react";
import { authFetch, normalizeAnomalies } from "@/lib/api";
import { TabContext } from "@/components/layout/Shell";
import { SectionTitle, PanelLabel, Pill, Loading, Stat } from "@/components/ui/primitives";
import {
  AXIS_INK, MONO_TICK, TOOLTIP_STYLE, ACCENT_CYAN, ACCENT_BLUE, WARN,
} from "@/lib/chart-theme";
import {
  mockKpis, mockMonthlyTrends, mockTopDistricts, mockHotStations, mockAnomalies,
} from "@/lib/mock";
import type {
  DashboardKpis, MonthlyTrendPoint, TopDistrict, HotStation, Anomaly,
} from "@/lib/types";

function Sparkline({ color, data }: { color: string; data: number[] }) {
  const chartData = data.map((v, i) => ({ i, v }));
  const gid = `spark-${color.replace("#", "")}`;
  return (
    <div className="mt-3 h-10 w-full select-none">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
          <defs>
            <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.32} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone" dataKey="v"
            stroke={color} strokeWidth={1.6} strokeLinecap="round"
            fill={`url(#${gid})`} dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// Isometric extrusion (depth px, up-and-right) fakes a 3D column from three
// flat SVG faces — Recharts has no native 3D bar, so the cap/side polygons
// must be hand-drawn per bar and layered back-to-front (side, top, front).
// The three fills are one hue at three light levels: the cap catches the key
// light, the front is the body gradient, the right face falls into shadow.
const BAR3D_DEPTH = 8;
const BAR3D_CAP = "#7cf0ff";
const BAR3D_SIDE = "#0891b2";
function Bar3D(props: { x?: number; y?: number; width?: number; height?: number }) {
  const { x = 0, y = 0, width = 0 } = props;
  // Recharts drives the entrance animation from height 0 up to its final
  // value on a real, continuously-mounted node — returning null here (e.g.
  // for a zero/negative height) unmounts that node and stalls the animation
  // at frame 0, so clamp instead of bailing out.
  const height = Math.max(0, props.height ?? 0);
  if (width <= 0) return null;
  const d = BAR3D_DEPTH;
  return (
    <g>
      <polygon
        points={`${x + width},${y} ${x + width + d},${y - d} ${x + width + d},${y + height - d} ${x + width},${y + height}`}
        fill={BAR3D_SIDE}
      />
      <polygon
        points={`${x},${y} ${x + d},${y - d} ${x + width + d},${y - d} ${x + width},${y}`}
        fill={BAR3D_CAP}
      />
      <rect x={x} y={y} width={width} height={height} fill="url(#bar3dFront)" />
    </g>
  );
}

function KpiCard({
  label, value, delta, deltaTone, icon: Icon, iconTone, spark, sparkColor,
}: {
  label: string; value: string; delta: string;
  deltaTone: "ok" | "warn" | "danger"; icon: React.ElementType; iconTone: string;
  spark: number[]; sparkColor: string;
}) {
  const up = deltaTone === "ok";
  return (
    <div className="glass glass-hover flex flex-col justify-between p-5">
      <div>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--color-ink-faint)]">{label}</p>
            <h3 className="mono mt-2 text-[30px] font-bold leading-none tracking-[-0.02em] text-[var(--color-ink)]">{value}</h3>
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
    </div>
  );
}

export default function DashboardView() {
  const { navigateTo } = useContext(TabContext);
  const [kpis, setKpis] = useState<DashboardKpis>(mockKpis);
  const [trends, setTrends] = useState<MonthlyTrendPoint[]>(mockMonthlyTrends);
  const [topDistricts, setTopDistricts] = useState<TopDistrict[]>(mockTopDistricts);
  const [hotStations, setHotStations] = useState<HotStation[]>(mockHotStations);
  const [anomalies, setAnomalies] = useState<Anomaly[]>(mockAnomalies);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        // Each block: swap the mock fallback for the real response in one line.
        const kpiRes = await authFetch("/api/dashboard/kpis");
        if (kpiRes.ok) {
          // Backend shape (total_firs, arrest_rate, conviction_rate, monthly_growth,
          // firs_this_month) doesn't match DashboardKpis 1:1 -- map it here rather than
          // in the backend, which has its own established response contract.
          const raw = await kpiRes.json();
          setKpis({
            total_firs: raw.total_firs,
            monthly_growth: raw.monthly_growth,
            solve_rate: raw.conviction_rate ?? mockKpis.solve_rate,
            active_investigations: raw.active_investigations ?? mockKpis.active_investigations,
          });
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
        /* keep mock fallbacks */
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <Loading />;

  const maxRate = Math.max(...topDistricts.map((d) => d.rate), 1);
  const growthPositive = kpis.monthly_growth >= 0;

  return (
    <div className="flex flex-col gap-[22px] fade-up">
      <div className="flex items-center justify-between">
        <SectionTitle>Executive Command Center</SectionTitle>
        <Pill tone="ok" className="px-3 py-1">Live · Karnataka State</Pill>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-1 gap-[18px] md:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Total FIRs (YTD)" value={kpis.total_firs.toLocaleString()}
          delta={`${growthPositive ? "+" : ""}${kpis.monthly_growth}% MoM`}
          deltaTone={growthPositive ? "ok" : "danger"}
          icon={Shield} iconTone="border-[var(--color-accent-blue)]/30 bg-[var(--color-accent-blue)]/10 text-[var(--color-accent-blue)]"
          spark={[23, 28, 25, 32, 29, 38, 35, 30, 33, 29, 27, 24]} sparkColor={ACCENT_BLUE}
        />
        <KpiCard
          label="Crime Solve Rate" value={`${kpis.solve_rate}%`}
          delta="+1.2% this quarter" deltaTone="ok"
          icon={Scale} iconTone="border-[var(--color-warn)]/30 bg-[var(--color-warn)]/10 text-[var(--color-warn)]"
          spark={[62, 60, 64, 63, 65, 64, 68, 66, 67, 68, 69, 71]} sparkColor={WARN}
        />
        <KpiCard
          label="Active Investigations" value={kpis.active_investigations.toLocaleString()}
          delta="18 opened today" deltaTone="warn"
          icon={SearchIcon} iconTone="border-[var(--color-accent-cyan)]/30 bg-[var(--color-accent-cyan)]/10 text-[var(--color-accent-cyan)]"
          spark={[140, 148, 152, 160, 171, 168, 176, 180, 178, 184, 182, 184]} sparkColor={ACCENT_CYAN}
        />
        <button
          onClick={() => navigateTo("forecast")}
          className="glass glass-hover glass-hover-violet group flex flex-col justify-between p-5 text-left"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--color-ink-faint)]">AI Forecast Engine</p>
              <h3 className="mt-2.5 text-lg font-bold uppercase tracking-[0.08em] text-[var(--color-ink)]">Status: Active</h3>
            </div>
            <div className="breathe rounded-[var(--radius-well)] border border-[var(--color-accent-purple)]/35 bg-[var(--color-accent-purple)]/[0.12] p-2.5 text-[var(--color-accent-purple)]">
              <Brain className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 flex items-center justify-between border-t border-[var(--color-hairline)] pt-3">
            <span className="text-[10px] text-[var(--color-ink-muted)]">
              Next 3-month prediction: <strong className="uppercase text-[var(--color-accent-purple)]">Stable</strong>
            </span>
            <ArrowUpRight className="h-4 w-4 shrink-0 text-[var(--color-ink-faint)] transition-colors group-hover:text-[var(--color-accent-purple)]" />
          </div>
        </button>
      </div>

      {/* Chart + rankings */}
      <div className="grid grid-cols-1 gap-[18px] lg:grid-cols-3">
        <div className="glass flex flex-col p-5 lg:col-span-2">
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
              <BarChart data={trends} margin={{ top: 6 + BAR3D_DEPTH, right: 8 + BAR3D_DEPTH, left: -12, bottom: 0 }}>
                <defs>
                  <linearGradient id="bar3dFront" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00D9FF" />
                    <stop offset="100%" stopColor="#0891b2" />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="month" stroke={AXIS_INK} fontSize={9} tickLine={false} axisLine={false} {...MONO_TICK} />
                <YAxis stroke={AXIS_INK} fontSize={9} tickLine={false} axisLine={false} domain={[0, (max: number) => Math.ceil(max * 1.15)]} {...MONO_TICK} />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.03)" }}
                  contentStyle={TOOLTIP_STYLE}
                  labelStyle={{ color: "#A1A1A6", fontWeight: 700 }}
                />
                <Bar dataKey="count" shape={<Bar3D />} maxBarSize={30} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass flex flex-col justify-between p-5">
          <div>
            <PanelLabel className="mb-5">Top District Rankings</PanelLabel>
            <div className="space-y-4">
              {topDistricts.map((d, i) => (
                <div key={i} className="space-y-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-[var(--color-ink-muted)]">{d.name}</span>
                    <Stat className="font-bold text-[var(--color-ink)]">{d.rate.toFixed(1)}</Stat>
                  </div>
                  <div className="h-3 w-full overflow-hidden rounded-full bg-black/30 shadow-[inset_0_2px_3px_rgba(0,0,0,0.55)]">
                    <div
                      className={`relative h-full overflow-hidden rounded-full shadow-[0_0_12px_rgba(0,217,255,0.3)] transition-[width] duration-1000 ease-[cubic-bezier(.2,.9,.2,1)] ${i === 0 ? "bg-gradient-to-r from-[var(--color-accent-cyan)] to-[var(--color-accent-blue)]" : "bg-gradient-to-r from-[var(--color-warn)] to-[var(--color-danger)]"}`}
                      style={{ width: `${Math.max(8, (d.rate / maxRate) * 100)}%` }}
                    >
                      <div className="absolute inset-x-0 top-0 h-1/2 rounded-t-full bg-gradient-to-b from-white/60 to-transparent" />
                      <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/30 to-transparent" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <button
            onClick={() => navigateTo("reports")}
            className="mt-6 w-full rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-white/[0.02] py-3 text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-muted)] transition-all hover:border-[var(--color-hairline-strong)] hover:text-[var(--color-ink)]"
          >
            View All Rankings
          </button>
        </div>
      </div>

      {/* Hot stations + anomalies */}
      <div className="grid grid-cols-1 gap-[18px] md:grid-cols-3">
        <div className="glass p-5">
          <PanelLabel className="mb-4 flex items-center gap-2">
            <MapPin className="h-4 w-4 text-[var(--color-accent-cyan)]" /> Top Active Police Stations
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
        </div>

        <div className="glass flex flex-col justify-between !border-[var(--color-danger)]/[0.22] !bg-[var(--color-danger)]/[0.05] p-5 md:col-span-2">
          <div>
            <PanelLabel className="mb-4 flex items-center gap-2 !text-[var(--color-danger)]">
              <AlertTriangle className="h-4 w-4 pulse-dot" /> Statistical Anomaly Alert Feed
            </PanelLabel>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {anomalies.map((a, i) => {
                const tone = a.severity === "CRITICAL" ? "danger" : a.severity === "WARNING" ? "warn" : "info";
                const bar = a.severity === "CRITICAL" ? "border-[var(--color-danger)]" : a.severity === "WARNING" ? "border-[var(--color-warn)]" : "border-[var(--color-accent-blue)]";
                return (
                  <div key={i} className={`rounded-[var(--radius-well)] border-l-2 ${bar} bg-white/[0.02] p-3`}>
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
          <div className="mt-4 flex items-center gap-3 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-white/[0.02] p-3">
            <Info className="h-4 w-4 shrink-0 text-[var(--color-ink-faint)]" />
            <span className="text-[10px] leading-normal text-[var(--color-ink-faint)]">
              <strong className="text-[var(--color-ink-muted)]">System Protocol:</strong> Alerts represent 1.5σ z-score deviations vs. baseline. Patrol units in affected sectors have been notified.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
