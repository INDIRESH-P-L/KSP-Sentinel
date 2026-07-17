"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Users, UserPlus, Shield, Trash2, RefreshCw, AlertTriangle, X, Ban, CheckCircle2, KeyRound
} from "lucide-react";
import { authFetch } from "@/lib/api";

interface ManagedUser {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string | null;
  created_by: string | null;
}

const ROLES = ["Admin", "Superintendent", "Investigator", "Analyst"];

function roleBadgeClass(role: string) {
  switch (role) {
    case "Admin": return "bg-purple-500/10 text-purple-300 border-purple-500/25";
    case "Superintendent": return "bg-cyan-500/10 text-cyan-300 border-cyan-500/25";
    case "Analyst": return "bg-amber-500/10 text-amber-300 border-amber-500/25";
    default: return "bg-blue-500/10 text-blue-300 border-blue-500/25";
  }
}

export default function AdminUsersView({ currentUsername }: { currentUsername: string }) {
  const [users, setUsers] = useState<ManagedUser[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  // Create-user form state
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("Investigator");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  // Password-reset UI state (per row)
  const [resetForId, setResetForId] = useState<number | null>(null);
  const [resetPassword, setResetPassword] = useState("");

  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await authFetch("/api/users/");
        if (cancelled) return;
        if (res.ok) {
          setUsers(await res.json());
        } else if (res.status === 403) {
          setError("Your account does not have admin privileges.");
        } else {
          setError(`Could not load users (HTTP ${res.status}).`);
        }
      } catch (e) {
        if (!cancelled) {
          setError("Cannot reach the KSP Sentinel API. Confirm the backend is running on http://localhost:8000.");
          console.error("Error loading users:", e);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [reloadKey]);

  // Lightweight re-fetch used after mutations (create/update/delete) -- called from
  // click handlers, not an effect, so it updates the table in place without flashing
  // the full-page loading state that the initial `load()` above shows.
  const refreshUsers = useCallback(async () => {
    try {
      const res = await authFetch("/api/users/");
      if (res.ok) setUsers(await res.json());
    } catch (e) {
      console.error("Error refreshing users:", e);
    }
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError("");
    if (newUsername.trim().length < 2) { setCreateError("Enter a valid username."); return; }
    if (newPassword.length < 6) { setCreateError("Password must be at least 6 characters."); return; }

    setCreating(true);
    try {
      const res = await authFetch("/api/users/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: newUsername.trim(), password: newPassword, role: newRole })
      });
      if (res.ok) {
        setNewUsername(""); setNewPassword(""); setNewRole("Investigator");
        setShowCreate(false);
        await refreshUsers();
      } else {
        const err = await res.json().catch(() => ({}));
        setCreateError(err.detail || "Could not create user.");
      }
    } catch (e) {
      setCreateError("Cannot reach the KSP Sentinel API.");
    } finally {
      setCreating(false);
    }
  };

  const handleRoleChange = async (id: number, role: string) => {
    setBusyId(id); setActionError(null);
    try {
      const res = await authFetch(`/api/users/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role })
      });
      if (res.ok) await refreshUsers();
      else { const err = await res.json().catch(() => ({})); setActionError(err.detail || "Could not update role."); }
    } catch { setActionError("Cannot reach the KSP Sentinel API."); }
    finally { setBusyId(null); }
  };

  const handleToggleActive = async (u: ManagedUser) => {
    setBusyId(u.id); setActionError(null);
    try {
      const res = await authFetch(`/api/users/${u.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !u.is_active })
      });
      if (res.ok) await refreshUsers();
      else { const err = await res.json().catch(() => ({})); setActionError(err.detail || "Could not update status."); }
    } catch { setActionError("Cannot reach the KSP Sentinel API."); }
    finally { setBusyId(null); }
  };

  const handleResetPassword = async (id: number) => {
    if (resetPassword.length < 6) { setActionError("Password must be at least 6 characters."); return; }
    setBusyId(id); setActionError(null);
    try {
      const res = await authFetch(`/api/users/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: resetPassword })
      });
      if (res.ok) { setResetForId(null); setResetPassword(""); await refreshUsers(); }
      else { const err = await res.json().catch(() => ({})); setActionError(err.detail || "Could not reset password."); }
    } catch { setActionError("Cannot reach the KSP Sentinel API."); }
    finally { setBusyId(null); }
  };

  const handleDelete = async (u: ManagedUser) => {
    if (!window.confirm(`Permanently remove the account "${u.username}"? This cannot be undone.`)) return;
    setBusyId(u.id); setActionError(null);
    try {
      const res = await authFetch(`/api/users/${u.id}`, { method: "DELETE" });
      if (res.ok) await refreshUsers();
      else { const err = await res.json().catch(() => ({})); setActionError(err.detail || "Could not delete user."); }
    } catch { setActionError("Cannot reach the KSP Sentinel API."); }
    finally { setBusyId(null); }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <Users className="w-8 h-8 text-cyan-400 animate-pulse" />
        <div className="text-cyan-400 font-bold text-lg animate-pulse tracking-wider">LOADING ACCESS REGISTRY...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="glass-panel max-w-md w-full p-8 rounded-xl border border-red-500/20 text-center space-y-4">
          <div className="w-14 h-14 mx-auto rounded-full bg-red-500/10 border border-red-500/25 flex items-center justify-center">
            <AlertTriangle className="w-7 h-7 text-red-400" />
          </div>
          <div>
            <h3 className="text-slate-100 font-bold uppercase tracking-wider text-sm">Access Registry Unavailable</h3>
            <p className="text-slate-400 text-xs mt-2 leading-relaxed">{error}</p>
          </div>
          <button onClick={() => setReloadKey(k => k + 1)} className="inline-flex items-center gap-2 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-semibold py-2.5 px-5 rounded-lg transition-all text-xs uppercase tracking-wider cursor-pointer">
            <RefreshCw className="w-3.5 h-3.5" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass-panel p-6 rounded-xl border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
            <Shield className="w-5 h-5 text-purple-400" />
            Officer Access Control
          </h2>
          <p className="text-xs text-slate-400 mt-1">Create console accounts, assign access levels, and revoke access. Admin only.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="p-3.5 rounded-lg bg-slate-950/40 border border-slate-800 text-center min-w-[90px]">
            <p className="text-2xl font-bold text-cyan-400">{users?.length ?? 0}</p>
            <span className="text-[9px] font-semibold text-slate-500 uppercase tracking-wider">Total Accounts</span>
          </div>
          <button
            onClick={() => setShowCreate(v => !v)}
            className="inline-flex items-center gap-2 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-semibold py-2.5 px-5 rounded-lg transition-all text-xs uppercase tracking-wider cursor-pointer"
          >
            <UserPlus className="w-4 h-4" />
            New Officer Account
          </button>
        </div>
      </div>

      {/* Create form */}
      {showCreate && (
        <div className="glass-panel p-6 rounded-xl border border-cyan-500/20 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200">New Officer Account</h3>
            <button onClick={() => setShowCreate(false)} className="text-slate-500 hover:text-slate-300 cursor-pointer">
              <X className="w-4 h-4" />
            </button>
          </div>
          <form onSubmit={handleCreate} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div>
              <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Username</label>
              <input
                value={newUsername}
                onChange={e => setNewUsername(e.target.value)}
                placeholder="e.g. officer_asha"
                className="w-full bg-slate-950/60 border border-slate-800 rounded-lg py-2 px-3 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Password</label>
              <input
                type="password"
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                placeholder="Min. 6 characters"
                className="w-full bg-slate-950/60 border border-slate-800 rounded-lg py-2 px-3 text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">Access Level</label>
              <select
                value={newRole}
                onChange={e => setNewRole(e.target.value)}
                className="w-full bg-slate-950/60 border border-slate-800 rounded-lg py-2 px-3 text-slate-100 text-sm focus:outline-none focus:border-cyan-500 cursor-pointer"
              >
                {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <button
              type="submit"
              disabled={creating}
              className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg transition-all text-xs uppercase tracking-wider cursor-pointer"
            >
              {creating ? "Creating..." : "Create Account"}
            </button>
          </form>
          {createError && (
            <div className="bg-red-500/10 border border-red-500/30 text-red-200 text-xs p-3 rounded-lg">{createError}</div>
          )}
        </div>
      )}

      {actionError && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-200 text-xs p-3 rounded-lg flex items-center justify-between">
          <span>{actionError}</span>
          <button onClick={() => setActionError(null)} className="text-red-300 hover:text-red-100 cursor-pointer"><X className="w-3.5 h-3.5" /></button>
        </div>
      )}

      {/* User table */}
      <div className="glass-panel rounded-xl border border-slate-800 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-950/40">
                <th className="text-left px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Username</th>
                <th className="text-left px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Access Level</th>
                <th className="text-left px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Status</th>
                <th className="text-left px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Created</th>
                <th className="text-right px-5 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users?.map(u => {
                const isSelf = u.username === currentUsername;
                const isBusy = busyId === u.id;
                return (
                  <tr key={u.id} className="border-b border-slate-850 last:border-b-0 hover:bg-slate-900/30 transition-colors">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-200">{u.username}</span>
                        {isSelf && <span className="text-[9px] font-bold text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 px-1.5 py-0.5 rounded uppercase">You</span>}
                      </div>
                      <p className="text-[10px] text-slate-500 mt-0.5">Added by {u.created_by || "—"}</p>
                    </td>
                    <td className="px-5 py-3.5">
                      <select
                        value={u.role}
                        disabled={isBusy}
                        onChange={e => handleRoleChange(u.id, e.target.value)}
                        className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded border cursor-pointer disabled:opacity-50 ${roleBadgeClass(u.role)}`}
                      >
                        {ROLES.map(r => <option key={r} value={r} className="bg-slate-900 text-slate-100">{r}</option>)}
                      </select>
                    </td>
                    <td className="px-5 py-3.5">
                      {u.is_active ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded">
                          <CheckCircle2 className="w-3 h-3" /> Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold uppercase text-slate-400 bg-slate-800/60 border border-slate-700 px-2 py-0.5 rounded">
                          <Ban className="w-3 h-3" /> Deactivated
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-slate-400 text-xs">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "—"}
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => { setResetForId(resetForId === u.id ? null : u.id); setResetPassword(""); }}
                          title="Reset password"
                          className="p-1.5 rounded bg-slate-900/60 border border-slate-800 text-slate-400 hover:text-cyan-300 hover:border-cyan-500/30 transition-all cursor-pointer"
                        >
                          <KeyRound className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleToggleActive(u)}
                          disabled={isSelf || isBusy}
                          title={isSelf ? "You cannot deactivate your own account" : u.is_active ? "Deactivate" : "Reactivate"}
                          className="p-1.5 rounded bg-slate-900/60 border border-slate-800 text-slate-400 hover:text-amber-300 hover:border-amber-500/30 transition-all cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                          {u.is_active ? <Ban className="w-3.5 h-3.5" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
                        </button>
                        <button
                          onClick={() => handleDelete(u)}
                          disabled={isSelf || isBusy}
                          title={isSelf ? "You cannot delete your own account" : "Remove account"}
                          className="p-1.5 rounded bg-slate-900/60 border border-slate-800 text-slate-400 hover:text-red-400 hover:border-red-500/30 transition-all cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      {resetForId === u.id && (
                        <div className="flex items-center gap-2 mt-2 justify-end">
                          <input
                            type="password"
                            autoFocus
                            value={resetPassword}
                            onChange={e => setResetPassword(e.target.value)}
                            placeholder="New password"
                            className="bg-slate-950/60 border border-slate-800 rounded-lg py-1.5 px-2.5 text-slate-100 placeholder-slate-500 text-xs w-36 focus:outline-none focus:border-cyan-500"
                          />
                          <button
                            onClick={() => handleResetPassword(u.id)}
                            disabled={isBusy}
                            className="text-[10px] font-bold uppercase bg-cyan-500/10 text-cyan-300 border border-cyan-500/25 px-2.5 py-1.5 rounded cursor-pointer disabled:opacity-50"
                          >
                            Set
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {users?.length === 0 && (
          <p className="text-slate-500 text-xs italic text-center py-8">No accounts yet.</p>
        )}
      </div>
    </div>
  );
}
