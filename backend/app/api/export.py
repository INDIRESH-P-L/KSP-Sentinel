from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io
import csv
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from app.database.session import get_db
from app.database.models import District, PoliceStation, FIR, EvidenceItem
from app.core.security import require_token_role, scope_to_user_district
from app.services.evidence import log_evidence_action

router = APIRouter(prefix="/export", tags=["Reports Export"])


def _evidence_by_fir(db: Session, fir_ids):
    """Evidence items grouped by fir_id, fetched in one query (no N+1)."""
    if not fir_ids:
        return {}
    rows = (db.query(EvidenceItem)
              .filter(EvidenceItem.fir_id.in_(list(fir_ids)))
              .order_by(EvidenceItem.fir_id, EvidenceItem.id).all())
    grouped = {}
    for r in rows:
        grouped.setdefault(r.fir_id, []).append(r)
    return grouped


def _log_exported(db: Session, items, actor: str, detail: str):
    """Writes one 'exported' custody row per evidence item that actually left the
    system in this response.

    Only ever called with the items genuinely included in the payload -- logging an
    export for evidence that wasn't in the file would put a false entry in a trail
    a court may rely on. No bytes are read here (file_reference is an opaque
    pointer), so each row records verification='not_verified' rather than implying
    an integrity check that never happened.
    """
    for item in items:
        log_evidence_action(db, item, accessed_by=actor, action="exported",
                            detail=detail, commit=False)
    if items:
        db.commit()

@router.get("/csv/district-report")
def export_district_report(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_token_role("analyst")),
):
    """Generates a downloadable CSV report of district statistics.

    Analyst clearance and a real token. require_token_role (not require_role) because
    get_current_user() falls back to a permissive "Investigator" identity when no token
    is presented -- under plain require_role an anonymous request would sail through
    while genuine Analysts were the only callers actually blocked. The frontend fetches
    this via authFetch and saves the blob, so the download carries a token.
    """
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
def export_crime_records(
    station_id: int = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_token_role("analyst")),
    scoped_district_id: int = Depends(scope_to_user_district),
):
    """Generates a CSV export of detailed FIR incident records.

    Analyst clearance and a real token, matching what GET /api/crimes/ allows. The
    frontend fetches this via authFetch and saves the blob, so it carries a token.

    District scoping is applied here for the same reason it is on GET /api/crimes/:
    without it an Analyst restricted to one district could pull every district's FIRs
    in bulk through the export instead, which made the scope on the list endpoint
    decorative.

    Carries no evidence data -- evidence leaves the system through
    /csv/evidence-manifest below, which writes chain-of-custody rows.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(["FIR Number", "Police Station", "District", "Subcategory", "Date Reported", "Status", "Latitude", "Longitude"])
    
    query = db.query(FIR)
    if station_id:
        query = query.filter(FIR.police_station_id == station_id)
    if scoped_district_id is not None:
        query = (query.join(PoliceStation, FIR.police_station_id == PoliceStation.id)
                      .filter(PoliceStation.district_id == scoped_district_id))

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
def sync_to_catalyst(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_token_role("superintendent")),
):
    """Synchronizes local SQLite database tables to Zoho Catalyst Datastore.

    Superintendent clearance: this pushes 16 tables of crime data -- FIRs, accused,
    arrests, convictions -- to an external cloud datastore. That is the highest-impact
    operation on this router and was previously callable by anyone who could reach the
    port.
    """
    from datetime import datetime, date
    from sqlalchemy import text
    
    try:
        from app.database.catalyst_db import CatalystDatabase
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


@router.get("/filestore/files")
def list_filestore_files(current_user: dict = Depends(require_token_role("superintendent"))):
    """Lists files in the Catalyst File Store folder 'ksp'.

    Superintendent clearance: exposes the contents of the project's external object
    storage.
    """
    import subprocess
    import requests
    
    try:
        # Decrypt token
        node_cmd = "node -e \"const Credential = require('/usr/lib/node_modules/zcatalyst-cli/lib/authentication/credential.js').default; const fs = require('fs'); const config = JSON.parse(fs.readFileSync('/home/keshav/.config/zcatalyst-cli-nodejs/zcatalyst-cli-v1.json', 'utf8')); console.log(Credential.decrypt(config.in.credential).access_token);\""
        res = subprocess.run(node_cmd, shell=True, capture_output=True, text=True)
        access_token = res.stdout.strip()
        
        project_id = "48446000000013048"
        folder_id = "48446000000036421"
        org_id = "60078436924"
        
        url = f"https://api.catalyst.zoho.in/baas/v1/project/{project_id}/folder/{folder_id}/file"
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Catalyst-org": org_id,
            "Environment": "Development"
        }
        
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            return r.json()
        else:
            raise HTTPException(status_code=r.status_code, detail=r.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/filestore/import")
def trigger_filestore_import(
    file_id: str,
    table_name: str,
    operation: str = "insert",
    find_by: str = None,
    current_user: dict = Depends(require_token_role("superintendent")),
):
    """Triggers a bulk write job by calling the deployed Catalyst function.

    Superintendent clearance: this writes arbitrary rows into a named table from an
    uploaded file, so it is a data-mutation path, not a read.
    """
    import requests
    
    function_url = "https://ksp-sentinel-60078436924.development.catalystserverless.in/server/ksp_sentinel_function/bulkwrite"
    params = {
        "file_id": file_id,
        "table_name": table_name,
        "operation": operation
    }
    if find_by:
        params["find_by"] = find_by
        
    try:
        r = requests.get(function_url, params=params)
        if r.status_code == 200:
            return r.json()
        else:
            raise HTTPException(status_code=r.status_code, detail=r.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/csv/evidence-manifest")
def export_evidence_manifest(
    fir_id: int = Query(None, gt=0, description="Limit to one case; omit for all cases"),
    station_id: int = Query(None, gt=0, description="Limit to cases at one police station"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_token_role("investigator")),
):
    """Exports the digital-evidence manifest as CSV and records the export in the
    chain of custody.

    One 'exported' row is written per item that actually appears in the file -- the
    trail must reflect what left the system, not what was asked for.

    The manifest carries evidence *metadata* only: file_reference is an opaque
    pointer and this service never holds the bytes, so nothing here is the evidence
    itself. `Integrity Flagged` is included as a first-class column so a compromised
    item cannot be exported without that fact travelling with it.

    Investigator clearance or above -- unlike the other exports on this router, this
    one carries evidence data.
    """
    query = db.query(EvidenceItem)
    if fir_id:
        query = query.filter(EvidenceItem.fir_id == fir_id)
    if station_id:
        fir_ids = [f.id for f in db.query(FIR.id).filter(FIR.police_station_id == station_id).all()]
        query = query.filter(EvidenceItem.fir_id.in_(fir_ids or [-1]))

    items = query.order_by(EvidenceItem.fir_id, EvidenceItem.id).all()

    fir_numbers = {}
    if items:
        ids = {i.fir_id for i in items}
        fir_numbers = {f.id: f.fir_number for f in db.query(FIR).filter(FIR.id.in_(ids)).all()}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Evidence ID", "FIR ID", "FIR Number", "Item Type", "File Reference", "Description",
        "Added By", "Added At", "Current Custodian", "Content Hash (SHA-256)",
        "Integrity Flagged", "Integrity Flagged At",
    ])
    for it in items:
        writer.writerow([
            it.id,
            it.fir_id,
            fir_numbers.get(it.fir_id, "N/A"),
            it.item_type,
            it.file_reference,
            it.description or "",
            it.added_by,
            it.added_at.strftime("%Y-%m-%d %H:%M:%S") if it.added_at else "N/A",
            it.current_custodian,
            it.content_hash or "",
            "YES" if it.integrity_flagged else "no",
            it.integrity_flagged_at.strftime("%Y-%m-%d %H:%M:%S") if it.integrity_flagged_at else "",
        ])

    scope = f"fir_id={fir_id}" if fir_id else (f"station_id={station_id}" if station_id else "all cases")
    _log_exported(db, items, actor=str(current_user.get("username") or "unknown"),
                  detail=f"Evidence manifest CSV exported ({scope})")

    output.seek(0)
    filename = f"ksp_evidence_manifest_fir_{fir_id}.csv" if fir_id else "ksp_evidence_manifest.csv"
    response = StreamingResponse(iter([output.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["X-Evidence-Items-Exported"] = str(len(items))
    response.headers["X-Custody-Rows-Written"] = str(len(items))
    return response
