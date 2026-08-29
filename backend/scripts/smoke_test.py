"""End-to-end smoke test against a running KSP Sentinel API.

Checks the things that were actually broken in production, so a regression in any of
them fails loudly instead of degrading silently:

  * every operational route refuses an anonymous caller (they were all readable
    without a token, because get_current_user fabricated an identity)
  * the removed bypasses stay removed (demo_token, the legacy demo passwords)
  * genuinely public routes still answer
  * security response headers are present (they were unreachable dead code)
  * .env-driven credentials actually loaded (they were read from a path that did
    not exist, so every API key was empty)
  * an authenticated session can read data, and the AI Copilot returns a real answer
  * Case Readiness scores every open case, and Serial Runs never issues a forecast
    below its confidence floor (that guardrail is what makes the output trustworthy)

Usage:
    cd backend
    python scripts/smoke_test.py --base http://127.0.0.1:8000 \
        --username qa_super --password 'QaVerify!2026'

Exits non-zero if any check fails, so it is usable as a CI gate.
"""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

PROTECTED_GET = [
    "/api/dashboard/kpis",
    "/api/dashboard/anomalies",
    "/api/dashboard/top-districts",
    "/api/districts/",
    "/api/districts/stations",
    "/api/districts/rankings",
    "/api/crimes/",
    "/api/network/",
    "/api/reviews",
    "/api/nudges",
    "/api/intelligence/series",
    "/api/crimes/readiness/queue",
]
PROTECTED_POST = [
    ("/api/grok/chatbot-query", {"message": "hello"}),
    ("/api/intelligence/check-duplicate", {"description": "a test description here"}),
]
PUBLIC_GET = ["/api/health", "/api/public/district-safety"]
SECURITY_HEADERS = [
    "X-Content-Type-Options", "X-Frame-Options",
    "Referrer-Policy", "Permissions-Policy",
]


class Runner:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.failures: list[str] = []
        self.passes = 0

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        if ok:
            self.passes += 1
            print(f"  PASS  {label}")
        else:
            self.failures.append(f"{label} — {detail}")
            print(f"  FAIL  {label}  ({detail})")
        return ok

    def request(self, path: str, method="GET", token=None, body=None, form=None,
                timeout=90):
        url = f"{self.base}{path}"
        data, headers = None, {}
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)
        except Exception as e:  # noqa: BLE001 — a connection failure is a test result
            return 0, str(e).encode(), {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--username", help="Account for the authenticated checks.")
    ap.add_argument("--password")
    ap.add_argument("--skip-ai", action="store_true",
                    help="Skip the live LLM call (it costs a provider request).")
    args = ap.parse_args()

    r = Runner(args.base)

    print(f"\nKSP Sentinel smoke test — {r.base}\n")

    print("[1] Anonymous access is refused on operational routes")
    for path in PROTECTED_GET:
        status, _, _ = r.request(path)
        r.check(status == 401, f"401 for anonymous GET {path}", f"got {status}")
    for path, body in PROTECTED_POST:
        status, _, _ = r.request(path, "POST", body=body)
        r.check(status == 401, f"401 for anonymous POST {path}", f"got {status}")

    print("\n[2] Removed bypasses stay removed")
    status, _, _ = r.request("/api/dashboard/kpis", token="demo_token")
    r.check(status == 401, "demo_token is rejected", f"got {status}")
    for user, pw in [("sp_admin", "password"), ("keshav", "ksp123"), ("x", "admin")]:
        status, _, _ = r.request("/api/auth/login", "POST", form={"username": user, "password": pw})
        r.check(status == 401, f"legacy login {user}/{pw} refused", f"got {status}")

    print("\n[3] Public routes still answer")
    for path in PUBLIC_GET:
        status, _, _ = r.request(path)
        r.check(status == 200, f"200 for public {path}", f"got {status}")

    print("\n[4] Security headers are applied")
    _, _, headers = r.request("/api/health")
    lower = {k.lower(): v for k, v in headers.items()}
    for h in SECURITY_HEADERS:
        r.check(h.lower() in lower, f"{h} present", "missing")

    print("\n[5] Configuration actually loaded")
    status, raw, _ = r.request("/api/health")
    health = json.loads(raw) if status == 200 else {}
    cfg = health.get("config", {})
    r.check(cfg.get("env_file_found") is True, ".env file discovered",
            f"looked at {cfg.get('env_file')}")
    r.check(cfg.get("secret_key", {}).get("configured") is True, "SECRET_KEY configured")
    r.check(cfg.get("totp_encryption_key", {}).get("configured") is True,
            "TOTP_ENCRYPTION_KEY configured (else MFA breaks every restart)")
    r.check(health.get("database", {}).get("reachable") is True, "database reachable")

    if not args.username:
        print("\n[6] Authenticated checks SKIPPED (pass --username/--password)")
    else:
        print("\n[6] Authenticated session")
        status, raw, _ = r.request("/api/auth/login", "POST",
                                   form={"username": args.username, "password": args.password})
        ok = r.check(status == 200, "login succeeds", f"got {status}: {raw[:160]!r}")
        token = json.loads(raw).get("access_token") if ok else None
        if token:
            for path in ["/api/dashboard/kpis", "/api/districts/", "/api/crimes/?limit=2",
                         "/api/network/", "/api/nudges"]:
                status, _, _ = r.request(path, token=token)
                r.check(status == 200, f"200 for authenticated {path}", f"got {status}")

            print('\n[7] Case Readiness and Serial Runs return usable analysis')
            status, raw, _ = r.request("/api/crimes/readiness/queue?limit=5", token=token)
            if status == 200:
                q = json.loads(raw)
                r.check(isinstance(q.get("cases"), list), "readiness queue returns cases")
                if q.get("cases"):
                    c = q["cases"][0]
                    r.check(isinstance(c.get("readiness_score"), (int, float)),
                            "readiness score is numeric", f"got {c.get('readiness_score')!r}")
                    r.check(c.get("band") in ("ready", "nearly_ready", "gaps", "blocked"),
                            "readiness band is one of the four", f"got {c.get('band')!r}")
            else:
                r.check(False, "readiness queue responded 200", f"got {status}")

            status, raw, _ = r.request("/api/intelligence/series", token=token)
            if status == 200:
                sr = json.loads(raw)
                r.check(isinstance(sr.get("series"), list), "series analysis returns a list")
                r.check(bool(sr.get("advisory")), "series response carries its advisory")
                forecast_series = [x for x in sr.get("series", []) if x.get("forecast")]
                for x in sr.get("series", []):
                    # A forecast must never be issued below the confidence floor -- that
                    # guardrail is the whole basis for trusting the output.
                    if x.get("forecast"):
                        r.check(x["confidence"] >= 0.35,
                                f"{x['series_id']}: forecast only above the confidence floor",
                                f"confidence {x['confidence']}")
                    else:
                        r.check(bool(x.get("forecast_withheld_reason")),
                                f"{x['series_id']}: withheld forecast states a reason")
                if forecast_series:
                    f = forecast_series[0]["forecast"]
                    r.check(f.get("window_start") != f.get("window_end"),
                            "forecast is a window, never a single instant")
                    r.check((f.get("search_radius_km") or 0) >= 1.0,
                            "forecast search radius is never sub-kilometre")
            else:
                r.check(False, "series analysis responded 200", f"got {status}")

            if not args.skip_ai:
                print("\n[7] AI Copilot answers with a real completion")
                status, raw, _ = r.request(
                    "/api/grok/chatbot-query", "POST", token=token,
                    body={"message": "In one short sentence, what is this dataset about?"},
                )
                if status == 200:
                    reply = (json.loads(raw) or {}).get("reply") or ""
                    r.check(len(reply.strip()) > 10, "Copilot returned a non-empty answer",
                            f"reply={reply[:80]!r}")
                else:
                    r.check(False, "Copilot responded 200", f"got {status}: {raw[:200]!r}")

    print("\n" + "=" * 68)
    if r.failures:
        print(f"  {r.passes} passed, {len(r.failures)} FAILED")
        for f in r.failures:
            print(f"    - {f}")
        print("=" * 68)
        return 1
    print(f"  ALL {r.passes} CHECKS PASSED")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
