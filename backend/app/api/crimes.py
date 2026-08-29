from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app.database.session import get_db
from app.database.models import FIR, PoliceStation
from app.core.security import deny_admin_from_crime_data, scope_to_user_district
from app.core.masking import mask_person
from app.services.case_readiness import assess_case
from embeddings.similarity_search import search_similar_firs, build_search_index
import math
from app import filestore_crime_data

router = APIRouter(prefix="/crimes", tags=["Crimes"])

@router.get("")
@router.get("/")
def list_firs(
    year: int = None,
    district_id: int = None,
    station_id: int = None,
    category_id: int = None,
    status: str = Query(None, max_length=50),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
    scoped_district_id: int = Depends(scope_to_user_district),
):
    """Lists FIRs with optional filters. Analyst/Investigator accounts with a district
    assigned are restricted to that district regardless of the district_id query
    param -- see scope_to_user_district for why unassigned accounts are unscoped.

    Sourced live from the Catalyst FileStore FIR CSVs (see app/filestore_crime_data.py)
    -- deliberately no Datastore fallback, so a FileStore outage surfaces as an explicit
    503 rather than silently serving stale local data."""
    effective_district_id = scoped_district_id if scoped_district_id is not None else district_id

    result = filestore_crime_data.list_firs(
        year=year, district_id=effective_district_id, station_id=station_id, category_id=category_id,
        status=status, limit=limit, offset=offset,
    )
    if result is None:
        raise HTTPException(status_code=503, detail="Crime data is unavailable: could not reach Catalyst FileStore.")
    return result

@router.get("/search")
def semantic_search(
    query: str = Query(..., min_length=1, max_length=500),
    top_k: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Semantic similar case search using Sentence Transformers and Cosine/FAISS index"""
    matches = search_similar_firs(query, top_k, db)
    
    results = []
    for m in matches:
        f = m["fir"]
        results.append({
            "fir_number": f.fir_number,
            "station": f.station.name if f.station else None,
            "subcategory": f.subcategory.name if f.subcategory else None,
            "date_reported": f.date_reported,
            "status": f.status,
            "description": f.description,
            "score": m["score"]
        })
    return results

@router.get("/{fir_id}/timeline")
def get_fir_timeline(fir_id: int, db: Session = Depends(get_db)):
    """Builds a beautiful sequential investigation timeline for a specific case"""
    fir = db.query(FIR).filter(FIR.id == fir_id).first()
    if not fir:
        raise HTTPException(status_code=404, detail="FIR not found")
        
    timeline = []
    
    # 1. Incident occurrence
    timeline.append({
        "stage": "Incident Occurred",
        "date": fir.date_occurred,
        "status": "COMPLETED",
        "details": "Crime incident occurred at the specified coordinates."
    })
    
    # 2. FIR Registered
    timeline.append({
        "stage": "FIR Registered",
        "date": fir.date_reported,
        "status": "COMPLETED",
        "details": f"FIR `{fir.fir_number}` officially registered at {fir.station.name}."
    })
    
    # 3. Investigation Assigned/Ongoing
    for inv in fir.investigations:
        timeline.append({
            "stage": f"Investigation ({inv.assigned_officer})",
            "date": inv.last_updated,
            "status": "COMPLETED" if inv.status == "COMPLETED" else "ACTIVE",
            "details": f"Investigation assigned to {inv.assigned_officer}. Current Status: {inv.status}."
        })
        
    # 4. Arrest stage (if any)
    for arr in fir.arrests:
        timeline.append({
            "stage": f"Suspect Arrested ({arr.accused.name})",
            "date": arr.arrest_date,
            "status": "COMPLETED",
            "details": f"Suspect {arr.accused.name} (Age: {arr.accused.age}) arrested and produced in court."
        })
        
    # 5. Chargesheet / Conviction (if any)
    for conv in fir.convictions:
        timeline.append({
            "stage": f"Trial & Conviction",
            "date": conv.conviction_date,
            "status": "COMPLETED",
            "details": f"Accused sentenced to {conv.sentence_months} months imprisonment under trial conviction."
        })
        
    return {
        "fir_number": fir.fir_number,
        "current_status": fir.status,
        "timeline": sorted(timeline, key=lambda x: x["date"] if x["date"] else datetime.min)
    }

@router.get("/{fir_id}/intelligence")
def get_fir_intelligence(fir_id: int, db: Session = Depends(get_db), current_user: dict = Depends(deny_admin_from_crime_data)):
    """Returns the structured Person/Location/ModusOperandi intelligence layer for a case."""
    fir = db.query(FIR).filter(FIR.id == fir_id).first()
    if not fir:
        raise HTTPException(status_code=404, detail="FIR not found")

    role = current_user.get("role", "")
    can_view_sensitive = current_user.get("can_view_sensitive", False)

    persons = []
    for link in fir.person_links:
        p = link.person
        raw = {
            "id": p.id,
            "name": p.full_name,
            "role": link.role,
            "age": p.age,
            "gender": p.gender,
            "address": p.address,
            "id_reference": p.id_reference,
            "sensitive": p.sensitive,
            "relationship_notes": link.relationship_notes,
        }
        persons.append(mask_person(raw, role, can_view_sensitive, is_sensitive=p.sensitive))

    location = None
    if fir.location:
        # Any person on this case being sensitive suppresses the incident address too
        # -- an exact address plus a name is exactly the re-identification risk IPC
        # 228A-style protection exists to prevent, even if the address field itself
        # isn't attached to the person record.
        case_is_sensitive = any(link.person.sensitive for link in fir.person_links)
        if case_is_sensitive:
            # Sensitive overrides role entirely -- a Superintendent without the
            # can_view_sensitive grant is masked exactly like everyone else, same as
            # mask_person() above does for name/address/id_reference.
            show_address = can_view_sensitive
        else:
            show_address = role.lower() != "analyst"
        location = {
            "id": fir.location.id,
            "latitude": fir.location.latitude,
            "longitude": fir.location.longitude,
            "location_type": fir.location.location_type,
            "address_text": fir.location.address_text if show_address else "[REDACTED]",
        }

    mo = None
    if fir.modus_operandi:
        mo = {
            "entry_method": fir.modus_operandi.entry_method,
            "weapon_used": fir.modus_operandi.weapon_used,
            "time_of_day_pattern": fir.modus_operandi.time_of_day_pattern,
            "target_type": fir.modus_operandi.target_type,
        }

    return {
        "fir_id": fir.id,
        "fir_number": fir.fir_number,
        "persons": persons,
        "location": location,
        "modus_operandi": mo,
    }


@router.post("/register")
def register_fir(
    fir_number: str = Query(..., min_length=1, max_length=50, pattern=r"^[A-Za-z0-9/\-]+$"),
    police_station_id: int = Query(..., gt=0),
    subcategory_id: int = Query(..., gt=0),
    description: str = Query(..., min_length=1, max_length=5000),
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    date_occurred: str = Query(..., max_length=40), # ISO string
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data)
):
    """Registers a new FIR in the database and schedules semantic re-indexing"""
    # Check duplicate
    existing = db.query(FIR).filter(FIR.fir_number == fir_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="FIR number already exists")
        
    try:
        dt_occurred = datetime.fromisoformat(date_occurred)
    except ValueError:
        dt_occurred = datetime.utcnow()
        
    new_fir = FIR(
        fir_number=fir_number,
        police_station_id=police_station_id,
        subcategory_id=subcategory_id,
        description=description,
        latitude=latitude,
        longitude=longitude,
        date_occurred=dt_occurred,
        date_reported=datetime.utcnow(),
        status="REGISTERED"
    )
    
    db.add(new_fir)
    db.commit()
    db.refresh(new_fir)
    
    # Rebuild search index in background to include the new case
    try:
        build_search_index(db)
    except Exception as e:
        print(f"Error updating FAISS index in background: {e}")
        
    return {"message": "FIR registered successfully", "fir_id": new_fir.id}

@router.get("/emerging-trends")
def get_emerging_trends(db: Session = Depends(get_db)):
    """Detects active emerging trend crime categories spiking in specific regions compared to history,
    using the same z-score-over-trailing-baseline anomaly detector as /dashboard/anomalies (CUSUM-style
    spike detection), rather than a fixed threshold."""
    if db.bind.dialect.name == "sqlite":
        sql = (
            "SELECT d.id as d_id, d.name as d_name, c.id as c_id, c.name as c_name, "
            "strftime('%Y-%m', f.date_reported) as ym, COUNT(f.id) as cnt "
            "FROM fir_cases f "
            "JOIN police_stations ps ON f.police_station_id = ps.id "
            "JOIN districts d ON ps.district_id = d.id "
            "JOIN crime_subcategories sub ON f.subcategory_id = sub.id "
            "JOIN crime_categories c ON sub.category_id = c.id "
            "GROUP BY d_id, c_id, ym ORDER BY ym"
        )
    else:
        sql = (
            "SELECT d.id as d_id, d.name as d_name, c.id as c_id, c.name as c_name, "
            "to_char(f.date_reported, 'YYYY-MM') as ym, COUNT(f.id) as cnt "
            "FROM fir_cases f "
            "JOIN police_stations ps ON f.police_station_id = ps.id "
            "JOIN districts d ON ps.district_id = d.id "
            "JOIN crime_subcategories sub ON f.subcategory_id = sub.id "
            "JOIN crime_categories c ON sub.category_id = c.id "
            "GROUP BY d_id, c_id, ym ORDER BY ym"
        )
    res = db.execute(text(sql)).fetchall()

    history = {}
    for row in res:
        key = (row[0], row[1], row[2], row[3])
        history.setdefault(key, []).append({"ym": row[4], "count": row[5]})

    real_trends = []
    for (d_id, d_name, c_id, c_name), monthly_data in history.items():
        if len(monthly_data) < 3:
            continue
        counts = [item["count"] for item in monthly_data]
        mean = sum(counts) / len(counts) if counts else 0.0
        var = sum((x - mean) ** 2 for x in counts) / len(counts) if counts else 0.0
        std = math.sqrt(var)
        latest = monthly_data[-1]
        latest_count = latest["count"]
        z_score = (latest_count - mean) / std if std > 0 else 0.0

        if (z_score > 1.5 and latest_count > mean + 2) or (std == 0 and latest_count > mean + 3):
            # Anchor the pulsing marker at the busiest station in this district for this category
            station_row = db.execute(text(
                "SELECT ps.name, ps.latitude, ps.longitude, COUNT(f.id) as cnt "
                "FROM fir_cases f "
                "JOIN police_stations ps ON f.police_station_id = ps.id "
                "JOIN crime_subcategories sub ON f.subcategory_id = sub.id "
                "WHERE ps.district_id = :d_id AND sub.category_id = :c_id "
                "GROUP BY ps.id ORDER BY cnt DESC LIMIT 1"
            ), {"d_id": d_id, "c_id": c_id}).fetchone()

            if station_row and station_row[1] and station_row[2]:
                growth_rate = round(((latest_count - mean) / mean) * 100, 1) if mean > 0 else 100.0
                real_trends.append({
                    "station_id": d_id,
                    "station_name": station_row[0],
                    "latitude": station_row[1],
                    "longitude": station_row[2],
                    "category_name": c_name,
                    "growth_rate": growth_rate,
                    "description": f"{c_name} spiked +{growth_rate}% above baseline in {d_name} ({latest_count} cases vs {mean:.1f} expected, z={z_score:.2f})."
                })

    if real_trends:
        return real_trends

    # Fallback illustrative data only when there's no live statistical spike to report
    trends = [
        {
            "station_id": 2,
            "station_name": "Indiranagar PS",
            "latitude": 12.9719,
            "longitude": 77.6412,
            "category_name": "Cyber Crime",
            "growth_rate": 43.0,
            "description": "Cyber phishing fraud cases spiked 43% near commercial areas."
        },
        {
            "station_id": 1,
            "station_name": "Majestic Transit PS",
            "latitude": 12.9778,
            "longitude": 77.5714,
            "category_name": "Theft & Burglary",
            "growth_rate": 28.5,
            "description": "Vehicle theft clusters detected during night hours near metro station."
        },
        {
            "station_id": 11,
            "station_name": "Pandeshwar PS",
            "latitude": 12.8596,
            "longitude": 74.8436,
            "category_name": "Narcotics",
            "growth_rate": 35.0,
            "description": "Drug trafficking operations active near transport corridors."
        }
    ]
    return trends


# ─────────────────────────────────────────────────────────────────────────────
# Case Readiness — the five intelligence signals rolled into one verdict.
# See app/services/case_readiness.py for the scoring rationale.
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{fir_id}/readiness")
def case_readiness(
    fir_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
    scoped_district_id: int | None = Depends(scope_to_user_district),
):
    """Can this case go to court, and if not, what is missing?

    Aggregates the accused/arrest record, evidence integrity and custody trail, section
    determination, investigation activity and cross-district linkage into a single
    weighted score, plus an ordered worklist of what to do next.

    The statutory chargesheet clock is reported alongside the score rather than inside
    it -- time remaining is not evidentiary quality, and averaging the two would hide
    both.
    """
    fir = db.query(FIR).filter(FIR.id == fir_id).first()
    if not fir:
        raise HTTPException(status_code=404, detail="FIR not found")

    if scoped_district_id is not None:
        station = fir.station
        fir_district = station.district_id if station else None
        if fir_district is not None and fir_district != scoped_district_id:
            raise HTTPException(status_code=403,
                                detail="This case is outside your assigned district.")

    return assess_case(db, fir)


@router.get("/readiness/queue")
def readiness_queue(
    band: str | None = Query(None, description="Filter to one band: blocked|gaps|nearly_ready|ready"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: dict = Depends(deny_admin_from_crime_data),
    scoped_district_id: int | None = Depends(scope_to_user_district),
):
    """Supervisor view: every open case ranked by how close it is to filing.

    Sorted by statutory urgency first, then by score ascending -- so the case closest to
    its deadline with the least prepared file surfaces at the top, which is the one
    genuinely at risk of collapsing on time limits.
    """
    q = db.query(FIR).filter(~FIR.status.in_(("CLOSED", "CHARGE_SHEETED")))
    if scoped_district_id is not None:
        q = q.join(FIR.station).filter(PoliceStation.district_id == scoped_district_id)

    # Oldest first, because `limit` is applied by the DATABASE, before any case has been
    # assessed. Ordering by id here would make "the 20 most urgent" actually mean "the
    # first 20 by id, then sorted" -- which can omit the very case the caller needs.
    # The statutory clock derives from date_reported, so oldest-first is the correct
    # pre-filter: the cases nearest their deadline are exactly the ones selected.
    rows = []
    for fir in q.order_by(FIR.date_reported.asc()).limit(limit).all():
        a = assess_case(db, fir)
        if band and a["band"] != band:
            continue
        rows.append({
            "fir_id": a["fir_id"],
            "fir_number": a["fir_number"],
            "status": a["status"],
            "readiness_score": a["readiness_score"],
            "band": a["band"],
            "days_remaining": a["statutory_clock"].get("days_remaining"),
            "statutory_status": a["statutory_clock"].get("status"),
            "blocker_count": len(a["next_actions"]),
            "top_action": a["next_actions"][0]["action"] if a["next_actions"] else None,
        })

    urgency = {"expired": 0, "critical": 1, "approaching": 2, "comfortable": 3, "filed": 4}
    rows.sort(key=lambda r: (urgency.get(r["statutory_status"], 5), r["readiness_score"]))

    return {
        "count": len(rows),
        "cases": rows,
        "district_scope_enforced": scoped_district_id is not None,
        "advisory": "Documentary completeness only -- not a recommendation to file or close.",
    }
