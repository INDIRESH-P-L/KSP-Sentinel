from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io
import csv
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from backend.app.database.session import get_db
from backend.app.database.models import District, PoliceStation, FIR

router = APIRouter(prefix="/export", tags=["Reports Export"])

@router.get("/csv/district-report")
def export_district_report(db: Session = Depends(get_db)):
    """Generates a downloadable CSV report of district statistics"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write headers
    writer.writerow(["District Name", "Population", "Risk Score", "Risk Factors"])
    
    # Query districts
    districts = db.query(District).all()
    for d in districts:
        writer.writerow([d.name, d.population, d.risk_score, d.risk_factors or "None"])
        
    output.seek(0)
    
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=ksp_district_risk_report.csv"
    return response

@router.get("/csv/crime-records")
def export_crime_records(station_id: int = None, db: Session = Depends(get_db)):
    """Generates a CSV export of detailed FIR incident records"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["FIR Number", "Police Station", "District", "Subcategory", "Date Reported", "Status", "Latitude", "Longitude"])
    
    query = db.query(FIR)
    if station_id:
        query = query.filter(FIR.police_station_id == station_id)
        
    firs = query.all()
    for f in firs:
        writer.writerow([
            f.fir_number,
            f.station.name if f.station else "N/A",
            f.station.district.name if (f.station and f.station.district) else "N/A",
            f.subcategory.name if f.subcategory else "N/A",
            f.date_reported.strftime("%Y-%m-%d %H:%M:%S") if f.date_reported else "N/A",
            f.status,
            f.latitude,
            f.longitude
        ])
        
    output.seek(0)
    
    filename = f"ksp_crime_records_station_{station_id}.csv" if station_id else "ksp_crime_records_all.csv"
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response
