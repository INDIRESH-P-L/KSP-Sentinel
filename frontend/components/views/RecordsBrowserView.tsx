"use client";

import React, { useState, useEffect, useContext } from "react";
import { Folder, FileText, ChevronRight, Server, Database, MapPin } from "lucide-react";
import { authFetch } from "@/lib/api";
import { SectionTitle, Pill } from "@/components/ui/primitives";
import { motion, AnimatePresence } from "framer-motion";
import { TabContext } from "@/components/layout/Shell";

export default function RecordsBrowserView() {
  const { navigationPayload } = useContext(TabContext);

  const [districts, setDistricts] = useState<any[]>([]);
  const [stations, setStations] = useState<any[]>([]);
  
  const [selectedDistrictId, setSelectedDistrictId] = useState<number | null>(() => {
    return navigationPayload?.districtId ? Number(navigationPayload.districtId) : null;
  });
  
  const [selectedStationId, setSelectedStationId] = useState<number | null>(() => {
    return navigationPayload?.stationId ? Number(navigationPayload.stationId) : null;
  });
  
  const [firs, setFirs] = useState<any[]>([]);
  const [loadingFirs, setLoadingFirs] = useState(false);
  
  const [totalFirs, setTotalFirs] = useState(0);
  const [page, setPage] = useState(0);
  const limit = 20;

  useEffect(() => {
    async function loadDistricts() {
      try {
        const res = await authFetch("/api/districts/");
        if (res.ok) {
          const data = await res.json();
          setDistricts(data);
        }
      } catch (e) {
        console.error("Failed to load districts", e);
      }
    }
    loadDistricts();
  }, []);

  useEffect(() => {
    async function loadStations() {
      if (!selectedDistrictId) {
        setStations([]);
        return;
      }
      try {
        const res = await authFetch("/api/districts/stations");
        if (res.ok) {
          const data = await res.json();
          setStations(data.filter((s: any) => s.district === districts.find(d => d.id === selectedDistrictId)?.name));
        }
      } catch (e) {
        console.error("Failed to load stations", e);
      }
    }
    loadStations();
  }, [selectedDistrictId, districts]);

  useEffect(() => {
    async function loadFirs() {
      if (!selectedStationId) {
        setFirs([]);
        return;
      }
      setLoadingFirs(true);
      try {
        const res = await authFetch(`/api/crimes/?station_id=${selectedStationId}&limit=${limit}&offset=${page * limit}`);
        if (res.ok) {
          const data = await res.json();
          setFirs(data.results || []);
          setTotalFirs(data.total || 0);
        }
      } catch (e) {
        console.error("Failed to load FIRs", e);
      } finally {
        setLoadingFirs(false);
      }
    }
    loadFirs();
  }, [selectedStationId, page]);

  return (
    <div className="flex flex-col gap-[22px] fade-up h-full">
      <div className="flex items-center justify-between">
        <SectionTitle>Catalyst Records Explorer</SectionTitle>
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-accent-cyan)]">
          <Server className="h-4 w-4" /> Live FileStore Sync
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6 h-[calc(100vh-140px)]">
        
        {/* DISTRICTS PANEL */}
        <div className="glass col-span-3 flex flex-col overflow-hidden">
          <div className="border-b border-[var(--color-hairline)] bg-[var(--color-surface-2)] p-4 text-xs font-bold uppercase tracking-wider text-[var(--color-ink-muted)] flex items-center gap-2">
            <MapPin className="h-4 w-4" /> Districts
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {districts.map(d => (
              <button
                key={d.id}
                onClick={() => { setSelectedDistrictId(d.id); setSelectedStationId(null); setPage(0); }}
                className={`flex w-full items-center justify-between rounded-md px-3 py-2.5 text-sm transition-all ${
                  selectedDistrictId === d.id
                    ? "bg-[var(--color-accent-blue)]/10 font-bold text-[var(--color-accent-blue)]"
                    : "text-[var(--color-ink)] hover:bg-[var(--color-surface-elevated)]"
                }`}
              >
                <div className="flex items-center gap-2">
                  <Folder className="h-4 w-4 shrink-0" />
                  <span className="truncate">{d.name}</span>
                </div>
                <ChevronRight className={`h-4 w-4 transition-transform ${selectedDistrictId === d.id ? "translate-x-1" : "opacity-0"}`} />
              </button>
            ))}
          </div>
        </div>

        {/* STATIONS PANEL */}
        <div className="glass col-span-3 flex flex-col overflow-hidden">
          <div className="border-b border-[var(--color-hairline)] bg-[var(--color-surface-2)] p-4 text-xs font-bold uppercase tracking-wider text-[var(--color-ink-muted)] flex items-center gap-2">
            <Database className="h-4 w-4" /> Police Stations
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {!selectedDistrictId && (
              <div className="p-4 text-center text-xs italic text-[var(--color-ink-faint)]">
                Select a district first
              </div>
            )}
            {stations.map(s => (
              <button
                key={s.id}
                onClick={() => { setSelectedStationId(s.id); setPage(0); }}
                className={`flex w-full items-center justify-between rounded-md px-3 py-2.5 text-sm transition-all ${
                  selectedStationId === s.id
                    ? "bg-[var(--color-accent-cyan)]/10 font-bold text-[var(--color-accent-cyan)]"
                    : "text-[var(--color-ink)] hover:bg-[var(--color-surface-elevated)]"
                }`}
              >
                <div className="flex items-center gap-2">
                  <Folder className="h-4 w-4 shrink-0" />
                  <span className="truncate">{s.name}</span>
                </div>
                <ChevronRight className={`h-4 w-4 transition-transform ${selectedStationId === s.id ? "translate-x-1" : "opacity-0"}`} />
              </button>
            ))}
          </div>
        </div>

        {/* RECORDS PANEL */}
        <div className="glass col-span-6 flex flex-col overflow-hidden">
          <div className="flex items-center justify-between border-b border-[var(--color-hairline)] bg-[var(--color-surface-2)] p-4">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[var(--color-ink-muted)]">
              <FileText className="h-4 w-4" /> FIR Records
            </div>
            {totalFirs > 0 && (
              <Pill tone="info">{totalFirs.toLocaleString()} Total Cases</Pill>
            )}
          </div>
          
          <div className="flex-1 overflow-y-auto p-4 relative">
            {!selectedStationId && (
              <div className="flex h-full items-center justify-center text-sm italic text-[var(--color-ink-faint)]">
                Select a police station to view live records from Zoho Catalyst
              </div>
            )}
            
            {selectedStationId && loadingFirs && firs.length === 0 && (
              <div className="flex h-full items-center justify-center text-sm font-bold uppercase tracking-widest text-[var(--color-accent-cyan)] animate-pulse">
                Fetching Live Data...
              </div>
            )}

            <AnimatePresence>
              {firs.length > 0 && (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-3">
                  {firs.map((f, i) => (
                    <div key={f.id || i} className="glass-hover flex flex-col gap-3 rounded-[var(--radius-panel)] border border-[var(--color-hairline)] bg-white/[0.01] p-4 transition-colors hover:bg-[var(--color-surface-elevated)]">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h4 className="text-sm font-bold text-[var(--color-ink)]">{f.fir_number}</h4>
                          <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] font-medium text-[var(--color-ink-muted)]">
                            <span className="rounded bg-[var(--color-surface-2)] px-1.5 py-0.5">{new Date(f.date_reported).toLocaleDateString()}</span>
                            <span>•</span>
                            <span className="rounded bg-[var(--color-surface-2)] px-1.5 py-0.5">{f.category}</span>
                            <span>•</span>
                            <span className="text-[var(--color-ink-faint)]">{f.subcategory}</span>
                          </div>
                        </div>
                        <Pill tone={f.status === 'REGISTERED' ? 'warn' : f.status === 'INVESTIGATING' ? 'info' : 'ok'}>
                          {f.status}
                        </Pill>
                      </div>
                      <p className="text-xs leading-relaxed text-[var(--color-ink-muted)] line-clamp-3">
                        {f.description || "No description provided."}
                      </p>
                    </div>
                  ))}
                  
                  {/* PAGINATION */}
                  <div className="flex items-center justify-between pt-4 pb-2">
                    <button 
                      onClick={() => setPage(p => Math.max(0, p - 1))}
                      disabled={page === 0}
                      className="rounded bg-[var(--color-surface-2)] px-3 py-1.5 text-xs font-semibold text-[var(--color-ink)] hover:bg-[var(--color-surface-elevated)] disabled:opacity-50"
                    >
                      Previous
                    </button>
                    <span className="text-xs text-[var(--color-ink-faint)]">
                      Page {page + 1} of {Math.ceil(totalFirs / limit) || 1}
                    </span>
                    <button 
                      onClick={() => setPage(p => p + 1)}
                      disabled={(page + 1) * limit >= totalFirs}
                      className="rounded bg-[var(--color-surface-2)] px-3 py-1.5 text-xs font-semibold text-[var(--color-ink)] hover:bg-[var(--color-surface-elevated)] disabled:opacity-50"
                    >
                      Next
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}
