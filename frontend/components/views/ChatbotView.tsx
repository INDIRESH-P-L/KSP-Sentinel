"use client";

import React, { useState, useEffect, useRef } from "react";
import { MessageSquare, Send, Cpu, Sparkles } from "lucide-react";
import { authFetch } from "@/lib/api";

interface ChatMessage {
  sender: "user" | "bot";
  text: string;
}

const SUGGESTED_PROMPTS = [
  "Show repeat offenders",
  "Why is Kalaburagi high risk?",
  "Which police station has the highest crime?",
  "Cases closed in the last 30 days",
];

// Safe inline markdown (bold/italic/code) -- returns React nodes, never raw HTML.
// The previous version built an HTML string via regex and rendered it with
// dangerouslySetInnerHTML on live AI-generated text; that's a real XSS vector even
// with the server-side prompt-injection guardrails (backend/app/core/guardrails.py)
// as a first line of defense, not the only one.
function renderInline(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g);
  return parts.filter(p => p !== "").map((part, idx) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={idx} className="text-slate-100">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={idx} className="bg-slate-950 px-1 py-0.5 rounded text-cyan-400 font-mono text-[10px]">{part.slice(1, -1)}</code>;
    }
    if (part.startsWith("*") && part.endsWith("*")) {
      return <em key={idx}>{part.slice(1, -1)}</em>;
    }
    return <React.Fragment key={idx}>{part}</React.Fragment>;
  });
}

// Minimal markdown-lite renderer: bold/italic/code inline, "* "/"- " bullets,
// "### " headers, and "| a | b |" tables. Every text node goes through renderInline
// above rather than dangerouslySetInnerHTML.
function renderMessageText(text: string) {
  const lines = text.split("\n");
  let inTable = false;
  let tableHeaders: string[] = [];
  let tableRows: string[][] = [];

  const formattedLines = lines.map((line, idx) => {
    if (line.startsWith("|")) {
      const cells = line.split("|").map(c => c.trim()).filter(c => c !== "");
      if (line.includes("---")) return null;
      if (!inTable) {
        inTable = true;
        tableHeaders = cells;
        return null;
      }
      tableRows.push(cells);
      return null;
    }

    if (inTable) {
      inTable = false;
      const table = (
        <div key={`table-${idx}`} className="overflow-x-auto my-3 border border-slate-800 rounded-xl">
          <table className="w-full text-[11px] text-left border-collapse">
            <thead>
              <tr className="bg-slate-900 border-b border-slate-800">
                {tableHeaders.map((th, i) => (
                  <th key={i} className="px-3 py-2 text-slate-300 font-semibold uppercase">{renderInline(th)}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 bg-slate-950/40">
              {tableRows.map((row, rIdx) => (
                <tr key={rIdx}>
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="px-3 py-2 text-slate-200">{renderInline(cell)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      tableHeaders = [];
      tableRows = [];
      return table;
    }

    if (line.startsWith("* ") || line.startsWith("- ")) {
      return <li key={idx} className="list-disc ml-5 text-slate-300 py-0.5">{renderInline(line.slice(2))}</li>;
    }

    if (line.startsWith("### ")) {
      return <h4 key={idx} className="text-sm font-bold text-cyan-400 mt-4 mb-2 uppercase tracking-wide">{renderInline(line.slice(4))}</h4>;
    }

    if (line.trim() === "") {
      return <div key={idx} className="h-2"></div>;
    }

    return <p key={idx} className="text-slate-300 leading-relaxed py-0.5">{renderInline(line)}</p>;
  }).filter(x => x !== null);

  return <div className="space-y-1">{formattedLines}</div>;
}

export default function ChatbotView() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Add default greeting
    setMessages([
      {
        sender: "bot",
        text: "Greetings Officer! I am **KSP-Sentinel AI Assistant**. You can ask me to search cases, query crime rates, explain risk scores, or identify repeat offenders.\n\nTry asking me:\n* *'Show murder cases in Bengaluru during 2024'*\n* *'Which police station has the highest crime?'*\n* *'Why is Kalaburagi high risk?'*\n* *'Show repeat offenders'*\n* *'Cases closed in the last 30 days'*"
      }
    ]);
  }, []);

  useEffect(() => {
    // Auto scroll to bottom
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const sendMessage = async (userMessage: string) => {
    if (!userMessage.trim()) return;
    setInput("");
    setMessages(prev => [...prev, { sender: "user", text: userMessage }]);
    setLoading(true);

    try {
      const res = await authFetch("/api/chatbot/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage })
      });

      if (res.ok) {
        const data = await res.json();
        if (data.error) {
          setMessages(prev => [...prev, { sender: "bot", text: data.error }]);
        } else {
          setMessages(prev => [...prev, { sender: "bot", text: data.reply }]);
        }
      } else {
        setMessages(prev => [...prev, { sender: "bot", text: "Error compiling request. Please verify the backend services are operational." }]);
      }
    } catch (e) {
      setMessages(prev => [...prev, { sender: "bot", text: "Failed to connect to the backend agent server. Verify host settings." }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendMessage(input);
  };

  return (
    <div className="glass-panel border border-slate-800 rounded-2xl flex flex-col h-[650px] overflow-hidden max-w-4xl mx-auto shadow-2xl">
      {/* Header bar */}
      <div className="h-14 bg-slate-900/80 border-b border-slate-800 px-6 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-cyan-600/10 border border-cyan-400/30 flex items-center justify-center text-cyan-400 alarm-pulse">
            <MessageSquare className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">Investigation Copilot</h3>
            <p className="text-[10px] text-slate-500">Autonomous crime analytics helper</p>
          </div>
        </div>
        <span className="flex items-center gap-1.5 bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 text-[9px] font-bold px-2.5 py-1 rounded-full uppercase">
          <Sparkles className="w-3 h-3" />
          AI Online
        </span>
      </div>

      {/* Message Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-slate-950/20">
        {messages.map((m, idx) => (
          <div key={idx} className={`flex ${m.sender === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-xl rounded-2xl p-4 text-xs shadow-md ${
              m.sender === "user"
                ? "bg-blue-600/25 border border-blue-500/20 text-slate-100 rounded-tr-md"
                : "bg-slate-900/60 border border-slate-800/80 rounded-tl-md"
            }`}>
              {m.sender === "bot" ? (
                renderMessageText(m.text)
              ) : (
                <p className="text-slate-200 font-semibold">{m.text}</p>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl rounded-tl-md p-4 flex items-center gap-2.5">
              <Cpu className="w-4 h-4 text-cyan-400 animate-spin" />
              <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">QUERYING COMMAND RECORDSETS...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggested prompts */}
      {messages.length <= 1 && (
        <div className="px-6 pb-3 flex flex-wrap gap-2 shrink-0">
          {SUGGESTED_PROMPTS.map((p, idx) => (
            <button
              key={idx}
              onClick={() => sendMessage(p)}
              className="text-[10px] text-slate-300 bg-slate-900/60 hover:bg-slate-800 border border-slate-800 hover:border-cyan-500/30 rounded-full px-3 py-1.5 transition-all cursor-pointer"
            >
              {p}
            </button>
          ))}
        </div>
      )}

      {/* Input bar */}
      <form onSubmit={handleSubmit} className="h-16 bg-slate-900/40 border-t border-slate-800 flex items-center px-4 gap-4 shrink-0">
        <input
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask about murder cases, crime rates, or high volume stations..."
          className="flex-1 bg-slate-950 border border-slate-800 rounded-xl py-2.5 px-4 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-all"
        />
        <button
          type="submit"
          className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-bold p-2.5 rounded-xl transition-all shadow-md shadow-cyan-500/20 cursor-pointer"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}
