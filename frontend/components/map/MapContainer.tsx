"use client";

import React, { useEffect, useRef, useState, useMemo } from "react";
import { GoogleMap, useJsApiLoader, HeatmapLayer, Polyline, OverlayView, MarkerF, Polygon } from "@react-google-maps/api";
import type { Hotspot, EmergingTrend } from "@/lib/types";

export type MapViewMode = "clusters" | "heatmap" | "st-clusters" | "satellite";

const MAROON_DEEP = "#470c13";
const MAROON = "#6e1622";
const MAROON_BRIGHT = "#98202f";
const WINE = "#7c2438";
const BRASS = "#c2a164";
const BRASS_BRIGHT = "#e8cb8e";
const DANGER = "#b03a3a";

// Simplified Dark Theme for Google Maps
const DARK_MAP_STYLE = [
  { elementType: "geometry", stylers: [{ color: "#0e0c0b" }] },
  { elementType: "labels.icon", stylers: [{ visibility: "off" }] },
  { elementType: "labels.text.fill", stylers: [{ color: "#757575" }] },
  { elementType: "labels.text.stroke", stylers: [{ color: "#212121" }] },
  { featureType: "administrative", elementType: "geometry", stylers: [{ color: "#757575" }] },
  { featureType: "poi", elementType: "geometry", stylers: [{ color: "#181818" }] },
  { featureType: "road", elementType: "geometry.fill", stylers: [{ color: "#2c2c2c" }] },
  { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#212a37" }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#000000" }] },
];

const GOOGLE_MAPS_LIBRARIES: ("visualization")[] = ["visualization"];

export default function CrimeMap({
  center,
  hotspots,
  patrolRoute,
  emergingTrends = [],
  viewMode = "clusters",
  focusPoint = null,
  onMarkerClick,
  stations = [],
  districtGeom,
}: {
  center: [number, number];
  hotspots: Hotspot[];
  patrolRoute: [number, number][];
  emergingTrends?: EmergingTrend[];
  viewMode?: MapViewMode;
  focusPoint?: [number, number] | null;
  onMarkerClick?: () => void;
  stations?: any[];
  districtGeom?: string;
}) {
  const { isLoaded } = useJsApiLoader({
    id: 'google-map-script',
    googleMapsApiKey: process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || "",
    libraries: GOOGLE_MAPS_LIBRARIES,
  });

  const mapRef = useRef<google.maps.Map | null>(null);
  const [hqPopupOpen, setHqPopupOpen] = useState(false);
  const [activeTrendPopup, setActiveTrendPopup] = useState<number | null>(null);
  
  const onLoad = React.useCallback((map: google.maps.Map) => {
    mapRef.current = map;
  }, []);

  const onUnmount = React.useCallback(() => {
    mapRef.current = null;
  }, []);

  // Handle Fly-To / panTo
  useEffect(() => {
    if (mapRef.current && center) {
      mapRef.current.panTo({ lat: center[0], lng: center[1] });
    }
  }, [center]);

  useEffect(() => {
    if (mapRef.current && focusPoint) {
      mapRef.current.panTo({ lat: focusPoint[0], lng: focusPoint[1] });
      mapRef.current.setZoom(14);
    }
  }, [focusPoint]);

  // Fit bounds to district outline for zoom-out effect
  useEffect(() => {
    if (!mapRef.current || !districtGeom || !districtGeom.startsWith("MULTIPOLYGON")) return;
    
    if (!window.google || !window.google.maps) return;

    const bounds = new window.google.maps.LatLngBounds();
    const polys = districtGeom
      .replace("MULTIPOLYGON", "")
      .replace(/^\s*\(\(\(/, "")
      .replace(/\)\)\)\s*$/, "")
      .split(")), ((");

    let pointCount = 0;
    polys.forEach((poly: string) => {
      poly.split("), (").forEach((ring: string) => {
        ring.split(",").forEach((point: string) => {
          const [lng, lat] = point.trim().split(/\s+/).map(Number);
          if (!isNaN(lat) && !isNaN(lng)) {
            bounds.extend({ lat, lng });
            pointCount++;
          }
        });
      });
    });

    if (pointCount > 0) {
      mapRef.current.fitBounds(bounds);
    }
  }, [districtGeom]);

  // Heatmap data
  const heatmapData = useMemo(() => {
    if (!isLoaded || !window.google) return [];
    const max = Math.max(...hotspots.map((h) => h.intensity), 1) || 1;
    return hotspots.map(h => ({
      location: new window.google.maps.LatLng(h.lat, h.lng),
      weight: Math.max(0.1, h.intensity / max),
    }));
  }, [hotspots, isLoaded]);

  // Gradient for heatmap
  const heatmapGradient = [
    "rgba(14,12,11,0)",
    MAROON_DEEP,
    MAROON,
    MAROON_BRIGHT,
    BRASS,
    BRASS_BRIGHT
  ];

  const mapCenter = useMemo(() => ({ lat: center[0], lng: center[1] }), [center]);

  if (!isLoaded) return <div className="h-full w-full flex items-center justify-center bg-black"><span className="text-white text-xs">Loading Google Maps...</span></div>;

  return (
    <GoogleMap
      mapContainerClassName="h-full w-full"
      center={mapCenter}
      zoom={7.8}
      onLoad={onLoad}
      onUnmount={onUnmount}
      options={{
        styles: viewMode === "satellite" ? undefined : DARK_MAP_STYLE,
        disableDefaultUI: false,
        zoomControl: true,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: false,
        backgroundColor: "#0e0c0b",
        mapTypeId: viewMode === "satellite" ? "satellite" : "roadmap",
      }}
    >
      {/* Heatmap Layer */}
      {viewMode === "heatmap" && heatmapData.length > 0 && (
        <HeatmapLayer
          data={heatmapData}
          options={{
            radius: 35,
            opacity: 0.88,
            gradient: heatmapGradient
          }}
        />
      )}

      {/* Cluster Zones & Spatio-Temporal */}
      {(viewMode === "clusters" || viewMode === "st-clusters") && hotspots.map((h, i) => {
        const max = Math.max(...hotspots.map((hot) => hot.intensity), 1) || 1;
        const w = Math.max(0.06, h.intensity / max);
        const band = i % 5;
        
        let fillColor = "";
        let strokeColor = "";
        if (viewMode === "clusters") {
           fillColor = w < 0.34 ? MAROON : w < 0.67 ? WINE : BRASS_BRIGHT;
           strokeColor = w < 0.34 ? MAROON_BRIGHT : w < 0.67 ? WINE : BRASS_BRIGHT;
        } else {
           fillColor = band === 0 ? MAROON_DEEP : band === 1 ? MAROON : band === 2 ? WINE : band === 3 ? BRASS : BRASS_BRIGHT;
           strokeColor = band === 0 ? MAROON : band === 1 ? MAROON_BRIGHT : band === 2 ? WINE : band === 3 ? BRASS : BRASS_BRIGHT;
        }

        const scale = 15 + (w * 25);
        
        return (
          <MarkerF
            key={`hs-${i}`}
            position={{ lat: h.lat, lng: h.lng }}
            icon={{
              path: window.google.maps.SymbolPath.CIRCLE,
              scale: scale / 2, // scale is radius
              fillColor: fillColor,
              fillOpacity: 0.32,
              strokeColor: strokeColor,
              strokeWeight: 1.5,
              strokeOpacity: 0.95,
            }}
          />
        );
      })}

      {/* Patrol Route */}
      {patrolRoute.length > 0 && (
        <>
          <Polyline
            path={patrolRoute.map(p => ({ lat: p[0], lng: p[1] }))}
            options={{
              strokeColor: BRASS_BRIGHT,
              strokeOpacity: 0.32,
              strokeWeight: 8,
              clickable: false
            }}
          />
          <Polyline
            path={patrolRoute.map(p => ({ lat: p[0], lng: p[1] }))}
            options={{
              strokeColor: BRASS_BRIGHT,
              strokeOpacity: 0.9,
              strokeWeight: 2.4,
              clickable: false,
              icons: [{
                icon: { path: "M 0,-1 0,1", strokeOpacity: 1, scale: 2 },
                offset: "0",
                repeat: "10px"
              }]
            }}
          />
        </>
      )}

      {/* Police Stations */}
      {stations && stations.map((s, i) => (
        <MarkerF
          key={`stn-${i}`}
          position={{ lat: s.latitude, lng: s.longitude }}
          icon={{
            path: window.google.maps.SymbolPath.CIRCLE,
            scale: 4,
            fillColor: "#4287f5",
            fillOpacity: 0.8,
            strokeColor: "#ffffff",
            strokeWeight: 1
          }}
        />
      ))}

      {/* Emerging Trend Auras */}
      {emergingTrends.map((t, i) => (
        <MarkerF
          key={`trend-aura-${i}`}
          position={{ lat: t.latitude, lng: t.longitude }}
          icon={{
            path: window.google.maps.SymbolPath.CIRCLE,
            scale: 25,
            fillColor: DANGER,
            fillOpacity: 0.1,
            strokeColor: DANGER,
            strokeWeight: 1.2,
            strokeOpacity: 0.5
          }}
        />
      ))}

      {/* Emerging Trend Markers & Popups */}
      {emergingTrends.map((t, i) => (
        <OverlayView
          key={`trend-mk-${i}`}
          position={{ lat: t.latitude, lng: t.longitude }}
          mapPaneName={OverlayView.OVERLAY_MOUSE_TARGET}
          getPixelPositionOffset={(width, height) => ({ x: -(width / 2), y: -(height / 2) })}
        >
          <div className="relative">
            <div className="ksp-mk ksp-mk-trend" onClick={() => setActiveTrendPopup(i === activeTrendPopup ? null : i)}>
              <span className="ksp-mk-ping"></span>
              <span className="ksp-mk-dot"></span>
            </div>
            
            {activeTrendPopup === i && (
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-max z-[100]">
                <div className="ksp-popup">
                  <span className="ksp-pop-title ksp-pop-danger">Emerging Spike</span><br/>
                  +{t.spike_percentage.toFixed(1)}% in 48h window
                </div>
              </div>
            )}
          </div>
        </OverlayView>
      ))}

      {/* HQ Marker */}
      <OverlayView
        position={mapCenter}
        mapPaneName={OverlayView.OVERLAY_MOUSE_TARGET}
        getPixelPositionOffset={(width, height) => ({ x: -(width / 2), y: -(height / 2) })}
      >
        <div className="relative">
          <div className="ksp-mk ksp-mk-hq" onClick={() => setHqPopupOpen(!hqPopupOpen)}>
            <span className="ksp-mk-ping"></span>
            <span className="ksp-mk-dot"></span>
          </div>
          
          {hqPopupOpen && (
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-max z-[100]">
               <div className="ksp-popup flex flex-col gap-2 p-1 w-32">
                <span className="ksp-pop-title" style={{ marginBottom: "4px" }}>Selected Police Station</span>
                <button 
                  onClick={(e) => { e.stopPropagation(); if (onMarkerClick) onMarkerClick(); }}
                  style={{ background: "var(--color-brass)", color: "black", padding: "6px 10px", borderRadius: "4px", fontSize: "10px", fontWeight: "bold", cursor: "pointer", border: "none", width: "100%" }}>
                  Explore FIRs &rarr;
                </button>
              </div>
            </div>
          )}
        </div>
      </OverlayView>

      {/* District Outline */}
      {districtGeom && districtGeom.startsWith("MULTIPOLYGON") && (
        <>
          {districtGeom
            .replace("MULTIPOLYGON", "")
            .replace(/^\s*\(\(\(/, "")
            .replace(/\)\)\)\s*$/, "")
            .split(")), ((")
            .map((poly: string, i: number) => (
              <Polygon
                key={`dist-poly-${i}`}
                paths={poly.split("), (").map((ring: string) =>
                  ring.split(",").map((point: string) => {
                    const [lng, lat] = point.trim().split(/\s+/).map(Number);
                    return { lat, lng };
                  })
                )}
                options={{
                  fillColor: "#c2a164", // BRASS
                  fillOpacity: 0.05,
                  strokeColor: "#c2a164",
                  strokeOpacity: 0.8,
                  strokeWeight: 2,
                  clickable: false,
                }}
              />
            ))}
        </>
      )}
    </GoogleMap>
  );
}
