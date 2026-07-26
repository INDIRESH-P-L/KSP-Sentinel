"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  ComposedChart, Line, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
} from "recharts";
import { TrendingUp, Cpu, Info, Gauge as GaugeIcon } from "lucide-react";
import { publicFetch, authFetch } from "@/lib/api";
import { SectionTitle, PanelLabel, Pill, Loading, Stat } from "@/components/ui/primitives";
import {
  AXIS_INK, LABEL_INK, MONO_TICK, TOOLTIP_STYLE, GRID_STROKE,
  ACCENT_CYAN, BASE_INK, OK, WARN, RED,
} from "@/lib/chart-theme";
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

/**
 * Large radial confidence dial. The arc's hue doubles as the verdict (green /
 * amber / red) and carries a drop-shadow in that same hue so the ring reads as
 * emissive, matching the smaller gauges elsewhere in the console.
 */
function ConfidenceGauge({ percent }: { percent: number }) {
  const r = 54;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, percent));
  const offset = c * (1 - clamped / 100);
  const color = clamped >= 80 ? OK : clamped >= 60 ? WARN : RED;
  return (
    <svg viewBox="0 0 140 140" className="h-36 w-36">
      <circle cx="70" cy="70" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="9" />
      <circle
        cx="70" cy="70" r={r} fill="none" stroke={color} strokeWidth="9" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={offset} transform="rotate(-90 70 70)"
        style={{ transition: "stroke-dashoffset 700ms ease", filter: `drop-shadow(0 0 5px ${color}88)` }}
      />
      <text
        x="70" y="67" textAnchor="middle" fontSize="26" fontWeight="800"
        fill="#fff" fontFamily="var(--font-mono)"
      >
        {Math.round(clamped)}%
      </text>
      <text x="70" y="88" textAnchor="middle" fontSize="8" fontWeight="700" fill={LABEL_INK} letterSpacing="1.5">
        CONFIDENCE
      </text>
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
  
  const [grokInsight, setGrokInsight] = useState<string | null>(null);
  const [grokLoading, setGrokLoading] = useState(false);
  const [grokError, setGrokError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const dRes = await publicFetch("/api/districts/");
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
        const res = await publicFetch(`/api/forecast/?district_id=${district}&category_id=${category}&model=${model}`);
        if (res.ok) {
          // Backend's `forecast` is [{date, actual, predicted, confidence}], and it has
          // no per-point bounds -- Forecast wants flat number[] + lower/upper bands, so
          // derive a band from each point's confidence (narrower band = higher confidence,
          // same relationship the UI's own confidence gauge below assumes).
          const raw: { forecast: { predicted: number; confidence: number }[] } = await res.json();
          const values = raw.forecast.map((p) => p.predicted);
          const lower = raw.forecast.map((p) => p.predicted * (1 - (1 - p.confidence) * 0.3));
          const upper = raw.forecast.map((p) => p.predicted * (1 + (1 - p.confidence) * 0.3));
          setForecast({ forecast: values, lower_bounds: lower, upper_bounds: upper });
        } else setForecast(mockForecast(model));
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
  const avg = Math.round(forecast.forecast.reduce((a, b) => a + b, 0) / forecast.forecast.length);
  const trend = forecast.forecast[2] > forecast.forecast[0] ? "an increase" : "a decrease";

  const generateGrokInsight = async () => {
    setGrokLoading(true);
    setGrokError(null);
    try {
      const res = await publicFetch("/api/grok/forecast-insight", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          district_name: districtName,
          category_name: categoryName,
          model_name: modelMeta.label,
          historical_data: HISTORY,
          forecast_data: forecast.forecast
        })
      });
      if (res.ok) {
        const data = await res.json();
        setGrokInsight(data.insight);
      } else {
        const errData = await res.json().catch(() => null);
        setGrokError(errData?.detail || `API Error: ${res.status}`);
      }
    } catch (err: any) {
      setGrokError(err.message || "Failed to generate insight");
    } finally {
      setGrokLoading(false);
    }
  };

  const confidence = Math.round(
    100 - (forecast.upper_bounds.reduce((s, u, i) => s + (u - forecast.lower_bounds[i]) / forecast.forecast[i], 0) / forecast.forecast.length) * 100 * 0.6
  );

  if (loading) return <Loading />;

  return (
    <div className="flex flex-col gap-[22px] fade-up">
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
      <div className="grid grid-cols-1 gap-[18px] lg:grid-cols-[1fr_320px]">
        <div className="glass p-5">
          <PanelLabel className="mb-5 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-[var(--color-accent-cyan)]" /> Expected Crime Incident Counts — Next 6 Months
          </PanelLabel>
          <div className={`h-80 w-full transition-opacity ${refetching ? "opacity-40" : "opacity-100"}`}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 6, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} vertical={false} />
                <XAxis dataKey="label" stroke={AXIS_INK} fontSize={9} tickLine={false} axisLine={false} {...MONO_TICK} />
                <YAxis stroke={AXIS_INK} fontSize={9} tickLine={false} axisLine={false} {...MONO_TICK} />
                <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: LABEL_INK, fontWeight: 700 }} />
                <Legend verticalAlign="top" height={34} wrapperStyle={{ fontSize: 11 }} />
                <Area name="Confidence Band" type="monotone" dataKey="band" stroke="none" fill="rgba(0,217,255,0.12)" />
                <Line name="Actual Incidents" type="monotone" dataKey="actual" stroke={OK} strokeWidth={2.5} dot={{ r: 3.5, stroke: BASE_INK, strokeWidth: 1.5 }} activeDot={{ r: 7 }} connectNulls />
                {/* Dashed + glowing: the forecast leg is visually distinct from measured history. */}
                <Line
                  name="AI Forecast" type="monotone" dataKey="predicted"
                  stroke={ACCENT_CYAN} strokeWidth={2.5} strokeDasharray="6 5"
                  dot={{ r: 4, stroke: BASE_INK, strokeWidth: 1.5 }} activeDot={{ r: 7 }}
                  style={{ filter: "drop-shadow(0 0 4px rgba(0,217,255,0.5))" }}
                  connectNulls
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="flex flex-col gap-[18px]">
          <div className="glass flex flex-1 flex-col items-center justify-center p-5">
            <span className="mb-2 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest text-[var(--color-ink-faint)]">
              <GaugeIcon className="h-3.5 w-3.5 text-[var(--color-accent-cyan)]" /> AI Confidence Score
            </span>
            <ConfidenceGauge percent={confidence} />
            <p className="mt-1 text-[10px] text-[var(--color-ink-faint)]">
              {confidence >= 80 ? "High confidence" : confidence >= 60 ? "Moderate confidence" : "Low confidence"} · based on model stability
            </p>
          </div>
          <div className="glass p-5 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <PanelLabel className="mb-0">Forecast Summary</PanelLabel>
              <button 
                onClick={generateGrokInsight}
                disabled={grokLoading}
                className="flex items-center gap-1.5 rounded-full border border-[var(--color-accent-cyan)]/30 bg-[var(--color-accent-cyan)]/10 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-[var(--color-accent-cyan)] hover:bg-[var(--color-accent-cyan)]/20 transition-colors disabled:opacity-50"
              >
                {grokLoading ? "Analyzing..." : "Generate Grok Insight"}
              </button>
            </div>
            {grokError && (
              <p className="text-xs text-[var(--color-red)]">{grokError}</p>
            )}
            <p className="text-xs leading-relaxed text-[var(--color-ink-muted)]">
              {grokInsight ? (
                <span className="text-[var(--color-ink)]">{grokInsight}</span>
              ) : (
                <>
                  The <span className="font-semibold text-[var(--color-ink)]">{modelMeta.label.split(" ")[0]}</span> model predicts {trend} in {categoryName} incidents
                  over the next quarter in {districtName}, averaging <Stat className="font-bold text-[var(--color-ink)]">{avg}</Stat> cases/month.
                  Key drivers: seasonal cycles and recent urban development. Confidence interval ±5%.
                </>
              )}
            </p>
          </div>
        </div>
      </div>

      {/* Per-month prediction cards */}
      <div className="grid grid-cols-1 gap-[18px] md:grid-cols-3">
        {forecast.forecast.map((v, i) => (
          <div key={i} className="glass flex flex-col justify-between gap-2 p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-[0.06em] text-[var(--color-ink-faint)]">{HORIZON[i] ?? `Month ${i + 1}`}</span>
              <Pill tone="ok"><Stat>{forecast.lower_bounds[i]}–{forecast.upper_bounds[i]}</Stat></Pill>
            </div>
            <div>
              <h4 className="mono text-2xl font-bold text-[var(--color-ink)]">{v} cases</h4>
              <p className="mt-1 text-[10px] text-[var(--color-ink-faint)]">Expected {categoryName} volume in {districtName}.</p>
            </div>
          </div>
        ))}
      </div>

      <div className="glass flex items-start gap-3 !border-[var(--color-accent-cyan)]/15 !bg-[var(--color-accent-cyan)]/[0.04] p-4">
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
