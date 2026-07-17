"use client";

import React, { useState, useEffect, useContext } from "react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis,
  Tooltip, ResponsiveContainer, CartesianGrid
} from "recharts";
import { Shield, TrendingUp, UserCheck, Scale, AlertTriangle, MapPin, Brain, ArrowUpRight } from "lucide-react";
import { authFetch } from "@/lib/api";
import { TabContext } from "@/components/layout/Shell";

export default function DashboardView() {
  const { navigateTo } = useContext(TabContext);
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

  const growthPositive = kpis.monthly_growth > 0;

  return (
    <div className="space-y-6">
      {/* Bento row 1: featured Total-FIRs card (with embedded sparkline) + two compact stat cards */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Featured card -- spans 2 columns, carries a decorative sparkline built from
            the same monthly-trend data the line chart below uses in full detail. */}
        <div className="lg:col-span-2 glass-panel p-7 rounded-2xl border border-slate-800 glass-panel-hover flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Total FIRs Registered</p>
              <h3 className="text-5xl font-bold tracking-tight text-blue-400 mt-2">{kpis.total_firs.toLocaleString()}</h3>
              <span className="inline-block mt-3 text-[10px] font-semibold text-slate-400 bg-slate-900/60 border border-slate-800 rounded-full px-2.5 py-1">
                {kpis.firs_this_month} filed this month
              </span>
            </div>
            <div className="p-3 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400">
              <Shield className="w-6 h-6" />
            </div>
          </div>
          {monthlyTrends.length > 0 && (
            <div className="h-16 -mb-2 mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={monthlyTrends}>
                  <Line type="monotone" dataKey="count" stroke="#60a5fa" strokeWidth={2.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="glass-panel p-6 rounded-2xl border border-slate-800 glass-panel-hover">
          <div className="flex items-start justify-between mb-4">
            <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Arrest Rate</p>
            <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
              <UserCheck className="w-5 h-5" />
            </div>
          </div>
          <h3 className="text-4xl font-bold tracking-tight text-cyan-400">{kpis.arrest_rate}%</h3>
          <span className="inline-block mt-3 text-[10px] font-semibold text-slate-400 bg-slate-900/60 border border-slate-800 rounded-full px-2.5 py-1">
            +1.2% this quarter
          </span>
        </div>

        <div className="glass-panel p-6 rounded-2xl border border-slate-800 glass-panel-hover">
          <div className="flex items-start justify-between mb-4">
            <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Conviction Rate</p>
            <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <Scale className="w-5 h-5" />
            </div>
          </div>
          <h3 className="text-4xl font-bold tracking-tight text-emerald-400">{kpis.conviction_rate}%</h3>
          <span className="inline-block mt-3 text-[10px] font-semibold text-slate-400 bg-slate-900/60 border border-slate-800 rounded-full px-2.5 py-1">
            Active court trials
          </span>
        </div>
      </div>

      {/* Bento row 2: growth-rate strip (wide, horizontal) + AI forecast engine teaser */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-2 glass-panel p-6 rounded-2xl border border-slate-800 glass-panel-hover flex items-center gap-5">
          <div className={`p-3.5 rounded-xl border ${growthPositive ? "bg-red-500/10 border-red-500/20 text-red-400" : "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"}`}>
            <TrendingUp className="w-6 h-6" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Monthly Growth Rate</p>
            <div className="flex items-baseline gap-2 mt-1">
              <h3 className={`text-3xl font-bold tracking-tight ${growthPositive ? "text-red-400" : "text-emerald-400"}`}>
                {growthPositive ? "+" : ""}{kpis.monthly_growth}%
              </h3>
              <span className="text-xs text-slate-500">vs. previous month</span>
            </div>
          </div>
        </div>

        <button
          onClick={() => navigateTo("forecast")}
          className="lg:col-span-2 glass-panel p-6 rounded-2xl border border-purple-500/20 glass-panel-hover flex items-center gap-5 text-left cursor-pointer group"
        >
          <div className="p-3.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
            <Brain className="w-6 h-6" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">AI Forecast Engine</p>
            <div className="flex items-center gap-2 mt-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 alarm-pulse"></span>
              <h3 className="text-lg font-bold text-slate-100">Active &middot; Stable predictions</h3>
            </div>
          </div>
          <ArrowUpRight className="w-5 h-5 text-slate-600 group-hover:text-purple-400 transition-colors shrink-0" />
        </button>
      </div>

      {/* Main Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Crime frequency line chart */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800 lg:col-span-2">
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
        <div className="glass-panel p-6 rounded-2xl border border-slate-800">
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
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Hot Stations Lists */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800">
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
        <div className="glass-panel p-6 rounded-2xl border border-red-500/20 bg-red-500/5">
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
