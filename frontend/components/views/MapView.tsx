"use client";

import React, { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { AlertCircle, Navigation, Users } from "lucide-react";

// Dynamically load the Leaflet container to disable SSR rendering
const MapContainer = dynamic(
  () => import("../map/MapContainer"),
  { 
    ssr: false,
    loading: () => (
      <div className="w-full h-[500px] bg-slate-900/60 border border-slate-800 rounded-xl flex items-center justify-center">
        <span className="text-cyan-400 font-bold text-sm animate-pulse tracking-widest">LOADING SATELLITE COMMAND MAP FEED...</span>
      </div>
    )
  }
);

export default function MapView() {
  const [stations, setStations] = useState<any[]>([]);
  const [selectedStation, setSelectedStation] = useState<number | null>(null);
  
  // Data for map
  const [hqLocation, setHqLocation] = useState<[number, number]>([12.9778, 77.5714]); // Majestic base
  const [firs, setFirs] = useState<any[]>([]);
  const [hotspots, setHotspots] = useState<any[]>([]);
  const [patrolRoute, setPatrolRoute] = useState<any[]>([]);
  const [incidentCount, setIncidentCount] = useState(0);
  
  const [loadingMap, setLoadingMap] = useState(true);

  // Load all stations
  useEffect(() => {
    async function loadStations() {
      try {
        const token = localStorage.getItem("ksp_token");
        const headers: Record<string, string> = {};
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }

        const res = await fetch("http://localhost:8000/api/districts/stations", { headers });
        if (res.ok) {
          const data = await res.json();
          setStations(data);
          if (data.length > 0) {
            setSelectedStation(data[0].id);
          }
        }
      } catch (e) {
        console.error("Error loading stations list:", e);
      }
    }
    loadStations();
  }, []);

  // Fetch hotspots & crimes for selected station
  useEffect(() => {
    if (!selectedStation) return;
    
    async function fetchMapData() {
      setLoadingMap(true);
      try {
        const token = localStorage.getItem("ksp_token");
        const headers: Record<string, string> = {};
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }
        
        // 1. Fetch hotspots and routes
        const hotRes = await fetch(`http://localhost:8000/api/districts/stations/${selectedStation}/hotspots`, { headers });
        if (hotRes.ok) {
          const hotData = await hotRes.json();
          if (hotData.station_location) {
            setHqLocation(hotData.station_location);
          }
          setHotspots(hotData.hotspots || []);
          setPatrolRoute(hotData.route || []);
        }
        
        // 2. Fetch FIR pins
        // We'll list FIRs with station filter from crimes API
        const crimesRes = await fetch(`http://localhost:8000/api/crimes/?limit=150`, { headers });
        if (crimesRes.ok) {
          const crimesData = await crimesRes.json();
          // Filter FIRs belonging to this station
          const stationFirs = crimesData.results.filter((f: any) => {
            // Find station name from our loaded list
            const currentStationObj = stations.find(s => s.id === selectedStation);
            return currentStationObj ? f.station === currentStationObj.name : false;
          });
          setFirs(stationFirs);
          setIncidentCount(stationFirs.length);
        }
      } catch (e) {
        console.error("Error fetching map coordinates:", e);
      } finally {
        setLoadingMap(false);
      }
    }
    fetchMapData();
  }, [selectedStation, stations]);

  return (
    <div className="space-y-6">
      {/* Station Selector Bar */}
      <div className="glass-panel p-6 rounded-xl border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wider">Predictive Patrol Command Map</h2>
          <p className="text-xs text-slate-400 mt-1">Geospatial crime mapping and optimized route planning</p>
        </div>
        
        <div className="flex items-center gap-4">
          <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Target Station:</label>
          <select 
            value={selectedStation || ""}
            onChange={e => setSelectedStation(Number(e.target.value))}
            className="bg-slate-900 border border-slate-700/50 rounded-lg py-2 px-4 text-slate-100 text-sm focus:outline-none focus:border-blue-500"
          >
            {stations.map(s => (
              <option key={s.id} value={s.id}>{s.name} ({s.district})</option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Grid: Map & Route details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 h-[550px] relative">
          {!loadingMap ? (
            <MapContainer 
              stationLocation={hqLocation} 
              firs={firs} 
              hotspots={hotspots} 
              patrolRoute={patrolRoute} 
            />
          ) : (
            <div className="w-full h-full bg-slate-900/60 border border-slate-800 rounded-xl flex items-center justify-center">
              <span className="text-cyan-400 font-bold text-sm animate-pulse tracking-widest">RECALCULATING HOTZONE COORDINATES...</span>
            </div>
          )}
        </div>

        {/* Patrol directions card */}
        <div className="glass-panel p-6 rounded-xl border border-slate-800 flex flex-col justify-between space-y-6 h-[550px]">
          <div>
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 mb-4 flex items-center gap-2">
              <Navigation className="w-5 h-5 text-cyan-400" />
              Optimal Patrol Path Waypoints
            </h3>
            
            <div className="space-y-3 overflow-y-auto max-h-[340px] pr-2">
              {patrolRoute.length === 0 ? (
                <p className="text-slate-500 text-xs italic">Select a station to display patrol checkpoints.</p>
              ) : (
                patrolRoute.map((pt, idx) => (
                  <div key={idx} className="flex items-start gap-3 bg-slate-950/40 border border-slate-800 p-2.5 rounded">
                    <div className="w-5 h-5 bg-cyan-500/10 border border-cyan-400 text-cyan-400 text-[10px] font-bold rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                      {idx + 1}
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-slate-200">{pt.name}</p>
                      <p className="text-[10px] text-slate-500 mt-0.5">Coords: {pt.lat.toFixed(4)}, {pt.lng.toFixed(4)}</p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Quick Stats Panel */}
          <div className="pt-4 border-t border-slate-800/80 grid grid-cols-2 gap-4">
            <div className="bg-slate-950/40 p-3 rounded border border-slate-800/50">
              <span className="text-[10px] font-semibold text-slate-500 uppercase">Analyzed Cases</span>
              <p className="text-lg font-bold text-red-400 mt-1">{incidentCount}</p>
            </div>
            <div className="bg-slate-950/40 p-3 rounded border border-slate-800/50">
              <span className="text-[10px] font-semibold text-slate-500 uppercase">Hotspot Densities</span>
              <p className="text-lg font-bold text-orange-400 mt-1">{hotspots.length}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
