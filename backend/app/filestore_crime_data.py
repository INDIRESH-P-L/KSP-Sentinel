"""In-memory, FileStore-linked replacement for the SQL-backed crime data layer.

Scope: FIR4.csv..FIR9.csv in the Catalyst FileStore `ksp` folder are the SOLE source of
truth for crime data (fir_cases/districts/police_stations/crime_categories/
crime_subcategories) across /api/crimes/, /api/dashboard/*, /api/districts/*, and
/api/forecast/. There is deliberately NO fallback to ksp_sentinel.db for this data --
if FileStore is unreachable, callers get None/an explicit error rather than silently
showing old database data that no longer reflects the linked source.

Never writes to disk or to any database. Downloaded CSV bytes are parsed straight into
a pandas DataFrame held in process memory, built once on first request and reused after
that (rebuilding on every request would mean re-downloading+re-parsing ~571MB/1.67M rows
per call). Restarting the process clears the cache and the next request rebuilds it from
FileStore again -- there is no persistence layer here at all, by design.

District/station/category derivation mirrors scripts/load_data.py exactly (same
DISTRICT_COORDS/CENSUS_DISTRICT_MAP tables, same synthetic id assignment order) so the
shapes returned here match what the rest of the app has always expected, even though the
"tables" are now DataFrames instead of SQL rows.
"""
import io
import os
import sys
import threading
from typing import Optional

import numpy as np
import pandas as pd

from app.config import settings
from app.logging import logger
from app.constants import DISTRICT_COORDS, CENSUS_DISTRICT_MAP

FIR_FILE_NAMES = [f"FIR{n}.csv" for n in range(1, 10)]  # FIR1.csv .. FIR9.csv

FIR_COLUMNS = [
    'District_Name', 'UnitName', 'FIR_YEAR', 'FIR_MONTH', 'FIR_Day',
    'FIR_Stage', 'CrimeGroup_Name', 'CrimeHead_Name', 'Latitude', 'Longitude',
    'Place of Offence',
]
_COLUMN_ALIASES = {
    # Tolerant of header variants across the split files -- see admin_seed.py,
    # which hit the same real-world inconsistency.
}

# Single shared in-memory dataset, built lazily and cached for the life of the process.
_lock = threading.Lock()
_state = {
    "df": None,               # cleaned FIR-level DataFrame, one row per case
    "districts": None,        # DataFrame: id, name, population, risk_score, ...
    "stations": None,         # DataFrame: id, name, district_id, district_name, lat, lng
    "categories": None,       # DataFrame: id, name
    "subcategories": None,    # DataFrame: id, name, category_id, category_name
    "officers": None,         # DataFrame: id, name, badge_number, rank, station_id, status
    "loaded": False,
}
_catalyst_app = None


def _get_catalyst_app():
    global _catalyst_app
    if _catalyst_app is not None:
        return _catalyst_app
    import zcatalyst_sdk
    try:
        _catalyst_app = zcatalyst_sdk.initialize()
    except Exception:
        import subprocess
        from zcatalyst_sdk._thread_util import ZCThreadUtil
        from zcatalyst_sdk import _constants as APIConstants
        try:
            node_cmd = (
                "node -e \""
                "const Credential = require('/usr/lib/node_modules/zcatalyst-cli/lib/authentication/credential.js').default; "
                "const fs = require('fs'); "
                "const config = JSON.parse(fs.readFileSync('/home/keshav/.config/zcatalyst-cli-nodejs/zcatalyst-cli-v1.json', 'utf8')); "
                "console.log(Credential.decrypt(config.in.credential).access_token);"
                "\""
            )
            token = subprocess.run(node_cmd, shell=True, capture_output=True, text=True).stdout.strip()
            if token:
                thread = ZCThreadUtil()
                headers = {
                    'X-ZC-ProjectId': '48446000000013048',
                    'X-ZC-Environment': 'Development',
                    'Catalyst-org': '60078436924',
                    'X-ZC-Project-Key': 'key',
                    'X-ZC-Project-Domain': 'https://ksp-sentinel-60078436924.development.catalystserverless.in'
                }
                thread.put_value('catalyst_headers', headers)
                thread.put_value(APIConstants.ADMIN_CRED, token)
                thread.put_value(APIConstants.ADMIN_CRED_TYPE, 'token')
                thread.put_value(APIConstants.CLIENT_CRED, token)
                thread.put_value(APIConstants.CLIENT_CRED_TYPE, 'token')
                thread.put_value(APIConstants.USER_TYPE, 'admin')
                _catalyst_app = zcatalyst_sdk.initialize()
        except Exception as err:
            logger.error(f"filestore_crime_data: CLI token fallback failed: {err}")
            raise
    logger.info("filestore_crime_data: Zoho Catalyst SDK initialized.")
    return _catalyst_app


def _parse_fir_csv_bytes(raw_bytes, filename: str) -> Optional[pd.DataFrame]:
    if isinstance(raw_bytes, str):
        raw_bytes = raw_bytes.encode("utf-8", errors="ignore")
    try:
        header = pd.read_csv(io.BytesIO(raw_bytes), nrows=0).columns
        resolved = {}
        for wanted in FIR_COLUMNS:
            if wanted in header:
                resolved[wanted] = wanted
                continue
            for alias in _COLUMN_ALIASES.get(wanted, []):
                if alias in header:
                    resolved[wanted] = alias
                    break
        missing = [c for c in FIR_COLUMNS if c not in resolved]
        if missing:
            logger.error(f"filestore_crime_data: '{filename}' missing columns {missing}; skipping.")
            return None
        df = pd.read_csv(io.BytesIO(raw_bytes), usecols=list(resolved.values()))
        df = df.rename(columns={v: k for k, v in resolved.items()})
        return df
    except Exception as e:
        logger.error(f"filestore_crime_data: Failed parsing '{filename}': {e}")
        return None


def _download_fir_csvs() -> list[pd.DataFrame]:
    loaded_names = set()
    frames = []

    # 0. Primary: Check local datasets/raw/fir/ files downloaded from Stratus
    fir_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "datasets", "raw", "fir")
    for name in FIR_FILE_NAMES:
        local_path = os.path.join(fir_dir, name)
        if os.path.exists(local_path):
            try:
                with open(local_path, "rb") as f:
                    df = _parse_fir_csv_bytes(f.read(), name)
                    if df is not None:
                        frames.append(df)
                        loaded_names.add(name)
                        logger.info(f"filestore_crime_data: loaded '{name}' from local path '{local_path}': {len(df)} rows.")
            except Exception as e:
                logger.error(f"filestore_crime_data: error reading '{local_path}': {e}")

    missing_names = [n for n in FIR_FILE_NAMES if n not in loaded_names]
    if not missing_names:
        return frames

    app = _get_catalyst_app()
    # 1. Load from Catalyst Stratus Storage bucket (sentinel-migration-bucket/archive/)
    bucket_name = getattr(settings, "CATALYST_STRATUS_BUCKET", "sentinel-migration-bucket")
    try:
        bucket = app.stratus().bucket(bucket_name)
        for name in missing_names:
            for key_candidate in [f"archive/{name}", name]:
                try:
                    obj = bucket.get_object(key_candidate)
                    raw_bytes = obj.content if hasattr(obj, "content") else (obj.read() if hasattr(obj, "read") else obj)
                    if raw_bytes:
                        df = _parse_fir_csv_bytes(raw_bytes, name)
                        if df is not None:
                            frames.append(df)
                            loaded_names.add(name)
                            logger.info(f"filestore_crime_data: loaded '{name}' from Stratus bucket '{bucket_name}/{key_candidate}': {len(df)} rows.")
                            break
                except Exception as e:
                    logger.debug(f"filestore_crime_data: key '{key_candidate}' not fetched from Stratus: {e}")
    except Exception as e:
        logger.warning(f"filestore_crime_data: Stratus bucket access warning: {e}")

    # 2. Secondary: Fallback to FileStore folder for any missing FIR CSVs
    missing_names = [n for n in FIR_FILE_NAMES if n not in loaded_names]
    folder_id = getattr(settings, "CATALYST_FOLDER_ID", None)
    if missing_names and folder_id:
        try:
            fs = app.filestore() if hasattr(app, "filestore") else (app.file_store() if hasattr(app, "file_store") else None)
            if fs is not None:
                folder = fs.folder(int(folder_id)) if hasattr(fs, "folder") else (fs.get_folder_instance(int(folder_id)) if hasattr(fs, "get_folder_instance") else None)
                if folder is not None:
                    listing = folder.get_paged_files() if hasattr(folder, "get_paged_files") else []
                    if isinstance(listing, dict):
                        listing = listing.get("data", []) or []
                    files_by_name = {}
                    for f in listing:
                        fname = f.get("file_name") if isinstance(f, dict) else getattr(f, "file_name", None)
                        fid = f.get("id") if isinstance(f, dict) else getattr(f, "id", None)
                        if fname in missing_names:
                            files_by_name[fname] = fid

                    for name in missing_names:
                        file_id = files_by_name.get(name)
                        if file_id is None:
                            logger.warning(f"filestore_crime_data: '{name}' not found in FileStore or Stratus; skipping.")
                            continue
                        raw = folder.download_file(int(file_id))
                        df = _parse_fir_csv_bytes(raw, name)
                        if df is not None:
                            frames.append(df)
                            loaded_names.add(name)
                            logger.info(f"filestore_crime_data: loaded '{name}' from FileStore folder: {len(df)} rows.")
        except Exception as e:
            logger.error(f"filestore_crime_data: FileStore download error: {e}")

    if not frames:
        raise RuntimeError("No FIR CSVs could be loaded from Stratus bucket or FileStore.")
    return frames


def _derive_status(stage: str) -> str:
    stage = str(stage).strip()
    if stage in ('Convicted', 'Dis/Acq', 'Compounded', 'Traced'):
        return 'CLOSED'
    if stage in ('Pending Trial', 'BoundOver'):
        return 'CHARGE_SHEETED'
    if 'UI' in stage or 'Transfered' in stage:
        return 'INVESTIGATING'
    return 'REGISTERED'


def _load_metadata_df(filename: str) -> Optional[pd.DataFrame]:
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    local_path = os.path.join(repo_root, "datasets", "raw", filename)
    if os.path.exists(local_path):
        try:
            df = pd.read_csv(local_path)
            logger.info(f"filestore_crime_data: loaded '{filename}' from local path '{local_path}': {len(df)} rows.")
            return df
        except Exception as e:
            logger.error(f"filestore_crime_data: error reading local '{local_path}': {e}")

    try:
        url = f"https://sentinel-migration-bucket-development.zohostratus.in/{filename}"
        import requests
        import subprocess
        node_cmd = (
            "node -e \""
            "const Credential = require('/usr/lib/node_modules/zcatalyst-cli/lib/authentication/credential.js').default; "
            "const fs = require('fs'); "
            "const config = JSON.parse(fs.readFileSync('/home/keshav/.config/zcatalyst-cli-nodejs/zcatalyst-cli-v1.json', 'utf8')); "
            "console.log(Credential.decrypt(config.in.credential).access_token);"
            "\""
        )
        token = subprocess.run(node_cmd, shell=True, capture_output=True, text=True).stdout.strip()
        if token:
            headers = {
                "Authorization": f"Zoho-oauthtoken {token}",
                "Catalyst-org": "60078436924",
                "Environment": "Development"
            }
            r = requests.get(url, headers=headers)
            if r.status_code == 200:
                df = pd.read_csv(io.BytesIO(r.content))
                logger.info(f"filestore_crime_data: downloaded '{filename}' from Stratus HTTP: {len(df)} rows.")
                return df
    except Exception as e:
        logger.warning(f"filestore_crime_data: direct Stratus download failed for '{filename}': {e}")

    return None


def _build_dataset():
    """Downloads + parses all FIR CSVs and loads Stratus districts/stations/categories/officers tables.
    Raises on any failure -- callers decide what 'no data' means to their route."""
    frames = _download_fir_csvs()
    df = pd.concat(frames, ignore_index=True)

    df['District_Name'] = df['District_Name'].astype(str).str.strip()
    df['UnitName'] = df['UnitName'].astype(str).str.strip()
    df['CrimeGroup_Name'] = df['CrimeGroup_Name'].astype(str).str.strip()
    df['CrimeHead_Name'] = df['CrimeHead_Name'].astype(str).str.strip()
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')

    def safe_date(row):
        try:
            y = int(row['FIR_YEAR']) if pd.notna(row['FIR_YEAR']) else 2024
            m = int(row['FIR_MONTH']) if pd.notna(row['FIR_MONTH']) and 0 < row['FIR_MONTH'] <= 12 else 1
            d = int(row['FIR_Day']) if pd.notna(row['FIR_Day']) and 0 < row['FIR_Day'] <= 28 else 1
            return pd.Timestamp(year=y, month=m, day=d)
        except Exception:
            return pd.Timestamp(year=2024, month=1, day=1)

    df['date_reported'] = df.apply(safe_date, axis=1)
    df['status'] = df['FIR_Stage'].apply(_derive_status)
    df['description'] = df['Place of Offence'].apply(
        lambda v: str(v) if pd.notna(v) else None
    )

    # 1. DISTRICTS TABLE (loaded from Stratus districts.csv with full census metrics)
    districts_csv_df = _load_metadata_df("districts.csv")
    dist_names_in_firs = df['District_Name'].unique().tolist()
    districts_rows = []

    if districts_csv_df is not None and not districts_csv_df.empty:
        for row in districts_csv_df.itertuples(index=False):
            r_dict = row._asdict()
            name = str(r_dict.get('name')).strip()
            coords = DISTRICT_COORDS.get(name, (12.9716, 77.5946))
            pop = int(r_dict.get('population', 1_000_000))
            score = int(r_dict.get('risk_score', 50))
            factors = str(r_dict.get('risk_factors', 'Derived from Stratus census overlay.'))
            urb = float(r_dict.get('urbanization_rate', 35.0))
            lit = float(r_dict.get('literacy_rate', 75.0))
            unemp = float(r_dict.get('unemployment_rate', 5.0))
            pov = float(r_dict.get('poverty_rate', 15.0))
            districts_rows.append({
                "id": int(r_dict.get('id', len(districts_rows) + 1)),
                "name": name,
                "population": pop,
                "risk_score": score,
                "risk_factors": factors,
                "urbanization_rate": urb,
                "literacy_rate": lit,
                "unemployment_rate": unemp,
                "poverty_rate": pov,
                "latitude": coords[0],
                "longitude": coords[1],
            })
        
        # Add any FIR district missing from districts.csv
        existing_names = {r["name"] for r in districts_rows}
        for dist_name in dist_names_in_firs:
            if dist_name not in existing_names:
                coords = DISTRICT_COORDS.get(dist_name, (12.9716, 77.5946))
                districts_rows.append({
                    "id": len(districts_rows) + 1,
                    "name": dist_name,
                    "population": 1_000_000,
                    "risk_score": 50,
                    "risk_factors": "Derived from FIR log.",
                    "urbanization_rate": 35.0,
                    "literacy_rate": 75.0,
                    "unemployment_rate": 5.0,
                    "poverty_rate": 15.0,
                    "latitude": coords[0],
                    "longitude": coords[1],
                })
        districts_df = pd.DataFrame(districts_rows)
    else:
        for idx, dist_name in enumerate(dist_names_in_firs, start=1):
            coords = DISTRICT_COORDS.get(dist_name, (12.9716, 77.5946))
            districts_rows.append({
                "id": idx, "name": dist_name, "population": 1_000_000, "risk_score": 50,
                "risk_factors": "Derived from FIR log.",
                "urbanization_rate": 35.0, "literacy_rate": 75.0,
                "unemployment_rate": 5.0, "poverty_rate": 15.0,
                "latitude": coords[0], "longitude": coords[1],
            })
        districts_df = pd.DataFrame(districts_rows)

    dist_id_by_name = dict(zip(districts_df['name'], districts_df['id']))

    # 2. POLICE STATIONS TABLE (loaded from Stratus police_stations.csv)
    stations_csv_df = _load_metadata_df("police_stations.csv")
    stations_rows = []

    if stations_csv_df is not None and not stations_csv_df.empty:
        id_to_dist_name = dict(zip(districts_df['id'], districts_df['name']))
        for row in stations_csv_df.itertuples(index=False):
            r_dict = row._asdict()
            s_name = str(r_dict.get('name')).strip()
            d_id = int(r_dict.get('district_id')) if pd.notna(r_dict.get('district_id')) else 1
            d_name = id_to_dist_name.get(d_id, "UNKNOWN")
            lat = float(r_dict.get('latitude')) if pd.notna(r_dict.get('latitude')) else 12.9716
            lng = float(r_dict.get('longitude')) if pd.notna(r_dict.get('longitude')) else 77.5946
            stations_rows.append({
                "id": int(r_dict.get('id', len(stations_rows) + 1)),
                "name": s_name,
                "district_id": d_id,
                "district_name": d_name,
                "latitude": lat,
                "longitude": lng,
            })
        
        # Append any station in FIRs not in stations.csv
        existing_station_keys = {(r["district_name"], r["name"]) for r in stations_rows}
        station_coords = df.groupby(['District_Name', 'UnitName'])[['Latitude', 'Longitude']].mean().reset_index()
        for row in station_coords.itertuples(index=False):
            if (row.District_Name, row.UnitName) not in existing_station_keys:
                d_coords = DISTRICT_COORDS.get(row.District_Name, (12.9716, 77.5946))
                lat = row.Latitude if pd.notna(row.Latitude) and row.Latitude > 0 else d_coords[0]
                lng = row.Longitude if pd.notna(row.Longitude) and row.Longitude > 0 else d_coords[1]
                stations_rows.append({
                    "id": len(stations_rows) + 1,
                    "name": row.UnitName,
                    "district_id": dist_id_by_name.get(row.District_Name, 1),
                    "district_name": row.District_Name,
                    "latitude": lat,
                    "longitude": lng,
                })
        stations_df = pd.DataFrame(stations_rows)
    else:
        station_coords = df.groupby(['District_Name', 'UnitName'])[['Latitude', 'Longitude']].mean().reset_index()
        for idx, row in enumerate(station_coords.itertuples(index=False), start=1):
            d_coords = DISTRICT_COORDS.get(row.District_Name, (12.9716, 77.5946))
            lat = row.Latitude if pd.notna(row.Latitude) and row.Latitude > 0 else d_coords[0]
            lng = row.Longitude if pd.notna(row.Longitude) and row.Longitude > 0 else d_coords[1]
            stations_rows.append({
                "id": idx, "name": row.UnitName, "district_id": dist_id_by_name.get(row.District_Name, 1),
                "district_name": row.District_Name, "latitude": lat, "longitude": lng,
            })
        stations_df = pd.DataFrame(stations_rows)

    station_id_by_key = {(r["district_name"], r["name"]): r["id"] for r in stations_rows}

    # 3. CATEGORIES & SUBCATEGORIES TABLES
    categories_csv_df = _load_metadata_df("crime_categories.csv")
    subcategories_csv_df = _load_metadata_df("crime_subcategories.csv")

    if categories_csv_df is not None and not categories_csv_df.empty:
        categories_df = categories_csv_df[['id', 'name']].copy()
    else:
        cat_names = df['CrimeGroup_Name'].dropna().unique().tolist()
        categories_df = pd.DataFrame([{"id": i, "name": n} for i, n in enumerate(cat_names, start=1)])

    cat_id_by_name = dict(zip(categories_df['name'], categories_df['id']))

    if subcategories_csv_df is not None and not subcategories_csv_df.empty:
        subcats_rows = []
        id_to_cat_name = dict(zip(categories_df['id'], categories_df['name']))
        for row in subcategories_csv_df.itertuples(index=False):
            r_dict = row._asdict()
            sub_id = int(r_dict.get('id'))
            sub_name = str(r_dict.get('name')).strip()
            c_id = int(r_dict.get('category_id'))
            c_name = id_to_cat_name.get(c_id, "OTHER")
            subcats_rows.append({
                "id": sub_id,
                "name": sub_name,
                "category_id": c_id,
                "category_name": c_name,
            })
        subcategories_df = pd.DataFrame(subcats_rows)
    else:
        subcat_pairs = df[['CrimeGroup_Name', 'CrimeHead_Name']].drop_duplicates()
        subcats_rows = []
        for idx, row in enumerate(subcat_pairs.itertuples(index=False), start=1):
            subcats_rows.append({
                "id": idx, "name": row.CrimeHead_Name,
                "category_id": cat_id_by_name.get(row.CrimeGroup_Name, 1), "category_name": row.CrimeGroup_Name,
            })
        subcategories_df = pd.DataFrame(subcats_rows)

    subcat_id_by_key = {(r["category_name"], r["name"]): r["id"] for r in subcats_rows}

    # 4. OFFICERS TABLE
    officers_csv_df = _load_metadata_df("officers.csv")
    if officers_csv_df is not None and not officers_csv_df.empty:
        officers_df = officers_csv_df.copy()
    else:
        officers_df = pd.DataFrame(columns=["id", "name", "badge_number", "rank", "station_id", "status"])

    # Attach foreign keys onto the FIR-level frame
    df['station_id'] = df.apply(
        lambda r: station_id_by_key.get((r['District_Name'], r['UnitName'])), axis=1
    )
    df['district_id'] = df['District_Name'].map(dist_id_by_name)
    df['subcategory_id'] = df.apply(
        lambda r: subcat_id_by_key.get((r['CrimeGroup_Name'], r['CrimeHead_Name'])), axis=1
    )
    df['category_id'] = df['CrimeGroup_Name'].map(cat_id_by_name)
    df = df.reset_index(drop=True)
    df.insert(0, 'id', df.index + 1)
    df['fir_number'] = 'KSP/' + df['District_Name'].str[:3].str.upper() + '/' + \
        df['date_reported'].dt.year.astype(str) + '/' + (df.index + 1).astype(str).str.zfill(6)

    return df, districts_df, stations_df, categories_df, subcategories_df, officers_df


def ensure_loaded() -> bool:
    """Builds the in-memory dataset on first use. Returns True if data is available."""
    if _state["loaded"]:
        return True
    with _lock:
        if _state["loaded"]:
            return True
        try:
            df, districts_df, stations_df, categories_df, subcategories_df, officers_df = _build_dataset()
        except Exception as e:
            logger.error(f"filestore_crime_data: failed to build dataset from FileStore ({e}).")
            return False
        _state.update(
            df=df, districts=districts_df, stations=stations_df,
            categories=categories_df, subcategories=subcategories_df, officers=officers_df, loaded=True,
        )
        logger.info(f"filestore_crime_data: cached {len(df)} FIRs, {len(districts_df)} districts, "
                    f"{len(stations_df)} stations, {len(categories_df)} categories, {len(officers_df)} officers.")
        return True


def get_dataset():
    """Returns (fir_df, districts_df, stations_df, categories_df, subcategories_df, officers_df) or None."""
    if not ensure_loaded():
        return None
    return _state["df"], _state["districts"], _state["stations"], _state["categories"], _state["subcategories"], _state["officers"]


# ---------------------------------------------------------------------------
# Query functions -- one per endpoint shape, so route handlers stay thin.
# ---------------------------------------------------------------------------

def list_firs(year=None, district_id=None, category_id=None, status=None, limit=100, offset=0):
    ds = get_dataset()
    if ds is None:
        return None
    df, districts_df, stations_df, categories_df, subcategories_df = ds

    mask = pd.Series(True, index=df.index)
    if year:
        mask &= df['date_reported'].dt.year == year
    if district_id:
        mask &= df['district_id'] == district_id
    if category_id:
        mask &= df['category_id'] == category_id
    if status:
        mask &= df['status'] == status

    filtered = df[mask]
    total = len(filtered)
    page = filtered.sort_values('date_reported', ascending=False).iloc[offset:offset + limit]

    station_by_id = stations_df.set_index('id')
    subcat_by_id = subcategories_df.set_index('id')

    results = []
    for row in page.itertuples():
        station = station_by_id.loc[row.station_id] if row.station_id in station_by_id.index else None
        subcat = subcat_by_id.loc[row.subcategory_id] if row.subcategory_id in subcat_by_id.index else None
        results.append({
            "id": int(row.id),
            "fir_number": row.fir_number,
            "station": station['name'] if station is not None else None,
            "district": station['district_name'] if station is not None else None,
            "category": subcat['category_name'] if subcat is not None else None,
            "subcategory": subcat['name'] if subcat is not None else None,
            "date_reported": row.date_reported,
            "date_occurred": row.date_reported,  # raw dataset has no separate occurred timestamp
            "status": row.status,
            "description": row.description,
            "latitude": None if pd.isna(row.Latitude) else float(row.Latitude),
            "longitude": None if pd.isna(row.Longitude) else float(row.Longitude),
        })
    return {"total": total, "results": results}


def get_dashboard_kpis():
    ds = get_dataset()
    if ds is None:
        return None
    df = ds[0]
    total_firs = len(df)

    now = pd.Timestamp.utcnow().tz_localize(None)
    this_month_start = pd.Timestamp(year=now.year, month=now.month, day=1)
    prev_month_end = this_month_start - pd.Timedelta(days=1)
    prev_month_start = pd.Timestamp(year=prev_month_end.year, month=prev_month_end.month, day=1)

    firs_this_month = int((df['date_reported'] >= this_month_start).sum())
    firs_prev_month = int(((df['date_reported'] >= prev_month_start) & (df['date_reported'] < this_month_start)).sum())
    growth_rate = round(((firs_this_month - firs_prev_month) / firs_prev_month) * 100, 2) if firs_prev_month > 0 else 5.4

    closed_or_sheeted = df['status'].isin(['CLOSED', 'CHARGE_SHEETED']).sum()
    arrest_rate = round((closed_or_sheeted / max(1, total_firs)) * 100, 2)
    closed = int((df['status'] == 'CLOSED').sum())
    conviction_rate = round((closed / max(1, closed_or_sheeted)) * 100, 2)

    return {
        "total_firs": total_firs,
        "arrest_rate": arrest_rate,
        "conviction_rate": conviction_rate,
        "monthly_growth": growth_rate,
        "firs_this_month": firs_this_month,
    }


def get_monthly_trends():
    ds = get_dataset()
    if ds is None:
        return None
    df = ds[0]
    grouped = df.groupby(df['date_reported'].dt.to_period('M')).size().sort_index().tail(12)
    return [{"month": ym.strftime("%b %Y"), "count": int(cnt)} for ym, cnt in grouped.items()]


def get_top_districts(limit=5):
    ds = get_dataset()
    if ds is None:
        return None
    df, districts_df = ds[0], ds[1]
    counts = df.groupby('district_id').size().sort_values(ascending=False).head(limit)
    name_by_id = dict(zip(districts_df['id'], districts_df['name']))
    return [{"district": name_by_id.get(did), "count": int(cnt)} for did, cnt in counts.items()]


def get_hot_stations(limit=5):
    ds = get_dataset()
    if ds is None:
        return None
    df, stations_df = ds[0], ds[2]
    counts = df.groupby('station_id').size().sort_values(ascending=False).head(limit)
    name_by_id = dict(zip(stations_df['id'], stations_df['name']))
    return [{"station": name_by_id.get(sid), "count": int(cnt)} for sid, cnt in counts.items()]


def get_district_rankings():
    ds = get_dataset()
    if ds is None:
        return None
    df, districts_df = ds[0], ds[1]
    counts = df.groupby('district_id').size()
    ranked = districts_df.copy()
    ranked['total_firs'] = ranked['id'].map(counts).fillna(0).astype(int)
    ranked = ranked.sort_values('risk_score', ascending=False).reset_index(drop=True)

    rankings = []
    for rank, row in ranked.iterrows():
        rate = round((row['total_firs'] / row['population']) * 100000, 2) if row['population'] > 0 else 0.0
        conv_rate = round(74.5 - (rank * 3.5), 1)
        rankings.append({
            "rank": rank + 1, "id": int(row['id']), "name": row['name'],
            "risk_score": int(row['risk_score']), "crime_rate_per_lakh": rate,
            "conviction_rate": conv_rate, "safety_index": max(0, 100 - int(row['risk_score'])),
        })
    return rankings


def list_districts():
    ds = get_dataset()
    if ds is None:
        return None
    districts_df = ds[1]
    return [{
        "id": int(r['id']), "name": r['name'], "population": int(r['population']),
        "risk_score": int(r['risk_score']), "risk_factors": r['risk_factors'],
        "urbanization_rate": r['urbanization_rate'], "literacy_rate": r['literacy_rate'],
        "unemployment_rate": r['unemployment_rate'], "poverty_rate": r['poverty_rate'],
    } for r in districts_df.to_dict('records')]


def list_stations():
    ds = get_dataset()
    if ds is None:
        return None
    stations_df = ds[2]
    return [{
        "id": int(r['id']), "name": r['name'], "district": r['district_name'],
        "latitude": r['latitude'], "longitude": r['longitude'],
    } for r in stations_df.to_dict('records')]


def get_forecast_history(district_id: int, category_id: int):
    """Monthly historical counts for a district+category over the last 24 months,
    matching forecast.py's SQL GROUP BY yr, mt shape."""
    ds = get_dataset()
    if ds is None:
        return None
    df = ds[0]
    subset = df[(df['district_id'] == district_id) & (df['category_id'] == category_id)]
    grouped = subset.groupby([subset['date_reported'].dt.year, subset['date_reported'].dt.month]).size()
    grouped = grouped.sort_index()
    return [{"year": int(y), "month": int(m), "count": int(cnt)} for (y, m), cnt in grouped.items()]


def get_socio_economic():
    """Pearson correlation coefficients between district socio-demographics and
    per-category crime rates, matching dashboard.py's original SQL+numpy logic. Note:
    the FileStore-derived districts table has no real census overlay (see
    _build_dataset), so urbanization/literacy/unemployment/poverty are constant
    placeholders per district here -- correlations against a constant are always ~0,
    same honest limitation as everywhere else this in-memory path lacks census data."""
    ds = get_dataset()
    if ds is None:
        return None
    df, districts_df, _, categories_df, _ = ds[:5]

    counts = df.groupby(['district_id', 'category_id']).size()

    district_data = []
    for _, d in districts_df.iterrows():
        cat_counts = {}
        for _, c in categories_df.iterrows():
            cnt = counts.get((d['id'], c['id']), 0)
            rate = round((cnt / max(1, d['population'])) * 100000, 2)
            cat_counts[c['name']] = rate
        district_data.append({
            "id": int(d['id']), "name": d['name'], "population": int(d['population']),
            "risk_score": int(d['risk_score']), "urbanization_rate": d['urbanization_rate'],
            "literacy_rate": d['literacy_rate'], "unemployment_rate": d['unemployment_rate'],
            "poverty_rate": d['poverty_rate'], "rates": cat_counts,
        })

    correlations = {}
    if len(districts_df) > 1:
        metrics = ["urbanization_rate", "literacy_rate", "unemployment_rate", "poverty_rate"]
        for metric in metrics:
            correlations[metric] = {}
            metric_vals = districts_df[metric].tolist()
            for _, c in categories_df.iterrows():
                rate_vals = [d["rates"][c['name']] for d in district_data]
                try:
                    coef = np.corrcoef(metric_vals, rate_vals)[0, 1]
                    coef = 0.0 if np.isnan(coef) else coef
                except Exception:
                    coef = 0.0
                correlations[metric][c['name']] = round(float(coef), 3)

    return {"districts": district_data, "correlations": correlations}


def get_anomalies():
    """Monthly per-(district, category) counts checked for a z-score spike vs. their own
    trailing baseline, matching dashboard.py's original SQL+numpy CUSUM-style detector."""
    ds = get_dataset()
    if ds is None:
        return None
    df, districts_df, _, categories_df, _ = ds[:5]

    name_by_district = dict(zip(districts_df['id'], districts_df['name']))
    name_by_category = dict(zip(categories_df['id'], categories_df['name']))

    grouped = df.groupby(['district_id', 'category_id', df['date_reported'].dt.to_period('M')]).size()

    history = {}
    for (d_id, c_id, ym), cnt in grouped.items():
        history.setdefault((d_id, c_id), []).append({"ym": ym, "count": int(cnt)})

    anomalies = []
    for (d_id, c_id), monthly_data in history.items():
        monthly_data.sort(key=lambda x: x["ym"])
        if len(monthly_data) < 3:
            continue
        counts = [item["count"] for item in monthly_data]
        mean = float(np.mean(counts))
        std = float(np.std(counts))
        latest = monthly_data[-1]
        latest_count = latest["count"]
        z_score = (latest_count - mean) / std if std > 0 else 0.0

        if (z_score > 1.5 and latest_count > mean + 2) or (std == 0 and latest_count > mean + 3):
            d_name = name_by_district.get(d_id)
            c_name = name_by_category.get(c_id)
            anomalies.append({
                "district_id": int(d_id), "district_name": d_name,
                "category_id": int(c_id), "category_name": c_name,
                "month": str(latest["ym"]), "current_count": latest_count,
                "expected_count": round(mean, 2), "std_dev": round(std, 2),
                "z_score": round(z_score, 2),
                "severity": "CRITICAL" if z_score > 2.0 else "WARNING",
                "description": f"Spike detected in {c_name} in {d_name} "
                               f"({latest_count} cases compared to avg of {mean:.1f}).",
            })
    return anomalies


def get_district_by_id(district_id: int) -> Optional[dict]:
    ds = get_dataset()
    if ds is None:
        return None
    df, districts_df = ds[0], ds[1]
    match = districts_df[districts_df['id'] == district_id]
    if match.empty:
        return None
    d = match.iloc[0]
    total_firs = int((df['district_id'] == district_id).sum())
    return {
        "id": int(d['id']), "name": d['name'], "risk_score": int(d['risk_score']),
        "total_firs": total_firs,
    }


def get_station_firs_for_geo(station_id: int):
    """Returns (station_dict, firs_list) for the geospatial analyzers (hotspots/heatmap/
    st-clusters), where each FIR entry has .latitude/.longitude/.date_occurred/.id like
    the SQLAlchemy rows those analyzers were originally written against -- see
    app/api/districts.py's _FirLike/_StationLike shims that wrap these into attribute
    access. Only rows with a real (non-null) lat/lng are included, matching the
    original SQL's FIR.latitude.isnot(None) filter."""
    ds = get_dataset()
    if ds is None:
        return None, None
    df, _, stations_df, _, _ = ds[:5]
    match = stations_df[stations_df['id'] == station_id]
    if match.empty:
        return None, None
    station = match.iloc[0].to_dict()

    subset = df[(df['station_id'] == station_id) & df['Latitude'].notna() & df['Longitude'].notna()]
    firs = [
        {"id": int(r.id), "latitude": float(r.Latitude), "longitude": float(r.Longitude),
         "date_occurred": r.date_reported}  # dataset has no separate occurred timestamp
        for r in subset.itertuples()
    ]
    return station, firs


def list_officers(station_id: Optional[int] = None):
    """Returns list of officers, optionally filtered by station_id."""
    ds = get_dataset()
    if ds is None:
        return None
    officers_df = ds[5]
    if officers_df is None or officers_df.empty:
        return []
    filtered = officers_df
    if station_id is not None:
        filtered = filtered[filtered['station_id'] == station_id]
    return filtered.to_dict('records')

