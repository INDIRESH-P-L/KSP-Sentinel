"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import { forceSimulation, forceManyBody, forceLink, forceCenter, forceCollide } from "d3-force";
import {
  forceSimulation as forceSimulation3d,
  forceManyBody as forceManyBody3d,
  forceLink as forceLink3d,
  forceCenter as forceCenter3d,
} from "d3-force-3d";
import { Share2, X, RefreshCw, FileText } from "lucide-react";
import { authFetch } from "@/lib/api";
import { SectionTitle, PanelLabel, Loading, Stat } from "@/components/ui/primitives";
import { GlassDefs, GlassSphere } from "@/components/ui/glass-svg";
import { mockNetwork } from "@/lib/mock";
import type { NetworkData, NetworkLink, NetworkNode } from "@/lib/types";

type Mode = "2d" | "3d";
type Positioned = NetworkNode & { x: number; y: number };
type Positioned3D = Positioned & { z: number };
type Edge<T> = { s: T; t: T };
type Adjacency = Map<string, Set<string>>;
type Box = { x: number; y: number; w: number; h: number };

const GANG_COLORS = ["#DC143C", "#7C3AED", "#FF3B30", "#ec4899", "#a855f7"];
const TYPE_COLORS = {
  fir: "#00D9FF", station: "#3b82f6", victim: "#eab308", crime_type: "#FF9500",
} as const;
/** Every colour a node can take — one glass gradient is emitted per entry. */
const NODE_COLORS = [...Object.values(TYPE_COLORS), ...GANG_COLORS];

/** Edge strokes: neighbours of the selection light up cyan, the rest recede. */
const EDGE_LIT = "rgba(0,217,255,0.8)";
const EDGE_IDLE = "rgba(148,163,184,0.13)";

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

/** Re-attach id-keyed links to their laid-out node objects, dropping danglers. */
function resolveEdges<T extends NetworkNode>(links: NetworkLink[], nodes: T[]): Edge<T>[] {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  return links
    .map((l) => ({ s: byId.get(l.source), t: byId.get(l.target) }))
    .filter((e): e is Edge<T> => !!e.s && !!e.t);
}

// Deterministic d3-force layouts, settled synchronously (verifiable, no canvas widget).
// Both are handed a *copy* of the links so d3 can't rewrite `data.links` id strings
// into node objects behind our back.
function layout2d(data: NetworkData): { nodes: Positioned[]; links: Edge<Positioned>[] } {
  const nodes = data.nodes.map((n) => ({ ...n })) as Positioned[];
  const sim = forceSimulation(nodes as never[])
    .force("charge", forceManyBody().strength(-160).distanceMax(500))
    .force(
      "link",
      forceLink(data.links.map((l) => ({ ...l })) as never[])
        .id((d) => (d as NetworkNode).id)
        .distance(70)
        .strength(0.4)
    )
    .force("center", forceCenter(0, 0))
    .force("collide", forceCollide().radius((n) => nodeRadius(n as NetworkNode) + 4))
    .stop();
  for (let i = 0; i < 300; i++) sim.tick();
  return { nodes, links: resolveEdges(data.links, nodes) };
}

function layout3d(data: NetworkData): { nodes: Positioned3D[]; links: Edge<Positioned3D>[] } {
  const nodes = data.nodes.map((n) => ({ ...n })) as Positioned3D[];
  const sim = forceSimulation3d(nodes, 3)
    .force("charge", forceManyBody3d().strength(-220).distanceMax(600))
    .force(
      "link",
      forceLink3d(data.links.map((l) => ({ ...l })))
        .id((d: NetworkNode) => d.id)
        .distance(82)
        .strength(0.4)
    )
    .force("center", forceCenter3d(0, 0, 0))
    .stop();
  for (let i = 0; i < 300; i++) sim.tick();
  return { nodes, links: resolveEdges(data.links, nodes) };
}

function bbox(nodes: Positioned[]): Box {
  if (!nodes.length) return { x: 0, y: 0, w: 100, h: 100 };
  const xs = nodes.map((n) => n.x), ys = nodes.map((n) => n.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const pad = 54;
  return { x: minX - pad, y: minY - pad, w: maxX - minX + pad * 2, h: maxY - minY + pad * 2 };
}

export default function NetworkView() {
  const [data, setData] = useState<NetworkData>(mockNetwork());
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<NetworkNode | null>(null);
  const [reload, setReload] = useState(0);
  const [mode, setMode] = useState<Mode>("3d");

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await authFetch("/api/network/?limit=150");
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

  // Trim before laying out — the simulations and the sphere count both scale
  // off this, so it has to happen upstream of the memo below.
  const core = useMemo(() => trimToCore(data), [data]);
  const trimmed = core.nodes.length < data.nodes.length;

  // Both layouts settle once per dataset so flipping 2D/3D is instant.
  const { flat, deep, adj } = useMemo(
    () => ({ flat: layout2d(core), deep: layout3d(core), adj: adjacency(core.links) }),
    [core]
  );

  const nodeById = useMemo(() => new Map(core.nodes.map((n) => [n.id, n])), [core]);
  const neighbours = selected ? adj.get(selected.id) : undefined;
  const dimmed = (id: string) => !!selected && selected.id !== id && !neighbours?.has(id);
  const lit = (e: Edge<NetworkNode>) => !!selected && (e.s.id === selected.id || e.t.id === selected.id);

  // ---- 2D: fitted viewBox with pan/zoom ------------------------------------
  // The override is tagged with the `fitted` it was derived from, so a fresh
  // layout (reload) transparently falls back to re-fitting — no effect, no
  // render-phase ref writes.
  const fitted = useMemo(() => bbox(flat.nodes), [flat]);
  const [override, setOverride] = useState<{ base: Box; win: Box } | null>(null);
  const vb = override && override.base === fitted ? override.win : fitted;
  const setVb = (updater: (v: Box) => Box) => setOverride({ base: fitted, win: updater(vb) });

  // ---- 3D: orbit + dolly ---------------------------------------------------
  const [rot, setRot] = useState({ x: -0.35, y: 0.55 });
  const [zoom, setZoom] = useState(1);

  const drag = useRef({ active: false, moved: false, lx: 0, ly: 0 });
  const onDown = (e: React.PointerEvent) => {
    drag.current = { active: true, moved: false, lx: e.clientX, ly: e.clientY };
  };
  const onMove = (e: React.PointerEvent) => {
    if (!drag.current.active) return;
    const dx = e.clientX - drag.current.lx;
    const dy = e.clientY - drag.current.ly;
    if (Math.abs(dx) + Math.abs(dy) > CLICK_SLOP) drag.current.moved = true;
    drag.current.lx = e.clientX;
    drag.current.ly = e.clientY;
    if (mode === "3d") {
      setRot((r) => ({ x: clamp(r.x + dy * 0.008, -1.35, 1.35), y: r.y + dx * 0.008 }));
    } else {
      const scale = vb.w / (e.currentTarget as SVGSVGElement).clientWidth;
      setVb((b) => ({ ...b, x: b.x - dx * scale, y: b.y - dy * scale }));
    }
  };
  const onUp = () => { drag.current.active = false; };
  const onWheel = (e: React.WheelEvent) => {
    if (mode === "3d") {
      setZoom((z) => clamp(z * (e.deltaY > 0 ? 0.92 : 1.08), 0.45, 3));
    } else {
      const factor = e.deltaY > 0 ? 1.1 : 0.9;
      setVb((b) => ({
        x: b.x + (b.w * (1 - factor)) / 2,
        y: b.y + (b.h * (1 - factor)) / 2,
        w: b.w * factor,
        h: b.h * factor,
      }));
    }
  };
  /** Swallow the click that terminates an orbit/pan gesture. */
  const select = (n: NetworkNode) => { if (!drag.current.moved) setSelected(n); };

  // Every neighbour, not just FIRs: live graphs are station/accused/crime_type
  // and contain no FIR nodes at all, so an FIR-only filter renders an
  // permanently empty panel against real data.
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

  // Only legend the kinds actually on screen — mock graphs are accused/FIR,
  // live ones are station/accused/crime_type, and a fixed list lies about both.
  const legend = useMemo(() => {
    const present = new Set(core.nodes.map((n) => n.type));
    return LEGEND_ORDER.filter((e) => present.has(e.type)).map((e) => ({
      label: e.label,
      // Accused have no single colour — they're keyed by gang, so show the first.
      color: e.type === "accused" ? GANG_COLORS[0] : TYPE_COLORS[e.type as keyof typeof TYPE_COLORS],
    }));
  }, [core]);

  if (loading) return <Loading label="Reconstructing criminal network graph…" />;

  const svgProps = {
    className: "h-full w-full cursor-grab touch-none active:cursor-grabbing",
    onPointerDown: onDown,
    onPointerMove: onMove,
    onPointerUp: onUp,
    onPointerLeave: onUp,
    onWheel,
  };

  // Painter's algorithm: far geometry first. Links carry a large z bias so the
  // whole edge mesh sits behind the node shells rather than threading through them.
  const projected = new Map(
    deep.nodes.map((n) => {
      const cosx = Math.cos(rot.x), sinx = Math.sin(rot.x);
      const cosy = Math.cos(rot.y), siny = Math.sin(rot.y);
      const x = n.x * cosy - n.z * siny;
      const z0 = n.x * siny + n.z * cosy;
      const y = n.y * cosx - z0 * sinx;
      const z = n.y * sinx + z0 * cosx;
      const s = FOCAL / (FOCAL + z + CAM_Z);
      return [n.id, { px: x * s, py: y * s, s, z }] as const;
    })
  );
  const depthSorted =
    mode === "3d"
      ? [
          ...deep.links.map((l, i) => {
            const a = projected.get(l.s.id)!, b = projected.get(l.t.id)!;
            const on = lit(l);
            return {
              z: (a.z + b.z) / 2 + 1e5,
              el: (
                <line
                  key={`l${i}`}
                  x1={a.px} y1={a.py} x2={b.px} y2={b.py}
                  stroke={on ? EDGE_LIT : EDGE_IDLE}
                  strokeWidth={on ? 1.6 : 0.5}
                />
              ),
            };
          }),
          ...deep.nodes.map((n) => {
            const p = projected.get(n.id)!;
            return {
              z: p.z,
              el: (
                <GlassSphere
                  key={n.id}
                  cx={p.px} cy={p.py}
                  r={Math.max(3, nodeRadius(n) * p.s * 1.35)}
                  color={nodeColor(n)}
                  active={selected?.id === n.id}
                  dim={dimmed(n.id)}
                  alpha={clamp(p.s * 0.85 + 0.28, 0.35, 1)}
                  onClick={() => select(n)}
                />
              ),
            };
          }),
        ].sort((a, b) => b.z - a.z)
      : [];

  const sceneW = SCENE_W / zoom, sceneH = SCENE_H / zoom;

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

          {/* Projection toggle */}
          <div
            role="group"
            aria-label="Graph projection"
            className="glass-chip absolute right-4 top-4 z-10 flex gap-0.5 rounded-[11px] p-[3px]"
          >
            {(["2d", "3d"] as const).map((m) => {
              const on = mode === m;
              return (
                <button
                  key={m}
                  onClick={() => { setMode(m); setSelected(null); }}
                  aria-pressed={on}
                  className={`rounded-lg px-3 py-1.5 text-[11px] font-bold tracking-[0.06em] transition-all duration-[250ms] ${
                    on
                      ? "bg-[var(--color-accent-cyan)]/[0.16] text-[var(--color-accent-cyan)] shadow-[0_0_12px_rgba(0,217,255,0.25)]"
                      : "text-[var(--color-ink-faint)] hover:text-[var(--color-ink-muted)]"
                  }`}
                >
                  {m.toUpperCase()}
                </button>
              );
            })}
          </div>

          <div className="h-[606px] w-full">
            {mode === "3d" ? (
              <svg viewBox={`${-sceneW / 2} ${-sceneH / 2} ${sceneW} ${sceneH}`} {...svgProps}>
                <GlassDefs colors={NODE_COLORS} />
                {depthSorted.map((item) => item.el)}
              </svg>
            ) : (
              <svg viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`} {...svgProps}>
                <GlassDefs colors={NODE_COLORS} />
                <g>
                  {flat.links.map((l, i) => {
                    const on = lit(l);
                    return (
                      <line
                        key={i}
                        x1={l.s.x} y1={l.s.y} x2={l.t.x} y2={l.t.y}
                        stroke={on ? EDGE_LIT : EDGE_IDLE}
                        strokeWidth={on ? 1.6 : 0.6}
                      />
                    );
                  })}
                </g>
                <g>
                  {flat.nodes.map((n) => (
                    <GlassSphere
                      key={n.id}
                      cx={n.x} cy={n.y} r={nodeRadius(n)}
                      color={nodeColor(n)}
                      active={selected?.id === n.id}
                      dim={dimmed(n.id)}
                      onClick={() => select(n)}
                    />
                  ))}
                </g>
              </svg>
            )}
          </div>
          <p className="absolute bottom-3 right-4 text-[10px] text-[var(--color-ink-faint)]">
            {mode === "3d" ? "Drag to orbit" : "Drag to pan"} · scroll to zoom · click a node
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
