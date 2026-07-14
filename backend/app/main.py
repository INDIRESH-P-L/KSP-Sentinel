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
from backend.app.api import auth, dashboard, crimes, districts, forecast, network, chatbot, export, reviews

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
