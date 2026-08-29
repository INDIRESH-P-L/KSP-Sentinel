"use client";

import React, { useCallback, useEffect, useState } from "react";
import { ClipboardCheck, ChevronRight, CircleAlert, CircleCheck, CircleMinus } from "lucide-react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
// authFetch, not publicFetch: readiness reads the full case file.
import { authFetch } from "@/lib/api";
import { SectionTitle, PanelLabel, Pill, Loading } from "@/components/ui/primitives";
import { GlassPanel } from "@/components/ui/GlassPanel";
import type { CaseReadiness, ReadinessCheck } from "@/lib/types";

/**
 * Case Readiness — can this case go to court, and if not, what is missing?
 *
 * The queue answers the supervisor's question (which of forty cases is at risk); the
 * detail panel answers the investigating officer's (what do I do about this one). Both
 * lead with the worklist rather than the score, because the number is only useful as a
 * way of ranking; the actions are the part anyone acts on.
 */

const BAND_TONE: Record<string, { tone: "ok" | "warn" | "danger" | "info"; label: string }> = {
  ready:        { tone: "ok",     label: "Ready" },
  nearly_ready: { tone: "info",   label: "Nearly ready" },
  gaps:         { tone: "warn",   label: "Gaps" },
  blocked:      { tone: "danger", label: "Blocked" },
};

const CLOCK_TONE: Record<string, "ok" | "warn" | "danger" | "info"> = {
  filed: "ok", comfortable: "ok", approaching: "warn", critical: "danger", expired: "danger",
};

const STATUS_ICON = {
  pass: CircleCheck,
  warn: CircleMinus,
  fail: CircleAlert,
} as const;

const STATUS_COLOR = {
  pass: "var(--color-ok-text)",
  warn: "var(--color-warn-text)",
  fail: "var(--color-danger-text)",
} as const;

type QueueRow = {
  fir_id: number;
  fir_number: string;
  status: string;
  readiness_score: number;
  band: string;
  days_remaining: number | null;
  statutory_status: string | null;
  blocker_count: number;
  top_action: string | null;
};

function CheckRow({ check }: { check: ReadinessCheck }) {
  const Icon = STATUS_ICON[check.status];
  return (
    <li className="flex items-start gap-3 border-b border-[var(--color-hairline)]/50 py-2.5 last:border-0">
      <Icon className="mt-0.5 h-4 w-4 shrink-0" style={{ color: STATUS_COLOR[check.status] }} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-sm font-medium text-[var(--color-ink)]">{check.label}</span>
          <span className="mono shrink-0 text-[10px] text-[var(--color-ink-faint)]">
            {Math.round(check.weight * 100)}%
          </span>
        </div>
        <p className="mt-0.5 text-xs text-[var(--color-ink-muted)]">{check.detail}</p>
        {check.action && (
          <p className="mt-1 text-xs text-[var(--color-brass)]">→ {check.action}</p>
        )}
      </div>
    </li>
  );
}

export default function ReadinessView() {
  const [queue, setQueue] = useState<QueueRow[]>([]);
  const [detail, setDetail] = useState<CaseReadiness | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const reduced = Boolean(useReducedMotion());

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await authFetch("/api/crimes/readiness/queue?limit=50");
        if (!res.ok) throw new Error(`Readiness queue unavailable (${res.status})`);
        const json = await res.json();
        if (cancelled) return;
        setQueue(json.cases ?? []);
        setSelectedId((prev) => prev ?? json.cases?.[0]?.fir_id ?? null);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not load the queue.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const loadDetail = useCallback(async (firId: number) => {
    setSelectedId(firId);
    setDetail(null);
    try {
      const res = await authFetch(`/api/crimes/${firId}/readiness`);
      if (res.ok) setDetail(await res.json());
    } catch { /* the panel simply stays empty */ }
  }, []);

  useEffect(() => {
    if (selectedId != null) loadDetail(selectedId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  if (loading && !queue.length) return <Loading label="Assessing case files…" />;

  if (error) {
    return (
      <div className="p-6">
        <GlassPanel className="p-6">
          <p className="text-sm text-[var(--color-danger-text)]">{error}</p>
        </GlassPanel>
      </div>
    );
  }

  const atRisk = queue.filter(
    (r) => r.statutory_status === "critical" || r.statutory_status === "expired").length;

  return (
    <div className="flex flex-col gap-5 p-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <SectionTitle>Case Readiness</SectionTitle>
          <p className="mt-1 max-w-2xl text-sm text-[var(--color-ink-muted)]">
            Every open case scored on the documentary preconditions a chargesheet
            requires, ordered by how close it is to its statutory deadline.
          </p>
        </div>
        {atRisk > 0 && (
          <Pill tone="danger">{atRisk} case{atRisk === 1 ? "" : "s"} at or past deadline</Pill>
        )}
      </div>

      {queue.length === 0 ? (
        <GlassPanel className="p-8 text-center">
          <ClipboardCheck className="mx-auto mb-3 h-8 w-8 text-[var(--color-ink-faint)]" />
          <p className="text-sm text-[var(--color-ink-muted)]">No open cases to assess.</p>
        </GlassPanel>
      ) : (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_400px]">
          {/* Queue */}
          <GlassPanel className="p-5">
            <PanelLabel>Open cases · most urgent first</PanelLabel>
            <div className="mt-3 flex flex-col">
              {queue.map((r) => {
                const band = BAND_TONE[r.band] ?? BAND_TONE.gaps;
                const isSel = r.fir_id === selectedId;
                return (
                  <button
                    key={r.fir_id}
                    type="button"
                    onClick={() => setSelectedId(r.fir_id)}
                    aria-pressed={isSel}
                    className={`flex items-center gap-3 rounded-[var(--radius-well)] border-b border-[var(--color-hairline)]/50 px-3 py-3 text-left transition-colors last:border-0 ${
                      isSel ? "bg-[var(--color-elevated)]" : "hover:bg-[var(--color-surface-2)]"
                    }`}
                  >
                    {/* Score as a bar, not just a number: the comparison across rows is
                        the useful reading, and a bar makes it scannable. */}
                    <div className="w-12 shrink-0">
                      <span className="mono text-sm font-semibold tabular-nums text-[var(--color-ink)]">
                        {r.readiness_score}
                      </span>
                      <div className="mt-1 h-1 overflow-hidden rounded-full bg-[var(--color-surface-2)]">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${r.readiness_score}%`,
                            background: r.band === "blocked" ? "var(--color-danger)"
                              : r.band === "gaps" ? "var(--color-warn)"
                              : "var(--color-ok)",
                          }}
                        />
                      </div>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="mono text-xs text-[var(--color-ink)]">{r.fir_number}</span>
                        <Pill tone={band.tone}>{band.label}</Pill>
                        {r.statutory_status && r.statutory_status !== "filed" && (
                          <Pill tone={CLOCK_TONE[r.statutory_status] ?? "info"}>
                            {r.days_remaining != null && r.days_remaining < 0
                              ? `${Math.abs(r.days_remaining)}d overdue`
                              : `${r.days_remaining}d left`}
                          </Pill>
                        )}
                      </div>
                      {r.top_action && (
                        <p className="mt-1 truncate text-xs text-[var(--color-ink-faint)]">
                          {r.top_action}
                        </p>
                      )}
                    </div>
                    <ChevronRight className="h-4 w-4 shrink-0 text-[var(--color-ink-faint)]" />
                  </button>
                );
              })}
            </div>
          </GlassPanel>

          {/* Detail */}
          <div className="flex flex-col gap-4">
            <AnimatePresence mode="wait">
              {detail && (
                <motion.div
                  key={detail.fir_id}
                  initial={reduced ? { opacity: 0 } : { opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.25 }}
                  className="flex flex-col gap-4"
                >
                  <GlassPanel className="p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <PanelLabel>{detail.fir_number}</PanelLabel>
                        <p className="mono mt-1.5 text-3xl font-semibold text-[var(--color-ink)]">
                          {detail.readiness_score}
                          <span className="ml-1 text-base text-[var(--color-ink-faint)]">/100</span>
                        </p>
                      </div>
                      <Pill tone={(BAND_TONE[detail.band] ?? BAND_TONE.gaps).tone}>
                        {(BAND_TONE[detail.band] ?? BAND_TONE.gaps).label}
                      </Pill>
                    </div>
                    <p className="mt-2 text-xs text-[var(--color-ink-muted)]">{detail.band_note}</p>

                    {detail.statutory_clock?.applicable && (
                      <div className="mt-3 border-t border-[var(--color-hairline)] pt-3">
                        <PanelLabel>Statutory clock</PanelLabel>
                        <p className="mt-1 text-sm text-[var(--color-ink)]">
                          {detail.statutory_clock.note ??
                            (detail.statutory_clock.days_remaining != null &&
                             detail.statutory_clock.days_remaining < 0
                              ? `${Math.abs(detail.statutory_clock.days_remaining)} days past the chargesheet deadline.`
                              : `${detail.statutory_clock.days_remaining} days to the chargesheet deadline.`)}
                        </p>
                        {detail.statutory_clock.basis && (
                          <p className="mt-1 text-[11px] text-[var(--color-ink-faint)]">
                            {detail.statutory_clock.basis}
                          </p>
                        )}
                      </div>
                    )}
                  </GlassPanel>

                  {detail.next_actions.length > 0 && (
                    <GlassPanel className="p-5">
                      <PanelLabel>What to do next</PanelLabel>
                      <ol className="mt-2.5 flex flex-col gap-2.5">
                        {detail.next_actions.map((a, i) => (
                          <li key={i} className="flex items-start gap-2.5">
                            <span
                              className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                              style={{
                                background: a.severity === "blocker"
                                  ? "var(--color-danger)" : "var(--color-warn)",
                              }}
                            />
                            <div>
                              <p className="text-sm text-[var(--color-ink)]">{a.action}</p>
                              <p className="mt-0.5 text-xs text-[var(--color-ink-faint)]">{a.detail}</p>
                            </div>
                          </li>
                        ))}
                      </ol>
                    </GlassPanel>
                  )}

                  <GlassPanel className="p-5">
                    <PanelLabel>Preconditions</PanelLabel>
                    <ul className="mt-2 flex flex-col">
                      {detail.checks.map((c) => <CheckRow key={c.key} check={c} />)}
                    </ul>
                  </GlassPanel>

                  <p className="px-1 text-[11px] leading-relaxed text-[var(--color-ink-faint)]">
                    {detail.advisory}
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      )}
    </div>
  );
}
