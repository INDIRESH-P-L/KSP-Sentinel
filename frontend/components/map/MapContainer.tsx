"use client";

import React, { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, Circle, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.heat";
import type { Hotspot, EmergingTrend } from "@/lib/types";

// Leaflet's default marker asset URLs break under bundlers; pin them explicitly.
const DefaultIcon = L.icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});
L.Marker.prototype.options.icon = DefaultIcon;

const pulsingIcon = () =>
  L.divIcon({
    html: `<span style="position:relative;display:flex;height:14px;width:14px;align-items:center;justify-content:center">
      <span style="position:absolute;height:100%;width:100%;border-radius:9999px;background:rgba(239,68,68,0.45);animation:ksp-ping 2s cubic-bezier(0,0,0.2,1) infinite"></span>
      <span style="position:relative;height:8px;width:8px;border-radius:9999px;background:#ef4444;border:1px solid #fff"></span>
    </span>`,
    className: "",
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });

function Recenter({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, map.getZoom());
  }, [center, map]);
  return null;
}

// leaflet.heat draws directly on the Leaflet instance (no react-leaflet component).
function HeatLayer({ points }: { points: Hotspot[] }) {
  const map = useMap();
  useEffect(() => {
    if (!points.length) return;
    const heat = L.heatLayer(
      points.map((p) => [p.lat, p.lng, p.intensity]),
      { radius: 30, blur: 24, maxZoom: 17, gradient: { 0.2: "#1d4ed8", 0.45: "#7c3aed", 0.7: "#f97316", 1.0: "#ef4444" } }
    );
    heat.addTo(map);
    return () => {
      map.removeLayer(heat);
    };
  }, [points, map]);
  return null;
}

export type MapViewMode = "clusters" | "heatmap" | "st-clusters";

export default function LeafletMap({
  center,
  hotspots,
  patrolRoute,
  emergingTrends = [],
  viewMode = "clusters",
}: {
  center: [number, number];
  hotspots: Hotspot[];
  patrolRoute: [number, number][];
  emergingTrends?: EmergingTrend[];
  viewMode?: MapViewMode;
}) {
  // Cluster mode: draw glowing blobs proportional to intensity.
  return (
    <MapContainer center={center} zoom={12} scrollWheelZoom style={{ height: "100%", width: "100%" }}>
      <TileLayer
        attribution='&copy; OpenStreetMap &copy; CARTO'
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />
      <Recenter center={center} />

      <Marker position={center}>
        <Popup>
          <div style={{ fontWeight: 600, fontSize: 12, padding: 2 }}>Station HQ</div>
        </Popup>
      </Marker>

      {viewMode === "heatmap" && <HeatLayer points={hotspots} />}

      {viewMode === "clusters" &&
        hotspots.map((h, i) => (
          <Circle
            key={`c-${i}`}
            center={[h.lat, h.lng]}
            radius={120 + h.intensity * 40}
            pathOptions={{
              color: h.intensity > 6 ? "#ef4444" : h.intensity > 3 ? "#a855f7" : "#3b82f6",
              fillColor: h.intensity > 6 ? "#ef4444" : h.intensity > 3 ? "#a855f7" : "#3b82f6",
              fillOpacity: 0.18,
              weight: 1,
            }}
          />
        ))}

      {viewMode === "st-clusters" &&
        hotspots.map((h, i) => (
          <Circle
            key={`st-${i}`}
            center={[h.lat, h.lng]}
            radius={180 + h.intensity * 30}
            pathOptions={{
              color: ["#1d4ed8", "#22c55e", "#eab308", "#f97316", "#ef4444"][i % 5],
              fillColor: ["#1d4ed8", "#22c55e", "#eab308", "#f97316", "#ef4444"][i % 5],
              fillOpacity: 0.22,
              weight: 2,
            }}
          >
            <Popup>
              <div style={{ fontSize: 12, padding: 2 }}>
                <b>Spatio-temporal cluster #{i + 1}</b>
                <br />
                Intensity {h.intensity.toFixed(1)}
              </div>
            </Popup>
          </Circle>
        ))}

      {emergingTrends.map((t, i) => (
        <React.Fragment key={`t-${i}`}>
          <Marker position={[t.latitude, t.longitude]} icon={pulsingIcon()}>
            <Popup>
              <div style={{ fontSize: 12, padding: 2, maxWidth: 200 }}>
                <b style={{ color: "#ef4444", textTransform: "uppercase", fontSize: 10 }}>Emerging Spike</b>
                <br />
                +{t.spike_percentage.toFixed(1)}% in 48h window
              </div>
            </Popup>
          </Marker>
          <Circle
            center={[t.latitude, t.longitude]}
            radius={500}
            pathOptions={{ color: "#ef4444", fillColor: "#ef4444", fillOpacity: 0.05, weight: 1.5, dashArray: "6 4" }}
          />
        </React.Fragment>
      ))}

      {patrolRoute.length > 1 && (
        <Polyline positions={patrolRoute} pathOptions={{ color: "#22d3ee", weight: 3, dashArray: "10 8", lineCap: "round" }} />
      )}
    </MapContainer>
  );
}
