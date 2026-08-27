"""Patrol optimization API (additive — see NEW_FEATURES.md, Feature 1).

GET /optimize is deliberately side-effect free: it returns a plan. Committing that plan
to the roster is a separate POST, so refreshing a planning screen can never quietly
rewrite who is posted where.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app.database.session import get_db
from app.database.models import Officer, PoliceStation, PatrolAssignment
from app.core.security import deny_admin_from_crime_data, require_role, scope_to_user_district
from app.services.patrol import optimize, persist, compare_with_optimal

router = APIRouter(prefix="/patrol", tags=["Patrol Optimization"])


def _effective_district(scoped: int | None, requested: int | None) -> int | None:
    """A user's own district scope wins over the query param, as on /api/crimes/."""
    return scoped if scoped is not None else requested


@router.get("/optimize")
def optimize_patrol(
    district_id: int = Query(None, gt=0),
    shift_id: int = Query(None, gt=0, description="Restrict to one shift; otherwise shifts covering now"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
    scoped_district_id: int = Depends(scope_to_user_district),
):
    """Assigns on-duty officers to forecast hotspots, highest intensity first.

    Read-only: this computes a plan and returns it. Use POST /patrol/assignments to
    commit it.

    Uncovered hotspots and idle officers are reported explicitly rather than dropped —
    "we could not cover ranks 6-9 tonight" is the part of the answer a duty officer
    most needs.
    """
    return optimize(db, district_id=_effective_district(scoped_district_id, district_id),
                    shift_id=shift_id)


@router.post("/assignments")
def commit_assignments(
    district_id: int = Query(None, gt=0),
    shift_id: int = Query(None, gt=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("investigator")),
    scoped_district_id: int = Depends(scope_to_user_district),
):
    """Computes a plan and writes it to the roster.

    Investigator clearance or above: this posts officers to locations.

    Re-running replaces today's assignments for the same district rather than stacking
    a second set of directions on the same officers.
    """
    district = _effective_district(scoped_district_id, district_id)
    plan = optimize(db, district_id=district, shift_id=shift_id)
    if not plan["assignments"]:
        raise HTTPException(
            status_code=409,
            detail=f"Nothing to assign: {plan['officers_available']} on-duty officer(s) with a "
                   f"located station and {plan['hotspots_considered']} hotspot(s) in scope.",
        )
    written = persist(db, plan)
    return {"message": f"{written} assignment(s) committed", "replaced_todays_scope": True, **plan}


@router.get("/assignments/current")
def current_assignments(
    district_id: int = Query(None, gt=0),
    station_id: int = Query(None, gt=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
    scoped_district_id: int = Depends(scope_to_user_district),
):
    """Today's committed assignments for a district or station, highest priority first."""
    today_start = datetime.combine(datetime.utcnow().date(), datetime.min.time())
    q = db.query(PatrolAssignment).filter(PatrolAssignment.assigned_at >= today_start)

    district = _effective_district(scoped_district_id, district_id)
    if district is not None:
        q = q.filter(PatrolAssignment.district_id == district)
    if station_id is not None:
        q = q.filter(PatrolAssignment.station_id == station_id)

    rows = q.order_by(PatrolAssignment.priority_rank.asc()).all()

    officers = {}
    stations = {}
    if rows:
        oids = {r.officer_id for r in rows}
        sids = {r.station_id for r in rows if r.station_id}
        officers = {o.id: o for o in db.query(Officer).filter(Officer.id.in_(oids)).all()}
        if sids:
            stations = {s.id: s for s in db.query(PoliceStation).filter(PoliceStation.id.in_(sids)).all()}

    return {
        "date": today_start.date().isoformat(),
        "district_id": district,
        "station_id": station_id,
        "count": len(rows),
        "total_distance_km": round(sum(r.distance_km or 0 for r in rows), 3),
        "assignments": [{
            "id": r.id,
            "priority_rank": r.priority_rank,
            "officer_id": r.officer_id,
            "officer_name": officers[r.officer_id].name if r.officer_id in officers else None,
            "badge_number": officers[r.officer_id].badge_number if r.officer_id in officers else None,
            "shift_id": r.shift_id,
            "from_station": stations[r.station_id].name if r.station_id in stations else None,
            "station_id": r.station_id,
            "district_id": r.district_id,
            "hotspot_id": r.hotspot_id,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "intensity": r.intensity,
            "distance_km": r.distance_km,
            "assigned_at": r.assigned_at,
        } for r in rows],
    }


@router.get("/optimize/compare")
def compare_strategies(
    district_id: int = Query(None, gt=0),
    shift_id: int = Query(None, gt=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
    scoped_district_id: int = Depends(scope_to_user_district),
):
    """Diagnostic: what the shipped greedy plan costs against the min-total-distance
    (Hungarian) optimum, and what that optimum does to the top-priority hotspot.

    Exposed so the algorithm choice stays reviewable with real numbers instead of being
    an assertion buried in a docstring. It does not change how assignments are made.
    """
    return compare_with_optimal(db, district_id=_effective_district(scoped_district_id, district_id),
                                shift_id=shift_id)
