"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Users, UserPlus, Shield, Trash2, RefreshCw, X, Ban, CheckCircle2, KeyRound, Copy,
} from "lucide-react";
import { authFetch } from "@/lib/api";
import { SectionTitle, PanelLabel, Pill, Loading } from "@/components/ui/primitives";
import { mockUsers } from "@/lib/mock";
import type { ConsoleUser } from "@/lib/types";

interface MfaEnrollment { username: string; totp_secret: string; otpauth_uri: string }

const ROLES: ConsoleUser["role"][] = ["Admin", "Superintendent", "Investigator", "Analyst"];

export default function AdminUsersView({ currentUsername }: { currentUsername: string }) {
  const [users, setUsers] = useState<ConsoleUser[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  // create form
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState<ConsoleUser["role"]>("Investigator");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  const [resetForId, setResetForId] = useState<number | null>(null);
  const [resetPassword, setResetPassword] = useState("");
  const [mfaEnrollment, setMfaEnrollment] = useState<MfaEnrollment | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await authFetch("/api/users/");
        if (cancelled) return;
        if (res.ok) setUsers(await res.json());
        else setUsers(mockUsers);
      } catch {
        if (!cancelled) setUsers(mockUsers);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [reloadKey]);

  const refresh = useCallback(async () => {
    try {
      const res = await authFetch("/api/users/");
      if (res.ok) setUsers(await res.json());
    } catch { /* keep current */ }
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError("");
    if (newUsername.trim().length < 2) return setCreateError("Enter a valid username.");
    if (newPassword.length < 6) return setCreateError("Password must be at least 6 characters.");
    setCreating(true);
    try {
      const res = await authFetch("/api/users/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: newUsername.trim(), password: newPassword, role: newRole }),
      });
      if (res.ok) {
        const created = await res.json();
        if (created.totp_secret) setMfaEnrollment({ username: created.username, totp_secret: created.totp_secret, otpauth_uri: created.otpauth_uri });
        setNewUsername(""); setNewPassword(""); setNewRole("Investigator");
        setShowCreate(false);
        await refresh();
      } else {
        const err = await res.json().catch(() => ({}));
        setCreateError(err.detail || "Could not create user.");
      }
    } catch {
      setCreateError("Cannot reach the KSP Sentinel API.");
    } finally {
      setCreating(false);
    }
  };

  const patch = async (id: number, body: Record<string, unknown>, failMsg: string) => {
    setBusyId(id); setActionError(null);
    try {
      const res = await authFetch(`/api/users/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) await refresh();
      else { const err = await res.json().catch(() => ({})); setActionError(err.detail || failMsg); }
    } catch { setActionError("Cannot reach the KSP Sentinel API."); }
    finally { setBusyId(null); }
  };

  const handleResetPassword = async (id: number) => {
    if (resetPassword.length < 6) return setActionError("Password must be at least 6 characters.");
    await patch(id, { password: resetPassword }, "Could not reset password.");
    setResetForId(null); setResetPassword("");
  };

  const handleDelete = async (u: ConsoleUser) => {
    if (!window.confirm(`Permanently remove the account "${u.username}"? This cannot be undone.`)) return;
    setBusyId(u.id); setActionError(null);
    try {
      const res = await authFetch(`/api/users/${u.id}`, { method: "DELETE" });
      if (res.ok) await refresh();
      else { const err = await res.json().catch(() => ({})); setActionError(err.detail || "Could not delete user."); }
    } catch { setActionError("Cannot reach the KSP Sentinel API."); }
    finally { setBusyId(null); }
  };

  if (loading) return <Loading label="Loading access registry…" />;

  return (
    <div className="flex flex-col gap-[22px] fade-up">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SectionTitle>Officer Access Control</SectionTitle>
        <div className="flex items-center gap-2">
          <button onClick={() => setReloadKey((k) => k + 1)} className="flex items-center gap-2 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-white/[0.02] px-3 py-2 text-xs font-semibold text-[var(--color-ink-muted)] transition-all hover:text-[var(--color-ink)]">
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </button>
          <button onClick={() => setShowCreate(true)} className="flex items-center gap-2 rounded-[var(--radius-well)] bg-gradient-to-r from-[var(--color-accent-blue)] to-[var(--color-accent-cyan)] px-4 py-2 text-xs font-semibold uppercase tracking-wider text-white transition-all hover:brightness-110">
            <UserPlus className="h-4 w-4" /> New User
          </button>
        </div>
      </div>

      {actionError && (
        <div className="rounded-[var(--radius-well)] border border-[var(--color-danger)]/30 bg-[var(--color-danger)]/10 p-3 text-sm text-[var(--color-danger)]">{actionError}</div>
      )}

      <div className="glass p-5">
        <PanelLabel className="mb-5 flex items-center gap-2">
          <Users className="h-4 w-4 text-[var(--color-accent-cyan)]" /> Console Access Registry
        </PanelLabel>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-xs">
            <thead>
              <tr className="border-b border-[var(--color-hairline)] text-[var(--color-ink-faint)]">
                {["User", "Role", "Status", "Created By", "Actions"].map((h, i) => (
                  <th key={h} className={`px-4 py-3 font-semibold uppercase tracking-wider ${i === 4 ? "text-right" : ""}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-hairline)]">
              {users?.map((u) => {
                const isSelf = u.username === currentUsername;
                const busy = busyId === u.id;
                return (
                  <React.Fragment key={u.id}>
                    <tr className="transition-colors hover:bg-white/[0.02]">
                      <td className="px-4 py-4">
                        <div className="flex items-center gap-3">
                          <div className="flex h-8 w-8 items-center justify-center rounded-full border border-[var(--color-accent-cyan)]/25 bg-[var(--color-accent-cyan)]/10 text-[var(--color-accent-cyan)]">
                            <Shield className="h-4 w-4" />
                          </div>
                          <span className="font-semibold text-[var(--color-ink)]">{u.username}{isSelf && <span className="ml-2 text-[10px] text-[var(--color-ink-faint)]">(you)</span>}</span>
                        </div>
                      </td>
                      <td className="px-4 py-4">
                        <select
                          value={u.role}
                          disabled={busy || isSelf}
                          onChange={(e) => patch(u.id, { role: e.target.value }, "Could not update role.")}
                          className="rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)] px-2.5 py-1.5 text-xs text-[var(--color-ink)] disabled:opacity-50 focus:outline-none"
                        >
                          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                        </select>
                      </td>
                      <td className="px-4 py-4">
                        <Pill tone={u.is_active ? "ok" : "danger"}>{u.is_active ? "Active" : "Inactive"}</Pill>
                      </td>
                      <td className="px-4 py-4 text-[var(--color-ink-muted)]">{u.created_by ?? "—"}</td>
                      <td className="px-4 py-4">
                        <div className="flex items-center justify-end gap-1.5">
                          <IconBtn title="Reset password" onClick={() => setResetForId(resetForId === u.id ? null : u.id)} disabled={busy}>
                            <KeyRound className="h-3.5 w-3.5" />
                          </IconBtn>
                          <IconBtn title={u.is_active ? "Deactivate" : "Activate"} onClick={() => patch(u.id, { is_active: !u.is_active }, "Could not update status.")} disabled={busy || isSelf}>
                            {u.is_active ? <Ban className="h-3.5 w-3.5" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                          </IconBtn>
                          <IconBtn title="Delete" onClick={() => handleDelete(u)} disabled={busy || isSelf} danger>
                            <Trash2 className="h-3.5 w-3.5" />
                          </IconBtn>
                        </div>
                      </td>
                    </tr>
                    
                    {resetForId === u.id && (
                      <tr>
                        <td colSpan={5} className="bg-white/[0.02] px-4 py-3">
                          <div className="flex items-center gap-2">
                            <input
                              type="password" value={resetPassword} onChange={(e) => setResetPassword(e.target.value)}
                              placeholder="New password (min 6 chars)"
                              className="flex-1 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)] px-3 py-2 text-xs text-[var(--color-ink)] focus:outline-none"
                            />
                            <button onClick={() => handleResetPassword(u.id)} disabled={busy} className="rounded-[var(--radius-well)] bg-[var(--color-accent-blue)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50">Set</button>
                            <button onClick={() => { setResetForId(null); setResetPassword(""); }} className="rounded-[var(--radius-well)] border border-[var(--color-hairline)] px-3 py-2 text-xs text-[var(--color-ink-muted)]">Cancel</button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md" onClick={() => setShowCreate(false)}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={handleCreate} className="glass w-full max-w-md space-y-5 p-6">
            <div className="flex items-center justify-between">
              <PanelLabel className="flex items-center gap-2"><UserPlus className="h-4 w-4 text-[var(--color-accent-cyan)]" /> Create Console User</PanelLabel>
              <button type="button" onClick={() => setShowCreate(false)} className="text-[var(--color-ink-faint)] hover:text-[var(--color-ink)]"><X className="h-4 w-4" /></button>
            </div>
            {createError && <div className="rounded-[var(--radius-well)] border border-[var(--color-danger)]/30 bg-[var(--color-danger)]/10 p-2.5 text-xs text-[var(--color-danger)]">{createError}</div>}
            <input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} placeholder="Username" className="w-full rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)] px-3 py-2.5 text-sm text-[var(--color-ink)] focus:outline-none" />
            <input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="Password (min 6 chars)" className="w-full rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)] px-3 py-2.5 text-sm text-[var(--color-ink)] focus:outline-none" />
            <select value={newRole} onChange={(e) => setNewRole(e.target.value as ConsoleUser["role"])} className="w-full rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)] px-3 py-2.5 text-sm text-[var(--color-ink)] focus:outline-none">
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <button type="submit" disabled={creating} className="w-full rounded-[var(--radius-well)] bg-gradient-to-r from-[var(--color-accent-blue)] to-[var(--color-accent-cyan)] py-2.5 text-sm font-semibold uppercase tracking-wider text-white disabled:opacity-50">
              {creating ? "Creating…" : "Create User"}
            </button>
          </form>
        </div>
      )}

      {/* One-time MFA enrollment display */}
      {mfaEnrollment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-md">
          <div className="glass w-full max-w-md space-y-4 p-6">
            <PanelLabel className="flex items-center gap-2"><KeyRound className="h-4 w-4 text-[var(--color-accent-cyan)]" /> MFA Enrollment — {mfaEnrollment.username}</PanelLabel>
            <p className="text-xs text-[var(--color-ink-muted)]">Share this secret once. It is shown only now and cannot be retrieved again.</p>
            <div className="flex items-center gap-2 rounded-[var(--radius-well)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)] p-3">
              <code className="flex-1 break-all font-mono text-xs text-[var(--color-accent-cyan)]">{mfaEnrollment.totp_secret}</code>
              <button onClick={() => navigator.clipboard?.writeText(mfaEnrollment.totp_secret)} className="text-[var(--color-ink-faint)] hover:text-[var(--color-ink)]"><Copy className="h-4 w-4" /></button>
            </div>
            <button onClick={() => setMfaEnrollment(null)} className="w-full rounded-[var(--radius-well)] border border-[var(--color-hairline)] py-2.5 text-sm font-semibold text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]">Done</button>
          </div>
        </div>
      )}
    </div>
  );
}

function IconBtn({
  children, title, onClick, disabled, danger,
}: { children: React.ReactNode; title: string; onClick: () => void; disabled?: boolean; danger?: boolean }) {
  return (
    <button
      title={title} onClick={onClick} disabled={disabled}
      className={`rounded-[var(--radius-well)] border border-[var(--color-hairline)] p-2 transition-all disabled:cursor-not-allowed disabled:opacity-30 ${
        danger ? "text-[var(--color-ink-muted)] hover:border-[var(--color-danger)]/40 hover:text-[var(--color-danger)]" : "text-[var(--color-ink-muted)] hover:text-[var(--color-ink)]"
      }`}
    >
      {children}
    </button>
  );
}
