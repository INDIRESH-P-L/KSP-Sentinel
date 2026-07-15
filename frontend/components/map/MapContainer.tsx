"use client";

import React, { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, Circle, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.heat";

// Fix standard marker icons in Leaflet + React
const DefaultIcon = L.icon({
  iconUrl: "https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

// Custom pulsing divIcon for emerging trends
const createPulsingIcon = () => {
  return L.divIcon({
    html: `
      <div class="relative flex items-center justify-center w-6 h-6">
        <span class="absolute inline-flex h-full w-full rounded-full bg-red-500/40 animate-ping"></span>
        <span class="relative inline-flex rounded-full h-3 w-3 bg-red-600 border border-white"></span>
      </div>
    `,
    className: "custom-pulsing-marker",
    iconSize: [24, 24],
    iconAnchor: [12, 12]
  });
};

// Custom active controller to center the map dynamically
function MapController({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, map.getZoom());
  }, [center, map]);
  return null;
}

// Imperative KDE heat layer — react-leaflet has no built-in heatmap component, and
// leaflet.heat operates directly on the underlying Leaflet map instance.
function HeatLayer({ points }: { points: { lat: number; lng: number; intensity: number }[] }) {
  const map = useMap();
  useEffect(() => {
    if (!points || points.length === 0) return;
    const heat = L.heatLayer(
      points.map(p => [p.lat, p.lng, p.intensity]),
      { radius: 28, blur: 22, maxZoom: 17, gradient: { 0.2: "#1d4ed8", 0.5: "#eab308", 0.8: "#f97316", 1.0: "#ef4444" } }
    );
    heat.addTo(map);
    return () => {
      map.removeLayer(heat);
    };
  }, [points, map]);
  return null;
}

const ST_CLUSTER_COLORS: [number, number, string][] = [
  [22, 4, "#1d4ed8"],   // late night / pre-dawn
  [4, 12, "#22c55e"],   // morning
  [12, 18, "#eab308"],  // afternoon
  [18, 22, "#f97316"],  // evening
  [22, 24, "#ef4444"],  // night
];

function colorForHour(hour: number) {
  for (const [start, end, color] of ST_CLUSTER_COLORS) {
    if (start > end) {
      if (hour >= start || hour < end) return color;
    } else if (hour >= start && hour < end) {
      return color;
    }
  }
  return "#94a3b8";
}

export default function LeafletMapContainer({
  stationLocation,
  firs,
  hotspots,
  patrolRoute,
  emergingTrends = [],
  viewMode = "clusters",
  heatmapPoints = [],
  stClusters = []
}: {
  stationLocation: [number, number];
  firs: any[];
  hotspots: any[];
  patrolRoute: any[];
  emergingTrends?: any[];
  viewMode?: "clusters" | "heatmap" | "st-clusters";
  heatmapPoints?: { lat: number; lng: number; intensity: number }[];
  stClusters?: any[];
}) {
  const routeCoords = patrolRoute.map(pt => [pt.lat, pt.lng] as [number, number]);

  return (
    <div className="w-full h-full relative rounded-xl overflow-hidden border border-slate-800">
      <MapContainer 
        center={stationLocation} 
        zoom={13} 
        scrollWheelZoom={true} 
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />
        
        {/* Dynamic map center controller */}
        <MapController center={stationLocation} />

        {/* Station HQ Marker */}
        <Marker position={stationLocation}>
          <Popup>
            <div className="text-slate-100 text-xs font-semibold p-1">
              🏢 Active Station HQ
            </div>
          </Popup>
        </Marker>

        {/* Render individual FIRs */}
        {firs.map((fir, idx) => (
          <Circle
            key={`fir-${idx}`}
            center={[fir.latitude, fir.longitude]}
            radius={20}
            pathOptions={{ color: "#ef4444", fillColor: "#ef4444", fillOpacity: 0.6 }}
          >
            <Popup>
              <div className="space-y-1.5 p-1 max-w-[200px] text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-100">{fir.fir_number}</span>
                  <span className="text-[9px] font-semibold text-cyan-400 bg-cyan-500/10 px-1.5 py-0.5 rounded">{fir.status}</span>
                </div>
                <p className="text-[10px] text-slate-300 font-semibold">{fir.subcategory}</p>
                <p className="text-[9px] text-slate-400 italic line-clamp-3">"{fir.description}"</p>
              </div>
            </Popup>
          </Circle>
        ))}

        {/* Render Hotspot density zones (plain DBSCAN cluster circles) */}
        {viewMode === "clusters" && hotspots.map((hot, idx) => (
          <Circle
            key={`hot-${idx}`}
            center={hot.center}
            radius={300}
            pathOptions={{
              color: "#f97316",
              fillColor: "#f97316",
              fillOpacity: 0.15,
              dashArray: "4 4"
            }}
          />
        ))}

        {/* Real Gaussian KDE density surface */}
        {viewMode === "heatmap" && <HeatLayer points={heatmapPoints} />}

        {/* ST-DBSCAN clusters, colored by dominant time-of-day so a night hotspot and a
            daytime one at the same street corner read as visually distinct */}
        {viewMode === "st-clusters" && stClusters.map((c, idx) => (
          <Circle
            key={`st-${idx}`}
            center={c.center}
            radius={200 + c.size * 40}
            pathOptions={{
              color: colorForHour(c.dominant_hour),
              fillColor: colorForHour(c.dominant_hour),
              fillOpacity: 0.25,
              weight: 2
            }}
          >
            <Popup>
              <div className="space-y-1 p-1 text-xs">
                <p className="font-bold text-slate-100">Spatio-temporal cluster #{c.cluster_id}</p>
                <p className="text-slate-300">{c.size} incidents</p>
                <p className="text-slate-300">Dominant hour: {Math.round(c.dominant_hour)}:00</p>
              </div>
            </Popup>
          </Circle>
        ))}

        {/* Render Emerging Trend Spikes (Pulsing Red Halos) */}
        {emergingTrends.map((trend, idx) => (
          <React.Fragment key={`trend-frag-${idx}`}>
            <Marker 
              position={[trend.latitude, trend.longitude]} 
              icon={createPulsingIcon()}
            >
              <Popup>
                <div className="space-y-1.5 p-1.5 max-w-[220px] text-xs">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-1.5 mb-1">
                    <span className="font-bold text-red-400 uppercase tracking-wider text-[9px]">🚨 Emerging Spike</span>
                    <span className="text-[9px] font-bold text-red-200 bg-red-500/20 px-1.5 py-0.5 rounded">+{trend.growth_rate}%</span>
                  </div>
                  <p className="text-[10px] text-slate-100 font-bold">{trend.category_name}</p>
                  <p className="text-[9px] text-slate-400 italic leading-relaxed">"{trend.description}"</p>
                </div>
              </Popup>
            </Marker>
            <Circle
              center={[trend.latitude, trend.longitude]}
              radius={450}
              pathOptions={{
                color: "#ef4444",
                fillColor: "#ef4444",
                fillOpacity: 0.05,
                weight: 1.5,
                dashArray: "6 4"
              }}
            />
          </React.Fragment>
        ))}

        {/* Render optimal patrol route */}
        {routeCoords.length > 1 && (
          <Polyline
            positions={routeCoords}
            pathOptions={{ 
              color: "#06b6d4", 
              weight: 3, 
              dashArray: "10 8",
              lineCap: "round"
            }}
          />
        )}
      </MapContainer>
    </div>
  );
}
