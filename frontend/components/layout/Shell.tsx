"use client";

import React, { useState, useEffect } from "react";
import {
  ShieldAlert, LayoutDashboard, Map, TrendingUp, Share2,
  Search, MessageSquare, FileSpreadsheet, LogOut, Bell, User,
  Brain, Sun, Moon, Shield
} from "lucide-react";
import AdminUsersView from "@/components/views/AdminUsersView";

export const TabContext = React.createContext<{
  activeTab: string;
  navigateTo: (tab: string) => void;
}>({
  activeTab: "dashboard",
  navigateTo: () => {},
});

export default function Shell({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<{ username: string; role: string } | null>(null);
  const [usernameInput, setUsernameInput] = useState("");
  const [passwordInput, setPasswordInput] = useState("");
  const [loginError, setLoginError] = useState("");
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications, setNotifications] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState("dashboard");
  const [theme, setTheme] = useState<"light" | "dark">("dark");

  useEffect(() => {
    const savedTheme = localStorage.getItem("ksp_theme") as "light" | "dark" | null;
    const initialTheme = savedTheme || "dark";
    setTheme(initialTheme);
    document.documentElement.setAttribute("data-theme", initialTheme);
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    localStorage.setItem("ksp_theme", nextTheme);
    document.documentElement.setAttribute("data-theme", nextTheme);
  };

  useEffect(() => {
    // Check local storage auth
    const storedToken = localStorage.getItem("ksp_token");
    const storedUser = localStorage.getItem("ksp_user");
    if (storedToken && storedUser) {
      setIsAuthenticated(true);
      setUser(JSON.parse(storedUser));
    }
    
    // Default notifications
    setNotifications([
      "Cyber Crime is rising in Bengaluru East (+43%)",
      "New Vehicle Theft hotspot detected in Indiranagar PS",
      "Repeat Offender Raghu 'Dada' Gowda reported active"
    ]);
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError("");

    if (!usernameInput || !passwordInput) {
      setLoginError("Please enter both username and password");
      return;
    }

    try {
      // POST form data to FastAPI login endpoint
      const formData = new URLSearchParams();
      formData.append("username", usernameInput);
      formData.append("password", passwordInput);

      const res = await fetch("http://localhost:8000/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: formData.toString()
      });

      if (res.ok) {
        const data = await res.json();
        localStorage.setItem("ksp_token", data.access_token);
        localStorage.setItem("ksp_user", JSON.stringify(data.user));
        setUser(data.user);
        setIsAuthenticated(true);
      } else {
        const err = await res.json();
        setLoginError(err.detail || "Authentication failed. Try password: 'password'");
      }
    } catch (e) {
      // Fallback bypass for frontend demo when the API server is unreachable
      if (passwordInput === "password" || passwordInput === "admin" || passwordInput === "ksp123") {
        const fakeUser = { username: usernameInput, role: "Superintendent" };
        localStorage.setItem("ksp_token", "fake_jwt_token");
        localStorage.setItem("ksp_user", JSON.stringify(fakeUser));
        setUser(fakeUser);
        setIsAuthenticated(true);
      } else {
        setLoginError("Cannot reach the KSP Sentinel API (http://localhost:8000). Start the backend, or use the demo password shown below.");
      }
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("ksp_token");
    localStorage.removeItem("ksp_user");
    setIsAuthenticated(false);
    setUser(null);
  };

  // Sync tab navigation with standard url hash or state
  useEffect(() => {
    const hash = window.location.hash.replace("#", "");
    if (hash) {
      setActiveTab(hash);
    }
  }, []);

  const navigateTo = (tabName: string) => {
    setActiveTab(tabName);
    window.location.hash = tabName;
  };

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <form onSubmit={handleLogin} className="glass-panel w-full max-w-md p-8 rounded-xl border border-blue-500/20 shadow-2xl">
          <div className="flex flex-col items-center mb-8">
            <div className="w-16 h-16 bg-[var(--accent-blue)]/10 border border-[rgba(30,64,175,0.12)] rounded-full flex items-center justify-center mb-4 soft-pulse">
              <ShieldAlert className="w-8 h-8 text-[var(--accent-blue)]" />
            </div>
            <h1 className="text-2xl font-bold tracking-wider text-[var(--foreground)] uppercase">KSP Sentinel</h1>
            <p className="muted text-sm mt-1">Karnataka Police Command Console</p>
          </div>

          {loginError && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-200 text-sm p-3 rounded-lg mb-6">
              {loginError}
            </div>
          )}

          <div className="space-y-4 mb-6">
            <div>
              <label className="block muted text-xs font-semibold uppercase tracking-wider mb-2">Officer Username</label>
              <input 
                type="text" 
                value={usernameInput}
                onChange={e => setUsernameInput(e.target.value)}
                placeholder="e.g. keshav" 
                className="w-full bg-white border border-gray-200 rounded-lg py-2.5 px-4 text-slate-700 placeholder-slate-400 focus:outline-none focus:border-[var(--accent-blue)] transition-all text-sm"
              />
            </div>
            <div>
              <label className="block muted text-xs font-semibold uppercase tracking-wider mb-2">Access Key Code</label>
              <input 
                type="password" 
                value={passwordInput}
                onChange={e => setPasswordInput(e.target.value)}
                placeholder="Enter password..." 
                className="w-full bg-white border border-gray-200 rounded-lg py-2.5 px-4 text-slate-700 placeholder-slate-400 focus:outline-none focus:border-[var(--accent-blue)] transition-all text-sm"
              />
            </div>
          </div>

          <button 
            type="submit" 
            className="w-full bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-semibold py-3 rounded-lg transition-all shadow-lg shadow-blue-500/20 text-sm uppercase tracking-wider cursor-pointer"
          >
            Authorize Access
          </button>

          <p className="text-slate-500 text-xs text-center mt-6">
            Secured Endpoint. Authorized personnel access only.
          </p>
          <p className="text-slate-400 text-[11px] text-center mt-2">
            Demo access key: <span className="font-mono text-slate-300">password</span>
          </p>
        </form>
      </div>
    );
  }

  // Admin accounts are scoped to user management only -- no dashboard/map/graph/etc
  // access. This drives both the sidebar (single item, non-navigable) and the content
  // pane below (always AdminUsersView, regardless of activeTab/hash).
  const isAdmin = (user?.role || "").toLowerCase() === "admin";

  const menuItems = isAdmin
    ? [{ id: "admin-users", label: "Officer Access Control", icon: Shield }]
    : [
        { id: "dashboard", label: "Executive Dashboard", icon: LayoutDashboard },
        { id: "map", label: "Interactive Crime Map", icon: Map },
        { id: "forecast", label: "AI Forecast Console", icon: TrendingUp },
        { id: "sociological", label: "Sociological & AI", icon: Brain },
        { id: "network", label: "Criminal Network", icon: Share2 },
        { id: "search", label: "Semantic Case Search", icon: Search },
        { id: "chatbot", label: "AI Copilot Chat", icon: MessageSquare },
        { id: "reports", label: "Briefing Reports", icon: FileSpreadsheet }
      ];

  return (
    <TabContext.Provider value={{ activeTab, navigateTo }}>
      <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 glass-panel flex flex-col justify-between z-20 p-0">
        <div>
          {/* Logo */}
          <div className="h-16 flex items-center px-6 border-b border-slate-800">
            <div className="flex items-center gap-3">
              <ShieldAlert className="w-6 h-6 text-cyan-400" />
              <span className="font-bold text-slate-100 tracking-wider uppercase text-sm">KSP Sentinel</span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-4 space-y-1.5">
            {menuItems.map(item => {
              const Icon = item.icon;
              const isActive = isAdmin ? true : activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => !isAdmin && navigateTo(item.id)}
                  className={`w-full flex items-center gap-3.5 px-4 py-3 rounded-lg text-sm font-medium transition-all cursor-pointer ${
                    isActive 
                      ? "bg-blue-600/20 text-cyan-400 border-l-2 border-cyan-400 shadow-md shadow-blue-500/5" 
                      : "text-slate-400 hover:bg-slate-800/40 hover:text-slate-200"
                  }`}
                >
                  <Icon className={`w-5 h-5 ${isActive ? "text-cyan-400" : "text-slate-400"}`} />
                  {item.label}
                </button>
              );
            })}
          </nav>
        </div>

        {/* User profile footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/40">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-9 h-9 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300">
              <User className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-slate-200 text-xs font-semibold truncate uppercase">{user?.username || "Officer"}</p>
              <p className="text-slate-500 text-[10px] truncate uppercase">{user?.role || "Investigator"}</p>
            </div>
          </div>
          <button 
            onClick={handleLogout}
            className="w-full flex items-center justify-center gap-2 border border-slate-800 hover:border-red-500/30 hover:bg-red-500/5 text-slate-400 hover:text-red-400 py-2 rounded-lg text-xs font-medium transition-all cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
            Logout Command
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header */}
        <header className="h-16 glass-panel flex items-center justify-between px-8 z-10">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold uppercase tracking-widest text-slate-500">
              {isAdmin ? "Administrative Access" : "Security Clearance Level IV"}
            </span>
            <span className="w-2 h-2 rounded-full bg-emerald-500 alarm-pulse"></span>
          </div>

          <div className="flex items-center gap-6">
            {/* Theme switcher */}
            <button
              onClick={toggleTheme}
              className="p-2 text-slate-400 hover:text-slate-100 rounded-full hover:bg-slate-800/40 transition-all cursor-pointer"
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              {theme === "dark" ? <Sun className="w-5 h-5 text-amber-450" /> : <Moon className="w-5 h-5 text-slate-500" />}
            </button>

            {/* Alarm notifications -- crime-intel alerts are out of scope for a
                user-management-only admin account, so this is hidden for admins. */}
            {!isAdmin && (
              <div className="relative">
                <button
                  onClick={() => setShowNotifications(!showNotifications)}
                  className="p-2 text-slate-400 hover:text-slate-100 rounded-full hover:bg-slate-800/40 transition-all relative cursor-pointer"
                >
                  <Bell className="w-5 h-5" />
                  {notifications.length > 0 && (
                    <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full alarm-pulse"></span>
                  )}
                </button>

                {showNotifications && (
                  <div className="absolute right-0 mt-2.5 w-80 glass-panel border border-slate-800 rounded-lg p-4 z-50">
                    <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 mb-3 flex items-center justify-between">
                      <span>Critical Alert Signal Feed</span>
                      <span className="text-[10px] font-normal text-cyan-400 lowercase cursor-pointer" onClick={() => setNotifications([])}>Dismiss All</span>
                    </h3>
                    <div className="space-y-2.5">
                      {notifications.length === 0 ? (
                        <p className="text-slate-500 text-xs py-2">No active warning signals detected.</p>
                      ) : (
                        notifications.map((msg, idx) => (
                          <div key={idx} className="bg-slate-950/60 border-l-2 border-red-500 p-2.5 rounded text-xs text-slate-300">
                            {msg}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="h-8 w-px bg-slate-800"></div>

            {/* Platform status indicator */}
            <div className="text-right">
              <p className="text-[10px] font-medium text-slate-500 uppercase">Gateway status</p>
              <p className="text-xs font-bold text-emerald-400 uppercase tracking-wider">ONLINE</p>
            </div>
          </div>
        </header>

        {/* Content Pane -- admins only ever see user management, regardless of
            activeTab/URL hash; everyone else gets the normal tab-dispatched page. */}
        <main className="flex-1 overflow-y-auto p-8">
          {isAdmin ? <AdminUsersView currentUsername={user?.username || ""} /> : children}
        </main>
      </div>
    </div>
    </TabContext.Provider>
  );
}
