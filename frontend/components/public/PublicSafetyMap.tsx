"use client";

import React, { useEffect, useRef } from "react";
// maplibre-gl v6 ships no default export from its ESM build -- namespace import only
// (same as components/map/MapContainer.tsx).
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { OK, WARN, DANGER, GRAPHITE } from "@/lib/palette";

/**
 * Simple district map for the public safety page.
 *
 * Deliberately NOT the operational MapContainer: that component is built around
 * hotspots, patrol routes and emerging-trend layers, none of which may appear on a
 * public page. This one plots district centroids and nothing else, so there is no
 * operational layer that could be switched on by accident.
 */

export type PublicDistrict = {
  district_name: string;
  latitude: number;
  longitude: number;
  safety_category: "Low" | "Medium" | "High";
  trend: string;
  /** Rendered by the page's cards; the map itself has no use for them. */
  safety_tips: string[];
};

// Muted functional tones from the design tokens — never bright, never a second accent.
const BAND_COLOR: Record<string, string> = {
  Low: OK,
  Medium: WARN,
  High: DANGER,
};

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
      { id: "bg", type: "background", paint: { "background-color": GRAPHITE } },
      {
        id: "basemap", type: "raster", source: "carto",
        paint: { "raster-opacity": 0.5, "raster-saturation": -0.72, "raster-brightness-max": 0.66, "raster-hue-rotate": -12 },
      },
      { id: "labels", type: "raster", source: "carto-labels", paint: { "raster-opacity": 0.45, "raster-saturation": -0.5 } },
    ],
  };
}

export default function PublicSafetyMap({
  districts,
  selected,
  onSelect,
}: {
  districts: PublicDistrict[];
  selected?: string | null;
  onSelect?: (name: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: graphiteStyle(),
      center: [76.6, 14.8],           // roughly the centre of Karnataka
      zoom: 5.6,
      pitch: reduced ? 0 : 35,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Redraw markers whenever the data or the selection changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    districts.forEach((d) => {
      const el = document.createElement("div");
      const isSelected = selected === d.district_name;
      el.className = "ksp-pub-dot";
      el.style.background = BAND_COLOR[d.safety_category] ?? BAND_COLOR.Medium;
      el.style.width = el.style.height = isSelected ? "20px" : "13px";
      el.style.boxShadow = isSelected
        ? `0 0 0 4px rgba(232,203,142,0.55), 0 0 16px ${BAND_COLOR[d.safety_category]}`
        : `0 0 10px ${BAND_COLOR[d.safety_category]}aa`;
      el.title = `${d.district_name} — ${d.safety_category}`;
      if (onSelect) {
        el.style.cursor = "pointer";
        el.addEventListener("click", () => onSelect(d.district_name));
      }
      const marker = new maplibregl.Marker({ element: el })
        .setLngLat([d.longitude, d.latitude])
        .setPopup(
          new maplibregl.Popup({ offset: 14, closeButton: false, className: "ksp-popup" }).setHTML(
            `<span class="ksp-pop-title">${d.district_name}</span><br>${d.safety_category} · trend ${d.trend}`
          )
        )
        .addTo(map);
      markersRef.current.push(marker);
    });
  }, [districts, selected, onSelect]);

  // Fly to a district picked from the card list.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selected) return;
    const d = districts.find((x) => x.district_name === selected);
    if (!d) return;
    map.flyTo({ center: [d.longitude, d.latitude], zoom: 8.5, speed: 0.8, essential: true });
  }, [selected, districts]);

  return <div ref={containerRef} className="h-full w-full" />;
}
