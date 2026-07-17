"use client";

import React, { useState } from "react";
import { Search, FileText, Calendar, ShieldAlert, Sparkles } from "lucide-react";
import { authFetch } from "@/lib/api";

const SUGGESTED_QUERIES = [
  "suspect stole a black pulsar motorcycle near bus stand during night hours",
  "chain snatching involving two riders on a two-wheeler",
  "house break-in with forced entry while family was away",
  "online fraud through fake investment app",
];

export default function SearchView() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const runSearch = async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setHasSearched(true);
    try {
      const res = await authFetch(`/api/crimes/search?query=${encodeURIComponent(q)}&top_k=5`);
      if (res.ok) {
        const data = await res.json();
        setResults(data);
      }
    } catch (e) {
      console.error("Error running semantic search:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    runSearch(query);
  };

  const handleSuggestionClick = (q: string) => {
    setQuery(q);
    runSearch(q);
  };

  return (
    <div className="space-y-6">
      {/* Search Input Card */}
      <div className="glass-panel p-8 rounded-2xl border border-slate-800 space-y-5 max-w-4xl mx-auto">
        <div className="text-center max-w-xl mx-auto space-y-2">
          <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wider">Semantic Case Matching Portal</h2>
          <p className="text-xs text-slate-400">Search similar historical cases using natural description matching</p>
        </div>

        <form onSubmit={handleSearch} className="flex gap-4">
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="e.g. suspect stole a black pulsar motorcycle near bus stand during night hours..."
            className="flex-1 bg-slate-900/60 border border-slate-700/50 rounded-xl py-3 px-5 text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-all text-sm"
          />
          <button
            type="submit"
            className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-semibold px-8 py-3 rounded-xl transition-all shadow-lg shadow-blue-500/20 text-sm uppercase tracking-wider flex items-center gap-2 cursor-pointer"
          >
            <Search className="w-4 h-4" />
            Query
          </button>
        </form>

        {/* Example query chips -- click to populate & run immediately */}
        <div className="flex flex-wrap items-center gap-2 justify-center pt-1">
          <span className="flex items-center gap-1 text-[10px] font-bold text-slate-500 uppercase tracking-wider mr-1">
            <Sparkles className="w-3 h-3 text-cyan-400" />
            Try:
          </span>
          {SUGGESTED_QUERIES.map((q, idx) => (
            <button
              key={idx}
              onClick={() => handleSuggestionClick(q)}
              className="text-[11px] text-slate-300 bg-slate-900/60 hover:bg-slate-800 border border-slate-800 hover:border-cyan-500/30 rounded-full px-3 py-1.5 transition-all cursor-pointer"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Results List */}
      <div className="max-w-4xl mx-auto">
        {loading ? (
          <div className="py-12 text-center">
            <span className="text-cyan-400 font-bold text-sm animate-pulse tracking-widest uppercase">ENCODING QUERY AND SCANNING FAISS INDEX SECTORS...</span>
          </div>
        ) : (
          <div className="space-y-5">
            {hasSearched && results.length === 0 && (
              <p className="text-slate-500 text-center py-6 text-sm">No matches found. Try refining search keywords.</p>
            )}

            {results.map((r, idx) => (
              <div key={idx} className="glass-panel p-6 rounded-2xl border border-slate-800 space-y-4 glass-panel-hover">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                  <div className="flex items-center gap-3">
                    <span className="w-6 h-6 bg-blue-600/10 border border-blue-400/30 text-blue-400 text-xs font-bold rounded-full flex items-center justify-center">
                      {idx + 1}
                    </span>
                    <h3 className="text-sm font-bold text-slate-200">FIR Case Record #{r.fir_number}</h3>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-bold px-2.5 py-1 rounded-full">
                      Match Confidence: {(r.score * 100).toFixed(1)}%
                    </span>
                    <span className="bg-slate-900 border border-slate-800 text-slate-400 text-[10px] font-semibold px-2.5 py-1 rounded-full uppercase">
                      {r.status}
                    </span>
                  </div>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed italic">
                  &ldquo;{r.description}&rdquo;
                </p>

                <div className="flex flex-wrap items-center gap-6 text-[10px] text-slate-500">
                  <span className="flex items-center gap-1.5 uppercase font-medium">
                    <FileText className="w-3.5 h-3.5" />
                    {r.subcategory}
                  </span>
                  <span className="flex items-center gap-1.5 uppercase font-medium">
                    <ShieldAlert className="w-3.5 h-3.5" />
                    {r.station}
                  </span>
                  <span className="flex items-center gap-1.5 uppercase font-medium">
                    <Calendar className="w-3.5 h-3.5" />
                    Reported: {new Date(r.date_reported).toLocaleDateString()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
