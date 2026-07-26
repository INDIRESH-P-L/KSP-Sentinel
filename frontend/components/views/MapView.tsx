"use client";

import React, { useState, useEffect, useMemo, useContext, useCallback } from "react";
import dynamic from "next/dynamic";
import { Layers, Flame, Boxes, MapPin, Navigation, Shield, Building2, Globe } from "lucide-react";
import { publicFetch } from "@/lib/api";
import { SectionTitle, PanelLabel, Loading, Gauge, Stat } from "@/components/ui/primitives";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { BRASS_BRIGHT, MAROON_BRIGHT, WINE, DANGER } from "@/lib/chart-theme";
import type { Hotspot, EmergingTrend } from "@/lib/types";
import type { MapViewMode } from "@/components/map/MapContainer";
import { TabContext } from "@/components/layout/Shell";

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
  { id: "satellite", label: "Satellite View", icon: Globe },
];

export default function MapView() {
  const { navigateTo } = useContext(TabContext);
  
  const [viewMode, setViewMode] = useState<MapViewMode>("clusters");
  const [timeWindow, setTimeWindow] = useState("all");
  
  // Selection State
  const [districts, setDistricts] = useState<any[]>([]);
  const [stations, setStations] = useState<any[]>([]);
  const [filteredStations, setFilteredStations] = useState<any[]>([]);
  const [selectedDistrictId, setSelectedDistrictId] = useState<number | null>(null);
  const [selectedStationId, setSelectedStationId] = useState<number | null>(null);

  // Map Data State
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [trends, setTrends] = useState<EmergingTrend[]>([]);
  const [loading, setLoading] = useState(true);
  const [mapCenter, setMapCenter] = useState<[number, number]>(BLR);
  const [focusPoint, setFocusPoint] = useState<[number, number] | null>(null);

  const handleMarkerClick = useCallback(() => {
    if (selectedDistrictId && selectedStationId) {
      navigateTo("records", { districtId: selectedDistrictId, stationId: selectedStationId });
    }
  }, [selectedDistrictId, selectedStationId, navigateTo]);

  // 1. Fetch Districts and Stations on Mount
  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const [distRes, statRes, trendsRes] = await Promise.all([
          publicFetch("/api/districts/"),
          publicFetch("/api/districts/stations"),
          publicFetch("/api/crimes/emerging-trends")
        ]);

        if (distRes.ok) {
          const dData = await distRes.json();
          setDistricts(dData);
          if (dData.length > 0) setSelectedDistrictId(dData[0].id);
        }
        if (statRes.ok) {
          const sData = await statRes.json();
          setStations(sData);
        }
        if (trendsRes.ok) {
          const tData: { latitude: number; longitude: number; growth_rate: number }[] = await trendsRes.json();
          setTrends(tData.map((r) => ({ latitude: r.latitude, longitude: r.longitude, spike_percentage: r.growth_rate })));
        }
      } catch (e) {
        console.error("Failed to load base map data:", e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // 2. Filter Stations when District changes
  useEffect(() => {
    if (selectedDistrictId && districts.length > 0 && stations.length > 0) {
      const selectedDistrictData = districts.find(d => d.id === selectedDistrictId);
      const selectedDistrictName = selectedDistrictData?.name;
      const filtered = stations.filter(s => s.district === selectedDistrictName);
      setFilteredStations(filtered);
      
      setSelectedStationId(null);
      setHotspots([]); // Clear station-specific hotspots
      
      if (selectedDistrictData?.latitude && selectedDistrictData?.longitude) {
        setMapCenter([selectedDistrictData.latitude, selectedDistrictData.longitude]);
        setFocusPoint(null);
      } else {
        setFocusPoint(null);
      }
    }
  }, [selectedDistrictId, districts, stations]);

  // 3. Fetch Hotspots/Map Data when Station or View Mode changes
  useEffect(() => {
    if (!selectedStationId) return;

    (async () => {
      try {
        // Fly to the new station immediately
        const station = stations.find(s => s.id === selectedStationId);
        if (station && station.latitude && station.longitude) {
          setMapCenter([station.latitude, station.longitude]);
          setFocusPoint([station.latitude, station.longitude]);
        }

        if (viewMode === "heatmap") {
          const hRes = await publicFetch(`/api/districts/stations/${selectedStationId}/heatmap`);
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
          const stRes = await publicFetch(`/api/districts/stations/${selectedStationId}/st-clusters`);
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
          const cRes = await publicFetch(`/api/districts/stations/${selectedStationId}/hotspots?time_of_day=${timeWindow}`);
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
            } else {
              setHotspots([]);
            }
          }
        }
      } catch (e) {
        console.error("Failed to fetch map layer data:", e);
      }
    })();
  }, [selectedStationId, viewMode, timeWindow, stations]);

  const patrolRoute = useMemo<[number, number][]>(() => {
    if (!selectedStationId) return [];
    const station = stations.find(s => s.id === selectedStationId);
    const hq: [number, number] = station && station.latitude && station.longitude 
      ? [station.latitude, station.longitude] 
      : BLR;
    
    const top = [...hotspots].sort((a, b) => b.intensity - a.intensity).slice(0, 3);
    return [hq, ...top.map((h) => [h.lat, h.lng] as [number, number])];
  }, [hotspots, selectedStationId, stations]);

  const waypoints = useMemo(
    () => patrolRoute.map((p, i) => ({ label: i === 0 ? "Station HQ" : `Hotspot Checkpoint ${i}`, lat: p[0], lng: p[1] })),
    [patrolRoute]
  );

  const selectedDistrictData = useMemo(() => {
    return districts.find(d => d.id === selectedDistrictId) || null;
  }, [districts, selectedDistrictId]);

  if (loading) return <Loading label="Loading Interactive GIS Map & Live Data…" />;

  return (
    <div className="flex flex-col gap-[22px] fade-up h-[calc(100vh-140px)]">
      <div className="flex flex-wrap items-center justify-between gap-3 shrink-0">
        <SectionTitle>Interactive Crime Map</SectionTitle>
        <div className="flex items-center gap-3">
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
      </div>

      <div className="grid grid-cols-1 gap-[18px] lg:grid-cols-[1fr_360px] flex-1 min-h-0">
        {/* Map panel */}
        <div className="glass relative overflow-hidden p-2 flex flex-col h-full">
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

          <div className="flex-1 w-full overflow-hidden rounded-[var(--radius-well)]">
            <CrimeMap
              center={mapCenter}
              hotspots={hotspots}
              patrolRoute={patrolRoute}
              emergingTrends={trends}
              stations={filteredStations}
              onMarkerClick={handleMarkerClick}
              focusPoint={focusPoint}
              districtGeom={selectedDistrictData?.geom}
              viewMode={viewMode}
            />
          </div>
        </div>

        {/* Right rail */}
        <div className="space-y-4 overflow-y-auto pr-2 custom-scrollbar flex flex-col h-full">
          
          {/* Controls Panel */}
          <GlassPanel sweep={false} bodyClassName="p-5 flex flex-col gap-4">
            <PanelLabel className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-[var(--color-brass)]" /> Catalyst Target
            </PanelLabel>
            
            <div className="flex flex-col gap-3">
              <div>
                <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-ink-muted)] mb-1 block">District</label>
                <select
                  value={selectedDistrictId || ""}
                  onChange={(e) => setSelectedDistrictId(Number(e.target.value))}
                  className="w-full rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-black/20 px-3 py-2 text-sm text-[var(--color-ink)] focus:border-[var(--color-brass)]/50 focus:outline-none"
                >
                  {districts.map(d => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-ink-muted)] mb-1 block">Police Station</label>
                <select
                  value={selectedStationId || ""}
                  onChange={(e) => setSelectedStationId(Number(e.target.value))}
                  className="w-full rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-black/20 px-3 py-2 text-sm text-[var(--color-ink)] focus:border-[var(--color-brass)]/50 focus:outline-none"
                  disabled={filteredStations.length === 0}
                >
                  {filteredStations.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
            </div>
          </GlassPanel>

          {/* Real Threat Profile from Catalyst */}
          {selectedDistrictData && (
            <GlassPanel sweep={false} bodyClassName="p-5">
              <PanelLabel className="mb-4 text-[var(--color-brass-bright)]">District Threat Profile</PanelLabel>
              <div className="grid grid-cols-2 gap-4">
                <Gauge value={selectedDistrictData.risk_score || 0} label="Risk Score" color={BRASS_BRIGHT} />
                <Gauge value={Math.round((selectedDistrictData.urbanization_rate || 0))} label="Urbanization" color={MAROON_BRIGHT} />
                <Gauge value={Math.round((selectedDistrictData.literacy_rate || 0))} label="Literacy Ratio" color={WINE} />
                <Gauge value={Math.round((selectedDistrictData.unemployment_rate || 0))} label="Unemployment" color={DANGER} />
              </div>
            </GlassPanel>
          )}

          <GlassPanel sweep={false} bodyClassName="p-5 flex-1 min-h-0 flex flex-col">
            <PanelLabel className="mb-4 flex items-center gap-2 shrink-0">
              <Navigation className="h-4 w-4 text-[var(--color-brass)]" /> Optimal Patrol Path
            </PanelLabel>
            <p className="mb-3 text-[10px] text-[var(--color-ink-faint)] shrink-0">Select a checkpoint to fly the map there.</p>
            <div className="space-y-2 overflow-y-auto custom-scrollbar pr-1 flex-1">
              {waypoints.length === 0 && (
                <p className="text-xs text-[var(--color-ink-faint)] py-4 text-center">No hotspots detected for this configuration.</p>
              )}
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
