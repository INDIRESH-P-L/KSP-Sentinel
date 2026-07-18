"use client";

import React, { useState, useEffect, useRef } from "react";
import { Send, Mic, Paperclip, Bot, User as UserIcon, Sparkles } from "lucide-react";
import { authFetch } from "@/lib/api";
import { PanelLabel } from "@/components/ui/primitives";
import { mockChatReply } from "@/lib/mock";

type Message = { sender: "user" | "bot"; text: string };

const RECENT_INVESTIGATIONS = [
  "Homicide Case #123", "Cyber Fraud Ring", "Gang Activity Bengaluru",
  "Missing Persons — Oct", "Financial Scam Report", "Data Breach Inquiry",
];

const SUGGESTED = [
  "Identify repeat offenders",
  "Why is Kalaburagi high risk?",
  "Cases closed in the last 30 days",
  "Map crime hotspots for theft",
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
  text: "Greetings Officer. I am the **KSP Sentinel AI Copilot**. Ask me to search cases, query crime rates, explain risk scores, or identify repeat offenders.",
};

export default function ChatbotView() {
  const [messages, setMessages] = useState<Message[]>([GREETING]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeCase, setActiveCase] = useState(RECENT_INVESTIGATIONS[0]);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async (text: string) => {
    if (!text.trim()) return;
    setInput("");
    setMessages((m) => [...m, { sender: "user", text }]);
    setLoading(true);
    try {
      const res = await authFetch("/api/chatbot/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text }), // spec §7.7
      });
      if (res.ok) {
        const data = await res.json();
        setMessages((m) => [...m, { sender: "bot", text: data.reply ?? mockChatReply }]);
      } else {
        setMessages((m) => [...m, { sender: "bot", text: mockChatReply }]);
      }
    } catch {
      setMessages((m) => [...m, { sender: "bot", text: mockChatReply }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid h-full grid-cols-1 gap-5 fade-up lg:grid-cols-[240px_1fr]">
      {/* Recent investigations */}
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
      </div>

      {/* Chat pane */}
      <div className="glass flex min-h-0 flex-col p-0">
        <div className="flex items-center justify-between border-b border-[var(--color-hairline)] px-6 py-4">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-[var(--color-accent-cyan)]" />
            <h2 className="text-lg font-bold uppercase tracking-wider text-[var(--color-ink)]">Investigation AI Copilot</h2>
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
            placeholder="Type a message…"
            className="flex-1 rounded-full border border-[var(--color-hairline)] bg-[var(--color-surface-2)] px-4 py-2.5 text-sm text-[var(--color-ink)] placeholder-[var(--color-ink-faint)] focus:border-[var(--color-accent-cyan)]/60 focus:outline-none"
          />
          <button type="button" className="rounded-full p-2 text-[var(--color-ink-faint)] hover:text-[var(--color-ink)]"><Paperclip className="h-4.5 w-4.5" /></button>
          <button type="submit" className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-r from-[var(--color-accent-blue)] to-[var(--color-accent-cyan)] text-white transition-all hover:brightness-110">
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
