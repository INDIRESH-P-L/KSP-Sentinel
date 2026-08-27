"""Feature 2 — officer-safety location risk.

Answers one question before an officer approaches a place: has anything happened to
officers *here* before?

    Scoring

        score = Σ  type_weight × (severity / pivot) × recency_factor

    over every recorded incident inside the radius. Three deliberate choices:

      * Incident type is weighted, because "assaulted here" and "argued with here"
        are not the same warning.
      * Severity is divided by a pivot (default 3) so a typical incident contributes
        ~1.0 and the scale stays readable.
      * Recency decays in bands but never to zero. A confrontation five years ago is a
        far weaker predictor than one last month, yet a location with a long violent
        history is still not a clean one.

    Bands are tuned so a SINGLE recent maximum-severity assault on an officer reaches
    "high" on its own. Under-calling that to avoid alarming people would be the wrong
    direction to fail in.

    The response always carries the contributing incidents and a per-incident
    contribution, because an officer told "high risk" with no reason will either ignore
    the flag or over-react to it. A number without its evidence is not usable safety
    information.

SQLite has no geospatial support, so the radius query is a bounding-box prefilter
(indexed on lat/lng) refined by exact haversine — the box alone would over-select at the
corners.
"""
import sys
import os
from datetime import datetime
from math import radians, sin, cos, asin, sqrt, degrees

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sqlalchemy.orm import Session
from app.database.models import OfficerIncidentHistory
from app.config import settings

ASSAULT = "assault_on_officer"
RESISTANCE = "resistance"
WEAPON = "weapon_involved"
INCIDENT_TYPES = (ASSAULT, RESISTANCE, WEAPON)

RISK_NONE, RISK_LOW, RISK_MEDIUM, RISK_HIGH = "none", "low", "medium", "high"

EARTH_RADIUS_M = 6_371_000.0


def _type_weight(incident_type: str) -> float:
    return {
        ASSAULT: settings.SAFETY_WEIGHT_ASSAULT,
        WEAPON: settings.SAFETY_WEIGHT_WEAPON,
        RESISTANCE: settings.SAFETY_WEIGHT_RESISTANCE,
    }.get(incident_type, settings.SAFETY_WEIGHT_RESISTANCE)


def _recency_factor(when: datetime | None, now: datetime) -> tuple[float, int | None]:
    """(factor, age_in_months). Unknown dates are treated as old, not as absent."""
    if when is None:
        return settings.SAFETY_RECENCY_FACTOR_ANCIENT, None
    months = max(0, int((now - when).days / 30.44))
    if months <= settings.SAFETY_RECENCY_RECENT_MONTHS:
        return 1.0, months
    if months <= settings.SAFETY_RECENCY_MID_MONTHS:
        return settings.SAFETY_RECENCY_FACTOR_MID, months
    if months <= settings.SAFETY_RECENCY_OLD_MONTHS:
        return settings.SAFETY_RECENCY_FACTOR_OLD, months
    return settings.SAFETY_RECENCY_FACTOR_ANCIENT, months


def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * asin(sqrt(a))


def _band(score: float) -> str:
    if score <= 0:
        return RISK_NONE
    if score < settings.SAFETY_BAND_LOW:
        return RISK_LOW
    if score < settings.SAFETY_BAND_MEDIUM:
        return RISK_MEDIUM
    return RISK_HIGH


ADVICE = {
    RISK_NONE: "No recorded officer-safety incidents nearby. Standard precautions.",
    RISK_LOW: "Isolated or dated incidents nearby. Standard precautions; stay aware.",
    RISK_MEDIUM: "Repeated or recent incidents nearby. Consider approaching with a second officer "
                 "and confirm comms before arrival.",
    RISK_HIGH: "Serious and/or recent violence against officers recorded here. Do not approach alone; "
               "notify control and consider backup before arrival.",
}


def assess_location(db: Session, lat: float, lng: float, radius_m: int | None = None,
                    now: datetime | None = None) -> dict:
    """Risk assessment for a point, with the evidence behind it."""
    radius_m = radius_m or settings.SAFETY_DEFAULT_RADIUS_M
    now = now or datetime.utcnow()

    # Bounding box first (indexed), haversine second (exact).
    lat_delta = degrees(radius_m / EARTH_RADIUS_M)
    cos_lat = max(cos(radians(lat)), 1e-6)          # guard the poles
    lng_delta = degrees(radius_m / (EARTH_RADIUS_M * cos_lat))

    candidates = (db.query(OfficerIncidentHistory)
                    .filter(OfficerIncidentHistory.latitude.between(lat - lat_delta, lat + lat_delta))
                    .filter(OfficerIncidentHistory.longitude.between(lng - lng_delta, lng + lng_delta))
                    .all())

    contributing = []
    score = 0.0
    by_type = {}
    most_recent = None

    for inc in candidates:
        distance = _haversine_m(lat, lng, inc.latitude, inc.longitude)
        if distance > radius_m:
            continue                                  # corner of the box, outside the circle

        weight = _type_weight(inc.incident_type)
        severity = inc.severity if inc.severity is not None else 3
        sev_factor = severity / settings.SAFETY_SEVERITY_PIVOT
        rec_factor, age_months = _recency_factor(inc.date, now)
        contribution = weight * sev_factor * rec_factor
        score += contribution

        by_type[inc.incident_type] = by_type.get(inc.incident_type, 0) + 1
        if inc.date and (most_recent is None or inc.date > most_recent):
            most_recent = inc.date

        contributing.append({
            "id": inc.id,
            "fir_id": inc.fir_id,
            "incident_type": inc.incident_type,
            "severity": severity,
            "date": inc.date,
            "age_months": age_months,
            "officers_injured": inc.officers_injured or 0,
            "distance_m": round(distance, 1),
            "description": inc.description,
            "contribution": round(contribution, 3),
        })

    contributing.sort(key=lambda c: c["contribution"], reverse=True)
    risk = _band(score)

    return {
        "latitude": lat,
        "longitude": lng,
        "radius_m": radius_m,
        "risk": risk,
        "risk_score": round(score, 3),
        "incident_count": len(contributing),
        "incidents_by_type": by_type,
        "most_recent_incident": most_recent,
        "days_since_most_recent": (now - most_recent).days if most_recent else None,
        "officers_injured_total": sum(c["officers_injured"] for c in contributing),
        "advice": ADVICE[risk],
        "bands": {
            "low_below": settings.SAFETY_BAND_LOW,
            "medium_below": settings.SAFETY_BAND_MEDIUM,
            "high_at_or_above": settings.SAFETY_BAND_MEDIUM,
        },
        "contributing_incidents": contributing,
    }
