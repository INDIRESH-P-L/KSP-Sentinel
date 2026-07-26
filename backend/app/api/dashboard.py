from fastapi import APIRouter, Depends, HTTPException
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app.core.security import deny_admin_from_crime_data
from app import filestore_crime_data

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

_UNAVAILABLE = "Crime data is unavailable: could not reach Catalyst FileStore."

@router.get("/kpis")
async def get_dashboard_kpis():
    """Returns top executive KPIs (Total FIRs, growth rate, arrests, conviction rate).
    Sourced live from Catalyst FileStore -- see app/filestore_crime_data.py; no
    Datastore fallback."""
    result = filestore_crime_data.get_dashboard_kpis()
    if result is None:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    return result

@router.get("/charts/monthly-trends")
async def get_monthly_trends():
    """Returns crime frequency aggregated by month for the past year, live from FileStore."""
    result = filestore_crime_data.get_monthly_trends()
    if result is None:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    return result

@router.get("/top-districts")
async def get_top_districts():
    """Returns top 5 districts by crime count, live from FileStore."""
    result = filestore_crime_data.get_top_districts()
    if result is None:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    return result

@router.get("/hot-stations")
async def get_hot_stations():
    """Returns top 5 police stations by crime count, live from FileStore."""
    result = filestore_crime_data.get_hot_stations()
    if result is None:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    return result

@router.get("/socio-economic")
async def get_socio_economic_correlations():
    """Pearson correlation coefficients between district socio-demographics and
    per-category crime rates, live from FileStore."""
    result = filestore_crime_data.get_socio_economic()
    if result is None:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    return result

@router.get("/anomalies")
async def get_anomaly_alerts():
    """Scans monthly crime aggregates and detects events deviating from baseline by
    standard deviations, live from FileStore."""
    result = filestore_crime_data.get_anomalies()
    if result is None:
        raise HTTPException(status_code=503, detail=_UNAVAILABLE)
    return result
