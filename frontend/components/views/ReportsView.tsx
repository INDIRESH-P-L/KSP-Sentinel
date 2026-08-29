"use client";

import React, { useState, useEffect } from "react";
import { FileSpreadsheet, ShieldCheck, ChevronRight, X, Database, AlertTriangle } from "lucide-react";
// authFetch, not publicFetch: every endpoint this view calls now requires a
// bearer token. The whole app was written against publicFetch because
// get_current_user fabricated an identity for unauthenticated requests, so
// omitting the header still returned data. It no longer does -- these calls
// would 401 and the view would silently render its mock/empty state.
import { authFetch } from "@/lib/api";
import { SectionTitle, PanelLabel, Loading } from "@/components/ui/primitives";
import { mockRankings, mockRiskExplanation } from "@/lib/mock";
import type { DistrictRanking, RiskExplanation } from "@/lib/types";

function riskColor(score: number) {
  return score >= 80 ? "var(--color-danger)" : score >= 60 ? "var(--color-warn)" : "var(--color-ok)";
}

interface FileStoreItem {
  id: string;
  file_name: string;
  file_size?: number | string;
}

export default function ReportsView() {
  const [rankings, setRankings] = useState<DistrictRanking[]>(mockRankings);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<DistrictRanking | null>(null);
  const [explanation, setExplanation] = useState<RiskExplanation | null>(null);
  const [loadingExpl, setLoadingExpl] = useState(false);

  // File Store imports state
  const [files, setFiles] = useState<FileStoreItem[]>([]);
  const [filesLoading, setFilesLoading] = useState(true);
  const [importStatus, setImportStatus] = useState<Record<string, string>>({});
  const [importingFileId, setImportingFileId] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      try {
        const res = await authFetch("/api/districts/rankings");
        if (res.ok && isMounted) {
          // Backend names two fields differently: crime_rate_per_lakh and
          // risk_score, where DistrictRanking/this view use crime_rate and
          // threat_score. Without the second mapping the Threat Score column
          // renders as a bare "/ 100".
          const rows: (DistrictRanking & { crime_rate_per_lakh?: number; risk_score?: number })[] = await res.json();
          setRankings(
            rows.map((r) => ({
              ...r,
              crime_rate: r.crime_rate_per_lakh ?? r.crime_rate,
              threat_score: r.risk_score ?? r.threat_score,
            }))
          );
        }
        else if (isMounted) setRankings(mockRankings);
      } catch {
        if (isMounted) setRankings(mockRankings);
      } finally {
        if (isMounted) setLoading(false);
      }
    })();

    (async () => {
      try {
        const res = await authFetch("/api/export/filestore/files");
        if (res.ok && isMounted) {
          const data = await res.json();
          // The zoho API response returns an array inside 'data' or directly
          setFiles(data.data || data || []);
        }
      } catch (e) {
        console.error("Failed to load files", e);
      } finally {
        if (isMounted) setFilesLoading(false);
      }
    })();

    return () => {
      isMounted = false;
    };
  }, []);

  const handleImport = async (fileId: string, filename: string) => {
    let tableName = "Crimes";
    let findBy = "incident_id";
    if (filename.toLowerCase().includes("officer")) {
      tableName = "Officers";
      findBy = "officer_id";
    }

    setImportingFileId(fileId);
    try {
      const res = await authFetch(
        `/api/export/filestore/import?file_id=${fileId}&table_name=${tableName}&find_by=${findBy}&operation=insert`, { method: "POST" }
      );
      const data = await res.json();
      if (res.ok) {
        setImportStatus((prev) => ({
          ...prev,
          [fileId]: `Success: Job #${data.job_id || "Scheduled"}`,
        }));
      } else {
        setImportStatus((prev) => ({
          ...prev,
          [fileId]: `Error: ${data.detail || data.error || "Failed"}`,
        }));
      }
    } catch {
      setImportStatus((prev) => ({ ...prev, [fileId]: "Network error" }));
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
    <div className="relative flex flex-col gap-[22px] fade-up">
      <SectionTitle>Briefing Reports &amp; Rankings</SectionTitle>

      {/* Export cards */}
      <div className="grid grid-cols-1 gap-[18px] md:grid-cols-2">
        <ExportCard
          icon={Database}
          tone="border-[var(--color-ok)]/20 bg-[var(--color-ok)]/10 text-[var(--color-ok)]"
          title="District Risk Ledger"
          desc="Export safety indices and demographic summaries."
          path="/api/export/csv/district-report"
          filename="ksp_district_risk_report.csv"
        />
        <ExportCard
          icon={FileSpreadsheet}
          tone="border-[var(--color-accent-blue)]/20 bg-[var(--color-accent-blue)]/10 text-[var(--color-accent-blue)]"
          title="FIR Record Database"
          desc="Export all geocoded complaint rows as CSV."
          path="/api/export/csv/crime-records"
          filename="ksp_crime_records_all.csv"
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
          These datasets are stored directly in your Catalyst File Store. Click &quot;Import&quot; to schedule a serverless bulk write job to load the rows directly into the Catalyst Datastore without downloading files locally.
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

/**
 * Export tile.
 *
 * Downloads go through `authFetch` and are saved from a blob rather than being a
 * plain <a href>. A bare href cannot carry the Authorization header, so the export
 * endpoints had to stay open to unauthenticated callers for the link to work; fetching
 * here lets those routes require Investigator clearance. It also keeps the token out of
 * the URL, where it would end up in server logs and Referer headers.
 */
function ExportCard({
  icon: Icon, tone, title, desc, path, filename,
}: { icon: React.ElementType; tone: string; title: string; desc: string; path: string; filename: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Prefer the server's own filename, falling back to the caller's. */
  const nameFrom = (disposition: string | null) => {
    const match = disposition?.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
    return match ? decodeURIComponent(match[1].trim()) : filename;
  };

  const download = async () => {
    setBusy(true);
    setError(null);
    let objectUrl: string | null = null;
    try {
      const res = await authFetch(path);
      if (!res.ok) {
        setError(
          res.status === 403
            ? "Your role is not cleared for this export."
            : `Export failed (${res.status}).`
        );
        return;
      }
      const blob = await res.blob();
      objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = nameFrom(res.headers.get("Content-Disposition"));
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch {
      setError("Cannot reach the export service.");
    } finally {
      // Revoking immediately after click() can cancel the download in some browsers,
      // so release the object URL on the next tick instead of in this frame.
      if (objectUrl) setTimeout(() => URL.revokeObjectURL(objectUrl as string), 10_000);
      setBusy(false);
    }
  };

  return (
    <div className="glass glass-hover flex items-center justify-between p-6">
      <div className="flex min-w-0 items-center gap-4">
        <div className={`shrink-0 rounded-[var(--radius-well)] border p-3 ${tone}`}>
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <h4 className="text-sm font-bold uppercase tracking-wider text-[var(--color-ink)]">{title}</h4>
          <p className="mt-0.5 text-[10px] text-[var(--color-ink-faint)]">{desc}</p>
          {error && (
            <p className="mt-1 text-[10px] font-semibold text-[var(--color-danger)]">{error}</p>
          )}
        </div>
      </div>
      <button
        type="button"
        onClick={download}
        disabled={busy}
        className="flex shrink-0 items-center gap-2 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-white/[0.02] px-5 py-2.5 text-xs font-semibold text-[var(--color-ink-muted)] transition-all hover:border-[var(--color-accent-cyan)] hover:text-[var(--color-accent-cyan)] disabled:cursor-not-allowed disabled:opacity-60"
      >
        <FileSpreadsheet className={`h-4 w-4 ${busy ? "spin" : ""}`} />
        {busy ? "Preparing…" : "Download"}
      </button>
    </div>
  );
}
