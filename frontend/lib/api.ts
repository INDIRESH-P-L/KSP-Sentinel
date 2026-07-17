export const API_BASE = "http://localhost:8000";

/**
 * Authenticated fetch wrapper for the KSP Sentinel API.
 *
 * Every view was attaching the stored token and then silently ignoring a
 * non-ok response -- so a stale/invalid token (e.g. left over from the
 * offline demo login fallback) made authenticated views render as
 * permanently empty with no indication why. This centralizes the header
 * attachment and, on a 401, clears the stale session and forces back to
 * the login screen instead of failing silently.
 */
export async function authFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = typeof window !== "undefined" ? localStorage.getItem("ksp_token") : null;
  const headers = new Headers(options.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401 && typeof window !== "undefined") {
    localStorage.removeItem("ksp_token");
    localStorage.removeItem("ksp_user");
    window.location.reload();
  }

  return res;
}
