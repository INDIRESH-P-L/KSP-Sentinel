"use client";

import React, { useState, useEffect, useRef } from "react";
import { Share2, Users, ShieldAlert, Award } from "lucide-react";

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
          
          // Run simple force simulation locally for layout spacing
          const k = Math.sqrt((width * height) / nodes.length);
          const forceStrength = 0.08;
          const gravity = 0.05;
          
          for (let iter = 0; iter < 80; iter++) {
            // Apply repulsive forces between nodes
            for (let i = 0; i < nodes.length; i++) {
              for (let j = i + 1; j < nodes.length; j++) {
                const dx = nodes[j].x - nodes[i].x;
                const dy = nodes[j].y - nodes[i].y;
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                
                // Repulsive force proportional to standard spacing k
                const force = (k * k) / dist;
                const fx = (dx / dist) * force * forceStrength;
                const fy = (dy / dist) * force * forceStrength;
                
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
                const dx = targetNode.x - sourceNode.x;
                const dy = targetNode.y - sourceNode.y;
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                
                // Attractive force pulling connected nodes closer
                const force = (dist * dist) / k;
                const fx = (dx / dist) * force * forceStrength * 0.5;
                const fy = (dy / dist) * force * forceStrength * 0.5;
                
                sourceNode.x += fx;
                sourceNode.y += fy;
                targetNode.x -= fx;
                targetNode.y -= fy;
              }
            });
            
            // Push nodes back to bounding box and gravity center
            nodes.forEach((node: Node) => {
              // Gravity pull to center
              node.x += (width / 2 - node.x) * gravity;
              node.y += (height / 2 - node.y) * gravity;
              
              // Boundaries
              node.x = Math.max(30, Math.min(width - 30, node.x));
              node.y = Math.max(30, Math.min(height - 30, node.y));
            });
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
            Co-Offender Network & Link Analysis
          </h2>
          <p className="text-xs text-slate-400 mt-1">Algorithmic community structures and PageRank key node tracking</p>
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
        <div className="lg:col-span-3 glass-panel p-4 rounded-xl border border-slate-800 h-[550px] relative bg-slate-900/30 overflow-hidden flex items-center justify-center">
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
              return (
                <line
                  key={`edge-${idx}`}
                  x1={sourceNode.x}
                  y1={sourceNode.y}
                  x2={targetNode.x}
                  y2={targetNode.y}
                  stroke={isGangLink ? "#f43f5e" : "rgba(255,255,255,0.08)"}
                  strokeWidth={isGangLink ? 2 : 1}
                  strokeDasharray={isGangLink ? undefined : "3 3"}
                />
              );
            })}

            {/* Draw Nodes */}
            {network?.nodes.map((node) => {
              const radius = getNodeRadius(node);
              const isSelected = selectedNode?.id === node.id;
              
              return (
                <g 
                  key={node.id} 
                  transform={`translate(${node.x}, ${node.y})`}
                  className="cursor-pointer"
                  onClick={() => setSelectedNode(node)}
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
                  {/* Label for high-centrality nodes */}
                  {(node.pagerank > 0.04 || node.type === "station") && (
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

        {/* Intelligence Details Panel */}
        <div className="space-y-6">
          {/* Selected Node Details Card */}
          {selectedNode && (
            <div className="glass-panel p-6 rounded-xl border border-slate-800 bg-slate-900/40 space-y-4">
              <div>
                <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${
                  selectedNode.type === "accused" ? "bg-red-500/10 text-red-400 border border-red-500/20" :
                  selectedNode.type === "station" ? "bg-blue-500/10 text-blue-400 border border-blue-500/20" : "bg-cyan-500/10 text-cyan-400"
                }`}>
                  {selectedNode.type} profile
                </span>
                <h3 className="text-lg font-bold text-slate-100 mt-2.5">{selectedNode.label}</h3>
              </div>

              <div className="space-y-2 text-xs">
                {selectedNode.type === "accused" && (
                  <>
                    <div className="flex justify-between py-1 border-b border-slate-800/60">
                      <span className="text-slate-400">Offender Age / Gender:</span>
                      <span className="text-slate-200">{selectedNode.age}y / {selectedNode.gender}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-800/60">
                      <span className="text-slate-400">Prior Crimes Counter:</span>
                      <span className="text-red-400 font-bold">{selectedNode.priors} offenses</span>
                    </div>
                  </>
                )}
                <div className="flex justify-between py-1 border-b border-slate-800/60">
                  <span className="text-slate-400">PageRank Importance:</span>
                  <span className="text-cyan-400 font-semibold">{selectedNode.pagerank.toFixed(4)}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800/60">
                  <span className="text-slate-400">Syndicate Community:</span>
                  <span className="text-slate-200">Gang Cell #{selectedNode.community}</span>
                </div>
              </div>
            </div>
          )}

          {/* Master Criminals Card */}
          <div className="glass-panel p-6 rounded-xl border border-slate-800 bg-slate-900/40">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-4 flex items-center gap-2">
              <Award className="w-4 h-4 text-cyan-400" />
              Highest Centrality Accused Nodes
            </h3>
            <div className="space-y-2">
              {network?.metrics.master_criminals.map((mc: any, idx: number) => (
                <div 
                  key={idx} 
                  onClick={() => {
                    const originalNode = network.nodes.find(n => n.id === mc.id);
                    if (originalNode) setSelectedNode(originalNode);
                  }}
                  className="flex items-center justify-between p-2 rounded bg-slate-950/60 border border-slate-800/60 hover:border-cyan-500/30 transition-all cursor-pointer"
                >
                  <span className="text-xs font-medium text-slate-200 truncate">{mc.label}</span>
                  <span className="text-[10px] font-bold text-red-400 bg-red-500/10 px-2 py-0.5 rounded">{mc.priors} priors</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
