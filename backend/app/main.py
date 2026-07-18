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
from app.api import auth, dashboard, crimes, districts, forecast, network, chatbot, export, reviews, users

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
origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "KSP-Sentinel-API",
        "engine": "FastAPI",
        "region": "Karnataka, IN"
    }

@app.on_event("startup")
def startup_event():
    logger.info("KSP Sentinel FastAPI backend starting up...")
    _seed_default_admin()

def _seed_default_admin():
    """Ensures at least one Admin account exists so the admin console is reachable
    on a fresh database. Non-destructive: create_all only adds the `users` table if
    it doesn't already exist (same pattern as scripts/migrate_intelligence_layer.py),
    and this only inserts a row when no Admin account is present yet."""
    from backend.app.database.session import SessionLocal, engine
    from backend.app.database.models import Base, User
    from backend.app.dependencies import hash_password
    from backend.app.core import mfa

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
