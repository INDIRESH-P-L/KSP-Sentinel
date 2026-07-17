"use client";

import React, { useState, useEffect } from "react";
import { FileSpreadsheet, AlertTriangle, ShieldCheck, ChevronRight, X, Database } from "lucide-react";
import { authFetch } from "@/lib/api";

export default function ReportsView() {
  const [rankings, setRankings] = useState<any[]>([]);
  const [selectedDistrict, setSelectedDistrict] = useState<any | null>(null);
  const [explanation, setExplanation] = useState<any | null>(null);
  const [loadingExpl, setLoadingExpl] = useState(false);
  const [loadingRank, setLoadingRank] = useState(true);

  useEffect(() => {
    async function loadRankings() {
      try {
        const res = await authFetch("/api/districts/rankings");
        if (res.ok) {
          const data = await res.json();
          setRankings(data);
        }
      } catch (e) {
        console.error("Error loading rankings:", e);
      } finally {
        setLoadingRank(false);
      }
    }
    loadRankings();
  }, []);

  const handleExplainRisk = async (dist: any) => {
    setSelectedDistrict(dist);
    setLoadingExpl(true);
    setExplanation(null);
    try {
      const res = await authFetch(`/api/districts/${dist.id}/explain-risk`);
      if (res.ok) {
        const data = await res.json();
        setExplanation(data);
      }
    } catch (e) {
      console.error("Error loading risk explanation:", e);
    } finally {
      setLoadingExpl(false);
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

  return (
    <div className="space-y-6 relative">
      {/* Downloads Panel */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="glass-panel p-6 rounded-2xl border border-slate-800 flex items-center justify-between glass-panel-hover">
          <div className="flex items-center gap-4 min-w-0">
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 shrink-0">
              <Database className="w-5 h-5" />
            </div>
            <div className="space-y-1 min-w-0">
              <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">District Risk Ledger</h4>
              <p className="text-[10px] text-slate-400">Export safety indices and demographic summaries</p>
            </div>
          </div>
          <a
            href="http://localhost:8000/api/export/csv/district-report"
            className="flex items-center gap-2 bg-slate-900 border border-slate-700/80 hover:border-cyan-400 hover:text-cyan-400 text-slate-300 font-semibold py-2.5 px-5 rounded-xl text-xs transition-all cursor-pointer shrink-0"
          >
            <FileSpreadsheet className="w-4 h-4" />
            Export
          </a>
        </div>

        <div className="glass-panel p-6 rounded-2xl border border-slate-800 flex items-center justify-between glass-panel-hover">
          <div className="flex items-center gap-4 min-w-0">
            <div className="p-3 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 shrink-0">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
            <div className="space-y-1 min-w-0">
              <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider">FIR Record Database</h4>
              <p className="text-[10px] text-slate-400">Export all geocoded complaint rows in CSV format</p>
            </div>
          </div>
          <a
            href="http://localhost:8000/api/export/csv/crime-records"
            className="flex items-center gap-2 bg-slate-900 border border-slate-700/80 hover:border-cyan-400 hover:text-cyan-400 text-slate-300 font-semibold py-2.5 px-5 rounded-xl text-xs transition-all cursor-pointer shrink-0"
          >
            <FileSpreadsheet className="w-4 h-4" />
            Export
          </a>
        </div>
      </div>

      {/* Main Table Rankings */}
      <div className="glass-panel p-6 rounded-2xl border border-slate-800">
        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 mb-6 flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-emerald-400" />
          Karnataka Districts Security Rankings
        </h3>

        {loadingRank ? (
          <div className="py-12 text-center">
            <span className="text-cyan-400 font-bold text-xs animate-pulse tracking-widest">LOADING LEDGER RECORDS...</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border-collapse">
              <thead>
                <tr className="bg-slate-900 border-b border-slate-800 text-slate-400">
                  <th className="px-6 py-3 font-semibold uppercase tracking-wider w-16">Rank</th>
                  <th className="px-6 py-3 font-semibold uppercase tracking-wider">District Name</th>
                  <th className="px-6 py-3 font-semibold uppercase tracking-wider">Crime rate (Per Lakh)</th>
                  <th className="px-6 py-3 font-semibold uppercase tracking-wider">Conviction Rate %</th>
                  <th className="px-6 py-3 font-semibold uppercase tracking-wider">Threat Score</th>
                  <th className="px-6 py-3 font-semibold uppercase tracking-wider text-right">XAI Profile</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 bg-slate-950/20">
                {rankings.map((dist) => (
                  <tr key={dist.id} className="hover:bg-slate-900/35 transition-colors">
                    <td className="px-6 py-4 font-bold text-slate-500">#{dist.rank}</td>
                    <td className="px-6 py-4 font-semibold text-slate-200">{dist.name}</td>
                    <td className="px-6 py-4 text-slate-300">{dist.crime_rate_per_lakh} cases</td>
                    <td className="px-6 py-4 text-slate-300">{dist.conviction_rate}%</td>
                    <td className={`px-6 py-4 font-bold ${getRiskColor(dist.risk_score)}`}>{dist.risk_score} / 100</td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleExplainRisk(dist)}
                        className="flex items-center gap-1 bg-blue-500/10 border border-blue-500/25 hover:border-cyan-400 hover:text-cyan-400 text-slate-300 px-3.5 py-1.5 rounded-full text-[10px] font-bold uppercase transition-all ml-auto cursor-pointer"
                      >
                        Explain Risk
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* XAI Sliding Side Drawer */}
      {selectedDistrict && (
        <div className="fixed inset-y-0 right-0 w-full max-w-lg bg-slate-900 border-l border-slate-800 shadow-2xl p-8 z-50 overflow-y-auto space-y-6">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Explainable AI Diagnose</span>
              <h3 className="text-lg font-bold text-slate-100 uppercase mt-1">{selectedDistrict.name} Threat Profile</h3>
            </div>
            <button
              onClick={() => setSelectedDistrict(null)}
              className="p-1.5 hover:bg-slate-850 rounded-full text-slate-400 hover:text-slate-100 transition-all cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {loadingExpl ? (
            <div className="py-24 text-center">
              <span className="text-cyan-400 font-bold text-xs animate-pulse tracking-widest uppercase">DISSECTING DISTRICT RISK SHAP VALUES...</span>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Score bar */}
              <div className="space-y-2.5">
                <div className="flex justify-between items-center text-xs font-semibold text-slate-300 uppercase">
                  <span>Crime Hazard Index</span>
                  <span className={`font-bold ${getRiskColor(explanation?.risk_score)}`}>{explanation?.risk_score} / 100</span>
                </div>
                <div className="w-full bg-slate-950 h-2.5 rounded-full overflow-hidden border border-slate-800">
                  <div
                    className={`h-full rounded-full ${getProgressColor(explanation?.risk_score)}`}
                    style={{ width: `${explanation?.risk_score}%` }}
                  />
                </div>
              </div>

              {/* SHAP Breakdown Bar */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">SHAP Feature Importance Breakdown</h4>

                {explanation?.factors && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-[11px] text-slate-300">
                      <span>Crime Density Factors</span>
                      <span className="font-semibold">+{explanation.factors.historical_density}%</span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slate-300">
                      <span>Recidivism / Repeat Offenders</span>
                      <span className="font-semibold">+{explanation.factors.recidivism}%</span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slate-300">
                      <span>Seasonal / Calendar Cycles</span>
                      <span className="font-semibold">+{explanation.factors.seasonality}%</span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slate-300">
                      <span>Infrastructure (Tech parks/Transit stands)</span>
                      <span className="font-semibold">+{explanation.factors.urban_density}%</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Explanations Details */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Threat Factor Interpretations</h4>
                <div className="space-y-2.5">
                  {explanation?.explanations.map((txt: string, idx: number) => (
                    <div key={idx} className="bg-slate-950/40 border border-slate-800/80 p-3 rounded-lg text-xs text-slate-300 leading-relaxed">{txt}</div>
                  ))}
                </div>
              </div>

              {/* Patrol recommendations */}
              <div className="bg-blue-500/5 border border-blue-500/10 p-5 rounded-xl space-y-3">
                <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4 text-cyan-400 alarm-pulse" />
                  Tactical Patrol Guidelines
                </h4>
                <ul className="space-y-2">
                  {explanation?.recommendations.map((rec: string, idx: number) => (
                    <li key={idx} className="list-disc ml-4 text-[11px] text-slate-300 leading-relaxed">{rec}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
