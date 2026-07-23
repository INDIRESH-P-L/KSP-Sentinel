import os
import sys
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── Path fix for Catalyst AppSail ─────────────────────────────────────────────
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)
_dependencies = os.path.join(_here, "lib")
if os.path.isdir(_dependencies) and _dependencies not in sys.path:
    sys.path.append(_dependencies)

# Pre-flight check: Try to import the app and capture any tracebacks
startup_error = None
try:
    print("[KSP Sentinel] Pre-flight import check...", flush=True)
    # Import the FastAPI application
    import app.main
    print("[KSP Sentinel] Pre-flight import check PASSED.", flush=True)
except Exception as e:
    startup_error = traceback.format_exc()
    print(f"[KSP Sentinel] Pre-flight import check FAILED:\n{startup_error}", flush=True)

if startup_error:
    # If it failed to import, run a diagnostic HTTP server to show the error
    class TracebackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = f"=== KSP Sentinel Backend Startup Error ===\n\n{startup_error}".encode('utf-8')
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    port = int(os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT", 9000))
    print(f"[KSP Sentinel] Running diagnostic error server on port {port}...", flush=True)
    server = HTTPServer(("0.0.0.0", port), TracebackHandler)
    server.serve_forever()
else:
    # If it succeeded, start the actual FastAPI app using uvicorn
    import uvicorn
    port = int(os.environ.get("X_ZOHO_CATALYST_LISTEN_PORT", 9000))
    print(f"[KSP Sentinel] Starting production FastAPI server on port {port}...", flush=True)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False,
    )
