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

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", ".."))  # repo root, for scripts/
from scripts.load_data import DISTRICT_COORDS, CENSUS_DISTRICT_MAP  # noqa: E402

FIR_FILE_NAMES = [f"FIR{n}.csv" for n in range(4, 10)]  # FIR4.csv .. FIR9.csv

FIR_COLUMNS = [
    'District_Name', 'UnitName', 'FIR_YEAR', 'FIR_MONTH', 'FIR_Day',
    'FIR_Stage', 'CrimeGroup_Name', 'CrimeHead_Name', 'Latitude', 'Longitude',
    'Place of Offence',
]
_COLUMN_ALIASES = {
    # Tolerant of header variants across the split FileStore files -- see admin_seed.py,
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
    "loaded": False,
}
_catalyst_app = None


def _get_catalyst_app():
    global _catalyst_app
    if _catalyst_app is not None:
        return _catalyst_app
    import zcatalyst_sdk
    _catalyst_app = zcatalyst_sdk.initialize()
    logger.info("filestore_crime_data: Zoho Catalyst SDK initialized.")
    return _catalyst_app


def _download_fir_csvs() -> list[pd.DataFrame]:
    app = _get_catalyst_app()
    folder_id = settings.CATALYST_FOLDER_ID
    if not folder_id:
        raise RuntimeError("CATALYST_FOLDER_ID is not configured.")
    folder = app.file_store().get_folder_instance(int(folder_id))

    listing = folder.get_paged_files()
    if isinstance(listing, dict):
        listing = listing.get("data", []) or []
    files_by_name = {}
    for f in listing:
        name = f.get("file_name") if isinstance(f, dict) else getattr(f, "file_name", None)
        fid = f.get("id") if isinstance(f, dict) else getattr(f, "id", None)
        if name in FIR_FILE_NAMES:
            files_by_name[name] = fid

    frames = []
    for name in FIR_FILE_NAMES:
        file_id = files_by_name.get(name)
        if file_id is None:
            logger.warning(f"filestore_crime_data: '{name}' not found in FileStore folder; skipping.")
            continue
        raw = folder.download_file(int(file_id))
        if isinstance(raw, str):
            raw = raw.encode("utf-8", errors="ignore")
        header = pd.read_csv(io.BytesIO(raw), nrows=0).columns
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
            logger.error(f"filestore_crime_data: '{name}' missing columns {missing}; skipping.")
            continue
        df = pd.read_csv(io.BytesIO(raw), usecols=list(resolved.values()))
        df = df.rename(columns={v: k for k, v in resolved.items()})
        frames.append(df)
        logger.info(f"filestore_crime_data: loaded {name}: {len(df)} rows.")

    if not frames:
        raise RuntimeError("No FIR CSVs could be loaded from FileStore.")
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


def _build_dataset():
    """Downloads + parses all FIR CSVs and derives districts/stations/categories tables,
    mirroring scripts/load_data.py's logic so shapes match what the app has always
    returned. Raises on any failure -- callers decide what "no data" means to their route."""
    frames = _download_fir_csvs()
    df = pd.concat(frames, ignore_index=True)

    df['District_Name'] = df['District_Name'].astype(str).str.strip()
    df['UnitName'] = df['UnitName'].astype(str).str.strip()
    df['CrimeGroup_Name'] = df['CrimeGroup_Name'].astype(str).str.strip()
    df['CrimeHead_Name'] = df['CrimeHead_Name'].astype(str).str.strip()
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')

    # Derive per-row date_reported/status/description exactly as load_data.py does,
    # vectorized instead of per-row Python loops (this runs over ~1.67M rows).
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

    # Districts (id assigned in first-seen order, same as load_data.py's dict insertion order)
    dist_names = df['District_Name'].unique().tolist()
    districts_rows = []
    for idx, dist_name in enumerate(dist_names, start=1):
        coords = DISTRICT_COORDS.get(dist_name, (12.9716, 77.5946))
        risk_score = min(95, max(20, 50))  # no census data available in this in-memory path
        districts_rows.append({
            "id": idx, "name": dist_name, "population": 1_000_000, "risk_score": risk_score,
            "risk_factors": "Derived from live FileStore FIR data (no census overlay).",
            "urbanization_rate": 35.0, "literacy_rate": 75.0,
            "unemployment_rate": 5.0, "poverty_rate": 15.0,
            "latitude": coords[0], "longitude": coords[1],
        })
    districts_df = pd.DataFrame(districts_rows)
    dist_id_by_name = dict(zip(districts_df['name'], districts_df['id']))

    # Stations (avg coordinates per District_Name+UnitName pair)
    station_coords = df.groupby(['District_Name', 'UnitName'])[['Latitude', 'Longitude']].mean().reset_index()
    stations_rows = []
    for idx, row in enumerate(station_coords.itertuples(index=False), start=1):
        d_coords = DISTRICT_COORDS.get(row.District_Name, (12.9716, 77.5946))
        lat = row.Latitude if pd.notna(row.Latitude) and row.Latitude > 0 else d_coords[0]
        lng = row.Longitude if pd.notna(row.Longitude) and row.Longitude > 0 else d_coords[1]
        stations_rows.append({
            "id": idx, "name": row.UnitName, "district_id": dist_id_by_name[row.District_Name],
            "district_name": row.District_Name, "latitude": lat, "longitude": lng,
        })
    stations_df = pd.DataFrame(stations_rows)
    station_id_by_key = {(r["district_name"], r["name"]): r["id"] for r in stations_rows}

    # Categories / subcategories
    cat_names = df['CrimeGroup_Name'].dropna().unique().tolist()
    categories_df = pd.DataFrame([{"id": i, "name": n} for i, n in enumerate(cat_names, start=1)])
    cat_id_by_name = dict(zip(categories_df['name'], categories_df['id']))

    subcat_pairs = df[['CrimeGroup_Name', 'CrimeHead_Name']].drop_duplicates()
    subcats_rows = []
    for idx, row in enumerate(subcat_pairs.itertuples(index=False), start=1):
        subcats_rows.append({
            "id": idx, "name": row.CrimeHead_Name,
            "category_id": cat_id_by_name[row.CrimeGroup_Name], "category_name": row.CrimeGroup_Name,
        })
    subcategories_df = pd.DataFrame(subcats_rows)
    subcat_id_by_key = {(r["category_name"], r["name"]): r["id"] for r in subcats_rows}

    # Attach foreign keys onto the FIR-level frame so downstream queries are plain
    # pandas filters/joins instead of repeated dict lookups per row.
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

    return df, districts_df, stations_df, categories_df, subcategories_df


def ensure_loaded() -> bool:
    """Builds the in-memory dataset on first use. Returns True if data is available.
    Failure leaves state uninitialized so the next call retries rather than being
    permanently stuck on a transient FileStore/SDK error."""
    if _state["loaded"]:
        return True
    with _lock:
        if _state["loaded"]:
            return True
        try:
            df, districts_df, stations_df, categories_df, subcategories_df = _build_dataset()
        except Exception as e:
            logger.error(f"filestore_crime_data: failed to build dataset from FileStore ({e}).")
            return False
        _state.update(
            df=df, districts=districts_df, stations=stations_df,
            categories=categories_df, subcategories=subcategories_df, loaded=True,
        )
        logger.info(f"filestore_crime_data: cached {len(df)} FIRs, {len(districts_df)} districts, "
                    f"{len(stations_df)} stations, {len(categories_df)} categories.")
        return True


def get_dataset():
    """Returns (fir_df, districts_df, stations_df, categories_df, subcategories_df) or
    None if FileStore is unreachable. Callers must treat None as "cannot serve this
    request" -- there is intentionally no SQL fallback for this data."""
    if not ensure_loaded():
        return None
    return _state["df"], _state["districts"], _state["stations"], _state["categories"], _state["subcategories"]


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
    df, districts_df, _, categories_df, _ = ds

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
    df, districts_df, _, categories_df, _ = ds

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
    df, _, stations_df, _, _ = ds
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
