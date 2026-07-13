"use client";

import React, { useEffect, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, Circle, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix standard marker icons in Leaflet + React
const DefaultIcon = L.icon({
  iconUrl: "https://unpkg.com/leaflet@1.7.1/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

// Custom active controller to center the map dynamically
function MapController({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, map.getZoom());
  }, [center, map]);
  return null;
}

export default function LeafletMapContainer({ 
  stationLocation, 
  firs, 
  hotspots, 
  patrolRoute 
}: { 
  stationLocation: [number, number]; 
  firs: any[]; 
  hotspots: any[]; 
  patrolRoute: any[]; 
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

        {/* Render Hotspot density zones */}
        {hotspots.map((hot, idx) => (
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
