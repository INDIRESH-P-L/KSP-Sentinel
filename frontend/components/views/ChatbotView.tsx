"use client";

import React, { useState, useEffect, useRef } from "react";
import { MessageSquare, Send, ShieldAlert, Cpu } from "lucide-react";

interface ChatMessage {
  sender: "user" | "bot";
  text: string;
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = input;
    setInput("");
    setMessages(prev => [...prev, { sender: "user", text: userMessage }]);
    setLoading(true);

    try {
      const token = localStorage.getItem("ksp_token");
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch("http://localhost:8000/api/chatbot/query", {
        method: "POST",
        headers,
        body: JSON.stringify({ message: userMessage })
      });

      if (res.ok) {
        const data = await res.json();
        setMessages(prev => [...prev, { sender: "bot", text: data.reply }]);
      } else {
        setMessages(prev => [...prev, { sender: "bot", text: "Error compiling request. Please verify the backend services are operational." }]);
      }
    } catch (e) {
      setMessages(prev => [...prev, { sender: "bot", text: "Failed to connect to the backend agent server. Verify host settings." }]);
    } finally {
      setLoading(false);
    }
  };

  // Convert basic markdown to HTML for beautiful display (specifically list items and bold tags)
  const renderMessageText = (text: string) => {
    const lines = text.split("\n");
    let inTable = false;
    let tableHeaders: string[] = [];
    let tableRows: string[][] = [];

    const formattedLines = lines.map((line, idx) => {
      // Bold syntax
      let cleanLine = line.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
      cleanLine = cleanLine.replace(/\*(.*?)\*/g, "<em>$1</em>");
      cleanLine = cleanLine.replace(/`(.*?)`/g, "<code class='bg-slate-950 px-1 py-0.5 rounded text-cyan-400 font-mono text-[10px]'>$1</code>");

      // Check Table
      if (cleanLine.startsWith("|")) {
        const cells = cleanLine.split("|").map(c => c.trim()).filter(c => c !== "");
        if (cleanLine.includes("---")) {
          // separator, skip
          return null;
        }
        if (!inTable) {
          inTable = true;
          tableHeaders = cells;
          return null;
        } else {
          tableRows.push(cells);
          return null;
        }
      } else if (inTable) {
        inTable = false;
        // Render completed table
        const tableHtml = (
          <div key={`table-${idx}`} className="overflow-x-auto my-3 border border-slate-800 rounded-lg">
            <table className="w-full text-[11px] text-left border-collapse">
              <thead>
                <tr className="bg-slate-900 border-b border-slate-800">
                  {tableHeaders.map((th, index) => (
                    <th key={index} className="px-3 py-2 text-slate-300 font-semibold uppercase">{th}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 bg-slate-950/40">
                {tableRows.map((row, rIdx) => (
                  <tr key={rIdx}>
                    {row.map((cell, cIdx) => (
                      <td key={cIdx} className="px-3 py-2 text-slate-200" dangerouslySetInnerHTML={{ __html: cell }} />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        // Reset buffers
        tableHeaders = [];
        tableRows = [];
        return tableHtml;
      }

      // Check bullet items
      if (cleanLine.startsWith("* ") || cleanLine.startsWith("- ")) {
        return (
          <li key={idx} className="list-disc ml-5 text-slate-300 py-0.5" dangerouslySetInnerHTML={{ __html: cleanLine.substring(2) }} />
        );
      }

      if (cleanLine.startsWith("### ")) {
        return (
          <h4 key={idx} className="text-sm font-bold text-cyan-400 mt-4 mb-2 uppercase tracking-wide" dangerouslySetInnerHTML={{ __html: cleanLine.substring(4) }} />
        );
      }

      if (cleanLine.trim() === "") {
        return <div key={idx} className="h-2"></div>;
      }

      return (
        <p key={idx} className="text-slate-300 leading-relaxed py-0.5" dangerouslySetInnerHTML={{ __html: cleanLine }} />
      );
    }).filter(x => x !== null);

    return <div className="space-y-1">{formattedLines}</div>;
  };

  return (
    <div className="glass-panel border border-slate-800 rounded-xl flex flex-col h-[650px] overflow-hidden max-w-4xl mx-auto shadow-2xl">
      {/* Header bar */}
      <div className="h-14 bg-slate-900/80 border-b border-slate-800 px-6 flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-cyan-600/10 border border-cyan-400/30 flex items-center justify-center text-cyan-400 alarm-pulse">
          <MessageSquare className="w-4 h-4" />
        </div>
        <div>
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">Investigation Copilot</h3>
          <p className="text-[10px] text-slate-500">Autonomous crime analytics helper</p>
        </div>
      </div>

      {/* Message Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-slate-950/20">
        {messages.map((m, idx) => (
          <div key={idx} className={`flex ${m.sender === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-xl rounded-xl p-4 text-xs shadow-md ${
              m.sender === "user" 
                ? "bg-blue-600/25 border border-blue-500/20 text-slate-100 rounded-tr-none" 
                : "bg-slate-900/60 border border-slate-800/80 rounded-tl-none"
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
            <div className="bg-slate-900/60 border border-slate-800/80 rounded-xl rounded-tl-none p-4 flex items-center gap-2.5">
              <Cpu className="w-4 h-4 text-cyan-400 animate-spin" />
              <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">QUERYING COMMAND RECORDSETS...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <form onSubmit={handleSubmit} className="h-16 bg-slate-900/40 border-t border-slate-800 flex items-center px-4 gap-4">
        <input 
          type="text" 
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder="Ask about murder cases, crime rates, or high volume stations..." 
          className="flex-1 bg-slate-950 border border-slate-800 rounded-lg py-2.5 px-4 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-all"
        />
        <button 
          type="submit"
          className="bg-cyan-600 hover:bg-cyan-500 text-white font-bold p-2.5 rounded-lg transition-all shadow-md shadow-cyan-500/20 cursor-pointer"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}
