"use client";

import React, { useState, useEffect, useMemo } from "react";
import { Share2, X, RefreshCw, FileText } from "lucide-react";
import { publicFetch } from "@/lib/api";
import { SectionTitle, PanelLabel, Loading, Stat } from "@/components/ui/primitives";
import { mockNetwork } from "@/lib/mock";
import type { NetworkData, NetworkLink, NetworkNode } from "@/lib/types";
import { GoogleMap, useJsApiLoader, MarkerF, Polyline } from "@react-google-maps/api";

type Adjacency = Map<string, Set<string>>;

// Gang cells are told apart by depth of oxblood, not by hue — the whole graph
// stays inside the emblem palette (maroon → wine → gold).
const GANG_COLORS = ["#98202f", "#6e1622", "#7c2438", "#470c13", "#a8434f"];
const TYPE_COLORS = {
  fir: "#e8cb8e", station: "#c2a164", victim: "#c9a24a", crime_type: "#8a6b3b",
} as const;
/** Every colour a node can take — one glass gradient is emitted per entry. */
const NODE_COLORS = [...Object.values(TYPE_COLORS), ...GANG_COLORS];

/** Edge strokes: neighbours of the selection light up gold, the rest recede. */
const EDGE_LIT = "rgba(232,203,142,0.82)";
const EDGE_IDLE = "rgba(196,185,164,0.13)";

/**
 * Cap on how much graph is laid out and drawn.
 *
 * The live endpoint ignores its `limit` query and returns the entire graph
 * (~2.8k nodes / 6.5k edges). Two 300-tick force simulations plus one blurred
 * glass sphere per node at that scale locks the main thread for minutes and is
 * unreadable besides — so the view renders the highest-PageRank core, which is
 * the part an analyst is actually looking for.
 */
const MAX_NODES = 150;

/** Dossier heading per node kind — live graphs carry more than accused/FIR. */
const PROFILE_TITLES: Record<NetworkNode["type"], string> = {
  fir: "Case Profile",
  station: "Station Profile",
  crime_type: "Crime Category",
  victim: "Victim Profile",
  accused: "Accused Profile",
};

/** Legend entries, in the order they should read. */
const LEGEND_ORDER: { type: NetworkNode["type"]; label: string }[] = [
  { type: "accused", label: "Suspects" },
  { type: "fir", label: "FIR Cases" },
  { type: "station", label: "Stations" },
  { type: "crime_type", label: "Crime Types" },
  { type: "victim", label: "Victims" },
];

/** Perspective camera for the 3D projection. */
const FOCAL = 640;
const CAM_Z = 520;
/** Base viewBox the 3D scene is drawn into, divided by the zoom factor. */
const SCENE_W = 900;
const SCENE_H = 606;
/** Pointer travel (px) past which a drag no longer counts as a node click. */
const CLICK_SLOP = 3;

function nodeColor(n: NetworkNode): string {
  if (n.type in TYPE_COLORS) return TYPE_COLORS[n.type as keyof typeof TYPE_COLORS];
  const idx = n.gang ? parseInt(n.gang.replace(/\D/g, "") || "0", 10) : 0;
  return GANG_COLORS[idx % GANG_COLORS.length];
}
function nodeRadius(n: NetworkNode) {
  if (n.type === "accused") return Math.min(20, 6 + Math.sqrt(Math.max(0, n.pagerank)) * 60);
  return 6;
}
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

/**
 * Reduce a graph to its `MAX_NODES` most central nodes, keeping only edges whose
 * endpoints both survive. Returns the input untouched when it already fits.
 */
function trimToCore(data: NetworkData): NetworkData {
  if (data.nodes.length <= MAX_NODES) return data;
  const nodes = [...data.nodes]
    .sort((a, b) => (b.pagerank ?? 0) - (a.pagerank ?? 0))
    .slice(0, MAX_NODES);
  const kept = new Set(nodes.map((n) => n.id));
  return { nodes, links: data.links.filter((l) => kept.has(l.source) && kept.has(l.target)) };
}

/** Undirected neighbour index — drives the dim/highlight pass and the dossier. */
function adjacency(links: NetworkLink[]): Adjacency {
  const adj: Adjacency = new Map();
  const connect = (a: string, b: string) => {
    const set = adj.get(a) ?? new Set<string>();
    set.add(b);
    adj.set(a, set);
  };
  for (const l of links) {
    connect(l.source, l.target);
    connect(l.target, l.source);
  }
  return adj;
}



const GOOGLE_MAPS_LIBRARIES: ("visualization")[] = ["visualization"];

export default function NetworkView() {
  const { isLoaded } = useJsApiLoader({
    id: "google-map-script",
    googleMapsApiKey: process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || "",
    libraries: GOOGLE_MAPS_LIBRARIES,
  });

  const [data, setData] = useState<NetworkData>(mockNetwork());
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<NetworkNode | null>(null);
  const [reload, setReload] = useState(0);


  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await publicFetch("/api/network/?limit=150");
        if (res.ok) {
          // Backend field is `edges`; NetworkData/layout() expect `links`.
          const raw = await res.json();
          setData({ nodes: raw.nodes ?? [], links: raw.links ?? raw.edges ?? [] });
        } else setData(mockNetwork());
      } catch {
        setData(mockNetwork());
      } finally {
        setLoading(false);
      }
    })();
  }, [reload]);

  const core = useMemo(() => trimToCore(data), [data]);
  const trimmed = core.nodes.length < data.nodes.length;

  const nodeById = useMemo(() => new Map(core.nodes.map((n) => [n.id, n])), [core]);
  const adj = useMemo(() => adjacency(core.links), [core.links]);
  const neighbours = selected ? adj.get(selected.id) : undefined;

  const select = (n: NetworkNode) => setSelected(n);

  const linked = useMemo(
    () =>
      selected
        ? [...(adj.get(selected.id) ?? [])]
            .map((id) => nodeById.get(id))
            .filter((n): n is NetworkNode => !!n)
        : [],
    [selected, adj, nodeById]
  );
  const linkedAreCases = linked.length > 0 && linked.every((n) => n.type === "fir");

  const legend = useMemo(() => {
    const present = new Set(core.nodes.map((n) => n.type));
    return LEGEND_ORDER.filter((e) => present.has(e.type)).map((e) => ({
      label: e.label,
      color: e.type === "accused" ? GANG_COLORS[0] : TYPE_COLORS[e.type as keyof typeof TYPE_COLORS],
    }));
  }, [core]);

  if (loading) return <Loading label="Reconstructing criminal network graph…" />;

  return (
    <div className="flex flex-col gap-[22px] fade-up">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionTitle>Criminal Network Analysis</SectionTitle>
        <button
          onClick={() => setReload((r) => r + 1)}
          className="flex items-center gap-2 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-white/[0.02] px-3.5 py-2.5 text-xs font-semibold text-[var(--color-ink-muted)] transition-all duration-300 hover:border-[var(--color-hairline-strong)] hover:text-[var(--color-ink)]"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Re-run analysis
        </button>
      </div>

      {/* Stat strip — counts describe the rendered core, not the raw payload. */}
      <div className="grid grid-cols-3 gap-[18px]">
        {[
          { label: "Syndicate Nodes", value: core.nodes.length },
          { label: "Gang Cells", value: new Set(core.nodes.map((n) => n.gang).filter(Boolean)).size },
          { label: "Bipartite Edges", value: core.links.length },
        ].map((s, i) => (
          <div key={i} className="glass p-5 text-center">
            <Stat className="block text-[32px] font-bold leading-none text-[var(--color-ink)]">{s.value}</Stat>
            <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--color-ink-faint)]">{s.label}</p>
          </div>
        ))}
      </div>

      {trimmed && (
        <p className="-mt-2 text-[11px] text-[var(--color-ink-faint)]">
          Showing the <Stat className="text-[var(--color-ink-muted)]">{core.nodes.length}</Stat> highest-PageRank nodes
          of <Stat className="text-[var(--color-ink-muted)]">{data.nodes.length.toLocaleString()}</Stat> returned.
        </p>
      )}

      <div className="grid grid-cols-1 gap-[18px] lg:grid-cols-[1fr_322px]">
        {/* Graph */}
        <div className="glass relative overflow-hidden p-0">
          {/* Legend */}
          <div className="glass-chip absolute left-4 top-4 z-10 flex flex-wrap gap-3 rounded-[var(--radius-well)] px-3 py-2">
            {legend.map((x) => (
              <span key={x.label} className="flex items-center gap-1.5 text-[10px] font-medium text-[var(--color-ink-muted)]">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: x.color }} /> {x.label}
              </span>
            ))}
          </div>



          <div className="h-[606px] w-full">
            {isLoaded ? (
              <GoogleMap
                mapContainerStyle={{ width: "100%", height: "100%" }}
                center={{ lat: 12.9716, lng: 77.5946 }} // default Bangalore
                zoom={10}
                options={{
                  disableDefaultUI: true,
                  zoomControl: true,
                  styles: [
                    { elementType: "geometry", stylers: [{ color: "#242f3e" }] },
                    { elementType: "labels.text.stroke", stylers: [{ color: "#242f3e" }] },
                    { elementType: "labels.text.fill", stylers: [{ color: "#746855" }] },
                    { featureType: "administrative.locality", elementType: "labels.text.fill", stylers: [{ color: "#d59563" }] },
                    { featureType: "road", elementType: "geometry", stylers: [{ color: "#38414e" }] },
                    { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#212a37" }] },
                    { featureType: "water", elementType: "geometry", stylers: [{ color: "#17263c" }] },
                  ],
                }}
              >
                {/* Edges */}
                {data.links.map((link, i) => {
                  const sourceNode = data.nodes.find(n => n.id === link.source);
                  const targetNode = data.nodes.find(n => n.id === link.target);
                  if (!sourceNode?.lat || !sourceNode?.lng || !targetNode?.lat || !targetNode?.lng) return null;
                  
                  const isLit = selected && (link.source === selected.id || link.target === selected.id);
                  return (
                    <Polyline
                      key={`edge-${i}`}
                      path={[
                        { lat: sourceNode.lat, lng: sourceNode.lng },
                        { lat: targetNode.lat, lng: targetNode.lng }
                      ]}
                      options={{
                        strokeColor: isLit ? "#00d9ff" : "rgba(255,255,255,0.1)",
                        strokeOpacity: isLit ? 0.8 : 0.4,
                        strokeWeight: isLit ? 3 : 1
                      }}
                    />
                  );
                })}
                
                {/* Nodes */}
                {data.nodes.filter(n => n.lat && n.lng).map((n) => (
                  <MarkerF
                    key={`node-${n.id}`}
                    position={{ lat: n.lat as number, lng: n.lng as number }}
                    onClick={() => select(n as NetworkNode)}
                    icon={{
                      path: "M-10,0a10,10 0 1,0 20,0a10,10 0 1,0 -20,0",
                      fillColor: nodeColor(n),
                      fillOpacity: (selected && selected.id !== n.id) ? 0.3 : 0.9,
                      strokeWeight: selected?.id === n.id ? 2 : 0,
                      strokeColor: "#00d9ff",
                      scale: 0.6 + (n.pagerank * 0.5)
                    }}
                  />
                ))}
              </GoogleMap>
            ) : (
              <div className="flex h-full w-full items-center justify-center text-xs text-[var(--color-ink-faint)]">
                Loading map...
              </div>
            )}
          </div>
          <p className="absolute bottom-3 right-4 text-[10px] text-[var(--color-ink-faint)]">
            Drag to pan · scroll to zoom · click a node
          </p>
        </div>

        {/* Dossier */}
        <div className="glass flex flex-col p-5">
          {selected ? (
            <>
              <div className="mb-4 flex items-center justify-between border-b border-[var(--color-hairline)] pb-3">
                <PanelLabel>{PROFILE_TITLES[selected.type] ?? "Node Profile"}</PanelLabel>
                <button onClick={() => setSelected(null)} className="text-[var(--color-ink-faint)] hover:text-[var(--color-ink)]">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <dl className="flex flex-col gap-2.5 text-xs">
                <Row k="Label" v={selected.label} />
                <Row k="ID" v={selected.id} mono />
                <Row k="Type" v={selected.type.toUpperCase()} />
                <Row k="PageRank" v={selected.pagerank.toFixed(3)} mono />
                {selected.gang && <Row k="Community" v={`Gang ${selected.gang}`} />}
              </dl>

              <div className="mt-5 border-t border-[var(--color-hairline)] pt-4">
                <PanelLabel className="mb-3 flex items-center gap-2">
                  <FileText className="h-3.5 w-3.5" />
                  {linkedAreCases ? "Linked Cases" : "Connected Entities"} ({linked.length})
                </PanelLabel>
                <div className="flex max-h-56 flex-col gap-1.5 overflow-y-auto pr-1">
                  {linked.length ? (
                    linked.map((c) => (
                      <div key={c.id} className="flex items-center gap-2 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-white/[0.02] px-3 py-2 text-xs text-[var(--color-ink-muted)]">
                        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: nodeColor(c) }} />
                        <span className="truncate">{c.label}</span>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs italic text-[var(--color-ink-faint)]">No connections in this graph slice.</p>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="flex min-h-[280px] flex-1 flex-col items-center justify-center text-center">
              <Share2 className="mb-3 h-10 w-10 text-[var(--color-ink-faint)]" />
              <p className="text-sm font-semibold text-[var(--color-ink-muted)]">Select a node</p>
              <p className="mt-1.5 max-w-[220px] text-xs text-[var(--color-ink-faint)]">Click any suspect to open their dossier — demographics, PageRank centrality, and linked cases.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({ k, v, mono = false }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-[var(--color-ink-faint)]">{k}</dt>
      <dd className={`truncate font-semibold text-[var(--color-ink)] ${mono ? "mono" : ""}`}>{v}</dd>
    </div>
  );
}
