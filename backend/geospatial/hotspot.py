from sqlalchemy.orm import Session
import sys
import os
import numpy as np

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from app.database.models import FIR, PoliceStation
from clustering.dbscan import perform_dbscan
from clustering.st_dbscan import perform_st_dbscan
from geospatial.kde import compute_kde_heatmap

class GeospatialHotspotAnalyzer:
    def __init__(self, db: Session):
        self.db = db

    def _get_station_firs(self, police_station_id: int):
        station = self.db.query(PoliceStation).filter(PoliceStation.id == police_station_id).first()
        if not station:
            return None, []
        firs = self.db.query(FIR).filter(
            FIR.police_station_id == police_station_id,
            FIR.latitude.isnot(None),
            FIR.longitude.isnot(None),
        ).all()
        return station, firs

    def get_kde_heatmap(self, police_station_id: int):
        """Real Gaussian KDE density surface over a station's incidents, for a genuine
        heatmap layer rather than translucent circles standing in for density."""
        station, firs = self._get_station_firs(police_station_id)
        if not station:
            return {"error": "Police station not found"}

        points = [[f.latitude, f.longitude] for f in firs]
        result = compute_kde_heatmap(points)
        result["station_name"] = station.name
        result["total_incidents"] = len(points)
        return result

    def get_st_clusters(self, police_station_id: int, eps_km: float = 0.75, eps_hours: float = 6.0, min_samples: int = 3):
        """Spatio-temporal DBSCAN: clusters incidents that are close in BOTH space and
        time-of-day, e.g. separating a 6-9pm chain-snatching hotspot from an unrelated
        cluster of incidents at the same street corner at 3am."""
        station, firs = self._get_station_firs(police_station_id)
        if not station:
            return {"error": "Police station not found"}

        points = []
        for f in firs:
            ref_dt = f.date_occurred or f.date_reported
            hour = ref_dt.hour if ref_dt else 12
            points.append({"latitude": f.latitude, "longitude": f.longitude, "hour": hour, "fir_id": f.id})

        result = perform_st_dbscan(points, eps_km=eps_km, eps_hours=eps_hours, min_samples=min_samples)
        result["station_name"] = station.name
        result["total_incidents"] = len(points)
        result["params"] = {"eps_km": eps_km, "eps_hours": eps_hours, "min_samples": min_samples}
        return result

    def get_station_hotspots_and_routes(self, police_station_id: int, time_of_day: str = None):
        """Finds dense crime hotspots for a station and outlines a recommended patrol path"""
        # Fetch FIRs for this station
        firs_query = self.db.query(FIR).filter(FIR.police_station_id == police_station_id)
        station = self.db.query(PoliceStation).filter(PoliceStation.id == police_station_id).first()
        
        if not station:
            return {"error": "Police station not found"}
            
        firs = firs_query.all()
        
        # Apply time of day filter if provided
        if time_of_day and time_of_day.lower() != "all":
            filtered = []
            tod = time_of_day.lower()
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
            # Fallback path around station if too few cases
            fallback_route = [
                {"name": "Station Base", "lat": station.latitude, "lng": station.longitude},
                {"name": "Patrol Checkpoint A", "lat": station.latitude + 0.005, "lng": station.longitude + 0.005},
                {"name": "Patrol Checkpoint B", "lat": station.latitude - 0.005, "lng": station.longitude - 0.005},
                {"name": "Station Base", "lat": station.latitude, "lng": station.longitude}
            ]
            return {
                "station_name": station.name,
                "hotspots": [],
                "route": fallback_route,
                "intensity": 0.25,
                "total_incidents_analyzed": len(firs)
            }
            
        coordinates = [[f.latitude, f.longitude] for f in firs if f.latitude and f.longitude]
        
        # Cluster coordinates using DBSCAN
        dbscan_result = perform_dbscan(coordinates, eps=0.008, min_samples=3)
        clusters = dbscan_result["clusters"]
        
        # Build patrol route by sorting cluster centers from the station base (TSP approximation)
        route = [{"name": "Station HQ", "lat": station.latitude, "lng": station.longitude}]
        
        active_centers = [c["center"] for c in clusters]
        current_loc = [station.latitude, station.longitude]
        
        # Sort centers by distance (Nearest Neighbor) to outline a loop
        while active_centers:
            distances = [np.linalg.norm(np.array(current_loc) - np.array(c)) for c in active_centers]
            next_idx = np.argmin(distances)
            next_center = active_centers.pop(next_idx)
            route.append({
                "name": f"Hotspot Checkpoint {len(route)}",
                "lat": next_center[0],
                "lng": next_center[1]
            })
            current_loc = next_center
            
        # Return to base
        route.append({"name": "Station HQ", "lat": station.latitude, "lng": station.longitude})
        
        return {
            "station_name": station.name,
            "station_location": [station.latitude, station.longitude],
            "hotspots": clusters,
            "route": route,
            "total_incidents_analyzed": len(firs)
        }
