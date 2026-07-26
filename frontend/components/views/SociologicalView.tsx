"use client";

import React, { useState, useEffect, useMemo } from "react";
import { Brain, Globe, Layers, AlertTriangle } from "lucide-react";
import { publicFetch, normalizeAnomalies } from "@/lib/api";
import { SectionTitle, PanelLabel, Pill, Loading, Gauge, Stat } from "@/components/ui/primitives";
import GlassScatter, { type ScatterPoint } from "@/components/ui/glass-scatter";
import { ACCENT_CYAN, ACCENT_BLUE, ACCENT_PURPLE, OK, WARN, RED } from "@/lib/chart-theme";
import { mockSocioEconomic, mockAnomalies, mockDistricts, mockRiskExplanation } from "@/lib/mock";
import type { SocioEconomic, Anomaly, District, RiskExplanation } from "@/lib/types";

function prettyCorrKey(k: string) {
  return k.replace(/_/g, " ").replace(/\bvs\b/, "↔");
}

export default function SociologicalView() {
  const [socio, setSocio] = useState<SocioEconomic>(mockSocioEconomic);
  const [anomalies, setAnomalies] = useState<Anomaly[]>(mockAnomalies);
  const [districts] = useState<District[]>(mockDistricts);
  const [selectedDistrict, setSelectedDistrict] = useState<District>(mockDistricts[0]);
  const [shap, setShap] = useState<RiskExplanation>(mockRiskExplanation);
  const [loading, setLoading] = useState(true);

  const [grokInsight, setGrokInsight] = useState<string | null>(null);
  const [grokLoading, setGrokLoading] = useState(false);
  const [grokError, setGrokError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const sRes = await publicFetch("/api/dashboard/socio-economic");
        if (sRes.ok) setSocio(await sRes.json());
        const aRes = await publicFetch("/api/dashboard/anomalies");
        if (aRes.ok) setAnomalies(normalizeAnomalies(await aRes.json()));
      } catch {
        /* mock */
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const res = await publicFetch(`/api/districts/${selectedDistrict.id}/explain-risk`);
        if (res.ok) setShap(await res.json());
        else setShap(mockRiskExplanation);
      } catch {
        setShap(mockRiskExplanation);
      }
    })();
  }, [selectedDistrict]);

  const corrData = useMemo(() => {
    // Backend nests correlations two levels deep (metric -> category -> coefficient);
    // flatten to the {key, value} pairs this view actually charts.
    const flat: { key: string; metric: string; category: string; value: number }[] = [];
    for (const [metric, byCategory] of Object.entries(socio.correlations)) {
      if (byCategory && typeof byCategory === "object") {
        for (const [category, coef] of Object.entries(byCategory as Record<string, number>)) {
          flat.push({ key: prettyCorrKey(`${metric} vs ${category}`), metric: prettyCorrKey(metric), category, value: coef });
        }
      } else if (typeof byCategory === "number") {
        flat.push({ key: prettyCorrKey(metric), metric: prettyCorrKey(metric), category: "", value: byCategory });
      }
    }
    return flat.sort((a, b) => a.value - b.value);
  }, [socio]);

  // Live data pairs every indicator with all ~110 crime categories — several
  // hundred rows. Only the strongest linkages are readable or worth ranking.
  const topFactors = useMemo(
    () => [...corrData].sort((a, b) => Math.abs(b.value) - Math.abs(a.value)).slice(0, 8),
    [corrData]
  );
  const hasSignal = topFactors.some((f) => Math.abs(f.value) >= 0.005);

  const strongest = useMemo(
    () => corrData.reduce((best, c) => (Math.abs(c.value) > Math.abs(best.value) ? c : best), corrData[0]),
    [corrData]
  );

  const topThreat = useMemo(() => [...districts].sort((a, b) => b.risk_score - a.risk_score)[0], [districts]);

  // The live endpoint sends `districts` (named, with population); the mock sends
  // pre-projected `scatter_data`. Prefer the richer live shape, fall back to the
  // mock's, and tolerate neither being present.
  const scatterPoints = useMemo<ScatterPoint[]>(() => {
    if (socio.districts?.length) {
      const maxPop = Math.max(...socio.districts.map((d) => d.population ?? 0), 1);
      return socio.districts.map((d) => ({
        x: d.urbanization_rate,
        y: d.risk_score,
        label: d.name,
        weight: (d.population ?? 0) / maxPop,
      }));
    }
    const rows = socio.scatter_data ?? [];
    const maxUrb = Math.max(...rows.map((r) => r.urbanization), 1);
    return rows.map((r, i) => ({
      x: r.urbanization,
      y: r.threat_score,
      label: r.district ?? `District ${i + 1}`,
      weight: r.urbanization / maxUrb,
    }));
  }, [socio]);

  const shapFactors = [
    { name: "Urbanization / Densification", value: shap.urbanization_impact, desc: "High density raises property & digital-theft risk indices." },
    { name: "Poverty (BPL) Friction", value: shap.poverty_impact, desc: "Economic friction raises general property break-ins." },
    { name: "Literacy Marginalization", value: shap.literacy_impact, desc: "Lower literacy correlates with susceptibility to cyber-phishing." },
  ];

  const urbanizationRate = socio.districts?.find(d => d.id === selectedDistrict.id)?.urbanization_rate ?? (socio.scatter_data?.[0]?.urbanization ?? 0);
  
  const generateGrokInsight = async () => {
    setGrokLoading(true);
    setGrokError(null);
    try {
      const res = await publicFetch("/api/grok/sociological-insight", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          district_name: selectedDistrict.name,
          risk_score: selectedDistrict.risk_score,
          urbanization_rate: urbanizationRate,
          top_factors: topFactors,
          anomalies: anomalies
        })
      });
      if (res.ok) {
        const data = await res.json();
        setGrokInsight(data.insight);
      } else {
        const errData = await res.json().catch(() => null);
        setGrokError(errData?.detail || `API Error: ${res.status}`);
      }
    } catch (err: any) {
      setGrokError(err.message || "Failed to generate insight");
    } finally {
      setGrokLoading(false);
    }
  };

  if (loading) return <Loading label="Compiling sociological correlations…" />;

  return (
    <div className="flex flex-col gap-[22px] fade-up">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionTitle>Sociological &amp; AI Analytics</SectionTitle>
        <Pill tone="info" className="gap-1.5 px-3 py-1">
          <Brain className="h-3.5 w-3.5" /> Predictive Engine v2
        </Pill>
      </div>

      {/* Hero row */}
      <div className="grid grid-cols-1 gap-[18px] lg:grid-cols-4">
        <div className="glass glass-hover flex items-center gap-[18px] border-[var(--color-danger)]/20 p-5 lg:col-span-2">
          <div className="shrink-0 rounded-[var(--radius-well)] border border-[var(--color-danger)]/25 bg-[var(--color-danger)]/10 p-4 text-[var(--color-danger)]">
            <Globe className="h-8 w-8" />
          </div>
          <div className="min-w-0">
            <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--color-ink-faint)]">Highest Threat District</span>
            <h4 className="mt-1 truncate text-[28px] font-extrabold leading-none text-[var(--color-ink)]">{topThreat.name}</h4>
            <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
              Threat score <Stat className="font-bold text-[var(--color-danger)]">{topThreat.risk_score}/100</Stat>
            </p>
          </div>
        </div>
        <div className="glass flex items-center gap-4 p-5">
          <div className="shrink-0 rounded-[var(--radius-well)] border border-[var(--color-accent-cyan)]/25 bg-[var(--color-accent-cyan)]/10 p-3 text-[var(--color-accent-cyan)]">
            <Layers className="h-6 w-6" />
          </div>
          <div className="min-w-0">
            <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--color-ink-faint)]">Primary Driver</span>
            <h4 className="mt-0.5 truncate text-sm font-bold text-[var(--color-ink)]">{strongest.key}</h4>
            <Stat className="mt-0.5 block text-[10px] text-[var(--color-ink-faint)]">r = {strongest.value.toFixed(2)}</Stat>
          </div>
        </div>
        <div className="glass flex items-center gap-4 p-5">
          <div className="shrink-0 rounded-[var(--radius-well)] border border-[var(--color-warn)]/25 bg-[var(--color-warn)]/10 p-3 text-[var(--color-warn)]">
            <AlertTriangle className="h-6 w-6 pulse-dot" />
          </div>
          <div className="min-w-0">
            <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--color-ink-faint)]">Anomaly Flags</span>
            <h4 className="mt-0.5 text-base font-bold text-[var(--color-ink)]">{anomalies.length} Districts</h4>
            <p className="mt-0.5 text-[10px] text-[var(--color-ink-faint)]">Exceed baseline + 1.5σ</p>
          </div>
        </div>
      </div>

      {/* State indicators */}
      <div className="glass p-5">
        <PanelLabel className="mb-[18px]">State Socio-Economic Indicators</PanelLabel>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Gauge value={77} label="Literacy Rate" color={ACCENT_CYAN} />
          <Gauge value={39} label="Urbanisation" color={ACCENT_PURPLE} />
          <Gauge value={61} label="Digital Access" color={ACCENT_BLUE} />
          <Gauge value={84} label="Gender Parity" color={OK} />
        </div>
      </div>

      {/* Correlation + scatter */}
      <div className="grid grid-cols-1 gap-[18px] lg:grid-cols-2">
        <div className="glass p-5">
          <PanelLabel className="mb-1">Strongest Socio-Economic Linkages</PanelLabel>
          <p className="mb-[18px] text-[11px] text-[var(--color-ink-faint)]">
            Top {topFactors.length} of {corrData.length.toLocaleString()} indicator ↔ crime-category pairs, by |r|
          </p>
          {hasSignal ? (
            <div className="flex flex-col gap-3.5">
              {topFactors.map((f) => {
                const positive = f.value >= 0;
                const color = positive ? (f.value > 0.6 ? RED : WARN) : OK;
                return (
                  <div key={f.key} className="grid grid-cols-[minmax(0,170px)_1fr_52px] items-center gap-3.5">
                    <div className="min-w-0">
                      <p className="truncate text-xs font-semibold text-[var(--color-ink)]">{f.metric}</p>
                      <p className="truncate text-[10px] text-[var(--color-ink-faint)]">{f.category}</p>
                    </div>
                    <div className="h-[9px] overflow-hidden rounded-full bg-white/[0.05]">
                      <div
                        className="h-full rounded-full transition-[width] duration-1000 ease-[cubic-bezier(.2,.9,.2,1)]"
                        style={{
                          width: `${Math.min(100, Math.abs(f.value) * 100)}%`,
                          background: color,
                          boxShadow: `0 0 10px ${color}66`,
                        }}
                      />
                    </div>
                    <Stat className="text-right text-[13px] font-bold" style={{ color }}>
                      {positive ? "+" : ""}{f.value.toFixed(2)}
                    </Stat>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="py-10 text-center text-xs leading-relaxed text-[var(--color-ink-faint)]">
              All {corrData.length.toLocaleString()} coefficients are effectively zero — the district indicators in this
              dataset carry no variance to correlate against.
            </p>
          )}
          <p className="mt-4 text-center text-[10px] italic text-[var(--color-ink-faint)]">
            +1.0 = strong positive linkage · −1.0 = strong inhibitory linkage.
          </p>
        </div>

        <div className="glass p-5">
          <PanelLabel className="mb-1">Urbanization vs. Threat Score</PanelLabel>
          <p className="mb-2.5 text-[11px] text-[var(--color-ink-faint)]">
            Each bubble is a district · size ∝ population · dashed line = fitted trend
          </p>
          <div className="h-64 w-full">
            <GlassScatter
              points={scatterPoints}
              xLabel="Urbanization Rate"
              yLabel="Threat Score"
              xUnit="%"
            />
          </div>
        </div>
      </div>

      {/* District list + SHAP */}
      <div className="grid grid-cols-1 gap-[18px] lg:grid-cols-3">
        <div className="glass space-y-3 p-5 lg:col-span-2">
          <PanelLabel>AI Threat Risk by District</PanelLabel>
          <div className="max-h-[350px] space-y-3 overflow-y-auto pr-1">
            {districts.map((d) => {
              const active = selectedDistrict.id === d.id;
              const tone = d.risk_score >= 80 ? RED : d.risk_score >= 60 ? WARN : OK;
              return (
                <button
                  key={d.id}
                  onClick={() => setSelectedDistrict(d)}
                  className={`flex w-full flex-col gap-1.5 rounded-[var(--radius-well)] border p-4 text-left transition-all ${
                    active ? "border-[var(--color-accent-purple)]/40 bg-[var(--color-accent-purple)]/10" : "border-[var(--color-hairline)] bg-white/[0.02] hover:border-[var(--color-hairline-strong)]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-[var(--color-ink)]">{d.name}</h4>
                    <Stat className="text-xs font-bold" style={{ color: tone }}>{d.risk_score} / 100</Stat>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.05]">
                    <div
                      className="h-full rounded-full transition-[width] duration-1000 ease-[cubic-bezier(.2,.9,.2,1)]"
                      style={{ width: `${d.risk_score}%`, background: tone, boxShadow: `0 0 10px ${tone}66` }}
                    />
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="glass flex flex-col p-5">
          <div className="mb-4 border-b border-[var(--color-hairline)] pb-3">
            <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--color-accent-purple)]">SHAP Risk Explainer</span>
            <h3 className="mt-1 text-base font-bold uppercase text-[var(--color-ink)]">{selectedDistrict.name}</h3>
          </div>
          <div className="space-y-3">
            {shapFactors.map((f, i) => (
              <div key={i} className="space-y-1 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-white/[0.02] p-3">
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span className="text-[var(--color-ink-muted)]">{f.name}</span>
                  <span className={f.value >= 0 ? "font-bold text-[var(--color-danger)]" : "font-bold text-[var(--color-ok)]"}>
                    {f.value >= 0 ? "+" : ""}{f.value}
                  </span>
                </div>
                <p className="text-[10px] leading-relaxed text-[var(--color-ink-faint)]">{f.desc}</p>
              </div>
            ))}
          </div>

          <div className="mt-4 border-t border-[var(--color-hairline)] pt-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--color-accent-purple)]">AI Insight</span>
              <button 
                onClick={generateGrokInsight}
                disabled={grokLoading}
                className="flex items-center gap-1.5 rounded-full border border-[var(--color-accent-purple)]/30 bg-[var(--color-accent-purple)]/10 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-[var(--color-accent-purple)] hover:bg-[var(--color-accent-purple)]/20 transition-colors disabled:opacity-50"
              >
                {grokLoading ? "Analyzing..." : "Generate Grok Insight"}
              </button>
            </div>
            {grokError && (
              <p className="mb-2 text-xs text-[var(--color-red)]">{grokError}</p>
            )}
            {grokInsight && (
              <div className="rounded-[var(--radius-well)] border border-[var(--color-accent-purple)]/20 bg-[var(--color-accent-purple)]/[0.04] p-3">
                <p className="text-xs leading-relaxed text-[var(--color-ink)]">{grokInsight}</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Anomaly feed */}
      <div className="glass space-y-4 p-5">
        <PanelLabel className="flex items-center gap-2 !text-[var(--color-danger)]">
          <AlertTriangle className="h-4 w-4 pulse-dot" /> Statistical Anomaly Alert Feed (Current Month vs. Baseline)
        </PanelLabel>
        <div className="space-y-3">
          {anomalies.map((a, i) => {
            const crit = a.severity === "CRITICAL";
            return (
              <div
                key={i}
                className={`flex flex-col justify-between gap-3 rounded-[var(--radius-well)] border p-4 md:flex-row md:items-center ${
                  crit ? "border-[var(--color-danger)]/30 bg-[var(--color-danger)]/[0.06]" : "border-[var(--color-warn)]/20 bg-[var(--color-warn)]/[0.05]"
                }`}
              >
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2.5">
                    <Pill tone={crit ? "danger" : "warn"}>{a.severity ?? "INFO"}</Pill>
                    <h4 className="text-xs font-bold uppercase text-[var(--color-ink)]">{a.district}</h4>
                  </div>
                  <p className="text-xs font-semibold text-[var(--color-ink-muted)]">{a.message}</p>
                  <Stat className="block text-[10px] font-semibold uppercase text-[var(--color-ink-faint)]">z-Score: +{a.z_score.toFixed(1)}σ</Stat>
                </div>
                <div className="shrink-0 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-white/[0.02] px-4 py-2 text-center">
                  <span className="block text-[10px] font-bold uppercase text-[var(--color-ink-faint)]">Anomalous Spike</span>
                  <Stat className="text-base font-bold text-[var(--color-danger)]">+{Math.round(a.z_score * 65)}%</Stat>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
