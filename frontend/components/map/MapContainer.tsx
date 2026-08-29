"use client";

import React, { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Hotspot, EmergingTrend } from "@/lib/types";

export type MapViewMode = "clusters" | "heatmap" | "st-clusters" | "satellite";

// Palette comes from the one canonical module. These were seven local literals that
// had to be kept in step with six other files by hand -- and had already drifted.
import { MAROON_DEEP, MAROON, MAROON_BRIGHT, WINE, BRASS, BRASS_BRIGHT, BRASS_DIM, DANGER, GRAPHITE, WHITE } from "@/lib/palette";

const sub = ["a", "b", "c"];
const CARTO_BASE = sub.map((s) => `https://${s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png`);
const CARTO_LABELS = sub.map((s) => `https://${s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}.png`);
// Keyless satellite imagery. Like the CARTO basemap this needs no API key and no
// billing account, which is the whole reason this component runs on MapLibre rather
// than the Google Maps SDK -- that path rendered a blank grey box on every install
// because NEXT_PUBLIC_GOOGLE_MAPS_API_KEY was never set anywhere in the project.
const ESRI_SATELLITE =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

function graphiteStyle(): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: {
      carto: { type: "raster", tiles: CARTO_BASE, tileSize: 256, attribution: "© OpenStreetMap contributors © CARTO" },
      "carto-labels": { type: "raster", tiles: CARTO_LABELS, tileSize: 256 },
      satellite: {
        type: "raster", tiles: [ESRI_SATELLITE], tileSize: 256,
        attribution: "Imagery © Esri, Maxar, Earthstar Geographics",
      },
    },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": GRAPHITE } },
      // Hidden until the Satellite layer is selected. Declared here (rather than
      // added on demand) so the toggle is a visibility flip with no tile refetch.
      {
        id: "satellite", type: "raster", source: "satellite",
        layout: { visibility: "none" },
        paint: { "raster-opacity": 0.92, "raster-saturation": -0.3, "raster-brightness-max": 0.88 },
      },
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

/** Parses the WKT `MULTIPOLYGON(((lng lat, ...)), ...)` string the districts API
 *  returns into GeoJSON. Returns null for anything unparseable rather than throwing,
 *  so a malformed geometry hides the outline instead of blanking the whole map. */
function districtGeoJSON(wkt?: string) {
  if (!wkt || !wkt.trim().toUpperCase().startsWith("MULTIPOLYGON")) return null;
  const body = wkt.replace(/^\s*MULTIPOLYGON\s*/i, "").trim();
  const inner = body.replace(/^\(\(\(/, "").replace(/\)\)\)\s*$/, "");
  const polygons = inner.split(")), ((").map((poly) =>
    poly.split("), (").map((ring) =>
      ring
        .split(",")
        .map((pt) => pt.trim().split(/\s+/).map(Number) as [number, number])
        .filter(([lng, lat]) => Number.isFinite(lng) && Number.isFinite(lat)),
    ).filter((ring) => ring.length >= 4),
  ).filter((poly) => poly.length > 0);

  if (!polygons.length) return null;
  return {
    type: "FeatureCollection" as const,
    features: [{
      type: "Feature" as const,
      properties: {},
      geometry: { type: "MultiPolygon" as const, coordinates: polygons },
    }],
  };
}

const EMPTY_FC = { type: "FeatureCollection" as const, features: [] };

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
  /** WKT MULTIPOLYGON outline of the selected district, from /api/districts. */
  districtGeom?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const readyRef = useRef(false);
  const hqRef = useRef<maplibregl.Marker | null>(null);
  const trendRef = useRef<maplibregl.Marker[]>([]);
  
  const centerRef = useRef(center);
  const hotspotsRef = useRef(hotspots);
  const routeRef = useRef(patrolRoute);
  const trendsRef = useRef(emergingTrends);
  const stationsRef = useRef(stations || []);
  const onMarkerClickRef = useRef(onMarkerClick);
  const districtGeomRef = useRef(districtGeom);

  useEffect(() => { centerRef.current = center; }, [center]);
  useEffect(() => { hotspotsRef.current = hotspots; }, [hotspots]);
  useEffect(() => { routeRef.current = patrolRoute; }, [patrolRoute]);
  useEffect(() => { trendsRef.current = emergingTrends; }, [emergingTrends]);
  useEffect(() => { stationsRef.current = stations || []; }, [stations]);
  useEffect(() => { onMarkerClickRef.current = onMarkerClick; }, [onMarkerClick]);
  useEffect(() => { districtGeomRef.current = districtGeom; }, [districtGeom]);

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
      map.addSource("hotspots", { type: "geojson", data: hotspotsGeoJSON(hotspotsRef.current) });
      map.addSource("trends", { type: "geojson", data: trendsGeoJSON(trendsRef.current) });
      map.addSource("route", { type: "geojson", data: routeGeoJSON(routeRef.current) });
      
      const stationsGeoJSON = {
        type: "FeatureCollection" as const,
        features: stationsRef.current.map((s) => ({
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates: lngLat(s.latitude, s.longitude) },
          properties: { name: s.name, district: s.district },
        })),
      };
      map.addSource("stations", { type: "geojson", data: stationsGeoJSON });
      map.addSource("district", { type: "geojson", data: districtGeoJSON(districtGeomRef.current) ?? EMPTY_FC });

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

      // All Police Stations Marker Layer
      map.addLayer({
        id: "stations-layer", type: "circle", source: "stations",
        paint: {
          "circle-radius": 4,
          "circle-color": BRASS_DIM, // dim gold -- no cool hue belongs in this palette
          "circle-stroke-color": WHITE,
          "circle-stroke-width": 1,
          "circle-opacity": 0.8
        },
      });

      // KDE Heatmap Mode
      // District outline sits directly above the basemap so hotspots, clusters and the
      // patrol route all draw on top of it.
      map.addLayer({
        id: "district-fill", type: "fill", source: "district",
        paint: { "fill-color": MAROON, "fill-opacity": 0.1 },
      });
      map.addLayer({
        id: "district-line", type: "line", source: "district",
        paint: { "line-color": BRASS, "line-width": 1.4, "line-opacity": 0.65 },
      });

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
      
      const popupNode = document.createElement("div");
      popupNode.className = "flex flex-col gap-2 p-1";
      popupNode.innerHTML = `
        <span class="ksp-pop-title" style="margin-bottom: 4px;">Selected Police Station</span>
        <button id="view-records-btn" style="background: var(--color-brass); color: black; padding: 6px 10px; border-radius: 4px; font-size: 10px; font-weight: bold; cursor: pointer; border: none; width: 100%;">
          Explore FIRs &rarr;
        </button>
      `;
      popupNode.querySelector("#view-records-btn")?.addEventListener("click", () => {
        if (onMarkerClickRef.current) onMarkerClickRef.current();
      });

      hqRef.current = new maplibregl.Marker({ element: hqEl })
        .setLngLat(lngLat(centerRef.current[0], centerRef.current[1]))
        .setPopup(new maplibregl.Popup({ offset: 16, className: "ksp-popup", closeButton: false }).setDOMContent(popupNode))
        .addTo(map);

      rebuildTrendMarkers();
      readyRef.current = true;
    });

    function rebuildTrendMarkers() {
      trendRef.current.forEach((m) => m.remove());
      trendRef.current = [];
      trendsRef.current.forEach((t) => {
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

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current || !stations) return;
    const stationsGeoJSON = {
      type: "FeatureCollection" as const,
      features: stations.map((s) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: lngLat(s.latitude, s.longitude) },
        properties: { name: s.name, district: s.district },
      })),
    };
    (map.getSource("stations") as maplibregl.GeoJSONSource | undefined)?.setData(stationsGeoJSON);
  }, [stations]);

  // ---- View mode toggle ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    const vis = (id: string, on: boolean) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    };
    vis("satellite", viewMode === "satellite");
    // The dark raster basemap is hidden under satellite so the imagery is not tinted
    // by the graphite wash; labels stay on, since an unlabelled satellite view of
    // Karnataka is unusable for dispatch.
    vis("basemap", viewMode !== "satellite");
    vis("hm", viewMode === "heatmap");
    vis("cl-glow", viewMode === "clusters");
    vis("cl", viewMode === "clusters");
    vis("st", viewMode === "st-clusters");
  }, [viewMode]);

  // ---- District outline + fit-to-bounds ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    const fc = districtGeoJSON(districtGeom);
    (map.getSource("district") as maplibregl.GeoJSONSource | undefined)?.setData(fc ?? EMPTY_FC);
    if (!fc) return;

    // Frame the whole district. Computed from the parsed ring coordinates rather than
    // a fixed zoom, so Bengaluru Urban and Kalaburagi both fill the viewport sensibly.
    const bounds = new maplibregl.LngLatBounds();
    for (const poly of fc.features[0].geometry.coordinates) {
      for (const ring of poly) {
        for (const [lng, lat] of ring) bounds.extend([lng, lat]);
      }
    }
    if (!bounds.isEmpty()) {
      map.fitBounds(bounds, { padding: 56, duration: 900, maxZoom: 11 });
    }
  }, [districtGeom]);

  // ---- Fly-to ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const newCenter = lngLat(center[0], center[1]);
    map.flyTo({ center: newCenter, speed: 0.7, curve: 1.4, essential: true });
    if (hqRef.current) {
      hqRef.current.setLngLat(newCenter);
    }
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
