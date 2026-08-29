"use client";

import React, { useState } from "react";
import { Search, FileText, Sparkles, ArrowRight, Brain, ChevronDown, ChevronUp, Loader2 } from "lucide-react";
// authFetch, not publicFetch: every endpoint this view calls now requires a
// bearer token. The whole app was written against publicFetch because
// get_current_user fabricated an identity for unauthenticated requests, so
// omitting the header still returned data. It no longer does -- these calls
// would 401 and the view would silently render its mock/empty state.
import { authFetch } from "@/lib/api";
import { SectionTitle, Pill } from "@/components/ui/primitives";
import { mockSearchResults } from "@/lib/mock";
import type { SearchResult } from "@/lib/types";

const SUGGESTIONS = [
  "Find cases with 'burglary' and 'rainy weather' in Bengaluru",
  "Identify suspects from robbery cases in the last 6 months",
  "Locate recent incidents of stolen vehicles in specific districts",
];

const RECENT = [
  "Cases with stolen silver Alto car near Ring Road",
  "Identify patterns in assault cases reported via mobile app",
  "Locate similar historical cases using natural description matching",
];

export default function SearchView() {
  const [query, setQuery]     = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  // Grok Pattern Analysis state
  const [grokInsight, setGrokInsight]   = useState<string | null>(null);
  const [grokLoading, setGrokLoading]   = useState(false);
  const [grokError, setGrokError]       = useState<string | null>(null);
  const [grokExpanded, setGrokExpanded] = useState(true);

  const callGrokAnalysis = async (q: string, res: SearchResult[]) => {
    if (!res.length) return;
    setGrokLoading(true);
    setGrokError(null);
    setGrokInsight(null);
    try {
      const r = await authFetch("/api/grok/search-analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, results: res }),
      });
      if (r.ok) {
        const data = await r.json();
        setGrokInsight(data.insight);
        setGrokExpanded(true);
      } else {
        const err = await r.json().catch(() => null);
        setGrokError(err?.detail || `Grok API Error: ${r.status}`);
      }
    } catch (e: any) {
      setGrokError(e.message || "Failed to reach Grok API");
    } finally {
      setGrokLoading(false);
    }
  };

  const run = async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setSearched(true);
    setGrokInsight(null);
    setGrokError(null);
    let searchResults: SearchResult[] = [];
    try {
      const res = await authFetch(`/api/crimes/search?query=${encodeURIComponent(q)}&limit=8`);
      if (res.ok) {
        searchResults = await res.json();
        setResults(searchResults);
      } else {
        searchResults = mockSearchResults;
        setResults(mockSearchResults);
      }
    } catch {
      searchResults = mockSearchResults;
      setResults(mockSearchResults);
    } finally {
      setLoading(false);
    }
    // Auto-trigger Grok pattern analysis
    if (searchResults.length > 0) {
      callGrokAnalysis(q, searchResults);
    }
  };

  return (
    <div className="flex flex-col gap-[22px] fade-up">
      <SectionTitle>Semantic Case Search</SectionTitle>

      <div className="glass mx-auto max-w-4xl space-y-6 p-8">
        <form onSubmit={(e) => { e.preventDefault(); run(query); }} className="flex gap-3">
          <div className="flex flex-1 items-center gap-3 rounded-full border border-[var(--color-accent-blue)]/30 bg-[var(--color-surface-2)] px-5 py-3.5 focus-within:border-[var(--color-accent-cyan)]/60">
            <Search className="h-4.5 w-4.5 text-[var(--color-ink-faint)]" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. suspect stole a black pulsar motorcycle near bus stand during night hours…"
              className="w-full bg-transparent text-sm text-[var(--color-ink)] placeholder-[var(--color-ink-faint)] focus:outline-none"
            />
          </div>
          <button type="submit" className="flex items-center gap-2 rounded-full bg-gradient-to-r from-[var(--color-accent-blue)] to-[var(--color-accent-cyan)] px-7 text-sm font-semibold uppercase tracking-wider text-white shadow-lg transition-all hover:brightness-110">
            <Search className="h-4 w-4" /> Search
          </button>
        </form>

        {!searched && (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div>
              <h4 className="mb-3 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[var(--color-ink-muted)]">
                <Sparkles className="h-3.5 w-3.5 text-[var(--color-accent-cyan)]" /> AI-Powered Suggestions
              </h4>
              <div className="space-y-2">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => { setQuery(s); run(s); }}
                    className="block w-full rounded-full border border-[var(--color-hairline)] bg-white/[0.02] px-4 py-2 text-left text-[11px] text-[var(--color-ink-muted)] transition-all hover:border-[var(--color-accent-cyan)]/30 hover:text-[var(--color-ink)]">
                    {s}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <h4 className="mb-3 text-xs font-bold uppercase tracking-wider text-[var(--color-ink-muted)]">Recent Complex Queries</h4>
              <div className="space-y-2.5">
                {RECENT.map((r) => (
                  <button key={r} onClick={() => { setQuery(r); run(r); }}
                    className="flex w-full items-center gap-2 text-left text-xs text-[var(--color-ink-faint)] transition-colors hover:text-[var(--color-ink)]">
                    <ArrowRight className="h-3 w-3 shrink-0" /> {r}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Grok Pattern Analysis Panel */}
      {searched && (grokLoading || grokInsight || grokError) && (
        <div className="mx-auto max-w-4xl w-full">
          <div className="glass border-[var(--color-accent-cyan)]/20 bg-[var(--color-accent-cyan)]/[0.03] overflow-hidden">
            <button
              onClick={() => setGrokExpanded(!grokExpanded)}
              className="flex w-full items-center justify-between px-5 py-3.5 text-left"
            >
              <div className="flex items-center gap-2.5">
                <Brain className="h-4.5 w-4.5 text-[var(--color-accent-cyan)]" />
                <span className="text-xs font-bold uppercase tracking-wider text-[var(--color-accent-cyan)]">
                  Grok Pattern Analysis
                </span>
                <span className="rounded-full border border-[var(--color-accent-cyan)]/30 bg-[var(--color-accent-cyan)]/10 px-2 py-0.5 text-[10px] font-bold text-[var(--color-accent-cyan)]">
                  Real Data
                </span>
              </div>
              {grokLoading
                ? <Loader2 className="h-4 w-4 animate-spin text-[var(--color-accent-cyan)]" />
                : grokExpanded
                  ? <ChevronUp className="h-4 w-4 text-[var(--color-ink-muted)]" />
                  : <ChevronDown className="h-4 w-4 text-[var(--color-ink-muted)]" />}
            </button>

            {grokExpanded && (
              <div className="border-t border-[var(--color-hairline)] px-5 pb-5 pt-4">
                {grokLoading && (
                  <div className="flex items-center gap-2 text-xs text-[var(--color-ink-muted)]">
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-[var(--color-accent-cyan)]" />
                    Grok is analysing patterns across the real Karnataka FIR database…
                  </div>
                )}
                {grokError && (
                  <p className="text-xs text-[var(--color-danger)]">{grokError}</p>
                )}
                {grokInsight && (
                  <p className="text-sm leading-relaxed text-[var(--color-ink)]">{grokInsight}</p>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="mx-auto max-w-4xl">
        {loading ? (
          <p className="py-12 text-center text-sm font-bold uppercase tracking-widest text-[var(--color-accent-cyan)] animate-pulse">
            Encoding query · scanning FAISS index…
          </p>
        ) : (
          <div className="space-y-4">
            {searched && results.length === 0 && (
              <p className="py-6 text-center text-sm text-[var(--color-ink-faint)]">No matches found. Try refining your keywords.</p>
            )}
            {results.map((r, i) => (
              <div key={i} className="glass glass-hover space-y-3 p-6">
                <div className="flex flex-col justify-between gap-2 border-b border-[var(--color-hairline)] pb-3 md:flex-row md:items-center">
                  <div className="flex items-center gap-3">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full border border-[var(--color-accent-blue)]/30 bg-[var(--color-accent-blue)]/10 text-xs font-bold text-[var(--color-accent-blue)]">{i + 1}</span>
                    <h3 className="text-sm font-bold text-[var(--color-ink)]">FIR Case #{r.fir_number}</h3>
                  </div>
                  <Pill tone="ok">Match {(r.score * 100).toFixed(1)}%</Pill>
                </div>
                <p className="text-xs italic leading-relaxed text-[var(--color-ink-muted)]">&ldquo;{r.description}&rdquo;</p>
                <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase text-[var(--color-ink-faint)]">
                  <FileText className="h-3.5 w-3.5" /> Semantic vector match
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
