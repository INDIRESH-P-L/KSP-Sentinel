import type { Anomaly } from "@/lib/types";

const DEFAULT_LOCAL_API_BASE = "http://localhost:8000";
// When the frontend is served FROM AppSail (same origin as API), use relative
// paths — this eliminates CORS entirely. No Authorization header, no preflight,
// no ZGS interception issues.
const DEFAULT_DEPLOYED_API_BASE = "";

export const API_BASE = (() => {
  const envBase = process.env.NEXT_PUBLIC_API_BASE?.trim();
  if (envBase) {
    return envBase.replace(/\/$/, "");
  }

  if (typeof window === "undefined") {
    return DEFAULT_LOCAL_API_BASE;
  }

  const hostname = window.location.hostname;
  if (
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    hostname.startsWith("192.168.") ||
    hostname.startsWith("10.") ||
    hostname.startsWith("172.")
  ) {
    return "";
  }

  return DEFAULT_DEPLOYED_API_BASE;
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

/**
 * Map `/api/dashboard/anomalies` onto the `Anomaly` shape the views render.
 *
 * The endpoint returns `district_name`/`description`, not `district`/`message`,
 * so reading the latter straight off the response renders a feed of blank rows.
 * Two views consume this endpoint, hence normalising here rather than at each
 * call site.
 */
export function normalizeAnomalies(rows: unknown): Anomaly[] {
  if (!Array.isArray(rows)) return [];
  return rows.map((r) => {
    const row = r as Record<string, unknown>;
    return {
      district: String(row.district ?? row.district_name ?? "Unknown district"),
      message: String(row.message ?? row.description ?? ""),
      z_score: Number(row.z_score ?? 0),
      severity: row.severity as Anomaly["severity"],
    };
  });
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

  // Only attach real JWTs — never "demo_token".
  // The Zoho ZGS edge layer intercepts OPTIONS preflights and strips CORS headers
  // before they reach FastAPI. Any request with an Authorization header triggers
  // a preflight, so demo sessions intentionally omit the header; the backend
  // already returns a default user when no token is present.
  if (token && token !== "demo_token") {
    headers.set("Authorization", `Bearer ${token}`);
  }

  console.log("FETCHING:", `${API_BASE}${path}`);
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401 && typeof window !== "undefined") {
    if (token === "demo_token") {
      return res;
    }
    if (!_isRetry) {
      const refreshed = await refreshSession();
      if (refreshed) {
        return authFetch(path, options, true);
      }
    }
    clearSessionAndReload();
  }

  return res;
}

/**
 * CORS-safe fetch for public, non-sensitive aggregated endpoints.
 *
 * Sends NO Authorization header, which means the browser issues a simple
 * GET request (no preflight). Use this for dashboard KPIs, trends, district
 * rankings, and other aggregated views that contain no PII.
 */
export async function publicFetch(path: string, options: RequestInit = {}): Promise<Response> {
  return fetch(`${API_BASE}${path}`, options);
}

