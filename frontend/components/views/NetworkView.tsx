"use client";

import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import {
  forceSimulation, forceManyBody, forceLink, forceCenter, forceCollide, forceX, forceY
} from "d3-force";
import {
  forceSimulation as forceSimulation3D, forceManyBody as forceManyBody3D,
  forceLink as forceLink3D, forceCenter as forceCenter3D, forceCollide as forceCollide3D
} from "d3-force-3d";
import {
  Share2, Award, MapPin, Layers, AlertTriangle, RefreshCw, Sparkles, GitBranch, Box, Maximize2, Play, Pause
} from "lucide-react";
import { authFetch } from "@/lib/api";

interface Node {
  id: string;
  label: string;
  type: string;
  centrality: number;
  pagerank: number;
  betweenness: number;
  community: number;
  gender?: string;
  age?: number;
  priors?: number;
  linked_cases?: any[];
  modus_operandi?: string;
}

interface Edge {
  source: string;
  target: string;
  relationship: string;
  weight: number;
}

// Positioned variants produced by the d3-force simulations.
type Node2D = Node & { x: number; y: number };
type Node3D = Node & { x: number; y: number; z: number };

const ACCUSED_COLORS = ["#ef4444", "#a855f7", "#ec4899", "#f43f5e", "#d946ef"];

function getNodeColor(type: string, community: number) {
  switch (type) {
    case "accused": return ACCUSED_COLORS[community % ACCUSED_COLORS.length];
    case "victim": return "#eab308";
    case "station": return "#3b82f6";
    case "crime_type": return "#06b6d4";
    default: return "#94a3b8";
  }
}

// Node radius scales with PageRank for suspects so the key players read as bigger hubs.
function nodeRadius(n: Node) {
  if (n.type === "accused") return Math.min(16, 4 + Math.sqrt(Math.max(0, n.pagerank)) * 42);
  if (n.type === "station") return 8;
  if (n.type === "crime_type") return 6;
  return 5;
}

// --- Layout computation (pure d3-force, runs to a settled state synchronously) ------
// 374 nodes with a Barnes-Hut quadtree is fast (~0.5s) and, crucially, deterministic
// and verifiable outside a browser -- unlike a canvas/WebGL graph widget.
function computeLayout2D(nodes: Node[], edges: Edge[]): Node2D[] {
  const simNodes: any[] = nodes.map(n => ({ ...n }));
  const simLinks: any[] = edges.map(e => ({ source: e.source, target: e.target, relationship: e.relationship }));
  const sim = forceSimulation(simNodes)
    .force("charge", forceManyBody().strength(-75).distanceMax(420))
    .force("link", forceLink(simLinks).id((d: any) => d.id).distance((l: any) => l.relationship === "co_accused" ? 24 : 46).strength(0.35))
    .force("center", forceCenter(0, 0))
    .force("collide", forceCollide().radius((n: any) => nodeRadius(n) + 2.5))
    .force("x", forceX(0).strength(0.045))
    .force("y", forceY(0).strength(0.045))
    .stop();
  for (let i = 0; i < 260; i++) sim.tick();
  return simNodes as Node2D[];
}

function computeLayout3D(nodes: Node[], edges: Edge[]): Node3D[] {
  const simNodes: any[] = nodes.map(n => ({ ...n }));
  const simLinks: any[] = edges.map(e => ({ source: e.source, target: e.target }));
  const sim = forceSimulation3D(simNodes, 3)
    .force("charge", forceManyBody3D().strength(-45))
    .force("link", forceLink3D(simLinks).id((d: any) => d.id).distance(32))
    .force("center", forceCenter3D(0, 0, 0))
    .force("collide", forceCollide3D().radius((n: any) => nodeRadius(n) + 2))
    .stop();
  for (let i = 0; i < 200; i++) sim.tick();
  return simNodes as Node3D[];
}

function bbox(nodes: { x: number; y: number }[]) {
  const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const pad = Math.max(40, (maxX - minX) * 0.06);
  return { x: minX - pad, y: minY - pad, w: (maxX - minX) + pad * 2, h: (maxY - minY) + pad * 2 };
}

export default function NetworkView() {
  const [network, setNetwork] = useState<{ nodes: Node[]; edges: Edge[]; metrics: any } | null>(null);
  const [nodes2d, setNodes2d] = useState<Node2D[] | null>(null);
  const [nodes3d, setNodes3d] = useState<Node3D[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [selectedCommunity, setSelectedCommunity] = useState<number | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [viewMode, setViewMode] = useState<"2d" | "3d">("2d");

  // 2D viewBox (pan/zoom is expressed as a viewBox window, so the SVG stays fully
  // responsive with no pixel measuring/canvas sizing).
  const [view, setView] = useState<{ x: number; y: number; w: number; h: number } | null>(null);
  const initialView = useRef<{ x: number; y: number; w: number; h: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const panState = useRef<{ active: boolean; lx: number; ly: number }>({ active: false, lx: 0, ly: 0 });

  // 3D orientation
  const [rot, setRot] = useState({ x: -0.35, y: 0 });
  const [autoRotate, setAutoRotate] = useState(true);
  const rot3dDrag = useRef<{ active: boolean; lx: number; ly: number }>({ active: false, lx: 0, ly: 0 });

  useEffect(() => {
    let cancelled = false;
    async function loadNetwork() {
      setLoading(true);
      setError(null);
      try {
        // Capped at 150 FIRs (~370 nodes): a denser graph is unreadable regardless of engine.
        const res = await authFetch("/api/network/?fir_limit=150");
        if (!res.ok) {
          if (!cancelled) setError(`Network intelligence service returned an error (HTTP ${res.status}).`);
          return;
        }
        const data = await res.json();
        if (cancelled) return;

        const laid2d = computeLayout2D(data.nodes, data.edges);
        const fitted = bbox(laid2d);
        setNetwork({ nodes: data.nodes, edges: data.edges, metrics: data.metrics });
        setNodes2d(laid2d);
        setNodes3d(null); // computed lazily on first 3D toggle
        setView(fitted);
        initialView.current = fitted;

        const topAccused = laid2d.find(n => n.type === "accused");
        if (topAccused) setSelectedNode(topAccused);
      } catch (e) {
        if (!cancelled) setError("Cannot reach the KSP Sentinel API. Confirm the backend is running on http://localhost:8000.");
        console.error("Error loading network graph:", e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadNetwork();
    return () => { cancelled = true; };
  }, [reloadKey]);

  // Compute the 3D layout the first time the 3D view is opened.
  useEffect(() => {
    if (viewMode === "3d" && network && !nodes3d) {
      setNodes3d(computeLayout3D(network.nodes, network.edges));
    }
  }, [viewMode, network, nodes3d]);

  // Gentle auto-rotation for the 3D view.
  useEffect(() => {
    if (viewMode !== "3d" || !autoRotate) return;
    let raf = 0;
    const loop = () => {
      setRot(r => ({ ...r, y: r.y + 0.0045 }));
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [viewMode, autoRotate]);

  const nodeById2d = useMemo(() => {
    const m = new Map<string, Node2D>();
    nodes2d?.forEach(n => m.set(n.id, n));
    return m;
  }, [nodes2d]);

  const gangCommunities = useMemo(() => {
    if (!network) return [];
    return Array.from(new Set(network.nodes.map(n => n.community))).map(cId => {
      const members = network.nodes.filter(n => n.community === cId && n.type === "accused");
      return { id: cId, size: members.length, names: members.map(m => m.label) };
    }).filter(c => c.size > 0);
  }, [network]);

  const renderEmphasized = (text: string) =>
    text.split(/(\*\*[^*]+\*\*)/g).map((part, idx) =>
      part.startsWith("**") && part.endsWith("**")
        ? <strong key={idx} className="text-slate-100">{part.slice(2, -2)}</strong>
        : <React.Fragment key={idx}>{part}</React.Fragment>
    );

  const dimmed = (community: number) => selectedCommunity !== null && community !== selectedCommunity;

  // ----- 2D pan / zoom handlers (viewBox-window model) -----
  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (!view || !svgRef.current) return;
    e.preventDefault();
    const rect = svgRef.current.getBoundingClientRect();
    const relX = (e.clientX - rect.left) / rect.width;
    const relY = (e.clientY - rect.top) / rect.height;
    const factor = e.deltaY < 0 ? 0.88 : 1.136;
    const base = initialView.current!;
    const newW = Math.min(base.w * 3, Math.max(base.w * 0.15, view.w * factor));
    const newH = view.h * (newW / view.w);
    setView({ x: view.x + (view.w - newW) * relX, y: view.y + (view.h - newH) * relY, w: newW, h: newH });
  }, [view]);

  const handlePanStart = useCallback((e: React.MouseEvent) => {
    panState.current = { active: true, lx: e.clientX, ly: e.clientY };
  }, []);
  const handlePanMove = useCallback((e: React.MouseEvent) => {
    if (!panState.current.active || !view || !svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const dx = (e.clientX - panState.current.lx) / rect.width * view.w;
    const dy = (e.clientY - panState.current.ly) / rect.height * view.h;
    panState.current.lx = e.clientX;
    panState.current.ly = e.clientY;
    setView(v => v ? { ...v, x: v.x - dx, y: v.y - dy } : v);
  }, [view]);
  const handlePanEnd = useCallback(() => { panState.current.active = false; }, []);
  const resetView = useCallback(() => { if (initialView.current) setView(initialView.current); }, []);

  // ----- 3D drag-to-rotate -----
  const handle3dStart = useCallback((e: React.MouseEvent) => {
    rot3dDrag.current = { active: true, lx: e.clientX, ly: e.clientY };
  }, []);
  const handle3dMove = useCallback((e: React.MouseEvent) => {
    if (!rot3dDrag.current.active) return;
    const dx = e.clientX - rot3dDrag.current.lx;
    const dy = e.clientY - rot3dDrag.current.ly;
    rot3dDrag.current.lx = e.clientX;
    rot3dDrag.current.ly = e.clientY;
    setRot(r => ({ x: Math.max(-1.4, Math.min(1.4, r.x + dy * 0.008)), y: r.y + dx * 0.008 }));
  }, []);
  const handle3dEnd = useCallback(() => { rot3dDrag.current.active = false; }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <GitBranch className="w-8 h-8 text-cyan-400 animate-pulse" />
        <div className="text-cyan-400 font-bold text-lg animate-pulse tracking-wider">MAPPING INTEL CRIMINAL SYNDICATES...</div>
        <p className="text-slate-500 text-xs">Computing force layout, PageRank &amp; gang community clusters</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="glass-panel max-w-md w-full p-8 rounded-xl border border-red-500/20 text-center space-y-4">
          <div className="w-14 h-14 mx-auto rounded-full bg-red-500/10 border border-red-500/25 flex items-center justify-center">
            <AlertTriangle className="w-7 h-7 text-red-400" />
          </div>
          <div>
            <h3 className="text-slate-100 font-bold uppercase tracking-wider text-sm">Network Intelligence Unavailable</h3>
            <p className="text-slate-400 text-xs mt-2 leading-relaxed">{error}</p>
          </div>
          <button
            onClick={() => setReloadKey(k => k + 1)}
            className="inline-flex items-center gap-2 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-semibold py-2.5 px-5 rounded-lg transition-all text-xs uppercase tracking-wider cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  if (!network || !nodes2d || network.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="glass-panel max-w-md w-full p-8 rounded-xl border border-slate-800 text-center space-y-4">
          <div className="w-14 h-14 mx-auto rounded-full bg-cyan-500/10 border border-cyan-500/25 flex items-center justify-center">
            <Share2 className="w-7 h-7 text-cyan-400" />
          </div>
          <div>
            <h3 className="text-slate-100 font-bold uppercase tracking-wider text-sm">No Network Data Yet</h3>
            <p className="text-slate-400 text-xs mt-2 leading-relaxed">
              No FIR records were found to build a co-offender graph from. Once cases with accused/victim details are on file, syndicate links will render here automatically.
            </p>
          </div>
          <button
            onClick={() => setReloadKey(k => k + 1)}
            className="inline-flex items-center gap-2 bg-slate-900/60 hover:bg-slate-800 border border-slate-800 text-slate-300 font-semibold py-2.5 px-5 rounded-lg transition-all text-xs uppercase tracking-wider cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Overview stats bar */}
      <div className="glass-panel p-6 rounded-xl border border-slate-800 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
        <div>
          <div className="flex items-center gap-2.5 mb-1.5">
            <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
              <Share2 className="w-5 h-5 text-cyan-400" />
              Criminological Network &amp; Link Analysis
            </h2>
            <span className="flex items-center gap-1.5 bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 text-[10px] font-bold px-2.5 py-1 rounded-lg uppercase">
              <Sparkles className="w-3 h-3" />
              D3-Force Engine
            </span>
          </div>
          <p className="text-xs text-slate-400">Co-offender networks, PageRank key suspects, and gang cell community clusters</p>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className="p-3.5 rounded-lg bg-slate-950/40 border border-slate-800 text-center min-w-[100px]">
            <p className="text-2xl font-bold text-cyan-400">{network.metrics.total_nodes}</p>
            <span className="text-[9px] font-semibold text-slate-500 uppercase tracking-wider">Syndicate Nodes</span>
          </div>
          <div className="p-3.5 rounded-lg bg-slate-950/40 border border-slate-800 text-center min-w-[100px]">
            <p className="text-2xl font-bold text-purple-400">{network.metrics.total_edges}</p>
            <span className="text-[9px] font-semibold text-slate-500 uppercase tracking-wider">Bipartite Edges</span>
          </div>
          <div className="p-3.5 rounded-lg bg-slate-950/40 border border-slate-800 text-center min-w-[100px]">
            <p className="text-2xl font-bold text-red-400">{gangCommunities.length}</p>
            <span className="text-[9px] font-semibold text-slate-500 uppercase tracking-wider">Gang Cells</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Force Graph Pane */}
        <div className="lg:col-span-3 glass-panel p-4 rounded-xl border border-slate-800 h-[640px] relative bg-slate-950/40 overflow-hidden flex flex-col">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-850 pb-2.5 z-10 shrink-0">
            <div className="flex items-center gap-2.5">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Interactive Force Mapping</span>
              <span className="text-[9px] text-slate-600 hidden md:inline">
                {viewMode === "2d" ? "— scroll to zoom, drag to pan, click a node to inspect" : "— drag to rotate, click a node to inspect"}
              </span>
            </div>

            <div className="flex items-center gap-3">
              <div className="flex gap-2">
                <span className="flex items-center gap-1 text-[9px] font-bold uppercase text-slate-400 bg-slate-950/40 px-2 py-0.5 rounded border border-slate-800"><span className="w-1.5 h-1.5 rounded-full bg-red-500"></span> Suspect</span>
                <span className="flex items-center gap-1 text-[9px] font-bold uppercase text-slate-400 bg-slate-950/40 px-2 py-0.5 rounded border border-slate-800"><span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span> Station</span>
                <span className="flex items-center gap-1 text-[9px] font-bold uppercase text-slate-400 bg-slate-950/40 px-2 py-0.5 rounded border border-slate-800"><span className="w-1.5 h-1.5 rounded-full bg-cyan-500"></span> Type</span>
                <span className="flex items-center gap-1 text-[9px] font-bold uppercase text-slate-400 bg-slate-950/40 px-2 py-0.5 rounded border border-slate-800"><span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span> Victim</span>
              </div>

              {viewMode === "2d" ? (
                <button onClick={resetView} title="Reset view" className="p-1.5 rounded bg-slate-950/60 border border-slate-800 text-slate-400 hover:text-cyan-300 transition-all cursor-pointer">
                  <Maximize2 className="w-3.5 h-3.5" />
                </button>
              ) : (
                <button onClick={() => setAutoRotate(a => !a)} title={autoRotate ? "Pause rotation" : "Auto-rotate"} className="p-1.5 rounded bg-slate-950/60 border border-slate-800 text-slate-400 hover:text-purple-300 transition-all cursor-pointer">
                  {autoRotate ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                </button>
              )}

              <div className="flex items-center bg-slate-950/60 border border-slate-800 rounded-lg p-0.5">
                <button onClick={() => setViewMode("2d")} className={`flex items-center gap-1 px-2.5 py-1 rounded text-[10px] font-bold uppercase tracking-wider transition-all cursor-pointer ${viewMode === "2d" ? "bg-cyan-500/15 text-cyan-300" : "text-slate-500 hover:text-slate-300"}`}>
                  <Layers className="w-3 h-3" /> 2D
                </button>
                <button onClick={() => setViewMode("3d")} className={`flex items-center gap-1 px-2.5 py-1 rounded text-[10px] font-bold uppercase tracking-wider transition-all cursor-pointer ${viewMode === "3d" ? "bg-purple-500/15 text-purple-300" : "text-slate-500 hover:text-slate-300"}`}>
                  <Box className="w-3 h-3" /> 3D
                </button>
              </div>
            </div>
          </div>

          <div className="flex-1 min-h-0 mt-2">
            {viewMode === "2d" && view ? (
              <svg
                ref={svgRef}
                viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
                className="w-full h-full select-none cursor-grab active:cursor-grabbing"
                onWheel={handleWheel}
                onMouseDown={handlePanStart}
                onMouseMove={handlePanMove}
                onMouseUp={handlePanEnd}
                onMouseLeave={handlePanEnd}
              >
                {/* Links */}
                {network.edges.map((edge, idx) => {
                  const s = nodeById2d.get(edge.source);
                  const t = nodeById2d.get(edge.target);
                  if (!s || !t) return null;
                  const isGang = edge.relationship === "co_accused";
                  const isDim = selectedCommunity !== null && !(s.community === selectedCommunity && t.community === selectedCommunity);
                  return (
                    <line
                      key={idx}
                      x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                      stroke={isGang ? "#f43f5e" : "#64748b"}
                      strokeWidth={isGang ? 1.6 : 0.5}
                      strokeOpacity={isDim ? 0.03 : isGang ? 0.55 : 0.12}
                      strokeDasharray={isGang ? undefined : "2 3"}
                    />
                  );
                })}
                {/* Nodes */}
                {nodes2d.map(node => {
                  const r = nodeRadius(node);
                  const isSel = selectedNode?.id === node.id;
                  const showLabel = node.type === "station" || node.pagerank > 0.02 || isSel;
                  return (
                    <g key={node.id} transform={`translate(${node.x},${node.y})`} className="cursor-pointer" opacity={dimmed(node.community) ? 0.18 : 1} onClick={() => setSelectedNode(node)}>
                      <circle
                        r={r}
                        fill={getNodeColor(node.type, node.community)}
                        stroke={isSel ? "#22d3ee" : "rgba(2,6,23,0.7)"}
                        strokeWidth={isSel ? 2.5 : 0.8}
                        style={{ filter: isSel ? "drop-shadow(0 0 6px #22d3ee)" : undefined }}
                      />
                      {showLabel && (
                        <text y={-r - 3} textAnchor="middle" fill="#cbd5e1" fontSize={Math.max(7, view.w / 130)} fontWeight="600" className="pointer-events-none" style={{ paintOrder: "stroke", stroke: "rgba(2,6,23,0.85)", strokeWidth: 2.4 }}>
                          {node.label.length > 22 ? node.label.slice(0, 21) + "…" : node.label}
                        </text>
                      )}
                    </g>
                  );
                })}
              </svg>
            ) : viewMode === "3d" && nodes3d ? (
              <ThreeDGraph
                nodes={nodes3d}
                edges={network.edges}
                rot={rot}
                selectedNode={selectedNode}
                selectedCommunity={selectedCommunity}
                onNodeClick={setSelectedNode}
                onDragStart={handle3dStart}
                onDragMove={handle3dMove}
                onDragEnd={handle3dEnd}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-purple-300 text-sm font-bold tracking-wider animate-pulse">
                BUILDING 3D PROJECTION…
              </div>
            )}
          </div>
        </div>

        {/* Intelligence Details Panels */}
        <div className="space-y-6 h-[640px] overflow-y-auto pr-1">
          {selectedNode && (
            <div className="glass-panel p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-4">
              <div>
                <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${
                  selectedNode.type === "accused" ? "bg-red-500/10 text-red-400 border border-red-500/20" :
                  selectedNode.type === "station" ? "bg-blue-500/10 text-blue-400 border border-blue-500/20" : "bg-cyan-500/10 text-cyan-400"
                }`}>
                  {selectedNode.type} profile
                </span>
                <h3 className="text-sm font-bold text-slate-100 mt-2.5">{selectedNode.label}</h3>
              </div>

              <div className="space-y-2 text-xs">
                {selectedNode.type === "accused" && (
                  <>
                    <div className="flex justify-between py-1 border-b border-slate-850">
                      <span className="text-slate-400">Demographics:</span>
                      <span className="text-slate-200">{selectedNode.age}y / {selectedNode.gender}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-850">
                      <span className="text-slate-400">Prior offenses:</span>
                      <span className="text-red-400 font-bold">{selectedNode.priors} counts</span>
                    </div>
                  </>
                )}
                <div className="flex justify-between py-1 border-b border-slate-850">
                  <span className="text-slate-400">PageRank score:</span>
                  <span className="text-cyan-400 font-semibold">{selectedNode.pagerank.toFixed(4)}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-850">
                  <span className="text-slate-400">Community cell:</span>
                  <span className="text-slate-200">Gang Cell #{selectedNode.community}</span>
                </div>
              </div>

              {selectedNode.type === "accused" && (
                <div className="space-y-4 pt-2 border-t border-slate-850">
                  <div className="space-y-1">
                    <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest block">Modus Operandi Dossier</span>
                    <p className="text-[10px] text-slate-300 leading-relaxed bg-slate-950/60 p-2.5 rounded border border-slate-900">
                      {selectedNode.modus_operandi ? renderEmphasized(selectedNode.modus_operandi) : "N/A"}
                    </p>
                  </div>

                  <div className="space-y-2">
                    <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest block">Cross-Jurisdictional Case History</span>
                    <div className="space-y-2 max-h-[140px] overflow-y-auto pr-1">
                      {selectedNode.linked_cases?.map((c, idx) => (
                        <div key={idx} className="bg-slate-950/30 border border-slate-900 p-2 rounded text-[10px] space-y-1">
                          <div className="flex items-center justify-between font-bold text-slate-300">
                            <span>{c.fir_number}</span>
                            <span className="text-slate-500">{c.date}</span>
                          </div>
                          <div className="flex gap-2 text-cyan-400 font-semibold text-[9px] uppercase">
                            <span className="flex items-center gap-0.5"><MapPin className="w-2.5 h-2.5" /> {c.station}</span>
                          </div>
                          <p className="text-slate-400 italic line-clamp-2">&ldquo;{c.description}&rdquo;</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Gang Cells */}
          <div className="glass-panel p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-cyan-400" />
              Syndicates &amp; Gang Cells
            </h3>
            <div className="space-y-2 max-h-[140px] overflow-y-auto pr-1">
              <button onClick={() => setSelectedCommunity(null)} className={`w-full text-left p-2 rounded text-[10px] uppercase font-bold transition-all border ${selectedCommunity === null ? "bg-cyan-500/10 border-cyan-400/30 text-cyan-400" : "bg-slate-950/60 border-slate-900 text-slate-400 hover:border-slate-800"}`}>
                Show All Gang Cells
              </button>
              {gangCommunities.map(gang => (
                <div key={gang.id} onClick={() => setSelectedCommunity(gang.id)} className={`p-2.5 rounded border transition-all cursor-pointer space-y-1 ${selectedCommunity === gang.id ? "bg-purple-500/10 border-purple-400/30 text-purple-300" : "bg-slate-950/60 border-slate-900 hover:border-slate-850"}`}>
                  <div className="flex justify-between items-center text-[10px] font-bold">
                    <span>GANG CELL #{gang.id}</span>
                    <span className="bg-slate-900 text-slate-400 px-2 py-0.5 rounded border border-slate-800">{gang.size} suspects</span>
                  </div>
                  <p className="text-[9px] text-slate-500 truncate">Members: {gang.names.join(", ")}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Master Criminals */}
          <div className="glass-panel p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-2 flex items-center gap-1.5">
              <Award className="w-4 h-4 text-cyan-400" />
              Highest Centrality Suspects
            </h3>
            <div className="space-y-2">
              {network.metrics.master_criminals.map((mc: any, idx: number) => (
                <div key={idx} onClick={() => { const n = network.nodes.find(x => x.id === mc.id); if (n) setSelectedNode(n); }} className="flex items-center justify-between p-2 rounded bg-slate-950/60 border border-slate-900 hover:border-cyan-500/30 transition-all cursor-pointer">
                  <span className="text-xs font-medium text-slate-200 truncate">{mc.label}</span>
                  <span className="text-[9px] font-bold text-red-400 bg-red-500/10 px-2 py-0.5 rounded border border-red-500/10">{mc.priors} priors</span>
                </div>
              ))}
            </div>
          </div>

          {/* Bridge Suspects */}
          <div className="glass-panel p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-2 flex items-center gap-1.5">
              <Share2 className="w-4 h-4 text-purple-400" />
              Cross-Gang Bridges
            </h3>
            <p className="text-[9px] text-slate-500 -mt-2">
              Ranked by betweenness centrality — suspects connecting otherwise-separate cells, not just the most connected.
            </p>
            <div className="space-y-2">
              {network.metrics.bridge_suspects?.map((bs: any, idx: number) => (
                <div key={idx} onClick={() => { const n = network.nodes.find(x => x.id === bs.id); if (n) setSelectedNode(n); }} className="flex items-center justify-between p-2 rounded bg-slate-950/60 border border-slate-900 hover:border-purple-500/30 transition-all cursor-pointer">
                  <span className="text-xs font-medium text-slate-200 truncate">{bs.label}</span>
                  <span className="text-[9px] font-bold text-purple-300 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/10">{bs.betweenness.toFixed(4)}</span>
                </div>
              ))}
              {(!network.metrics.bridge_suspects || network.metrics.bridge_suspects.length === 0) && (
                <p className="text-slate-500 text-[10px] italic">No bridging suspects identified in the current network.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// --- 3D projected graph -------------------------------------------------------------
// Orthographic projection of the d3-force-3d layout, rotated by (rot.x, rot.y), drawn
// as depth-sorted SVG. Depth drives node size & opacity for a genuine 3D read, with no
// WebGL dependency to break under the Next/React toolchain.
function ThreeDGraph({
  nodes, edges, rot, selectedNode, selectedCommunity, onNodeClick, onDragStart, onDragMove, onDragEnd
}: {
  nodes: Node3D[];
  edges: Edge[];
  rot: { x: number; y: number };
  selectedNode: Node | null;
  selectedCommunity: number | null;
  onNodeClick: (n: Node) => void;
  onDragStart: (e: React.MouseEvent) => void;
  onDragMove: (e: React.MouseEvent) => void;
  onDragEnd: () => void;
}) {
  const cx = Math.cos(rot.x), sx = Math.sin(rot.x);
  const cy = Math.cos(rot.y), sy = Math.sin(rot.y);

  const projected = useMemo(() => {
    const map = new Map<string, { sx: number; sy: number; depth: number; n: Node3D }>();
    for (const n of nodes) {
      // rotate around Y then X
      const x1 = n.x * cy - n.z * sy;
      const z1 = n.x * sy + n.z * cy;
      const y1 = n.y * cx - z1 * sx;
      const z2 = n.y * sx + z1 * cx;
      map.set(n.id, { sx: x1, sy: y1, depth: z2, n });
    }
    return map;
  }, [nodes, cx, sx, cy, sy]);

  const depthMin = Math.min(...Array.from(projected.values()).map(p => p.depth));
  const depthMax = Math.max(...Array.from(projected.values()).map(p => p.depth));
  const depthNorm = (d: number) => depthMax === depthMin ? 0.5 : (d - depthMin) / (depthMax - depthMin);

  // Painter's algorithm: draw far nodes first.
  const ordered = Array.from(projected.values()).sort((a, b) => a.depth - b.depth);

  const gangSegments: string[] = [];
  const normalSegments: string[] = [];
  for (const e of edges) {
    const s = projected.get(e.source), t = projected.get(e.target);
    if (!s || !t) continue;
    if (selectedCommunity !== null && !(s.n.community === selectedCommunity && t.n.community === selectedCommunity)) continue;
    const seg = `M${s.sx.toFixed(1)},${s.sy.toFixed(1)}L${t.sx.toFixed(1)},${t.sy.toFixed(1)}`;
    (e.relationship === "co_accused" ? gangSegments : normalSegments).push(seg);
  }

  return (
    <svg
      viewBox="-900 -900 1800 1800"
      className="w-full h-full select-none cursor-grab active:cursor-grabbing"
      onMouseDown={onDragStart}
      onMouseMove={onDragMove}
      onMouseUp={onDragEnd}
      onMouseLeave={onDragEnd}
    >
      {/* edges as two batched paths (cheap even during rotation) */}
      <path d={normalSegments.join("")} stroke="#64748b" strokeWidth={0.6} fill="none" strokeOpacity={0.1} />
      <path d={gangSegments.join("")} stroke="#f43f5e" strokeWidth={1.4} fill="none" strokeOpacity={0.5} />
      {/* nodes back-to-front */}
      {ordered.map(({ sx: px, sy: py, depth, n }) => {
        const t = depthNorm(depth);              // 0 = far, 1 = near
        const r = nodeRadius(n) * (0.6 + t * 0.7);
        const isSel = selectedNode?.id === n.id;
        const dim = selectedCommunity !== null && n.community !== selectedCommunity;
        return (
          <circle
            key={n.id}
            cx={px} cy={py} r={r}
            fill={getNodeColor(n.type, n.community)}
            fillOpacity={dim ? 0.12 : 0.35 + t * 0.65}
            stroke={isSel ? "#22d3ee" : "rgba(2,6,23,0.6)"}
            strokeWidth={isSel ? 2.5 : 0.6}
            className="cursor-pointer"
            style={{ filter: isSel ? "drop-shadow(0 0 7px #22d3ee)" : undefined }}
            onClick={(ev) => { ev.stopPropagation(); onNodeClick(n); }}
          />
        );
      })}
    </svg>
  );
}
