"use client";

import React, { useState, useEffect, useMemo } from "react";
import dynamic from "next/dynamic";
import { Layers, Flame, Boxes, MapPin, Navigation } from "lucide-react";
import { authFetch } from "@/lib/api";
import { SectionTitle, PanelLabel, Loading, Gauge, Stat } from "@/components/ui/primitives";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { BRASS_BRIGHT, MAROON_BRIGHT, WINE, DANGER } from "@/lib/chart-theme";
import { mockHotspots } from "@/lib/mock";
import type { Hotspot, EmergingTrend } from "@/lib/types";
import type { MapViewMode } from "@/components/map/MapContainer";

// maplibre-gl touches window/WebGL — must be client-only (no SSR under output:export).
const CrimeMap = dynamic(() => import("@/components/map/MapContainer"), {
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

export default function MapView() {
  const [viewMode, setViewMode] = useState<MapViewMode>("clusters");
  const [timeWindow, setTimeWindow] = useState("all");
  const [hotspots, setHotspots] = useState<Hotspot[]>(mockHotspots);
  const [trends, setTrends] = useState<EmergingTrend[]>([]);
  const [loading, setLoading] = useState(true);
  const [focusPoint, setFocusPoint] = useState<[number, number] | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const hRes = await authFetch(`/api/districts/stations/1/hotspots?time_of_day=${timeWindow}`);
        if (hRes.ok) {
          const data = await hRes.json();
          const clusters: { center: [number, number]; size: number }[] = data?.hotspots ?? [];
          if (clusters.length > 0) {
            const maxSize = Math.max(...clusters.map((c) => c.size), 1);
            setHotspots(
              clusters.map((c) => ({
                lat: c.center[0],
                lng: c.center[1],
                intensity: c.size / maxSize,
              }))
            );
          }
        }
        const tRes = await authFetch("/api/crimes/emerging-trends");
        if (tRes.ok) {
          const rows: { latitude: number; longitude: number; growth_rate: number }[] = await tRes.json();
          setTrends(rows.map((r) => ({ latitude: r.latitude, longitude: r.longitude, spike_percentage: r.growth_rate })));
        }
      } catch (e) {
        console.error("MapView error:", e);
      } finally {
        setLoading(false);
      }
    })();
  }, [timeWindow]);

  // Mode changes (KDE Heatmap, ST Clusters, Cluster Zones)
  useEffect(() => {
    (async () => {
      try {
        if (viewMode === "heatmap") {
          const hRes = await authFetch("/api/districts/stations/1/heatmap");
          if (hRes.ok) {
            const data = await hRes.json();
            if (data.density_surface?.points) {
              setHotspots(
                data.density_surface.points.map(([lat, lng, val]: [number, number, number]) => ({
                  lat,
                  lng,
                  intensity: val,
                }))
              );
            }
          }
        } else if (viewMode === "st-clusters") {
          const stRes = await authFetch("/api/districts/stations/1/st-clusters");
          if (stRes.ok) {
            const data = await stRes.json();
            if (data.clusters) {
              setHotspots(
                data.clusters.map((c: any) => ({
                  lat: c.center[0],
                  lng: c.center[1],
                  intensity: Math.min(1.0, (c.size || 5) / 20),
                }))
              );
            }
          }
        } else {
          const cRes = await authFetch(`/api/districts/stations/1/hotspots?time_of_day=${timeWindow}`);
          if (cRes.ok) {
            const data = await cRes.json();
            const clusters: { center: [number, number]; size: number }[] = data?.hotspots ?? [];
            if (clusters.length > 0) {
              const maxSize = Math.max(...clusters.map((c) => c.size), 1);
              setHotspots(
                clusters.map((c) => ({
                  lat: c.center[0],
                  lng: c.center[1],
                  intensity: c.size / maxSize,
                }))
              );
            }
          }
        }
      } catch (e) {
        console.error("Mode fetch error:", e);
      }
    })();
  }, [viewMode, timeWindow]);

  const patrolRoute = useMemo<[number, number][]>(() => {
    const top = [...hotspots].sort((a, b) => b.intensity - a.intensity).slice(0, 3);
    return [BLR, ...top.map((h) => [h.lat, h.lng] as [number, number])];
  }, [hotspots]);

  const waypoints = useMemo(
    () => patrolRoute.map((p, i) => ({ label: i === 0 ? "Station HQ" : `Hotspot Checkpoint ${i}`, lat: p[0], lng: p[1] })),
    [patrolRoute]
  );

  if (loading) return <Loading label="Loading Interactive GIS Map…" />;

  return (
    <div className="flex flex-col gap-[22px] fade-up">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionTitle>Interactive Crime Map</SectionTitle>
        <select
          value={timeWindow}
          onChange={(e) => setTimeWindow(e.target.value)}
          className="rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)] px-3.5 py-2 text-xs font-semibold text-[var(--color-ink-muted)] focus:outline-none"
        >
          {TIME_WINDOWS.map((t) => (
            <option key={t.id} value={t.id}>{t.label}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-1 gap-[18px] lg:grid-cols-[1fr_320px]">
        {/* Map panel */}
        <div className="glass relative overflow-hidden p-2">
          {/* Mode Toggles */}
          <div className="absolute right-5 top-5 z-[500] flex flex-col gap-2">
            {LAYERS.map((l) => {
              const Icon = l.icon;
              const active = viewMode === l.id;
              return (
                <button
                  key={l.id}
                  onClick={() => setViewMode(l.id)}
                  className={`flex items-center gap-2 rounded-full border px-4 py-2 text-xs font-bold backdrop-blur-md transition-all duration-300 ${
                    active
                      ? "border-[var(--color-brass)]/60 bg-[var(--color-brass)]/25 text-[var(--color-brass-bright)] shadow-lg shadow-black/50"
                      : "glass-chip text-[var(--color-ink-muted)] hover:text-[var(--color-ink)] hover:bg-[var(--color-brass)]/10"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {l.label}
                </button>
              );
            })}
          </div>

          <div className="h-[620px] w-full overflow-hidden rounded-[var(--radius-well)]">
            <CrimeMap
              center={BLR}
              hotspots={hotspots}
              patrolRoute={patrolRoute}
              emergingTrends={trends}
              viewMode={viewMode}
              focusPoint={focusPoint}
            />
          </div>
        </div>

        {/* Right rail */}
        <div className="space-y-5">
          <GlassPanel sweep={false} bodyClassName="p-5">
            <PanelLabel className="mb-4">District Threat Profile</PanelLabel>
            <div className="grid grid-cols-2 gap-4">
              <Gauge value={70} label="Security Index" color={BRASS_BRIGHT} />
              <Gauge value={80} label="Urbanization" color={MAROON_BRIGHT} />
              <Gauge value={70} label="Literacy Ratio" color={WINE} />
              <Gauge value={70} label="Unemployment" color={DANGER} />
            </div>
          </GlassPanel>

          <GlassPanel sweep={false} bodyClassName="p-5">
            <PanelLabel className="mb-4 flex items-center gap-2">
              <Navigation className="h-4 w-4 text-[var(--color-brass)]" /> Optimal Patrol Path
            </PanelLabel>
            <p className="mb-3 text-[10px] text-[var(--color-ink-faint)]">Select a checkpoint to fly the map there.</p>
            <div className="space-y-2">
              {waypoints.map((w, i) => (
                <button
                  key={i}
                  onClick={() => setFocusPoint([w.lat, w.lng])}
                  className="flex w-full items-center gap-3 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-ivory)]/[0.02] p-3 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-[var(--color-brass)]/40 hover:bg-[var(--color-brass)]/[0.06]"
                >
                  <Stat className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-brass)]/15 text-[11px] font-bold text-[var(--color-brass-bright)]">
                    {i + 1}
                  </Stat>
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold text-[var(--color-ink)]">{w.label}</p>
                    <Stat className="block text-[10px] text-[var(--color-ink-faint)]">
                      {w.lat.toFixed(4)}, {w.lng.toFixed(4)}
                    </Stat>
                  </div>
                  <MapPin className="ml-auto h-3.5 w-3.5 shrink-0 text-[var(--color-ink-faint)]" />
                </button>
              ))}
            </div>
          </GlassPanel>
        </div>
      </div>
    </div>
  );
}
