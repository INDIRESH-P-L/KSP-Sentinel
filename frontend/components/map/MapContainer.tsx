"use client";

import React, { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Hotspot, EmergingTrend } from "@/lib/types";

export type MapViewMode = "clusters" | "heatmap" | "st-clusters";

const MAROON_DEEP = "#470c13";
const MAROON = "#6e1622";
const MAROON_BRIGHT = "#98202f";
const WINE = "#7c2438";
const BRASS = "#c2a164";
const BRASS_BRIGHT = "#e8cb8e";
const DANGER = "#b03a3a";

const sub = ["a", "b", "c"];
const CARTO_BASE = sub.map((s) => `https://${s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png`);
const CARTO_LABELS = sub.map((s) => `https://${s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}.png`);

function graphiteStyle(): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: {
      carto: { type: "raster", tiles: CARTO_BASE, tileSize: 256, attribution: "© OpenStreetMap contributors © CARTO" },
      "carto-labels": { type: "raster", tiles: CARTO_LABELS, tileSize: 256 },
    },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": "#0e0c0b" } },
      {
        id: "basemap", type: "raster", source: "carto",
        paint: { "raster-opacity": 0.55, "raster-saturation": -0.72, "raster-contrast": -0.04, "raster-brightness-max": 0.66, "raster-hue-rotate": -12 },
      },
      {
        id: "labels", type: "raster", source: "carto-labels",
        paint: { "raster-opacity": 0.5, "raster-saturation": -0.5, "raster-brightness-max": 0.9 },
      },
    ],
  };
}

const lngLat = (lat: number, lng: number): [number, number] => [lng, lat];

function hotspotsGeoJSON(hotspots: Hotspot[]) {
  const max = Math.max(...hotspots.map((h) => h.intensity), 1) || 1;
  return {
    type: "FeatureCollection" as const,
    features: hotspots.map((h, i) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: lngLat(h.lat, h.lng) },
      properties: { w: Math.max(0.06, h.intensity / max), band: i % 5, intensity: h.intensity },
    })),
  };
}

function trendsGeoJSON(trends: EmergingTrend[]) {
  return {
    type: "FeatureCollection" as const,
    features: trends.map((t) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: lngLat(t.latitude, t.longitude) },
      properties: { spike: t.spike_percentage },
    })),
  };
}

function routeGeoJSON(route: [number, number][]) {
  return {
    type: "FeatureCollection" as const,
    features: [{
      type: "Feature" as const,
      geometry: { type: "LineString" as const, coordinates: route.map(([lat, lng]) => lngLat(lat, lng)) },
      properties: {},
    }],
  };
}

function pulseMarker(kind: "hq" | "trend") {
  const el = document.createElement("div");
  el.className = `ksp-mk ksp-mk-${kind}`;
  el.innerHTML = `<span class="ksp-mk-ping"></span><span class="ksp-mk-dot"></span>`;
  return el;
}

export default function CrimeMap({
  center,
  hotspots,
  patrolRoute,
  emergingTrends = [],
  viewMode = "clusters",
  focusPoint = null,
}: {
  center: [number, number];
  hotspots: Hotspot[];
  patrolRoute: [number, number][];
  emergingTrends?: EmergingTrend[];
  viewMode?: MapViewMode;
  focusPoint?: [number, number] | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const readyRef = useRef(false);
  const hqRef = useRef<maplibregl.Marker | null>(null);
  const trendRef = useRef<maplibregl.Marker[]>([]);

  // ---- Init map (once) ----
  useEffect(() => {
    if (!containerRef.current) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: graphiteStyle(),
      center: lngLat(center[0], center[1]),
      zoom: 7.8,
      pitch: reduced ? 0 : 45,
      bearing: reduced ? 0 : -10,
      maxPitch: 75,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-left");

    map.on("load", () => {
      map.addSource("hotspots", { type: "geojson", data: hotspotsGeoJSON(hotspots) });
      map.addSource("trends", { type: "geojson", data: trendsGeoJSON(emergingTrends) });
      map.addSource("route", { type: "geojson", data: routeGeoJSON(patrolRoute) });

      // Patrol route
      map.addLayer({
        id: "route-glow", type: "line", source: "route",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": BRASS_BRIGHT, "line-width": 8, "line-blur": 8, "line-opacity": 0.32 },
      });
      map.addLayer({
        id: "route-line", type: "line", source: "route",
        layout: { "line-cap": "round" },
        paint: { "line-color": BRASS_BRIGHT, "line-width": 2.4, "line-dasharray": [2, 2], "line-opacity": 0.9 },
      });

      // KDE Heatmap Mode
      map.addLayer({
        id: "hm", type: "heatmap", source: "hotspots",
        layout: { visibility: viewMode === "heatmap" ? "visible" : "none" },
        paint: {
          "heatmap-weight": ["get", "w"],
          "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 6, 1, 15, 3.5],
          "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 6, 28, 15, 60],
          "heatmap-opacity": 0.88,
          "heatmap-color": [
            "interpolate", ["linear"], ["heatmap-density"],
            0, "rgba(14,12,11,0)",
            0.15, MAROON_DEEP,
            0.35, MAROON,
            0.55, MAROON_BRIGHT,
            0.78, BRASS,
            1, BRASS_BRIGHT,
          ],
        },
      });

      // Cluster Zones Mode
      map.addLayer({
        id: "cl-glow", type: "circle", source: "hotspots",
        layout: { visibility: viewMode === "clusters" ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, ["+", 12, ["*", ["get", "w"], 28]], 15, ["+", 35, ["*", ["get", "w"], 75]]],
          "circle-color": ["step", ["get", "w"], MAROON, 0.34, WINE, 0.67, BRASS_BRIGHT],
          "circle-opacity": 0.16,
          "circle-blur": 0.8,
        },
      });
      map.addLayer({
        id: "cl", type: "circle", source: "hotspots",
        layout: { visibility: viewMode === "clusters" ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, ["+", 6, ["*", ["get", "w"], 14]], 15, ["+", 16, ["*", ["get", "w"], 38]]],
          "circle-color": ["step", ["get", "w"], MAROON, 0.34, WINE, 0.67, BRASS_BRIGHT],
          "circle-opacity": 0.30,
          "circle-stroke-color": ["step", ["get", "w"], MAROON_BRIGHT, 0.34, WINE, 0.67, BRASS_BRIGHT],
          "circle-stroke-width": 1.5,
          "circle-stroke-opacity": 0.95,
        },
      });

      // Spatio-Temporal Mode (Banded by time-of-day/period)
      map.addLayer({
        id: "st", type: "circle", source: "hotspots",
        layout: { visibility: viewMode === "st-clusters" ? "visible" : "none" },
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, ["+", 8, ["*", ["get", "w"], 18]], 15, ["+", 20, ["*", ["get", "w"], 48]]],
          "circle-color": ["match", ["get", "band"], 0, MAROON_DEEP, 1, MAROON, 2, WINE, 3, BRASS, 4, BRASS_BRIGHT, MAROON],
          "circle-opacity": 0.32,
          "circle-stroke-color": ["match", ["get", "band"], 0, MAROON, 1, MAROON_BRIGHT, 2, WINE, 3, BRASS, 4, BRASS_BRIGHT, MAROON],
          "circle-stroke-width": 1.8,
          "circle-stroke-opacity": 0.95,
        },
      });

      // Emerging trend markers
      map.addLayer({
        id: "trend-aura", type: "circle", source: "trends",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 16, 15, 45],
          "circle-color": DANGER,
          "circle-opacity": 0.1,
          "circle-stroke-color": DANGER,
          "circle-stroke-width": 1.2,
          "circle-stroke-opacity": 0.5,
        },
      });

      // HQ marker
      const hqEl = pulseMarker("hq");
      hqRef.current = new maplibregl.Marker({ element: hqEl })
        .setLngLat(lngLat(center[0], center[1]))
        .setPopup(new maplibregl.Popup({ offset: 16, className: "ksp-popup", closeButton: false }).setHTML('<span class="ksp-pop-title">Karnataka Police HQ (Bengaluru)</span>'))
        .addTo(map);

      rebuildTrendMarkers();
      readyRef.current = true;
    });

    function rebuildTrendMarkers() {
      trendRef.current.forEach((m) => m.remove());
      trendRef.current = [];
      emergingTrends.forEach((t) => {
        const el = pulseMarker("trend");
        const m = new maplibregl.Marker({ element: el })
          .setLngLat(lngLat(t.latitude, t.longitude))
          .setPopup(
            new maplibregl.Popup({ offset: 14, className: "ksp-popup", closeButton: false }).setHTML(
              `<span class="ksp-pop-title ksp-pop-danger">Emerging Spike</span><br>+${t.spike_percentage.toFixed(1)}% in 48h window`
            )
          )
          .addTo(map);
        trendRef.current.push(m);
      });
    }

    (map as unknown as { _rebuildTrends?: () => void })._rebuildTrends = rebuildTrendMarkers;

    return () => {
      map.remove();
      mapRef.current = null;
      readyRef.current = false;
      hqRef.current = null;
      trendRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- Data updates ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    (map.getSource("hotspots") as maplibregl.GeoJSONSource | undefined)?.setData(hotspotsGeoJSON(hotspots));
  }, [hotspots]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    (map.getSource("route") as maplibregl.GeoJSONSource | undefined)?.setData(routeGeoJSON(patrolRoute));
  }, [patrolRoute]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    (map.getSource("trends") as maplibregl.GeoJSONSource | undefined)?.setData(trendsGeoJSON(emergingTrends));
    (map as unknown as { _rebuildTrends?: () => void })._rebuildTrends?.();
  }, [emergingTrends]);

  // ---- View mode toggle ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    const vis = (id: string, on: boolean) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    };
    vis("hm", viewMode === "heatmap");
    vis("cl-glow", viewMode === "clusters");
    vis("cl", viewMode === "clusters");
    vis("st", viewMode === "st-clusters");
  }, [viewMode]);

  // ---- Fly-to ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.flyTo({ center: lngLat(center[0], center[1]), speed: 0.7, curve: 1.4, essential: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [center[0], center[1]]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focusPoint) return;
    map.flyTo({ center: lngLat(focusPoint[0], focusPoint[1]), zoom: 14, pitch: 55, speed: 0.85, curve: 1.5, essential: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusPoint]);

  return <div ref={containerRef} className="h-full w-full" />;
}
