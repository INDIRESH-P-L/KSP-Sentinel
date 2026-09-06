import os
import site
import sys
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Path fix for Catalyst AppSail ─────────────────────────────────────────────
# The AppSail python_3_11 stack does not always expose the packages it installed on
# a plain `python run.py`, so the interpreter's own environment is re-asserted here
# and backend/vendor/ (pre-built manylinux wheels) stands in for anything missing.
#
# Order is deliberate: real environment first, then backend/ so `app.*` resolves,
# then vendor LAST. Vendor is a fallback, not an override -- ahead of the live
# environment it would shadow whatever the platform actually installed, and it
# breaks a non-Linux dev machine outright since those wheels ship Linux .so files.
#
# There used to be an unpruned `os.walk` over /catalyst, /app AND $HOME here that
# front-inserted every directory ending in "site-packages". It descended
# node_modules and the dataset trees on every boot (seconds to minutes of cold
# start, enough to trip the AppSail start timeout) and could hoist a stale
# site-packages found deep in the tree ahead of the pinned versions. The candidate
# list below is explicit and bounded: a handful of isdir() calls, no recursion.
_here = os.path.dirname(os.path.abspath(__file__))
_vendor = os.path.join(_here, "vendor")
_pyver = f"python{sys.version_info.major}.{sys.version_info.minor}"

_env_candidates = []
try:
    _env_candidates.extend(site.getsitepackages())
    _env_candidates.append(site.getusersitepackages())
except Exception:
    # site can be crippled in an isolated/embedded interpreter; the explicit
    # candidates below still cover the container layouts we care about.
    pass

_env_candidates.append(os.path.join(sys.prefix, "lib", _pyver, "site-packages"))
for _root in ("/catalyst", "/app"):
    for _venv in ("", ".venv", "venv"):
        _env_candidates.append(os.path.join(_root, _venv, "lib", _pyver, "site-packages"))

for _candidate in _env_candidates:
    if _candidate and os.path.isdir(_candidate) and _candidate not in sys.path:
        sys.path.append(_candidate)

_vendor_found = os.path.isdir(_vendor)
if _vendor_found and _vendor not in sys.path:
    sys.path.append(_vendor)
if _here in sys.path:
    sys.path.remove(_here)
sys.path.insert(0, _here)

# Set India region datacenter environment variables for Catalyst AppSail & Stratus
os.environ.setdefault("X_ZOHO_CATALYST_CONSOLE_URL", "https://console.catalyst.zoho.in")
os.environ.setdefault("X_ZOHO_CATALYST_ACCOUNTS_URL", "https://accounts.zoho.in")
os.environ.setdefault("X_ZOHO_STRATUS_RESOURCE_SUFFIX", ".zohostratus.in")
os.environ.setdefault("X_ZOHO_CATALYST_ORG_ID", "60078436924")

# Pre-flight check: Try to import the app and capture any tracebacks
startup_error = None
try:
    # One boot line an operator can act on. Dumping the whole of sys.path on every
    # start buried the useful lines in the AppSail log.
    print(f"[KSP Sentinel] Pre-flight import check: interpreter={sys.executable} "
          f"vendor={'found' if _vendor_found else 'MISSING'}", flush=True)
    # Import the FastAPI application
    import app.main
    print("[KSP Sentinel] Pre-flight import check PASSED.", flush=True)
except Exception as e:
    startup_error = traceback.format_exc()
    print(f"[KSP Sentinel] Pre-flight import check FAILED:\n{startup_error}", flush=True)
    print(f"[KSP Sentinel] sys.path was: {sys.path}", flush=True)

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
