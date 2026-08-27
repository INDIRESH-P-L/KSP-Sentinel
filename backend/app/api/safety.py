"""Officer-safety risk API (additive — see NEW_FEATURES.md, Feature 2).

`/safety/case/{fir_id}` is a deliberate companion to GET /api/crimes/{fir_id} rather
than a new field on it: the existing response shape is a published contract, and a
caller that does not know about officer safety should not start receiving it. A client
that wants the flag makes one extra call.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app.database.session import get_db
from app.database.models import FIR, OfficerIncidentHistory
from app.core.security import deny_admin_from_crime_data, require_role
from app.config import settings
from app.services.officer_safety import assess_location, INCIDENT_TYPES

router = APIRouter(prefix="/safety", tags=["Officer Safety"])


@router.get("/location-risk")
def location_risk(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(None, ge=10, le=50000, description="Defaults to SAFETY_DEFAULT_RADIUS_M (300)"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
):
    """Officer-safety risk at a point, from past incidents recorded nearby.

    Returns a band (none/low/medium/high), the count, the most recent date, and the
    incidents that produced the score. The evidence travels with the verdict on purpose:
    an officer told "high risk" with no reason will either ignore the flag or over-react
    to it.
    """
    if radius_m is not None and radius_m > settings.SAFETY_MAX_RADIUS_M:
        raise HTTPException(
            status_code=422,
            detail=f"radius_m may not exceed {settings.SAFETY_MAX_RADIUS_M}; a wider radius stops "
                   f"describing 'this location' and starts describing the whole beat.",
        )
    return assess_location(db, lat, lng, radius_m)


@router.get("/case/{fir_id}")
def case_location_risk(
    fir_id: int,
    radius_m: int = Query(None, ge=10, le=50000),
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
):
    """Officer-safety risk at a case's location.

    Companion call to GET /api/crimes/{fir_id} -- that endpoint's response shape is
    unchanged.
    """
    fir = db.query(FIR).filter(FIR.id == fir_id).first()
    if not fir:
        raise HTTPException(status_code=404, detail="FIR not found")

    lat = fir.latitude if fir.latitude is not None else (fir.location.latitude if fir.location else None)
    lng = fir.longitude if fir.longitude is not None else (fir.location.longitude if fir.location else None)
    if lat is None or lng is None:
        # Honest "cannot assess" rather than a fabricated all-clear.
        return {
            "fir_id": fir.id,
            "fir_number": fir.fir_number,
            "assessable": False,
            "risk": None,
            "reason": "This case has no coordinates on record, so nearby officer-safety "
                      "incidents cannot be looked up.",
        }

    assessment = assess_location(db, lat, lng, radius_m)
    return {
        "fir_id": fir.id,
        "fir_number": fir.fir_number,
        "assessable": True,
        **assessment,
    }


class IncidentCreate(BaseModel):
    model_config = {"extra": "forbid"}

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    incident_type: str = Field(..., max_length=40, description=f"One of {INCIDENT_TYPES}")
    severity: int = Field(3, ge=1, le=5, description="1 minor .. 5 severe")
    date: str | None = Field(None, max_length=40, description="ISO 8601; defaults to now")
    description: str | None = Field(None, max_length=2000)
    officers_injured: int = Field(0, ge=0, le=100)
    fir_id: int | None = Field(None, gt=0)


@router.post("/incidents")
def record_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("investigator")),
):
    """Records an officer-safety incident.

    Investigator clearance: these rows drive a warning other officers act on, so they
    are not open to anonymous or Analyst-level writes.

    `fir_id` is optional -- resistance during a patrol stop is worth recording whether
    or not it ever became a case.
    """
    if payload.incident_type not in INCIDENT_TYPES:
        raise HTTPException(status_code=422, detail=f"incident_type must be one of {list(INCIDENT_TYPES)}")
    if payload.fir_id and not db.query(FIR).filter(FIR.id == payload.fir_id).first():
        raise HTTPException(status_code=404, detail="FIR not found")

    when = datetime.utcnow()
    if payload.date:
        try:
            when = datetime.fromisoformat(payload.date)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid ISO datetime: {payload.date!r}")

    inc = OfficerIncidentHistory(
        fir_id=payload.fir_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        incident_type=payload.incident_type,
        severity=payload.severity,
        date=when,
        description=payload.description,
        officers_injured=payload.officers_injured,
    )
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return {
        "message": "Officer-safety incident recorded",
        "incident": {
            "id": inc.id, "fir_id": inc.fir_id, "latitude": inc.latitude, "longitude": inc.longitude,
            "incident_type": inc.incident_type, "severity": inc.severity, "date": inc.date,
            "officers_injured": inc.officers_injured, "description": inc.description,
        },
    }


@router.get("/incident-types")
def incident_vocabulary():
    """Incident types, severity range and band cut-offs, so clients need not hardcode them."""
    return {
        "incident_types": list(INCIDENT_TYPES),
        "severity_range": [1, 5],
        "risk_bands": ["none", "low", "medium", "high"],
        "default_radius_m": settings.SAFETY_DEFAULT_RADIUS_M,
        "max_radius_m": settings.SAFETY_MAX_RADIUS_M,
    }
