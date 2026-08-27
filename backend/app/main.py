from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
import sys
import os
from pathlib import Path

# Set paths
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from app.config import settings
from app.logging import logger
from app.core.rate_limit import limiter, check_global_rate_limit
from app.core.brute_force import is_banned

# Import API routers
from app.api import auth, dashboard, crimes, districts, forecast, network, chatbot, export, reviews, users, admin_seed, grok_insights, chatbot_grok
# Investigation Intelligence additions (see NEW_FEATURES.md) -- additive routers only.
from app.api import intelligence, evidence, nudges, safety, patrol, public, complainant

app = FastAPI(
    title="KSP Sentinel API",
    description="AI-Powered Crime Intelligence & Predictive Analytics Platform for Karnataka Police",
    version="1.0.0"
)

# Global rate limiting (100/min per IP by default; individual routes tighten this
# further with their own @limiter.limit(...) -- see auth.py, chatbot.py).
app.state.limiter = limiter
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Too many requests. Slow down and try again shortly."})

# CORS configuration
origins = [
    "https://ksp-sentinel.onslate.in",
    "https://ksp-sentinel-60078436924.development.catalystserverless.in",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.zohocatalyst\.in|https://.*\.onslate\.in|https://.*\.catalystserverless\.in|http://localhost:.*|http://127\.0\.0\.1:.*|http://192\.168\..*|http://10\..*|http://172\..*",
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.middleware("http")
async def security_headers_and_ban_check(request: Request, call_next):
    origin = request.headers.get("origin", "")
    if request.method == "OPTIONS":
        response = JSONResponse(status_code=200, content={"status": "ok"})
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Accept, Origin, User-Agent, X-Requested-With"
        else:
            response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    client_ip = request.client.host if request.client else "unknown"
    if is_banned(client_ip):
        return JSONResponse(
            status_code=403,
            content={"detail": "This IP address is temporarily blocked due to repeated failed login attempts."},
        )

    response = await call_next(request)
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Accept, Origin, User-Agent, X-Requested-With"
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    return response

    # Global 100/min-per-IP cap. See core/rate_limit.py's module docstring for why
    # this is a manual check rather than slowapi's default_limits+middleware combo.
    if not check_global_rate_limit(client_ip):
        return JSONResponse(status_code=429, content={"detail": "Too many requests. Slow down and try again shortly."})

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

_BACKEND_DIR = Path(__file__).parent.parent  # backend/
_STATIC_DIR = _BACKEND_DIR / "static"
FRONTEND_DIR = str(_STATIC_DIR) if _STATIC_DIR.is_dir() else os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "out"))

# Mount API routers
app.include_router(auth.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(crimes.router, prefix="/api")
app.include_router(districts.router, prefix="/api")
app.include_router(forecast.router, prefix="/api")
app.include_router(network.router, prefix="/api")
app.include_router(chatbot.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(admin_seed.router, prefix="/api")
app.include_router(grok_insights.router, prefix="/api")
app.include_router(chatbot_grok.router, prefix="/api")
app.include_router(intelligence.router, prefix="/api")
app.include_router(evidence.router, prefix="/api")
app.include_router(nudges.router, prefix="/api")
app.include_router(safety.router, prefix="/api")
app.include_router(patrol.router, prefix="/api")
app.include_router(public.router, prefix="/api")
app.include_router(complainant.router, prefix="/api")

@app.get("/")
def read_root(request: Request):
    """Root. Content-negotiated so one URL serves both audiences."""
    accepts_html = "text/html" in (request.headers.get("accept") or "")
    if accepts_html:
        index = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.isfile(index):
            return FileResponse(index)

    return {
        "status": "online",
        "service": "KSP-Sentinel-API",
        "engine": "FastAPI",
        "region": "Karnataka, IN"
    }

@app.get("/migrate")
def trigger_migration(request: Request):
    from app.migration.migrate import run_migration
    import threading
    def migrate_task():
        try:
            run_migration(request)
        except Exception as e:
            logger.error(f"Migration error: {e}")
    threading.Thread(target=migrate_task).start()
    return {"message": "Migration started in background"}

# ─────────────────────────────────────────────────────────────────────────────
# Single-origin serving: the built frontend is served from this same app, so the
# whole product lives on one URL and the browser makes same-origin API calls (no
# CORS round-trip, no second port to run).
#
# Registered AFTER every router on purpose. FastAPI matches in registration order,
# so /api/*, /docs and /openapi.json are all claimed before this catch-all is
# consulted -- it can only ever pick up what nothing else wanted.
#
# Entirely optional: if frontend/out does not exist (nobody has run `npm run build`),
# none of this mounts and the API behaves exactly as before.
# ─────────────────────────────────────────────────────────────────────────────

if os.path.isdir(FRONTEND_DIR):
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    _next_assets = os.path.join(FRONTEND_DIR, "_next")
    if os.path.isdir(_next_assets):
        app.mount("/_next", StaticFiles(directory=_next_assets), name="next-assets")

    def _resolve_static(path: str) -> str | None:
        """Map a URL path to a file in the export, refusing anything outside it.

        `next build` with output:"export" emits `preview.html` and `public/safety.html`
        rather than `preview/index.html`, so the `.html` suffix is tried first; the
        directory form is kept as a fallback in case that layout changes.
        """
        clean = (path or "").strip("/")
        candidates = ["index.html"] if not clean else [
            f"{clean}.html",
            os.path.join(clean, "index.html"),
            clean,
        ]
        for candidate in candidates:
            full = os.path.abspath(os.path.join(FRONTEND_DIR, candidate))
            # Path-traversal guard: a crafted "../.." must not escape the export.
            if not full.startswith(FRONTEND_DIR + os.sep) and full != FRONTEND_DIR:
                continue
            if os.path.isfile(full):
                return full
        return None

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        """Serves the built UI. Never answers for /api -- that 404s as an API route
        would, rather than handing an HTML page to something expecting JSON."""
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        found = _resolve_static(full_path)
        if found:
            return FileResponse(found)

        not_found = os.path.join(FRONTEND_DIR, "404.html")
        if os.path.isfile(not_found):
            return FileResponse(not_found, status_code=404)
        raise HTTPException(status_code=404, detail="Not Found")

    logger.info(f"Serving built frontend from {FRONTEND_DIR} at / (single-origin mode).")
else:
    logger.info("frontend/out not found -- API-only mode. Run `npm run build` in frontend/ to serve the UI here.")


@app.on_event("startup")
def startup_event():
    logger.info("KSP Sentinel FastAPI backend starting up...")
    _seed_default_admin()
    import threading
    def background_preload():
        try:
            from app import filestore_crime_data
            logger.info("Pre-warming crime dataset in memory in background...")
            filestore_crime_data.ensure_loaded()
            logger.info("Crime dataset pre-warmed successfully.")
        except Exception as err:
            logger.error(f"Failed to pre-warm crime dataset in background: {err}")
    threading.Thread(target=background_preload, daemon=True).start()

@app.get("/migrate")
async def trigger_migration():
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "migration"))
    import migrate
    import threading
    threading.Thread(target=migrate.run_migration).start()
    return {"status": "Migration started"}

def _seed_default_admin():
    """Ensures at least one Admin account exists so the admin console is reachable
    on a fresh database. Non-destructive: create_all only adds the `users` table if
    it doesn't already exist (same pattern as scripts/migrate_intelligence_layer.py),
    and this only inserts a row when no Admin account is present yet."""
    from app.database.session import SessionLocal, engine
    from app.database.models import Base, User
    from app.dependencies import hash_password
    from app.core import mfa

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if not db.query(User).filter(User.role == "Admin").first():
            plaintext_secret = mfa.generate_totp_secret()
            db.add(User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="Admin",
                is_active=True,
                created_by="system",
                totp_secret=mfa.encrypt_secret(plaintext_secret),
                mfa_enabled=True,
            ))
            db.commit()
            logger.warning(
                "Seeded default admin account (username='admin', password='admin123'). "
                "MFA is enabled -- enroll this TOTP secret in an authenticator app "
                f"before logging in: {plaintext_secret} "
                f"(otpauth URI: {mfa.provisioning_uri(plaintext_secret, 'admin')}). "
                "Change the password and re-enroll MFA immediately in any real deployment."
            )
    finally:
        db.close()
