from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
import sys
import os

# Set paths
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from app.config import settings
from app.logging import logger
from app.core.rate_limit import limiter, check_global_rate_limit
from app.core.brute_force import is_banned

# Import API routers
from app.api import auth, dashboard, crimes, districts, forecast, network, chatbot, export, reviews, users, admin_seed

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
origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()]
if not origins or "*" in origins:
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
    allow_origin_regex=r"https://.*\.onslate\.in|https://.*\.catalystserverless\.in|http://localhost:.*|http://127\.0\.0\.1:.*",
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.middleware("http")
async def security_headers_and_ban_check(request: Request, call_next):
    # A banned IP (backend/app/core/brute_force.py) is rejected before it reaches any
    # route, including ones without an explicit rate limit.
    client_ip = request.client.host if request.client else "unknown"
    if is_banned(client_ip):
        return JSONResponse(
            status_code=403,
            content={"detail": "This IP address is temporarily blocked due to repeated failed login attempts."},
        )

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

@app.get("/")
def read_root():
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
    # Run migration in a separate thread so the request can complete
    def migrate_task():
        try:
            run_migration(request)
        except Exception as e:
            logger.error(f"Migration error: {e}")
    threading.Thread(target=migrate_task).start()
    return {"message": "Migration started in background"}

@app.on_event("startup")
def startup_event():
    logger.info("KSP Sentinel FastAPI backend starting up...")
    _seed_default_admin()
    try:
        from app import filestore_crime_data
        logger.info("Pre-warming crime dataset in memory...")
        filestore_crime_data.ensure_loaded()
        logger.info("Crime dataset pre-warmed successfully.")
    except Exception as err:
        logger.error(f"Failed to pre-warm crime dataset on startup: {err}")

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
