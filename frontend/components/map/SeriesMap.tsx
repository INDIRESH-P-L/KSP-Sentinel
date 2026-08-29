"use client";

import React, { useEffect, useMemo, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { CrimeSeries } from "@/lib/types";
import { GRAPHITE, BRASS, BRASS_BRIGHT, MAROON_BRIGHT, DANGER, WARN } from "@/lib/palette";

/**
 * The track of a serial run, and where it is forecast to continue.
 *
 * Three layers, in the order a reader needs them:
 *   1. the offence sequence, drawn as a numbered path so the direction of travel is
 *      visible rather than inferred;
 *   2. the forecast search area, as a ring sized to the analysis' own radius — never a
 *      pin, because a pin would imply an address the evidence cannot support;
 *   3. the epicentre, marked but subordinate to the ring.
 *
 * The ring pulses only while a forecast window is open or overdue. That is the single
 * piece of motion on the map, and it encodes state rather than decorating: a series that
 * is not currently due does not pulse.
 */

const sub = ["a", "b", "c"];
const CARTO_BASE = sub.map((s) => `https://${s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png`);
const CARTO_LABELS = sub.map((s) => `https://${s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}.png`);

function graphiteStyle(): maplibregl.StyleSpecification {
  return {
    version: 8,
    sources: {
      carto: {
        type: "raster", tiles: CARTO_BASE, tileSize: 256,
        attribution: "© OpenStreetMap contributors © CARTO",
      },
      "carto-labels": { type: "raster", tiles: CARTO_LABELS, tileSize: 256 },
    },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": GRAPHITE } },
      {
        id: "basemap", type: "raster", source: "carto",
        paint: {
          "raster-opacity": 0.5, "raster-saturation": -0.72,
          "raster-brightness-max": 0.62, "raster-hue-rotate": -12,
        },
      },
      {
        id: "labels", type: "raster", source: "carto-labels",
        paint: { "raster-opacity": 0.42, "raster-saturation": -0.5 },
      },
    ],
  };
}

const EMPTY_FC = { type: "FeatureCollection" as const, features: [] };

/** Approximates a circle of `radiusKm` as a polygon ring. MapLibre has no metric
 *  circle primitive — `circle-radius` is in screen pixels, which would misrepresent
 *  the search area at every zoom except one. */
function circlePolygon(lat: number, lng: number, radiusKm: number, steps = 72) {
  const coords: [number, number][] = [];
  const latRad = (lat * Math.PI) / 180;
  const kmPerDegLat = 110.574;
  const kmPerDegLng = 111.32 * Math.cos(latRad);
  for (let i = 0; i <= steps; i++) {
    const theta = (i / steps) * 2 * Math.PI;
    coords.push([
      lng + (radiusKm / kmPerDegLng) * Math.cos(theta),
      lat + (radiusKm / kmPerDegLat) * Math.sin(theta),
    ]);
  }
  return {
    type: "FeatureCollection" as const,
    features: [{
      type: "Feature" as const, properties: {},
      geometry: { type: "Polygon" as const, coordinates: [coords] },
    }],
  };
}

export default function SeriesMap({ series }: { series: CrimeSeries | null }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const readyRef = useRef(false);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  const located = useMemo(
    () => (series?.members ?? []).filter(
      (m) => typeof m.lat === "number" && typeof m.lng === "number"),
    [series],
  );

  const trackFC = useMemo(() => {
    if (located.length < 2) return EMPTY_FC;
    return {
      type: "FeatureCollection" as const,
      features: [{
        type: "Feature" as const, properties: {},
        geometry: {
          type: "LineString" as const,
          coordinates: located.map((m) => [m.lng as number, m.lat as number]),
        },
      }],
    };
  }, [located]);

  const forecastFC = useMemo(() => {
    const f = series?.forecast;
    if (!f?.predicted_epicenter || !f.search_radius_km) return EMPTY_FC;
    return circlePolygon(f.predicted_epicenter.lat, f.predicted_epicenter.lng,
                         f.search_radius_km);
  }, [series]);

  // ---- init once ----
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: graphiteStyle(),
      center: [76.6, 14.8],
      zoom: 6,
      pitch: reduced ? 0 : 30,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    map.on("load", () => {
      map.addSource("forecast", { type: "geojson", data: EMPTY_FC });
      map.addSource("track", { type: "geojson", data: EMPTY_FC });

      map.addLayer({
        id: "forecast-fill", type: "fill", source: "forecast",
        paint: { "fill-color": DANGER, "fill-opacity": 0.13 },
      });
      map.addLayer({
        id: "forecast-edge", type: "line", source: "forecast",
        paint: { "line-color": DANGER, "line-width": 1.6, "line-opacity": 0.75,
                 "line-dasharray": [3, 2] },
      });
      map.addLayer({
        id: "track-line", type: "line", source: "track",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": BRASS, "line-width": 2, "line-opacity": 0.7,
                 "line-dasharray": [2, 1.6] },
      });
      readyRef.current = true;
    });

    return () => {
      readyRef.current = false;
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // ---- data + framing ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;

    (map.getSource("track") as maplibregl.GeoJSONSource | undefined)?.setData(trackFC);
    (map.getSource("forecast") as maplibregl.GeoJSONSource | undefined)?.setData(forecastFC);

    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];
    if (!series) return;

    // Numbered offence markers. The number is the sequence position — the single most
    // useful thing to read off the map, because it turns a scatter of points into a
    // direction of travel.
    located.forEach((m, i) => {
      const last = i === located.length - 1;
      const el = document.createElement("div");
      el.className = "ksp-seq";
      el.textContent = String(i + 1);
      el.style.cssText = `
        width:22px;height:22px;border-radius:9999px;display:flex;align-items:center;
        justify-content:center;font:600 11px/1 var(--font-mono),monospace;
        color:${last ? GRAPHITE : BRASS_BRIGHT};
        background:${last ? BRASS_BRIGHT : "rgba(20,18,16,.85)"};
        border:1px solid ${last ? BRASS_BRIGHT : BRASS};
        box-shadow:0 0 ${last ? "14px" : "6px"} ${last ? BRASS_BRIGHT : "rgba(0,0,0,.5)"};
        cursor:default;`;
      el.title = `${i + 1}. ${m.fir_number} — ${m.district_name ?? "?"} — ` +
                 `${new Date(m.date).toLocaleDateString()}`;
      markersRef.current.push(
        new maplibregl.Marker({ element: el })
          .setLngLat([m.lng as number, m.lat as number])
          .addTo(map));
    });

    const f = series.forecast;
    if (f?.predicted_epicenter) {
      const due = f.state === "overdue" || f.state === "due_now";
      const el = document.createElement("div");
      el.className = due ? "ksp-mk ksp-mk-trend" : "ksp-mk";
      el.innerHTML = due
        ? `<span class="ksp-mk-ping" style="background:rgba(176,58,58,.45)"></span>
           <span class="ksp-mk-dot" style="background:${DANGER};box-shadow:0 0 10px ${DANGER}"></span>`
        : `<span class="ksp-mk-dot" style="background:${WARN};box-shadow:0 0 8px ${WARN}"></span>`;
      el.title = `Forecast area — ${f.state.replace("_", " ")}`;
      markersRef.current.push(
        new maplibregl.Marker({ element: el })
          .setLngLat([f.predicted_epicenter.lng, f.predicted_epicenter.lat])
          .addTo(map));
    }

    // Frame the run and its forecast area together.
    const bounds = new maplibregl.LngLatBounds();
    located.forEach((m) => bounds.extend([m.lng as number, m.lat as number]));
    forecastFC.features.forEach((feat) =>
      (feat.geometry.coordinates[0] as [number, number][])
        .forEach((c) => bounds.extend(c)));
    if (!bounds.isEmpty()) {
      map.fitBounds(bounds, { padding: 64, duration: 900, maxZoom: 11 });
    }
  }, [series, located, trackFC, forecastFC]);

  return <div ref={containerRef} className="h-full w-full" />;
}
