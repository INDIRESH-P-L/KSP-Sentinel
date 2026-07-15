"use client";

import React, { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { AlertCircle, Navigation, Users, ShieldAlert, Clock, BarChart } from "lucide-react";

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

interface District {
  id: number;
  name: string;
  population: number;
  risk_score: number;
  risk_factors: string;
  urbanization_rate: number;
  literacy_rate: number;
  unemployment_rate: number;
  poverty_rate: number;
}

export default function MapView() {
  const [districts, setDistricts] = useState<District[]>([]);
  const [selectedDistrict, setSelectedDistrict] = useState<number | null>(null);
  
  const [stations, setStations] = useState<any[]>([]);
  const [filteredStations, setFilteredStations] = useState<any[]>([]);
  const [selectedStation, setSelectedStation] = useState<number | null>(null);
  
  const [timeOfDay, setTimeOfDay] = useState("all");
  const [emergingTrends, setEmergingTrends] = useState<any[]>([]);

  // Data for map
  const [hqLocation, setHqLocation] = useState<[number, number]>([12.9778, 77.5714]); // Majestic base
  const [firs, setFirs] = useState<any[]>([]);
  const [hotspots, setHotspots] = useState<any[]>([]);
  const [patrolRoute, setPatrolRoute] = useState<any[]>([]);
  const [incidentCount, setIncidentCount] = useState(0);
  
  const [loadingMap, setLoadingMap] = useState(true);

  // 1. Load all districts
  useEffect(() => {
    async function loadDistricts() {
      try {
        const token = localStorage.getItem("ksp_token");
        const headers: Record<string, string> = {};
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }

        const res = await fetch("http://localhost:8000/api/districts/", { headers });
        if (res.ok) {
          const data = await res.json();
          setDistricts(data);
          if (data.length > 0) {
            // Find "Bengaluru City" or default to first
            const defaultDist = data.find((d: any) => d.name === "Bengaluru City") || data[0];
            setSelectedDistrict(defaultDist.id);
          }
        }
      } catch (e) {
        console.error("Error loading districts:", e);
      }
    }
    loadDistricts();
  }, []);

  // 2. Load all stations & emerging trends
  useEffect(() => {
    async function loadStationsAndTrends() {
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
        }

        const trendRes = await fetch("http://localhost:8000/api/crimes/emerging-trends", { headers });
        if (trendRes.ok) {
          const trendData = await trendRes.json();
          setEmergingTrends(trendData);
        }
      } catch (e) {
        console.error("Error loading stations and trends:", e);
      }
    }
    loadStationsAndTrends();
  }, []);

  // 3. Filter stations when district changes & update map center to average station location
  useEffect(() => {
    if (selectedDistrict === null || stations.length === 0) return;

    const districtObj = districts.find(d => d.id === selectedDistrict);
    if (!districtObj) return;

    // Filter stations belonging to this district
    const matches = stations.filter(s => s.district === districtObj.name);
    setFilteredStations(matches);

    if (matches.length > 0) {
      // Find default station
      setSelectedStation(matches[0].id);
      
      // Compute average coordinate for centering
      const avgLat = matches.reduce((acc, curr) => acc + curr.latitude, 0) / matches.length;
      const avgLng = matches.reduce((acc, curr) => acc + curr.longitude, 0) / matches.length;
      setHqLocation([avgLat, avgLng]);
    } else {
      setSelectedStation(null);
    }
  }, [selectedDistrict, stations, districts]);

  // 4. Fetch hotspots & crimes for selected station + time of day slice
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
        
        // 1. Fetch hotspots and routes with time of day slice
        const hotRes = await fetch(`http://localhost:8000/api/districts/stations/${selectedStation}/hotspots?time_of_day=${timeOfDay}`, { headers });
        if (hotRes.ok) {
          const hotData = await hotRes.json();
          if (hotData.station_location) {
            setHqLocation(hotData.station_location);
          }
          setHotspots(hotData.hotspots || []);
          setPatrolRoute(hotData.route || []);
        }
        
        // 2. Fetch FIR pins
        const crimesRes = await fetch(`http://localhost:8000/api/crimes/?limit=200`, { headers });
        if (crimesRes.ok) {
          const crimesData = await crimesRes.json();
          const currentStationObj = stations.find(s => s.id === selectedStation);
          
          let stationFirs = crimesData.results.filter((f: any) => 
            currentStationObj ? f.station === currentStationObj.name : false
          );

          // Apply client-side time-of-day slice to FIR circles
          if (timeOfDay !== "all") {
            stationFirs = stationFirs.filter((f: any) => {
              if (!f.date_occurred) return false;
              const hour = new Date(f.date_occurred).getHours();
              if (timeOfDay === "night") return hour >= 22 || hour < 4;
              if (timeOfDay === "morning") return hour >= 4 && hour < 12;
              if (timeOfDay === "afternoon") return hour >= 12 && hour < 18;
              if (timeOfDay === "evening") return hour >= 18 && hour < 22;
              return true;
            });
          }

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
  }, [selectedStation, timeOfDay, stations]);

  const selectedDistrictObj = districts.find(d => d.id === selectedDistrict);

  return (
    <div className="space-y-6">
      {/* Selector Panels & Details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* District & Station Selector */}
        <div className="glass-panel p-6 rounded-xl border border-slate-800 flex flex-col justify-between space-y-4 lg:col-span-2">
          <div>
            <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wider">Predictive Patrol Command Map</h2>
            <p className="text-xs text-slate-400 mt-1">Select a district and station to view dynamic spatiotemporal clusters and hotspots</p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider block">1. Target District:</label>
              <select 
                value={selectedDistrict || ""}
                onChange={e => setSelectedDistrict(Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700/50 rounded-lg py-2.5 px-4 text-slate-100 text-sm focus:outline-none focus:border-purple-500"
              >
                {districts.map(d => (
                  <option key={d.id} value={d.id}>{d.name}</option>
                ))}
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider block">2. Target Police Station:</label>
              <select 
                value={selectedStation || ""}
                onChange={e => setSelectedStation(Number(e.target.value))}
                disabled={filteredStations.length === 0}
                className="w-full bg-slate-900 border border-slate-700/50 rounded-lg py-2.5 px-4 text-slate-100 text-sm focus:outline-none focus:border-purple-500 disabled:opacity-40"
              >
                {filteredStations.map(s => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Time of Day Slider/Selector */}
          <div className="space-y-2 pt-2">
            <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Clock className="w-4 h-4 text-cyan-400" />
              Spatiotemporal Time of Day Slice:
            </label>
            <div className="flex flex-wrap gap-2">
              {[
                { id: "all", label: "All Hours" },
                { id: "morning", label: "Morning (04:00 - 12:00)" },
                { id: "afternoon", label: "Afternoon (12:00 - 18:00)" },
                { id: "evening", label: "Evening (18:00 - 22:00)" },
                { id: "night", label: "Night (22:00 - 04:00)" }
              ].map(tod => (
                <button
                  key={tod.id}
                  onClick={() => setTimeOfDay(tod.id)}
                  className={`px-3.5 py-1.5 rounded-lg text-xs font-bold uppercase transition-all cursor-pointer border ${
                    timeOfDay === tod.id
                      ? "bg-purple-600/20 text-purple-300 border-purple-400/50 shadow-md shadow-purple-500/5"
                      : "bg-slate-950/40 border-slate-800 text-slate-400 hover:border-slate-750 hover:text-slate-200"
                  }`}
                >
                  {tod.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* District Threat Dossier */}
        <div className="glass-panel p-6 rounded-xl border border-slate-800 space-y-4 bg-slate-900/40 flex flex-col justify-between">
          <div className="space-y-2.5">
            <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
              <ShieldAlert className="w-5 h-5 text-purple-400" />
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">District Threat Profile</h3>
            </div>
            
            {selectedDistrictObj ? (
              <div className="space-y-2.5 text-xs">
                <div className="flex justify-between py-1 border-b border-slate-800/40">
                  <span className="text-slate-500">Security Index:</span>
                  <span className="text-slate-200 font-bold">{100 - selectedDistrictObj.risk_score} / 100</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800/40">
                  <span className="text-slate-500">Urbanization Level:</span>
                  <span className="text-slate-200 font-bold">{selectedDistrictObj.urbanization_rate || 30.0}%</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800/40">
                  <span className="text-slate-500">Literacy Ratio:</span>
                  <span className="text-slate-200 font-bold">{selectedDistrictObj.literacy_rate || 75.0}%</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-800/40">
                  <span className="text-slate-500">Unemployment Friction:</span>
                  <span className="text-slate-200 font-bold">{selectedDistrictObj.unemployment_rate || 5.0}%</span>
                </div>
                <p className="text-[10px] text-slate-400 mt-2 italic leading-relaxed">
                  <strong>Risk Summary:</strong> {selectedDistrictObj.risk_factors}
                </p>
              </div>
            ) : (
              <p className="text-slate-500 text-xs italic">Select a district to view safety parameters.</p>
            )}
          </div>
          
          <div className="bg-purple-950/20 border border-purple-500/20 rounded p-2.5 text-center">
            <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest block">Threat classification</span>
            <span className={`text-sm font-extrabold uppercase ${
              selectedDistrictObj && selectedDistrictObj.risk_score >= 80 ? "text-red-400" :
              selectedDistrictObj && selectedDistrictObj.risk_score >= 60 ? "text-orange-400" : "text-emerald-400"
            }`}>
              {selectedDistrictObj && selectedDistrictObj.risk_score >= 80 ? "Critical Hazard" :
               selectedDistrictObj && selectedDistrictObj.risk_score >= 60 ? "High Alert" : "Moderate Risk"}
            </span>
          </div>
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
              emergingTrends={emergingTrends}
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
              <span className="text-[10px] font-semibold text-slate-500 uppercase">Filtered Incidents</span>
              <p className="text-lg font-bold text-red-400 mt-1">{incidentCount}</p>
            </div>
            <div className="bg-slate-950/40 p-3 rounded border border-slate-800/50">
              <span className="text-[10px] font-semibold text-slate-500 uppercase">Hotspot Centers</span>
              <p className="text-lg font-bold text-orange-400 mt-1">{hotspots.length}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
