"use client";

import React, { useState } from "react";
import { Search, FileText, Sparkles, ArrowRight } from "lucide-react";
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
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const run = async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setSearched(true);
    try {
      const res = await authFetch(`/api/crimes/search?query=${encodeURIComponent(q)}&limit=5`);
      if (res.ok) setResults(await res.json());
      else setResults(mockSearchResults);
    } catch {
      setResults(mockSearchResults);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 fade-up">
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
                  <button
                    key={s}
                    onClick={() => { setQuery(s); run(s); }}
                    className="block w-full rounded-full border border-[var(--color-hairline)] bg-white/[0.02] px-4 py-2 text-left text-[11px] text-[var(--color-ink-muted)] transition-all hover:border-[var(--color-accent-cyan)]/30 hover:text-[var(--color-ink)]"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <h4 className="mb-3 text-xs font-bold uppercase tracking-wider text-[var(--color-ink-muted)]">Recent Complex Queries</h4>
              <div className="space-y-2.5">
                {RECENT.map((r) => (
                  <button
                    key={r}
                    onClick={() => { setQuery(r); run(r); }}
                    className="flex w-full items-center gap-2 text-left text-xs text-[var(--color-ink-faint)] transition-colors hover:text-[var(--color-ink)]"
                  >
                    <ArrowRight className="h-3 w-3 shrink-0" /> {r}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

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
