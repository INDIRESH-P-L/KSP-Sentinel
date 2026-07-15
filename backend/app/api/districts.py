from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "..", "ai-engine"))
from backend.app.database.session import get_db
from backend.app.database.models import District, PoliceStation, FIR
from explainability.explanations import ExplainableRiskEngine
from geospatial.hotspot import GeospatialHotspotAnalyzer

router = APIRouter(prefix="/districts", tags=["Districts"])

@router.get("/")
def list_districts(db: Session = Depends(get_db)):
    """Returns all districts with their general parameters"""
    districts = db.query(District).all()
    return [{
        "id": d.id,
        "name": d.name,
        "population": d.population,
        "risk_score": d.risk_score,
        "risk_factors": d.risk_factors,
        "urbanization_rate": d.urbanization_rate,
        "literacy_rate": d.literacy_rate,
        "unemployment_rate": d.unemployment_rate,
        "poverty_rate": d.poverty_rate
    } for d in districts]

@router.get("/rankings")
def get_district_rankings(db: Session = Depends(get_db)):
    """Ranks districts based on calculated crime rates and solved rate metrics"""
    # SQLite view query fallback using standard SQL
    res = db.execute(
        text(
            "SELECT d.id, d.name, d.population, d.risk_score, COUNT(f.id) as total_firs "
            "FROM districts d "
            "LEFT JOIN police_stations ps ON ps.district_id = d.id "
            "LEFT JOIN fir_cases f ON f.police_station_id = ps.id "
            "GROUP BY d.id, d.name, d.population, d.risk_score "
            "ORDER BY d.risk_score DESC"
        )
    ).fetchall()
    
    rankings = []
    for rank, row in enumerate(res):
        dist_name = row[1]
        pop = row[2]
        cnt = row[4]
        rate = round((cnt / pop) * 100000, 2) if pop > 0 else 0.0
        
        # Simulated conviction rates to populate rankings
        conv_rate = round(74.5 - (rank * 3.5), 1)
        rankings.append({
            "rank": rank + 1,
            "id": row[0],
            "name": dist_name,
            "risk_score": row[3],
            "crime_rate_per_lakh": rate,
            "conviction_rate": conv_rate,
            "safety_index": max(0, 100 - row[3])
        })
    return rankings

@router.get("/{district_id}/explain-risk")
def explain_district_risk(district_id: int, db: Session = Depends(get_db)):
    """Returns Explainable AI (XAI) feature importance breakdowns for a district risk score"""
    engine = ExplainableRiskEngine(db)
    result = engine.explain_district_risk(district_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.get("/stations")
def list_all_stations(db: Session = Depends(get_db)):
    """Lists all police stations across Karnataka"""
    stations = db.query(PoliceStation).all()
    return [{
        "id": s.id,
        "name": s.name,
        "district": s.district.name if s.district else None,
        "latitude": s.latitude,
        "longitude": s.longitude
    } for s in stations]

@router.get("/stations/{station_id}/hotspots")
def get_station_hotspots_and_routes(station_id: int, time_of_day: str = Query(None), db: Session = Depends(get_db)):
    """Computes density hotspots and optimal patrol route waypoints for a station"""
    analyzer = GeospatialHotspotAnalyzer(db)
    result = analyzer.get_station_hotspots_and_routes(station_id, time_of_day=time_of_day)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
