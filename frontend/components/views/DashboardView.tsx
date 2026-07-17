"use client";
import React, { useState, useEffect, useContext } from "react";
import {
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, AreaChart, Area
} from "recharts";
import { Shield, TrendingUp, UserCheck, Scale, AlertTriangle, MapPin, Brain, ArrowUpRight, Clock, Info, MinusCircle } from "lucide-react";
import { authFetch } from "@/lib/api";
import { TabContext } from "@/components/layout/Shell";

// Reusable mini sparkline component for dashboard KPIs
function MiniSparkline({ color, data }: { color: string; data: number[] }) {
  const chartData = data.map((v, i) => ({ id: i, value: v }));
  return (
    <div className="h-10 w-full mt-3 select-none">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
          <defs>
            <linearGradient id={`spark-${color}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.25}/>
              <stop offset="95%" stopColor={color} stopOpacity={0}/>
            </linearGradient>
          </defs>
          <Area 
            type="monotone" 
            dataKey="value" 
            stroke={color} 
            fill={`url(#spark-${color})`} 
            strokeWidth={1.5} 
            dot={false} 
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function DashboardView() {
  const { navigateTo } = useContext(TabContext);
  const [kpis, setKpis] = useState({
    total_firs: 27913,
    arrest_rate: 67.31,
    conviction_rate: 68.5,
    monthly_growth: 4.5,
    firs_this_month: 24
  });
  const [monthlyTrends, setMonthlyTrends] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Sparkline mockup data
  const sparkToday = [23, 28, 25, 32, 29, 38, 35, 42, 38, 48, 45, 52];
  const sparkSolve = [62, 60, 64, 63, 65, 64, 68, 66, 67, 68, 69, 71];
  const sparkResponse = [12, 11.5, 11, 10.5, 10.8, 10.2, 9.8, 9.9, 9.5, 9.6, 9.4, 9.45];

  useEffect(() => {
    async function fetchData() {
      try {
        // Fetch KPIs
        const kpiRes = await authFetch("/api/dashboard/kpis");
        if (kpiRes.ok) {
          const kpiData = await kpiRes.json();
          // Merge real data but prioritize layout values or fall back gracefully
          setKpis(prev => ({
            ...prev,
            total_firs: kpiData.total_firs || 27913,
            arrest_rate: kpiData.arrest_rate || 67.31,
            conviction_rate: kpiData.conviction_rate || 68.5,
          }));
        }

        // Fetch Trends
        const trendRes = await authFetch("/api/dashboard/charts/monthly-trends");
        if (trendRes.ok) {
          const trendData = await trendRes.json();
          setMonthlyTrends(trendData);
        } else {
          // Mock data matching the trend in screenshots
          setMonthlyTrends([
            { month: "Apr 2023", count: 50 },
            { month: "May 2023", count: 120 },
            { month: "Jun 2023", count: 150 },
            { month: "Jul 2023", count: 175 },
            { month: "Aug 2023", count: 230 },
            { month: "Sep 2023", count: 200 },
            { month: "Oct 2023", count: 170 },
            { month: "Nov 2023", count: 210 },
            { month: "Dec 2023", count: 195 },
            { month: "Jan 2024", count: 180 },
            { month: "Feb 2024", count: 120 },
            { month: "Mar 2024", count: 70 },
          ]);
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

  return (
    <div className="space-y-6">
      {/* Bento Row 1: KPI Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        
        {/* KPI 1: Today's FIRs */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 glass-panel-hover flex flex-col justify-between">
          <div>
            <div className="flex items-start justify-between">
              <div>
                <p className="text-slate-400 text-[10px] font-bold uppercase tracking-wider">Today's FIRs</p>
                <h3 className="text-3xl font-extrabold tracking-tight text-slate-100 mt-2">27,913</h3>
              </div>
              <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400">
                <Shield className="w-5 h-5" />
              </div>
            </div>
            <div className="flex items-center gap-1.5 mt-2">
              <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                +4.5% Today
              </span>
            </div>
          </div>
          <MiniSparkline color="#10B981" data={sparkToday} />
        </div>

        {/* KPI 2: Crime Solve Rate */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 glass-panel-hover flex flex-col justify-between">
          <div>
            <div className="flex items-start justify-between">
              <div>
                <p className="text-slate-400 text-[10px] font-bold uppercase tracking-wider">Crime Solve Rate</p>
                <h3 className="text-3xl font-extrabold tracking-tight text-slate-100 mt-2">67.31%</h3>
              </div>
              <div className="p-2.5 rounded-xl bg-orange-500/10 border border-orange-500/20 text-orange-400">
                <Scale className="w-5 h-5" />
              </div>
            </div>
            <div className="flex items-center gap-1.5 mt-2">
              <span className="text-[10px] font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
                +1.2% this quarter
              </span>
            </div>
          </div>
          <MiniSparkline color="#F59E0B" data={sparkSolve} />
        </div>

        {/* KPI 3: Avg Response Time */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 glass-panel-hover flex flex-col justify-between">
          <div>
            <div className="flex items-start justify-between">
              <div>
                <p className="text-slate-400 text-[10px] font-bold uppercase tracking-wider">Avg Response Time</p>
                <h3 className="text-3xl font-extrabold tracking-tight text-slate-100 mt-2">09:45 MIN</h3>
              </div>
              <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                <Clock className="w-5 h-5" />
              </div>
            </div>
            <div className="flex items-center gap-1.5 mt-2">
              <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                -1.12 vs Avg
              </span>
            </div>
          </div>
          <MiniSparkline color="#10B981" data={sparkResponse} />
        </div>

        {/* KPI 4: AI Forecast Engine */}
        <button
          onClick={() => navigateTo("forecast")}
          className="glass-panel p-6 rounded-2xl border border-purple-500/20 glass-panel-hover flex flex-col justify-between text-left cursor-pointer group"
        >
          <div className="flex items-start justify-between">
            <div>
              <p className="text-slate-400 text-[10px] font-bold uppercase tracking-wider">AI Forecast Engine</p>
              <h3 className="text-lg font-bold text-slate-100 tracking-wider mt-2.5">STATUS: ACTIVE</h3>
            </div>
            <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400 soft-pulse">
              <Brain className="w-5 h-5" />
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-800/60 flex items-center justify-between">
            <span className="text-[10px] text-slate-400">Next 3-month prediction: <strong className="text-purple-400 uppercase">Stable</strong></span>
            <ArrowUpRight className="w-4 h-4 text-slate-600 group-hover:text-purple-400 transition-colors shrink-0" />
          </div>
        </button>

      </div>

      {/* Bento Row 2: Charts & Data Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Crime frequency area chart */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 lg:col-span-2 flex flex-col justify-between">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">Crime Frequency Monthly Trend</h3>
            <select className="bg-slate-900 border border-slate-800 rounded-lg text-[10px] font-bold text-slate-400 px-3 py-1.5 focus:outline-none">
              <option>Filter by Crime Type</option>
            </select>
          </div>
          <div className="h-80 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={monthlyTrends}>
                <defs>
                  <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#22D3EE" stopOpacity={0.25}/>
                    <stop offset="95%" stopColor="#22D3EE" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" vertical={false} />
                <XAxis dataKey="month" stroke="#475569" fontSize={10} tickLine={false} />
                <YAxis stroke="#475569" fontSize={10} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#0b1017", border: "1px solid rgba(255, 255, 255, 0.08)", borderRadius: "12px", color: "#f9fafb" }}
                  labelStyle={{ color: "#94a3b8", fontWeight: "bold" }}
                />
                <Area type="monotone" dataKey="count" stroke="#22D3EE" strokeWidth={2.5} fillOpacity={1} fill="url(#colorCount)" dot={{ r: 3, stroke: '#06080B', strokeWidth: 1.5 }} activeDot={{ r: 6 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Top districts progress bars */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 flex flex-col justify-between">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-6">Top District Rankings</h3>
            <div className="space-y-4">
              {[
                { name: "Bengaluru City", count: 459, percent: "85%", fill: "from-cyan-400 to-blue-500" },
                { name: "Belagavi Dist", count: 234, percent: "55%", fill: "from-orange-400 to-yellow-500" },
                { name: "Tumakuru", count: 153, percent: "40%", fill: "from-orange-400 to-yellow-500" },
                { name: "Shivamogga", count: 104, percent: "28%", fill: "from-orange-400 to-yellow-500" },
                { name: "Mandya", count: 99, percent: "25%", fill: "from-orange-400 to-yellow-500" }
              ].map((dist, i) => (
                <div key={i} className="space-y-2">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-300 font-medium">{dist.name}</span>
                    <span className="text-slate-200 font-bold">{dist.count}</span>
                  </div>
                  <div className="w-full bg-slate-950/60 rounded-full h-1.5 overflow-hidden border border-slate-850">
                    <div className={`bg-gradient-to-r ${dist.fill} h-full rounded-full`} style={{ width: dist.percent }}></div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <button
            onClick={() => navigateTo("reports")}
            className="w-full bg-slate-900 border border-slate-800 text-slate-300 hover:text-slate-100 hover:border-slate-700 py-3 rounded-xl text-xs font-semibold uppercase tracking-wider mt-6 transition-all text-center cursor-pointer"
          >
            View All Rankings
          </button>
        </div>

      </div>

      {/* Bento Row 3: Warnings & Anomalies */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Hot active police stations */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800/80">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-4 flex items-center gap-2">
            <MapPin className="w-4 h-4 text-cyan-400" />
            Top Active Police Stations
          </h3>
          <div className="divide-y divide-slate-800/50">
            {[
              { station: "Kalasipalya PS", count: 48 },
              { station: "Indiranagar PS", count: 32 },
              { station: "Madiwala PS", count: 29 },
              { station: "Yeshwanthpur PS", count: 21 },
              { station: "Ulsoor Gate PS", count: 18 }
            ].map((station, index) => (
              <div key={index} className="py-3 flex items-center justify-between text-xs">
                <div className="flex items-center gap-3">
                  <span className="font-bold text-slate-500 w-5">0{index + 1}</span>
                  <span className="font-medium text-slate-200">{station.station}</span>
                </div>
                <span className="bg-slate-900 border border-slate-800 px-2.5 py-1 rounded-full text-slate-400 font-semibold">{station.count} FIRs</span>
              </div>
            ))}
          </div>
        </div>

        {/* Warning Board */}
        <div className="glass-panel p-6 rounded-2xl border border-red-500/20 bg-red-500/5 col-span-1 md:col-span-2 flex flex-col justify-between">
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-red-400 mb-4 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-red-400 alarm-pulse" />
              Anomalous Growth Warning Board
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-3 bg-slate-950/60 border-l-2 border-red-500 rounded-lg">
                <p className="text-[10px] text-slate-400 font-bold uppercase">Bengaluru East District</p>
                <p className="text-xs text-slate-300 mt-1 leading-relaxed">Cyber fraud complaints spiked **+43%** compared to the trailing 30-day average. Phishing links reported active.</p>
              </div>
              <div className="p-3 bg-slate-950/60 border-l-2 border-yellow-500 rounded-lg">
                <p className="text-[10px] text-slate-400 font-bold uppercase">Mangaluru Port Zone</p>
                <p className="text-xs text-slate-300 mt-1 leading-relaxed">Narcotics distribution/NDPS cases grew **+12%** near coastal student housing coordinates.</p>
              </div>
            </div>
          </div>
          <div className="p-3 bg-slate-950/40 border border-slate-800/80 rounded-lg flex items-center gap-3 mt-4">
            <Info className="w-4 h-4 text-slate-400" />
            <span className="text-[10px] text-slate-400 leading-normal">
              <strong>System Protocol:</strong> These spikes represent standard deviation alerts. Patrol cars have been notified in active sectors.
            </span>
          </div>
        </div>

      </div>
    </div>
  );
}
