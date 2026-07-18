"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import { forceSimulation, forceManyBody, forceLink, forceCenter, forceCollide } from "d3-force";
import { Share2, X, RefreshCw, FileText } from "lucide-react";
import { authFetch } from "@/lib/api";
import { SectionTitle, PanelLabel, Loading } from "@/components/ui/primitives";
import { mockNetwork } from "@/lib/mock";
import type { NetworkData, NetworkNode } from "@/lib/types";

type Positioned = NetworkNode & { x: number; y: number };

const GANG_COLORS = ["#ef4444", "#a855f7", "#ec4899", "#f43f5e", "#d946ef"];

function nodeColor(n: NetworkNode) {
  if (n.type === "fir") return "#22d3ee";
  if (n.type === "station") return "#3b82f6";
  if (n.type === "victim") return "#eab308";
  const idx = n.gang ? parseInt(n.gang.replace(/\D/g, "") || "0", 10) : 0;
  return GANG_COLORS[idx % GANG_COLORS.length];
}
function nodeRadius(n: NetworkNode) {
  if (n.type === "accused") return Math.min(20, 6 + Math.sqrt(Math.max(0, n.pagerank)) * 60);
  return 6;
}

// Deterministic d3-force layout, settled synchronously (verifiable, no canvas widget).
function layout(data: NetworkData): { nodes: Positioned[]; links: { s: Positioned; t: Positioned }[] } {
  const sim: (NetworkNode & { x?: number; y?: number })[] = data.nodes.map((n) => ({ ...n }));
  const links = data.links.map((l) => ({ source: l.source, target: l.target }));
  const s = forceSimulation(sim as never[])
    .force("charge", forceManyBody().strength(-160).distanceMax(500))
    .force("link", forceLink(links as never[]).id((d) => (d as { id: string }).id).distance(70).strength(0.4))
    .force("center", forceCenter(0, 0))
    .force("collide", forceCollide().radius((n) => nodeRadius(n as NetworkNode) + 4))
    .stop();
  for (let i = 0; i < 300; i++) s.tick();
  const byId = new Map(sim.map((n) => [n.id, n as Positioned]));
  return {
    nodes: sim as Positioned[],
    links: data.links.map((l) => ({ s: byId.get(l.source)!, t: byId.get(l.target)! })).filter((l) => l.s && l.t),
  };
}

function bbox(nodes: Positioned[]) {
  const xs = nodes.map((n) => n.x), ys = nodes.map((n) => n.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const pad = 40;
  return `${minX - pad} ${minY - pad} ${maxX - minX + pad * 2} ${maxY - minY + pad * 2}`;
}

export default function NetworkView() {
  const [data, setData] = useState<NetworkData>(mockNetwork());
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<NetworkNode | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const res = await authFetch("/api/network/?limit=150");
        if (res.ok) setData(await res.json());
        else setData(mockNetwork());
      } catch {
        setData(mockNetwork());
      } finally {
        setLoading(false);
      }
    })();
  }, [reload]);

  const { nodes, links } = useMemo(() => layout(data), [data]);
  const fitted = useMemo(() => {
    const [x, y, w, h] = (nodes.length ? bbox(nodes) : "0 0 100 100").split(" ").map(Number);
    return { x, y, w, h };
  }, [nodes]);

  // Pan/zoom window. The override is tagged with the `fitted` it was derived from, so a
  // fresh layout (reload) transparently falls back to re-fitting — no effect, no render
  // -phase ref writes.
  const [override, setOverride] = useState<{ base: typeof fitted; win: { x: number; y: number; w: number; h: number } } | null>(null);
  const vb = override && override.base === fitted ? override.win : fitted;
  const setVb = (updater: (v: { x: number; y: number; w: number; h: number }) => { x: number; y: number; w: number; h: number }) =>
    setOverride({ base: fitted, win: updater(vb) });

  const pan = useRef({ active: false, lx: 0, ly: 0 });
  const onDown = (e: React.PointerEvent) => { pan.current = { active: true, lx: e.clientX, ly: e.clientY }; };
  const onMove = (e: React.PointerEvent) => {
    if (!pan.current.active) return;
    const svg = e.currentTarget as SVGSVGElement;
    const scale = vb.w / svg.clientWidth;
    setVb((b) => ({ ...b, x: b.x - (e.clientX - pan.current.lx) * scale, y: b.y - (e.clientY - pan.current.ly) * scale }));
    pan.current.lx = e.clientX; pan.current.ly = e.clientY;
  };
  const onUp = () => { pan.current.active = false; };
  const onWheel = (e: React.WheelEvent) => {
    const factor = e.deltaY > 0 ? 1.1 : 0.9;
    setVb((b) => ({ x: b.x + (b.w * (1 - factor)) / 2, y: b.y + (b.h * (1 - factor)) / 2, w: b.w * factor, h: b.h * factor }));
  };

  const stats = useMemo(() => ({
    suspects: data.nodes.filter((n) => n.type === "accused").length,
    firs: data.nodes.filter((n) => n.type === "fir").length,
    edges: data.links.length,
  }), [data]);

  const dossierCases = useMemo(
    () => (selected ? links.filter((l) => l.s.id === selected.id || l.t.id === selected.id).map((l) => (l.s.id === selected.id ? l.t : l.s)).filter((n) => n.type === "fir") : []),
    [selected, links]
  );

  if (loading) return <Loading label="Reconstructing criminal network graph…" />;

  return (
    <div className="space-y-6 fade-up">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionTitle>Criminal Network Analysis</SectionTitle>
        <button
          onClick={() => setReload((r) => r + 1)}
          className="flex items-center gap-2 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-white/[0.02] px-3 py-2 text-xs font-semibold text-[var(--color-ink-muted)] transition-all hover:text-[var(--color-ink)]"
        >
          <RefreshCw className="h-3.5 w-3.5" /> Re-run analysis
        </button>
      </div>

      {/* Stat strip */}
      <div className="grid grid-cols-3 gap-5">
        {[
          { label: "Syndicate Nodes", value: data.nodes.length },
          { label: "Gang Cells", value: new Set(data.nodes.map((n) => n.gang).filter(Boolean)).size },
          { label: "Bipartite Edges", value: stats.edges },
        ].map((s, i) => (
          <div key={i} className="glass p-5 text-center">
            <p className="text-3xl font-extrabold text-[var(--color-ink)]">{s.value}</p>
            <p className="mt-1 text-[10px] font-bold uppercase tracking-widest text-[var(--color-ink-faint)]">{s.label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_320px]">
        {/* Graph */}
        <div className="glass relative overflow-hidden p-0">
          {/* Legend */}
          <div className="absolute left-4 top-4 z-10 flex flex-wrap gap-3 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface)]/80 px-3 py-2 backdrop-blur-md">
            {[
              { c: "#ef4444", l: "Suspects" },
              { c: "#22d3ee", l: "FIR Cases" },
              { c: "#3b82f6", l: "Stations" },
            ].map((x) => (
              <span key={x.l} className="flex items-center gap-1.5 text-[10px] font-medium text-[var(--color-ink-muted)]">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: x.c }} /> {x.l}
              </span>
            ))}
          </div>
          <div className="h-[600px] w-full">
              <svg
                viewBox={`${vb.x} ${vb.y} ${vb.w} ${vb.h}`}
                className="h-full w-full cursor-grab touch-none active:cursor-grabbing"
                onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={onUp} onWheel={onWheel}
              >
                {links.map((l, i) => (
                  <line key={i} x1={l.s.x} y1={l.s.y} x2={l.t.x} y2={l.t.y} stroke="rgba(148,163,184,0.18)" strokeWidth={0.6} />
                ))}
                {nodes.map((n) => {
                  const active = selected?.id === n.id;
                  return (
                    <g key={n.id} onClick={() => setSelected(n)} className="cursor-pointer">
                      <circle
                        cx={n.x} cy={n.y} r={nodeRadius(n)}
                        fill={nodeColor(n)} fillOpacity={active ? 1 : 0.85}
                        stroke={active ? "#fff" : "rgba(255,255,255,0.25)"} strokeWidth={active ? 1.5 : 0.5}
                        style={active ? { filter: "drop-shadow(0 0 6px rgba(255,255,255,0.6))" } : undefined}
                      />
                    </g>
                  );
                })}
              </svg>
          </div>
          <p className="absolute bottom-3 right-4 text-[10px] text-[var(--color-ink-faint)]">Drag to pan · scroll to zoom · click a node</p>
        </div>

        {/* Dossier */}
        <div className="glass flex flex-col p-5">
          {selected ? (
            <>
              <div className="mb-4 flex items-center justify-between border-b border-[var(--color-hairline)] pb-3">
                <PanelLabel>Accused Profile</PanelLabel>
                <button onClick={() => setSelected(null)} className="text-[var(--color-ink-faint)] hover:text-[var(--color-ink)]">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <dl className="space-y-2.5 text-xs">
                <Row k="Label" v={selected.label} />
                <Row k="ID" v={selected.id} />
                <Row k="Type" v={selected.type.toUpperCase()} />
                <Row k="PageRank" v={selected.pagerank.toFixed(3)} />
                {selected.gang && <Row k="Community" v={`Gang ${selected.gang}`} />}
              </dl>

              <div className="mt-5 border-t border-[var(--color-hairline)] pt-4">
                <PanelLabel className="mb-3 flex items-center gap-2">
                  <FileText className="h-3.5 w-3.5" /> Linked Cases ({dossierCases.length})
                </PanelLabel>
                <div className="max-h-56 space-y-1.5 overflow-y-auto pr-1">
                  {dossierCases.length ? (
                    dossierCases.map((c) => (
                      <div key={c.id} className="rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-white/[0.02] px-3 py-2 text-xs text-[var(--color-ink-muted)]">
                        {c.label}
                      </div>
                    ))
                  ) : (
                    <p className="text-xs italic text-[var(--color-ink-faint)]">No linked cases in this graph slice.</p>
                  )}
                </div>
              </div>
            </>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center text-center">
              <Share2 className="mb-3 h-10 w-10 text-[var(--color-ink-faint)]" />
              <p className="text-sm font-semibold text-[var(--color-ink-muted)]">Select a node</p>
              <p className="mt-1 text-xs text-[var(--color-ink-faint)]">Click any suspect to open their dossier — demographics, PageRank centrality, and linked cases.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-[var(--color-ink-faint)]">{k}</dt>
      <dd className="truncate font-semibold text-[var(--color-ink)]">{v}</dd>
    </div>
  );
}
