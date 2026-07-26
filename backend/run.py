import os
import sys
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Path fix for Catalyst AppSail ─────────────────────────────────────────────
import site
_here = os.path.dirname(os.path.abspath(__file__))
_vendor = os.path.join(_here, "vendor")
if os.path.isdir(_vendor) and _vendor not in sys.path:
    sys.path.insert(0, _vendor)
if _here not in sys.path:
    sys.path.insert(0, _here)

# Ensure container site-packages and user site-packages are on sys.path
try:
    for sp in site.getsitepackages():
        if os.path.isdir(sp) and sp not in sys.path:
            sys.path.insert(0, sp)
    user_sp = site.getusersitepackages()
    if user_sp and os.path.isdir(user_sp) and user_sp not in sys.path:
        sys.path.insert(0, user_sp)
except Exception:
    pass

prefix_sp = os.path.join(sys.prefix, "lib", f"python{sys.version_info.major}.{sys.version_info.minor}", "site-packages")
if os.path.isdir(prefix_sp) and prefix_sp not in sys.path:
    sys.path.insert(0, prefix_sp)

for candidate_root in ["/catalyst", "/app", os.path.expanduser("~")]:
    if os.path.isdir(candidate_root):
        try:
            for root, dirs, _ in os.walk(candidate_root):
                if root.endswith("site-packages") and root not in sys.path:
                    sys.path.insert(0, root)
        except Exception:
            pass

# Set India region datacenter environment variables for Catalyst AppSail & Stratus
os.environ.setdefault("X_ZOHO_CATALYST_CONSOLE_URL", "https://console.catalyst.zoho.in")
os.environ.setdefault("X_ZOHO_CATALYST_ACCOUNTS_URL", "https://accounts.zoho.in")
os.environ.setdefault("X_ZOHO_STRATUS_RESOURCE_SUFFIX", ".zohostratus.in")
os.environ.setdefault("X_ZOHO_CATALYST_ORG_ID", "60078436924")

# Pre-flight check: Try to import the app and capture any tracebacks
startup_error = None
try:
    print("[KSP Sentinel] Pre-flight import check...", flush=True)
    import sys
    print("SYS EXECUTABLE IS:", sys.executable)
    print("SYS PATH IS:", sys.path)
    # Import the FastAPI application
    import app.main
    print("[KSP Sentinel] Pre-flight import check PASSED.", flush=True)
except Exception as e:
    startup_error = traceback.format_exc()
    print(f"[KSP Sentinel] Pre-flight import check FAILED:\n{startup_error}", flush=True)

if startup_error:
    # If it failed to import, run a diagnostic HTTP server to show the error
    class TracebackHandler(BaseHTTPRequestHandler):
        def _respond(self):
            body = f"=== KSP Sentinel Backend Startup Error ===\n\n{startup_error}".encode('utf-8')
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self): self._respond()
        def do_HEAD(self): self._respond()
        def do_POST(self): self._respond()
        def do_OPTIONS(self): self._respond()

    raw_port = os.environ.get("LISTEN_PORT") or os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT") or os.environ.get("PORT") or "9000"
    port = int(raw_port)
    print(f"[KSP Sentinel] Running diagnostic error server on port {port}...", flush=True)
    server = HTTPServer(("0.0.0.0", port), TracebackHandler)
    server.serve_forever()
else:
    # If it succeeded, start the actual FastAPI app using uvicorn
    import uvicorn
    raw_port = os.environ.get("LISTEN_PORT") or os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT") or os.environ.get("PORT") or "9000"
    port = int(raw_port)
    print(f"[KSP Sentinel] Starting production FastAPI server on port {port}...", flush=True)
    print(f"[KSP Sentinel] Env PORT keys: LISTEN_PORT={os.environ.get('LISTEN_PORT')}, X_ZOHO_CATALYST_LISTEN_PORT={os.environ.get('X_ZOHO_CATALYST_LISTEN_PORT')}, PORT={os.environ.get('PORT')}", flush=True)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False,
    )
