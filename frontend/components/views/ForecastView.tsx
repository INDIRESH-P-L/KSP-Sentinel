"use client";

import React, { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, Legend
} from "recharts";
import { TrendingUp, Cpu, Info, Gauge } from "lucide-react";
import { authFetch } from "@/lib/api";

const MODEL_DESCRIPTIONS: Record<string, string> = {
  ARIMA: "Classical statistical model optimized for stationary seasonal trends.",
  PROPHET: "Additive regression model optimized for capturing strong weekly/yearly seasonal patterns and holidays.",
  XGBOOST: "Gradient boosted decision trees capable of learning complex non-linear lag relationships.",
  LSTM: "Recurrent neural network capable of modeling long-term sequence dependencies.",
};

// Compact circular confidence gauge -- pure SVG, no charting library needed for a
// single-value ring. Matches the "AI Confidence Score" dial in the reference design.
function ConfidenceGauge({ percent }: { percent: number }) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, percent));
  const offset = circumference * (1 - clamped / 100);
  const color = clamped >= 80 ? "#34d399" : clamped >= 60 ? "#fbbf24" : "#f87171";

  return (
    <svg viewBox="0 0 140 140" className="w-36 h-36">
      <circle cx="70" cy="70" r={radius} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="10" />
      <circle
        cx="70" cy="70" r={radius} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
        strokeDasharray={circumference} strokeDashoffset={offset}
        transform="rotate(-90 70 70)"
        style={{ transition: "stroke-dashoffset 600ms ease" }}
      />
      <text x="70" y="65" textAnchor="middle" fontSize="26" fontWeight="bold" fill="#f8fafc">{Math.round(clamped)}%</text>
      <text x="70" y="86" textAnchor="middle" fontSize="9" fill="#94a3b8" letterSpacing="1">CONFIDENCE</text>
    </svg>
  );
}

export default function ForecastView() {
  const [districts, setDistricts] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [selectedDistrict, setSelectedDistrict] = useState(1);
  const [selectedCategory, setSelectedCategory] = useState(1);
  const [selectedModel, setSelectedModel] = useState("ARIMA");
  const [forecastData, setForecastData] = useState<any>(null);
  const [loadingForecast, setLoadingForecast] = useState(true);

  // Initialize filters
  useEffect(() => {
    async function loadFilters() {
      try {
        const dRes = await authFetch("/api/districts/");
        if (dRes.ok) {
          const dData = await dRes.json();
          setDistricts(dData);
          if (dData.length > 0) setSelectedDistrict(dData[0].id);
        }

        // Mock categories since we don't have category endpoint, or fetch them if they are in database
        // Let's seed categories list
        setCategories([
          { id: 1, name: "Theft & Burglary" },
          { id: 2, name: "Crimes Against Persons" },
          { id: 3, name: "Cyber Crime" },
          { id: 4, name: "Narcotics" },
          { id: 5, name: "Economic Offenses" },
          { id: 6, name: "Women & Child Safety" }
        ]);
      } catch (e) {
        console.error("Error loading filters:", e);
      }
    }
    loadFilters();
  }, []);

  // Fetch forecast when selectors change
  useEffect(() => {
    async function fetchForecast() {
      if (!selectedDistrict || !selectedCategory) return;
      setLoadingForecast(true);
      try {
        const url = `/api/forecast/?district_id=${selectedDistrict}&category_id=${selectedCategory}&model_name=${selectedModel}&forecast_months=3`;
        const res = await authFetch(url);
        if (res.ok) {
          const data = await res.json();
          setForecastData(data);
        }
      } catch (e) {
        console.error("Error loading forecast:", e);
      } finally {
        setLoadingForecast(false);
      }
    }
    fetchForecast();
  }, [selectedDistrict, selectedCategory, selectedModel]);

  const avgConfidence = forecastData?.forecast?.length
    ? (forecastData.forecast.reduce((sum: number, f: any) => sum + f.confidence, 0) / forecastData.forecast.length) * 100
    : 0;

  const districtName = forecastData?.district ?? districts.find(d => d.id === selectedDistrict)?.name ?? "the selected district";
  const categoryName = forecastData?.category?.toLowerCase() ?? categories.find(c => c.id === selectedCategory)?.name?.toLowerCase() ?? "selected crime types";
  const trendDirection = forecastData?.forecast?.length >= 2
    ? (forecastData.forecast[forecastData.forecast.length - 1].predicted >= forecastData.forecast[0].predicted ? "an upward" : "a downward")
    : null;

  return (
    <div className="space-y-6">
      {/* Selectors Panel */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-800 grid grid-cols-1 md:grid-cols-4 gap-6">
        <div>
          <label className="block text-slate-300 text-xs font-semibold uppercase tracking-wider mb-2">District Jurisdiction</label>
          <select
            value={selectedDistrict}
            onChange={e => setSelectedDistrict(Number(e.target.value))}
            className="w-full bg-slate-900/60 border border-slate-700/50 rounded-lg py-2.5 px-4 text-slate-100 focus:outline-none focus:border-blue-500 text-sm"
          >
            {districts.map(d => (
              <option key={d.id} value={d.id} className="bg-slate-950">{d.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-slate-300 text-xs font-semibold uppercase tracking-wider mb-2">Crime Classification</label>
          <select
            value={selectedCategory}
            onChange={e => setSelectedCategory(Number(e.target.value))}
            className="w-full bg-slate-900/60 border border-slate-700/50 rounded-lg py-2.5 px-4 text-slate-100 focus:outline-none focus:border-blue-500 text-sm"
          >
            {categories.map(c => (
              <option key={c.id} value={c.id} className="bg-slate-950">{c.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-slate-300 text-xs font-semibold uppercase tracking-wider mb-2">AI Forecasting Engine</label>
          <select
            value={selectedModel}
            onChange={e => setSelectedModel(e.target.value)}
            className="w-full bg-slate-900/60 border border-slate-700/50 rounded-lg py-2.5 px-4 text-slate-100 focus:outline-none focus:border-blue-500 text-sm"
          >
            <option value="ARIMA" className="bg-slate-950">ARIMA (Classical Stats)</option>
            <option value="PROPHET" className="bg-slate-950">Facebook Prophet</option>
            <option value="XGBOOST" className="bg-slate-950">XGBoost Regressor</option>
            <option value="LSTM" className="bg-slate-950">LSTM Neural Net</option>
          </select>
        </div>

        <div className="flex items-center gap-3 bg-blue-500/5 border border-blue-500/10 p-4 rounded-xl">
          <Cpu className="w-8 h-8 text-cyan-400 flex-shrink-0" />
          <div className="min-w-0">
            <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">{selectedModel} Engine</h4>
            <p className="text-[10px] text-slate-400 mt-0.5 leading-relaxed line-clamp-2">{MODEL_DESCRIPTIONS[selectedModel]}</p>
          </div>
        </div>
      </div>

      {loadingForecast ? (
        <div className="glass-panel rounded-2xl border border-slate-800 h-96 flex items-center justify-center">
          <div className="text-cyan-400 font-semibold animate-pulse text-sm tracking-wider">CALCULATING PROBABILISTIC CRIME TRENDS...</div>
        </div>
      ) : (
        <>
          {/* Bento: forecast chart (wide) + confidence gauge + narrative summary */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="lg:col-span-3 glass-panel p-6 rounded-2xl border border-slate-800">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-6 flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-cyan-400" />
                Expected Crime Incident Counts: Next 3 Months
              </h3>
              <div className="h-80 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={forecastData?.combined}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="date" stroke="#94a3b8" fontSize={11} />
                    <YAxis stroke="#94a3b8" fontSize={11} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "#0f172a", border: "1px solid rgba(59, 130, 246, 0.2)", borderRadius: "8px" }}
                      labelStyle={{ color: "#f8fafc", fontWeight: "bold" }}
                    />
                    <Legend verticalAlign="top" height={36} />
                    <Line
                      name="Actual Incidents"
                      type="monotone"
                      dataKey="actual"
                      stroke="#3b82f6"
                      strokeWidth={3}
                      dot={{ r: 4 }}
                      activeDot={{ r: 8 }}
                    />
                    <Line
                      name="AI Forecast (Dashed)"
                      type="monotone"
                      dataKey="predicted"
                      stroke="#22c55e"
                      strokeWidth={3}
                      strokeDasharray="5 5"
                      dot={{ r: 5 }}
                      activeDot={{ r: 8 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="flex flex-col gap-6">
              {/* AI Confidence Score gauge */}
              <div className="glass-panel p-6 rounded-2xl border border-slate-800 flex flex-col items-center justify-center flex-1">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2 flex items-center gap-1.5">
                  <Gauge className="w-3.5 h-3.5 text-cyan-400" />
                  AI Confidence Score
                </span>
                <ConfidenceGauge percent={avgConfidence} />
                <p className="text-[10px] text-slate-500 text-center mt-2">
                  {avgConfidence >= 80 ? "High confidence" : avgConfidence >= 60 ? "Moderate confidence" : "Low confidence"}
                </p>
              </div>

              {/* Forecast summary narrative */}
              <div className="glass-panel p-5 rounded-2xl border border-slate-800">
                <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Forecast Summary</h4>
                <p className="text-xs text-slate-300 leading-relaxed">
                  The {selectedModel} model predicts {trendDirection ?? "a stable"} trend in {categoryName} incidents
                  across the next quarter in {districtName}
                  {forecastData?.forecast?.length ? `, averaging ${Math.round(forecastData.forecast.reduce((s: number, f: any) => s + f.predicted, 0) / forecastData.forecast.length)} cases/month` : ""}.
                </p>
              </div>
            </div>
          </div>

          {/* Prediction Summary Details */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {forecastData?.forecast.map((f: any, idx: number) => (
              <div key={idx} className="glass-panel p-4 rounded-2xl border border-slate-800 flex flex-col justify-between space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{f.date}</span>
                  <span className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-bold px-2 py-0.5 rounded-full">Confidence: {Math.round(f.confidence * 100)}%</span>
                </div>
                <div>
                  <h4 className="text-2xl font-bold text-slate-200">{f.predicted} cases</h4>
                  <p className="text-[10px] text-slate-500 mt-1">Expected case volume for {categoryName} in {districtName}.</p>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Informational Alerts */}
      <div className="flex items-start gap-3 bg-blue-500/5 border border-blue-500/10 p-4 rounded-xl text-xs text-blue-300">
        <Info className="w-5 h-5 text-cyan-400 flex-shrink-0 mt-0.5" />
        <div className="leading-relaxed">
          <p className="font-bold uppercase tracking-wider text-slate-300 text-[10px] mb-1">Methodology Notice</p>
          Predictions are computed dynamically based on the past 24 months of geo-coded FIR histories, factoring in seasonal variances (festivals, weather, and calendar cycles) and linear growth coefficients. Dispatch commanders are advised to leverage these forecasts to optimize CCTV locations and assign auxiliary patrol cars.
        </div>
      </div>
    </div>
  );
}
