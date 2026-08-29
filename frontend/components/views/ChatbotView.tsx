"use client";

import React, { useState, useEffect, useRef } from "react";
import { Send, Mic, Paperclip, Bot, User as UserIcon, Sparkles, Zap } from "lucide-react";
// authFetch, not publicFetch: every endpoint this view calls now requires a
// bearer token. The whole app was written against publicFetch because
// get_current_user fabricated an identity for unauthenticated requests, so
// omitting the header still returned data. It no longer does -- these calls
// would 401 and the view would silently render its mock/empty state.
import { authFetch } from "@/lib/api";
import { PanelLabel } from "@/components/ui/primitives";

type Message = { sender: "user" | "bot"; text: string };
type HistoryItem = { role: "user" | "assistant"; content: string };

const RECENT_INVESTIGATIONS = [
  "Homicide Case #123", "Cyber Fraud Ring", "Gang Activity Bengaluru",
  "Missing Persons — Oct", "Financial Scam Report", "Data Breach Inquiry",
];

const SUGGESTED = [
  "What are the top crime districts in Karnataka?",
  "How many FIRs are in the database?",
  "Which district has the highest risk score?",
  "Identify patterns in theft cases",
  "Analyse Bengaluru Urban crime trends",
  "What are the most common crime categories?",
];

function renderBold(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**")
      ? <strong key={i} className="text-[var(--color-ink)]">{part.slice(2, -2)}</strong>
      : <React.Fragment key={i}>{part}</React.Fragment>
  );
}

const GREETING: Message = {
  sender: "bot",
  text: "Greetings Officer. I am the **KSP Sentinel AI Copilot** powered by Grok, with live access to the real Karnataka crime database from Zoho Catalyst. Ask me about crime trends, district risk scores, FIR statistics, or case patterns.",
};

export default function ChatbotView() {
  const [messages, setMessages]     = useState<Message[]>([GREETING]);
  const [history, setHistory]       = useState<HistoryItem[]>([]);
  const [input, setInput]           = useState("");
  const [loading, setLoading]       = useState(false);
  const [activeCase, setActiveCase] = useState(RECENT_INVESTIGATIONS[0]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async (text: string) => {
    if (!text.trim()) return;
    setInput("");

    const userMsg: Message = { sender: "user", text };
    setMessages((m) => [...m, userMsg]);
    setLoading(true);

    // Build history for multi-turn context (limit to last 10 exchanges)
    const newHistory: HistoryItem[] = [
      ...history,
      { role: "user" as const, content: text },
    ].slice(-20);

    try {
      const res = await authFetch("/api/grok/chatbot-query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history: newHistory.slice(0, -1) }),
      });

      if (res.ok) {
        const data = await res.json();
        const replyText = data.reply ?? "I encountered an issue. Please try again.";
        setMessages((m) => [...m, { sender: "bot", text: replyText }]);
        setHistory([...newHistory, { role: "assistant", content: replyText }]);
      } else {
        const errData = await res.json().catch(() => null);
        const errMsg  = errData?.detail || "Grok API is temporarily unavailable.";
        setMessages((m) => [...m, { sender: "bot", text: errMsg }]);
      }
    } catch {
      setMessages((m) => [...m, { sender: "bot", text: "Network error — please check your connection." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid h-full grid-cols-1 gap-[18px] fade-up lg:grid-cols-[240px_1fr]">
      {/* Sidebar */}
      <div className="glass hidden flex-col p-4 lg:flex">
        <PanelLabel className="mb-4">Recent Investigations</PanelLabel>
        <div className="space-y-1.5">
          {RECENT_INVESTIGATIONS.map((c) => (
            <button
              key={c}
              onClick={() => setActiveCase(c)}
              className={`w-full rounded-[var(--radius-well)] px-3 py-2.5 text-left text-xs font-medium transition-all ${
                activeCase === c
                  ? "border border-[var(--color-accent-cyan)]/30 bg-[var(--color-accent-cyan)]/10 text-[var(--color-ink)]"
                  : "border border-transparent text-[var(--color-ink-muted)] hover:bg-white/[0.03]"
              }`}
            >
              {c}
            </button>
          ))}
        </div>

        {/* Grok badge */}
        <div className="mt-auto pt-4 border-t border-[var(--color-hairline)]">
          <div className="flex items-center gap-2 rounded-[var(--radius-well)] border border-[var(--color-accent-cyan)]/20 bg-[var(--color-accent-cyan)]/[0.05] px-3 py-2">
            <Zap className="h-3.5 w-3.5 text-[var(--color-accent-cyan)]" />
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-accent-cyan)]">Grok-3-mini</p>
              <p className="text-[9px] text-[var(--color-ink-faint)]">Live Karnataka dataset</p>
            </div>
          </div>
        </div>
      </div>

      {/* Chat pane */}
      <div className="glass flex min-h-0 flex-col p-0">
        <div className="flex items-center justify-between border-b border-[var(--color-hairline)] px-6 py-4">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-[var(--color-accent-cyan)]" />
            <h2 className="text-lg font-bold uppercase tracking-wider text-[var(--color-ink)]">Investigation AI Copilot</h2>
            <span className="rounded-full border border-[var(--color-accent-cyan)]/20 bg-[var(--color-accent-cyan)]/10 px-2 py-0.5 text-[9px] font-bold uppercase text-[var(--color-accent-cyan)]">
              Grok + Real Data
            </span>
          </div>
          <span className="flex items-center gap-1.5 text-[10px] font-bold uppercase text-[var(--color-ok)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-ok)] pulse-dot" /> Online
          </span>
        </div>

        {/* Thread */}
        <div className="flex-1 space-y-5 overflow-y-auto p-6">
          {messages.map((m, i) => (
            <div key={i} className={`flex gap-3 ${m.sender === "user" ? "flex-row-reverse" : ""}`}>
              <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border ${
                m.sender === "user"
                  ? "border-[var(--color-accent-blue)]/30 bg-[var(--color-accent-blue)]/10 text-[var(--color-accent-blue)]"
                  : "border-[var(--color-accent-cyan)]/30 bg-[var(--color-accent-cyan)]/10 text-[var(--color-accent-cyan)]"
              }`}>
                {m.sender === "user" ? <UserIcon className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
              </div>
              <div className={`max-w-[75%] rounded-2xl border px-4 py-3 text-xs leading-relaxed ${
                m.sender === "user"
                  ? "border-[var(--color-accent-blue)]/20 bg-[var(--color-accent-blue)]/10 text-[var(--color-ink)]"
                  : "border-[var(--color-hairline)] bg-white/[0.02] text-[var(--color-ink-muted)]"
              }`}>
                {renderBold(m.text)}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full border border-[var(--color-accent-cyan)]/30 bg-[var(--color-accent-cyan)]/10 text-[var(--color-accent-cyan)]">
                <Bot className="h-4 w-4" />
              </div>
              <div className="flex gap-1 rounded-2xl border border-[var(--color-hairline)] bg-white/[0.02] px-4 py-3">
                {[0, 1, 2].map((d) => (
                  <span key={d} className="h-1.5 w-1.5 rounded-full bg-[var(--color-ink-faint)] pulse-dot" style={{ animationDelay: `${d * 0.2}s` }} />
                ))}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Suggested chips */}
        <div className="flex flex-wrap gap-2 border-t border-[var(--color-hairline)] px-6 py-3">
          <span className="flex items-center gap-1 text-[10px] font-bold uppercase text-[var(--color-ink-faint)]">
            <Sparkles className="h-3 w-3 text-[var(--color-accent-cyan)]" /> Try:
          </span>
          {SUGGESTED.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="rounded-full border border-[var(--color-hairline)] bg-white/[0.02] px-3 py-1.5 text-[11px] text-[var(--color-ink-muted)] transition-all hover:border-[var(--color-accent-cyan)]/30 hover:text-[var(--color-ink)]"
            >
              {s}
            </button>
          ))}
        </div>

        {/* Input */}
        <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex items-center gap-2 border-t border-[var(--color-hairline)] p-4">
          <button type="button" className="rounded-full p-2 text-[var(--color-ink-faint)] hover:text-[var(--color-ink)]"><Mic className="h-4.5 w-4.5" /></button>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about crime stats, districts, or investigation patterns…"
            className="flex-1 rounded-full border border-[var(--color-hairline)] bg-[var(--color-surface-2)] px-4 py-2.5 text-sm text-[var(--color-ink)] placeholder-[var(--color-ink-faint)] focus:border-[var(--color-accent-cyan)]/60 focus:outline-none"
          />
          <button type="button" className="rounded-full p-2 text-[var(--color-ink-faint)] hover:text-[var(--color-ink)]"><Paperclip className="h-4.5 w-4.5" /></button>
          <button type="submit" disabled={loading} className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-r from-[var(--color-accent-blue)] to-[var(--color-accent-cyan)] text-white transition-all hover:brightness-110 disabled:opacity-50">
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
