"use client";

import React, { useState, useEffect } from "react";
import { 
  LineChart, Line, BarChart, Bar, XAxis, YAxis, 
  Tooltip, ResponsiveContainer, CartesianGrid, Legend 
} from "recharts";
import { Shield, TrendingUp, UserCheck, Scale, AlertTriangle, MapPin } from "lucide-react";
import { authFetch } from "@/lib/api";

export default function DashboardView() {
  const [kpis, setKpis] = useState({
    total_firs: 250,
    arrest_rate: 80.0,
    conviction_rate: 68.5,
    monthly_growth: 5.4,
    firs_this_month: 24
  });
  const [monthlyTrends, setMonthlyTrends] = useState<any[]>([]);
  const [topDistricts, setTopDistricts] = useState<any[]>([]);
  const [hotStations, setHotStations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        // Fetch KPIs
        const kpiRes = await authFetch("/api/dashboard/kpis");
        if (kpiRes.ok) {
          const kpiData = await kpiRes.json();
          setKpis(kpiData);
        }

        // Fetch Trends
        const trendRes = await authFetch("/api/dashboard/charts/monthly-trends");
        if (trendRes.ok) {
          const trendData = await trendRes.json();
          setMonthlyTrends(trendData);
        }

        // Fetch Top Districts
        const distRes = await authFetch("/api/dashboard/top-districts");
        if (distRes.ok) {
          const distData = await distRes.json();
          setTopDistricts(distData);
        }

        // Fetch Hot Stations
        const stationRes = await authFetch("/api/dashboard/hot-stations");
        if (stationRes.ok) {
          const stationData = await stationRes.json();
          setHotStations(stationData);
        }
      } catch (err) {
        console.error("Error loading dashboard data:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-cyan-400 font-bold text-lg animate-pulse tracking-wider">LOADING COMMAND DATAFEEDS...</div>
      </div>
    );
  }

  const cardData = [
    { label: "Total FIRs Registered", value: kpis.total_firs, icon: Shield, color: "text-blue-400", change: "Historical Total" },
    { label: "Arrest Rate %", value: `${kpis.arrest_rate}%`, icon: UserCheck, color: "text-cyan-400", change: "+1.2% this quarter" },
    { label: "Conviction Rate %", value: `${kpis.conviction_rate}%`, icon: Scale, color: "text-emerald-400", change: "Active court trials" },
    { label: "Monthly Growth Rate", value: `${kpis.monthly_growth > 0 ? "+" : ""}${kpis.monthly_growth}%`, icon: TrendingUp, color: kpis.monthly_growth > 0 ? "text-red-400" : "text-emerald-400", change: `${kpis.firs_this_month} registered this month` }
  ];

  return (
    <div className="space-y-8">
      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {cardData.map((card, index) => {
          const Icon = card.icon;
          return (
            <div key={index} className="glass-panel p-6 rounded-xl border border-slate-800 flex items-start justify-between glass-panel-hover">
              <div className="space-y-2">
                <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">{card.label}</p>
                <h3 className={`text-3xl font-bold ${card.color}`}>{card.value}</h3>
                <p className="text-[10px] text-slate-500">{card.change}</p>
              </div>
              <div className={`p-3 rounded-lg bg-slate-900/60 border border-slate-800 ${card.color}`}>
                <Icon className="w-6 h-6" />
              </div>
            </div>
          );
        })}
      </div>

      {/* Main Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Crime frequency line chart */}
        <div className="glass-panel p-6 rounded-xl border border-slate-800 lg:col-span-2">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-6">Crime Frequency Monthly Trend</h3>
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={monthlyTrends}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="month" stroke="#94a3b8" fontSize={11} />
                <YAxis stroke="#94a3b8" fontSize={11} />
                <Tooltip 
                  contentStyle={{ backgroundColor: "#0f172a", border: "1px solid rgba(59, 130, 246, 0.2)", borderRadius: "8px" }}
                  labelStyle={{ color: "#f8fafc", fontWeight: "bold" }}
                />
                <Line type="monotone" dataKey="count" stroke="#3b82f6" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 8 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Top districts bar chart */}
        <div className="glass-panel p-6 rounded-xl border border-slate-800">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-6">Top District Rankings</h3>
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topDistricts} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" stroke="#94a3b8" fontSize={10} />
                <YAxis dataKey="district" type="category" stroke="#94a3b8" fontSize={10} width={90} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#0f172a", border: "1px solid rgba(59, 130, 246, 0.2)", borderRadius: "8px" }}
                />
                <Bar dataKey="count" fill="#06b6d4" radius={[0, 4, 4, 0]} barSize={18} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Auxiliary Details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Hot Stations Lists */}
        <div className="glass-panel p-6 rounded-xl border border-slate-800">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-4 flex items-center gap-2">
            <MapPin className="w-5 h-5 text-cyan-400" />
            Top Active Police Stations
          </h3>
          <div className="divide-y divide-slate-800">
            {hotStations.map((station, index) => (
              <div key={index} className="py-3.5 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-bold text-slate-500 w-5">0{index + 1}</span>
                  <span className="text-sm font-medium text-slate-200">{station.station}</span>
                </div>
                <span className="bg-slate-900 border border-slate-800 text-xs px-3 py-1 rounded-full text-slate-400 font-semibold">{station.count} FIRs</span>
              </div>
            ))}
          </div>
        </div>

        {/* Warning Board */}
        <div className="glass-panel p-6 rounded-xl border border-red-500/20 bg-red-500/5">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-red-400 mb-4 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-400 alarm-pulse" />
            Anomalous Growth Warning Board
          </h3>
          <div className="space-y-4">
            <div className="p-3 bg-slate-950/60 border-l-2 border-red-500 rounded">
              <p className="text-xs text-slate-300 font-semibold uppercase">Bengaluru East District</p>
              <p className="text-sm text-slate-200 mt-1">Cyber fraud complaints spiked **+43%** compared to the trailing 30-day average. Phishing links reported active.</p>
            </div>
            <div className="p-3 bg-slate-950/60 border-l-2 border-yellow-500 rounded">
              <p className="text-xs text-slate-300 font-semibold uppercase">Mangaluru Port Zone</p>
              <p className="text-sm text-slate-200 mt-1">Narcotics distribution/NDPS cases grew **+12%** near coastal student housing coordinates.</p>
            </div>
            <div className="p-3 bg-slate-950/60 border-l-2 border-yellow-500 rounded">
              <p className="text-xs text-slate-300 font-semibold uppercase">Indiranagar PS Bounds</p>
              <p className="text-sm text-slate-200 mt-1">Vehicle theft clusters detected during night hours (22:00 - 02:00) near metro transit stations.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
