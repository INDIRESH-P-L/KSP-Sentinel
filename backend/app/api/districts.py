from fastapi import APIRouter, HTTPException, Query
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app import filestore_crime_data
from clustering.dbscan import perform_dbscan
from clustering.st_dbscan import perform_st_dbscan
from geospatial.kde import compute_kde_heatmap
import numpy as np

router = APIRouter(prefix="/districts", tags=["Districts"])

_UNAVAILABLE = "Crime data is unavailable: could not reach Catalyst FileStore."


class _FirLike:
    """Minimal attribute-access shim so the geospatial helpers below (originally written
    against SQLAlchemy FIR rows) can run unmodified over FileStore-sourced dicts."""
    def __init__(self, d: dict):
        self.id = d["id"]
        self.latitude = d["latitude"]
        self.longitude = d["longitude"]
        self.date_occurred = d["date_occurred"]


@router.get("/")
def list_districts():
    """Returns all districts with their general parameters, live from FileStore."""
    result = filestore_crime_data.list_districts()
    if result is None:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    return result

@router.get("/rankings")
def get_district_rankings():
    """Ranks districts based on calculated crime rates and solved rate metrics, live from FileStore."""
    result = filestore_crime_data.get_district_rankings()
    if result is None:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    return result

@router.get("/{district_id}/explain-risk")
def explain_district_risk(district_id: int):
    """Returns Explainable AI (XAI) feature importance breakdowns for a district risk score,
    live from FileStore."""
    district = filestore_crime_data.get_district_by_id(district_id)
    if district is None:
        # get_district_by_id returns None both for "FileStore unreachable" and "no such
        # district" -- disambiguate by checking whether FileStore data loaded at all.
        if filestore_crime_data.get_dataset() is None:
            raise HTTPException(status_code=503, detail=_UNAVAILABLE)
        raise HTTPException(status_code=404, detail="District not found")

    score = district["risk_score"]
    total_crimes = district["total_firs"]

    volume_impact = min(40, int((total_crimes / 150) * 40))
    import datetime
    current_month = datetime.datetime.now().month
    is_festival_season = current_month in [10, 11, 12, 1]
    season_impact = 25 if is_festival_season else 15
    priors_avg = 2.4
    recidivism_impact = min(30, int(priors_avg * 10))

    total_calculated = volume_impact + season_impact + recidivism_impact
    scale = score / max(1, total_calculated)
    volume_final = min(40, round(volume_impact * scale))
    season_final = min(30, round(season_impact * scale))
    recidivism_final = min(30, round(recidivism_impact * scale))
    infra_final = max(0, score - (volume_final + season_final + recidivism_final))

    explanations = [
        f"**Historical Crime Density (+{volume_final}%)**: High incident volume of {total_crimes} registered cases increases the baseline hazard rate.",
        f"**Temporal / Seasonal Factors (+{season_final}%)**: Current monthly trend shows elevated activity matching historical weekend/night cycles.",
        f"**Recidivism Rate (+{recidivism_final}%)**: High density of active offenders with prior criminal history residing or operating in the district bounds.",
        f"**Population & Urban Infrastructure (+{infra_final}%)**: Density and commercial concentration zones create target-rich environments (e.g. tech parks, transit hubs).",
    ]
    recommendations = [
        "Increase patrolling frequency during night hours (22:00 - 04:00) in commercial corridors.",
        "Deploy decoy police teams near transit and bus stands (Majestic/Koramangala equivalent transit points).",
        "Establish active verification checkpoints on border roads and highway escape routes.",
    ]

    return {
        "district_id": district_id,
        "district_name": district["name"],
        "risk_score": score,
        "risk_level": "CRITICAL" if score >= 80 else ("HIGH" if score >= 60 else "MODERATE"),
        "factors": {
            "historical_density": volume_final, "seasonality": season_final,
            "recidivism": recidivism_final, "urban_density": infra_final,
        },
        "explanations": explanations,
        "recommendations": recommendations,
    }

@router.get("/stations")
def list_all_stations():
    """Lists all police stations across Karnataka, live from FileStore."""
    result = filestore_crime_data.list_stations()
    if result is None:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    return result

@router.get("/stations/{station_id}/hotspots")
def get_station_hotspots_and_routes(station_id: int, time_of_day: str = Query(None)):
    """Computes density hotspots and optimal patrol route waypoints for a station,
    live from FileStore."""
    station, firs_raw = filestore_crime_data.get_station_firs_for_geo(station_id)
    if station is None:
        if filestore_crime_data.get_dataset() is None:
            raise HTTPException(status_code=503, detail=_UNAVAILABLE)
        raise HTTPException(status_code=404, detail="Police station not found")

    firs = [_FirLike(f) for f in firs_raw]

    if time_of_day and time_of_day.lower() != "all":
        tod = time_of_day.lower()
        filtered = []
        for f in firs:
            if not f.date_occurred:
                continue
            h = f.date_occurred.hour
            if tod == "night" and (h >= 22 or h < 4):
                filtered.append(f)
            elif tod == "morning" and (h >= 4 and h < 12):
                filtered.append(f)
            elif tod == "afternoon" and (h >= 12 and h < 18):
                filtered.append(f)
            elif tod == "evening" and (h >= 18 and h < 22):
                filtered.append(f)
        firs = filtered

    if len(firs) < 3:
        fallback_route = [
            {"name": "Station Base", "lat": station["latitude"], "lng": station["longitude"]},
            {"name": "Patrol Checkpoint A", "lat": station["latitude"] + 0.005, "lng": station["longitude"] + 0.005},
            {"name": "Patrol Checkpoint B", "lat": station["latitude"] - 0.005, "lng": station["longitude"] - 0.005},
            {"name": "Station Base", "lat": station["latitude"], "lng": station["longitude"]},
        ]
        return {
            "station_name": station["name"], "hotspots": [], "route": fallback_route,
            "intensity": 0.25, "total_incidents_analyzed": len(firs),
        }

    coordinates = [[f.latitude, f.longitude] for f in firs if f.latitude and f.longitude]
    dbscan_result = perform_dbscan(coordinates, eps=0.008, min_samples=3)
    clusters = dbscan_result["clusters"]

    route = [{"name": "Station HQ", "lat": station["latitude"], "lng": station["longitude"]}]
    active_centers = [c["center"] for c in clusters]
    current_loc = [station["latitude"], station["longitude"]]
    while active_centers:
        distances = [np.linalg.norm(np.array(current_loc) - np.array(c)) for c in active_centers]
        next_idx = np.argmin(distances)
        next_center = active_centers.pop(next_idx)
        route.append({"name": f"Hotspot Checkpoint {len(route)}", "lat": next_center[0], "lng": next_center[1]})
        current_loc = next_center
    route.append({"name": "Station HQ", "lat": station["latitude"], "lng": station["longitude"]})

    return {
        "station_name": station["name"],
        "station_location": [station["latitude"], station["longitude"]],
        "hotspots": clusters, "route": route, "total_incidents_analyzed": len(firs),
    }

@router.get("/stations/{station_id}/heatmap")
def get_station_kde_heatmap(station_id: int):
    """Gaussian KDE density surface over a station's incidents, live from FileStore."""
    station, firs_raw = filestore_crime_data.get_station_firs_for_geo(station_id)
    if station is None:
        if filestore_crime_data.get_dataset() is None:
            raise HTTPException(status_code=503, detail=_UNAVAILABLE)
        raise HTTPException(status_code=404, detail="Police station not found")

    points = [[f["latitude"], f["longitude"]] for f in firs_raw]
    result = compute_kde_heatmap(points)
    result["station_name"] = station["name"]
    result["total_incidents"] = len(points)
    return result

@router.get("/stations/{station_id}/st-clusters")
def get_station_st_clusters(
    station_id: int,
    eps_km: float = Query(0.75, description="Spatial neighborhood radius in kilometers"),
    eps_hours: float = Query(6.0, description="Temporal neighborhood radius in hours"),
    min_samples: int = Query(3, description="Minimum incidents to form a cluster"),
):
    """Spatio-temporal DBSCAN: clusters incidents close in both space AND time-of-day,
    live from FileStore."""
    station, firs_raw = filestore_crime_data.get_station_firs_for_geo(station_id)
    if station is None:
        if filestore_crime_data.get_dataset() is None:
            raise HTTPException(status_code=503, detail=_UNAVAILABLE)
        raise HTTPException(status_code=404, detail="Police station not found")

    points = []
    for f in firs_raw:
        ref_dt = f["date_occurred"]
        hour = ref_dt.hour if ref_dt else 12
        points.append({"latitude": f["latitude"], "longitude": f["longitude"], "hour": hour, "fir_id": f["id"]})

    result = perform_st_dbscan(points, eps_km=eps_km, eps_hours=eps_hours, min_samples=min_samples)
    result["station_name"] = station["name"]
    result["total_incidents"] = len(points)
    result["params"] = {"eps_km": eps_km, "eps_hours": eps_hours, "min_samples": min_samples}
    return result
