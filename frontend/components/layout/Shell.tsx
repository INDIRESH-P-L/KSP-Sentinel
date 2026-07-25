"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  ShieldAlert, LayoutDashboard, Map, TrendingUp, Brain, Share2,
  Search, MessageSquare, FileSpreadsheet, LogOut, Bell, User,
  Sun, Moon, Shield, KeyRound, ChevronRight, Command, Database,
} from "lucide-react";
import { motion, AnimatePresence, LayoutGroup, useReducedMotion } from "framer-motion";
import AdminUsersView from "@/components/views/AdminUsersView";
import { API_BASE } from "@/lib/api";
import { GlassPanel, Magnetic } from "@/components/ui/GlassPanel";
import { KSPEmblemBadge } from "@/components/ui/KSPEmblemBadge";

export const TabContext = React.createContext<{
  activeTab: string;
  navigateTo: (tab: string, payload?: any) => void;
  navigationPayload: any;
}>({
  activeTab: "dashboard",
  navigateTo: () => {},
  navigationPayload: null,
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
  { id: "records", label: "Catalyst Data Explorer", icon: Database, desc: "Live hierarchical FIR records" },
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
  const [otpauthUri, setOtpauthUri] = useState<string | null>(null);
  const [totpSecret, setTotpSecret] = useState<string | null>(null);
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications, setNotifications] = useState<string[]>(DEFAULT_NOTIFICATIONS);
  const [activeTab, setActiveTab] = useState("dashboard");
  const [navigationPayload, setNavigationPayload] = useState<any>(null);
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  const [showPalette, setShowPalette] = useState(false);
  const [paletteQuery, setPaletteQuery] = useState("");
  const reduced = Boolean(useReducedMotion());

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

  // Signal auth state to the root <EmblemWatermark>: on the login/landing screen
  // (unauthenticated) it swells into a larger, brighter hero; inside the app it
  // stays faint. One shared watermark, one flag — no per-page copies.
  useEffect(() => {
    document.documentElement.setAttribute("data-authed", String(isAuthenticated));
  }, [isAuthenticated]);

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
          setOtpauthUri(data.otpauth_uri || null);
          setTotpSecret(data.totp_secret || null);
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

  const handleBypassOtp = async () => {
    setLoginError("");
    setOtpSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pre_auth_token: pendingPreAuthToken, code: "000000" }),
      });
      const data = await res.json();
      if (res.ok) {
        persistSession(data);
        setPendingPreAuthToken(null);
        setOtpInput("");
        setOtpauthUri(null);
        setTotpSecret(null);
      } else {
        setLoginError(data.detail || "Failed to bypass MFA.");
      }
    } catch {
      setLoginError("Cannot reach the KSP Sentinel API for MFA bypass.");
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
    return <OtpScreen {...{ handleVerifyOtp, handleBypassOtp, loginError, otpInput, setOtpInput, otpSubmitting, otpauthUri, totpSecret, reduced, onBack: () => { setPendingPreAuthToken(null); setOtpInput(""); setLoginError(""); setOtpauthUri(null); setTotpSecret(null); } }} />;
  }
  if (!isAuthenticated) {
    return <LoginScreen {...{ handleLogin, loginError, usernameInput, setUsernameInput, passwordInput, setPasswordInput, reduced }} />;
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
    <TabContext.Provider value={{ activeTab, navigateTo, navigationPayload }}>
      <div className="flex h-screen gap-3.5 overflow-hidden p-3.5">
        {/* ================= SIDEBAR ================= */}
        <GlassPanel
          as="aside"
          interactive
          sweep={false}
          className="z-20 w-[236px] shrink-0 p-0"
          bodyClassName="flex h-full flex-col justify-between"
        >
          <div>
            {/* Logo */}
            <div className="flex h-16 items-center gap-3 border-b border-[var(--color-hairline)] px-5">
              <div className="flex h-[34px] w-[34px] items-center justify-center rounded-[10px] border border-[var(--color-brass)]/40 bg-[var(--color-maroon)]/25 text-[var(--color-brass-bright)] shadow-[0_0_18px_rgba(184,147,90,0.28)]">
                <ShieldAlert className="h-[18px] w-[18px]" />
              </div>
              <span className="text-sm font-extrabold uppercase tracking-[0.14em] text-[var(--color-ink)]">
                KSP Sentinel
              </span>
            </div>

            <LayoutGroup id="sidebar-nav">
              <nav className="flex flex-col gap-1 p-3">
                {menu.map((item) => (
                  <NavButton
                    key={item.id}
                    item={item}
                    active={isAdmin ? true : activeTab === item.id}
                    reduced={!!reduced}
                    onClick={() => {
                      if (!isAdmin) {
                        sessionStorage.removeItem("ksp_target_district");
                        sessionStorage.removeItem("ksp_target_station");
                        navigateTo(item.id);
                      }
                    }}
                  />
                ))}
              </nav>
            </LayoutGroup>
          </div>

          {/* User footer */}
          <div className="border-t border-[var(--color-hairline)] p-3">
            <div className="mb-3 flex items-center gap-3 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-ivory)]/[0.02] p-2.5">
              <div className="flex h-[38px] w-[38px] items-center justify-center rounded-full border border-[var(--color-brass)]/30 bg-gradient-to-br from-[var(--color-maroon)]/40 to-[var(--color-brass)]/25 text-[var(--color-brass-bright)]">
                <User className="h-4.5 w-4.5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-bold uppercase text-[var(--color-ink)]">{user?.username || "Officer"}</p>
                <p className="truncate text-[10px] font-semibold uppercase tracking-[0.08em] text-[var(--color-ink-faint)]">{user?.role || "Investigator"}</p>
              </div>
            </div>
            <motion.button
              onClick={handleLogout}
              whileHover={reduced ? undefined : { y: -2 }}
              whileTap={reduced ? undefined : { scale: 0.98 }}
              transition={{ type: "spring", stiffness: 400, damping: 26 }}
              className="flex w-full items-center justify-center gap-2 rounded-[var(--radius-well)] border border-[var(--color-hairline)] py-2.5 text-xs font-semibold text-[var(--color-ink-muted)] transition-colors duration-200 hover:border-[var(--color-danger)]/40 hover:bg-[var(--color-danger)]/[0.08] hover:text-[#c96a6a]"
            >
              <LogOut className="h-4 w-4" />
              Logout
            </motion.button>
          </div>
        </GlassPanel>

        {/* ================= MAIN ================= */}
        <div className="flex flex-1 flex-col gap-3.5 overflow-hidden">
          {/* Topbar Header with Center Emblem */}
          <GlassPanel
            as="header"
            interactive
            sweep={false}
            className="z-10 h-16 shrink-0"
            bodyClassName="relative flex h-full items-center justify-between px-5"
          >
            <motion.button
              onClick={() => setShowPalette(true)}
              whileHover={reduced ? undefined : { y: -1 }}
              transition={{ type: "spring", stiffness: 400, damping: 26 }}
              className="flex min-w-0 max-w-[280px] items-center gap-3 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-ivory)]/[0.02] px-3.5 py-2 text-left transition-colors duration-200 hover:border-[var(--color-brass)]/35"
            >
              <Search className="h-4 w-4 shrink-0 text-[var(--color-ink-faint)]" />
              <span className="truncate text-xs text-[var(--color-ink-faint)]">Search 1.68M FIR cases…</span>
              <span className="mono ml-auto flex shrink-0 items-center gap-1 rounded-[5px] border border-[var(--color-hairline)] px-1.5 py-0.5 text-[9px] text-[var(--color-ink-faint)]">
                <Command className="h-2.5 w-2.5" />K
              </span>
            </motion.button>

            {/* EXACT CENTER: KARNATAKA STATE POLICE EMBLEM */}
            <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 hidden md:block">
              <KSPEmblemBadge />
            </div>

            <div className="flex items-center gap-4">
              {/* Gateway status */}
              <div className="flex items-center gap-2 rounded-full border border-[var(--color-ok)]/30 bg-[var(--color-ok)]/10 px-3.5 py-[5px]">
                <span className="relative flex h-[7px] w-[7px]">
                  <span className="ping-ring absolute inline-flex h-full w-full rounded-full bg-[var(--color-ok)]" />
                  <span className="relative inline-flex h-[7px] w-[7px] rounded-full bg-[var(--color-ok)]" />
                </span>
                <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-[var(--color-ok)]">Catalyst Online</span>
              </div>

              <div className="h-6 w-px bg-[var(--color-hairline)]" />

              <Magnetic radius={8}>
                <button
                  onClick={toggleTheme}
                  className="rounded-full p-2 text-[var(--color-ink-muted)] transition-colors hover:bg-[var(--color-ivory)]/[0.05] hover:text-[var(--color-ink)]"
                  title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
                >
                  {theme === "dark" ? <Sun className="h-4.5 w-4.5 text-[var(--color-brass-bright)]" /> : <Moon className="h-4.5 w-4.5" />}
                </button>
              </Magnetic>

              {!isAdmin && (
                <div className="relative">
                  <Magnetic radius={8}>
                    <button
                      onClick={() => setShowNotifications((s) => !s)}
                      className="relative rounded-full p-2 text-[var(--color-ink-muted)] transition-colors hover:bg-[var(--color-ivory)]/[0.05] hover:text-[var(--color-ink)]"
                    >
                      <Bell className="h-4.5 w-4.5" />
                      {notifications.length > 0 && (
                        <span className="pulse-dot absolute right-1.5 top-1.5 h-[7px] w-[7px] rounded-full bg-[var(--color-danger)]" />
                      )}
                    </button>
                  </Magnetic>

                  <AnimatePresence>
                    {showNotifications && (
                      <motion.div
                        initial={reduced ? { opacity: 0 } : { opacity: 0, y: -8, scale: 0.97 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={reduced ? { opacity: 0 } : { opacity: 0, y: -8, scale: 0.97 }}
                        transition={{ duration: 0.16, ease: [0.2, 0.9, 0.2, 1] }}
                        className="absolute right-0 z-40 mt-2.5 w-80 origin-top-right"
                      >
                        <GlassPanel sweep={false} className="p-4">
                          <div className="mb-3 flex items-center justify-between">
                            <h3 className="text-[11px] font-bold uppercase tracking-[0.1em] text-[var(--color-ink-muted)]">Critical Alert Feed</h3>
                            <button onClick={() => setNotifications([])} className="text-[10px] text-[var(--color-brass-bright)] hover:underline">Dismiss all</button>
                          </div>
                          <div className="flex flex-col gap-2">
                            {notifications.length === 0 ? (
                              <p className="py-2 text-xs text-[var(--color-ink-faint)]">No active warning signals.</p>
                            ) : (
                              notifications.map((msg, i) => (
                                <div key={i} className="rounded-md border-l-2 border-[var(--color-danger)] bg-[var(--color-ivory)]/[0.02] p-2.5 text-xs text-[var(--color-ink-muted)]">
                                  {msg}
                                </div>
                              ))
                            )}
                          </div>
                        </GlassPanel>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}
            </div>
          </GlassPanel>

          {/* Live Incident Marquee Ticker Bar */}
          <div className="flex h-8 shrink-0 items-center overflow-hidden rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)] px-4 text-xs font-semibold backdrop-blur-md">
            <span className="flex items-center gap-1.5 shrink-0 font-bold uppercase tracking-wider text-[var(--color-brass-bright)] mr-4 border-r border-[var(--color-hairline)] pr-4">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
              </span>
              LIVE CATALYST STREAM
            </span>
            <div className="flex items-center gap-8 overflow-hidden whitespace-nowrap text-[var(--color-ink-muted)]">
              <span>🚨 <strong className="text-[var(--color-ink)]">1,680,000 Karnataka FIR Records</strong> active across 40 State Districts</span>
              <span className="opacity-40">•</span>
              <span>⚡ <strong className="text-[var(--color-brass-bright)]">Bengaluru Urban</strong> (668 FIRs)</span>
              <span className="opacity-40">•</span>
              <span>🛡️ <strong className="text-[var(--color-ok)]">State Conviction Rate</strong> <strong className="text-[var(--color-ink)]">66.66%</strong></span>
              <span className="opacity-40">•</span>
              <span>📡 <strong className="text-[var(--color-brass-bright)]">CUSUM Z-Score Anomaly Engine</strong> Online</span>
            </div>
          </div>

          {/* Content — page/tab transitions (fade + slight scale/slide) */}
          <main className="glass flex-1 overflow-y-auto overflow-x-hidden p-[26px]">
            <AnimatePresence mode="wait">
              <motion.div
                key={isAdmin ? "admin" : activeTab}
                initial={reduced ? { opacity: 0 } : { opacity: 0, y: 10, scale: 0.994 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={reduced ? { opacity: 0 } : { opacity: 0, y: -8, scale: 0.994 }}
                transition={{ duration: reduced ? 0.12 : 0.24, ease: [0.2, 0.9, 0.2, 1] }}
              >
                {isAdmin ? <AdminUsersView currentUsername={user?.username || ""} /> : children}
              </motion.div>
            </AnimatePresence>
          </main>
        </div>
      </div>

      {/* ================= COMMAND PALETTE ================= */}
      <AnimatePresence>
        {showPalette && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 z-[60] flex items-start justify-center bg-black/70 p-4 pt-[17vh] backdrop-blur-[10px]"
            onClick={() => { setShowPalette(false); setPaletteQuery(""); }}
          >
            <motion.div
              initial={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.95, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={reduced ? { opacity: 0 } : { opacity: 0, scale: 0.97, y: 8 }}
              transition={{ duration: 0.2, ease: [0.2, 0.9, 0.2, 1] }}
              className="w-full max-w-[520px]"
              onClick={(e) => e.stopPropagation()}
            >
              <GlassPanel className="overflow-hidden !shadow-[var(--shadow-pop)]">
                <div className="flex items-center gap-3 border-b border-[var(--color-hairline)] px-4">
                  <Search className="h-4.5 w-4.5 text-[var(--color-ink-faint)]" />
                  <input
                    autoFocus
                    value={paletteQuery}
                    onChange={(e) => setPaletteQuery(e.target.value)}
                    placeholder="Type a command or search…"
                    className="w-full bg-transparent py-4 text-sm text-[var(--color-ink)] placeholder-[var(--color-ink-faint)] focus:outline-none"
                  />
                  <span className="mono rounded-[5px] border border-[var(--color-hairline)] px-1.5 py-0.5 text-[9px] text-[var(--color-ink-faint)]">ESC</span>
                </div>
                <div className="max-h-[340px] overflow-y-auto p-2">
                  <div className="px-3 py-2 text-[10px] font-bold uppercase tracking-[0.16em] text-[var(--color-ink-faint)]">Navigation</div>
                  {paletteItems.map((cmd) => {
                    const Icon = cmd.icon;
                    return (
                      <motion.button
                        key={cmd.id}
                        onClick={() => { navigateTo(cmd.id); setShowPalette(false); setPaletteQuery(""); }}
                        whileHover={reduced ? undefined : { x: 3 }}
                        transition={{ type: "spring", stiffness: 400, damping: 28 }}
                        className="group flex w-full items-center gap-3 rounded-[var(--radius-well)] px-3 py-3 text-left transition-colors hover:bg-[var(--color-maroon)]/15"
                      >
                        <Icon className="h-4.5 w-4.5 text-[var(--color-ink-faint)] group-hover:text-[var(--color-brass-bright)]" />
                        <div className="flex-1">
                          <p className="text-xs font-semibold text-[var(--color-ink)]">Jump to {cmd.label}</p>
                          <p className="text-[10px] text-[var(--color-ink-faint)]">{cmd.desc}</p>
                        </div>
                        <ChevronRight className="h-4 w-4 text-[var(--color-ink-faint)] opacity-0 transition-opacity group-hover:opacity-100" />
                      </motion.button>
                    );
                  })}
                  {paletteItems.length === 0 && (
                    <p className="px-3 py-6 text-center text-xs text-[var(--color-ink-faint)]">No matching commands.</p>
                  )}
                </div>
              </GlassPanel>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </TabContext.Provider>
  );
}

// ======================================================================
// SIDEBAR NAV ITEM — capsule + hover-pop description popover
// ======================================================================
function NavButton({
  item, active, onClick, reduced,
}: { item: MenuItem; active: boolean; onClick: () => void; reduced: boolean }) {
  const [hover, setHover] = useState(false);
  const Icon = item.icon;
  return (
    <div className="relative" onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
      <motion.button
        onClick={onClick}
        whileHover={reduced || active ? undefined : { x: 3 }}
        transition={{ type: "spring", stiffness: 400, damping: 26 }}
        className={`relative flex w-full items-center gap-3 rounded-full px-3.5 py-2.5 text-left text-[13px] font-medium transition-colors duration-200 ${
          active ? "text-[var(--color-ink)]" : "text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]"
        }`}
      >
        {active && (
          <motion.span
            layoutId="nav-capsule"
            className="absolute inset-0 rounded-full border border-[var(--color-brass)]/40 bg-gradient-to-r from-[var(--color-maroon)]/75 to-[var(--color-wine)]/50 shadow-[0_6px_20px_rgba(122,31,43,0.4)]"
            transition={{ type: "spring", stiffness: 420, damping: 34 }}
          />
        )}
        <Icon className={`relative z-10 h-[18px] w-[18px] shrink-0 ${active ? "text-[var(--color-brass-bright)]" : "text-[var(--color-ink-faint)]"}`} />
        <span className="relative z-10 truncate">{item.label}</span>
      </motion.button>

      {/* Hover-pop: a short description in a glass popover to the right */}
      <AnimatePresence>
        {hover && !active && (
          <motion.div
            initial={reduced ? { opacity: 0 } : { opacity: 0, x: -6, scale: 0.96 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={reduced ? { opacity: 0 } : { opacity: 0, x: -4 }}
            transition={{ duration: 0.15, ease: [0.2, 0.9, 0.2, 1] }}
            className="pointer-events-none absolute left-[calc(100%+14px)] top-1/2 z-50 w-max max-w-[220px] -translate-y-1/2"
          >
            <div className="glass glass-body rounded-[12px] px-3 py-2 shadow-[var(--shadow-pop)]">
              <p className="text-xs font-semibold text-[var(--color-ink)]">{item.label}</p>
              <p className="mt-0.5 text-[11px] leading-snug text-[var(--color-ink-faint)]">{item.desc}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ======================================================================
// AUTH SUB-COMPONENTS
// ======================================================================
function LoginScreen({
  handleLogin, loginError, usernameInput, setUsernameInput, passwordInput, setPasswordInput, reduced,
}: {
  handleLogin: (e: React.FormEvent) => void;
  loginError: string;
  usernameInput: string; setUsernameInput: (v: string) => void;
  passwordInput: string; setPasswordInput: (v: string) => void;
  reduced: boolean;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <motion.form
        onSubmit={handleLogin}
        initial={reduced ? { opacity: 0 } : { opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.2, 0.9, 0.2, 1] }}
        className="glass w-full max-w-md p-8"
      >
        <div className="mb-8 flex flex-col items-center">
          <div className="breathe mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-[var(--color-brass)]/35 bg-[var(--color-maroon)]/20 text-[var(--color-brass-bright)] shadow-[0_0_34px_rgba(184,147,90,0.22)]">
            <ShieldAlert className="h-8 w-8" />
          </div>
          <h1 className="text-2xl font-bold uppercase tracking-wider text-[var(--color-ink)]">KSP Sentinel</h1>
          <p className="mt-1 text-sm text-[var(--color-ink-muted)]">Karnataka Police Command Console</p>
        </div>
        {loginError && (
          <div className="mb-6 rounded-[var(--radius-well)] border border-[var(--color-danger)]/30 bg-[var(--color-danger)]/10 p-3 text-sm text-[#d08585]">{loginError}</div>
        )}
        <div className="mb-6 space-y-4">
          <Field label="Officer Username">
            <input type="text" value={usernameInput} onChange={(e) => setUsernameInput(e.target.value)} placeholder="e.g. keshav" className="ksp-input" />
          </Field>
          <Field label="Access Key Code">
            <input type="password" value={passwordInput} onChange={(e) => setPasswordInput(e.target.value)} placeholder="Enter password…" className="ksp-input" />
          </Field>
        </div>
        <motion.button
          type="submit"
          whileHover={reduced ? undefined : { scale: 1.015 }}
          whileTap={reduced ? undefined : { scale: 0.985 }}
          transition={{ type: "spring", stiffness: 400, damping: 24 }}
          className="ksp-cta"
        >
          Authorize Access
        </motion.button>
        <p className="mt-6 text-center text-xs text-[var(--color-ink-faint)]">Secured endpoint. Authorized personnel only.</p>
        <p className="mt-2 text-center text-[11px] text-[var(--color-ink-muted)]">
          Demo key: <span className="font-mono text-[var(--color-ink)]">password</span> · admin login → Officer Access Control
        </p>
      </motion.form>
      <InputStyles />
    </div>
  );
}

function OtpScreen({
  handleVerifyOtp, handleBypassOtp, loginError, otpInput, setOtpInput, otpSubmitting, otpauthUri, totpSecret, onBack, reduced,
}: {
  handleVerifyOtp: (e: React.FormEvent) => void;
  handleBypassOtp: () => void;
  loginError: string; otpInput: string; setOtpInput: (v: string) => void;
  otpSubmitting: boolean; otpauthUri: string | null; totpSecret: string | null; onBack: () => void; reduced: boolean;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <motion.form
        onSubmit={handleVerifyOtp}
        initial={reduced ? { opacity: 0 } : { opacity: 0, y: 16, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.2, 0.9, 0.2, 1] }}
        className="glass w-full max-w-md p-8"
      >
        <div className="mb-8 flex flex-col items-center">
          <div className="breathe mb-4 flex h-16 w-16 items-center justify-center rounded-2xl border border-[var(--color-brass)]/35 bg-[var(--color-maroon)]/20 text-[var(--color-brass-bright)] shadow-[0_0_34px_rgba(184,147,90,0.22)]">
            <KeyRound className="h-8 w-8" />
          </div>
          <h1 className="text-2xl font-bold uppercase tracking-wider text-[var(--color-ink)]">Two-Factor Check</h1>
          <p className="mt-1 text-center text-sm text-[var(--color-ink-muted)]">Enter the 6-digit code from your authenticator app</p>
        </div>
        {loginError && (
          <div className="mb-6 rounded-[var(--radius-well)] border border-[var(--color-danger)]/30 bg-[var(--color-danger)]/10 p-3 text-sm text-[#d08585]">{loginError}</div>
        )}

        {otpauthUri && (
          <div className="mb-6 flex flex-col items-center justify-center rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)] p-4 text-center">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-brass-bright)]">MFA Setup Scan</p>
            <img
              src={`https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(otpauthUri)}`}
              alt="MFA QR Code"
              className="mb-3 rounded-lg border border-[var(--color-hairline)] bg-white p-1"
            />
            <p className="text-[11px] text-[var(--color-ink-faint)]">Scan with Google Authenticator or manual key:</p>
            <code className="mt-1 select-all break-all font-mono text-xs text-[var(--color-ink)]">{totpSecret}</code>
          </div>
        )}

        <Field label="Authentication Code">
          <input
            type="text" inputMode="numeric" autoFocus maxLength={6} value={otpInput}
            onChange={(e) => setOtpInput(e.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="000000"
            className="ksp-input text-center font-mono text-xl tracking-[0.5em]"
          />
        </Field>

        <div className="mt-6 flex flex-col gap-3">
          <motion.button
            type="submit" disabled={otpSubmitting}
            whileHover={reduced || otpSubmitting ? undefined : { scale: 1.015 }}
            whileTap={reduced || otpSubmitting ? undefined : { scale: 0.985 }}
            transition={{ type: "spring", stiffness: 400, damping: 24 }}
            className="ksp-cta disabled:opacity-50"
          >
            {otpSubmitting ? "Verifying…" : "Verify & Continue"}
          </motion.button>

          <button type="button" onClick={handleBypassOtp} disabled={otpSubmitting} className="w-full rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)] py-2 text-xs font-semibold uppercase tracking-wider text-[var(--color-brass-bright)] transition-colors hover:border-[var(--color-brass)]/40 hover:bg-[var(--color-elevated)]">
            Bypass MFA (Demo Mode)
          </button>
        </div>

        <button type="button" onClick={onBack} className="mt-4 w-full text-center text-xs text-[var(--color-ink-faint)] hover:text-[var(--color-ink-muted)]">← Back to password</button>
      </motion.form>
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
        border-color: color-mix(in srgb, var(--color-brass) 60%, transparent);
        box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-brass) 12%, transparent);
      }
      .ksp-cta {
        width: 100%;
        background: linear-gradient(90deg, var(--color-maroon), var(--color-wine));
        color: var(--color-ink);
        font-weight: 600;
        padding: 0.75rem;
        border-radius: var(--radius-well);
        font-size: 0.8125rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        border: 1px solid color-mix(in srgb, var(--color-brass) 40%, transparent);
        box-shadow: 0 8px 24px color-mix(in srgb, var(--color-maroon) 40%, transparent);
        transition: filter 150ms ease;
      }
      .ksp-cta:hover { filter: brightness(1.12); }
    `}</style>
  );
}
