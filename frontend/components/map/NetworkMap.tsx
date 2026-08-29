"use client";

import React, { useEffect, useMemo, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { NetworkData, NetworkNode } from "@/lib/types";
import { GRAPHITE } from "@/lib/palette";

/**
 * Geographic view of the criminal-link graph.
 *
 * Runs on MapLibre with the same keyless CARTO raster basemap as the operational
 * crime map, so the whole product uses ONE map engine. This view previously used
 * the Google Maps SDK, which needed `NEXT_PUBLIC_GOOGLE_MAPS_API_KEY` -- a variable
 * set nowhere in the project, in no .env file and in no deployment config -- so it
 * rendered a permanently blank panel behind a "Loading map..." string.
 *
 * Edges and nodes are drawn as GeoJSON layers rather than one React component per
 * element. The live graph carries thousands of edges; mounting a component apiece
 * (the previous `<Polyline>`/`<MarkerF>` approach) re-renders the entire set on every
 * selection change, whereas a layer repaints on the GPU.
 */

// Palette is passed in from the caller so the graph's colour rules live in exactly
// one place (NetworkView owns nodeColor/GANG_COLORS/TYPE_COLORS).
export type NetworkMapProps = {
  data: NetworkData;
  selected: NetworkNode | null;
  onSelect: (node: NetworkNode) => void;
  nodeColor: (n: NetworkNode) => string;
  edgeLit: string;
  edgeIdle: string;
};

const KARNATAKA_CENTER: [number, number] = [76.6, 14.8];

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

export default function NetworkMap({
  data, selected, onSelect, nodeColor, edgeLit, edgeIdle,
}: NetworkMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const readyRef = useRef(false);
  const onSelectRef = useRef(onSelect);
  useEffect(() => { onSelectRef.current = onSelect; }, [onSelect]);

  // Node lookup by id, so edge building is O(edges) rather than O(edges × nodes).
  // The previous implementation called data.nodes.find() twice per link inside the
  // render, which is O(n·m) and ran again on every selection change.
  const nodeById = useMemo(() => {
    const m = new Map<string, NetworkNode>();
    for (const n of data.nodes) m.set(n.id, n);
    return m;
  }, [data.nodes]);

  const nodesFC = useMemo(() => ({
    type: "FeatureCollection" as const,
    features: data.nodes
      .filter((n) => Number.isFinite(n.lat) && Number.isFinite(n.lng))
      .map((n) => ({
        type: "Feature" as const,
        geometry: { type: "Point" as const, coordinates: [n.lng as number, n.lat as number] },
        properties: {
          id: n.id,
          color: nodeColor(n),
          // PageRank drives radius; clamped so a hub cannot swallow the viewport
          // and a leaf stays clickable.
          radius: Math.max(3.5, Math.min(14, 4 + (n.pagerank ?? 0) * 60)),
        },
      })),
  }), [data.nodes, nodeColor]);

  const edgesFC = useMemo(() => {
    const selId = selected?.id;
    return {
      type: "FeatureCollection" as const,
      features: data.links.flatMap((link, i) => {
        const a = nodeById.get(link.source);
        const b = nodeById.get(link.target);
        if (!a?.lat || !a?.lng || !b?.lat || !b?.lng) return [];
        const lit = Boolean(selId && (link.source === selId || link.target === selId));
        return [{
          type: "Feature" as const,
          id: i,
          geometry: {
            type: "LineString" as const,
            coordinates: [[a.lng, a.lat], [b.lng, b.lat]] as [number, number][],
          },
          properties: { lit: lit ? 1 : 0 },
        }];
      }),
    };
  }, [data.links, nodeById, selected]);

  // ---- init (once) ----
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: graphiteStyle(),
      center: KARNATAKA_CENTER,
      zoom: 6.1,
      pitch: reduced ? 0 : 28,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    map.on("load", () => {
      map.addSource("edges", { type: "geojson", data: EMPTY_FC });
      map.addSource("nodes", { type: "geojson", data: EMPTY_FC });

      map.addLayer({
        id: "edges", type: "line", source: "edges",
        paint: {
          "line-color": ["case", ["==", ["get", "lit"], 1], edgeLit, edgeIdle],
          "line-width": ["case", ["==", ["get", "lit"], 1], 2.2, 0.7],
        },
      });
      map.addLayer({
        id: "node-glow", type: "circle", source: "nodes",
        paint: {
          "circle-color": ["get", "color"],
          "circle-radius": ["*", ["get", "radius"], 2.1],
          "circle-blur": 1,
          "circle-opacity": 0.28,
        },
      });
      map.addLayer({
        id: "nodes", type: "circle", source: "nodes",
        paint: {
          "circle-color": ["get", "color"],
          "circle-radius": ["get", "radius"],
          "circle-stroke-width": 1,
          "circle-stroke-color": "rgba(242,236,224,0.55)",
          "circle-opacity": 0.92,
        },
      });

      map.on("click", "nodes", (e) => {
        const id = e.features?.[0]?.properties?.id;
        if (!id) return;
        const node = nodeById.get(String(id));
        if (node) onSelectRef.current(node);
      });
      map.on("mouseenter", "nodes", () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "nodes", () => { map.getCanvas().style.cursor = ""; });

      readyRef.current = true;
      (map.getSource("edges") as maplibregl.GeoJSONSource).setData(edgesFC);
      (map.getSource("nodes") as maplibregl.GeoJSONSource).setData(nodesFC);
    });

    return () => {
      readyRef.current = false;
      map.remove();
      mapRef.current = null;
    };
    // Intentionally mount-once: data flows in through the setData effects below, so
    // the map is never torn down and rebuilt when the graph changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---- data updates ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    (map.getSource("nodes") as maplibregl.GeoJSONSource | undefined)?.setData(nodesFC);
  }, [nodesFC]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    (map.getSource("edges") as maplibregl.GeoJSONSource | undefined)?.setData(edgesFC);
  }, [edgesFC]);

  // ---- fly to the selected node ----
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selected?.lat || !selected?.lng) return;
    map.flyTo({
      center: [selected.lng, selected.lat],
      zoom: Math.max(map.getZoom(), 9),
      speed: 0.8, curve: 1.4, essential: true,
    });
  }, [selected]);

  return <div ref={containerRef} className="h-full w-full" />;
}
