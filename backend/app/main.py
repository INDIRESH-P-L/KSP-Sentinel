"""KSP Sentinel API — application assembly, middleware and static-frontend serving."""
import os
import re
import secrets
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

# Set paths
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from app.config import settings
from app.logging import logger
from app.core.rate_limit import limiter, check_global_rate_limit
from app.core.brute_force import is_banned
from app.dependencies import get_current_admin

# Import API routers
from app.api import (
    auth, dashboard, crimes, districts, forecast, network, chatbot, export,
    reviews, users, admin_seed, grok_insights, chatbot_grok,
)
# Investigation Intelligence additions (see NEW_FEATURES.md) -- additive routers only.
from app.api import intelligence, evidence, nudges, safety, patrol, public, complainant


# ─────────────────────────────────────────────────────────────────────────────
# CORS
#
# The allow-list is explicit. The previous configuration combined `allow_origins`
# with a very broad `allow_origin_regex` AND a hand-rolled middleware that
# reflected ANY inbound Origin back with `Access-Control-Allow-Credentials: true`,
# falling back to `*` when no Origin was sent. Reflecting an arbitrary origin with
# credentials lets any website a signed-in officer visits read this API as that
# officer; `*` together with credentials is rejected outright by browsers, so it
# also did not do what it appeared to do.
#
# The reflection behaviour existed for a real reason -- the Zoho ZGS edge layer
# intercepts OPTIONS preflights and strips CORS headers before they reach FastAPI
# -- so it is kept, but only for origins that actually match the allow-list.
# ─────────────────────────────────────────────────────────────────────────────
_STATIC_ORIGINS = [
    "https://ksp-sentinel.onslate.in",
    "https://ksp-sentinel-60078436924.development.catalystserverless.in",
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]

# Deployment can extend the list without a code change: ALLOWED_ORIGINS=a,b,c
_CONFIGURED = [
    o.strip() for o in (settings.ALLOWED_ORIGINS or "").split(",")
    if o.strip() and o.strip() != "*"
]
ALLOWED_ORIGINS = list(dict.fromkeys(_STATIC_ORIGINS + _CONFIGURED))

# Catalyst/Zoho deployment hosts and LAN development machines. Note this no longer
# matches arbitrary schemes or hosts the way the old `http://localhost:.*` and
# `http://10\..*` fragments did.
ALLOWED_ORIGIN_REGEX = re.compile(
    r"^https://[A-Za-z0-9.\-]+\.(zohocatalyst\.in|onslate\.in|catalystserverless\.in)$"
    r"|^http://(localhost|127\.0\.0\.1)(:\d+)?$"
    r"|^http://(192\.168\.\d{1,3}\.\d{1,3}"
    r"|10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})(:\d+)?$"
)


def is_allowed_origin(origin: str) -> bool:
    """True only for an origin on the allow-list or matching the deployment regex."""
    if not origin:
        return False
    return origin in ALLOWED_ORIGINS or bool(ALLOWED_ORIGIN_REGEX.match(origin))


_BACKEND_DIR = Path(__file__).parent.parent  # backend/
_STATIC_DIR = _BACKEND_DIR / "static"
FRONTEND_DIR = str(_STATIC_DIR) if _STATIC_DIR.is_dir() else os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "out")
)


def _seed_default_admin() -> None:
    """Ensures one Admin account exists so the console is reachable on a fresh DB.

    Non-destructive: `create_all` only adds missing tables, and a row is inserted
    only when no Admin is present. The password is randomly generated per
    deployment and printed exactly once -- it used to be the literal string
    "admin123", which shipped as a known credential on every install.
    """
    from app.database.session import SessionLocal, engine
    from app.database.models import Base, User
    from app.dependencies import hash_password
    from app.core import mfa

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if db.query(User).filter(User.role == "Admin").first():
            return

        password = secrets.token_urlsafe(18)
        plaintext_secret = mfa.generate_totp_secret()
        db.add(User(
            username="admin",
            password_hash=hash_password(password),
            role="Admin",
            is_active=True,
            created_by="system",
            totp_secret=mfa.encrypt_secret(plaintext_secret),
            mfa_enabled=True,
        ))
        db.commit()
        logger.warning(
            "\n"
            "==================== KSP SENTINEL - FIRST-RUN ADMIN ====================\n"
            "  username : admin\n"
            "  password : %s\n"
            "  TOTP     : %s\n"
            "  otpauth  : %s\n"
            "\n"
            "  Shown ONCE. Enroll the TOTP secret in an authenticator app now and\n"
            "  change the password after first sign-in. This account cannot read\n"
            "  crime data (separation of duties) -- create operational accounts\n"
            "  from the admin console.\n"
            "=======================================================================",
            password, plaintext_secret, mfa.provisioning_uri(plaintext_secret, "admin"),
        )
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown. Replaces the deprecated @app.on_event("startup") hook,
    which FastAPI removes in a future major."""
    logger.info("KSP Sentinel FastAPI backend starting up...")
    _seed_default_admin()

    def background_preload():
        try:
            from app import filestore_crime_data
            logger.info("Pre-warming crime dataset in memory in background...")
            filestore_crime_data.ensure_loaded()
            logger.info("Crime dataset pre-warmed successfully.")
        except Exception as err:
            logger.error(f"Failed to pre-warm crime dataset in background: {err}")

    threading.Thread(target=background_preload, daemon=True).start()
    yield
    logger.info("KSP Sentinel FastAPI backend shutting down.")


app = FastAPI(
    title="KSP Sentinel API",
    description="AI-Powered Crime Intelligence & Predictive Analytics Platform for Karnataka Police",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Slow down and try again shortly."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX.pattern,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin",
                   "User-Agent", "X-Requested-With"],
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


@app.middleware("http")
async def security_headers_and_ban_check(request: Request, call_next):
    """IP ban check, global rate limit, and security response headers.

    The previous version returned the response immediately after stamping CORS
    headers, leaving everything below that point -- the global rate limit AND all
    four security headers -- as unreachable dead code. None of it was applied to a
    single response in production.
    """
    origin = request.headers.get("origin", "")
    origin_ok = is_allowed_origin(origin)

    client_ip = request.client.host if request.client else "unknown"
    if is_banned(client_ip):
        return JSONResponse(
            status_code=403,
            content={"detail": "This IP address is temporarily blocked due to "
                               "repeated failed login attempts."},
        )

    # Global per-IP cap. Individual routes tighten this further with their own
    # @limiter.limit(...) -- see auth.py and chatbot.py.
    if not check_global_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Slow down and try again shortly."},
        )

    response = await call_next(request)

    for header, value in SECURITY_HEADERS.items():
        response.headers[header] = value

    # Re-assert CORS for allow-listed origins only. Needed because the Zoho ZGS
    # edge layer can strip CORSMiddleware's headers in front of this app.
    if origin_ok:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"

    return response


# Mount API routers
for _router_module in (
    auth, dashboard, crimes, districts, forecast, network, chatbot, export, reviews,
    users, admin_seed, grok_insights, chatbot_grok, intelligence, evidence, nudges,
    safety, patrol, public, complainant,
):
    app.include_router(_router_module.router, prefix="/api")


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
        "region": "Karnataka, IN",
    }


@app.get("/api/health", tags=["Health"])
def health():
    """Liveness + configuration probe.

    Reports which integrations are actually wired, so a misconfigured deployment is
    visible without reading logs. Never returns a secret -- only whether one is
    present. This exists because the single most damaging class of bug in this
    codebase was silent misconfiguration (an unloaded .env meant every LLM call
    failed and every MFA secret was re-keyed on boot, with nothing surfacing it).
    """
    from app.integrations_status import integration_status
    return integration_status()


@app.post("/api/migrate", tags=["Admin"])
def trigger_migration(current_user: dict = Depends(get_current_admin)):
    """Kicks off the Catalyst datastore migration in a background thread.

    Was previously registered TWICE as an unauthenticated GET (two separate
    `@app.get("/migrate")` declarations in this file), which produced a duplicate
    OpenAPI operation id and let any anonymous caller start a migration. One route,
    admin-only, and a POST because it mutates.
    """
    from app.migration.migrate import run_migration

    def migrate_task():
        try:
            run_migration()
        except Exception as e:
            logger.error(f"Migration error: {e}")

    threading.Thread(target=migrate_task, daemon=True).start()
    logger.warning("Datastore migration started by admin '%s'.", current_user.get("username"))
    return {"status": "Migration started in background"}


# ─────────────────────────────────────────────────────────────────────────────
# Single-origin serving: the built frontend is served from this same app, so the
# whole product lives on one URL and the browser makes same-origin API calls.
#
# Registered AFTER every router on purpose. FastAPI matches in registration order,
# so /api/*, /docs and /openapi.json are all claimed before this catch-all is
# consulted -- it can only ever pick up what nothing else wanted.
# ─────────────────────────────────────────────────────────────────────────────
if os.path.isdir(FRONTEND_DIR):
    _next_assets = os.path.join(FRONTEND_DIR, "_next")
    if os.path.isdir(_next_assets):
        app.mount("/_next", StaticFiles(directory=_next_assets), name="next-assets")

    def _resolve_static(path: str) -> str | None:
        """Maps a URL path to a file in the export, refusing anything outside it.

        `next build` with output:"export" emits `preview.html` and
        `public/safety.html` rather than `preview/index.html`, so the `.html` suffix
        is tried first; the directory form is kept as a fallback.
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
    logger.info("frontend export not found -- API-only mode. "
                "Run `npm run build` in frontend/ to serve the UI here.")
