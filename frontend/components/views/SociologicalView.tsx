"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  ScatterChart, Scatter, Cell, ReferenceLine,
} from "recharts";
import { Brain, Globe, Layers, AlertTriangle } from "lucide-react";
import { authFetch } from "@/lib/api";
import { SectionTitle, PanelLabel, Pill, Loading } from "@/components/ui/primitives";
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

  useEffect(() => {
    (async () => {
      try {
        const sRes = await authFetch("/api/dashboard/socio-economic");
        if (sRes.ok) setSocio(await sRes.json());
        const aRes = await authFetch("/api/dashboard/anomalies");
        if (aRes.ok) setAnomalies(await aRes.json());
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
        const res = await authFetch(`/api/districts/${selectedDistrict.id}/explain-risk`);
        if (res.ok) setShap(await res.json());
        else setShap(mockRiskExplanation);
      } catch {
        setShap(mockRiskExplanation);
      }
    })();
  }, [selectedDistrict]);

  const corrData = useMemo(
    () =>
      Object.entries(socio.correlations)
        .map(([k, v]) => ({ key: prettyCorrKey(k), value: v }))
        .sort((a, b) => a.value - b.value),
    [socio]
  );

  const strongest = useMemo(
    () => corrData.reduce((best, c) => (Math.abs(c.value) > Math.abs(best.value) ? c : best), corrData[0]),
    [corrData]
  );

  const topThreat = useMemo(() => [...districts].sort((a, b) => b.risk_score - a.risk_score)[0], [districts]);

  const shapFactors = [
    { name: "Urbanization / Densification", value: shap.urbanization_impact, desc: "High density raises property & digital-theft risk indices." },
    { name: "Poverty (BPL) Friction", value: shap.poverty_impact, desc: "Economic friction raises general property break-ins." },
    { name: "Literacy Marginalization", value: shap.literacy_impact, desc: "Lower literacy correlates with susceptibility to cyber-phishing." },
  ];

  if (loading) return <Loading label="Compiling sociological correlations…" />;

  return (
    <div className="space-y-6 fade-up">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionTitle>Sociological &amp; AI Analytics</SectionTitle>
        <Pill tone="info" className="gap-1.5 px-3 py-1">
          <Brain className="h-3.5 w-3.5" /> Predictive Engine v2
        </Pill>
      </div>

      {/* Hero row */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-4">
        <div className="glass glass-hover flex items-center gap-5 border-[var(--color-danger)]/20 p-5 lg:col-span-2">
          <div className="shrink-0 rounded-[var(--radius-well)] border border-[var(--color-danger)]/25 bg-[var(--color-danger)]/10 p-4 text-[var(--color-danger)]">
            <Globe className="h-8 w-8" />
          </div>
          <div className="min-w-0">
            <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--color-ink-faint)]">Highest Threat District</span>
            <h4 className="mt-1 truncate text-3xl font-extrabold text-[var(--color-ink)]">{topThreat.name}</h4>
            <p className="mt-1 text-xs text-[var(--color-ink-muted)]">
              Threat score <span className="font-bold text-[var(--color-danger)]">{topThreat.risk_score}/100</span>
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
            <p className="mt-0.5 text-[10px] text-[var(--color-ink-faint)]">r = {strongest.value.toFixed(2)}</p>
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

      {/* Correlation + scatter */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="glass p-5">
          <PanelLabel className="mb-5">Pearson Correlation Matrix</PanelLabel>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={corrData} margin={{ left: -10, right: 10, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
                <XAxis dataKey="key" stroke="#64748b" fontSize={9} angle={-25} textAnchor="end" interval={0} height={60} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={10} domain={[-1, 1]} tickLine={false} axisLine={false} />
                <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" />
                <Tooltip
                  contentStyle={{ background: "#111a2b", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, color: "#f8fafc", fontSize: 12 }}
                  formatter={(v) => [Number(v).toFixed(2), "coefficient"]}
                />
                <Bar dataKey="value" radius={4} barSize={22}>
                  {corrData.map((d, i) => (
                    <Cell key={i} fill={d.value >= 0 ? "#10b981" : "#ef4444"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-center text-[10px] italic text-[var(--color-ink-faint)]">
            +1.0 = strong positive linkage · −1.0 = strong inhibitory linkage.
          </p>
        </div>

        <div className="glass p-5">
          <PanelLabel className="mb-5">Urbanization vs. Threat Score</PanelLabel>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
                <CartesianGrid stroke="rgba(255,255,255,0.04)" />
                <XAxis type="number" dataKey="urbanization" name="Urbanization" unit="%" stroke="#64748b" fontSize={10} tickLine={false} />
                <YAxis type="number" dataKey="threat_score" name="Threat" stroke="#64748b" fontSize={10} tickLine={false} />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3" }}
                  content={({ active, payload }) => {
                    if (active && payload?.length) {
                      const p = payload[0].payload;
                      return (
                        <div className="rounded-lg border border-[var(--color-hairline)] bg-[var(--color-elevated)] p-3 text-xs">
                          <p className="font-bold text-[var(--color-ink)]">{p.district}</p>
                          <p className="text-[var(--color-ink-muted)]">Urbanization: {p.urbanization}%</p>
                          <p className="font-semibold text-[var(--color-accent-purple)]">Threat: {p.threat_score}</p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Scatter data={socio.scatter_data} fill="#c084fc" />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* District list + SHAP */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="glass space-y-3 p-5 lg:col-span-2">
          <PanelLabel>AI Threat Risk by District</PanelLabel>
          <div className="max-h-[350px] space-y-3 overflow-y-auto pr-1">
            {districts.map((d) => {
              const active = selectedDistrict.id === d.id;
              const tone = d.risk_score >= 80 ? "#ef4444" : d.risk_score >= 60 ? "#f59e0b" : "#10b981";
              return (
                <button
                  key={d.id}
                  onClick={() => setSelectedDistrict(d)}
                  className={`w-full space-y-1.5 rounded-[var(--radius-well)] border p-4 text-left transition-all ${
                    active ? "border-[var(--color-accent-purple)]/40 bg-[var(--color-accent-purple)]/10" : "border-[var(--color-hairline)] bg-white/[0.02] hover:border-[var(--color-hairline-strong)]"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-[var(--color-ink)]">{d.name}</h4>
                    <span className="text-xs font-bold" style={{ color: tone }}>{d.risk_score} / 100</span>
                  </div>
                  <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.04]">
                    <div className="h-full rounded-full" style={{ width: `${d.risk_score}%`, background: tone }} />
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
                  <p className="text-[10px] font-semibold uppercase text-[var(--color-ink-faint)]">z-Score: +{a.z_score.toFixed(1)}σ</p>
                </div>
                <div className="shrink-0 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-white/[0.02] px-4 py-2 text-center">
                  <span className="block text-[10px] font-bold uppercase text-[var(--color-ink-faint)]">Anomalous Spike</span>
                  <span className="text-base font-extrabold text-[var(--color-danger)]">+{Math.round(a.z_score * 65)}%</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
