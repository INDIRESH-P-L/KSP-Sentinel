"use client";

import React, { useState, useEffect, useRef } from "react";
import { Share2, Users, ShieldAlert, Award, FileText, MapPin, Layers } from "lucide-react";

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
  x: number;
  y: number;
}

interface Edge {
  source: string;
  target: string;
  relationship: string;
  weight: number;
}

export default function NetworkView() {
  const [network, setNetwork] = useState<{ nodes: Node[]; edges: Edge[]; metrics: any } | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [selectedCommunity, setSelectedCommunity] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  
  // Simulation parameters
  const width = 800;
  const height = 500;

  useEffect(() => {
    async function loadNetwork() {
      try {
        const token = localStorage.getItem("ksp_token");
        const headers: Record<string, string> = {};
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }

        const res = await fetch("http://localhost:8000/api/network/", { headers });
        if (res.ok) {
          const data = await res.json();
          
          // Seed initial positions randomly for simulation
          const nodes = data.nodes.map((node: Node) => ({
            ...node,
            x: width / 2 + (Math.random() - 0.5) * 350,
            y: height / 2 + (Math.random() - 0.5) * 250
          }));
          
          // Run simple stable force simulation locally for layout spacing
          const k = Math.sqrt((width * height) / Math.max(1, nodes.length));
          const forceStrength = 0.05;
          const gravity = 0.05;
          let temperature = 10.0;
          
          for (let iter = 0; iter < 80; iter++) {
            // Apply repulsive forces between nodes
            for (let i = 0; i < nodes.length; i++) {
              for (let j = i + 1; j < nodes.length; j++) {
                let dx = nodes[j].x - nodes[i].x;
                let dy = nodes[j].y - nodes[i].y;
                if (dx === 0 && dy === 0) {
                  dx = Math.random() - 0.5;
                  dy = Math.random() - 0.5;
                }
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                
                const force = (k * k) / dist;
                let fx = (dx / dist) * force * forceStrength;
                let fy = (dy / dist) * force * forceStrength;
                
                // Cap displacement using temperature cooling
                fx = Math.max(-temperature, Math.min(temperature, fx));
                fy = Math.max(-temperature, Math.min(temperature, fy));
                
                nodes[i].x -= fx;
                nodes[i].y -= fy;
                nodes[j].x += fx;
                nodes[j].y += fy;
              }
            }
            
            // Apply attractive forces along edges
            data.edges.forEach((edge: Edge) => {
              const sourceNode = nodes.find((n: Node) => n.id === edge.source);
              const targetNode = nodes.find((n: Node) => n.id === edge.target);
              
              if (sourceNode && targetNode) {
                let dx = targetNode.x - sourceNode.x;
                let dy = targetNode.y - sourceNode.y;
                if (dx === 0 && dy === 0) {
                  dx = Math.random() - 0.5;
                  dy = Math.random() - 0.5;
                }
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                
                const force = (dist * dist) / k;
                let fx = (dx / dist) * force * forceStrength * 0.5;
                let fy = (dy / dist) * force * forceStrength * 0.5;
                
                fx = Math.max(-temperature, Math.min(temperature, fx));
                fy = Math.max(-temperature, Math.min(temperature, fy));
                
                sourceNode.x += fx;
                sourceNode.y += fy;
                targetNode.x -= fx;
                targetNode.y -= fy;
              }
            });
            
            // Push nodes back to bounding box and gravity center
            nodes.forEach((node: Node) => {
              node.x += (width / 2 - node.x) * gravity;
              node.y += (height / 2 - node.y) * gravity;
              
              node.x = Math.max(30, Math.min(width - 30, node.x));
              node.y = Math.max(30, Math.min(height - 30, node.y));
              
              // Prevent any NaN leaking
              if (isNaN(node.x) || !isFinite(node.x)) node.x = width / 2;
              if (isNaN(node.y) || !isFinite(node.y)) node.y = height / 2;
            });
            
            temperature *= 0.95; // Cool layout force
          }
          
          setNetwork({ nodes, edges: data.edges, metrics: data.metrics });
          if (nodes.length > 0) {
            const topAccused = nodes.find((n: Node) => n.type === "accused");
            if (topAccused) setSelectedNode(topAccused);
          }
        }
      } catch (e) {
        console.error("Error loading network graph:", e);
      } finally {
        setLoading(false);
      }
    }
    loadNetwork();
  }, []);

  const getNodeColor = (type: string, community: number) => {
    switch (type) {
      case "accused":
        // Distinguish different gangs by community ID
        const colors = ["#ef4444", "#a855f7", "#ec4899", "#f43f5e", "#d946ef"];
        return colors[community % colors.length];
      case "victim":
        return "#eab308"; // Amber
      case "station":
        return "#3b82f6"; // Blue
      case "crime_type":
        return "#06b6d4"; // Cyan
      default:
        return "#94a3b8";
    }
  };

  const getNodeRadius = (node: Node) => {
    if (node.type === "accused") {
      return 8 + (node.pagerank * 100);
    }
    if (node.type === "station") return 14;
    return 10;
  };

  // Group nodes by community (Gangs) to count them
  const gangCommunities = network?.nodes
    ? Array.from(new Set(network.nodes.map(n => n.community))).map(cId => {
        const members = network.nodes.filter(n => n.community === cId && n.type === "accused");
        return {
          id: cId,
          size: members.length,
          names: members.map(m => m.label)
        };
      }).filter(c => c.size > 0)
    : [];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-cyan-400 font-bold text-lg animate-pulse tracking-wider">MAPPING INTEL CRIMINAL SYNDICATES...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Overview stats bar */}
      <div className="glass-panel p-6 rounded-xl border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
            <Share2 className="w-5 h-5 text-cyan-400" />
            Criminological Network & Link Analysis
          </h2>
          <p className="text-xs text-slate-400 mt-1">Co-offender networks, PageRank key suspects, and gang cell community clusters</p>
        </div>

        <div className="flex items-center gap-6">
          <div className="text-right">
            <span className="text-[10px] font-semibold text-slate-500 uppercase">Syndicate Nodes</span>
            <p className="text-base font-bold text-slate-200">{network?.metrics.total_nodes || 0}</p>
          </div>
          <div className="text-right">
            <span className="text-[10px] font-semibold text-slate-500 uppercase">Bipartite Edges</span>
            <p className="text-base font-bold text-slate-200">{network?.metrics.total_edges || 0}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* SVG Network Graph Pane */}
        <div className="lg:col-span-3 glass-panel p-4 rounded-xl border border-slate-800 h-[600px] relative bg-slate-900/30 overflow-hidden flex flex-col justify-between">
          <div className="flex items-center justify-between border-b border-slate-850 pb-2 z-10">
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Interactive Bipartite Force Mapping</span>
            <div className="flex gap-2">
              <span className="flex items-center gap-1 text-[9px] font-bold uppercase text-slate-400 bg-slate-950/40 px-2 py-0.5 rounded border border-slate-800">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500"></span> Suspect
              </span>
              <span className="flex items-center gap-1 text-[9px] font-bold uppercase text-slate-400 bg-slate-950/40 px-2 py-0.5 rounded border border-slate-800">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span> Station
              </span>
              <span className="flex items-center gap-1 text-[9px] font-bold uppercase text-slate-400 bg-slate-950/40 px-2 py-0.5 rounded border border-slate-800">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-500"></span> Type
              </span>
              <span className="flex items-center gap-1 text-[9px] font-bold uppercase text-slate-400 bg-slate-950/40 px-2 py-0.5 rounded border border-slate-800">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span> Victim
              </span>
            </div>
          </div>
          
          <svg 
            ref={svgRef}
            viewBox={`0 0 ${width} ${height}`} 
            className="w-full h-full cursor-grab active:cursor-grabbing select-none"
          >
            {/* Draw Links */}
            {network?.edges.map((edge, idx) => {
              const sourceNode = network.nodes.find(n => n.id === edge.source);
              const targetNode = network.nodes.find(n => n.id === edge.target);
              
              if (!sourceNode || !targetNode) return null;
              
              const isGangLink = edge.relationship === "co_accused";
              
              // Apply community highlights
              let opacity = "0.08";
              if (selectedCommunity !== null) {
                if (sourceNode.community === selectedCommunity && targetNode.community === selectedCommunity) {
                  opacity = "0.75";
                } else {
                  opacity = "0.02";
                }
              } else {
                opacity = isGangLink ? "0.7" : "0.08";
              }

              return (
                <line
                  key={`edge-${idx}`}
                  x1={sourceNode.x}
                  y1={sourceNode.y}
                  x2={targetNode.x}
                  y2={targetNode.y}
                  stroke={isGangLink ? "#f43f5e" : "rgba(255,255,255,0.8)"}
                  strokeWidth={isGangLink ? 2.5 : 1}
                  strokeDasharray={isGangLink ? undefined : "3 3"}
                  strokeOpacity={opacity}
                />
              );
            })}

            {/* Draw Nodes */}
            {network?.nodes.map((node) => {
              const radius = getNodeRadius(node);
              const isSelected = selectedNode?.id === node.id;
              
              let opacity = 1.0;
              if (selectedCommunity !== null) {
                opacity = node.community === selectedCommunity ? 1.0 : 0.15;
              }

              return (
                <g 
                  key={node.id} 
                  transform={`translate(${node.x}, ${node.y})`}
                  className="cursor-pointer"
                  onClick={() => setSelectedNode(node)}
                  opacity={opacity}
                >
                  <circle
                    r={radius}
                    fill={getNodeColor(node.type, node.community)}
                    stroke={isSelected ? "#00ffff" : "rgba(15,23,42,0.6)"}
                    strokeWidth={isSelected ? 3 : 1}
                    className="transition-all hover:scale-110"
                    style={{
                      filter: isSelected ? "drop-shadow(0px 0px 8px #00ffff)" : undefined
                    }}
                  />
                  {(node.pagerank > 0.03 || node.type === "station" || isSelected) && (
                    <text
                      y={-radius - 4}
                      textAnchor="middle"
                      fill="#e2e8f0"
                      fontSize={9}
                      fontWeight="bold"
                      className="bg-slate-950 px-1 py-0.5 rounded pointer-events-none"
                    >
                      {node.label}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        </div>

        {/* Intelligence Details Panels */}
        <div className="space-y-6 h-[600px] overflow-y-auto pr-1">
          {/* Selected Node Details Card */}
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

              {/* Accused Specific Dossier details */}
              {selectedNode.type === "accused" && (
                <div className="space-y-4 pt-2 border-t border-slate-850">
                  <div className="space-y-1">
                    <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest block">Modus Operandi Dossier</span>
                    <p className="text-[10px] text-slate-300 leading-relaxed bg-slate-950/60 p-2.5 rounded border border-slate-900" dangerouslySetInnerHTML={{ __html: selectedNode.modus_operandi || "N/A" }} />
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
                          <p className="text-slate-400 italic line-clamp-2">"{c.description}"</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Gang Cells Communities Card */}
          <div className="glass-panel p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
              <Layers className="w-4 h-4 text-cyan-400" />
              Syndicates & Gang Cells
            </h3>
            <div className="space-y-2 max-h-[140px] overflow-y-auto pr-1">
              <button
                onClick={() => setSelectedCommunity(null)}
                className={`w-full text-left p-2 rounded text-[10px] uppercase font-bold transition-all border ${
                  selectedCommunity === null
                    ? "bg-cyan-500/10 border-cyan-400/30 text-cyan-400"
                    : "bg-slate-950/60 border-slate-900 text-slate-400 hover:border-slate-800"
                }`}
              >
                Show All Gang Cells
              </button>

              {gangCommunities.map((gang, idx) => (
                <div
                  key={gang.id}
                  onClick={() => setSelectedCommunity(gang.id)}
                  className={`p-2.5 rounded border transition-all cursor-pointer space-y-1 ${
                    selectedCommunity === gang.id
                      ? "bg-purple-500/10 border-purple-400/30 text-purple-300"
                      : "bg-slate-950/60 border-slate-900 hover:border-slate-850"
                  }`}
                >
                  <div className="flex justify-between items-center text-[10px] font-bold">
                    <span>GANG CELL #{gang.id}</span>
                    <span className="bg-slate-900 text-slate-400 px-2 py-0.5 rounded border border-slate-800">{gang.size} suspects</span>
                  </div>
                  <p className="text-[9px] text-slate-500 truncate">Members: {gang.names.join(", ")}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Master Criminals Card */}
          <div className="glass-panel p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-2 flex items-center gap-1.5">
              <Award className="w-4 h-4 text-cyan-400" />
              Highest Centrality Suspects
            </h3>
            <div className="space-y-2">
              {network?.metrics.master_criminals.map((mc: any, idx: number) => (
                <div
                  key={idx}
                  onClick={() => {
                    const originalNode = network.nodes.find(n => n.id === mc.id);
                    if (originalNode) setSelectedNode(originalNode);
                  }}
                  className="flex items-center justify-between p-2 rounded bg-slate-950/60 border border-slate-900 hover:border-cyan-500/30 transition-all cursor-pointer"
                >
                  <span className="text-xs font-medium text-slate-200 truncate">{mc.label}</span>
                  <span className="text-[9px] font-bold text-red-400 bg-red-500/10 px-2 py-0.5 rounded border border-red-500/10">{mc.priors} priors</span>
                </div>
              ))}
            </div>
          </div>

          {/* Bridge Suspects Card (betweenness centrality) */}
          <div className="glass-panel p-5 rounded-xl border border-slate-800 bg-slate-900/40 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-2 flex items-center gap-1.5">
              <Share2 className="w-4 h-4 text-purple-400" />
              Cross-Gang Bridges
            </h3>
            <p className="text-[9px] text-slate-500 -mt-2">
              Ranked by betweenness centrality — suspects connecting otherwise-separate cells, not just the most connected.
            </p>
            <div className="space-y-2">
              {network?.metrics.bridge_suspects?.map((bs: any, idx: number) => (
                <div
                  key={idx}
                  onClick={() => {
                    const originalNode = network.nodes.find(n => n.id === bs.id);
                    if (originalNode) setSelectedNode(originalNode);
                  }}
                  className="flex items-center justify-between p-2 rounded bg-slate-950/60 border border-slate-900 hover:border-purple-500/30 transition-all cursor-pointer"
                >
                  <span className="text-xs font-medium text-slate-200 truncate">{bs.label}</span>
                  <span className="text-[9px] font-bold text-purple-300 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/10">{bs.betweenness.toFixed(4)}</span>
                </div>
              ))}
              {(!network?.metrics.bridge_suspects || network.metrics.bridge_suspects.length === 0) && (
                <p className="text-slate-500 text-[10px] italic">No bridging suspects identified in the current network.</p>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
