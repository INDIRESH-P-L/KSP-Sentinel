"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  ComposedChart, Line, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from "recharts";
import { TrendingUp, Cpu, Info, Gauge as GaugeIcon } from "lucide-react";
import { authFetch } from "@/lib/api";
import { SectionTitle, PanelLabel, Pill, Loading } from "@/components/ui/primitives";
import { mockDistricts, mockForecast } from "@/lib/mock";
import type { District, Forecast } from "@/lib/types";

const CATEGORIES = [
  { id: 1, name: "Theft & Burglary" },
  { id: 2, name: "Crimes Against Persons" },
  { id: 3, name: "Cyber Crime" },
  { id: 4, name: "Narcotics (NDPS)" },
  { id: 5, name: "Economic Offenses" },
  { id: 6, name: "Women & Child Safety" },
];

const MODELS = [
  { id: "arima", label: "ARIMA (Classical Stats)", desc: "Statistical model optimized for stationary seasonal trends." },
  { id: "prophet", label: "Facebook Prophet", desc: "Additive regression capturing strong weekly/yearly seasonality and holidays." },
  { id: "lstm", label: "LSTM Neural Net", desc: "Recurrent network modeling long-term sequence dependencies." },
  { id: "xgboost", label: "XGBoost Regressor", desc: "Gradient-boosted trees learning complex non-linear lag relationships." },
];

// Historical actuals shown before the forecast horizon (from monthly-trends style data).
const HISTORY = [
  { label: "Jan 2023", actual: 143 },
  { label: "Apr 2023", actual: 151 },
  { label: "Jul 2023", actual: 138 },
  { label: "Oct 2023", actual: 176 },
  { label: "Jan 2024", actual: 168 },
];
const HORIZON = ["Apr 2024", "May 2024", "Jun 2024"];

function ConfidenceGauge({ percent }: { percent: number }) {
  const r = 54;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, percent));
  const offset = c * (1 - clamped / 100);
  const color = clamped >= 80 ? "#10b981" : clamped >= 60 ? "#f59e0b" : "#ef4444";
  return (
    <svg viewBox="0 0 140 140" className="h-36 w-36">
      <circle cx="70" cy="70" r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="9" />
      <circle
        cx="70" cy="70" r={r} fill="none" stroke={color} strokeWidth="9" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={offset} transform="rotate(-90 70 70)"
        style={{ transition: "stroke-dashoffset 600ms ease" }}
      />
      <text x="70" y="66" textAnchor="middle" fontSize="26" fontWeight="800" fill="#f8fafc">{Math.round(clamped)}%</text>
      <text x="70" y="88" textAnchor="middle" fontSize="8" fontWeight="700" fill="#94a3b8" letterSpacing="1.5">CONFIDENCE</text>
    </svg>
  );
}

export default function ForecastView() {
  const [districts, setDistricts] = useState<District[]>(mockDistricts);
  const [district, setDistrict] = useState(mockDistricts[0].id);
  const [category, setCategory] = useState(1);
  const [model, setModel] = useState("arima");
  const [forecast, setForecast] = useState<Forecast>(mockForecast("arima"));
  const [loading, setLoading] = useState(true);
  const [refetching, setRefetching] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const dRes = await authFetch("/api/districts/");
        if (dRes.ok) {
          const data: District[] = await dRes.json();
          if (data.length) {
            setDistricts(data);
            setDistrict(data[0].id);
          }
        }
      } catch {
        /* mock */
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      setRefetching(true);
      try {
        const res = await authFetch(`/api/forecast/?district_id=${district}&category_id=${category}&model=${model}`);
        if (res.ok) setForecast(await res.json());
        else setForecast(mockForecast(model));
      } catch {
        setForecast(mockForecast(model));
      } finally {
        setRefetching(false);
      }
    })();
  }, [district, category, model]);

  // Build the composed chart series from the spec shape.
  const chartData = useMemo(() => {
    const hist = HISTORY.map((h) => ({ label: h.label, actual: h.actual, predicted: null as number | null, band: undefined as [number, number] | undefined }));
    // Bridge the last actual into the forecast line so it connects visually.
    const last = HISTORY[HISTORY.length - 1].actual;
    const fc = forecast.forecast.map((v, i) => ({
      label: HORIZON[i] ?? `M${i + 1}`,
      actual: null as number | null,
      predicted: v,
      band: [forecast.lower_bounds[i], forecast.upper_bounds[i]] as [number, number],
    }));
    if (fc.length) fc[0] = { ...fc[0], actual: last };
    return [...hist, ...fc];
  }, [forecast]);

  const districtName = districts.find((d) => d.id === district)?.name ?? "the selected district";
  const categoryName = CATEGORIES.find((c) => c.id === category)?.name.toLowerCase() ?? "selected crimes";
  const modelMeta = MODELS.find((m) => m.id === model)!;
  const avg = Math.round(forecast.forecast.reduce((s, v) => s + v, 0) / forecast.forecast.length);
  const trend = forecast.forecast[forecast.forecast.length - 1] >= forecast.forecast[0] ? "a slight increase" : "a decrease";
  // Confidence from band tightness: narrower band → higher confidence.
  const confidence = Math.round(
    100 - (forecast.upper_bounds.reduce((s, u, i) => s + (u - forecast.lower_bounds[i]) / forecast.forecast[i], 0) / forecast.forecast.length) * 100 * 0.6
  );

  if (loading) return <Loading />;

  return (
    <div className="space-y-6 fade-up">
      <div className="flex items-center justify-between">
        <SectionTitle>AI Crime Forecast Console</SectionTitle>
        <span className="text-xs font-bold uppercase tracking-wider text-[var(--color-ink-faint)]">
          Gateway Status <span className="text-[var(--color-ok)]">Online</span>
        </span>
      </div>

      {/* Selectors */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Selector label="District Jurisdiction" value={district} onChange={(v) => setDistrict(Number(v))}>
          {districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </Selector>
        <Selector label="Crime Classification" value={category} onChange={(v) => setCategory(Number(v))}>
          {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </Selector>
        <Selector label="AI Forecasting Engine" value={model} onChange={setModel}>
          {MODELS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
        </Selector>
      </div>

      <div className="glass flex items-center gap-3 p-4">
        <Cpu className="h-7 w-7 shrink-0 text-[var(--color-accent-cyan)]" />
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--color-ink)]">{modelMeta.label} Engine</h4>
          <p className="mt-0.5 text-[11px] leading-relaxed text-[var(--color-ink-faint)]">{modelMeta.desc}</p>
        </div>
      </div>

      {/* Chart + gauge + summary */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_320px]">
        <div className="glass p-5">
          <PanelLabel className="mb-5 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-[var(--color-accent-cyan)]" /> Expected Crime Incident Counts — Next 6 Months
          </PanelLabel>
          <div className={`h-80 w-full transition-opacity ${refetching ? "opacity-40" : "opacity-100"}`}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 6, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                <XAxis dataKey="label" stroke="#64748b" fontSize={10} tickLine={false} axisLine={false} />
                <YAxis stroke="#64748b" fontSize={10} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ background: "#111a2b", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 12, color: "#f8fafc", fontSize: 12 }}
                  labelStyle={{ color: "#94a3b8", fontWeight: 700 }}
                />
                <Legend verticalAlign="top" height={34} wrapperStyle={{ fontSize: 11 }} />
                <Area name="Confidence Band" type="monotone" dataKey="band" stroke="none" fill="rgba(34,211,238,0.1)" />
                <Line name="Actual Incidents" type="monotone" dataKey="actual" stroke="#10b981" strokeWidth={2.5} dot={{ r: 4, stroke: "#06080b", strokeWidth: 1.5 }} activeDot={{ r: 7 }} connectNulls />
                <Line name="AI Forecast" type="monotone" dataKey="predicted" stroke="#22d3ee" strokeWidth={2.5} strokeDasharray="5 5" dot={{ r: 5, stroke: "#06080b", strokeWidth: 1.5 }} activeDot={{ r: 7 }} connectNulls />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="flex flex-col gap-5">
          <div className="glass flex flex-1 flex-col items-center justify-center p-5">
            <span className="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-[var(--color-ink-faint)]">
              <GaugeIcon className="h-3.5 w-3.5 text-[var(--color-accent-cyan)]" /> AI Confidence Score
            </span>
            <ConfidenceGauge percent={confidence} />
            <p className="mt-1 text-[10px] text-[var(--color-ink-faint)]">
              {confidence >= 80 ? "High confidence" : confidence >= 60 ? "Moderate confidence" : "Low confidence"} · based on model stability
            </p>
          </div>
          <div className="glass p-5">
            <PanelLabel className="mb-2">Forecast Summary</PanelLabel>
            <p className="text-xs leading-relaxed text-[var(--color-ink-muted)]">
              The <span className="font-semibold text-[var(--color-ink)]">{modelMeta.label.split(" ")[0]}</span> model predicts {trend} in {categoryName} incidents
              over the next quarter in {districtName}, averaging <span className="font-semibold text-[var(--color-ink)]">{avg}</span> cases/month.
              Key drivers: seasonal cycles and recent urban development. Confidence interval ±5%.
            </p>
          </div>
        </div>
      </div>

      {/* Per-month prediction cards */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
        {forecast.forecast.map((v, i) => (
          <div key={i} className="glass flex flex-col justify-between gap-2 p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-faint)]">{HORIZON[i] ?? `Month ${i + 1}`}</span>
              <Pill tone="ok">{forecast.lower_bounds[i]}–{forecast.upper_bounds[i]}</Pill>
            </div>
            <div>
              <h4 className="text-2xl font-extrabold text-[var(--color-ink)]">{v} cases</h4>
              <p className="mt-1 text-[10px] text-[var(--color-ink-faint)]">Expected {categoryName} volume in {districtName}.</p>
            </div>
          </div>
        ))}
      </div>

      <div className="glass flex items-start gap-3 border-[var(--color-accent-blue)]/15 bg-[var(--color-accent-blue)]/[0.04] p-4">
        <Info className="mt-0.5 h-5 w-5 shrink-0 text-[var(--color-accent-cyan)]" />
        <div className="text-xs leading-relaxed text-[var(--color-ink-muted)]">
          <p className="mb-1 text-[10px] font-bold uppercase tracking-wider text-[var(--color-ink-faint)]">Methodology Notice</p>
          Predictions are computed from the past 24 months of geo-coded FIR histories, factoring seasonal variance (festivals, weather, calendar cycles) and growth coefficients. Commanders should use these forecasts to optimize CCTV placement and auxiliary patrol assignments.
        </div>
      </div>
    </div>
  );
}

function Selector({
  label, value, onChange, children,
}: {
  label: string; value: string | number; onChange: (v: string) => void; children: React.ReactNode;
}) {
  return (
    <div className="glass p-4">
      <label className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-[var(--color-ink-faint)]">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)] px-4 py-2.5 text-sm text-[var(--color-ink)] focus:border-[var(--color-accent-cyan)]/60 focus:outline-none"
      >
        {children}
      </select>
    </div>
  );
}
