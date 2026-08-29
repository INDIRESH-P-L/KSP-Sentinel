"""Feature 1 — patrol optimization.

Assigns on-duty officers to forecast hotspots.

    Why priority-ordered greedy and not the Hungarian algorithm.

    The brief names two objectives that pull against each other: minimise total travel
    distance, and cover the highest-intensity hotspots first.

    scipy's linear_sum_assignment minimises the SUM of distances. To lower that global
    total it will hand the worst hotspot to a farther officer whenever doing so improves
    the overall figure. For patrol dispatch that is the wrong trade -- the highest-
    intensity hotspot is exactly the one that should be reached soonest, not the one
    sacrificed to tidy up an aggregate.

    Greedy in priority order implements the stated priority directly: the top hotspot
    takes the nearest available officer, the next takes the nearest of those remaining,
    and so on. Total distance lands near-optimal as a by-product, which is the correct
    ranking of the two goals here.

    `compare_with_optimal()` measures the gap against the Hungarian optimum so that
    ranking stays an evidence-based choice rather than an assumption. It is a diagnostic,
    not the assignment path.

Distance is straight-line (haversine) from the officer's station to the hotspot. Road
distance would need a routing engine and none is available offline; this is documented
rather than silently presented as drive distance.
"""
import sys
import os
from datetime import datetime
from math import radians, sin, cos, asin, sqrt

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from sqlalchemy.orm import Session
from app.database.models import (
    Officer, OfficerShift, PoliceStation, CrimeHotspot, PatrolAssignment,
)
from app.core.timeutil import local_day_start_utc, utc_now

ON_DUTY = "on_duty"
EARTH_RADIUS_KM = 6371.0


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def available_officers(db: Session, district_id: int | None = None,
                       shift_id: int | None = None, now: datetime | None = None) -> list[dict]:
    """On-duty officers with a usable station location.

    An officer whose station has no coordinates is excluded rather than defaulted to the
    district centre -- a fabricated origin would produce a confident but meaningless
    distance.
    """
    now = now or utc_now()
    q = (db.query(OfficerShift, Officer, PoliceStation)
           .join(Officer, OfficerShift.officer_id == Officer.id)
           .outerjoin(PoliceStation, OfficerShift.station_id == PoliceStation.id)
           .filter(OfficerShift.status == ON_DUTY))

    if shift_id is not None:
        q = q.filter(OfficerShift.id == shift_id)
    else:
        # Only shifts actually covering this moment.
        q = q.filter(OfficerShift.shift_start <= now, OfficerShift.shift_end >= now)
    if district_id is not None:
        q = q.filter(PoliceStation.district_id == district_id)

    out = []
    for shift, officer, station in q.all():
        if station is None or station.latitude is None or station.longitude is None:
            continue
        out.append({
            "officer_id": officer.id,
            "officer_name": officer.name,
            "badge_number": officer.badge_number,
            "rank": officer.rank,
            "shift_id": shift.id,
            "shift_start": shift.shift_start,
            "shift_end": shift.shift_end,
            "station_id": station.id,
            "station_name": station.name,
            "district_id": station.district_id,
            "lat": station.latitude,
            "lng": station.longitude,
        })
    return out


def target_hotspots(db: Session, district_id: int | None = None, limit: int = 200) -> list[dict]:
    """Forecast hotspots, highest intensity first — that ordering IS the priority."""
    q = (db.query(CrimeHotspot, PoliceStation)
           .join(PoliceStation, CrimeHotspot.police_station_id == PoliceStation.id))
    if district_id is not None:
        q = q.filter(PoliceStation.district_id == district_id)

    rows = q.order_by(CrimeHotspot.intensity.desc()).limit(limit).all()
    return [{
        "hotspot_id": h.id,
        "lat": h.latitude,
        "lng": h.longitude,
        "intensity": h.intensity,
        "prediction_date": h.prediction_date,
        "station_id": station.id,
        "station_name": station.name,
        "district_id": station.district_id,
    } for h, station in rows]


def optimize(db: Session, district_id: int | None = None, shift_id: int | None = None,
             now: datetime | None = None) -> dict:
    """Greedy nearest-available-officer, walking hotspots in descending intensity."""
    now = now or utc_now()
    officers = available_officers(db, district_id=district_id, shift_id=shift_id, now=now)
    hotspots = target_hotspots(db, district_id=district_id)

    unassigned_officers = {o["officer_id"]: o for o in officers}
    assignments = []
    uncovered = []

    for rank, hs in enumerate(hotspots, start=1):
        if not unassigned_officers:
            # Ran out of officers: everything below this rank is uncovered, and the
            # response says so rather than quietly truncating the list.
            uncovered.append({**hs, "priority_rank": rank,
                              "reason": "No on-duty officer remaining"})
            continue

        best_id, best_dist = None, None
        for oid, off in unassigned_officers.items():
            d = _haversine_km(off["lat"], off["lng"], hs["lat"], hs["lng"])
            if best_dist is None or d < best_dist:
                best_id, best_dist = oid, d

        off = unassigned_officers.pop(best_id)
        assignments.append({
            "priority_rank": rank,
            "officer_id": off["officer_id"],
            "officer_name": off["officer_name"],
            "badge_number": off["badge_number"],
            "rank_title": off["rank"],
            "shift_id": off["shift_id"],
            "from_station": off["station_name"],
            "from_station_id": off["station_id"],
            "district_id": hs["district_id"],
            "hotspot_id": hs["hotspot_id"],
            "hotspot_lat": hs["lat"],
            "hotspot_lng": hs["lng"],
            "intensity": hs["intensity"],
            "distance_km": round(best_dist, 3),
        })

    total_km = round(sum(a["distance_km"] for a in assignments), 3)
    return {
        "strategy": "greedy_priority_nearest",
        "generated_at": now,
        "district_id": district_id,
        "shift_id": shift_id,
        "officers_available": len(officers),
        "hotspots_considered": len(hotspots),
        "assigned_count": len(assignments),
        "uncovered_count": len(uncovered),
        "idle_officer_count": len(unassigned_officers),
        "total_distance_km": total_km,
        "average_distance_km": round(total_km / len(assignments), 3) if assignments else 0.0,
        "distance_basis": "straight-line (haversine) station-to-hotspot; not road distance",
        "assignments": assignments,
        "uncovered_hotspots": uncovered,
        "idle_officers": list(unassigned_officers.values()),
    }


def compare_with_optimal(db: Session, district_id: int | None = None,
                         shift_id: int | None = None, now: datetime | None = None) -> dict:
    """Diagnostic: greedy vs the Hungarian (min-total-distance) optimum.

    Reports the distance greedy gives up AND what the optimum does to the top-priority
    hotspot, which is the trade that actually matters. Not part of the assignment path.
    """
    now = now or utc_now()
    officers = available_officers(db, district_id=district_id, shift_id=shift_id, now=now)
    hotspots = target_hotspots(db, district_id=district_id)
    if not officers or not hotspots:
        return {"comparable": False, "reason": "Needs at least one officer and one hotspot."}

    try:
        import numpy as np
        from scipy.optimize import linear_sum_assignment
    except ImportError:
        return {"comparable": False, "reason": "scipy/numpy not installed."}

    n = min(len(officers), len(hotspots))
    cost = np.array([[_haversine_km(o["lat"], o["lng"], h["lat"], h["lng"])
                      for h in hotspots] for o in officers], dtype=float)
    rows, cols = linear_sum_assignment(cost)
    optimal_total = float(cost[rows, cols].sum())

    greedy = optimize(db, district_id=district_id, shift_id=shift_id, now=now)
    greedy_total = greedy["total_distance_km"]

    # What each approach does for the single highest-intensity hotspot.
    greedy_top = next((a["distance_km"] for a in greedy["assignments"] if a["priority_rank"] == 1), None)
    optimal_top = None
    for r, c in zip(rows, cols):
        if c == 0:                                   # hotspots are already intensity-sorted
            optimal_top = float(cost[r, c])
    top_covered_by_optimal = optimal_top is not None

    return {
        "comparable": True,
        "pairs_compared": n,
        "greedy_total_km": greedy_total,
        "hungarian_total_km": round(optimal_total, 3),
        "greedy_excess_km": round(greedy_total - optimal_total, 3),
        "greedy_excess_pct": round(((greedy_total - optimal_total) / optimal_total * 100), 2) if optimal_total else 0.0,
        "top_priority_hotspot": {
            "greedy_distance_km": greedy_top,
            "hungarian_distance_km": round(optimal_top, 3) if optimal_top is not None else None,
            "covered_by_hungarian": top_covered_by_optimal,
        },
    }


def persist(db: Session, plan: dict) -> int:
    """Writes a plan's assignments, replacing today's rows for the SAME scope so a
    re-run updates the roster instead of stacking duplicate directions on the same
    officers.

    "Same scope" means district AND shift. `shift_id` was previously present in the
    plan but absent from the delete filter, so committing the night shift deleted
    that district's day and evening rosters as well -- silent data loss that only
    showed up as officers whose assignments had vanished. An unscoped commit
    (district_id=None) additionally cleared every district in the state; it is now
    confined to the districts the plan actually covers.
    """
    today_start = local_day_start_utc()

    q = db.query(PatrolAssignment).filter(PatrolAssignment.assigned_at >= today_start)

    scope_district = plan.get("district_id")
    if scope_district is not None:
        q = q.filter(PatrolAssignment.district_id == scope_district)
    else:
        # No district scope on the plan: only clear the districts this plan writes to,
        # never the whole state.
        covered = {a["district_id"] for a in plan["assignments"] if a.get("district_id") is not None}
        if covered:
            q = q.filter(PatrolAssignment.district_id.in_(covered))

    scope_shift = plan.get("shift_id")
    if scope_shift is not None:
        q = q.filter(PatrolAssignment.shift_id == scope_shift)

    q.delete(synchronize_session=False)

    for a in plan["assignments"]:
        db.add(PatrolAssignment(
            officer_id=a["officer_id"], shift_id=a["shift_id"], hotspot_id=a["hotspot_id"],
            station_id=a["from_station_id"], district_id=a["district_id"],
            latitude=a["hotspot_lat"], longitude=a["hotspot_lng"], intensity=a["intensity"],
            distance_km=a["distance_km"], priority_rank=a["priority_rank"],
            assigned_at=utc_now(),
        ))
    db.commit()
    return len(plan["assignments"])
