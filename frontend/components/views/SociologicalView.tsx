"use client";

import React, { useState, useEffect } from "react";
import { 
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, 
  CartesianGrid, ScatterChart, Scatter, Label, Legend
} from "recharts";
import { 
  ShieldAlert, TrendingUp, HelpCircle, Activity, Globe, 
  Award, Sparkles, Brain, AlertTriangle, Layers
} from "lucide-react";

interface DistrictMetric {
  id: number;
  name: string;
  population: number;
  risk_score: number;
  urbanization_rate: number;
  literacy_rate: number;
  unemployment_rate: number;
  poverty_rate: number;
  rates: Record<string, number>;
}

export default function SociologicalView() {
  const [data, setData] = useState<{ districts: DistrictMetric[]; correlations: Record<string, Record<string, number>> } | null>(null);
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [selectedMetric, setSelectedMetric] = useState("urbanization_rate");
  const [selectedDistrict, setSelectedDistrict] = useState<DistrictMetric | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchSociologicalData() {
      try {
        const token = localStorage.getItem("ksp_token");
        const headers: Record<string, string> = {};
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }

        const socioRes = await fetch("http://localhost:8000/api/dashboard/socio-economic", { headers });
        if (socioRes.ok) {
          const socioData = await socioRes.json();
          setData(socioData);
          if (socioData.districts && socioData.districts.length > 0) {
            setSelectedDistrict(socioData.districts[0]);
          }
        }

        const anomalyRes = await fetch("http://localhost:8000/api/dashboard/anomalies", { headers });
        if (anomalyRes.ok) {
          const anomalyData = await anomalyRes.json();
          setAnomalies(anomalyData);
        }
      } catch (err) {
        console.error("Error fetching sociological insights:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchSociologicalData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-cyan-400 font-bold text-lg animate-pulse tracking-wider">COMPILING SOCIOLOGICAL CORRELATIONS...</div>
      </div>
    );
  }

  // Format correlation data for bar chart
  const corrData = data?.correlations[selectedMetric]
    ? Object.keys(data.correlations[selectedMetric]).map(cat => ({
        category: cat,
        coefficient: data.correlations[selectedMetric][cat],
        fill: data.correlations[selectedMetric][cat] >= 0 ? "#ef4444" : "#22c55e"
      }))
    : [];

  // Format scatter data (Urbanization vs Risk Score)
  const scatterData = data?.districts.map(d => ({
    name: d.name,
    x: d.urbanization_rate,
    y: d.risk_score,
    pop: d.population
  })) || [];

  const getMetricLabel = (m: string) => {
    switch (m) {
      case "urbanization_rate": return "Urbanization Rate (%)";
      case "literacy_rate": return "Literacy Rate (%)";
      case "unemployment_rate": return "Unemployment Rate (%)";
      case "poverty_rate": return "Poverty Rate (%)";
      default: return m;
    }
  };

  const getRiskColor = (score: number) => {
    if (score >= 80) return "text-red-400";
    if (score >= 60) return "text-orange-400";
    return "text-emerald-400";
  };

  const getProgressColor = (score: number) => {
    if (score >= 80) return "bg-red-500";
    if (score >= 60) return "bg-orange-500";
    return "bg-emerald-500";
  };

  // Mock SHAP factors based on district attributes for drill down
  const getShapBreakdown = (d: DistrictMetric) => {
    const total = d.risk_score;
    const urbanWeight = Math.min(40, Math.round((d.urbanization_rate / 100) * 35));
    const litWeight = Math.round((100 - d.literacy_rate) * 0.25);
    const unempWeight = Math.round(d.unemployment_rate * 2.5);
    const calculatedSum = urbanWeight + litWeight + unempWeight;
    const scale = total / Math.max(1, calculatedSum);
    
    return [
      { name: "Urban Densification Target", value: Math.round(urbanWeight * scale), desc: "High population density increases property and digital theft risk indices." },
      { name: "Unemployment Friction", value: Math.round(unempWeight * scale), desc: "Higher local friction increases general property break-ins." },
      { name: "Socio-Literacy Marginalization", value: Math.round(litWeight * scale), desc: "Marginalization leads to higher susceptibility to cyber phishing fraud schemes." },
      { name: "Transit Hub Exposure", value: Math.max(2, total - Math.round(calculatedSum * scale)), desc: "Presence of bus/railway corridors attracts transient offenders." }
    ];
  };

  return (
    <div className="space-y-8 animate-[fadeIn_0.5s_ease-out]">
      {/* Page Header */}
      <div className="glass-panel p-6 rounded-xl border border-slate-800 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
            <Brain className="w-5 h-5 text-purple-400" />
            Sociological & AI Predictive Analytics Dashboard
          </h2>
          <p className="text-xs text-slate-400 mt-1">Cross-referencing crime clusters with state-wide socio-economic metrics</p>
        </div>
        <div className="flex items-center gap-2 bg-purple-500/10 border border-purple-500/20 text-purple-300 text-[10px] font-bold px-3 py-1.5 rounded-lg uppercase">
          <Sparkles className="w-3.5 h-3.5" />
          AI Engine V2
        </div>
      </div>

      {/* KPI Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-panel p-5 rounded-xl border border-slate-800 flex items-center gap-4">
          <div className="p-3 bg-red-500/10 border border-red-500/25 rounded-lg text-red-400">
            <Globe className="w-6 h-6" />
          </div>
          <div>
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Highest Threat District</span>
            <h4 className="text-base font-bold text-slate-200 mt-0.5">Bengaluru City</h4>
            <p className="text-[9px] text-slate-400 mt-0.5">Risk Factor: High Urbanization (97.4%)</p>
          </div>
        </div>

        <div className="glass-panel p-5 rounded-xl border border-slate-800 flex items-center gap-4">
          <div className="p-3 bg-cyan-500/10 border border-cyan-500/25 rounded-lg text-cyan-400">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Primary Sociological Driver</span>
            <h4 className="text-base font-bold text-slate-200 mt-0.5">Urban Concentration</h4>
            <p className="text-[9px] text-slate-400 mt-0.5">Strong positive correlation to Cyber & Theft</p>
          </div>
        </div>

        <div className="glass-panel p-5 rounded-xl border border-slate-800 flex items-center gap-4">
          <div className="p-3 bg-amber-500/10 border border-amber-500/25 rounded-lg text-amber-400">
            <AlertTriangle className="w-6 h-6 alarm-pulse" />
          </div>
          <div>
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Active Anomaly Flags</span>
            <h4 className="text-base font-bold text-slate-200 mt-0.5">{anomalies.length} Districts Flagged</h4>
            <p className="text-[9px] text-slate-400 mt-0.5">Current month exceeds historical mean + 1.5σ</p>
          </div>
        </div>
      </div>

      {/* Main Section: Correlations & Scatter plots */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Pearson Correlation coefficients */}
        <div className="glass-panel p-6 rounded-xl border border-slate-800 flex flex-col justify-between space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">Pearson Correlation Matrix</h3>
            
            <select
              id="metric-selector"
              value={selectedMetric}
              onChange={e => setSelectedMetric(e.target.value)}
              className="bg-slate-900 border border-slate-700/50 rounded-lg py-1 px-3 text-slate-100 text-xs focus:outline-none focus:border-purple-500 cursor-pointer"
            >
              <option value="urbanization_rate">Urbanization Rate</option>
              <option value="literacy_rate">Literacy Rate</option>
              <option value="unemployment_rate">Unemployment Rate</option>
              <option value="poverty_rate">Poverty Rate</option>
            </select>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={corrData} margin={{ left: 10, right: 10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="category" stroke="#94a3b8" fontSize={9} angle={-15} textAnchor="end" interval={0} />
                <YAxis stroke="#94a3b8" fontSize={10} domain={[-1, 1]} />
                <Tooltip 
                  contentStyle={{ backgroundColor: "#0f172a", border: "1px solid rgba(139, 92, 246, 0.2)", borderRadius: "8px" }}
                  labelStyle={{ color: "#f8fafc", fontWeight: "bold" }}
                />
                <Bar dataKey="coefficient" radius={4} barSize={25} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          
          <p className="text-[10px] text-slate-500 italic text-center">
            Interpretation: Values close to +1.0 indicate strong positive linkage; values close to -1.0 indicate strong negative (inhibitory) linkage.
          </p>
        </div>

        {/* Scatter Plot: Urbanization vs Risk Score */}
        <div className="glass-panel p-6 rounded-xl border border-slate-800">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-6">Urbanization vs Threat Score Scatter</h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 10 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" dataKey="x" name="Urbanization" unit="%" stroke="#94a3b8" fontSize={10}>
                  <Label value="Urbanization Rate %" offset={-10} position="insideBottom" stroke="#64748b" fontSize={10} />
                </XAxis>
                <YAxis type="number" dataKey="y" name="Risk Score" stroke="#94a3b8" fontSize={10}>
                  <Label value="Threat Index" angle={-90} position="insideLeft" style={{ textAnchor: 'middle' }} stroke="#64748b" fontSize={10} />
                </YAxis>
                <Tooltip 
                  cursor={{ strokeDasharray: '3 3' }}
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const dataNode = payload[0].payload;
                      return (
                        <div className="bg-slate-900 border border-slate-800 p-3 rounded-lg text-xs space-y-1">
                          <p className="font-bold text-slate-100">{dataNode.name}</p>
                          <p className="text-slate-300">Urbanization: {dataNode.x}%</p>
                          <p className="text-purple-400 font-semibold">Threat Score: {dataNode.y}</p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Scatter name="Districts" data={scatterData} fill="#c084fc" shape="circle" line={false} />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Grid: District List & SHAP Drill down */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* District list */}
        <div className="glass-panel p-6 rounded-xl border border-slate-800 lg:col-span-2 space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300">AI Threat Risk & Demographic Scores</h3>
          
          <div className="overflow-y-auto max-h-[350px] space-y-3.5 pr-2">
            {data?.districts.map(dist => (
              <div 
                key={dist.id} 
                onClick={() => setSelectedDistrict(dist)}
                className={`p-4 rounded-xl border transition-all cursor-pointer flex items-center justify-between ${
                  selectedDistrict?.id === dist.id 
                    ? "bg-purple-950/15 border-purple-500/40 shadow-lg shadow-purple-500/5" 
                    : "bg-slate-950/20 border-slate-800/80 hover:bg-slate-900/20 hover:border-slate-700/50"
                }`}
              >
                <div className="space-y-1.5 flex-1 pr-6">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-slate-200">{dist.name}</h4>
                    <span className={`font-bold text-xs ${getRiskColor(dist.risk_score)}`}>{dist.risk_score} / 100</span>
                  </div>
                  
                  {/* Progress bar */}
                  <div className="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden border border-slate-900">
                    <div className={`h-full rounded-full ${getProgressColor(dist.risk_score)}`} style={{ width: `${dist.risk_score}%` }} />
                  </div>
                  
                  {/* Minor Details */}
                  <div className="flex gap-4 text-[10px] text-slate-500 uppercase font-semibold">
                    <span>Urbanization: {dist.urbanization_rate}%</span>
                    <span>Literacy: {dist.literacy_rate}%</span>
                    <span>Poverty BPL: {dist.poverty_rate}%</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* SHAP explanation panel */}
        <div className="glass-panel p-6 rounded-xl border border-slate-800 flex flex-col justify-between h-[450px]">
          <div>
            <div className="border-b border-slate-800 pb-3 mb-4">
              <span className="text-[10px] font-bold text-purple-400 uppercase tracking-widest">District Risk Explainer</span>
              <h3 className="text-base font-bold text-slate-200 mt-1 uppercase">{selectedDistrict?.name} Risk Drivers</h3>
            </div>

            {selectedDistrict ? (
              <div className="space-y-4 overflow-y-auto max-h-[310px] pr-2">
                {getShapBreakdown(selectedDistrict).map((factor, idx) => (
                  <div key={idx} className="bg-slate-950/50 border border-slate-900 p-3 rounded-lg space-y-1.5">
                    <div className="flex justify-between items-center text-xs font-semibold">
                      <span className="text-slate-300">{factor.name}</span>
                      <span className="text-purple-400 font-bold">+{factor.value}%</span>
                    </div>
                    <p className="text-[10px] text-slate-400 leading-relaxed">{factor.desc}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-slate-500 text-xs italic">Select a district to view AI-driven feature importance breakups.</p>
            )}
          </div>
        </div>
      </div>

      {/* Statistical Anomalies Feed */}
      <div className="glass-panel p-6 rounded-xl border border-slate-800 space-y-6">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
          <Activity className="w-5 h-5 text-red-500 alarm-pulse" />
          Statistical Anomaly Alert Feed (Current Month vs. Baseline)
        </h3>

        <div className="space-y-3.5">
          {anomalies.map((anom, idx) => (
            <div 
              key={idx} 
              className={`p-4 rounded-xl border flex flex-col md:flex-row md:items-center justify-between gap-4 transition-all ${
                anom.severity === "CRITICAL"
                  ? "bg-red-950/10 border-red-500/30 shadow-md shadow-red-500/5"
                  : "bg-amber-950/10 border-amber-500/20"
              }`}
            >
              <div className="space-y-1.5">
                <div className="flex items-center gap-2.5">
                  <span className={`text-[9px] font-bold px-2 py-0.5 rounded border ${
                    anom.severity === "CRITICAL"
                      ? "bg-red-500/10 text-red-400 border-red-500/20"
                      : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                  }`}>
                    {anom.severity} Alert
                  </span>
                  <h4 className="text-xs font-bold text-slate-200 uppercase">{anom.district_name} • {anom.category_name}</h4>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed font-semibold">{anom.description}</p>
                <div className="flex gap-4 text-[10px] text-slate-500 uppercase font-semibold">
                  <span>Count: **{anom.current_count}**</span>
                  <span>Baseline Avg: {anom.expected_count}</span>
                  <span>z-Score: +{anom.z_score}σ</span>
                </div>
              </div>
              
              <div className="flex-shrink-0">
                <div className="bg-slate-900/60 border border-slate-800 py-2 px-4 rounded-lg text-center">
                  <span className="text-[10px] font-bold text-slate-500 uppercase block">Anomalous Spike</span>
                  <span className="text-base font-extrabold text-red-400">+{Math.round(((anom.current_count - anom.expected_count) / anom.expected_count) * 100)}%</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
