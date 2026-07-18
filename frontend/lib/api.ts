export const API_BASE = (() => {
  if (typeof window === "undefined") {
    return "http://localhost:8000";
  }
  const hostname = window.location.hostname;
  if (hostname === "localhost" || hostname === "127.0.0.1" || hostname.startsWith("192.168.") || hostname.startsWith("10.")) {
    return "http://localhost:8000";
  }
  return "https://ksp-sentinel-backend-50044046242.development.catalystappsail.in";
})();

/**
 * Authenticated fetch wrapper for the KSP Sentinel API.
 *
 * Every view was attaching the stored token and then silently ignoring a
 * non-ok response -- so a stale/invalid token (e.g. left over from the
 * offline demo login fallback) made authenticated views render as
 * permanently empty with no indication why. This centralizes the header
 * attachment and, on a 401, tries a silent refresh before giving up.
 *
 * Access tokens are short-lived for MFA-enrolled accounts (15 min), so a
 * silent refresh-then-retry is what keeps a session usable across normal use
 * instead of bouncing back to the login screen every 15 minutes.
 */

let refreshPromise: Promise<boolean> | null = null;

/** Multiple requests can 401 around the same moment (several views fetch in
 * parallel). Refresh tokens are single-use/rotating server-side, so if each
 * caller raced to refresh independently, only the first would succeed and
 * the rest would invalidate each other. Sharing one in-flight promise makes
 * concurrent 401s coalesce into a single refresh call. */
function refreshSession(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const refreshToken = typeof window !== "undefined" ? localStorage.getItem("ksp_refresh_token") : null;
    if (!refreshToken) return false;

    try {
      const res = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!res.ok) return false;

      const data = await res.json();
      localStorage.setItem("ksp_token", data.access_token);
      localStorage.setItem("ksp_refresh_token", data.refresh_token);
      localStorage.setItem("ksp_user", JSON.stringify(data.user));
      return true;
    } catch {
      return false;
    }
  })().finally(() => {
    refreshPromise = null;
  });

  return refreshPromise;
}

function clearSessionAndReload() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("ksp_token");
  localStorage.removeItem("ksp_refresh_token");
  localStorage.removeItem("ksp_user");
  window.location.reload();
}

export async function authFetch(path: string, options: RequestInit = {}, _isRetry = false): Promise<Response> {
  const token = typeof window !== "undefined" ? localStorage.getItem("ksp_token") : null;
  const headers = new Headers(options.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401 && typeof window !== "undefined") {
    if (!_isRetry) {
      const refreshed = await refreshSession();
      if (refreshed) {
        return authFetch(path, options, true);
      }
    }
    // No refresh token, or the refresh itself failed (expired/revoked) -- the
    // session is genuinely over, so clear it instead of leaving views stuck
    // silently empty against a token that will never work again.
    clearSessionAndReload();
  }

  return res;
}
