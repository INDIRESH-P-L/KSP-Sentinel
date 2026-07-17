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

@router.post("/sync-to-catalyst")
def sync_to_catalyst(db: Session = Depends(get_db)):
    """Synchronizes local SQLite database tables to Zoho Catalyst Datastore"""
    from datetime import datetime, date
    from sqlalchemy import text
    
    try:
        from backend.app.database.catalyst_db import CatalystDatabase
        cat_db = CatalystDatabase()
    except Exception as e:
        return {"status": "error", "message": f"Failed to initialize Catalyst SDK: {str(e)}"}
        
    tables_to_sync = [
        "districts", "taluks", "police_stations", 
        "crime_categories", "crime_subcategories", 
        "fir_cases", "accused", "fir_accused", 
        "arrests", "investigations", "chargesheets", 
        "convictions", "officers", "crime_review_monthly", 
        "crime_review_yearly", "crime_statistics"
    ]
    
    results = {}
    for table_name in tables_to_sync:
        try:
            # Query row count
            count_res = db.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            if not count_res:
                results[table_name] = "0 rows (skipped)"
                continue
                
            # Fetch all rows
            rows_res = db.execute(text(f"SELECT * FROM {table_name}"))
            colnames = list(rows_res.keys())
            rows = rows_res.fetchall()
            
            # Fetch table reference from Catalyst
            catalyst_table = cat_db.get_table(table_name)
            
            # Prepare batch upload
            batch_size = 100
            inserted = 0
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i+batch_size]
                cleaned_batch = []
                for row in batch:
                    row_dict = {}
                    for col, val in zip(colnames, row):
                        if val is None:
                            continue
                        # Catalyst expects boolean type for boolean columns
                        if table_name == "accused" and col in ["repeat_offender", "history_sheet"]:
                            row_dict[col] = bool(val)
                        elif isinstance(val, (datetime, date)):
                            row_dict[col] = val.strftime("%Y-%m-%d %H:%M:%S")
                        elif isinstance(val, str) and (col.endswith("_date") or col.startswith("date_") or col == "created_at"):
                            # If date is stored as string in SQLite, parse and clean it
                            try:
                                clean_val = val.split(".")[0]
                                dt = datetime.strptime(clean_val, "%Y-%m-%d %H:%M:%S")
                                row_dict[col] = dt.strftime("%Y-%m-%d %H:%M:%S")
                            except Exception:
                                row_dict[col] = val
                        else:
                            row_dict[col] = val
                    cleaned_batch.append(row_dict)
                
                catalyst_table.insert_rows(cleaned_batch)
                inserted += len(cleaned_batch)
                
            results[table_name] = f"Synced {inserted} / {len(rows)} rows"
        except Exception as e:
            results[table_name] = f"Error: {str(e)}"
            
    return {"status": "success", "results": results}

