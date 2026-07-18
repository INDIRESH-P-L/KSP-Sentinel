"use client";

import React, { useState, useEffect, useMemo } from "react";
import dynamic from "next/dynamic";
import { Layers, Flame, Boxes, MapPin, Navigation } from "lucide-react";
import { authFetch } from "@/lib/api";
import { SectionTitle, PanelLabel, Loading } from "@/components/ui/primitives";
import { mockHotspots } from "@/lib/mock";
import type { Hotspot, EmergingTrend } from "@/lib/types";
import type { MapViewMode } from "@/components/map/MapContainer";

// react-leaflet touches window/document — must be client-only (no SSR under output:export).
const LeafletMap = dynamic(() => import("@/components/map/MapContainer"), {
  ssr: false,
  loading: () => <Loading label="Initializing GIS basemap…" />,
});

const BLR: [number, number] = [12.9716, 77.5946];

const TIME_WINDOWS = [
  { id: "all", label: "All Day" },
  { id: "morning", label: "Morning · 06–12" },
  { id: "afternoon", label: "Afternoon · 12–18" },
  { id: "evening", label: "Evening · 18–22" },
  { id: "night", label: "Night · 22–06" },
];

const LAYERS: { id: MapViewMode; label: string; icon: React.ElementType }[] = [
  { id: "clusters", label: "Cluster Zones", icon: Layers },
  { id: "heatmap", label: "KDE Heatmap", icon: Flame },
  { id: "st-clusters", label: "Spatio-Temporal", icon: Boxes },
];

function Gauge({ value, label, color }: { value: number; label: string; color: string }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  const dash = (value / 100) * c;
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative h-16 w-16">
        <svg viewBox="0 0 64 64" className="h-full w-full -rotate-90">
          <circle cx="32" cy="32" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="6" />
          <circle cx="32" cy="32" r={r} fill="none" stroke={color} strokeWidth="6" strokeLinecap="round" strokeDasharray={`${dash} ${c}`} />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-sm font-bold text-[var(--color-ink)]">{value}%</span>
      </div>
      <span className="text-center text-[10px] font-medium leading-tight text-[var(--color-ink-faint)]">{label}</span>
    </div>
  );
}

export default function MapView() {
  const [viewMode, setViewMode] = useState<MapViewMode>("heatmap");
  const [timeWindow, setTimeWindow] = useState("all");
  const [hotspots, setHotspots] = useState<Hotspot[]>(mockHotspots);
  const [trends, setTrends] = useState<EmergingTrend[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const hRes = await authFetch("/api/districts/stations/1/hotspots");
        if (hRes.ok) setHotspots(await hRes.json());
        const tRes = await authFetch("/api/crimes/emerging-trends");
        if (tRes.ok) setTrends(await tRes.json());
      } catch {
        /* mock fallback */
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Deterministic patrol path from the strongest hotspots + HQ.
  const patrolRoute = useMemo<[number, number][]>(() => {
    const top = [...hotspots].sort((a, b) => b.intensity - a.intensity).slice(0, 3);
    return [BLR, ...top.map((h) => [h.lat, h.lng] as [number, number])];
  }, [hotspots]);

  const waypoints = useMemo(
    () => patrolRoute.map((p, i) => ({ label: i === 0 ? "Station HQ" : `Hotspot Checkpoint ${i}`, lat: p[0], lng: p[1] })),
    [patrolRoute]
  );

  if (loading) return <Loading />;

  return (
    <div className="space-y-6 fade-up">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionTitle>Interactive Crime Map</SectionTitle>
        <select
          value={timeWindow}
          onChange={(e) => setTimeWindow(e.target.value)}
          className="rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)] px-3 py-2 text-xs font-semibold text-[var(--color-ink-muted)] focus:outline-none"
        >
          {TIME_WINDOWS.map((t) => (
            <option key={t.id} value={t.id}>{t.label}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_320px]">
        {/* Map panel */}
        <div className="glass relative overflow-hidden p-2">
          <div className="absolute right-5 top-5 z-[500] flex flex-col gap-2">
            {LAYERS.map((l) => {
              const Icon = l.icon;
              const active = viewMode === l.id;
              return (
                <button
                  key={l.id}
                  onClick={() => setViewMode(l.id)}
                  className={`flex items-center gap-2 rounded-full border px-3.5 py-2 text-xs font-semibold backdrop-blur-md transition-all ${
                    active
                      ? "border-[var(--color-accent-cyan)]/40 bg-[var(--color-accent-cyan)]/15 text-[var(--color-accent-cyan)]"
                      : "border-[var(--color-hairline)] bg-[var(--color-surface)]/80 text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {l.label}
                </button>
              );
            })}
          </div>
          <div className="h-[560px] w-full overflow-hidden rounded-[var(--radius-well)]">
            <LeafletMap center={BLR} hotspots={hotspots} patrolRoute={patrolRoute} emergingTrends={trends} viewMode={viewMode} />
          </div>
        </div>

        {/* Right rail */}
        <div className="space-y-5">
          <div className="glass p-5">
            <PanelLabel className="mb-4">District Threat Profile</PanelLabel>
            <div className="grid grid-cols-2 gap-4">
              <Gauge value={70} label="Security Index" color="#22d3ee" />
              <Gauge value={80} label="Urbanization" color="#3b82f6" />
              <Gauge value={70} label="Literacy Ratio" color="#a855f7" />
              <Gauge value={70} label="Unemployment" color="#ef4444" />
            </div>
          </div>

          <div className="glass p-5">
            <PanelLabel className="mb-4 flex items-center gap-2">
              <Navigation className="h-4 w-4 text-[var(--color-accent-cyan)]" /> Optimal Patrol Path
            </PanelLabel>
            <div className="space-y-2">
              {waypoints.map((w, i) => (
                <div key={i} className="flex items-center gap-3 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-white/[0.02] p-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent-cyan)]/15 text-[11px] font-bold text-[var(--color-accent-cyan)]">
                    {i + 1}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold text-[var(--color-ink)]">{w.label}</p>
                    <p className="font-mono text-[10px] text-[var(--color-ink-faint)]">
                      {w.lat.toFixed(4)}, {w.lng.toFixed(4)}
                    </p>
                  </div>
                  <MapPin className="ml-auto h-3.5 w-3.5 shrink-0 text-[var(--color-ink-faint)]" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
