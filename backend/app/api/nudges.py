"""Case timeline nudges API (additive — see NEW_FEATURES.md, Feature 3)."""
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app.database.session import get_db
from app.core.timeutil import utc_now
from app.database.models import FIR, PoliceStation, CaseNudge
from app.core.security import deny_admin_from_crime_data, require_role, scope_to_user_district
from app.services.nudges import (
    run_nudge_scan, serialize_nudge, NUDGE_TYPES,
    PENDING, ACKNOWLEDGED, RESOLVED, OPEN_STATUSES,
)

router = APIRouter(prefix="/nudges", tags=["Case Nudges"])

VALID_STATUSES = (PENDING, ACKNOWLEDGED, RESOLVED)


def _hydrate(db: Session, nudges: list):
    """Bulk-loads the FIR + station behind each nudge (avoids N+1)."""
    fir_ids = {n.fir_id for n in nudges}
    if not fir_ids:
        return {}, {}
    firs = {f.id: f for f in db.query(FIR).filter(FIR.id.in_(fir_ids)).all()}
    station_ids = {f.police_station_id for f in firs.values() if f.police_station_id}
    stations = ({s.id: s for s in db.query(PoliceStation).filter(PoliceStation.id.in_(station_ids)).all()}
                if station_ids else {})
    return firs, stations


class NudgeUpdateRequest(BaseModel):
    """Only the workflow state is editable — a nudge's `reason` and `due_date` are the
    scan's findings, not a user's to rewrite."""
    model_config = {"extra": "forbid"}

    status: str = Field(..., description=f"One of {VALID_STATUSES}")
    note: str | None = Field(None, max_length=300, description="Optional resolution note")


@router.get("")
@router.get("/", include_in_schema=False)
# Registered at BOTH spellings. This was the only list route in the feature set
# declared solely as "/" -- every sibling (/intelligence/mo-matches,
# /patrol/assignments/current, /evidence/actions) answers without the trailing
# slash. Starlette would normally 307 /api/nudges -> /api/nudges/, but main.py's
# SPA catch-all matches /api/nudges first and 404s it, so the redirect never runs.
def list_nudges(
    station_id: int | None = Query(None, gt=0),
    supervisor: str | None = Query(None, max_length=100),
    nudge_type: str | None = Query(None, max_length=30),
    status: str | None = Query(None, max_length=20),
    open_only: bool = Query(False, description="Shorthand for pending + acknowledged"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
    scoped_district_id: int | None = Depends(scope_to_user_district),
):
    """Lists case nudges, most urgent first (soonest due date).

    An Analyst/Investigator with a district assigned sees only nudges for cases in that
    district, matching how /api/crimes/ and the MO matches are scoped.
    """
    if nudge_type and nudge_type not in NUDGE_TYPES:
        raise HTTPException(status_code=422, detail=f"nudge_type must be one of {list(NUDGE_TYPES)}")
    if status and status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {list(VALID_STATUSES)}")

    q = db.query(CaseNudge)
    if nudge_type:
        q = q.filter(CaseNudge.nudge_type == nudge_type)
    if status:
        q = q.filter(CaseNudge.status == status)
    if open_only:
        q = q.filter(CaseNudge.status.in_(OPEN_STATUSES))
    if supervisor:
        q = q.filter(CaseNudge.assigned_supervisor == supervisor)

    # Station and district both live on the FIR's station, so join once if either is used.
    if station_id or scoped_district_id is not None:
        q = q.join(FIR, CaseNudge.fir_id == FIR.id).join(
            PoliceStation, FIR.police_station_id == PoliceStation.id)
        if station_id:
            q = q.filter(PoliceStation.id == station_id)
        if scoped_district_id is not None:
            q = q.filter(PoliceStation.district_id == scoped_district_id)

    total = q.count()
    # NULL due dates sort last: an undated nudge is not more urgent than a dated one.
    nudges = (q.order_by(CaseNudge.due_date.is_(None), CaseNudge.due_date.asc(), CaseNudge.id.asc())
                .offset(offset).limit(limit).all())
    firs, stations = _hydrate(db, nudges)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {
            "station_id": station_id, "supervisor": supervisor, "nudge_type": nudge_type,
            "status": status, "open_only": open_only,
            "district_scope_enforced": scoped_district_id is not None,
        },
        "nudges": [
            serialize_nudge(n, firs.get(n.fir_id),
                            stations.get(firs[n.fir_id].police_station_id) if n.fir_id in firs else None)
            for n in nudges
        ],
    }


@router.patch("/{nudge_id}")
def update_nudge(
    nudge_id: int,
    payload: NudgeUpdateRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("investigator")),
):
    """Acknowledges or resolves a nudge.

    Investigator clearance or above -- reading the queue is open to Analysts, but
    clearing an item off it is an accountability action.

    Re-opening a resolved nudge is not offered: the daily scan raises a fresh one if the
    condition still holds, so a resolved row stays an accurate record of what was closed
    and when.
    """
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {list(VALID_STATUSES)}")

    nudge = db.query(CaseNudge).filter(CaseNudge.id == nudge_id).first()
    if not nudge:
        raise HTTPException(status_code=404, detail="Nudge not found")
    if nudge.status == RESOLVED and payload.status != RESOLVED:
        raise HTTPException(
            status_code=409,
            detail="This nudge is already resolved. The daily scan re-raises it if the "
                   "condition still holds, so resolved entries are not reopened by hand.",
        )

    previous = nudge.status
    nudge.status = payload.status
    nudge.updated_at = utc_now()
    # Only a genuine resolution records a resolver. This used to be assigned
    # unconditionally -- acknowledging a nudge, or moving it back to pending, stamped
    # the actor into resolved_by, so supervisors saw a "resolved by" name against
    # items that were still open.
    if payload.status == RESOLVED:
        nudge.resolved_by = str(current_user.get("username") or "unknown")
    if payload.note:
        nudge.resolution_note = payload.note.strip()
    db.commit()
    db.refresh(nudge)

    fir = db.query(FIR).filter(FIR.id == nudge.fir_id).first()
    station = (db.query(PoliceStation).filter(PoliceStation.id == fir.police_station_id).first()
               if fir and fir.police_station_id else None)
    return {
        "message": f"Nudge {previous} -> {nudge.status}",
        "previous_status": previous,
        "nudge": serialize_nudge(nudge, fir, station),
    }


@router.post("/scan")
def trigger_nudge_scan(
    staleness_days: int | None = Query(None, ge=1, le=365),
    window_days: int | None = Query(None, ge=1, le=180),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_role("investigator")),
):
    """Runs the nudge scan on demand.

    The same function the daily Celery task calls, so the scheduled and manual paths
    cannot drift apart.
    """
    # Overridden thresholds make this an exploratory run, so it must not write
    # closures: `still_valid` would then hold only what THESE parameters produced,
    # and the auto-resolve pass would close every nudge the configured daily scan
    # had legitimately raised. A parameterised run reports; only a default-threshold
    # run reconciles.
    exploratory = staleness_days is not None or window_days is not None
    result = run_nudge_scan(db, staleness_days=staleness_days, window_days=window_days,
                            auto_resolve=not exploratory)
    result["auto_resolve_applied"] = not exploratory
    if exploratory:
        result["note"] = ("Ran with overridden thresholds, so existing nudges were left "
                          "untouched. Re-run without parameters to reconcile.")
    return result


@router.get("/types")
def nudge_vocabulary():
    """Nudge types and statuses, so a client need not hardcode them."""
    return {"nudge_types": list(NUDGE_TYPES), "statuses": list(VALID_STATUSES),
            "open_statuses": list(OPEN_STATUSES)}
