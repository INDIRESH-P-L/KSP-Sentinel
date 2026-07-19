"use client";

import React, { useState, useEffect } from "react";
import { FileSpreadsheet, ShieldCheck, ChevronRight, X, Database, AlertTriangle } from "lucide-react";
import { authFetch } from "@/lib/api";
import { API_BASE } from "@/lib/api";
import { SectionTitle, PanelLabel, Loading } from "@/components/ui/primitives";
import { mockRankings, mockRiskExplanation } from "@/lib/mock";
import type { DistrictRanking, RiskExplanation } from "@/lib/types";

function riskColor(score: number) {
  return score >= 80 ? "var(--color-danger)" : score >= 60 ? "var(--color-warn)" : "var(--color-ok)";
}

export default function ReportsView() {
  const [rankings, setRankings] = useState<DistrictRanking[]>(mockRankings);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<DistrictRanking | null>(null);
  const [explanation, setExplanation] = useState<RiskExplanation | null>(null);
  const [loadingExpl, setLoadingExpl] = useState(false);

  // File Store imports state
  const [files, setFiles] = useState<any[]>([]);
  const [filesLoading, setFilesLoading] = useState(true);
  const [importStatus, setImportStatus] = useState<Record<string, string>>({});
  const [importingFileId, setImportingFileId] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await authFetch("/api/districts/rankings");
        if (res.ok) setRankings(await res.json());
        else setRankings(mockRankings);
      } catch {
        setRankings(mockRankings);
      } finally {
        setLoading(false);
      }
    })();

    // Fetch File Store files
    (async () => {
      try {
        const res = await authFetch("/api/export/filestore/files");
        if (res.ok) {
          const data = await res.json();
          setFiles(data.data || []);
        }
      } catch (err) {
        console.error("Failed to load File Store files:", err);
      } finally {
        setFilesLoading(false);
      }
    })();
  }, []);

  const handleImport = async (fileId: string, fileName: string) => {
    let tableName = "fir_cases";
    if (fileName.toUpperCase().includes("REVIEW") || fileName.toUpperCase().includes("REVEIW")) {
      tableName = "crime_review_monthly";
    }
    
    setImportingFileId(fileId);
    setImportStatus(prev => ({ ...prev, [fileId]: "Triggering import..." }));
    try {
      const res = await authFetch(`/api/export/filestore/import?file_id=${fileId}&table_name=${tableName}`, {
        method: "POST"
      });
      if (res.ok) {
        const data = await res.json();
        setImportStatus(prev => ({ 
          ...prev, 
          [fileId]: `Success! Job ID: ${data.job_id || "Scheduled"}` 
        }));
      } else {
        const err = await res.json().catch(() => ({}));
        setImportStatus(prev => ({ 
          ...prev, 
          [fileId]: `Failed: ${err.detail || "Error"}` 
        }));
      }
    } catch {
      setImportStatus(prev => ({ ...prev, [fileId]: "Failed: network error" }));
    } finally {
      setImportingFileId(null);
    }
  };

  const explainRisk = async (d: DistrictRanking) => {
    setSelected(d);
    setLoadingExpl(true);
    setExplanation(null);
    try {
      const res = await authFetch(`/api/districts/${d.rank}/explain-risk`);
      if (res.ok) setExplanation(await res.json());
      else setExplanation(mockRiskExplanation);
    } catch {
      setExplanation(mockRiskExplanation);
    } finally {
      setLoadingExpl(false);
    }
  };

  const shapRows = explanation
    ? [
        { name: "Urbanization / Densification", value: explanation.urbanization_impact },
        { name: "Poverty (BPL) Friction", value: explanation.poverty_impact },
        { name: "Literacy Marginalization", value: explanation.literacy_impact },
      ]
    : [];

  return (
    <div className="relative space-y-6 fade-up">
      <SectionTitle>Briefing Reports &amp; Rankings</SectionTitle>

      {/* Export cards */}
      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        <ExportCard
          icon={Database}
          tone="border-[var(--color-ok)]/20 bg-[var(--color-ok)]/10 text-[var(--color-ok)]"
          title="District Risk Ledger"
          desc="Export safety indices and demographic summaries."
          href={`${API_BASE}/api/export/csv/district-report`}
        />
        <ExportCard
          icon={FileSpreadsheet}
          tone="border-[var(--color-accent-blue)]/20 bg-[var(--color-accent-blue)]/10 text-[var(--color-accent-blue)]"
          title="FIR Record Database"
          desc="Export all geocoded complaint rows as CSV."
          href={`${API_BASE}/api/export/csv/crime-records`}
        />
      </div>

      {/* Rankings table */}
      <div className="glass p-5">
        <PanelLabel className="mb-5 flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-[var(--color-ok)]" /> Karnataka Districts Security Rankings
        </PanelLabel>
        {loading ? (
          <Loading label="Loading ledger records…" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-[var(--color-hairline)] text-[var(--color-ink-faint)]">
                  {["Rank", "District Name", "Crime Rate (per lakh)", "Conviction Rate %", "Threat Score", "XAI Profile"].map((h, i) => (
                    <th key={h} className={`px-5 py-3 font-semibold uppercase tracking-wider ${i === 5 ? "text-right" : ""}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-hairline)]">
                {rankings.map((d) => (
                  <tr key={d.rank} className="transition-colors hover:bg-white/[0.02]">
                    <td className="px-5 py-4 font-bold text-[var(--color-ink-faint)]">#{d.rank}</td>
                    <td className="px-5 py-4 font-semibold text-[var(--color-ink)]">{d.name}</td>
                    <td className="px-5 py-4 text-[var(--color-ink-muted)]">{d.crime_rate.toFixed(2)}</td>
                    <td className="px-5 py-4 text-[var(--color-ink-muted)]">{d.conviction_rate.toFixed(1)}%</td>
                    <td className="px-5 py-4 font-bold" style={{ color: riskColor(d.threat_score) }}>{d.threat_score} / 100</td>
                    <td className="px-5 py-4 text-right">
                      <button
                        onClick={() => explainRisk(d)}
                        className="ml-auto flex items-center gap-1 rounded-full border border-[var(--color-accent-blue)]/25 bg-[var(--color-accent-blue)]/10 px-3.5 py-1.5 text-[10px] font-bold uppercase text-[var(--color-ink-muted)] transition-all hover:border-[var(--color-accent-cyan)] hover:text-[var(--color-accent-cyan)]"
                      >
                        Explain Risk <ChevronRight className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* SHAP drawer */}
      {selected && (
        <>
          <div className="fixed inset-0 z-40 bg-black/50" onClick={() => setSelected(null)} />
          <div className="glass fixed inset-y-0 right-0 z-50 w-full max-w-md space-y-6 overflow-y-auto !rounded-none border-l p-8">
            <div className="flex items-center justify-between border-b border-[var(--color-hairline)] pb-4">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--color-accent-purple)]">Explainable AI Diagnostic</span>
                <h3 className="mt-1 text-lg font-bold uppercase text-[var(--color-ink)]">{selected.name}</h3>
              </div>
              <button onClick={() => setSelected(null)} className="rounded-full p-1.5 text-[var(--color-ink-faint)] hover:text-[var(--color-ink)]">
                <X className="h-5 w-5" />
              </button>
            </div>

            {loadingExpl ? (
              <Loading label="Dissecting SHAP values…" />
            ) : (
              <div className="space-y-6">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs font-semibold uppercase text-[var(--color-ink-muted)]">
                    <span>Crime Hazard Index</span>
                    <span className="font-bold" style={{ color: riskColor(selected.threat_score) }}>{selected.threat_score} / 100</span>
                  </div>
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-white/[0.04]">
                    <div className="h-full rounded-full" style={{ width: `${selected.threat_score}%`, background: riskColor(selected.threat_score) }} />
                  </div>
                </div>

                <div className="space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--color-ink-muted)]">SHAP Feature Importance</h4>
                  {shapRows.map((r) => {
                    const mag = Math.min(100, Math.abs(r.value) * 5);
                    const pos = r.value >= 0;
                    return (
                      <div key={r.name} className="space-y-1">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="text-[var(--color-ink-muted)]">{r.name}</span>
                          <span className={pos ? "font-bold text-[var(--color-danger)]" : "font-bold text-[var(--color-ok)]"}>
                            {pos ? "+" : ""}{r.value}
                          </span>
                        </div>
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.04]">
                          <div className="h-full rounded-full" style={{ width: `${mag}%`, background: pos ? "var(--color-danger)" : "var(--color-ok)" }} />
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div className="space-y-3 rounded-[var(--radius-well)] border border-[var(--color-accent-blue)]/15 bg-[var(--color-accent-blue)]/[0.04] p-5">
                  <h4 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[var(--color-ink)]">
                    <AlertTriangle className="h-4 w-4 text-[var(--color-accent-cyan)] pulse-dot" /> Tactical Patrol Guidelines
                  </h4>
                  <ul className="ml-4 list-disc space-y-2 text-[11px] leading-relaxed text-[var(--color-ink-muted)]">
                    <li>Increase evening patrol density in high-urbanization corridors.</li>
                    <li>Deploy cyber-awareness outreach where literacy impact is negative.</li>
                    <li>Coordinate with welfare units in high-poverty-friction wards.</li>
                  </ul>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* File Store Manager */}
      <div className="glass p-5">
        <PanelLabel className="mb-5 flex items-center gap-2">
          <Database className="h-4 w-4 text-[var(--color-accent-cyan)]" /> File Store Datasets &amp; Direct Imports
        </PanelLabel>
        <p className="mb-4 text-xs text-[var(--color-ink-muted)]">
          These datasets are stored directly in your Catalyst File Store. Click "Import" to schedule a serverless bulk write job to load the rows directly into the Catalyst Datastore without downloading files locally.
        </p>
        
        {filesLoading ? (
          <Loading label="Querying Catalyst File Store..." />
        ) : files.length === 0 ? (
          <div className="text-center py-6 text-xs text-[var(--color-ink-faint)]">
            No files found in File Store folder `ksp`.
          </div>
        ) : (
          <div className="max-h-96 overflow-y-auto rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-white/[0.01]">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-[var(--color-hairline)] bg-white/[0.02] text-[var(--color-ink-faint)]">
                  {["File Name", "Size (bytes)", "Target Table", "Import Action", "Job Status"].map((h) => (
                    <th key={h} className="px-5 py-3 font-semibold uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-hairline)]">
                {files.map((f) => {
                  const targetTable = f.file_name.toUpperCase().includes("REVIEW") || f.file_name.toUpperCase().includes("REVEIW") 
                    ? "crime_review_monthly" 
                    : "fir_cases";
                  const status = importStatus[f.id] || "Ready";
                  return (
                    <tr key={f.id} className="transition-colors hover:bg-white/[0.01]">
                      <td className="px-5 py-4 font-mono font-semibold text-[var(--color-ink)]">{f.file_name}</td>
                      <td className="px-5 py-4 text-[var(--color-ink-muted)]">{Number(f.file_size).toLocaleString()}</td>
                      <td className="px-5 py-4 font-mono text-[var(--color-accent-cyan)]">{targetTable}</td>
                      <td className="px-5 py-4">
                        <button
                          onClick={() => handleImport(f.id, f.file_name)}
                          disabled={importingFileId !== null}
                          className="rounded-lg border border-[var(--color-accent-cyan)]/25 bg-[var(--color-accent-cyan)]/10 px-3 py-1 text-[10px] font-bold uppercase text-[var(--color-accent-cyan)] transition-all hover:bg-[var(--color-accent-cyan)] hover:text-white disabled:opacity-30"
                        >
                          {importingFileId === f.id ? "Importing..." : "Import"}
                        </button>
                      </td>
                      <td className="px-5 py-4 font-semibold text-[var(--color-ink-muted)]">{status}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function ExportCard({
  icon: Icon, tone, title, desc, href,
}: { icon: React.ElementType; tone: string; title: string; desc: string; href: string }) {
  return (
    <div className="glass glass-hover flex items-center justify-between p-6">
      <div className="flex min-w-0 items-center gap-4">
        <div className={`shrink-0 rounded-[var(--radius-well)] border p-3 ${tone}`}>
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <h4 className="text-sm font-bold uppercase tracking-wider text-[var(--color-ink)]">{title}</h4>
          <p className="mt-0.5 text-[10px] text-[var(--color-ink-faint)]">{desc}</p>
        </div>
      </div>
      <a
        href={href}
        className="flex shrink-0 items-center gap-2 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-white/[0.02] px-5 py-2.5 text-xs font-semibold text-[var(--color-ink-muted)] transition-all hover:border-[var(--color-accent-cyan)] hover:text-[var(--color-accent-cyan)]"
      >
        <FileSpreadsheet className="h-4 w-4" /> Download
      </a>
    </div>
  );
}
