"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  ShieldAlert, LayoutDashboard, Map, TrendingUp, Brain, Share2,
  Search, MessageSquare, FileSpreadsheet, LogOut, Bell, User,
  Sun, Moon, Shield, KeyRound, ChevronRight, Command,
} from "lucide-react";
import AdminUsersView from "@/components/views/AdminUsersView";
import { API_BASE } from "@/lib/api";

export const TabContext = React.createContext<{
  activeTab: string;
  navigateTo: (tab: string) => void;
}>({
  activeTab: "dashboard",
  navigateTo: () => {},
});

type MenuItem = { id: string; label: string; icon: React.ElementType; desc: string };

const DEFAULT_NOTIFICATIONS = [
  "Cyber Crime rising in Bengaluru East (+43%)",
  "New vehicle-theft hotspot detected near Indiranagar PS",
  "Repeat offender flagged active in Kalasipalya beat",
];

const OPERATOR_MENU: MenuItem[] = [
  { id: "dashboard", label: "Executive Dashboard", icon: LayoutDashboard, desc: "Command overview & KPIs" },
  { id: "map", label: "Interactive Crime Map", icon: Map, desc: "Hotspots & patrol routes" },
  { id: "forecast", label: "AI Forecast Console", icon: TrendingUp, desc: "Predictive trend forecasting" },
  { id: "sociological", label: "Sociological & AI", icon: Brain, desc: "Socio-economic correlations" },
  { id: "network", label: "Criminal Network", icon: Share2, desc: "Gang cells & suspect links" },
  { id: "search", label: "Semantic Case Search", icon: Search, desc: "NLP-powered case search" },
  { id: "chatbot", label: "AI Copilot Chat", icon: MessageSquare, desc: "Investigation assistant" },
  { id: "reports", label: "Briefing Reports", icon: FileSpreadsheet, desc: "Rankings & CSV exports" },
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<{ username: string; role: string } | null>(null);
  const [usernameInput, setUsernameInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  const [loginError, setLoginError] = useState("");
  const [pendingPreAuthToken, setPendingPreAuthToken] = useState<string | null>(null);
  const [otpInput, setOtpInput] = useState("");
  const [otpSubmitting, setOtpSubmitting] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications, setNotifications] = useState<string[]>(DEFAULT_NOTIFICATIONS);
  const [activeTab, setActiveTab] = useState("dashboard");
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  const [showPalette, setShowPalette] = useState(false);
  const [paletteQuery, setPaletteQuery] = useState("");

  // ---- Command palette hotkey ----
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setShowPalette((p) => !p);
      }
      if (e.key === "Escape") setShowPalette(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("ksp_theme", next);
    document.documentElement.setAttribute("data-theme", next);
  };

  // ---- Mount-time hydration from browser-only APIs (theme, session, hash) ----
  // These reads must happen post-mount (localStorage/window are unavailable during
  // SSR/prerender), so setting state here is intentional, not an avoidable cascade.
  useEffect(() => {
    const savedTheme = (localStorage.getItem("ksp_theme") as "light" | "dark") || "dark";
    document.documentElement.setAttribute("data-theme", savedTheme);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(savedTheme);

    const token = localStorage.getItem("ksp_token");
    const stored = localStorage.getItem("ksp_user");
    if (token && stored) {
      setIsAuthenticated(true);
      setUser(JSON.parse(stored));
    }

    const hash = window.location.hash.replace("#", "");
    if (hash) setActiveTab(hash);
  }, []);

  const navigateTo = useCallback((tab: string) => {
    setActiveTab(tab);
    window.location.hash = tab;
  }, []);

  // ---- Auth ----
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError("");
    if (!usernameInput || !passwordInput) {
      setLoginError("Please enter both username and password.");
      return;
    }
    try {
      const body = new URLSearchParams();
      body.append("username", usernameInput);
      body.append("password", passwordInput);
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: body.toString(),
      });
      if (res.ok) {
        const data = await res.json();
        if (data.mfa_required) {
          setPendingPreAuthToken(data.pre_auth_token);
          setPasswordInput("");
          return;
        }
        persistSession(data);
      } else {
        const err = await res.json().catch(() => ({}));
        setLoginError(err.detail || "Authentication failed. Try demo password: 'password'.");
      }
    } catch {
      // Offline demo fallback
      if (["password", "admin", "ksp123"].includes(passwordInput)) {
        const role = usernameInput.toLowerCase() === "admin" ? "Admin" : "Superintendent";
        const fakeUser = { username: usernameInput, role };
        localStorage.setItem("ksp_token", "demo_token");
        localStorage.setItem("ksp_user", JSON.stringify(fakeUser));
        setUser(fakeUser);
        setIsAuthenticated(true);
      } else {
        setLoginError("Cannot reach the KSP Sentinel API. Start the backend, or use demo password 'password'.");
      }
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError("");
    if (!pendingPreAuthToken) return;
    if (!/^\d{6}$/.test(otpInput)) {
      setLoginError("Enter the 6-digit code from your authenticator app.");
      return;
    }
    setOtpSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pre_auth_token: pendingPreAuthToken, code: otpInput }),
      });
      const data = await res.json();
      if (res.ok) {
        persistSession(data);
        setPendingPreAuthToken(null);
        setOtpInput("");
      } else {
        setLoginError(data.detail || "Invalid authentication code.");
        setOtpInput("");
      }
    } catch {
      setLoginError("Cannot reach the KSP Sentinel API. The MFA session may have expired — go back and sign in again.");
    } finally {
      setOtpSubmitting(false);
    }
  };

  function persistSession(data: {
    access_token: string; refresh_token?: string; user: { username: string; role: string };
  }) {
    localStorage.setItem("ksp_token", data.access_token);
    if (data.refresh_token) localStorage.setItem("ksp_refresh_token", data.refresh_token);
    localStorage.setItem("ksp_user", JSON.stringify(data.user));
    setUser(data.user);
    setIsAuthenticated(true);
  }

  const handleLogout = () => {
    const refresh = localStorage.getItem("ksp_refresh_token");
    if (refresh) {
      fetch(`${API_BASE}/api/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      }).catch(() => {});
    }
    localStorage.removeItem("ksp_token");
    localStorage.removeItem("ksp_refresh_token");
    localStorage.removeItem("ksp_user");
    setIsAuthenticated(false);
    setUser(null);
  };

  // ======================================================================
  // AUTH SCREENS
  // ======================================================================
  if (!isAuthenticated && pendingPreAuthToken) {
    return <OtpScreen {...{ handleVerifyOtp, loginError, otpInput, setOtpInput, otpSubmitting, onBack: () => { setPendingPreAuthToken(null); setOtpInput(""); setLoginError(""); } }} />;
  }
  if (!isAuthenticated) {
    return <LoginScreen {...{ handleLogin, loginError, usernameInput, setUsernameInput, passwordInput, setPasswordInput }} />;
  }

  // ======================================================================
  // AUTHENTICATED SHELL
  // ======================================================================
  const isAdmin = (user?.role || "").toLowerCase() === "admin";
  const menu: MenuItem[] = isAdmin
    ? [{ id: "admin-users", label: "Officer Access Control", icon: Shield, desc: "Manage console accounts" }]
    : OPERATOR_MENU;

  const paletteItems = OPERATOR_MENU.filter(
    (m) => !paletteQuery || m.label.toLowerCase().includes(paletteQuery.toLowerCase())
  );

  return (
    <TabContext.Provider value={{ activeTab, navigateTo }}>
      <div className="flex h-screen gap-4 overflow-hidden bg-[var(--color-base)] p-4">
        {/* ================= SIDEBAR ================= */}
        <aside className="glass z-20 flex w-[230px] shrink-0 flex-col justify-between p-0">
          <div>
            {/* Logo */}
            <div className="flex h-16 items-center gap-3 border-b border-[var(--color-hairline)] px-5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--color-accent-cyan)]/25 bg-[var(--color-accent-cyan)]/10">
                <ShieldAlert className="h-[18px] w-[18px] text-[var(--color-accent-cyan)]" />
              </div>
              <span className="text-sm font-bold uppercase tracking-wider text-[var(--color-ink)]">
                KSP Sentinel
              </span>
            </div>

            {/* Nav */}
            <nav className="space-y-1 p-3">
              {menu.map((item) => {
                const Icon = item.icon;
                const active = isAdmin ? true : activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => !isAdmin && navigateTo(item.id)}
                    className={`group relative flex w-full items-center gap-3 rounded-[var(--radius-well)] px-3.5 py-2.5 text-left text-[13px] font-medium transition-all ${
                      active
                        ? "bg-[var(--color-accent-blue)]/10 text-[var(--color-ink)]"
                        : "text-[var(--color-ink-muted)] hover:bg-white/[0.03] hover:text-[var(--color-ink)]"
                    }`}
                  >
                    {active && (
                      <span className="absolute left-0 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r-full bg-[var(--color-accent-cyan)]" />
                    )}
                    <Icon
                      className={`h-[18px] w-[18px] shrink-0 ${
                        active ? "text-[var(--color-accent-cyan)]" : "text-[var(--color-ink-faint)] group-hover:text-[var(--color-ink-muted)]"
                      }`}
                    />
                    <span className="truncate">{item.label}</span>
                  </button>
                );
              })}
            </nav>
          </div>

          {/* User footer */}
          <div className="border-t border-[var(--color-hairline)] p-3">
            <div className="mb-3 flex items-center gap-3 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-white/[0.02] p-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-full border border-[var(--color-accent-cyan)]/25 bg-gradient-to-br from-[var(--color-accent-cyan)]/25 to-[var(--color-accent-blue)]/25 text-[var(--color-accent-cyan)]">
                <User className="h-4.5 w-4.5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-bold uppercase text-[var(--color-ink)]">{user?.username || "Officer"}</p>
                <p className="truncate text-[10px] font-semibold uppercase tracking-wide text-[var(--color-ink-faint)]">{user?.role || "Investigator"}</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="flex w-full items-center justify-center gap-2 rounded-[var(--radius-well)] border border-[var(--color-hairline)] py-2.5 text-xs font-semibold text-[var(--color-ink-muted)] transition-all hover:border-[var(--color-danger)]/30 hover:bg-[var(--color-danger)]/5 hover:text-[var(--color-danger)]"
            >
              <LogOut className="h-4 w-4" />
              Logout
            </button>
          </div>
        </aside>

        {/* ================= MAIN ================= */}
        <div className="flex flex-1 flex-col gap-4 overflow-hidden">
          {/* Topbar */}
          <header className="glass z-10 flex h-16 shrink-0 items-center justify-between px-5">
            <button
              onClick={() => setShowPalette(true)}
              className="flex w-80 items-center gap-3 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-white/[0.02] px-4 py-2.5 text-left transition-all hover:border-[var(--color-hairline-strong)]"
            >
              <Search className="h-4 w-4 text-[var(--color-ink-faint)]" />
              <span className="text-xs text-[var(--color-ink-faint)]">Search cases, reports, or AI insights…</span>
              <span className="ml-auto flex items-center gap-1 rounded border border-[var(--color-hairline)] px-1.5 py-0.5 font-mono text-[9px] text-[var(--color-ink-faint)]">
                <Command className="h-2.5 w-2.5" />K
              </span>
            </button>

            <div className="flex items-center gap-4">
              {/* Gateway status */}
              <div className="flex items-center gap-2 rounded-full border border-[var(--color-ok)]/25 bg-[var(--color-ok)]/10 px-3 py-1">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="ping-ring absolute inline-flex h-full w-full rounded-full bg-[var(--color-ok)]" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[var(--color-ok)]" />
                </span>
                <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-ok)]">Gateway Status: Online</span>
              </div>

              <div className="h-6 w-px bg-[var(--color-hairline)]" />

              <button
                onClick={toggleTheme}
                className="rounded-full p-2 text-[var(--color-ink-muted)] transition-all hover:bg-white/[0.04] hover:text-[var(--color-ink)]"
                title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
              >
                {theme === "dark" ? <Sun className="h-4.5 w-4.5 text-[var(--color-accent-amber)]" /> : <Moon className="h-4.5 w-4.5" />}
              </button>

              {!isAdmin && (
                <div className="relative">
                  <button
                    onClick={() => setShowNotifications((s) => !s)}
                    className="relative rounded-full p-2 text-[var(--color-ink-muted)] transition-all hover:bg-white/[0.04] hover:text-[var(--color-ink)]"
                  >
                    <Bell className="h-4.5 w-4.5" />
                    {notifications.length > 0 && (
                      <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-[var(--color-danger)] pulse-dot" />
                    )}
                  </button>
                  {showNotifications && (
                    <div className="glass absolute right-0 mt-2.5 w-80 p-4">
                      <div className="mb-3 flex items-center justify-between">
                        <h3 className="text-xs font-bold uppercase tracking-wider text-[var(--color-ink-muted)]">Critical Alert Feed</h3>
                        <button onClick={() => setNotifications([])} className="text-[10px] text-[var(--color-accent-cyan)] hover:underline">Dismiss all</button>
                      </div>
                      <div className="space-y-2">
                        {notifications.length === 0 ? (
                          <p className="py-2 text-xs text-[var(--color-ink-faint)]">No active warning signals.</p>
                        ) : (
                          notifications.map((msg, i) => (
                            <div key={i} className="rounded border-l-2 border-[var(--color-danger)] bg-white/[0.02] p-2.5 text-xs text-[var(--color-ink-muted)]">
                              {msg}
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </header>

          {/* Content */}
          <main className="glass flex-1 overflow-y-auto p-6">
            {isAdmin ? <AdminUsersView currentUsername={user?.username || ""} /> : children}
          </main>
        </div>
      </div>

      {/* ================= COMMAND PALETTE ================= */}
      {showPalette && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center bg-black/70 p-4 pt-[18vh] backdrop-blur-md"
          onClick={() => { setShowPalette(false); setPaletteQuery(""); }}
        >
          <div
            className="glass flex w-full max-w-lg flex-col overflow-hidden !shadow-[var(--shadow-pop)]"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 border-b border-[var(--color-hairline)] px-4">
              <Search className="h-4.5 w-4.5 text-[var(--color-ink-faint)]" />
              <input
                autoFocus
                value={paletteQuery}
                onChange={(e) => setPaletteQuery(e.target.value)}
                placeholder="Type a command or search…"
                className="w-full bg-transparent py-4 text-sm text-[var(--color-ink)] placeholder-[var(--color-ink-faint)] focus:outline-none"
              />
              <span className="rounded border border-[var(--color-hairline)] px-1.5 py-0.5 font-mono text-[9px] text-[var(--color-ink-faint)]">ESC</span>
            </div>
            <div className="max-h-80 overflow-y-auto p-2">
              <div className="px-3 py-2 text-[10px] font-bold uppercase tracking-widest text-[var(--color-ink-faint)]">Navigation</div>
              {paletteItems.map((cmd) => {
                const Icon = cmd.icon;
                return (
                  <button
                    key={cmd.id}
                    onClick={() => { navigateTo(cmd.id); setShowPalette(false); setPaletteQuery(""); }}
                    className="group flex w-full items-center gap-3 rounded-[var(--radius-well)] px-3 py-3 text-left transition-all hover:bg-[var(--color-accent-cyan)]/10"
                  >
                    <Icon className="h-4.5 w-4.5 text-[var(--color-ink-faint)] group-hover:text-[var(--color-accent-cyan)]" />
                    <div className="flex-1">
                      <p className="text-xs font-semibold text-[var(--color-ink)]">Jump to {cmd.label}</p>
                      <p className="text-[10px] text-[var(--color-ink-faint)]">{cmd.desc}</p>
                    </div>
                    <ChevronRight className="h-4 w-4 text-[var(--color-ink-faint)] opacity-0 transition-opacity group-hover:opacity-100" />
                  </button>
                );
              })}
              {paletteItems.length === 0 && (
                <p className="px-3 py-6 text-center text-xs text-[var(--color-ink-faint)]">No matching commands.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </TabContext.Provider>
  );
}

// ======================================================================
// AUTH SUB-COMPONENTS
// ======================================================================
function LoginScreen({
  handleLogin, loginError, usernameInput, setUsernameInput, passwordInput, setPasswordInput,
}: {
  handleLogin: (e: React.FormEvent) => void;
  loginError: string;
  usernameInput: string; setUsernameInput: (v: string) => void;
  passwordInput: string; setPasswordInput: (v: string) => void;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={handleLogin} className="glass w-full max-w-md p-8">
        <div className="mb-8 flex flex-col items-center">
          <div className="breathe mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-[var(--color-accent-cyan)]/25 bg-[var(--color-accent-cyan)]/10 shadow-[0_0_24px_rgba(34,211,238,0.15)]">
            <ShieldAlert className="h-8 w-8 text-[var(--color-accent-cyan)]" />
          </div>
          <h1 className="text-2xl font-bold uppercase tracking-wider text-[var(--color-ink)]">KSP Sentinel</h1>
          <p className="mt-1 text-sm text-[var(--color-ink-muted)]">Karnataka Police Command Console</p>
        </div>
        {loginError && (
          <div className="mb-6 rounded-[var(--radius-well)] border border-[var(--color-danger)]/30 bg-[var(--color-danger)]/10 p-3 text-sm text-[var(--color-danger)]">{loginError}</div>
        )}
        <div className="mb-6 space-y-4">
          <Field label="Officer Username">
            <input type="text" value={usernameInput} onChange={(e) => setUsernameInput(e.target.value)} placeholder="e.g. keshav" className="ksp-input" />
          </Field>
          <Field label="Access Key Code">
            <input type="password" value={passwordInput} onChange={(e) => setPasswordInput(e.target.value)} placeholder="Enter password…" className="ksp-input" />
          </Field>
        </div>
        <button type="submit" className="ksp-cta">Authorize Access</button>
        <p className="mt-6 text-center text-xs text-[var(--color-ink-faint)]">Secured endpoint. Authorized personnel only.</p>
        <p className="mt-2 text-center text-[11px] text-[var(--color-ink-muted)]">
          Demo key: <span className="font-mono text-[var(--color-ink)]">password</span> · admin login → Officer Access Control
        </p>
      </form>
      <InputStyles />
    </div>
  );
}

function OtpScreen({
  handleVerifyOtp, loginError, otpInput, setOtpInput, otpSubmitting, onBack,
}: {
  handleVerifyOtp: (e: React.FormEvent) => void;
  loginError: string; otpInput: string; setOtpInput: (v: string) => void;
  otpSubmitting: boolean; onBack: () => void;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={handleVerifyOtp} className="glass w-full max-w-md p-8">
        <div className="mb-8 flex flex-col items-center">
          <div className="breathe mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-[var(--color-accent-cyan)]/25 bg-[var(--color-accent-cyan)]/10 shadow-[0_0_24px_rgba(34,211,238,0.15)]">
            <KeyRound className="h-8 w-8 text-[var(--color-accent-cyan)]" />
          </div>
          <h1 className="text-2xl font-bold uppercase tracking-wider text-[var(--color-ink)]">Two-Factor Check</h1>
          <p className="mt-1 text-center text-sm text-[var(--color-ink-muted)]">Enter the 6-digit code from your authenticator app</p>
        </div>
        {loginError && (
          <div className="mb-6 rounded-[var(--radius-well)] border border-[var(--color-danger)]/30 bg-[var(--color-danger)]/10 p-3 text-sm text-[var(--color-danger)]">{loginError}</div>
        )}
        <Field label="Authentication Code">
          <input
            type="text" inputMode="numeric" autoFocus maxLength={6} value={otpInput}
            onChange={(e) => setOtpInput(e.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="000000"
            className="ksp-input text-center font-mono text-xl tracking-[0.5em]"
          />
        </Field>
        <button type="submit" disabled={otpSubmitting} className="ksp-cta mt-6 disabled:opacity-50">
          {otpSubmitting ? "Verifying…" : "Verify & Continue"}
        </button>
        <button type="button" onClick={onBack} className="mt-4 w-full text-center text-xs text-[var(--color-ink-faint)] hover:text-[var(--color-ink-muted)]">← Back to password</button>
      </form>
      <InputStyles />
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-2 block text-xs font-semibold uppercase tracking-wider text-[var(--color-ink-muted)]">{label}</label>
      {children}
    </div>
  );
}

/** Inline utility classes for auth forms (kept local so the token file stays lean). */
function InputStyles() {
  return (
    <style>{`
      .ksp-input {
        width: 100%;
        background: color-mix(in srgb, var(--color-surface-2) 60%, transparent);
        border: 1px solid var(--color-hairline);
        border-radius: var(--radius-well);
        padding: 0.75rem 1rem;
        color: var(--color-ink);
        font-size: 0.875rem;
        transition: border-color 150ms ease, box-shadow 150ms ease;
      }
      .ksp-input::placeholder { color: var(--color-ink-faint); }
      .ksp-input:focus {
        outline: none;
        border-color: color-mix(in srgb, var(--color-accent-cyan) 60%, transparent);
        box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-accent-cyan) 10%, transparent);
      }
      .ksp-cta {
        width: 100%;
        background: linear-gradient(90deg, var(--color-accent-blue), var(--color-accent-cyan));
        color: #fff;
        font-weight: 600;
        padding: 0.75rem;
        border-radius: var(--radius-well);
        font-size: 0.8125rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        box-shadow: 0 8px 24px color-mix(in srgb, var(--color-accent-blue) 25%, transparent);
        transition: filter 150ms ease;
      }
      .ksp-cta:hover { filter: brightness(1.1); }
    `}</style>
  );
}
