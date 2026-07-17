from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# Set paths
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.app.config import settings
from backend.app.logging import logger

# Import API routers
from backend.app.api import auth, dashboard, crimes, districts, forecast, network, chatbot, export, reviews, users

app = FastAPI(
    title="KSP Sentinel API",
    description="AI-Powered Crime Intelligence & Predictive Analytics Platform for Karnataka Police",
    version="1.0.0"
)

# CORS configuration
origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if not db.query(User).filter(User.role == "Admin").first():
            db.add(User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="Admin",
                is_active=True,
                created_by="system",
            ))
            db.commit()
            logger.warning(
                "Seeded default admin account (username='admin', password='admin123'). "
                "Change this password immediately in any real deployment."
            )
    finally:
        db.close()
